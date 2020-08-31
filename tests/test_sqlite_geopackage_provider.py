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

from pygeoapi.provider.base import ProviderItemNotFoundError, \
    ProviderSchemaError, ProviderItemAlreadyExistsError
from pygeoapi.provider.sqlite import SQLiteGPKGProvider


@pytest.fixture()
def config_sqlite():
    return {
        'name': 'SQLiteGPKG',
        'type': 'feature',
        'data': './tests/data/ne_110m_admin_0_countries.sqlite',
        'id_field': 'ogc_fid',
        'table': 'ne_110m_admin_0_countries'
    }


@pytest.fixture()
def config_geopackage():
    return {
        'name': 'SQLiteGPKG',
        'type': 'feature',
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


def test_query_hits_sqlite_geopackage(config_sqlite):
    """Testing hits results type for sqlite/geopackage"""

    p = SQLiteGPKGProvider(config_sqlite)
    results = p.query(resulttype="hits")
    assert results["numberMatched"] == 177
    results = p.query(
        bbox=[28.3373, -5.4099, 32.3761, -3.3924],
        properties=[("continent", "Africa")], resulttype="hits")
    assert results["numberMatched"] == 3


def test_query_with_property_filter_sqlite_geopackage(config_sqlite):
    """Test query  valid features when filtering by property"""

    p = SQLiteGPKGProvider(config_sqlite)
    feature_collection = p.query(properties=[
        ("continent", "Europe")], limit=100)
    features = feature_collection.get('features', None)
    assert len(features) == 39


def test_query_with_property_filter_bbox_sqlite_geopackage(config_sqlite):
    """Test query  valid features when filtering by property"""
    p = SQLiteGPKGProvider(config_sqlite)
    feature_collection = p.query(properties=[("continent", "Europe")],
                                 bbox=[29.3373, -3.4099, 29.3761, -3.3924])
    features = feature_collection.get('features', None)
    assert len(features) == 0


def test_query_bbox_sqlite_geopackage(config_sqlite):
    """Test query with a specified bounding box"""

    psp = SQLiteGPKGProvider(config_sqlite)
    boxed_feature_collection = psp.query(
        bbox=[29.3373, -3.4099, 29.3761, -3.3924]
    )

    assert len(boxed_feature_collection['features']) == 1
    assert 'Burundi' in \
        boxed_feature_collection['features'][0]['properties']['name']


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


def test_get_sqlite_not_existing_item_raise_exception(config_sqlite):
    """Testing query for a not existing object"""
    p = SQLiteGPKGProvider(config_sqlite)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(1234567890)


def test_get_geopackage_not_existing_item_raise_exception(config_geopackage):
    """Testing query for a not existing object"""
    p = SQLiteGPKGProvider(config_geopackage)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_create_sqlite(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    new_feature = {
        'type': 'Feature',
        'id': 1234,
        'geometry': {
            'type': 'MultiPolygon',
            'coordinates': [
                [
                    [
                        [6.15665815595878, 50.80372101501058],
                        [5.606975945670001, 51.03729848896978],
                        [4.973991326526914, 51.47502370869813],
                        [4.047071160507528, 51.26725861266857],
                        [6.15665815595878, 50.80372101501058]
                    ]
                ]
            ]
        },
        'properties': {
            'type': 'Country'
        }
    }
    id = p.create(new_feature)
    assert id == 1234
    feature = p.get(1234)
    assert feature['properties']['type'] == 'Country'


def test_create_sqlite_existing_item_raise_exception(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    new_feature = {
        'type': 'Feature',
        'id': 1234,
        'geometry': {
            'type': 'MultiPolygon',
            'coordinates': [
                [
                    [
                        [6.15665815595878, 50.80372101501058],
                        [5.606975945670001, 51.03729848896978],
                        [4.973991326526914, 51.47502370869813],
                        [4.047071160507528, 51.26725861266857],
                        [6.15665815595878, 50.80372101501058]
                    ]
                ]
            ]
        },
        'properties': {
            'type': 'Country'
        }
    }

    with pytest.raises(ProviderItemAlreadyExistsError):
        p.create(new_feature)


def test_create_sqlite_invalid_schema_raise_exception(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    new_feature = {
        'type': 'Feature',
        'id': 2345,
        'geometry': {
            'type': 'MultiPolygon',
            'coordinates': [
                [
                    [
                        [6.15665815595878, 50.80372101501058],
                        [5.606975945670001, 51.03729848896978],
                        [4.973991326526914, 51.47502370869813],
                        [4.047071160507528, 51.26725861266857],
                        [6.15665815595878, 50.80372101501058]
                    ]
                ]
            ]
        },
        'properties': {
            'i_am_an_alien': 1,
            'type': 'Country'
        }
    }
    with pytest.raises(ProviderSchemaError):
        p.create(new_feature)


def test_replace_sqlite(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'MultiPolygon',
            'coordinates': [
                [
                    [
                        [6.15665815595878, 50.80372101501058],
                        [5.606975945670001, 51.03729848896978],
                        [4.973991326526914, 51.47502370869813],
                        [4.047071160507528, 51.26725861266857],
                        [6.15665815595878, 50.80372101501058]
                    ]
                ]
            ]
        },
        'properties': {
            'type': 'State'
        }
    }
    p.replace(1234, feature)
    feature = p.get(1234)
    assert feature['properties']['type'] == 'State'


def test_replace_sqlite_non_existing_item_raise_exception(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'MultiPolygon',
            'coordinates': [
                [
                    [
                        [6.15665815595878, 50.80372101501058],
                        [5.606975945670001, 51.03729848896978],
                        [4.973991326526914, 51.47502370869813],
                        [4.047071160507528, 51.26725861266857],
                        [6.15665815595878, 50.80372101501058]
                    ]
                ]
            ]
        },
        'properties': {
            'type': 'State'
        }
    }
    with pytest.raises(ProviderItemNotFoundError):
        p.replace(-1, feature)


def test_replace_sqlite_invalid_schema_raise_exception(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'MultiPolygon',
            'coordinates': [
                [
                    [
                        [6.15665815595878, 50.80372101501058],
                        [5.606975945670001, 51.03729848896978],
                        [4.973991326526914, 51.47502370869813],
                        [4.047071160507528, 51.26725861266857],
                        [6.15665815595878, 50.80372101501058]
                    ]
                ]
            ]
        },
        'properties': {
            'i_am_an_alien': 1,
            'type': 'State'
        }
    }
    with pytest.raises(ProviderSchemaError):
        p.replace(1234, feature)


def test_update_sqlite(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    updates = {"modify": [{"name": "type", "value": "Island"}]}
    p.update(1234, updates)
    updated_feature = p.get(1234)
    assert updated_feature['properties']['type'] == "Island"


def test_update_sqlite_non_existing_item_raise_exception(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    updates = {"modify": [{"name": "type", "value": "Island"}]}
    with pytest.raises(ProviderItemNotFoundError):
        p.update(-1, updates)


def test_update_sqlite_invalid_updates_raise_exception(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    updates = {"modify": [{"name": "oldname", "value": "atlantis"}]}
    prev_results = p.get(1234)
    with pytest.raises(ProviderSchemaError):
        p.update(1234, updates)
    results = p.get(1234)
    assert results == prev_results


def test_delete_sqlite(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    p.delete(1234)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(1234)


def test_delete_sqlite_non_existing_item_raise_exception(config_sqlite):
    p = SQLiteGPKGProvider(config_sqlite)
    with pytest.raises(ProviderItemNotFoundError):
        p.delete(-1)


'''
def test_create_geopackage(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    new_feature = {
        'type': 'Feature',
        'id': 111111111,
        'geometry': {
            'type': 'Point',
            'coordinates': [-8.419435, 40.20902399999999]
        },
        'properties': {
            'fclass': 'cafe'
        }
    }
    id = p.create(new_feature)
    assert id == 111111111
    print(p.get(111111111))
    new_feature = p.get(111111111)
    assert new_feature['properties']['type'] == 'Country'


def test_create_geopackage_existing_item_raise_exception(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    new_feature = {
        'type': 'Feature',
        'id': 111111111,
        'geometry': {
            'type': 'Point',
            'coordinates': [-8.419435, 40.20902399999999]
        },
        'properties': {
            'fclass': 'cafe'
        }
    }
    with pytest.raises(ProviderItemAlreadyExistsError):
        p.create(new_feature)


def test_create_geopackage_invalid_schema_raise_exception(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    new_feature = {
        'type': 'Feature',
        'id': 222222222,
        'geometry': {
            'type': 'Point',
            'coordinates': [-8.419435, 40.20902399999999]
        },
        'properties': {
            'i_am_an_alien': 1,
            'fclass': 'cafe'
        }
    }
    with pytest.raises(ProviderSchemaError):
        p.create(new_feature)


def test_replace_geopackage(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [-8.419435, 40.20902399999999]
        },
        'properties': {
            'fclass': 'cafe'
        }
    }
    p.replace(111111111, feature)
    feature = p.get(111111111)
    assert feature['properties']['type'] == 'State'


def test_replace_geopackage_non_existing_item_raise_excpton(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Feature',
            'geometry': {
            'type': 'Point',
            'coordinates': [-8.419435, 40.20902399999999]
        },
        'properties': {
            'fclass': 'cafe'
        }
    }
    with pytest.raises(ProviderItemNotFoundError):
        p.replace(-1, feature)


def test_replace_geopackage_invalid_schema_raise_exception(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [-8.419435, 40.20902399999999]
        },
        'properties': {
            'i_am_an_alien': 1,
            'fclass': 'cafe'
        }
    }
    with pytest.raises(ProviderSchemaError):
        p.replace(111111111, feature)


def test_update_geopackage(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    updates = {"modify": [{"name": "fclass", "value": "hotel"}]}
    p.update(111111111, updates)
    updated_feature = p.get(111111111)
    assert updated_feature['properties']['type'] == "Island"


def test_update_geopackage_non_existing_item_raise_excepton(config_geopackage):
    p = SQLiteGPKGProvider(config_sqlite)
    updates = {"modify": [{"name": "fclass", "value": "hotel"}]}
    with pytest.raises(ProviderItemNotFoundError):
        p.update(-1, updates)


def test_update_geopackage_invalid_updates_raise_exception(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    updates = {"modify": [{"name": "oldname", "value": "transelvenia"}]}
    prev_results = p.get(111111111)
    with pytest.raises(ProviderSchemaError):
        p.update(111111111, updates)
    results = p.get(111111111)
    assert results == prev_results


def test_delete_geopackage(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    p.delete(111111111)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(111111111)


def test_delete_geopackage_non_existing_item_raise_excepton(config_geopackage):
    p = SQLiteGPKGProvider(config_geopackage)
    with pytest.raises(ProviderItemNotFoundError):
        p.delete(-1)
'''
