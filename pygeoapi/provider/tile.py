# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Francesco Bartoli
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
from http import HTTPStatus

from pygeoapi.provider.base import (
    ProviderGenericError, ProviderItemNotFoundError)

LOGGER = logging.getLogger(__name__)


class BaseTileProvider:
    """generic Tile Provider ABC"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.tile.BaseTileProvider
        """

        self.name = provider_def['name']
        self.data = provider_def['data']
        self.format_type = provider_def['format']['name']
        self.mimetype = provider_def['format']['mimetype']
        self.options = provider_def.get('options')
        self.tile_type = None
        self.fields = {}

    def get_layer(self):
        """
        Get provider layer name

        :returns: `string` of layer name
        """

    def get_fields(self):
        """
        Get provider field information (names, types)

        :returns: `dict` of fields
        """

        raise NotImplementedError()

    def get_tiling_schemes(self):
        """
        Get provider field information (names, types)

        :returns: `dict` of tiling schemes
        """

        raise NotImplementedError()

    def get_tiles_service(self, baseurl, servicepath, dirpath,
                          tile_type):
        """
        Gets tile service description

        :param baseurl: base URL of endpoint
        :param servicepath: base path of URL
        :param dirpath: directory basepath (equivalent of URL)
        :param tile_type: tile format type

        :returns: `dict` of file listing or `dict` of GeoJSON item or raw file
        """

        raise NotImplementedError()

    def get_tiles(self, layer, tileset, z, y, x, format_):
        """
        Gets tiles data

        :param layer: tile layer
        :param tileset: tile set
        :param z: z index
        :param y: y index
        :param x: x index
        :param format_: tile format type

        :returns: `binary` of the tile
        """

        raise NotImplementedError()

    def get_metadata(self):
        """
        Provide data/file metadata

        :returns: `dict` of metadata construct (format
                  determined by provider/standard)
        """

        raise NotImplementedError()


class ProviderTileQueryError(ProviderGenericError):
    """provider tile query error"""
    default_msg = 'Tile not found'


class ProviderTileNotFoundError(ProviderItemNotFoundError):
    """provider tile not found error"""
    default_msg = 'Tile not found (check logs)'


class ProviderTilesetIdNotFoundError(ProviderTileQueryError):
    """provider tileset matrix query error"""
    default_msg = 'Tileset id not found'
    http_status_code = HTTPStatus.NOT_FOUND
    ogc_exception_code = 'NotFound'
