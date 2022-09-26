# =================================================================
#
# Authors: Just van den Broecke <justb4@gmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#
# Copyright (c) 2019 Just van den Broecke
# Copyright (c) 2019 Tom Kralidis
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
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

import pytest

from pygeofilter.parsers.ecql import parse

from pygeoapi.provider.base import (
    ProviderConnectionError,
    ProviderItemNotFoundError,
    ProviderQueryError
)
from pygeoapi.provider.postgresql import PostgreSQLProvider

import os
PASSWORD = os.environ.get('POSTGRESQL_PASSWORD', 'postgres')


@pytest.fixture()
def config():
    return {
        'name': 'PostgreSQL',
        'type': 'feature',
        'data': {'host': '127.0.0.1',
                 'dbname': 'test',
                 'user': 'postgres',
                 'password': PASSWORD,
                 'search_path': ['osm', 'public']
                 },
        'id_field': 'osm_id',
        'table': 'hotosm_bdi_waterways',
        'geom_field': 'foo_geom'
    }


def test_query(config):
    """Testing query for a valid JSON object with geometry"""
    p = PostgreSQLProvider(config)
    feature_collection = p.query()
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert features is not None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None


def test_query_materialised_view(config):
    """Testing query using a materialised view"""
    config_materialised_view = config.copy()
    config_materialised_view['table'] = 'hotosm_bdi_drains'
    provider = PostgreSQLProvider(config_materialised_view)

    # Only ID, width and depth properties should be available
    assert set(provider.get_fields().keys()) == {"osm_id", "width", "depth"}


def test_query_with_property_filter(config):
    """Test query valid features when filtering by property"""
    p = PostgreSQLProvider(config)
    feature_collection = p.query(properties=[("waterway", "stream")])
    features = feature_collection.get('features', None)
    stream_features = list(
        filter(lambda feature: feature['properties']['waterway'] == 'stream',
               features))
    assert (len(features) == len(stream_features))

    feature_collection = p.query(limit=50)
    features = feature_collection.get('features', None)
    stream_features = list(
        filter(lambda feature: feature['properties']['waterway'] == 'stream',
               features))
    other_features = list(
        filter(lambda feature: feature['properties']['waterway'] != 'stream',
               features))
    assert (len(features) != len(stream_features))
    assert (len(other_features) != 0)


def test_query_with_config_properties(config):
    """
    Test that query is restricted by properties in the config.
    No properties should be returned that are not requested.
    Note that not all requested properties have to exist in the query result.
    """
    config.update(
        {'properties': ['name', 'waterway', 'width', 'does_not_exist']})
    provider = PostgreSQLProvider(config)
    result = provider.query()
    feature = result.get('features')[0]
    properties = feature.get('properties', None)
    for property_name in properties.keys():
        assert property_name in config["properties"]


@pytest.mark.parametrize("property_filter, expected", [
    ([], 14776),
    ([("waterway", "stream")], 13930),
    ([("waterway", "this does not exist")], 0),
])
def test_query_hits_with_property_filter(config, property_filter, expected):
    """Test query resulttype=hits"""
    provider = PostgreSQLProvider(config)
    results = provider.query(properties=property_filter, resulttype="hits")
    assert results["numberMatched"] == expected


def test_query_bbox(config):
    """Test query with a specified bounding box"""
    psp = PostgreSQLProvider(config)
    boxed_feature_collection = psp.query(
        bbox=[29.3373, -3.4099, 29.3761, -3.3924]
    )
    assert len(boxed_feature_collection['features']) == 5


def test_query_sortby(config):
    """Test query with sorting"""
    psp = PostgreSQLProvider(config)
    up = psp.query(sortby=[{'property': 'osm_id', 'order': '+'}])
    assert up['features'][0]['id'] == 13990765
    down = psp.query(sortby=[{'property': 'osm_id', 'order': '-'}])
    assert down['features'][0]['id'] == 620735702

    name = psp.query(sortby=[{'property': 'name', 'order': '+'}])
    assert name['features'][0]['properties']['name'] == 'Agasasa'


def test_query_skip_geometry(config):
    """Test query without geometry"""
    provider = PostgreSQLProvider(config)
    result = provider.query(skip_geometry=True)
    feature = result['features'][0]
    assert feature['geometry'] is None


@pytest.mark.parametrize('properties', [
    ['name'],
    ['name', 'waterway'],
    ['name', 'waterway', 'this does not exist']
])
def test_query_select_properties(config, properties):
    """Test query with selected properties"""
    provider = PostgreSQLProvider(config)
    result = provider.query(select_properties=properties)
    feature = result['features'][0]

    expected = set(provider.get_fields().keys()).intersection(properties)
    assert set(feature['properties'].keys()) == expected


@pytest.mark.parametrize('id_, prev, next_', [
    (29701937, 29698243, 29704504),
    (13990765, 13990765, 25469515),  # First item, prev should be id_
    (620735702, 620420337, 620735702),  # Last item, next should be id_
])
def test_get_simple(config, id_, prev, next_):
    """Testing query for a specific object and identifying prev/next"""
    p = PostgreSQLProvider(config)
    result = p.get(id_)
    assert result['id'] == id_
    assert 'geometry' in result
    assert 'properties' in result
    assert result['type'] == 'Feature'
    assert 'foo_geom' not in result['properties']  # geometry is separate

    assert result['prev'] == prev
    assert result['next'] == next_


