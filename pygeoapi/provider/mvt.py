# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
# Authors: Tom Kralidis <tomkralidis@gmail.com>
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

import json
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse

from pygeoapi.provider.tile import (
    BaseTileProvider)
from pygeoapi.provider.base import ProviderConnectionError
from pygeoapi.models.provider.base import (
    TileMatrixSetEnum, TilesMetadataFormat, TileSetMetadata, LinkType,
    GeospatialDataType)
from pygeoapi.models.provider.mvt import MVTTilesJson
from pygeoapi.util import is_url, url_join

LOGGER = logging.getLogger(__name__)


class MVTProvider(BaseTileProvider):
    """Generic provider for MapBox Vector Tiles
    Subclass this on specific providers.
    """

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.MVT.MVTProvider
        """

        super().__init__(provider_def)

        self.tile_type = 'vector'

    def __repr__(self):
        raise NotImplementedError()

    @property
    def service_url(self):
        return self._service_url

    @property
    def service_metadata_url(self):
        return self._service_metadata_url

    def get_layer(self):
        raise NotImplementedError()

    def get_tiling_schemes(self):

        tile_matrix_set_links_list = [
                TileMatrixSetEnum.WORLDCRS84QUAD.value,
                TileMatrixSetEnum.WEBMERCATORQUAD.value
            ]
        tile_matrix_set_links = [
            item for item in tile_matrix_set_links_list
            if item.tileMatrixSet in self.options['schemes']]

        return tile_matrix_set_links

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

        url = urlparse(self.data)
        baseurl = baseurl or f'{url.scheme}://{url.netloc}'
        # @TODO: support multiple types
        tile_type = tile_type or self.format_type
        basepath = url.path.split('/{z}/{x}/{y}')[0]
        servicepath = servicepath or f'{basepath}/tiles/{{tileMatrixSetId}}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}{tile_type}'  # noqa

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

        raise NotImplementedError()

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

        if is_url(self.data):
            url = urlparse(self.data)
            base_url = f'{url.scheme}://{url.netloc}'
            if metadata_format == TilesMetadataFormat.TILEJSON:
                with requests.Session() as session:
                    session.get(base_url)
                    resp = session.get(f'{base_url}/{layer}/metadata.json')
                    resp.raise_for_status()
                metadata_json_content = resp.json()
        else:
            if not isinstance(self.service_metadata_url, Path):
                msg = f'Wrong data path configuration: {self.service_metadata_url}'  # noqa
                LOGGER.error(msg)
                raise ProviderConnectionError(msg)

            if self.service_metadata_url.exists():
                with open(self.service_metadata_url, 'r') as md_file:
                    metadata_json_content = json.loads(md_file.read())

        service_url = url_join(
            server_url,
            f'collections/{dataset}/tiles/{tileset}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}?f=mvt')  # noqa

        content = {}
        if metadata_format == TilesMetadataFormat.TILEJSON:
            if 'metadata_json_content' in locals():
                content = MVTTilesJson(**metadata_json_content)
                content.tiles = service_url
                content.vector_layers = json.loads(
                        metadata_json_content["json"])["vector_layers"]
                return content.dict()
            else:
                msg = f'No tiles metadata json available: {self.service_metadata_url}'  # noqa
                LOGGER.error(msg)
                raise ProviderConnectionError(msg)
        elif metadata_format == TilesMetadataFormat.CUSTOMJSON:
            if 'metadata_json_content' in locals():
                content = metadata_json_content
                if 'json' in metadata_json_content:
                    content['json'] = json.loads(metadata_json_content['json'])
                return content
            else:
                msg = f'No custom JSON for tiles metadata available: {self.service_metadata_url}'  # noqa
                LOGGER.error(msg)
                raise ProviderConnectionError(msg)
        else:
            tiling_schemes = self.get_tiling_schemes()
            # Default values
            tileMatrixSetURI = tiling_schemes[0].tileMatrixSetURI
            crs = tiling_schemes[0].crs
            # Checking the selected matrix in configured tiling_schemes
            for schema in tiling_schemes:
                if (schema.tileMatrixSet == tileset):
                    crs = schema.crs
                    tileMatrixSetURI = schema.tileMatrixSetURI

            content = TileSetMetadata(title=title, description=description,
                                      keywords=keywords, crs=crs,
                                      tileMatrixSetURI=tileMatrixSetURI)

            links = []
            service_url_link_type = "application/vnd.mapbox-vector-tile"
            service_url_link_title = f'{tileset} vector tiles for {layer}'
            service_url_link = LinkType(href=service_url, rel="item",
                                        type=service_url_link_type,
                                        title=service_url_link_title)
            links.append(service_url_link)

            content.links = links

            if 'metadata_json_content' in locals():
                vector_layers = json.loads(
                    metadata_json_content["json"])["vector_layers"]
                layers = []
                for vector_layer in vector_layers:
                    layers.append(GeospatialDataType(id=vector_layer['id']))
                content.layers = layers
            return content.dict(exclude_none=True)

    def get_tms_links(self):
        """
        Generates TileMatrixSet Links

        :returns: a JSON object with TMS links
        """

        tile_matrix_set = self.service_url.split(
            '/{tileMatrix}/{tileRow}/{tileCol}')[0]
        self._service_metadata_url = url_join(tile_matrix_set, 'metadata')
        links = {
            'links': [
                {
                    'type': 'application/json',
                    'rel': 'self',
                    'title': 'This collection as multi vector tilesets',
                    'href': f'{tile_matrix_set}?f=json'
                },
                {
                    'type': self.mimetype,
                    'rel': 'item',
                    'title': 'This collection as multi vector tiles',
                    'href': self.service_url
                }, {
                    'type': 'application/json',
                    'rel': 'describedby',
                    'title': 'Collection metadata in TileJSON format',
                    'href': f'{self.service_metadata_url}?f=json'
                }
            ]
        }
        return links
