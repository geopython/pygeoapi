# =================================================================
#
# Authors: Ben Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2025 Ben Webb
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

# Needs to be run like: python3 -m pytest
# See pygeoapi/provider/postgresql.py for instructions on setting up
# test database in Docker

import os
import pytest

from pygeoapi.provider.mvt_postgresql import MVTPostgreSQLProvider
from pygeoapi.provider.tile import ProviderTileNotFoundError

PASSWORD = os.environ.get('POSTGRESQL_PASSWORD', 'postgres')
SERVER_URL = 'http://localhost'
DATASET = 'hotosm_bdi_waterways'


@pytest.fixture()
def config():
    return {
        'name': 'MVT-postgresql',
        'type': 'tile',
        'data': {
            'host': '127.0.0.1',
            'dbname': 'test',
            'user': 'postgres',
            'password': PASSWORD,
            'search_path': ['osm', 'public']
        },
        'id_field': 'osm_id',
        'table': 'hotosm_bdi_waterways',
        'geom_field': 'foo_geom',
        'options': {
            'zoom': {
                'min': 0,
                'max': 15
            }
        },
        'format': {
            'name': 'pbf',
            'mimetype': 'application/vnd.mapbox-vector-tile'
        },
        'storage_crs': 'http://www.opengis.net/def/crs/EPSG/0/4326'
    }


def test_metadata(config):
    """Testing query for a valid JSON object with geometry"""
    p = MVTPostgreSQLProvider(config)
    ts = 'WebMercatorQuad'

    assert p.table == 'hotosm_bdi_waterways'
    assert p.geom == 'foo_geom'
    assert p.id_field == 'osm_id'
    assert p.get_layer() == config['table']

    md = p.get_metadata(
        dataset=DATASET,
        server_url=SERVER_URL,
        layer='layer1',
        tileset=ts,
        metadata_format='json',
        title='Waterways',
        description='OpenStreetMap Waterways',
    )
    assert md['crs'] == \
        'http://www.opengis.net/def/crs/EPSG/0/3857'

    assert 'links' in md
    assert any(link['rel'].endswith('tiling-scheme') for link in md['links'])

    [tile_format,] = [link for link in md['links'] if link['rel'] == 'item']
    assert tile_format['href'].startswith(SERVER_URL)
    assert DATASET in tile_format['href']
    assert ts in tile_format['href']


def test_tile_out_of_bounds(config):
    config['options']['zoom']['min'] = 4
    config['options']['zoom']['max'] = 5

    p = MVTPostgreSQLProvider(config)

    [tileset_schema] = [
        schema for schema in p.get_tiling_schemes()
        if 'WebMercatorQuad' == schema.tileMatrixSet
    ]
    assert not p.is_in_limits(tileset_schema, 0, 0, 3)
    assert not p.is_in_limits(tileset_schema, 6, 0, 3)
    assert p.is_in_limits(tileset_schema, 5, 0, 3)


def test_get_tiling_schemes(config):
    provider = MVTPostgreSQLProvider(config)

    schemes = provider.get_tiling_schemes()
    assert any(s.tileMatrixSet == 'WebMercatorQuad' for s in schemes)
    assert any(s.tileMatrixSet == 'WorldCRS84Quad' for s in schemes)


def test_get_default_metadata_WebMercatorQuad(config):
    provider = MVTPostgreSQLProvider(config)
    ts = 'WebMercatorQuad'

    md = provider.get_default_metadata(
        dataset=DATASET,
        server_url=SERVER_URL,
        layer='layer1',
        tileset=ts,
        title='Waterways',
        description='OpenStreetMap Waterways',
        keywords=['osm', 'rivers']
    )

    assert md['tileMatrixSetURI'] == \
        'http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad'
    assert md['crs'] == \
        'http://www.opengis.net/def/crs/EPSG/0/3857'

    assert 'links' in md
    assert any(link['rel'].endswith('tiling-scheme') for link in md['links'])

    [tile_format,] = [link for link in md['links'] if link['rel'] == 'item']
    assert tile_format['href'].startswith(SERVER_URL)
    assert DATASET in tile_format['href']
    assert ts in tile_format['href']


