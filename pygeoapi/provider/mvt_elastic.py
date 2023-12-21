# =================================================================
#
# Authors: Joana Simoes <jo@byteroad.net>
#
# Copyright (c) 2023 Joana Simoes
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
import requests
from urllib.parse import urlparse

from pygeoapi.provider.mvt import MVTProvider
from pygeoapi.provider.base import ProviderConnectionError
from pygeoapi.util import is_url, url_join

LOGGER = logging.getLogger(__name__)


class MVTElasticProvider(MVTProvider):
    """MVT Elastic Provider
    Provider for serving tiles rendered with the Elasticsearch
    Vector Tile API
    https://www.elastic.co/guide/en/elasticsearch/reference/current/search-vector-tile-api.html
    As of 12/23, elastic does not provide any tileset metadata.
    """

    def __init__(self, MVTProvider):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.MVT.MVTElasticProvider
        """

        super().__init__(MVTProvider)

        self.tile_type = 'vector'

        if not is_url(self.data):
            msg = 'Wrong input format for Elasticsearch MVT'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

        url = urlparse(self.data)
        baseurl = f'{url.scheme}://{url.netloc}'
        param_type = '?f=mvt'
        layer = f'/{self.get_layer()}'

        LOGGER.debug('Extracting layer name from URL')
        LOGGER.debug(f'Layer: {layer}')

        tilepath = f'{layer}/tiles'
        servicepath = f'{tilepath}/{{tileMatrixSetId}}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}{param_type}'  # noqa

        self._service_url = url_join(baseurl, servicepath)

        self._service_metadata_url = url_join(
            self.service_url.split('{tileMatrix}/{tileRow}/{tileCol}')[0],
            'metadata')

    def __repr__(self):
        return f'<MVTElasticProvider> {self.data}'

    @property
    def service_url(self):
        return self._service_url

    @property
    def service_metadata_url(self):
        return self._service_metadata_url

    def get_layer(self):
        """
        Extracts layer name from url

        :returns: layer name
        """

        if not is_url(self.data):
            msg = 'Wrong input format for Elasticsearch MVT'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

        url = urlparse(self.data)

        if ('/{z}/{x}/{y}' not in url.path):
            msg = 'Wrong input format for Elasticsearch MVT'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

        layer = url.path.split('/{z}/{x}/{y}')[0]

        LOGGER.debug(layer)
        LOGGER.debug('Removing leading "/"')
        return layer[1:]

    def get_tiles_service(self, baseurl=None, servicepath=None,
                          dirpath=None, tile_type=None):
        """
        Gets mvt service description

        :param baseurl: base URL of endpoint
        :param servicepath: base path of URL
        :param dirpath: directory basepath (equivalent of URL)
        :param tile_type: tile format type

        :returns: `dict` of item tile service
        """

        super().get_tiles_service(baseurl, servicepath,
                                  dirpath, tile_type)

        self._service_url = servicepath
        return self.get_tms_links()

    def get_tiles(self, layer=None, tileset=None,
                  z=None, y=None, x=None, format_=None):
        """
        Gets tile

        :param layer: mvt tile layer
        :param tileset: mvt tileset
        :param z: z index
        :param y: y index
        :param x: x index
        :param format_: tile format

        :returns: an encoded mvt tile
        """
        if format_ == 'mvt':
            format_ = self.format_type

        if is_url(self.data):
            url = urlparse(self.data)
            base_url = f'{url.scheme}://{url.netloc}'

            if url.query:
                url_query = f'?{url.query}'
            else:
                url_query = ''

            with requests.Session() as session:
                session.get(base_url)
                resp = session.get(f'{base_url}/{layer}/{z}/{y}/{x}{url_query}')  # noqa
                resp.raise_for_status()
                return resp.content
        else:
            msg = 'Wrong input format for Elasticsearch MVT'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

    def get_metadata(self, dataset, server_url, layer=None,
                     tileset=None, metadata_format=None, title=None,
                     description=None, keywords=None, **kwargs):
        """
        Gets tile metadata

        :param dataset: dataset name
        :param server_url: server base url
        :param layer: mvt tile layer name
        :param tileset: mvt tileset name
        :param metadata_format: format for metadata,
                            enum TilesMetadataFormat

        :returns: `dict` of JSON metadata
        """

        return super().get_metadata(dataset, server_url, layer,
                                    tileset, metadata_format, title,
                                    description, keywords, **kwargs)
