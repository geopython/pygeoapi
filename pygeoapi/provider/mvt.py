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

import json
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse, urljoin

from pygeoapi.util import is_url, url_join
from pygeoapi.provider.tile import (
    BaseTileProvider, ProviderTileNotFoundError)
from pygeoapi.provider.base import ProviderConnectionError


LOGGER = logging.getLogger(__name__)


class MVTProvider(BaseTileProvider):
    """MVT Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.MVT.MVTProvider
        """

        super().__init__(provider_def)

        if is_url(self.data):
            url = urlparse(self.data)
            baseurl = '{}://{}'.format(url.scheme, url.netloc)
            param_type = '?f=mvt'
            servicepath = \
                '{}/tiles/{{{}}}/{{{}}}/{{{}}}/{{{}}}{}'.format(
                    url.path.split('/{z}/{x}/{y}')[0],
                    'tileMatrixSetId',
                    'tileMatrix',
                    'tileRow',
                    'tileCol',
                    param_type)

            self._service_url = url_join(baseurl, servicepath)
            self._service_metadata_url = urljoin(
                self.service_url.split('{tileMatrix}/{tileRow}/{tileCol}')[0],
                'metadata')
        else:
            data_path = Path(self.data)
            if not data_path.exists():
                msg = 'Service does not exist: {}'.format(self.data)
                LOGGER.error(msg)
                raise ProviderConnectionError(msg)
            self._service_url = data_path
            metadata_path = data_path.joinpath('metadata.json')
            if not metadata_path.exists():
                msg = 'Service metadata does not exist: {}'.format(
                    metadata_path.name)
                LOGGER.error(msg)
                raise ProviderConnectionError(msg)
            self._service_metadata_url = metadata_path

    def __repr__(self):
        return '<MVTProvider> {}'.format(self.data)

    @property
    def service_url(self):
        return self._service_url

    @property
    def service_metadata_url(self):
        return self._service_metadata_url

    def get_layer(self):

        if is_url(self.data):
            url = urlparse(self.data)
            return url.path.split("/{z}/{x}/{y}")[0][1:]
        else:
            return None

    def get_tiling_schemes(self):

        tile_matrix_set_links_list = [{
                'tileMatrixSet': 'WorldCRS84Quad',
                'tileMatrixSetURI': 'http://schemas.opengis.net/tms/1.0/json/examples/WorldCRS84Quad.json',  # noqa
                'crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
            }, {
                'tileMatrixSet': 'WebMercatorQuad',
                'tileMatrixSetURI': 'http://schemas.opengis.net/tms/1.0/json/examples/WebMercatorQuad.json',  # noqa
                'crs': 'http://www.opengis.net/def/crs/EPSG/0/3857'
            }]
        tile_matrix_set_links = [
            item for item in tile_matrix_set_links_list if item[
                'tileMatrixSet'] in self.options['schemes']]

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
        baseurl = baseurl or '{}://{}'.format(url.scheme, url.netloc)
        # @TODO: support multiple types
        tile_type = tile_type or self.format_type
        servicepath = \
            servicepath or \
            '{}/tiles/{{{}}}/{{{}}}/{{{}}}/{{{}}}{}'.format(
                url.path.split('/{z}/{x}/{y}')[0],
                'tileMatrixSetId',
                'tileMatrix',
                'tileRow',
                'tileCol',
                tile_type)

        if servicepath.startswith(baseurl):
            self._service_url = servicepath
        else:
            self._service_url = url_join(baseurl, servicepath)
        self._service_metadata_url = urljoin(
            self.service_url.split('{tileMatrix}/{tileRow}/{tileCol}')[0],
            'metadata')

        links = {
            'links': [
                {
                    'type': 'application/json',
                    'rel': 'self',
                    'title': 'This collection as multi vector tilesets',
                    'href': self.service_url,
                },
                {
                    'type': self.mimetype,
                    'rel': 'item',
                    'title': 'This collection as multi vector tiles',
                    'href': self.service_url,
                }, {
                    'type': 'application/json',
                    'rel': 'describedby',
                    'title': 'Collection metadata in TileJSON format',
                    'href': '{}?f=json'.format(self.service_metadata_url),
                }
            ]
        }

        return links

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

        if format_ == "mvt":
            format_ = self.format_type
        if is_url(self.data):
            url = urlparse(self.data)
            base_url = '{}://{}'.format(url.scheme, url.netloc)
            with requests.Session() as session:
                session.get(base_url)
                resp = session.get('{base_url}/{lyr}/{z}/{y}/{x}{f}'.format(
                    base_url=base_url, lyr=layer,
                    z=z, y=y, x=x, f= '?grid_precision=0' if format_ == "elastic" else '.' + format_))
                resp.raise_for_status()
                return resp.content
        else:
            if not isinstance(self.service_url, Path):
                msg = 'Wrong data path configuration: {}'.format(
                    self.service_url)
                LOGGER.error(msg)
                raise ProviderConnectionError(msg)
            else:
                try:
                    with open(self.service_url.joinpath(
                        '{z}/{y}/{x}.{f}'.format(
                            z=z, y=y, x=x, f=format_)), 'rb') as tile:
                        return tile.read()
                except FileNotFoundError as err:
                    raise ProviderTileNotFoundError(err)

    def get_metadata(self, dataset, server_url, layer=None,
                     tileset=None, tilejson=True, **kwargs):
        """
        Gets tile metadata

        :param dataset: dataset name
        :param server_url: server base url
        :param layer: mvt tile layer name
        :param tileset: mvt tileset name
        :param tilejson: `bool` for the returning json structure
                        if True it returns MapBox TileJSON 3.0
                        otherwise the raw JSON is served

        :returns: `dict` of JSON metadata
        """

        if tilejson is False:
             return

        if is_url(self.data):
            url = urlparse(self.data)
            base_url = '{}://{}'.format(url.scheme, url.netloc)
            with requests.Session() as session:
                session.get(base_url)
                resp = session.get('{base_url}/{lyr}/metadata.json'.format(
                    base_url=base_url, lyr=layer))
                resp.raise_for_status()
            content = resp.json()
        else:
            if not isinstance(self.service_metadata_url, Path):
                msg = 'Wrong data path configuration: {}'.format(
                    self.service_metadata_url)
                LOGGER.error(msg)
                raise ProviderConnectionError(msg)
            with open(self.service_metadata_url, 'r') as md_file:
                content = json.loads(md_file.read())
        if tilejson:
            service_url = urljoin(
                server_url,
                'collections/{}/tiles/{}/{{{}}}/{{{}}}/{{{}}}{}'.format(
                    dataset, tileset, 'tileMatrix',
                    'tileRow', 'tileCol', '?f=mvt'))
            content = {
                "tilejson": "3.0.0",
                "name": content["name"],
                "tiles": service_url,
                "minzoom": content["minzoom"],
                "maxzoom": content["maxzoom"],
                "bounds": content["bounds"],
                "center": content["center"],
                "attribution": None,
                "description": None,
                "vector_layers": json.loads(
                    content["json"])["vector_layers"]
            }
        else:
            content['json'] = json.loads(content['json'])

        return content
