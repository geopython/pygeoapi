# =================================================================
#
# Authors: Matthew Perry <perrygeo@gmail.com>
#
# Copyright (c) 2018 Matthew Perry
# Copyright (c) 2021 Tom Kralidis
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

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.geojson import GeoJSONProvider


path = '/tmp/test.geojson'


@pytest.fixture()
def fixture():
    data = {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'id': '123-456',
            'geometry': {
                'type': 'Point',
                'coordinates': [125.6, 10.1]},
            'properties': {
                'name': 'Dinagat Islands',
                'foo': 'bar'
            }}
        ]
    }

    with open(path, 'w') as fh:
        fh.write(json.dumps(data))
    return path


@pytest.fixture()
def config():
    return {
        'name': 'GeoJSON',
        'type': 'feature',
        'data': path,
        'id_field': 'id'
    }


def test_query(fixture, config):
    p = GeoJSONProvider(config)

    fields = p.get_fields()
    assert len(fields) == 2
    assert fields['name']['type'] == 'string'

    results = p.query()
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1
    assert results['features'][0]['id'] == '123-456'

    results = p.query(select_properties=['foo'])
    assert len(results['features'][0]['properties']) == 1

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None

    results = p.query(properties=[('foo', 'bar')])
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1


def test_get(fixture, config):
    p = GeoJSONProvider(config)
    results = p.get('123-456')
    assert isinstance(results, dict)
    assert 'Dinagat' in results['properties']['name']


def test_get_not_existing_item_raise_exception(
    fixture, config
):
    """Testing query for a not existing object"""
    p = GeoJSONProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_delete(fixture, config):
    p = GeoJSONProvider(config)
    p.delete('123-456')

    results = p.query()
    assert len(results['features']) == 0


def test_create(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'id': '123-456',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]},
        'properties': {
            'name': 'Null Island'}}

    p.create(new_feature)

    results = p._load()
    assert len(results['features']) == 2
    assert 'Dinagat' in results['features'][0]['properties']['name']
    assert 'Null' in results['features'][1]['properties']['name']


def test_update(fixture, config):
    p = GeoJSONProvider(config)
    new_feature = {
        'type': 'Feature',
        'id': '123-456',
        'geometry': {
            'type': 'Point',
            'coordinates': [0.0, 0.0]},
        'properties': {
            'name': 'Null Island'}}

    p.update('123-456', new_feature)

    # Should be changed
    results = p.get('123-456')
    assert 'Null' in results['properties']['name']