def test_get_not_existing_item_raise_exception(config):
    """Testing query for a not existing object"""
    p = PostgreSQLProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


@pytest.mark.parametrize('cql, expected_ids', [
  ("osm_id BETWEEN 80800000 AND 80900000",
   [80827787, 80827793, 80835468, 80835470, 80835472, 80835474,
    80835475, 80835478, 80835483, 80835486]),
  ("osm_id BETWEEN 80800000 AND 80900000 AND waterway = 'stream'",
   [80835470]),
  ("osm_id BETWEEN 80800000 AND 80900000 AND waterway ILIKE 'sTrEam'",
   [80835470]),
  ("osm_id BETWEEN 80800000 AND 80900000 AND waterway LIKE 's%'",
   [80835470]),
  ("osm_id BETWEEN 80800000 AND 80900000 AND name IN ('Muhira', 'Mpanda')",
   [80835468, 80835472, 80835475, 80835478]),
  ("osm_id BETWEEN 80800000 AND 80900000 AND name IS NULL",
   [80835474, 80835483]),
  ("osm_id BETWEEN 80800000 AND 80900000 AND BBOX(foo_geom, 29, -2.8, 29.2, -2.9)",  # noqa
   [80827793, 80835470, 80835472, 80835483, 80835489]),
  ("osm_id BETWEEN 80800000 AND 80900000 AND "
   "CROSSES(foo_geom,  LINESTRING(29.091 -2.731, 29.253 -2.845))",
   [80835470, 80835472, 80835489])
])
def test_query_cql(config, cql, expected_ids):
    """Test a variety of CQL queries"""
    ast = parse(cql)
    provider = PostgreSQLProvider(config)

    feature_collection = provider.query(filterq=ast)
    assert feature_collection.get('type', None) == 'FeatureCollection'

    features = feature_collection.get('features', None)
    ids = [feature["id"] for feature in features]
    assert ids == expected_ids


def test_query_cql_properties_bbox_filters(config):
    """Test query with CQL, properties and bbox filters"""
    # Arrange
    properties = [('waterway', 'stream')]
    bbox = [29, -2.8, 29.2, -2.9]
    filterq = parse("osm_id BETWEEN 80800000 AND 80900000")
    expected_ids = [80835470]

    # Act
    provider = PostgreSQLProvider(config)
    feature_collection = provider.query(filterq=filterq,
                                        properties=properties,
                                        bbox=bbox)

    # Assert
    ids = [feature["id"] for feature in feature_collection.get('features')]
    assert ids == expected_ids


def test_instantiation(config):
    """Test attributes are correctly set during instantiation."""
    # Arrange
    expected_fields = {
        'blockage': 'VARCHAR(80)',
        'covered': 'VARCHAR(80)',
        'depth': 'VARCHAR(80)',
        'layer': 'VARCHAR(80)',
        'name': 'VARCHAR(80)',
        'natural': 'VARCHAR(80)',
        'osm_id': 'INTEGER',
        'tunnel': 'VARCHAR(80)',
        'water': 'VARCHAR(80)',
        'waterway': 'VARCHAR(80)',
        'width': 'VARCHAR(80)',
        'z_index': 'VARCHAR(80)'
    }

    # Act
    provider = PostgreSQLProvider(config)

    # Assert
    assert provider.name == "PostgreSQL"
    assert provider.table == "hotosm_bdi_waterways"
    assert provider.id_field == "osm_id"
    assert provider.get_fields() == expected_fields


@pytest.mark.parametrize('bad_data, exception, match', [
    ({'table': 'bad_table'}, ProviderQueryError,
     'Table.*not found in schema.*'),
    ({'data': {'bad': 'data'}}, ProviderConnectionError,
     r'Could not connect to .*None:\*\*\*@'),
    ({'id_field': 'bad_id'}, ProviderQueryError,
     r'No such id_field column \(bad_id\) on osm.hotosm_bdi_waterways.'),
])
def test_instantiation_with_bad_config(config, bad_data, exception, match):
    # Arrange
    config.update(bad_data)

    # Act and assert
    with pytest.raises(exception, match=match):
        PostgreSQLProvider(config)


def test_instantiation_with_bad_credentials(config):
    # Arrange
    config['data'].update({'user': 'bad_user'})
    match = r'Could not connect to .*bad_user:\*\*\*@'

    # Act and assert
    with pytest.raises(ProviderConnectionError, match=match):
        PostgreSQLProvider(config)


def test_engine_store(config):
    provider1 = PostgreSQLProvider(config)

    # Same database connection details
    different_table = config.copy()
    different_table.update(table="hotosm_bdi_drains")
    provider2 = PostgreSQLProvider(different_table)
    assert repr(provider2._engine) == repr(provider1._engine)
    assert provider2._engine is provider1._engine

    # Although localhost is 127.0.0.1, this should get different engine
    different_host = config.copy()
    different_host["data"]["host"] = "localhost"
    provider3 = PostgreSQLProvider(different_host)
    assert provider3._engine is not provider1._engine
