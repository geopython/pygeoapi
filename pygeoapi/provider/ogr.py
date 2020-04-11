# =================================================================
#
# Authors: Just van den Broecke <justb4@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2019 Just van den Broecke
# Copyright (c) 2020 Francesco Bartoli
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

import importlib
import logging
import functools
from typing import Any

from osgeo import gdal as osgeo_gdal
from osgeo import ogr as osgeo_ogr
from osgeo import osr as osgeo_osr

from pygeoapi.provider.base import (
    BaseProvider, ProviderGenericError, ProviderQueryError)

LOGGER = logging.getLogger(__name__)


class OGRProvider(BaseProvider):
    """
    OGR Provider. Uses GDAL/OGR Python-bindings to access OGR
    Vector sources. References:
    https://pcjericks.github.io/py-gdalogr-cookbook/
    https://www.gdal.org/ogr_formats.html (per-driver specifics).

    In theory any OGR source type (Driver) could be used, although
    some Source Types are Driver-specific handling. This is handled
    in Source Helper classes, instantiated per Source-Type.

    The following Source Types have been tested to work:
    GeoPackage (GPKG), SQLite, GeoJSON, ESRI Shapefile, WFS v2.
    """

    # To deal with some OGR Source-Driver specifics.
    SOURCE_HELPERS = {
        'ESRIJSON': 'pygeoapi.provider.ogr.ESRIJSONHelper',
        'WFS': 'pygeoapi.provider.ogr.WFSHelper',
        '*': 'pygeoapi.provider.ogr.CommonSourceHelper'
    }

    # Setting for traditional CRS axis order.
    OAMS_TRADITIONAL_GIS_ORDER = osgeo_osr.OAMS_TRADITIONAL_GIS_ORDER

    def __init__(self, provider_def):
        """
        Initialize object

        # Typical OGRProvider YAML config:

        provider:
            name: OGR
            data:
                source_type: WFS
                source: WFS:http://geodata.nationaalgeoregister.nl/rdinfo/wfs?
                source_srs: EPSG:28992
                target_srs: EPSG:4326
                source_capabilities:
                    paging: True
                source_options:
                    OGR_WFS_LOAD_MULTIPLE_LAYER_DEFN: NO
                # open_options:
                    # EXPOSE_GML_ID: NO
                gdal_ogr_options:
                    EMPTY_AS_NULL: NO
                    GDAL_CACHEMAX: 64
                    # GDAL_HTTP_PROXY: (optional proxy)
                    # GDAL_PROXY_AUTH: (optional auth for remote WFS)
                    CPL_DEBUG: NO

            id_field: gml_id
            layer: rdinfo:stations


        :param provider_def: provider definition

        :returns: pygeoapi.providers.ogr.OGRProvider
        """

        BaseProvider.__init__(self, provider_def)

        self.ogr = osgeo_ogr
        # http://trac.osgeo.org/gdal/wiki/PythonGotchas
        self.gdal = osgeo_gdal
        LOGGER.info("Using GDAL/OGR version: %d"
                    % int(osgeo_gdal.VersionInfo('VERSION_NUM')))

        # install error handler
        err = GdalErrorHandler()
        self.handler = err.handler
        self.gdal.PushErrorHandler(self.handler)
        # Exceptions will get raised on anything >= gdal.CE_Failure
        self.gdal.UseExceptions()
        LOGGER.debug('Setting OGR properties')

        self.data_def = provider_def['data']

        # Generic GDAL/OGR options (optional)
        gdal_ogr_options = self.data_def.get('gdal_ogr_options', {})
        for key in gdal_ogr_options:
            self.gdal.SetConfigOption(key, str(gdal_ogr_options[key]))

        # Driver-specific options (optional)
        source_options = self.data_def.get('source_options', {})
        for key in source_options:
            self.gdal.SetConfigOption(key, str(source_options[key]))
        # Open options
        self.open_options = self.data_def.get('open_options', {})

        self.source_capabilities = self.data_def.get('source_capabilities',
                                                     {'paging': False})

        self.source_srs = int(self.data_def.get('source_srs',
                                                'EPSG:4326').split(':')[1])
        self.target_srs = int(self.data_def.get('target_srs',
                                                'EPSG:4326').split(':')[1])

        # Optional coordinate transformation inward (requests) and
        # outward (responses) when the source layers and WFS3 collections
        # differ in EPSG-codes.
        self.transform_in = None
        self.transform_out = None
        if self.source_srs != self.target_srs:
            source = osgeo_osr.SpatialReference()
            source.SetAxisMappingStrategy(
                OGRProvider.OAMS_TRADITIONAL_GIS_ORDER)
            source.ImportFromEPSG(self.source_srs)

            target = osgeo_osr.SpatialReference()
            target.SetAxisMappingStrategy(
                OGRProvider.OAMS_TRADITIONAL_GIS_ORDER)
            target.ImportFromEPSG(self.target_srs)

            self.transform_in = \
                osgeo_osr.CoordinateTransformation(target, source)
            self.transform_out = \
                osgeo_osr.CoordinateTransformation(source, target)

        self._load_source_helper(self.data_def['source_type'])

        # Layer name is required
        self.layer_name = provider_def.get('layer', None)
        if not self.layer_name:
            msg = 'Need explicit \'layer\' attr in provider config'
            LOGGER.error(msg)
            raise Exception(msg)

        # Init driver and Source connection
        self.driver = None
        self.conn = None

    def _list_open_options(self):
        return [
            f"{key}={str(value)}" for key, value in self.open_options.items()]

    def _open(self):
        source_type = self.data_def['source_type']
        self.driver = self.ogr.GetDriverByName(source_type)
        if not self.driver:
            msg = 'No Driver for Source: {}'.format(source_type)
            LOGGER.error(msg)
            raise Exception(msg)
        if self.open_options:
            try:
                self.conn = self.gdal.OpenEx(
                    self.data_def['source'],
                    self.gdal.OF_VECTOR,
                    open_options=self._list_open_options())
            except Exception:
                msg = 'Ignore errors during the connection for Driver \
                    {}'.format(source_type)
                LOGGER.error(msg)
                self.conn = _ignore_gdal_error(
                    self.gdal, 'OpenEx', self.data_def['source'],
                    self.gdal.OF_VECTOR,
                    open_options=self._list_open_options())
        else:
            try:
                self.conn = self.driver.Open(self.data_def['source'], 0)
            except Exception:
                msg = 'Ignore errors during the connection for Driver \
                    {}'.format(source_type)
                LOGGER.error(msg)
                # ignore errors for ESRIJSON not having geometry member
                # see https://github.com/OSGeo/gdal/commit/38b0feed67f80ded32be6c508323d862e1a14474 # noqa 
                self.conn = _ignore_gdal_error(
                    self.driver, 'Open', self.data_def['source'], 0)
        if not self.conn:
            msg = 'Cannot open OGR Source: %s' % self.data_def['source']
            LOGGER.error(msg)
            raise Exception(msg)

        # Always need to disable paging immediately after Open!
        if self.source_capabilities['paging']:
            self.source_helper.disable_paging()

    def _close(self):
        self.source_helper.close()
        self.conn = None
        LOGGER.debug('closed self.conn')

        self.driver = None

    def _get_layer(self):
        if not self.conn:
            self._open()

        # Delegate getting Layer to SourceHelper
        return self.source_helper.get_layer()

    def get_fields(self):
        """
        Get provider field information (names, types)

        :returns: dict of fields
        """

        fields = {}
        try:
            layer_defn = self._get_layer().GetLayerDefn()
            for fld in range(layer_defn.GetFieldCount()):
                field_defn = layer_defn.GetFieldDefn(fld)
                fieldName = field_defn.GetName()
                fieldTypeCode = field_defn.GetType()
                fieldType = field_defn.GetFieldTypeName(fieldTypeCode)
                fields[fieldName] = fieldType.lower()
                # fieldWidth = layer_defn.GetFieldDefn(fld).GetWidth()
                # GetPrecision = layer_defn.GetFieldDefn(fld).GetPrecision()

        except Exception as err:
            LOGGER.error(err)

        finally:
            self._close()

        return fields

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime=None, properties=[], sortby=[]):
        """
        Query OGR source

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)

        :returns: dict of 0..n GeoJSON features
        """
        result = None
        try:
            if self.source_capabilities['paging']:
                self.source_helper.enable_paging(startindex, limit)

            layer = self._get_layer()

            if bbox:
                LOGGER.debug('processing bbox parameter')
                minx, miny, maxx, maxy = bbox

                wkt = "POLYGON (({minx} {miny},{minx} {maxy},{maxx} {maxy}," \
                      "{maxx} {miny},{minx} {miny}))".format(
                        minx=float(minx), miny=float(miny),
                        maxx=float(maxx), maxy=float(maxy))

                polygon = self.ogr.CreateGeometryFromWkt(wkt)
                if self.transform_in:
                    polygon.Transform(self.transform_in)

                layer.SetSpatialFilter(polygon)

                # layer.SetSpatialFilterRect(
                # float(minx), float(miny), float(maxx), float(maxy))

            # Make response based on resulttype specified
            if resulttype == 'hits':
                LOGGER.debug('hits only specified')
                result = self._response_feature_hits(layer)
            elif resulttype == 'results':
                LOGGER.debug('results specified')
                result = self._response_feature_collection(layer, limit)
            else:
                LOGGER.error('Invalid resulttype: %s' % resulttype)

        except RuntimeError as err:
            LOGGER.error(err)
            raise ProviderQueryError(err)
        except Exception as err:
            LOGGER.error(err)
            raise ProviderGenericError(err)

        finally:
            self._close()

        return result

    def get(self, identifier):
        """
        Get Feature by id

        :param identifier: feature id

        :returns: feature collection
        """
        result = None
        try:
            LOGGER.debug('Fetching identifier {}'.format(identifier))
            layer = self._get_layer()

            layer.SetAttributeFilter("{field} = '{id}'".format(
                field=self.id_field, id=identifier))

            ogr_feature = self._get_next_feature(layer)
            result = self._ogr_feature_to_json(ogr_feature)

        except RuntimeError as err:
            LOGGER.error(err)
            raise ProviderQueryError(err)
        except Exception as err:
            LOGGER.error(err)
            raise ProviderGenericError(err)

        finally:
            self._close()

        return result

    def __repr__(self):
        return '<OGRProvider> {}'.format(self.data)

    def _load_source_helper(self, source_type):
        """
        Loads Source Helper by name.

        :param Source type: Source type name

        :returns: Source Helper object
        """
        helper_type = source_type
        if source_type not in OGRProvider.SOURCE_HELPERS.keys():
            helper_type = '*'

        # Create object from full package.class name string.
        source_helper_class = OGRProvider.SOURCE_HELPERS[helper_type]

        packagename, classname = source_helper_class.rsplit('.', 1)
        module = importlib.import_module(packagename)
        class_ = getattr(module, classname)
        self.source_helper = class_(self)

    def _get_next_feature(self, layer):
        try:
            # Ignore gdal error
            next_feature = _ignore_gdal_error(layer, 'GetNextFeature')
            if all(val is None for val in next_feature.items().values()):
                self.gdal.Error(
                    self.gdal.CE_Failure, 1, "Object properties are all null"
                )
            return next_feature
        except RuntimeError as gdalerr:
            LOGGER.error(self.gdal.GetLastErrorMsg())
            raise gdalerr

    def _ogr_feature_to_json(self, ogr_feature):
        geom = ogr_feature.GetGeometryRef()
        if self.transform_out:
            # Optionally reproject the geometry
            geom.Transform(self.transform_out)

        json_feature = ogr_feature.ExportToJson(as_object=True)
        try:
            json_feature['id'] = json_feature['properties'].pop(self.id_field)
        except Exception as err:
            LOGGER.error(err)
            json_feature['id'] = ogr_feature.GetFID()

        return json_feature

    def _response_feature_collection(self, layer, limit):
        """
        Assembles output from Layer query as
        GeoJSON FeatureCollection structure.

        :returns: GeoJSON FeatureCollection
        """

        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        # See https://github.com/OSGeo/gdal/blob/master/autotest/
        #     ogr/ogr_wfs.py#L313
        layer.ResetReading()

        try:
            # Ignore gdal error
            ogr_feature = _ignore_gdal_error(layer, 'GetNextFeature')
            count = 0
            while ogr_feature is not None:
                json_feature = self._ogr_feature_to_json(ogr_feature)

                feature_collection['features'].append(json_feature)

                count += 1
                if count == limit:
                    break

                # Ignore gdal error
                ogr_feature = _ignore_gdal_error(layer, 'GetNextFeature')

            return feature_collection
        except RuntimeError as gdalerr:
            LOGGER.error(self.gdal.GetLastErrorMsg())
            raise gdalerr

    def _response_feature_hits(self, layer):
        """
        Assembles GeoJSON hits from OGR Feature count
        e.g: http://localhost:5000/collections/
        hotosm_bdi_waterways/items?resulttype=hits

        :returns: GeoJSON FeaturesCollection
        """

        return {
            'type': 'FeatureCollection',
            'numberMatched': layer.GetFeatureCount(),
            'features': []
        }


