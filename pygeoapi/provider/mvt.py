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

import logging
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
        self.services = self.get_tile_services()

    def get_tiling_schemes(self):

        tileMatrixSetLinks = {
            'tileMatrixSetLinks': [{
                'tileMatrixSet': 'WorldCRS84Quad',
                'tileMatrixSetURI': 'http://schemas.opengis.net/tms/1.0/json/examples/WorldCRS84Quad.json'  # noqa
            },
            {
                'tileMatrixSet': 'WebMercatorQuad',
                'tileMatrixSetURI': 'http://schemas.opengis.net/tms/1.0/json/examples/WebMercatorQuad.json'  # noqa
            }]
        }

        return tileMatrixSetLinks

    def get_tile_services(self, baseurl=None, servicepath=None,
                          tile_type=None):
        """
        Gets mvt service description

        :param baseurl: base URL of endpoint
        :param servicepath: base path of URL
        :param tile_type: tile format type

        :returns: `dict` of item tile service
        """

        url = urlparse(self.source)
        baseurl = baseurl or '{}://{}'.format(url.scheme, url.netloc)
        # @TODO: support multiple types
        tile_type = tile_type or self.format_types[0]
        servicepath = \
            servicepath or \
            '{}/tiles/{{{}}}/{{{}}}/{{{}}}/{{{}}}{}'.format(
                url.path.split('/{z}/{x}/{y}')[0],
                'tileMatrixSetId',
                'tileMatrix',
                'tileRow',
                'tileCol',
                tile_type)

        service_url = urljoin(baseurl, servicepath)
        service_metadata = urljoin(
            service_url.split('{tileMatrix}/{tileRow}/{tileCol}')[0],
            'metadata')

        links = {
            'links': [{
                'type': 'application/vnd.mapbox-vector-tile',
                'rel': 'item',
                'title': 'This collection as Mapbox vector tiles',
                'href': service_url,
                'templated': True
            }, {
                'type': 'application/json',
                'rel': 'describedby',
                'title': 'Metadata for this collection in the TileJSON format',
                'href': '{}?f=json'.format(service_metadata),
                'templated': True
            }]
        }

        return links

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
