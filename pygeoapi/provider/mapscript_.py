# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
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

import logging

from osgeo import osr
import mapscript
from mapscript import MapServerError

from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
                                    ProviderQueryError)

LOGGER = logging.getLogger(__name__)

IMAGE_FORMATS = {
    'png': 'GD/PNG',
    'png24': 'GD/PNG24',
    'gif': 'GD/GIF',
    'jpeg': 'GD/JPEG'
}


class MapScriptProvider(BaseProvider):
    """MapScript map provider (https://mapserver.org/mapscript)"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.mapscript_.MapScriptProvider
        """

        BaseProvider.__init__(self, provider_def)

        self.crs_list = []
        self.styles = []
        self.default_format = 'png'

        LOGGER.debug(f'MapScript version: {mapscript.MS_VERSION}')

        try:
            LOGGER.debug('Creating new mapObj and layerObj')
            self._map = mapscript.mapObj()
            self._layer = mapscript.layerObj(self._map)
            self._layer.status = mapscript.MS_ON

            file_extension = self.data.split('.')[-1]

            if file_extension in ['shp', 'tif']:
                LOGGER.debug('Setting built-in MapServer driver')
                self._layer.data = self.data
            else:
                LOGGER.debug('Setting OGR driver')
                self._layer.setConnectionType(mapscript.MS_OGR, 'OGR')
                self._layer.connection = self.data

            self._layer.type = getattr(mapscript, self.options['type'])

            try:
                self.crs = int(self.options['projection'])
            except KeyError:
                self.crs = 4326

            self._layer.setProjection(self._epsg2projstring(self.crs))

            LOGGER.debug(f'Layer projection: {self._layer.getProjection()}')

            if 'style' in self.options:
                if self.options['style'].endswith(('xml', 'sld')):
                    LOGGER.debug('Setting SLD')
                    with open(self.options['style']) as fh:
                        self._layer.applySLD(fh.read(), self.options['layer'])
                elif self.options['style'].endswith('inc'):
                    LOGGER.debug('Setting MapServer class file')
                    cls = mapscript.classObj(self._layer)
                    with open(self.options['style']) as fh:
                        cls.updateFromString(fh.read())
            else:
                if self.options['type'] != 'MS_LAYER_RASTER':
                    LOGGER.debug('No vector styling found, setting default')
                    cls = mapscript.classObj()
                    cls_def = 'CLASS NAME "default" STYLE COLOR 0 0 0 END END'
                    cls.updateFromString(cls_def)
                    self._layer.insertClass(cls)

        except MapServerError as err:
            LOGGER.warning(err)
            raise ProviderConnectionError('Cannot connect to map service')

    def query(self, style=None, bbox=[], width=500, height=300, crs='CRS84',
              datetime_=None, format_='png', transparent=True, **kwargs):
        """
        Generate map

        :param style: style name (default is `None`)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param width: width of output image (in pixels)
        :param height: height of output image (in pixels)
        :param datetime_: temporal (datestamp or extent)
        :param crs: coordinate reference system identifier
        :param format_: Output format (default is `png`)
        :param transparent: Apply transparency to map (default is `True`)

        :returns: `bytes` of map image
        """

        try:
            image_obj_format = IMAGE_FORMATS[format_]
        except KeyError:
            LOGGER.error(f'Bad output format: {image_obj_format}')
            raise ProviderQueryError('Bad image format')

        LOGGER.debug('Setting output map CRS')
        try:
            if crs not in ['CRS84', 4326]:
                LOGGER.debug('Reprojecting coordinates')
                prj_dst_text = self._epsg2projstring(int(crs.split("/")[-1]))

                prj_src = mapscript.projectionObj(self._layer.getProjection())
                prj_dst = mapscript.projectionObj(prj_dst_text)

                rect = mapscript.rectObj(*bbox)
                _ = rect.project(prj_src, prj_dst)

                map_bbox = [rect.minx, rect.miny, rect.maxx, rect.maxy]
                map_crs = prj_dst_text
                self._map.units = mapscript.MS_METERS

            else:
                map_bbox = bbox
                map_crs = self._epsg2projstring(4326)
                self._map.units = mapscript.MS_DD

        except MapServerError as err:
            LOGGER.error(err)
            raise ProviderQueryError('bad projection')

        if datetime_ is not None:
            if self.time_field is None:
                LOGGER.debug('collection is not time enabled')
            else:
                fe = f'{self.time_field} = "{datetime_}"'
                LOGGER.debug(f'Setting temporal filter: {fe}')
                self._layer.setFilter(fe)

        LOGGER.debug('Setting output image properties')
        fmt = mapscript.outputFormatObj(image_obj_format)
        if transparent:
            fmt.transparent = mapscript.MS_ON
        else:
            fmt.transparent = mapscript.MS_OFF

        self._map.setOutputFormat(fmt)
        self._map.setExtent(*map_bbox)
        self._map.setSize(width, height)

        self._map.setProjection(map_crs)
        self._map.setConfigOption('MS_NONSQUARE', 'yes')

        LOGGER.debug(f'Mapfile: {self._map.convertToString()}')
        try:
            img = self._map.draw()
        except MapServerError as err:
            LOGGER.debug(err)
            raise ProviderQueryError(err)

        return img.getBytes()

    def _epsg2projstring(self, epsg_code):
        """
        Helper function to derive a proj string from an EPSG code

        :param epsg_code: `int` of EPSG code

        :returns: `str` of PROJ string/syntax
        """

        prj = osr.SpatialReference()
        prj.ImportFromEPSG(epsg_code)

        return prj.ExportToProj4().strip()

    def __repr__(self):
        return f'<MapScriptProvider> {self.data}'
