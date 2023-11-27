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
from urllib.parse import urlencode

import pyproj
import requests

from pygeoapi.provider.base import BaseProvider, ProviderQueryError

LOGGER = logging.getLogger(__name__)

OUTPUT_FORMATS = {
    'png': 'image/png'
}

CRS_CODES = {
    4326: 'EPSG:4326',
    'http://www.opengis.net/def/crs/EPSG/0/3857': 'EPSG:3857'
}


class WMSFacadeProvider(BaseProvider):
    """WMS 1.3.0 provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.map_facade.WMSFacadeProvider
        """

        BaseProvider.__init__(self, provider_def)

        LOGGER.debug(f'pyproj version: {pyproj.__version__}')

    def query(self, style=None, bbox=[-180, -90, 180, 90], width=500,
              height=300, crs=4326, datetime_=None, transparent=True,
              format_='png'):
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

        self._transparent = 'TRUE'

        if crs in [4326, 'CRS;84']:
            LOGGER.debug('Swapping 4326 axis order to WMS 1.3 mode (yx)')
            bbox2 = ','.join(str(c) for c in
                             [bbox[1], bbox[0], bbox[3], bbox[2]])
        else:
            LOGGER.debug('Reprojecting coordinates')
            LOGGER.debug(f'Output CRS: {CRS_CODES[crs]}')

            src_crs = pyproj.CRS.from_string('epsg:4326')
            dest_crs = pyproj.CRS.from_string(CRS_CODES[crs])

            transformer = pyproj.Transformer.from_crs(src_crs, dest_crs,
                                                      always_xy=True)

            minx, miny = transformer.transform(bbox[0], bbox[1])
            maxx, maxy = transformer.transform(bbox[2], bbox[3])

            bbox2 = ','.join(str(c) for c in [minx, miny, maxx, maxy])

        if not transparent:
            self._transparent = 'FALSE'

        params = {
            'version': '1.3.0',
            'service': 'WMS',
            'request': 'GetMap',
            'bbox': bbox2,
            'crs': CRS_CODES[crs],
            'layers': self.options['layer'],
            'styles': self.options.get('style', 'default'),
            'width': width,
            'height': height,
            'format': OUTPUT_FORMATS[format_],
            'transparent': self._transparent
        }

        if datetime_ is not None:
            params['time'] = datetime_

        if '?' in self.data:
            request_url = '&'.join([self.data, urlencode(params)])
        else:
            request_url = '?'.join([self.data, urlencode(params)])

        LOGGER.debug(f'WMS 1.3.0 request url: {request_url}')

        response = requests.get(request_url)

        if b'ServiceException' in response.content:
            msg = f'WMS error: {response.content}'
            LOGGER.error(msg)
            raise ProviderQueryError(msg)

        return response.content

    def __repr__(self):
        return f'<WMSFacadeProvider> {self.data}'