class InvalidHelperError(Exception):
    """Invalid helper"""
    pass


class SourceHelper:
    """
    Helper classes for OGR-specific Source Types (Drivers).
    For some actions Driver-specific settings or processing is
    required. This is delegated to the OGR SourceHelper classes.
    """

    def __init__(self, provider):
        """
        Initialize object with related OGRProvider object.

        :param provider: provider instance

        :returns: pygeoapi.providers.ogr.SourceHelper
        """
        self.provider = provider

    def close(self):
        """
        OGR Driver-specific handling of closing dataset.
        Default is no specific handling.

        """

        pass

    def get_layer(self):
        """
        Default action to get a Layer object from opened OGR Driver.
        :return:
        """
        layer = self.provider.conn.GetLayerByName(self.provider.layer_name)

        if not layer:
            msg = 'Cannot get Layer {} from OGR Source'.\
                format(self.provider.layer_name)
            LOGGER.error(msg)
            raise Exception(msg)

        return layer

    def enable_paging(self, startindex=-1, limit=-1):
        """
        Enable paged access to dataset (OGR Driver-specific)

        """

        pass

    def disable_paging(self):
        """
        Disable paged access to dataset (OGR Driver-specific)
        """

        pass


class CommonSourceHelper(SourceHelper):
    """
    SourceHelper for most common OGR Source types:
    Shapefile, GeoPackage, SQLite, GeoJSON etc.
    """
    def __init__(self, provider):
        """
        Initialize object

        :param provider: provider instance

        :returns: pygeoapi.providers.ogr.SourceHelper
        """
        SourceHelper.__init__(self, provider)
        self.startindex = -1
        self.limit = -1
        self.result_set = None

    def close(self):
        """
        OGR Driver-specific handling of closing dataset.
        If ExecuteSQL has been (successfully) called
        must close ResultSet explicitly.
        https://gis.stackexchange.com/questions/114112/explicitly-close-a-ogr-result-object-from-a-call-to-executesql  # noqa
        """

        if not self.result_set:
            return

        try:
            self.provider.conn.ReleaseResultSet(self.result_set)
        except Exception as err:
            msg = 'ReleaseResultSet exception for Layer {}'.format(
                self.provider.layer_name)
            LOGGER.error(msg, err)
        finally:
            self.result_set = None

    def enable_paging(self, startindex=-1, limit=-1):
        """
        Enable paged access to dataset (OGR Driver-specific)
        using OGR SQL https://www.gdal.org/ogr_sql.html
        e.g. SELECT * FROM poly LIMIT 10 OFFSET 30

        """
        self.startindex = startindex
        self.limit = limit

    def disable_paging(self):
        """
        Disable paged access to dataset (OGR Driver-specific)
        """

        pass

    def get_layer(self):
        """
        Gets OGR Layer from opened OGR dataset.
        When startindex defined 1 or greater will invoke
        OGR SQL SELECT with LIMIT and OFFSET and return
        as Layer as ResultSet from ExecuteSQL on dataset.
        :return: OGR layer object
        """
        if self.startindex <= 0:
            return SourceHelper.get_layer(self)

        self.close()

        sql = "SELECT * FROM {ds_name} LIMIT {limit} OFFSET {offset}".format(
            ds_name=self.provider.layer_name,
            limit=self.limit,
            offset=self.startindex)
        self.result_set = self.provider.conn.ExecuteSQL(sql)

        # Reset since needs to be set each time explicitly
        self.startindex = -1
        self.limit = -1

        if not self.result_set:
            msg = 'Cannot get Layer {} via ExecuteSQL'.format(
                self.provider.layer_name)
            LOGGER.error(msg)
            raise Exception(msg)

        return self.result_set


