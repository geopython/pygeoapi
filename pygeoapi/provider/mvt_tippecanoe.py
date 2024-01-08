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

import json
import logging
from pathlib import Path
from urllib.parse import urlparse

from pygeoapi.provider.tile import (
    ProviderTileNotFoundError)
from pygeoapi.provider.base import ProviderConnectionError
from pygeoapi.provider.base_mvt import BaseMVTProvider
from pygeoapi.models.provider.base import (
    TileSetMetadata, LinkType)
from pygeoapi.models.provider.mvt import MVTTilesJson

from pygeoapi.util import is_url, url_join

LOGGER = logging.getLogger(__name__)


class MVTTippecanoeProvider(BaseMVTProvider):
    """MVT Tippecanoe Provider
    Provider for serving tiles generated with Mapbox Tippecanoe
    https://github.com/mapbox/tippecanoe
    It supports both, tiles from a an url or a path on disk.
    Tippecanoe also provides a TileSet Metadata in a file called
    "metadata.json".
    """

    def __init__(self, BaseMVTProvider):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.MVT.MVTTippecanoeProvider
        """

        super().__init__(BaseMVTProvider)

        # Pre-rendered tiles served from a static url
        if is_url(self.data):
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
        # Pre-rendered tiles served from a local path
        else:
            data_path = Path(self.data)
            if not data_path.exists():
                msg = f'Service does not exist: {self.data}'
                LOGGER.error(msg)
                raise ProviderConnectionError(msg)
            self._service_url = data_path
            metadata_path = data_path.joinpath('metadata.json')
            if not metadata_path.exists():
                msg = f'Service metadata does not exist: {metadata_path.name}'
                LOGGER.error(msg)
                LOGGER.warning(msg)
            self._service_metadata_url = metadata_path

    def __repr__(self):
        return f'<MVTTippecanoeProvider> {self.data}'

    def get_layer(self):
        """
        Extracts layer name from url or data path

        :returns: layer name
        """

        if is_url(self.data):
            url = urlparse(self.data)

            if ('/{z}/{x}/{y}' not in url.path):
                msg = f'This url template is not supported yet: {url.path}'
                LOGGER.error(msg)
                raise ProviderConnectionError(msg)

            layer = url.path.split('/{z}/{x}/{y}')[0]

            LOGGER.debug(layer)
            LOGGER.debug('Removing leading "/"')
            return layer[1:]

        else:
            return Path(self.data).name

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

        if not isinstance(self.service_url, Path):
            msg = f'Wrong data path configuration: {self.service_url}'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)
        else:
            try:
                service_url_path = self.service_url.joinpath(f'{z}/{y}/{x}.{format_}')  # noqa
                with open(service_url_path, mode='rb') as tile:
                    return tile.read()
            except FileNotFoundError as err:
                raise ProviderTileNotFoundError(err)

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
        # Some providers may not implement tilejson metadata
        metadata['tilejson_url'] = f'{metadata_url}?f=tilejson'

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

        return content.dict(exclude_none=True)

    def get_tilejson_metadata(self, dataset, server_url, layer, tileset,
                              title, description, keywords, **kwargs):
        """
        Gets tile metadata in tilejson format
        """

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
