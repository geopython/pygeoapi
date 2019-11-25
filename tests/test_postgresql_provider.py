# =================================================================
#
# Authors: Just van den Broecke <justb4@gmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2019 Just van den Broecke
# Copyright (c) 2019 Tom Kralidis
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

import pytest
from pygeoapi.provider.postgresql import PostgreSQLProvider


@pytest.fixture()
def config():
    return {
        'name': 'PostgreSQL',
        'data': {'host': '127.0.0.1',
                 'dbname': 'test',
                 'user': 'postgres',
                 'password': 'postgres',
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


def test_query_with_property_filter(config):
    """Test query  valid features when filtering by property"""
    p = PostgreSQLProvider(config)
    feature_collection = p.query(properties=[("waterway", "stream")])
    features = feature_collection.get('features', None)
    stream_features = list(
        filter(lambda feature: feature['properties']['waterway'] == 'stream',
               features))
    assert (len(features) == len(stream_features))

    feature_collection = p.query()
    features = feature_collection.get('features', None)
    stream_features = list(
        filter(lambda feature: feature['properties']['waterway'] == 'stream',
               features))
    other_features = list(
        filter(lambda feature: feature['properties']['waterway'] != 'stream',
               features))
    assert (len(features) != len(stream_features))
    assert (len(other_features) != 0)


def test_query_bbox(config):
    """Test query with a specified bounding box"""
    psp = PostgreSQLProvider(config)
    boxed_feature_collection = psp.query(
        bbox=[29.3373, -3.4099, 29.3761, -3.3924]
    )
    assert len(boxed_feature_collection['features']) == 5


def test_get(config):
    """Testing query for a specific object"""
    p = PostgreSQLProvider(config)
    result = p.get(29701937)
    assert isinstance(result, dict)
    assert 'geometry' in result
    assert 'properties' in result
    assert 'id' in result
    assert 'Kanyosha' in result['properties']['name']


@pytest.fixture()
def col_prop_config():
    return {
        'name': 'PostgreSQL',
        'data': {'host': '127.0.0.1',
                 'dbname': 'test',
                 'user': 'postgres',
                 'password': 'postgres',
                 'search_path': ['osm', 'public']
                 },
        'id_field': 'osm_id',
        'column_property_mapping': {
            'name': 'name',
            'waterway': 'waterWay',
            'covered': 'covered',
            'width': 'width',
            'depth': 'depth',
            'z_index': 'zIndex'
        },
        'table': 'hotosm_bdi_waterways',
        'geom_field': 'foo_geom'
    }


def test_query_with_col_prop(col_prop_config):
    """Testing query for a valid JSON object with geometry"""

    p = PostgreSQLProvider(col_prop_config)
    feature_collection = p.query()
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert features is not None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    assert properties.get('zIndex', None) is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None


def test_query_with_col_prop_and_with_property_filter(col_prop_config):
    """Test query  valid features when filtering by property"""
    p = PostgreSQLProvider(col_prop_config)
    feature_collection = p.query(properties=[("waterWay", "stream")])
    features = feature_collection.get('features', None)
    stream_features = list(
        filter(lambda feature: feature['properties']['waterWay'] == 'stream',
               features))
    assert (len(features) == len(stream_features))

    feature_collection = p.query()
    features = feature_collection.get('features', None)
    stream_features = list(
        filter(lambda feature: feature['properties']['waterWay'] == 'stream',
               features))
    other_features = list(
        filter(lambda feature: feature['properties']['waterWay'] != 'stream',
               features))
    assert (len(features) != len(stream_features))
    assert (len(other_features) != 0)


def test_query_with_col_prop_bbox(col_prop_config):
    """Test query with a specified bounding box"""
    psp = PostgreSQLProvider(col_prop_config)
    boxed_feature_collection = psp.query(
        bbox=[29.3373, -3.4099, 29.3761, -3.3924]
    )
    assert len(boxed_feature_collection['features']) == 5


def test_get_with_col_prop(col_prop_config):
    """Testing query for a specific object"""
    p = PostgreSQLProvider(col_prop_config)
    result = p.get(29701937)
    assert isinstance(result, dict)
    assert 'geometry' in result
    assert 'properties' in result
    assert 'zIndex' in result.get('properties')
    assert 'id' in result
    assert 'Kanyosha' in result['properties']['name']
