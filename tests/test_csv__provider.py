# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2018 Tom Kralidis
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

import pytest

from pygeoapi.provider.base import (ProviderItemNotFoundError,
                                    ProviderSchemaError,
                                    ProviderItemAlreadyExistsError)
from pygeoapi.provider.csv_ import CSVProvider


path = '/tmp/test.csv'


def are_same(value1, value2):
    return str(value1) == str(value2)


@pytest.fixture()
def fixture():
    data = 'id,stn_id,datetime,value,lat,long\n'\
        '371,35,"2001-10-30T14:24:55Z",89.9,45,-75\n'\
        '377,35,"2002-10-30T18:31:38Z",93.9,45,-75\n'\
        '238,2147,"2007-10-30T08:57:29Z",103.5,43,-79\n'\
        '297,2147,"2003-10-30T07:37:29Z",93.5,43,-79\n'\
        '964,604,"2000-10-30T18:24:39Z",99.9,49,-122\n'

    with open(path, 'w') as fh:
        fh.write(data)
    return path


@pytest.fixture()
def config():
    return {
        'name': 'CSV',
        'data': path,
        'id_field': 'id',
        'geometry': {
            'x_field': 'long',
            'y_field': 'lat'
        }
    }


def test_query(fixture, config):
    p = CSVProvider(config)
    fields = p.get_fields()
    assert len(fields) == 6
    results = p.query()
    assert len(results['features']) == 5
    assert results['numberMatched'] == 5
    assert results['numberReturned'] == 5
    assert results['features'][0]['id'] == 371
    assert results['features'][0]['properties']['value'] == 89.9
    assert results['features'][0]['geometry']['coordinates'][0] == -75.0
    assert results['features'][0]['geometry']['coordinates'][1] == 45.0
    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == 371
    results = p.query(startindex=2, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == 238
    assert len(results['features'][0]['properties']) == 3
    config['properties'] = ['value', 'stn_id']
    p = CSVProvider(config)
    results = p.query()
    assert len(results['features'][0]['properties']) == 2


def test_get(fixture, config):
    p = CSVProvider(config)
    result = p.get(371)
    assert result['id'] == 371
    assert result['properties']['value'] == 89.9
    assert result['properties']['stn_id'] == 35
    assert result['properties']['datetime'] == '2001-10-30T14:24:55Z'


def test_get_not_existing_item_raise_exception(fixture, config):
    """Testing query for a not existing object"""
    p = CSVProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(404)


def test_delete(config):
    p = CSVProvider(config)
    p.delete(371)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(371)


def test_delete_non_existing_item_raise_exception(fixture, config):
    p = CSVProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.delete(9999)


def test_create(fixture, config):
    p = CSVProvider(config)
    new_feature = {
        'type': 'Feature',
        'id': 301,
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]
        },
        'properties': {
            'stn_id': 50
        }
    }
    p.create(new_feature)
    feature = p.get(301)
    assert are_same(feature['properties']['stn_id'],
                    new_feature['properties']['stn_id'])
    assert are_same(feature['geometry']['coordinates'][0],
                    new_feature['geometry']['coordinates'][0])
    assert are_same(feature['geometry']['coordinates'][0],
                    new_feature['geometry']['coordinates'][0])


def test_create_existing_item_raise_exception(fixture, config):
    p = CSVProvider(config)
    new_feature = {
        'type': 'Feature',
        'id': 964,
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]
        },
        'properties': {
            'stn_id': 50
        }
    }
    with pytest.raises(ProviderItemAlreadyExistsError):
        p.create(new_feature)


def test_create_invalid_schema_raise_exception(fixture, config):
    p = CSVProvider(config)
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
        p.create(new_feature)


def test_replace(fixture, config):
    p = CSVProvider(config)
    new_feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]
        },
        'properties': {
            'stn_id': 50
        }
    }
    p.replace(377, new_feature)
    # new_feature properties should overwrite feature properties
    feature = p.get(377)
    assert are_same(feature['properties']['stn_id'],
                    new_feature['properties']['stn_id'])
    assert are_same(feature['geometry']['coordinates'][0],
                    new_feature['geometry']['coordinates'][0])
    assert are_same(feature['geometry']['coordinates'][0],
                    new_feature['geometry']['coordinates'][0])


def test_replace_non_existing_item_raise_exception(fixture, config):
    p = CSVProvider(config)
    new_feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]
        },
        'properties': {
            'stn_id': 50
        }
    }
    with pytest.raises(ProviderItemNotFoundError):
        p.replace(9999, new_feature)


def test_replace_invalid_schema_raise_exception(fixture, config):
    p = CSVProvider(config)
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
        p.create(new_feature)


def test_update(fixture, config):
    p = CSVProvider(config)
    updates = {'add':
               [{'name': 'name', 'value': 'abc'}],
               'modify':
               [{'name': 'stn_id', 'value': 4545}],
               'remove':
               ['datetime']
               }
    updated_feature = p.update(377, updates)
    assert 'name' in updated_feature['properties']
    assert are_same(updated_feature['properties']['name'], 'abc')
    assert are_same(updated_feature['properties']['stn_id'], 4545)
    assert ('datetime' not in updated_feature['properties']) or \
        (updated_feature['properties']['datetime'] is None)
    results = p.get(377)
    assert 'name' in results['properties']
    assert are_same(results['properties']['name'], 'abc')
    assert are_same(results['properties']['stn_id'], 4545)
    assert ('datetime' not in updated_feature['properties']) or \
        (updated_feature['properties']['datetime'] is None)


def test_update_non_existing_item_raise_exception(fixture, config):
    p = CSVProvider(config)
    updates = {'add':
               [{'name': 'name', 'value': 'abc'}],
               'modify':
               [{'name': 'stn_id', 'value': 4545}],
               'remove':
               ['datetime']
               }
    with pytest.raises(ProviderItemNotFoundError):
        p.update(9999, updates)


def test_update_invalid_updates_raise_exception(fixture, config):
    p = CSVProvider(config)
    invalid_add = {"add": [{'name': 'value', 'value': 77}],
                   "modify": [], "remove": []}
    invalid_modify = {"add": [], "modify": [{"name": "count", "value": 54}],
                      "remove": []}
    invalid_remove = {"add": [], "modify": [], "remove": ["cost"]}
    prev_results = p.get(377)
    with pytest.raises(ProviderSchemaError):
        p.update(377, invalid_add)
        p.update(377, invalid_modify)
        p.update(377, invalid_remove)
    results = p.get(377)
    assert results == prev_results
