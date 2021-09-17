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

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.postgresql import PostgreSQLProvider


@pytest.fixture()
def config():
    return {
        'name': 'PostgreSQL',
        'type': 'feature',
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


def test_query_hits(config):
    """Test query resulttype=hits with properties"""
    psp = PostgreSQLProvider(config)
    results = psp.query(resulttype="hits")
    assert results["numberMatched"] == 14776

    results = psp.query(
        bbox=[29.3373, -3.4099, 29.3761, -3.3924], resulttype="hits")
    assert results["numberMatched"] == 5

    results = psp.query(properties=[("waterway", "stream")], resulttype="hits")
    assert results["numberMatched"] == 13930


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
    psp = PostgreSQLProvider(config)
    skipped = psp.query(skip_geometry=True)
    assert skipped['features'][0]['geometry'] is None


def test_query_select_properties(config):
    """Test query with selected properties"""
    psp = PostgreSQLProvider(config)
    props = psp.query(select_properties=['name'])
    assert len(props['features'][0]['properties']) == 1


def test_get(config):
    """Testing query for a specific object"""
    p = PostgreSQLProvider(config)
    result = p.get(29701937)
    assert isinstance(result, dict)
    assert 'geometry' in result
    assert 'properties' in result
    assert 'id' in result
    assert 'Kanyosha' in result['properties']['name']


def test_get_not_existing_item_raise_exception(config):
    """Testing query for a not existing object"""
    p = PostgreSQLProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)
