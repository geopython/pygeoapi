# =================================================================
#
# Authors: Matthew Perry <perrygeo@gmail.com>
#
# Copyright (c) 2018 Matthew Perry
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

import json
import pytest

from pygeoapi.provider.base import (ProviderItemNotFoundError,
                                    ProviderSchemaError,
                                    ProviderItemAlreadyExistsError)
from pygeoapi.provider.geojson import GeoJSONProvider


path = '/tmp/test.geojson'


def are_same(value1, value2):
    return str(value1) == str(value2)


@pytest.fixture()
def fixture():
    data = {
        'type': 'FeatureCollection',
        'features':
        [{
            'type': 'Feature',
            'id': '123-456',
            'geometry': {
                'type': 'Point',
                'coordinates': [125.6, 10.1]
            },
            'properties': {
                'name': 'Dinagat Islands',
                'area': 500
            }
         }]
    }

    with open(path, 'w') as fh:
        fh.write(json.dumps(data))
    return path


@pytest.fixture()
def config():
    return {
        'name': 'GeoJSON',
        'data': path,
        'id_field': 'id'
    }


def test_query(fixture, config):
    p = GeoJSONProvider(config)

    fields = p.get_fields()
    assert len(fields) == 2
    assert fields['name'] == 'string'
    assert fields['area'] == 'string'

    results = p.query()
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1
    assert results['features'][0]['id'] == '123-456'


def test_get(fixture, config):
    p = GeoJSONProvider(config)
    results = p.get('123-456')
    assert isinstance(results, dict)
    assert 'Dinagat' in results['properties']['name']


def test_get_non_existing_item_raise_exception(
    fixture, config
):
    """Testing query for a not existing object"""
    p = GeoJSONProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get('NON EXISTING ID')


def test_delete(fixture, config):
    p = GeoJSONProvider(config)
    p.delete('123-456')

    results = p.query()
    assert len(results['features']) == 0


def test_delete_non_existing_item_raise_exception(fixture, config):
    p = GeoJSONProvider(config)

    with pytest.raises(ProviderItemNotFoundError):
        p.delete('NON EXISTING ID')


def test_create(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'id': '789',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]
        },
        'properties': {
            'name': 'Null Island'
        }
    }

    p.create(new_feature)

    results = p._load()
    assert len(results['features']) == 2
    assert 'Dinagat' in results['features'][0]['properties']['name']
    assert 'Null' in results['features'][1]['properties']['name']


def test_create_existing_item_raise_exception(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'id': '123-456',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]
        },
        'properties': {
            'name': 'Null Island'
        }
    }

    with pytest.raises(ProviderItemAlreadyExistsError):
        p.create(new_feature)


def test_create_invalid_schema_raise_exception(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'id': '567',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]
        },
        'properties': {
            'name': 'Caimen Island',
            'i_am_an_alien': 1
        }
    }

    with pytest.raises(ProviderSchemaError):
        p.create(new_feature)


def test_replace(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]
        },
        'properties': {
            'name': 'Null Island'
        }
    }

    p.replace('123-456', new_feature)

    results = p.get('123-456')
    assert 'Null' in results['properties']['name']


def test_replace_non_existing_item_raise_exception(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]
        },
        'properties': {
            'name': 'Null Island'
        }
    }

    with pytest.raises(ProviderItemNotFoundError):
        p.replace('NON EXISTING ID', new_feature)


def test_replace_invalid_schema_raise_exception(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]
        },
        'properties': {
            'stn_id': 50,
            'i_am_an_alien': 1
        }
    }

    with pytest.raises(ProviderSchemaError):
        p.replace('123-456', new_feature)


def test_update(fixture, config):
    p = GeoJSONProvider(config)
    updates = {"add":
               [{"name": "nearby", "value": "shutter island"}],
               "modify":
               [{"name": "name", "value": "atlantis"}],
               "remove":
               ["area"]
               }

    updated_feature = p.update('123-456', updates)

    assert 'nearby' in updated_feature['properties']
    assert updated_feature['properties']['nearby'] == "shutter island"
    assert updated_feature['properties']['name'] == "atlantis"
    assert 'area' not in updated_feature['properties']

    results = p.get('123-456')
    assert 'nearby' in results['properties']
    assert results['properties']['nearby'] == "shutter island"
    assert results['properties']['name'] == "atlantis"
    assert 'area' not in results['properties']


def test_update_non_existing_item_raise_exception(fixture, config):
    p = GeoJSONProvider(config)
    updates = {"add":
               [{"name": "nearby", "value": "shutter island"}],
               "modify":
               [{"name": "name", "value": "atlantis"}],
               "remove":
               ["area"]
               }

    with pytest.raises(ProviderItemNotFoundError):
        p.update('NON EXISTING ID', updates)


def test_update_invalid_updates_raise_exception(fixture, config):
    p = GeoJSONProvider(config)
    invalid_add = {"add": [{"name": "name", "value": "shutter island"}],
                   "modify": [], "remove": []}
    invalid_modify = {"add": [], "modify": [{"name": "rule", "value": "zeus"}],
                      "remove": []}
    invalid_remove = {"add": [], "modify": [], "remove": ["cost"]}

    prev_results = p.get('123-456')

    with pytest.raises(ProviderSchemaError):
        p.update('123-456', invalid_add)
        p.update('123-456', invalid_modify)
        p.update('123-456', invalid_remove)

    results = p.get('123-456')
    assert results == prev_results
