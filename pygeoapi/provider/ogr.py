# =================================================================
#
# Authors: Just van den Broecke <justb4@gmail.com>
#
# Copyright (c) 2019 Just van den Broecke
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

from osgeo import gdal as osgeo_gdal
from osgeo import ogr as osgeo_ogr
from osgeo import osr as osgeo_osr

from pygeoapi.provider.base import (BaseProvider)

LOGGER = logging.getLogger(__name__)


class OGRProvider(BaseProvider):
    """OGR Provider"""

    # To deal with some OGR Source-Driver specifics.
    SOURCE_HELPERS = {
        'WFS': 'pygeoapi.provider.ogr.WFSHelper',
        'ESRI Shapefile': 'pygeoapi.provider.ogr.ShapefileHelper',
        'GPKG': 'pygeoapi.provider.ogr.GPKGHelper'
    }

    def __init__(self, provider_def):
        """
        Initialize object

        # Typical OGR Provider config:
        # provider:
        #     name: OGR
        #     data:
        #         source_type: WFS
        #         source: WFS:
        #               http://geodata.nationaalgeoregister.nl/rdinfo/wfs?
        #         source_srs: EPSG:28992
        #         target_srs: EPSG:4326
        #         source_capabilities:
        #             paging: True
        #         source_options:
        #             VERSION: 2.0.0
        #             OGR_WFS_PAGING_ALLOWED: YES
        #             OGR_WFS_LOAD_MULTIPLE_LAYER_DEFN: NO
        #         gdal_ogr_options:
        #             GDAL_CACHEMAX: 64
        #             GDAL_HTTP_PROXY: (optional proxy)
        #             GDAL_PROXY_AUTH: (optional auth for remote WFS)
        #             CPL_DEBUG: NO
        #     id_field: gml_id
        #     layer: rdinfo:stations


        :param provider_def: provider definition

        :returns: pygeoapi.providers.ogr.OGRProvider
        """

        BaseProvider.__init__(self, provider_def)

        self.ogr = osgeo_ogr
        # http://trac.osgeo.org/gdal/wiki/PythonGotchas
        self.gdal = osgeo_gdal
        self.gdal.UseExceptions()
        LOGGER.info("Using GDAL/OGR version: %d"
                    % int(osgeo_gdal.VersionInfo('VERSION_NUM')))

        # GDAL error handler function
        # http://pcjericks.github.io/py-gdalogr-cookbook/gdal_general.html
        def gdal_error_handler(err_class, err_num, err_msg):
            err_type = {
                osgeo_gdal.CE_None: 'None',
                osgeo_gdal.CE_Debug: 'Debug',
                osgeo_gdal.CE_Warning: 'Warning',
                osgeo_gdal.CE_Failure: 'Failure',
                osgeo_gdal.CE_Fatal: 'Fatal'
            }
            err_msg = err_msg.replace('\n', ' ')
            err_class = err_type.get(err_class, 'None')
            LOGGER.error('Error Number: %s, Type: %s, Msg: %s'
                         % (err_num, err_class, err_msg))

        # install error handler
        self.gdal.PushErrorHandler(gdal_error_handler)
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
            source.ImportFromEPSG(self.source_srs)

            target = osgeo_osr.SpatialReference()
            target.ImportFromEPSG(self.target_srs)

            self.transform_in = \
                osgeo_osr.CoordinateTransformation(target, source)
            self.transform_out = \
                osgeo_osr.CoordinateTransformation(source, target)

        self._load_source_helper(self.data_def['source_type'])

        # Init
        self.driver = None
        self.conn = None
        self.layer = None
        self.layer_name = provider_def.get('layer', None)

    def _open(self):
        source_type = self.data_def['source_type']
        self.driver = self.ogr.GetDriverByName(source_type)
        if not self.driver:
            msg = 'No Driver for Source: {}'.format(source_type)
            LOGGER.error(msg)
            raise Exception(msg)

        self.conn = self.driver.Open(self.data_def['source'], 0)
        if not self.conn:
            msg = 'cannot open OGR Source: %s' % self.data_def['source']
            LOGGER.error(msg)
            raise Exception(msg)

    def _get_layer(self):
        if not self.conn:
            self._open()

        if not self.layer_name:
            # E.g. Shapefiles may not have explicitly named Layers
            layer = self.conn.GetLayer(0)
        else:
            layer = self.conn.GetLayerByName(self.layer_name)

        if not layer:
            msg = 'Cannot get Layer {} from OGR Source'.format(self.layer_name)
            LOGGER.error(msg)
            raise Exception(msg)

        return layer

    def get_fields(self):
        """
         Get provider field information (names, types)

        :returns: dict of fields
        """

        fields = {}

        layer_defn = self._get_layer().GetLayerDefn()
        for fld in range(layer_defn.GetFieldCount()):
            field_defn = layer_defn.GetFieldDefn(fld)
            fieldName = field_defn.GetName()
            fieldTypeCode = field_defn.GetType()
            fieldType = field_defn.GetFieldTypeName(fieldTypeCode)
            fields[fieldName] = fieldType.lower()
            # fieldWidth = layer_defn.GetFieldDefn(fld).GetWidth()
            # GetPrecision = layer_defn.GetFieldDefn(fld).GetPrecision()

        return fields

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], time=None, properties=[], sortby=[]):
        """
        Query OGR source

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param time: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)

        :returns: dict of 0..n GeoJSON features
        """
        if self.source_capabilities['paging']:
            self.source_helper.set_paging(startindex, limit)

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
        if resulttype == 'hits':
            LOGGER.debug('hits only specified')
            return self._response_feature_hits(layer)
        elif resulttype == 'results':
            LOGGER.debug('results specified')
            return self._response_feature_collection(layer, limit)
        else:
            LOGGER.error('Invalid resulttype: %s' % resulttype)
            return None

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

            result = self._response_feature_collection(layer, 1)

        except Exception as err:
            LOGGER.error(err)

        return result

    def __repr__(self):
        return '<OGRProvider> {}'.format(self.data)

    def _load_source_helper(self, source_type):
        """
        Loads Source Helper by name.

        :param Source type: Source type name

        :returns: Source Helper object
        """

        if source_type not in OGRProvider.SOURCE_HELPERS.keys():
            msg = 'No Helper found for OGR Source type: {}'.format(source_type)
            LOGGER.exception(msg)
            raise InvalidHelperError(msg)

        # Create object from full package.class name string.
        source_helper_class = OGRProvider.SOURCE_HELPERS[source_type]

        packagename, classname = source_helper_class.rsplit('.', 1)
        module = importlib.import_module(packagename)
        class_ = getattr(module, classname)
        self.source_helper = class_(self)

    def _response_feature_collection(self, layer, limit):
        """Assembles GeoJSON output from DB query

        :returns: GeoJSON FeaturesCollection
        """

        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }
        count = 0
        for feature in layer:
            geom = feature.GetGeometryRef()
            if self.transform_out:
                # Optionally reproject the geometry
                geom.Transform(self.transform_out)

            json_feature = feature.ExportToJson(as_object=True)
            json_feature['id'] = json_feature['properties'].pop(self.id_field)

            feature_collection['features'].append(json_feature)
            count += 1
            if count == limit:
                break

        return feature_collection

    def _response_feature_hits(self, layer):
        """Assembles GeoJSON/Feature number
        e.g: http://localhost:5000/collections/
        hotosm_bdi_waterways/items?resulttype=hits

        :returns: GeoJSON FeaturesCollection
        """

        feature_collection = {
            'type': 'FeatureCollection',
            'numberMatched': layer.GetFeatureCount(),
            'features': []
        }

        return feature_collection


