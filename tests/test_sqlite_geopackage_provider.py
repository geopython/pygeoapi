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

# Needs to be run like: pytest -s test_sqlite_provider.py
# In eclipse we need to set PYGEOAPI_CONFIG, Run>Debug Configurations>
# (Arguments as py.test and set external variables to the correct config path)

import pytest
from pygeoapi.provider.sqlite import SQLiteGPKGProvider


@pytest.fixture()
def config_sqlite():
    return {
        'name': 'SQLiteGPKG',
        'data': './tests/data/ne_110m_admin_0_countries.sqlite',
        'id_field': 'ogc_fid',
        'table': 'ne_110m_admin_0_countries'
    }


@pytest.fixture()
def config_geopackage():
    return {
        'name': 'SQLiteGPKG',
        'data': './tests/data/poi_portugal.gpkg',
        'id_field': 'osm_id',
        'table': 'poi_portugal'
    }


def test_query_sqlite(config_sqlite):
    """Testing query for a valid JSON object with geometry for sqlite3"""

    p = SQLiteGPKGProvider(config_sqlite)
    feature_collection = p.query()
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert features is not None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None


def test_query_geopackage(config_geopackage):
    """Testing query for a valid JSON object with geometry for geopackage"""

    p = SQLiteGPKGProvider(config_geopackage)
    feature_collection = p.query()
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert features is not None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None


def test_query_with_property_filter_sqlite(config_sqlite):
    """Test query  valid features when filtering by property"""

    p = SQLiteGPKGProvider(config_sqlite)
    feature_collection = p.query(properties=[
        ("continent", "Europe")], limit=100)
    features = feature_collection.get('features', None)
    assert len(features) == 39


def test_query_with_property_filter_geopackage(config_geopackage):
    """Test query  valid features when filtering by property"""

    p = SQLiteGPKGProvider(config_geopackage)
    feature_collection = p.query(properties=[
        ("fclass", "cafe")], limit=10000)
    features = feature_collection.get('features', None)

    assert len(features) == 823


def test_query_with_property_filter_bbox_sqlite(config_sqlite):
    """Test query  valid features when filtering by property"""
    p = SQLiteGPKGProvider(config_sqlite)
    feature_collection = p.query(properties=[("continent", "Europe")],
                                 bbox=[29.3373, -3.4099, 29.3761, -3.3924])
    features = feature_collection.get('features', None)
    assert len(features) == 0


def test_query_with_property_filter_bbox_geopackage(config_geopackage):
    """Test query  valid features when filtering by property"""
    p = SQLiteGPKGProvider(config_geopackage)
    feature_collection = p.query(properties=[("fclass", "cafe")],
                                 bbox=[
                                     -16.3991310876,
                                     33.0063015781,
                                     -16.3366454278,
                                     33.0560854323
                                     ])
    features = feature_collection.get('features', None)
    assert len(features) == 0


def test_query_bbox_sqlite(config_sqlite):
    """Test query with a specified bounding box"""

    psp = SQLiteGPKGProvider(config_sqlite)
    boxed_feature_collection = psp.query(
        bbox=[29.3373, -3.4099, 29.3761, -3.3924]
    )

    assert len(boxed_feature_collection['features']) == 1
    assert 'Burundi' in \
        boxed_feature_collection['features'][0]['properties']['name']


def test_query_bbox_geopackage(config_geopackage):
    """Test query with a specified bounding box"""

    psp = SQLiteGPKGProvider(config_geopackage)
    boxed_feature_collection = psp.query(
        bbox=[-16.3991310876, 33.0063015781, -16.3366454278, 33.0560854323]
    )

    assert len(boxed_feature_collection['features']) == 5


def test_get_sqlite(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    result = p.get(118)
    assert isinstance(result, dict)
    assert 'geometry' in result
    assert 'properties' in result
    assert 'id' in result
    assert 'Netherlands' in result['properties']['admin']


def test_get_geopackage(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    result = p.get(536678593)
    assert isinstance(result, dict)
    assert 'geometry' in result
    assert 'properties' in result
    assert 'id' in result
    assert 'Académico' in result['properties']['name']
