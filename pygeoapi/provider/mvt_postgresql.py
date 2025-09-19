# =================================================================
#
# Authors: Prajwal Amaravati <prajwal.s@satsure.co>
#          Tanvi Prasad <tanvi.prasad@cdpg.org.in>
#          Bryan Robert <bryan.robert@cdpg.org.in>
#          Benjamin Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2025 Prajwal Amaravati
# Copyright (c) 2025 Tanvi Prasad
# Copyright (c) 2025 Bryan Robert
# Copyright (c) 2025 Benjamin Webb
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

from geoalchemy2.functions import (ST_TileEnvelope, ST_Transform, ST_AsMVTGeom,
                                   ST_AsMVT, ST_CurveToLine, ST_MakeEnvelope)

from sqlalchemy.sql import select
from sqlalchemy.orm import Session

from pygeoapi.crs import get_crs
from pygeoapi.models.provider.base import (
    TileSetMetadata, TileMatrixSetEnum, LinkType)
from pygeoapi.provider.base import ProviderConnectionError
from pygeoapi.provider.base_mvt import BaseMVTProvider
from pygeoapi.provider.sql import PostgreSQLProvider
from pygeoapi.provider.tile import ProviderTileNotFoundError
from pygeoapi.util import url_join

LOGGER = logging.getLogger(__name__)


class MVTPostgreSQLProvider(BaseMVTProvider, PostgreSQLProvider):
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
        PostgreSQLProvider.__init__(self, provider_def)
        BaseMVTProvider.__init__(self, provider_def)

    def get_fields(self):
        """
        Get Postgres columns

        :returns: `list` of columns
        """
        if not self._fields:
            for column in self.table_model.__table__.columns:
                LOGGER.debug(f'Testing {column.name}')
                if column.name == self.geom:
                    continue

                self._fields[str(column.name)] = (
                    column.label('id')
                    if column.name == self.id_field else
                    column
                )

        return self._fields

    def get_layer(self):
        """
        Use table name as layer name

        :returns: `str` of layer name
        """
        return self.table

    def get_tiling_schemes(self):
        """
        Only WebMercatorQuad and WorldCRS84Quad tiling schemes
        are supported for PostgreSQL
        """

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

        BaseMVTProvider.get_tiles_service(self,
                                          baseurl, servicepath,
                                          dirpath, tile_type)

        self._service_url = servicepath
        return self.get_tms_links()

    def get_tiles(self, layer='default', tileset=None,
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
        z, y, x = map(int, [z, y, x])

        [tileset_schema] = [
            schema for schema in self.get_tiling_schemes()
            if tileset == schema.tileMatrixSet
        ]
        if not self.is_in_limits(tileset_schema, z, x, y):
            LOGGER.warning(f'Tile {z}/{x}/{y} not found')
            raise ProviderTileNotFoundError

        envelope = self.get_envelope(z, y, x, tileset)
        geom_column = getattr(self.table_model, self.geom)
        geom_filter = geom_column.intersects(
            ST_Transform(envelope, self.storage_crs.to_string())
        )

        out_srid = get_crs(tileset_schema.crs).to_string()
        mvtgeom = (
            ST_AsMVTGeom(
                ST_Transform(ST_CurveToLine(geom_column), out_srid),
                ST_Transform(envelope, out_srid))
            .label('mvtgeom')
        )

        mvtrow = (
            select(mvtgeom, *self.fields.values())
            .filter(geom_filter)
            .cte('mvtrow')
        )

        mvtquery = select(
            ST_AsMVT(mvtrow.table_valued(), layer)
        )

        with Session(self._engine) as session:
            result = bytes(
                session.execute(mvtquery).scalar()
            ) or None

        return result

    def get_html_metadata(self, dataset, server_url, layer, tileset,
                          title, description, keywords, **kwargs):

        service_url = url_join(
            server_url,
            f'collections/{dataset}/tiles/{tileset}',
            '{tileMatrix}/{tileRow}/{tileCol}?f=mvt')
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
            f'collections/{dataset}/tiles/{tileset}',
            '{tileMatrix}/{tileRow}/{tileCol}?f=mvt'
            )

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
                    server_url, 'TileMatrixSets', schema.tileMatrixSet)
                tiling_scheme_url_type = 'application/json'
                tiling_scheme_url_title = f'{schema.tileMatrixSet} tile matrix set definition' # noqa

                tiling_scheme = LinkType(
                    href=tiling_scheme_url,
                    rel='http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme',
                    type_=tiling_scheme_url_type,
                    title=tiling_scheme_url_title)

        if tiling_scheme is None:
            msg = 'Could not identify a valid tiling schema'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

        content = TileSetMetadata(title=title, description=description,
                                  keywords=keywords, crs=crs,
                                  tileMatrixSetURI=tileMatrixSetURI)

        links = []
        service_url_link_type = 'application/vnd.mapbox-vector-tile'
        service_url_link_title = f'{tileset} vector tiles for {layer}'
        service_url_link = LinkType(href=service_url, rel='item',
                                    type_=service_url_link_type,
                                    title=service_url_link_title)

        links.append(tiling_scheme)
        links.append(service_url_link)

        content.links = links

        return content.model_dump(exclude_none=True)

    @staticmethod
    def get_envelope(z, y, x, tileset):
        """
        Calculate the Tile bounding box of a tile at zoom z, y, x.

        WorldCRS84Quad tiles have:
        - origin top-left (y=0 is north)
        - full lon: -180 to 180

        :param tileset: mvt tileset
        :param z: z index
        :param y: y index
        :param x: x index

        :returns: SQL Alchemy Tile Envelope
        """

        if tileset == TileMatrixSetEnum.WORLDCRS84QUAD.value.tileMatrixSet:

            tile_size = 180 / 2 ** z

            xmin = tile_size * x - 180
            ymax = tile_size * -y + 90

            # getting bottom-right coordinates of the tile
            xmax = xmin + tile_size
            ymin = ymax - tile_size

            envelope = ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326)

        else:
            envelope = ST_TileEnvelope(z, x, y)

        return envelope.label('bounds')

    def __repr__(self):
        return f'<MVTPostgreSQLProvider> {self.data}'
