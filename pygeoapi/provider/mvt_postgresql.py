# =================================================================
#
# Authors: Prajwal Amaravati <prajwal.s@satsure.co>
#          Tanvi Prasad <tanvi.prasad@cdpg.org.in>
#          Bryan Robert <bryan.robert@cdpg.org.in>
#
# Copyright (c) 2025 Prajwal Amaravati
# Copyright (c) 2025 Tanvi Prasad
# Copyright (c) 2025 Bryan Robert
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

from copy import deepcopy
import logging

from sqlalchemy.sql import text

from pygeoapi.models.provider.base import (
    TileSetMetadata, TileMatrixSetEnum, LinkType)
from pygeoapi.provider.base import ProviderConnectionError
from pygeoapi.provider.base_mvt import BaseMVTProvider
from pygeoapi.provider.sql import PostgreSQLProvider
from pygeoapi.provider.tile import ProviderTileNotFoundError
from pygeoapi.util import url_join

LOGGER = logging.getLogger(__name__)


class MVTPostgreSQLProvider(BaseMVTProvider):
    """
    MVT PostgreSQL Provider
    Provider for serving tiles rendered on-the-fly from
    feature tables in PostgreSQL
    """

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.MVT.MVTPostgreSQLProvider
        """

        super().__init__(provider_def)

        pg_def = deepcopy(provider_def)
        # delete the zoom option before initializing the PostgreSQL provider
        # that provider breaks otherwise
        del pg_def["options"]["zoom"]
        self.postgres = PostgreSQLProvider(pg_def)

        self.layer_name = provider_def["table"]
        self.table = provider_def['table']
        self.id_field = provider_def['id_field']
        self.geom = provider_def.get('geom_field', 'geom')

        LOGGER.debug(f'DB connection: {repr(self.postgres._engine.url)}')

    def __repr__(self):
        return f'<MVTPostgreSQLProvider> {self.data}'

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

        fields_arr = self.postgres.get_fields().keys()
        fields = ', '.join(['"' + f + '"' for f in fields_arr])
        if len(fields) != 0:
            fields = ',' + fields

        query = ''
        if tileset == TileMatrixSetEnum.WEBMERCATORQUAD.value.tileMatrixSet:
            if not self.is_in_limits(TileMatrixSetEnum.WEBMERCATORQUAD.value, z, x, y): # noqa
                raise ProviderTileNotFoundError

            query = text("""
                WITH
                    bounds AS (
                        SELECT ST_TileEnvelope({z}, {x}, {y}) AS boundgeom
                    ),
                    mvtgeom AS (
                        SELECT ST_AsMVTGeom(ST_Transform(ST_CurveToLine({geom}), 3857), bounds.boundgeom) AS geom {fields}
                        FROM "{table}", bounds
                        WHERE ST_Intersects({geom}, ST_Transform(bounds.boundgeom, 4326))
                    )
                SELECT ST_AsMVT(mvtgeom, 'default') FROM mvtgeom;
            """.format(geom=self.geom, table=self.table, fields=fields, z=z, x=x, y=y)) # noqa

        if tileset == TileMatrixSetEnum.WORLDCRS84QUAD.value.tileMatrixSet:
            if not self.is_in_limits(TileMatrixSetEnum.WORLDCRS84QUAD.value, z, x, y): # noqa
                raise ProviderTileNotFoundError

            # get tile size in degrees based on zoom level.
            # Tile size is a function of the zoom level,
            # e.g at zoom level 0, tile size is 180,
            # at zoom level 1, tile size is 90 and so on.
            tile_size_deg = 180/pow(2, int(z))

            # getting top-left coordinates of the tile
            xmin = (tile_size_deg * int(x)) - 180
            ymax = (-tile_size_deg * int(y)) + 90

            # getting bottom-right coordinates of the tile
            xmax = xmin + tile_size_deg
            ymin = ymax - tile_size_deg

            query = text("""
                WITH
                    bounds AS (
                        SELECT ST_MakeEnvelope({xmin},{ymin},{xmax},{ymax}, 4326) AS boundgeom
                    ),
                    mvtgeom AS (
                        SELECT ST_AsMVTGeom(ST_CurveToLine({geom}), bounds.boundgeom) AS geom {fields}
                        FROM "{table}", bounds
                        WHERE ST_Intersects({geom}, bounds.boundgeom)
                    )
                SELECT ST_AsMVT(mvtgeom, 'default') FROM mvtgeom;
            """.format(geom=self.geom, table=self.table, fields=fields, xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)) # noqa

        with self.postgres._engine.connect() as session:
            result = session.execute(query).fetchone()

            if len(bytes(result[0])) == 0:
                return None
            return bytes(result[0])

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
