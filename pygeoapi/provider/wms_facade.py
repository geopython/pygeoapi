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
    'http://www.opengis.net/def/crs/EPSG/0/4326': 'EPSG:4326',
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
              bbox_crs=4326, format_='png'):
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

        version = self.options.get('version', '1.3.0')

        if version == '1.3.0' and CRS_CODES[bbox_crs] == 'EPSG:4326':
            bbox = [bbox[1], bbox[0], bbox[3], bbox[2]]
        bbox2 = ','.join(map(str, bbox))

        if not transparent:
            self._transparent = 'FALSE'
        crs_param = 'crs' if version == '1.3.0' else 'srs'

        params = {
            'version': version,
            'service': 'WMS',
            'request': 'GetMap',
            'bbox': bbox2,
            crs_param: CRS_CODES[crs],
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

        LOGGER.debug(f'WMS {version} request url: {request_url}')

        response = requests.get(request_url)

        if b'ServiceException' in response.content:
            msg = f'WMS error: {response.content}'
            LOGGER.error(msg)
            raise ProviderQueryError(msg)

        return response.content

    def __repr__(self):
        return f'<WMSFacadeProvider> {self.data}'
