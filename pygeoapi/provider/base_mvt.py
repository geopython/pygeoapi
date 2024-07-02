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

import logging
from urllib.parse import urlparse

from pygeoapi.provider.tile import BaseTileProvider
from pygeoapi.models.provider.base import (
    TileMatrixSetEnum, TilesMetadataFormat)
from pygeoapi.util import url_join

LOGGER = logging.getLogger(__name__)


class BaseMVTProvider(BaseTileProvider):
    """Base MVT Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.base_mvt.BaseMVTProvider
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

    def get_html_metadata(self, dataset, server_url, layer, tileset,
                          title, description, keywords, **kwargs):
        """
        Gets tile metadata information in html format

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

        raise NotImplementedError()

    def get_default_metadata(self, dataset, server_url, layer, tileset,
                             title, description, keywords, **kwargs):
        """
        Gets tile metadata in default Tile Set Metadata format

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
        raise NotImplementedError()

    def get_vendor_metadata(self, dataset, server_url, layer, tileset,
                            title, description, keywords, **kwargs):
        """
        Gets tile metadata in Tilejson format

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

        raise NotImplementedError()

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
        elif metadata_format.upper() == TilesMetadataFormat.TILEJSON:
            return self.get_vendor_metadata(dataset, server_url, layer,
                                            tileset, title, description,
                                            keywords, **kwargs)
        elif metadata_format.upper() == TilesMetadataFormat.HTML:
            return self.get_html_metadata(dataset, server_url, layer,
                                          tileset, title, description,
                                          keywords, **kwargs)
        elif metadata_format.upper() == TilesMetadataFormat.JSONLD:
            return self.get_default_metadata(dataset, server_url, layer,
                                             tileset, title, description,
                                             keywords, **kwargs)
        else:
            raise NotImplementedError(f"_{metadata_format.upper()}_ is not supported") # noqa

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
