# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
# Authors: Tom Kralidis <tomkralidis@gmail.com>
# Authors: Simon Seyock <simonseyock@gmail.com>
#
# Copyright (c) 2020 Francesco Bartoli
# Copyright (c) 2023 Tom Kralidis
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
from urllib.parse import urlparse, urlencode

from pygeoapi.provider.tile import (
    BaseTileProvider)
from pygeoapi.provider.base import ProviderConnectionError
from pygeoapi.models.provider.base import (
    TileMatrixSetEnum, TilesMetadataFormat, TileSetMetadata, LinkType)
from pygeoapi.util import is_url, url_join

LOGGER = logging.getLogger(__name__)


class WMTSFacadeProvider(BaseTileProvider):
    """WMTS Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.WMTSFacadeProvider
        """

        if provider_def['format']['name'] not in ['png', 'jpeg']:
            raise RuntimeError("WMTS format has to be 'png' or 'jpeg'")

        super().__init__(provider_def)

        self.tile_type = 'raster'

    def __repr__(self):
        return f'<WMTSFacadeProvider> {self.data}'

    @property
    def service_url(self):
        return self._service_url

    @property
    def service_metadata_url(self):
        return self._service_metadata_url

    def get_tiling_schemes(self):

        tile_matrix_set_links_list = [
            TileMatrixSetEnum.WORLDCRS84QUAD.value,
            TileMatrixSetEnum.WEBMERCATORQUAD.value
        ]
        tile_matrix_set_links = [
            item for item in tile_matrix_set_links_list
            if item.tileMatrixSet == self.options['scheme']
        ]

        return tile_matrix_set_links

    def get_tiles_service(self, baseurl=None, servicepath=None,
                          dirpath=None, tile_type=None):
        """
        Gets service description

        :param baseurl: base URL of endpoint
        :param servicepath: base path of URL
        :param dirpath: directory basepath (equivalent of URL)
        :param tile_type: tile format type

        :returns: `dict` of item tile service
        """

        url = urlparse(self.data)
        baseurl = baseurl or f'{url.scheme}://{url.netloc}'
        tile_type = self.format_type
        basepath = url.path.split('/{z}/{x}/{y}')[0]
        servicepath = servicepath or f'{basepath}/tiles/{{tileMatrixSetId}}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}?f={tile_type}'  # noqa

        if servicepath.startswith(baseurl):
            self._service_url = servicepath
        else:
            self._service_url = url_join(baseurl, servicepath)

        tile_matrix_set = self.service_url.split(
            '/{tileMatrix}/{tileRow}/{tileCol}')[0]
        self._service_metadata_url = url_join(tile_matrix_set, 'metadata')

        links = {
            'links': [
                {
                    'type': self.mimetype,
                    'rel': 'item',
                    'title': 'This collection as image tiles',
                    'href': self.service_url
                },
                {
                    'type': 'application/json',
                    'rel': 'describedby',
                    'title': 'Collection metadata in TileJSON format',
                    'href': f'{self.service_metadata_url}?f=json'
                }
            ]
        }
        return links

    def get_tiles(self, layer=None, tileset=None,
                  z=None, y=None, x=None, format_=None):
        """
        Gets tile

        :param layer: The layer name
        :param tileset: The tileset name
        :param z: z index
        :param y: y index
        :param x: x index
        :param format_: tile format

        :returns: an image tile
        """
        if is_url(self.data):
            params = {
                'service': 'WMTS',
                'request': 'GetTile',
                'version': '1.0.0',
                'format': self.mimetype,
                'layer': self.options['wmts_layer'],
                'tileMatrixSet': self.options['wmts_tile_matrix_set'],
                'tileMatrix': z,
                'tileRow': y,
                'tileCol': x,
                'style': ''
            }

            if '?' in self.data:
                request_url = '&'.join([self.data, urlencode(params)])
            else:
                request_url = '?'.join([self.data, urlencode(params)])

            LOGGER.debug(f'WMTS 1.0.0 request url: {request_url}')

            with requests.Session() as session:
                resp = session.get(request_url)
                resp.raise_for_status()
                return resp.content
        else:
            msg = f'Wrong data path configuration: {self.data}'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

    def get_metadata(self, dataset, server_url, layer=None,
                     tileset=None, metadata_format=None, title=None,
                     description=None, keywords=None, **kwargs):
        """
        Gets tiles metadata

        :param dataset: dataset name
        :param server_url: server base url
        :param layer: mvt tile layer name
        :param tileset: mvt tileset name
        :param metadata_format: format for metadata,
                            enum TilesMetadataFormat
        :param title: title name
        :param description: description name
        :param keywords: keywords list

        :returns: `dict` of JSON metadata
        """

        if metadata_format.upper() == TilesMetadataFormat.JSON:
            return self.get_default_metadata(dataset, server_url, layer,
                                             tileset, title, description,
                                             keywords, **kwargs)
        elif metadata_format.upper() == TilesMetadataFormat.HTML:
            return self.get_html_metadata(dataset, server_url, layer,
                                          tileset, title, description,
                                          keywords, **kwargs)
        else:
            raise NotImplementedError(f"_{metadata_format.upper()}_ is not supported") # noqa

    def get_html_metadata(self, dataset, server_url, layer, tileset,
                          title, description, keywords, **kwargs):

        service_url = url_join(
            server_url,
            f'collections/{dataset}/tiles/{tileset}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}?f={self.format_type}')  # noqa
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
            f'collections/{dataset}/tiles/{tileset}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}?f={self.format_type}')  # noqa

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
        service_url_link_title = f'{tileset} raster tiles for {dataset}'
        service_url_link = LinkType(href=service_url, rel="item",
                                    type_=self.mimetype,
                                    title=service_url_link_title)

        links.append(tiling_scheme)
        links.append(service_url_link)

        content.links = links

        return content.dict(exclude_none=True)