class ESRIJSONHelper(SourceHelper):

    def __init__(self, provider):
        """
        Initialize object

        :param provider: provider instance

        :returns: pygeoapi.providers.ogr.SourceHelper
        """
        SourceHelper.__init__(self, provider)

    def enable_paging(self, startindex=-1, limit=-1):
        """
        Enable paged access to dataset (OGR Driver-specific)

        """
        if startindex < 0:
            return

        self.provider.open_options.update(FEATURE_SERVER_PAGING=True)
        self.startindex = startindex
        self.limit = limit

    def disable_paging(self):
        """
        Disable paged access to dataset (OGR Driver-specific)
        """

        self.provider.open_options.update(FEATURE_SERVER_PAGING=False)

    def get_layer(self):
        """
        Gets OGR Layer from opened OGR dataset.
        When startindex defined 1 or greater will invoke
        OGR SQL SELECT with LIMIT and OFFSET and return
        as Layer as ResultSet from ExecuteSQL on dataset.
        :return: OGR layer object
        """
        if self.startindex <= 0:
            return SourceHelper.get_layer(self)

        self.close()

        sql = "SELECT * FROM {ds_name} LIMIT {limit} OFFSET {offset}".format(
            ds_name=self.provider.layer_name,
            limit=self.limit,
            offset=self.startindex)
        self.result_set = self.provider.conn.ExecuteSQL(sql)

        # Reset since needs to be set each time explicitly
        self.startindex = -1
        self.limit = -1

        if not self.result_set:
            msg = 'Cannot get Layer {} via ExecuteSQL'.format(
                self.provider.layer_name)
            LOGGER.error(msg)
            raise Exception(msg)

        return self.result_set


