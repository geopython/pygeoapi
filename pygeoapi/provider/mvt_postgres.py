# =================================================================
#
# Authors: 
#
# Copyright (c)
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
from pygeoapi.provider.postgresql import PostgreSQLProvider
from pygeoapi.provider.base import (ProviderConnectionError,
                                    ProviderGenericError,
                                    ProviderInvalidQueryError)
from pygeoapi.provider.tile import ProviderTileNotFoundError
from pygeoapi.models.provider.base import (
    TileSetMetadata, TileMatrixSetEnum, LinkType)
from pygeoapi.util import is_url, url_join

from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import functools
import logging

LOGGER = logging.getLogger(__name__)


class MVTPostgresProvider(BaseMVTProvider):

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.MVT.MVTPostgresProvider
        """

        super().__init__(provider_def)
        
        pg_def = deepcopy(provider_def)
        del pg_def["options"]["zoom"]
        self.postgres = PostgreSQLProvider(pg_def)
        self.layer_name = provider_def["table"]


    def __repr__(self):
        return f'<MVTPostgresProvider> {self.data}'

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

        return self.layer_name

    def get_tiling_schemes(self):

        return [
                TileMatrixSetEnum.WEBMERCATORQUAD.value,
                TileMatrixSetEnum.WORLDCRS84QUAD.value
            ]

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

        # @TODO : Update tile fetch code. 
        raise NotImplementedError()
        """
        if is_url(self.data):
            url = urlparse(self.data)
            base_url = f'{url.scheme}://{url.netloc}'

            if url.query:
                url_query = f'?{url.query}'
            else:
                url_query = ''

            try:
                with requests.Session() as session:
                    data = {'fields': ['*']}
                    session.get(base_url)
                    resp = session.get(f'{base_url}/{layer}/{z}/{y}/{x}{url_query}', json=data)  # noqa

                    if resp.status_code == 404:
                        if (self.is_in_limits(self.get_tilematrixset(tileset), z, x, y)): # noqa
                            return None
                        raise ProviderTileNotFoundError

                    resp.raise_for_status()
                    return resp.content
            except requests.exceptions.RequestException as e:
                LOGGER.debug(e)
                if resp.status_code < 500:
                    raise ProviderInvalidQueryError  # Client is sending an invalid request # noqa
                raise ProviderGenericError  # Server error
        else:
            msg = 'Wrong input format for Elasticsearch MVT'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)
        """    

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
