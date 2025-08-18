# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2025 Tom Kralidis
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
import shutil

import pytest

from pygeoapi.provider.base import (ProviderItemNotFoundError,
                                    ProviderInvalidQueryError)
from pygeoapi.provider.tinydb_ import TinyDBProvider

from ..util import get_test_file_path

path = get_test_file_path('tests/data/canada-hydat-daily-mean-02HC003.tinydb')


@pytest.fixture()
def data():
    return json.dumps({
        'type': 'Feature',
        'geometry': {
            'type': 'Polygon',
            'coordinates': [[
                [100.0, 0.0], [101.0, 0.0], [101.0, 1.0],
                [100.0, 1.0], [100.0, 0.0]
                ]]
        },
        'properties': {
            'identifier': 123,
            'title': 'test item',
            'description': 'test item'
        }
    })


@pytest.fixture()
def data_no_id():
    return json.dumps({
        'type': 'Feature',
        'geometry': {
            'type': 'Polygon',
            'coordinates': [[
                [100.0, 0.0], [101.0, 0.0], [101.0, 1.0],
                [100.0, 1.0], [100.0, 0.0]
                ]]
        },
        'properties': {
            'title': 'test item',
            'description': 'test item'
        }
    })


@pytest.fixture()
def config(tmp_path):
    tmp_file = tmp_path / 'sample-features.tinydb'
    shutil.copy(path, tmp_file)
    return {
        'name': 'TinyDB',
        'type': 'feature',
        'data': tmp_file,
        'id_field': 'IDENTIFIER',
        'time_field': 'DATE'
    }


def test_domains(config):
    p = TinyDBProvider(config)

    domains, current = p.get_domains()

    assert current

    expected_properties = ['DATE', 'FLOW', 'FLOW_SYMBOL_EN', 'FLOW_SYMBOL_FR',
                           'IDENTIFIER', 'LEVEL', 'PROV_TERR_STATE_LOC',
                           'STATION_NAME', 'STATION_NUMBER']

    assert sorted(domains.keys()) == expected_properties

    assert len(domains['STATION_NUMBER']) == 1

    domains, current = p.get_domains(['STATION_NAME'])

    assert current

    assert list(domains.keys()) == ['STATION_NAME']


def test_query(config):
    p = TinyDBProvider(config)

    fields = p.get_fields()
    assert len(fields) == 11
    assert fields['FLOW']['type'] == 'number'
    assert fields['DATE']['type'] == 'string'
    assert fields['DATE']['format'] == 'date'

    results = p.query()
    assert len(results['features']) == 10
    assert results['numberMatched'] == 50
    assert results['numberReturned'] == 10
    assert results['features'][0]['id'] == '02HC003.1975-10-03'
    assert results['features'][0]['properties']['STATION_NUMBER'] == '02HC003'

    results = p.query(properties=[('FLOW', 2.039999961853028)])
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1

    results = p.query(properties=[('STATION_NAME', 'HUMBER RIVER AT WESTON')])
    assert len(results['features']) == 10
    assert results['numberMatched'] == 50
    assert results['numberReturned'] == 10

    results = p.query(properties=[('IDENTIFIER', '02HC003.1975-10-03')])
    assert len(results['features']) == 1
    assert results['numberMatched'] == 1
    assert results['numberReturned'] == 1

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '02HC003.1975-10-03'

    results = p.query(datetime_='2017/..')
    assert len(results['features']) == 3
    assert results['features'][0]['id'] == '02HC003.2017-05-23'

    results = p.query(datetime_='../2017')
    assert len(results['features']) == 10
    assert results['features'][0]['id'] == '02HC003.1975-10-03'

    results = p.query(datetime_='1987-11-11/2000-11-11')
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '02HC003.1995-01-29'

    results = p.query(bbox=[-154, 42, -52, 84])
    assert len(results['features']) == 10
    assert results['features'][0]['id'] == '02HC003.1975-10-03'

    results = p.query(offset=1, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '02HC003.1975-10-02'

    results = p.query(offset=2, limit=2)
    assert len(results['features']) == 2
    assert results['features'][0]['id'] == '02HC003.1975-10-01'

    results = p.query(sortby=[{'property': 'DATE', 'order': '+'}])
    assert results['features'][0]['id'] == '02HC003.1955-09-01'

    results = p.query(sortby=[{'property': 'DATE', 'order': '-'}])
    assert results['features'][0]['id'] == '02HC003.2017-05-27'


def test_get_invalid_property(config):
    """Testing query for an invalid property name"""
    p = TinyDBProvider(config)
    with pytest.raises(ProviderInvalidQueryError):
        p.query(properties=[('\'foo', 'bar')])


def test_get(config):
    p = TinyDBProvider(config)

    result = p.get('02HC003.1975-10-02')
    assert result['id'] == '02HC003.1975-10-02'
    assert result['properties']['FLOW'] == 2.059999942779541


def test_get_not_existing_item_raise_exception(config):
    """Testing query for a not existing object"""
    p = TinyDBProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get('404')


def test_transactions_create(config, data):
    """Testing transactional capabilities"""

    p = TinyDBProvider(config)

    new_id = p.create(data)
    assert new_id == 123

    assert p.update(123, data)

    assert p.delete(123)


def test_transactions_create_no_id(config, data_no_id):
    """Testing transactional capabilities with incoming feature without ID"""

    p = TinyDBProvider(config)

    new_id = p.create(data_no_id)
    assert new_id is not None

    data_got = p.get(new_id)
    assert data_got['id'] == new_id
    assert data_got['geometry'] == json.loads(data_no_id)['geometry']

    assert p.update(new_id, json.dumps(data_got))

    assert p.delete(new_id)
