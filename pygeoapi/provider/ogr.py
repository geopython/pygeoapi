# =================================================================
#
# Authors: Just van den Broecke <justb4@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2019 Just van den Broecke
# Copyright (c) 2020 Francesco Bartoli
# Copyright (c) 2022 Tom Kralidis
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

import functools
import importlib
import logging
import os
from typing import Any

from osgeo import gdal as osgeo_gdal
from osgeo import ogr as osgeo_ogr
from osgeo import osr as osgeo_osr

from pygeoapi.provider.base import (
    BaseProvider, ProviderGenericError,
    ProviderQueryError, ProviderConnectionError,
    ProviderItemNotFoundError)

from pygeoapi.util import get_crs_from_uri

LOGGER = logging.getLogger(__name__)


class OGRProvider(BaseProvider):
    """
    OGR Provider. Uses GDAL/OGR Python-bindings to access OGR
    Vector sources. References:
    https://pcjericks.github.io/py-gdalogr-cookbook/
    https://gdal.org/ogr_formats.html (per-driver specifics).

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
    os.environ['OGR_GEOJSON_MAX_OBJ_SIZE'] = os.environ.get(
        'OGR_GEOJSON_MAX_OBJ_SIZE', '20MB')

    def __init__(self, provider_def):
        """
        Initialize object

        # Typical OGRProvider YAML config:

        provider:
            name: OGR
            data:
                source_type: WFS
                source: WFS:https://service.pdok.nl/kadaster/rdinfo/wfs/v1_0?
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

        :returns: pygeoapi.provider.ogr.OGRProvider
        """

        super().__init__(provider_def)

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

        # self.source_srs = int(self.data_def.get('source_srs',
        #                                         'EPSG:4326').split(':')[1])
        # self.target_srs = int(self.data_def.get('target_srs',
        #                                         'EPSG:4326').split(':')[1])
        if self.data_def.get('source_srs') is not None \
                or self.data_def.get('target_srs') is not None:
            LOGGER.warning('source/target_srs no longer supported in OGRProvider') # noqa
            LOGGER.warning('Use crs and storage_crs in config, see docs')

        # Optional coordinate transformation inward (requests) and
        # outward (responses) when the source layers and
        # OGC API - Features collections differ in EPSG-codes.
        self.transform_in = None
        self.transform_out = None
        # if self.source_srs != self.target_srs:
        #     source = self._get_spatial_ref_from_epsg(self.source_srs)
        #     target = self._get_spatial_ref_from_epsg(self.target_srs)
        #
        #     self.transform_in = \
        #         osgeo_osr.CoordinateTransformation(target, source)
        #     self.transform_out = \
        #         osgeo_osr.CoordinateTransformation(source, target)

        self._load_source_helper(self.data_def['source_type'])

        self.geom_field = provider_def.get('geom_field')

        # ID field is required
        self.id_field = provider_def.get('id_field')
        if not self.id_field:
            msg = 'Need explicit \'id_field\' attr in provider config'
            LOGGER.error(msg)
            raise Exception(msg)

        # Layer name is required
        self.layer_name = provider_def.get('layer')
        if not self.layer_name:
            msg = 'Need explicit \'layer\' attr in provider config'
            LOGGER.error(msg)
            raise Exception(msg)

        # Init driver and Source connection
        self.driver = None
        self.conn = None

        LOGGER.debug('Grabbing field information')
        self.fields = self.get_fields()

    def _list_open_options(self):
        return [
            f"{key}={str(value)}" for key, value in self.open_options.items()]

    def _open(self):
        source_type = self.data_def['source_type']
        self.driver = self.ogr.GetDriverByName(source_type)
        if not self.driver:
            msg = f'No Driver for Source: {source_type}'
            LOGGER.error(msg)
            raise Exception(msg)
        if self.open_options:
            try:
                self.conn = self.gdal.OpenEx(
                    self.data_def['source'],
                    self.gdal.OF_VECTOR,
                    open_options=self._list_open_options())
            except RuntimeError as err:
                LOGGER.error(err)
                raise ProviderConnectionError(err)
            except Exception:
                msg = f'Ignore errors during the connection for Driver {source_type}'  # noqa
                LOGGER.error(msg)
                self.conn = _ignore_gdal_error(
                    self.gdal, 'OpenEx', self.data_def['source'],
                    self.gdal.OF_VECTOR,
                    open_options=self._list_open_options())
        else:
            try:
                self.conn = self.driver.Open(self.data_def['source'], 0)
            except RuntimeError as err:
                LOGGER.error(err)
                raise ProviderConnectionError(err)
            except Exception:
                msg = f'Ignore errors during the connection for Driver {source_type}'  # noqa
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

                fieldName2 = fieldType.lower()

                if fieldName2 == 'integer64':
                    fieldName2 = 'integer'
                elif fieldName2 == 'real':
                    fieldName2 = 'number'

                fields[fieldName] = {'type': fieldName2}

                if fieldName2 == 'datetime':
                    fields[fieldName] = {
                        'type': 'string',
                        'format': 'date-time'
                    }

                # fieldWidth = layer_defn.GetFieldDefn(fld).GetWidth()
                # GetPrecision = layer_defn.GetFieldDefn(fld).GetPrecision()

        except RuntimeError as err:
            LOGGER.error(err)
            raise ProviderConnectionError(err)
        except Exception as err:
            LOGGER.error(err)

        finally:
            self._close()

        return fields

    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None,
              crs_transform_spec=None, **kwargs):
        """
        Query OGR source

        :param offset: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param q: full-text search term(s)
        :param crs_transform_spec: `CrsTransformSpec` instance, optional

        :returns: dict of 0..n GeoJSON features
        """
        result = None
        try:
            if self.source_capabilities['paging']:
                self.source_helper.enable_paging(offset, limit)

            layer = self._get_layer()

            if bbox:
                LOGGER.debug('processing bbox parameter')
                minx, miny, maxx, maxy = [float(b) for b in bbox]

                wkt = f"POLYGON (({minx} {miny},{minx} {maxy},{maxx} {maxy}," \
                      f"{maxx} {miny},{minx} {miny}))"

                polygon = self.ogr.CreateGeometryFromWkt(wkt)
                # if self.transform_in:
                #     polygon.Transform(self.transform_in)

                layer.SetSpatialFilter(polygon)

                # layer.SetSpatialFilterRect(
                # float(minx), float(miny), float(maxx), float(maxy))

            if properties:
                LOGGER.debug('processing properties')

                attribute_filter = ' and '.join(
                    map(lambda x: f'{x[0]} = \'{x[1]}\'', properties)
                )

                LOGGER.debug(attribute_filter)

                layer.SetAttributeFilter(attribute_filter)

            # Make response based on resulttype specified
            if resulttype == 'hits':
                LOGGER.debug('hits only specified')
                result = self._response_feature_hits(layer)
            elif resulttype == 'results':
                LOGGER.debug('results specified')
                result = self._response_feature_collection(
                    layer,
                    limit,
                    skip_geometry=skip_geometry,
                    crs_transform_spec=crs_transform_spec,
                )
            else:
                LOGGER.error('Invalid resulttype: %s' % resulttype)

        except RuntimeError as err:
            LOGGER.error(err)
            raise ProviderQueryError(err)
        except ProviderConnectionError as err:
            LOGGER.error(err)
            raise ProviderConnectionError(err)
        except Exception as err:
            LOGGER.error(err)
            raise ProviderGenericError(err)

        finally:
            self._close()

        return result

    def _get_spatial_ref_from_epsg(self, epsg_code, force_auth_comply=False):
        axis_order = osgeo_osr.OAMS_AUTHORITY_COMPLIANT
        # Assume http://www.opengis.net/def/crs/OGC/1.3/CRS84
        # for EPSG:4326, GeoJSON Compliant
        if epsg_code == 4326 and not force_auth_comply:
            axis_order = osgeo_osr.OAMS_TRADITIONAL_GIS_ORDER
        spatial_ref = osgeo_osr.SpatialReference()
        spatial_ref.SetAxisMappingStrategy(axis_order)
        spatial_ref.ImportFromEPSG(epsg_code)
        return spatial_ref

    def _get_spatial_ref_from_uri(self, crs_uri):
        # Assume http://www.opengis.net/def/crs/OGC/1.3/CRS84
        # is EPSG:4326, with lon/lat order
        if crs_uri == 'http://www.opengis.net/def/crs/OGC/1.3/CRS84':
            epsg_code = 4326
            force_auth_comply = False
        else:
            pyproj_crs = get_crs_from_uri(crs_uri)
            epsg_code = int(pyproj_crs.srs.split(':')[1])
            force_auth_comply = True
        return self._get_spatial_ref_from_epsg(
            epsg_code, force_auth_comply=force_auth_comply)

    def _get_crs_transform(self, crs_transform_spec=None):
        if crs_transform_spec is not None:
            source = self._get_spatial_ref_from_uri(
                crs_transform_spec.source_crs_uri)
            target = self._get_spatial_ref_from_uri(
                crs_transform_spec.target_crs_uri)
            crs_transform = osgeo_osr.CoordinateTransformation(source, target)
        else:
            crs_transform = None
        return crs_transform

    def get(self, identifier, crs_transform_spec=None, **kwargs):
        """
        Get Feature by id

        :param identifier: feature id
        :param crs_transform_spec: `CrsTransformSpec` instance, optional

        :returns: feature collection
        """
        result = None
        crs_transform_out = self._get_crs_transform(crs_transform_spec)

        # Keep support for source_srs/target_srs
        # if crs_transform_out is None:
        #     crs_transform_out = self.transform_out
        try:
            LOGGER.debug(f'Fetching identifier {identifier}')
            layer = self._get_layer()

            layer.SetAttributeFilter(f"{self.id_field} = '{identifier}'")

            ogr_feature = self._get_next_feature(layer, identifier)
            result = self._ogr_feature_to_json(
                ogr_feature, crs_transform_out=crs_transform_out,
            )

        except RuntimeError as err:
            LOGGER.error(err)
            raise ProviderQueryError(err)
        except ProviderConnectionError as err:
            LOGGER.error(err)
            raise ProviderConnectionError(err)
        except ProviderItemNotFoundError as err:
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)
        except Exception as err:
            LOGGER.error(err)
            raise ProviderGenericError(err)

        finally:
            self._close()

        return result

    def __repr__(self):
        return f'<OGRProvider> {self.data}'

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

    def _get_next_feature(self, layer, feature_id):
        try:
            if layer.GetFeatureCount() == 0:
                msg = f"item {feature_id} is not found"
                LOGGER.error(msg)
                raise ProviderItemNotFoundError(msg)
            # Ignore gdal error
            next_feature = _ignore_gdal_error(layer, 'GetNextFeature')
            if next_feature:
                if all(val is None for val in next_feature.items().values()):
                    self.gdal.Error(
                        self.gdal.CE_Failure, 1,
                        "Object properties are all null"
                    )
            else:
                raise RuntimeError(
                    f"GDAL has returned a null feature for item {feature_id}")
            return next_feature
        except RuntimeError as gdalerr:
            LOGGER.error(self.gdal.GetLastErrorMsg())
            raise gdalerr

    def _ogr_feature_to_json(
        self, ogr_feature, skip_geometry=False, crs_transform_out=None,
    ):
        if self.geom_field is not None:
            geom = ogr_feature.GetGeomFieldRef(self.geom_field)
        else:
            geom = ogr_feature.GetGeometryRef()

        if crs_transform_out is not None:
            # Optionally reproject the geometry
            geom.Transform(crs_transform_out)

        # NB With GDAL >= 3.3 seems that Axis is swapped for e.g.
        # EPSG:4258 in ExportToJson where it shouldn't. See #1174.
        # Suppress swapping by unassigning SpatialReference
        geom.AssignSpatialReference(None)
        json_feature = ogr_feature.ExportToJson(as_object=True)

        if skip_geometry:
            json_feature['geometry'] = None

        try:
            json_feature['id'] = json_feature['properties'].pop(
                self.id_field, json_feature['id']
            )
        except KeyError as err:
            LOGGER.error(f"Cannot use configured id_field nor fid as id, err={err}")  # noqa

        return json_feature

    def _response_feature_collection(
        self, layer, limit, skip_geometry=False, crs_transform_spec=None,
    ):
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
        crs_transform_out = self._get_crs_transform(crs_transform_spec)

        # Keep support for source_srs/target_srs
        # if crs_transform_out is None:
        #     crs_transform_out = self.transform_out
        try:
            # Ignore gdal error
            ogr_feature = _ignore_gdal_error(layer, 'GetNextFeature')
            count = 0
            while ogr_feature is not None:
                json_feature = self._ogr_feature_to_json(
                    ogr_feature,
                    skip_geometry=skip_geometry,
                    crs_transform_out=crs_transform_out,
                )

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

        :returns: pygeoapi.provider.ogr.SourceHelper
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
            msg = f'Cannot get Layer {self.provider.layer_name} from OGR Source'  # noqa
            LOGGER.error(msg)
            raise Exception(msg)

        return layer

    def enable_paging(self, offset=-1, limit=-1):
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

        :returns: pygeoapi.provider.ogr.SourceHelper
        """

        super().__init__(provider)

        self.offset = -1
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
            msg = f'ReleaseResultSet exception for Layer {self.provider.layer_name}'  # noqa
            LOGGER.error(msg, err)
        finally:
            self.result_set = None

    def enable_paging(self, offset=-1, limit=-1):
        """
        Enable paged access to dataset (OGR Driver-specific)
        using OGR SQL https://gdal.org/user/ogr_sql_dialect.html
        e.g. SELECT * FROM poly LIMIT 10 OFFSET 30

        """
        self.offset = offset
        self.limit = limit

    def disable_paging(self):
        """
        Disable paged access to dataset (OGR Driver-specific)
        """

        pass

    def get_layer(self):
        """
        Gets OGR Layer from opened OGR dataset.
        When offset defined 1 or greater will invoke
        OGR SQL SELECT with LIMIT and OFFSET and return
        as Layer as ResultSet from ExecuteSQL on dataset.
        :return: OGR layer object
        """
        if self.offset <= 0:
            return SourceHelper.get_layer(self)

        self.close()

        sql = f'SELECT * FROM "{self.provider.layer_name}" LIMIT {self.limit} OFFSET {self.offset}'  # noqa
        self.result_set = self.provider.conn.ExecuteSQL(sql)

        # Reset since needs to be set each time explicitly
        self.offset = -1
        self.limit = -1

        if not self.result_set:
            msg = f'Cannot get Layer {self.provider.layer_name} via ExecuteSQL'
            LOGGER.error(msg)
            raise Exception(msg)

        return self.result_set


