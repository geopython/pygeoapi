# =================================================================
#
# Authors: Timo Tuunanen <timo.tuunanen@rdvelho.com>
#
# Copyright (c) 2019 Timo Tuunanen
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

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.mongo import MongoProvider

monogourl = 'mongodb://localhost:27017/testdb'
mongocollection = 'testplaces'


@pytest.fixture()
def config():
    return {
        'name': 'MongoDB',
        'type': 'feature',
        'data': monogourl,
        'collection': mongocollection
    }


def delete_by_name(provided, name):
    # delete all existing
    results = provided.query(properties=[('name', name)])
    for res in results['features']:
        provided.delete(res['id'])


def init(provider):
    # delete all existing Unit Test and Null Islands
    delete_by_name(provider, 'Unit Test Island')
    delete_by_name(provider, 'Null Island')


def test_query(config):
    p = MongoProvider(config)
    init(p)
    results = p.query()
    assert len(results['features']) == 10
    assert results['numberMatched'] == 243
    assert results['numberReturned'] == 10
    assert results['features'][0]['properties']['nameascii'] == 'Vatican City'

    results = p.query(properties=[('nameascii', 'Vatican City')])
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1
    assert results['features'][0]['properties']['nameascii'] == 'Vatican City'

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['properties']['nameascii'] == 'Vatican City'

    results = p.query(offset=2, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['properties']['nameascii'] == 'Vaduz'

    results = p.query(sortby=[{'property': 'nameascii', 'order': '+'}])
    assert results['features'][0]['properties']['nameascii'] == 'Abidjan'

    results = p.query(sortby=[{'property': 'nameascii', 'order': '-'}])
    assert results['features'][0]['properties']['nameascii'] == 'Zagreb'

    results = p.query(sortby=[{'property': 'scalerank', 'order': '+'}])
    assert results['features'][0]['properties']['scalerank'] == 0

    results = p.query(sortby=[{'property': 'scalerank', 'order': '-'}])
    assert results['features'][0]['properties']['scalerank'] == 8

    assert len(results['features'][0]['properties']) == 37

    results = p.query(skip_geometry=True)
    for feature in results['features']:
        assert feature['geometry'] is None


def test_get(config):
    p = MongoProvider(config)
    init(p)

    res = p.query(properties=[['nameascii', 'Reykjavik']])
    result = p.get(res['features'][0]['id'])
    assert isinstance(result, dict)
    assert 'Reykjavik' in result['properties']['ls_name']


def test_get_not_existing_item_raise_exception(config):
    """Testing query for a not existing object"""
    p = MongoProvider(config)
    init(p)
    with pytest.raises(ProviderItemNotFoundError):
        p.get('123456789012345678901234')


def test_get_fields(config):
    p = MongoProvider(config)
    init(p)
    results = p.get_fields()
    assert len(results) == 37


def test_create_and_delete(config):
    p = MongoProvider(config)
    init(p)

    new_feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]},
        'properties': {
            'name': 'Null Island'}}

    p.create(new_feature)
    results = p.query()
    assert results['numberMatched'] == 244

    results = p.query(properties=[('name', 'Null Island')])
    assert len(results['features']) == 1
    assert 'Null Island' in results['features'][0]['properties']['name']

    p.delete(results['features'][0]['id'])

    results = p.query(properties=[('name', 'Null Island')])
    assert len(results['features']) == 0

    results = p.query()
    assert results['numberMatched'] == 243


def test_update(config):
    p = MongoProvider(config)
    init(p)

    new_feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]},
        'properties': {
            'name': 'Unit Test Island'}}

    p.create(new_feature)

    res = p.query(properties=[('name', 'Unit Test Island')])
    assert len(res['features']) == 1

    updated_feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]},
        'properties': {
            'name': 'Null Island'
        }
    }

    p.update(res['features'][0]['id'], updated_feature)

    # Should be changed
    results = p.get(res['features'][0]['id'])
    assert 'Null Island' in results['properties']['name']
    delete_by_name(p, 'Null Island')


def test_update_safe_id(config):
    p = MongoProvider(config)
    init(p)

    new_feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]},
        'properties': {
            'name': 'Unit Test Island'}}

    p.create(new_feature)

    updated_feature = {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]
        },
        'properties': {
            'name': 'Null Island',
        },
        'id': '123456789012345678901234'
    }

    res = p.query(properties=[('name', 'Unit Test Island')])
    assert len(res['features']) == 1
    p.update(res['features'][0]['id'], updated_feature)

    # Don't let the id change, should not exist
    with pytest.raises(ProviderItemNotFoundError):
        p.get('123456789012345678901234')

    # Should still be at the old id
    results = p.get(res['features'][0]['id'])
    assert 'Null Island' in results['properties']['name']
    delete_by_name(p, 'Null Island')