class InvalidHelperError(Exception):
    """Invalid helper"""
    pass


class SourceHelper:
    def __init__(self, provider):
        """
        Initialize object

        :param provider: provider instance

        :returns: pygeoapi.providers.ogr.SourceHelper
        """
        self.provider = provider

    def set_paging(self, startindex=-1, limit=-1):
        """
        Get provider field information (names, types)

        :returns: dict of fields
        """

        pass


class GPKGHelper(SourceHelper):

    def __init__(self, provider):
        """
        Initialize object

        :param provider: provider instance

        :returns: pygeoapi.providers.ogr.SourceHelper
        """
        self.provider = provider
        SourceHelper.__init__(self, provider)


class ShapefileHelper(SourceHelper):

    def __init__(self, provider):
        """
        Initialize object

        :param provider: provider instance

        :returns: pygeoapi.providers.ogr.SourceHelper
        """
        self.provider = provider
        SourceHelper.__init__(self, provider)


class WFSHelper(SourceHelper):

    def __init__(self, provider):
        """
        Initialize object

        :param provider: provider instance

        :returns: pygeoapi.providers.ogr.SourceHelper
        """
        self.provider = provider
        SourceHelper.__init__(self, provider)

    def set_paging(self, startindex=-1, limit=-1):
        """
        Get provider field information (names, types)

        :returns: dict of fields
        """

        if startindex < 0:
            return

        self.provider.gdal.SetConfigOption(
            'OGR_WFS_BASE_START_INDEX', str(startindex))
        self.provider.gdal.SetConfigOption(
            'OGR_WFS_PAGE_SIZE', str(limit))
