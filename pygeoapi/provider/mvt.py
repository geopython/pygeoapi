# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#
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

import io
import logging
import os
from urllib.parse import urlparse, urljoin

from pygeoapi.provider.base import (BaseTileProvider, ProviderConnectionError,
                                    ProviderNotFoundError)

LOGGER = logging.getLogger(__name__)


class MVTProvider(BaseTileProvider):
    """MVT Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.MVT.MVTProvider
        """

        BaseTileProvider.__init__(self, provider_def)

        # if not os.path.exists(self.data):
        #     msg = 'Service does not exist: {}'.format(self.source)
        #     LOGGER.error(msg)
        #     raise ProviderConnectionError(msg)
        self.schemes = self.get_tiling_schemes()
        self.service = self.get_tile_service()
    
    
    def get_tiling_schemes(self):
        
        content = {}
        
        tileMatrixSetLinks = [{
                'tileMatrixSet': 'WorldCRS84Quad',
                'tileMatrixSetURI': 'http://schemas.opengis.net/tms/1.0/json/examples/WorldCRS84Quad.json'
            },{
                'tileMatrixSet': 'WebMercatorQuad',
                'tileMatrixSetURI': 'http://schemas.opengis.net/tms/1.0/json/examples/WebMercatorQuad.json'
            }
        ]
        
        content.update(tileMatrixSetLinks=tileMatrixSetLinks)
        
        return content
    

    def get_tile_service(self, baseurl=None, servicepath=None,
                         tile_type=None):
        """
        Gets mvt service description

        :param baseurl: base URL of endpoint
        :param servicepath: base path of URL
        :param tile_type: tile format type

        :returns: `dict` 
        """

        url = urlparse(self.source)
        baseurl = baseurl or '{}://{}'.format(url.scheme, url.netloc)
        servicepath = servicepath or url.path
        # @TODO: support multiple types
        tile_type = tile_type or self.format_types[0]
        serviceurl = urljoin(urljoin(baseurl, servicepath), tile_type)

        content = {
            'links': [{
                'rel': 'item',
                # {tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}.pbf
                'href': serviceurl,
                'title': 'This collection as Mapbox vector tiles',
                'type': 'application/vnd.mapbox-vector-tile',
                'templated': True
            }, {
                'rel': 'describedby',
                # tiles/{tileMatrixSetId}/metadata
                'href': serviceurl,
                'title': 'Metadata for this collection in the TileJSON format',
                'type': 'application/json',
                'templated': True
            }]
        }

        return content

    def __repr__(self):
        return '<MVTProvider> {}'.format(self.source)


def _describe_service(self):
    """
    Helper function to describe a vector tile service

    :param layer: path to file

    :returns: `dict` of JSON metadata
    """

    content = {
    }

    return content