class ESRIJSONHelper(CommonSourceHelper):

    def __init__(self, provider):
        """
        Initialize object

        :param provider: provider instance

        :returns: pygeoapi.provider.ogr.SourceHelper
        """

        super().__init__(provider)

    def enable_paging(self, offset=-1, limit=-1):
        """
        Enable paged access to dataset (OGR Driver-specific)

        """
        if offset < 0:
            return

        self.provider.open_options.update(FEATURE_SERVER_PAGING=True)
        self.offset = offset
        self.limit = limit

    def disable_paging(self):
        """
        Disable paged access to dataset (OGR Driver-specific)
        """

        self.provider.open_options.update(FEATURE_SERVER_PAGING=False)

    def get_layer(self):
        """
        Gets OGR Layer from opened OGR dataset.
        When offset defined 1 or greater will invoke
        OGR SQL SELECT with LIMIT and OFFSET and return
        as Layer as ResultSet from ExecuteSQL on dataset.
        :return: OGR layer object
        """
        if self.offset <= 0:
            return CommonSourceHelper.get_layer(self)

        self.close()

        sql = f"SELECT * FROM {self.provider.layer_name} LIMIT {self.limit} OFFSET {self.offset}"  # noqa
        self.result_set = self.provider.conn.ExecuteSQL(sql)

        # Reset since needs to be set each time explicitly
        self.offset = -1
        self.limit = -1

        if not self.result_set:
            msg = f'Cannot get Layer {self.provider.layer_name} via ExecuteSQL'
            LOGGER.error(msg)
            raise Exception(msg)

        return self.result_set


class WFSHelper(SourceHelper):

    def __init__(self, provider):
        """
        Initialize object

        :param provider: provider instance

        :returns: pygeoapi.provider.ogr.SourceHelper
        """

        super().__init__(provider)

    def enable_paging(self, offset=-1, limit=-1):
        """
        Enable paged access to dataset (OGR Driver-specific)

        """

        if offset < 0:
            return

        self.provider.gdal.SetConfigOption(
            'OGR_WFS_PAGING_ALLOWED', 'ON')
        self.provider.gdal.SetConfigOption(
            'OGR_WFS_BASE_START_INDEX', str(offset))
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

        :returns: pygeoapi.provider.ogr.GdalErrorHandler
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

        :returns: pygeoapi.provider.ogr.GdalErrorHandler
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
            if 'HTTP error code' in last_error:
                # 500 <= http error ode <=599
                for i in list(range(500, 599)):
                    if str(i) in last_error:
                        raise ProviderConnectionError(last_error)
            else:
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
