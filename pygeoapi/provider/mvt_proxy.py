# =================================================================
#
# Authors: Antonio Cerciello <ant@byteroad.net>
#
# Copyright (c) 2024 Antonio Cerciello
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

from pygeoapi.provider.base_mvt import BaseMVTProvider
from pygeoapi.provider.base import (ProviderConnectionError,
                                    ProviderGenericError,
                                    ProviderInvalidQueryError)
from pygeoapi.models.provider.base import (
    TileSetMetadata, LinkType)
from pygeoapi.util import is_url, url_join

LOGGER = logging.getLogger(__name__)


class MVTProxyProvider(BaseMVTProvider):
    """
    MVT Proxy Provider
    Provider for serving tiles rendered with an external
    tiles provider
    """

    def __init__(self, BaseMVTProvider):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.mvt_proxy.pygeoapi/provider/mvt_proxy.py # noqa
        """

        super().__init__(BaseMVTProvider)

        if not is_url(self.data):
            msg = 'Wrong input format for MVT'
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
        return f'<MVTProxyProvider> {self.data}'

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
            msg = 'Wrong input format for MVT'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

        url = urlparse(self.data)

        if ('/{z}/{x}/{y}' not in url.path):
            msg = 'Wrong input format for MVT'
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

            resp = None

            try:
                with requests.Session() as session:
                    session.get(base_url)
                    if '.' in url.path:
                        resp = session.get(f'{base_url}/{layer}/{z}/{y}/{x}.{format_}{url_query}')  # noqa
                    else:
                        resp = session.get(f'{base_url}/{layer}/{z}/{y}/{x}{url_query}')  # noqa

                    resp.raise_for_status()
                    return resp.content
            except requests.exceptions.RequestException as e:
                LOGGER.debug(e)
                if resp and resp.status_code < 500:
                    raise ProviderInvalidQueryError  # Client is sending an invalid request # noqa
                raise ProviderGenericError  # Server error
        else:
            msg = 'Wrong input format for MVT'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

    def get_html_metadata(self, dataset, server_url, layer, tileset,
                          title, description, keywords, **kwargs):

        service_url = url_join(
            server_url,
            f'collections/{dataset}/tiles/{tileset}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}?f=mvt')  # noqa
        metadata_url = url_join(
            server_url,
            f'collections/{dataset}/tiles/{tileset}/metadata')

        metadata = dict()
        metadata['id'] = dataset
        metadata['title'] = title
        metadata['tileset'] = tileset
        metadata['collections_path'] = service_url
        metadata['json_url'] = f'{metadata_url}?f=json'

        return metadata

    def get_default_metadata(self, dataset, server_url, layer, tileset,
                             title, description, keywords, **kwargs):

        service_url = url_join(
            server_url,
            f'collections/{dataset}/tiles/{tileset}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}?f=mvt')  # noqa

        content = {}
        tiling_schemes = self.get_tiling_schemes()
        # Default values
        tileMatrixSetURI = tiling_schemes[0].tileMatrixSetURI
        crs = tiling_schemes[0].crs
        # Checking the selected matrix in configured tiling_schemes
        for schema in tiling_schemes:
            if (schema.tileMatrixSet == tileset):
                crs = schema.crs
                tileMatrixSetURI = schema.tileMatrixSetURI

                tiling_scheme_url = url_join(
                    server_url, f'/TileMatrixSets/{schema.tileMatrixSet}')
                tiling_scheme_url_type = "application/json"
                tiling_scheme_url_title = f'{schema.tileMatrixSet} tile matrix set definition' # noqa

                tiling_scheme = LinkType(href=tiling_scheme_url,
                                         rel="http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme", # noqa
                                         type_=tiling_scheme_url_type,
                                         title=tiling_scheme_url_title)

        if tiling_scheme is None:
            msg = f'Could not identify a valid tiling schema'  # noqa
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

        content = TileSetMetadata(title=title, description=description,
                                  keywords=keywords, crs=crs,
                                  tileMatrixSetURI=tileMatrixSetURI)

        links = []
        service_url_link_type = "application/vnd.mapbox-vector-tile"
        service_url_link_title = f'{tileset} vector tiles for {layer}'
        service_url_link = LinkType(href=service_url, rel="item",
                                    type_=service_url_link_type,
                                    title=service_url_link_title)

        links.append(tiling_scheme)
        links.append(service_url_link)

        content.links = links

        return content.dict(exclude_none=True)
