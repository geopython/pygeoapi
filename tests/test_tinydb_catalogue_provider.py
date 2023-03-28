# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2023 Tom Kralidis
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

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.tinydb_ import TinyDBCatalogueProvider

from .util import get_test_file_path

path = get_test_file_path('tests/data/open.canada.ca/sample-records.tinydb')


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
    tmp_file = tmp_path / 'sample-records.tinydb'
    shutil.copy(path, tmp_file)
    return {
        'name': 'TinyDBCatalogue',
        'type': 'feature',
        'data': tmp_file,
        'id_field': 'externalId',
        'time_field': 'created'
    }


def test_query(config):
    p = TinyDBCatalogueProvider(config)

    fields = p.get_fields()
    assert len(fields) == 9
    assert fields['created']['type'] == 'string'
    assert fields['title']['type'] == 'string'
    assert fields['q']['type'] == 'string'

    results = p.query()
    assert len(results['features']) == 10
    assert results['numberMatched'] == 10
    assert results['numberReturned'] == 10
    assert results['features'][0]['id'] == 'e5a71860-827c-453f-990e-0e0ba0ee67bb'  # noqa
    assert results['features'][0]['properties']['type'] == 'RI_622'

    for term in ['crops', 'Crops', 'CROPS', 'CrOpS', 'CROps', 'CRops']:
        results = p.query(q=term)
        assert len(results['features']) == 6
        assert results['numberMatched'] == 6
        assert results['numberReturned'] == 6

    results = p.query(q='crops barley')
    assert len(results['features']) == 2
    assert results['numberMatched'] == 2
    assert results['numberReturned'] == 2

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == 'e5a71860-827c-453f-990e-0e0ba0ee67bb'  # noqa

    results = p.query(datetime_='2020/..')
    assert len(results['features']) == 6
    assert results['features'][0]['id'] == '64e70d29-57a3-44a8-b55c-d465639d1e2e'  # noqa

    results = p.query(datetime_='../2020')
    assert len(results['features']) == 4
    assert results['features'][0]['id'] == 'e5a71860-827c-453f-990e-0e0ba0ee67bb'  # noqa

    results = p.query(datetime_='2020-09-17/2020-12-01')
    assert len(results['features']) == 6
    assert results['features'][0]['id'] == '64e70d29-57a3-44a8-b55c-d465639d1e2e'  # noqa

    results = p.query(bbox=[-154, 42, -52, 84])
    assert len(results['features']) == 10
    assert results['features'][0]['id'] == 'e5a71860-827c-453f-990e-0e0ba0ee67bb'  # noqa

    results = p.query(offset=1, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '64e70d29-57a3-44a8-b55c-d465639d1e2e'  # noqa

    results = p.query(offset=2, limit=2)
    assert len(results['features']) == 2
    assert results['features'][0]['id'] == 'd3028ad0-b0d0-47ff-bcc3-d383881e17cd'  # noqa

    results = p.query(sortby=[{'property': 'title', 'order': '+'}])
    assert results['features'][0]['id'] == '1687cac6-ee13-4866-ab8a-114c2ede7b13'  # noqa

    results = p.query(sortby=[{'property': 'title', 'order': '-'}])
    assert results['features'][0]['id'] == '8a09413a-0a01-4aab-8925-720d987deb20'  # noqa


def test_get(config):
    p = TinyDBCatalogueProvider(config)

    result = p.get('caeb0592-8c95-4461-b9a5-5fde7f2ccbb3')
    assert result['id'] == 'caeb0592-8c95-4461-b9a5-5fde7f2ccbb3'
    assert result['properties']['title'] == 'Probability of Ice freeze days (herbaceous crops) during non-growing season (<-5°C)'  # noqa


def test_get_not_existing_item_raise_exception(config):
    """Testing query for a not existing object"""
    p = TinyDBCatalogueProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get('404')


def test_transactions_create(config, data):
    """Testing transactional capabilities"""

    p = TinyDBCatalogueProvider(config)

    new_id = p.create(data)
    assert new_id == 123

    assert p.update(123, data)

    assert p.delete(123)


def test_transactions_create_no_id(config, data_no_id):
    """Testing transactional capabilities with incoming feature without ID"""

    p = TinyDBCatalogueProvider(config)

    new_id = p.create(data_no_id)
    assert new_id is not None

    data_got = p.get(new_id)
    assert data_got['id'] == new_id
    assert data_got['geometry'] == json.loads(data_no_id)['geometry']

    assert p.update(new_id, json.dumps(data_got))

    assert p.delete(new_id)