class WFSHelper(SourceHelper):

    def __init__(self, provider):
        """
        Initialize object

        :param provider: provider instance

        :returns: pygeoapi.providers.ogr.SourceHelper
        """
        SourceHelper.__init__(self, provider)

    def enable_paging(self, startindex=-1, limit=-1):
        """
        Enable paged access to dataset (OGR Driver-specific)

        """

        if startindex < 0:
            return

        self.provider.gdal.SetConfigOption(
            'OGR_WFS_PAGING_ALLOWED', 'ON')
        self.provider.gdal.SetConfigOption(
            'OGR_WFS_BASE_START_INDEX', str(startindex))
        self.provider.gdal.SetConfigOption(
            'OGR_WFS_PAGE_SIZE', str(limit))

    def disable_paging(self):
        """
        Disable paged access to dataset (OGR Driver-specific)
        """

        self.provider.gdal.SetConfigOption(
            'OGR_WFS_PAGING_ALLOWED', None)
        self.provider.gdal.SetConfigOption(
            'OGR_WFS_PAGE_SIZE', None)


class GdalErrorHandler:

    def __init__(self):
        """
        Initialize the error handler

        :returns: pygeoapi.providers.ogr.GdalErrorHandler
        """
        self.err_level = osgeo_gdal.CE_None
        self.err_num = 0
        self.err_msg = ''

    def handler(self, err_level, err_num, err_msg):
        """
        Define custom GDAL error handler function

        :param err_level: error level
        :param err_num: internal gdal error number
        :param err_msg: error message

        :returns: pygeoapi.providers.ogr.GdalErrorHandler
        """

        err_type = {
            osgeo_gdal.CE_None: 'None',
            osgeo_gdal.CE_Debug: 'Debug',
            osgeo_gdal.CE_Warning: 'Warning',
            osgeo_gdal.CE_Failure: 'Failure',
            osgeo_gdal.CE_Fatal: 'Fatal'
        }
        err_msg = err_msg.replace('\n', ' ')
        level = err_type.get(err_level, 'None')

        self.err_level = err_level
        self.err_num = err_num
        self.err_msg = err_msg

        LOGGER.error('Error Number: %s, Type: %s, Msg: %s' % (
            self.err_num, level, self.err_msg))
        last_error = osgeo_gdal.GetLastErrorMsg()
        if self.err_level >= osgeo_gdal.CE_Failure:
            raise ProviderGenericError(last_error)


def _silent_gdal_error(f):
    """
    Decorator function for gdal
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        osgeo_gdal.PushErrorHandler('CPLQuietErrorHandler')
        v = f(*args, **kwargs)
        osgeo_gdal.PopErrorHandler()
        return v

    return wrapper


@_silent_gdal_error
def _ignore_gdal_error(inst, fn, *args, **kwargs) -> Any:
    """
    Evaluate the function with the object instance.

    :param inst: Object instance
    :param fn: String function name
    :param args: List of positional arguments
    :param kwargs: Keyword arguments

    :returns: Any function evaluation result
    """
    value = getattr(inst, fn)(*args, **kwargs)
    return value
