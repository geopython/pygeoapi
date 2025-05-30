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

from copy import deepcopy
import logging

from sqlalchemy.sql import func, select
from sqlalchemy.orm import Session
from pygeoapi.models.provider.base import (
    TileSetMetadata, TileMatrixSetEnum, LinkType)
from pygeoapi.provider.base import ProviderConnectionError
from pygeoapi.provider.base_mvt import BaseMVTProvider
from pygeoapi.provider.postgresql import PostgreSQLProvider
from pygeoapi.provider.tile import ProviderTileNotFoundError
from pygeoapi.util import url_join

LOGGER = logging.getLogger(__name__)

WEBMERCATORQUAD = TileMatrixSetEnum.WEBMERCATORQUAD.value
WORLDCRS84QUAD = TileMatrixSetEnum.WORLDCRS84QUAD.value

CRS_CODES = {
    'http://www.opengis.net/def/crs/OGC/1.3/CRS84': 4326,
    'https://www.opengis.net/def/crs/OGC/0/CRS84': 4326,
    'http://www.opengis.net/def/crs/EPSG/0/3857': 3857
}


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
        pg_def = deepcopy(provider_def)
        # delete the zoom option before initializing the PostgreSQL provider
        # that provider breaks otherwise
        del pg_def['options']['zoom']
        PostgreSQLProvider.__init__(self, pg_def)
        BaseMVTProvider.__init__(self, provider_def)

    def get_fields(self):
        """
        Get Postgrres fields

        :returns: `dict` of item fields
        """
        PostgreSQLProvider.get_fields(self)

    def get_layer(self):
        """
        Extracts layer name from url

        :returns: layer name
        """
        return self.table

    def get_tiling_schemes(self):
        return [WEBMERCATORQUAD, WORLDCRS84QUAD]

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
        if format_ == 'mvt':
            format_ = self.format_type

        geom_column = getattr(self.table_model, self.geom)
        tile_envelope = func.ST_TileEnvelope(z, x, y)
        [tileset_schema] = [
            schema for schema in self.get_tiling_schemes()
            if tileset == schema.tileMatrixSet
        ]

        if not self.is_in_limits(tileset_schema, z, x, y):
            return ProviderTileNotFoundError

        if tileset_schema.crs != self.storage_crs:
            LOGGER.debug('Transforming geometry')
            tile_envelope = func.ST_Transform(
                tile_envelope, CRS_CODES[tileset_schema.crs]
            )
            geom_column = func.ST_Transform(
                geom_column, CRS_CODES[tileset_schema.crs]
            )

        all_columns = [
            c for c in self.table_model.__table__.columns if c.name != 'geom'
        ]
        all_columns.append(
            func.ST_AsMVTGeom(geom_column, tile_envelope).label('mvt')
        )
        tile_query = select(
            func.ST_AsMVT(
                select(*all_columns)
                .select_from(self.table_model)
                .cte('tile')
                .table_valued(),
                layer
            )
        )

        with Session(self._engine) as session:
            result = session.execute(tile_query).scalar()
            return bytes(result) or None

    def get_html_metadata(self, dataset, server_url, layer, tileset,
                          title, description, keywords, **kwargs):

        service_url = url_join(
            server_url,
            f'collections/{dataset}/tiles/{tileset}'
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

    def __repr__(self):
        return f'<MVTPostgreSQLProvider> {self.data}'