def test_get_default_metadata_WorldCRS84Quad(config):
    provider = MVTPostgreSQLProvider(config)
    ts = 'WorldCRS84Quad'

    md = provider.get_default_metadata(
        dataset=DATASET,
        server_url=SERVER_URL,
        layer='layer1',
        tileset=ts,
        title='Waterways',
        description='OpenStreetMap Waterways',
        keywords=['osm', 'rivers']
    )

    assert md['tileMatrixSetURI'] == \
        'http://www.opengis.net/def/tilematrixset/OGC/1.0/WorldCRS84Quad'
    assert md['crs'] == \
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84'

    assert 'links' in md
    assert any(link['rel'].endswith('tiling-scheme') for link in md['links'])

    [tile_format,] = [link for link in md['links'] if link['rel'] == 'item']
    assert tile_format['href'].startswith(SERVER_URL)
    assert DATASET in tile_format['href']
    assert ts in tile_format['href']


def test_get_html_metadata_WebMercatorQuad(config):
    provider = MVTPostgreSQLProvider(config)
    title = 'Waterways'
    ts = 'WebMercatorQuad'

    md = provider.get_html_metadata(
        dataset=DATASET,
        server_url=SERVER_URL,
        layer='layer1',
        tileset=ts,
        title=title,
        description='OpenStreetMap Waterways',
        keywords=['osm', 'rivers']
    )

    assert md['id'] == DATASET
    assert md['title'] == title
    assert md['tileset'] == ts

    assert md['collections_path'].startswith(SERVER_URL)
    assert DATASET in md['collections_path']
    assert ts in md['collections_path']

    assert md['json_url'].startswith(SERVER_URL)
    assert DATASET in md['json_url']
    assert ts in md['json_url']


def test_get_html_metadata_WorldCRS84Quad(config):
    provider = MVTPostgreSQLProvider(config)
    title = 'Waterways'
    ts = 'WorldCRS84Quad'

    md = provider.get_html_metadata(
        dataset=DATASET,
        server_url=SERVER_URL,
        layer='layer1',
        tileset=ts,
        title=title,
        description='OpenStreetMap Waterways',
        keywords=['osm', 'rivers']
    )

    assert md['id'] == DATASET
    assert md['title'] == title
    assert md['tileset'] == ts

    assert md['collections_path'].startswith(SERVER_URL)
    assert DATASET in md['collections_path']
    assert ts in md['collections_path']

    assert md['json_url'].startswith(SERVER_URL)
    assert DATASET in md['json_url']
    assert ts in md['json_url']


def test_get_tiles_WebMercatorQuad(config):
    p = MVTPostgreSQLProvider(config)
    tileset = 'WebMercatorQuad'

    # Valid tile, no content
    z, x, y = 14, 10200, 10300
    tile = p.get_tiles(
        tileset=tileset,
        z=z, x=x, y=y,
    )
    assert tile is None

    # Valid tile, content
    z, x, y = 10, 595, 521
    tile = p.get_tiles(
        tileset=tileset,
        z=z, x=x, y=y,
        layer=p.get_layer()
    )
    assert isinstance(tile, bytes)
    assert len(tile) > 0

    # Layer name
    assert b'waterways' in tile
    assert b'default' not in tile

    # Feature properties
    assert b'id' in tile
    assert b'waterway' in tile
    assert b'name' in tile
    assert b'z_index' in tile

    # Tile does not exist in matrixset
    z, x, y = 1, 1000000, 1000000
    with pytest.raises(ProviderTileNotFoundError):
        p.get_tiles(
            tileset=tileset,
            z=z, x=x, y=y
        )


def test_get_tiles_WorldCRS84Quad(config):
    p = MVTPostgreSQLProvider(config)
    tileset = 'WorldCRS84Quad'

    # Valid tile, no content
    z, x, y = 14, 10200, 10300
    tile = p.get_tiles(
        tileset=tileset,
        z=z, x=x, y=y,
    )
    assert tile is None

    # Valid tile, content
    z, x, y = 9, 595, 267
    tile = p.get_tiles(
        tileset=tileset,
        z=z, x=x, y=y,
    )
    assert isinstance(tile, bytes)
    assert len(tile) > 0

    # Layer name
    assert b'waterways' not in tile
    assert b'default' in tile

    # Feature properties
    assert b'id' in tile
    assert b'waterway' in tile
    assert b'name' in tile
    assert b'z_index' in tile

    # Tile does not exist in matrixset
    z, x, y = 1, 1000000, 1000000
    with pytest.raises(ProviderTileNotFoundError):
        p.get_tiles(
            tileset=tileset,
            z=z, x=x, y=y
        )
