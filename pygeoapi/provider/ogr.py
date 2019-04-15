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

import gdal
import ogr

from pygeoapi.provider.base import (BaseProvider)

LOGGER = logging.getLogger(__name__)


class OGRProvider(BaseProvider):
    """OGR Provider"""

    SOURCE_HELPERS = {
        'WFS': 'pygeoapi.provider.ogr.WFSHelper',
        'ESRI Shapefile': 'pygeoapi.provider.ogr.ShapefileHelper'
    }

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.providers.ogr.OGRProvider
        """

        BaseProvider.__init__(self, provider_def)

        self.ogr = ogr
        # http://trac.osgeo.org/gdal/wiki/PythonGotchas
        self.gdal = gdal
        self.gdal.UseExceptions()
        LOGGER.info("Using GDAL/OGR version: %d" % int(gdal.VersionInfo('VERSION_NUM')))

        # GDAL error handler function
        # http://pcjericks.github.io/py-gdalogr-cookbook/gdal_general.html
        def gdal_error_handler(err_class, err_num, err_msg):
            err_type = {
                gdal.CE_None: 'None',
                gdal.CE_Debug: 'Debug',
                gdal.CE_Warning: 'Warning',
                gdal.CE_Failure: 'Failure',
                gdal.CE_Fatal: 'Fatal'
            }
            err_msg = err_msg.replace('\n', ' ')
            err_class = err_type.get(err_class, 'None')
            LOGGER.error('Error Number: %s, Type: %s, Msg: %s' % (err_num, err_class, err_msg))

        # install error handler
        self.gdal.PushErrorHandler(gdal_error_handler)
        LOGGER.debug('Setting OGR properties')

        # Typical config:
        # provider:
        #     name: OGR
        #     data:
        #         source_type: WFS
        #         source: WFS: http://geodata.nationaalgeoregister.nl/rdinfo/wfs?
        #         source_supports:
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
        self.layer_name = provider_def['layer']

        self.data_def = provider_def['data']
        gdal_ogr_options = self.data_def['gdal_ogr_options']
        for key in gdal_ogr_options:
            gdal.SetConfigOption(key, str(gdal_ogr_options[key]))
        source_options = self.data_def['source_options']
        for key in source_options:
            gdal.SetConfigOption(key, str(source_options[key]))
        self.source_supports = self.data_def['source_supports']
        self._load_source_helper(self.data_def['source_type'])
        self.driver = None
        self.conn = None
        self.layer = None

    def open(self):
        self.driver = ogr.GetDriverByName(self.data_def['source_type'])

        self.conn = self.driver.Open(self.data_def['source'], 0)
        if not self.conn:
            LOGGER.error('cannot open OGR Source: %s' % self.data_def['source'])
            return

    def get_layer(self):
        if not self.conn:
            self.open()
            
        return self.conn.GetLayerByName(self.layer_name)

    def get_fields(self):
        """
         Get provider field information (names, types)

        :returns: dict of fields
        """

        fields_ = {}

        return fields_

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
        if self.source_supports['paging']:
            self.source_helper.set_paging(startindex, limit)

        layer = self.get_layer()

        if bbox:
            LOGGER.debug('processing bbox parameter')
            minx, miny, maxx, maxy = bbox

            wkt = "POLYGON (({minx} {miny},{minx} {maxy},{maxx} {maxy},{maxx} {miny},{minx} {miny}))".format(minx=minx, miny=miny, maxx=maxx, maxy=maxy)
            layer.SetSpatialFilter(ogr.CreateGeometryFromWkt(wkt))

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
            layer = self.get_layer()

            layer.SetAttributeFilter("{field} = '{id}'".format(field=self.id_field, id=identifier))

            result = self._response_feature_collection(layer, 1)

        except Exception as err:
            LOGGER.error(err)

        return result

    def __repr__(self):
        return '<OGRProvider> {}'.format(self.data)

    def _load_source_helper(self, source_type):
        """
        loads Source Helper by name

        :param Source Helper_type: type of Source Helper (provider, formatter)
        :param Source Helper_def: Source Helper definition

        :returns: Source Helper object
        """

        if source_type not in OGRProvider.SOURCE_HELPERS.keys():
            msg = 'No Helper found for OGR Source type: {}'.format(source_type)
            LOGGER.exception(msg)
            raise InvalidHelperError(msg)

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
            feature_collection['features'].append(
                feature.ExportToJson(as_object=True))
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

        self.provider.gdal.SetConfigOption('OGR_WFS_BASE_START_INDEX', str(startindex))
        self.provider.gdal.SetConfigOption('OGR_WFS_PAGE_SIZE', str(limit))
