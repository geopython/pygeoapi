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
                 'password': 'postgres'
                 },
        'id_field': 'osm_id',
        'table': 'hotosm_bdi_waterways',
        'allow_property_filtering': True
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
    stream_features = list(filter(lambda feature: feature['properties']['waterway'] == 'stream', features))
    assert(len(features) == len(stream_features))

    feature_collection = p.query()
    features = feature_collection.get('features', None)
    stream_features = list(filter(lambda feature: feature['properties']['waterway'] == 'stream', features))
    other_features = list(filter(lambda feature: feature['properties']['waterway'] != 'stream', features))
    assert(len(features) != len(stream_features))
    assert(len(other_features) != 0)


def test_get(config):
    """Testing query for a specific object"""
    p = PostgreSQLProvider(config)
    result = p.get(29701937)
    assert isinstance(result, dict)
    assert 'geometry' in result
    assert 'properties' in result
    assert 'id' in result
    assert 'Kanyosha' in result['properties']['name']
