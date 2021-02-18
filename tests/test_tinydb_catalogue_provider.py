# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
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

import os

import pytest

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.tinydb_ import TinyDBCatalogueProvider


def get_test_file_path(filename):
    """helper function to open test file safely"""

    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


path = get_test_file_path('tests/data/open.canada.ca/sample-records.db')


@pytest.fixture()
def config():
    return {
        'name': 'TinyDBCatalogue',
        'type': 'feature',
        'data': path,
        'id_field': 'externalId'
    }


def test_query(config):
    p = TinyDBCatalogueProvider(config)

    fields = p.get_fields()
    assert len(fields) == 7
    assert fields['record-created'] == 'string'
    assert fields['title'] == 'string'

    results = p.query()
    assert len(results['features']) == 10
    assert results['numberMatched'] == 10
    assert results['numberReturned'] == 10
    assert results['features'][0]['id'] == '07b7ef80-6061-43fc-b874-e2800e9ae547'  # noqa
    assert results['features'][0]['properties']['type'] == 'RI_622'

    results = p.query(q='crops')
    assert len(results['features']) == 6
    assert results['numberMatched'] == 6
    assert results['numberReturned'] == 6

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '07b7ef80-6061-43fc-b874-e2800e9ae547'  # noqa

    results = p.query(bbox=[-154, 42, -52, 84])
    assert len(results['features']) == 10
    assert results['features'][0]['id'] == '07b7ef80-6061-43fc-b874-e2800e9ae547'  # noqa

    results = p.query(startindex=1, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '4e81a467-fc14-4fa0-a1d6-9d65336587c6'  # noqa

    results = p.query(startindex=2, limit=2)
    assert len(results['features']) == 2
    assert results['features'][0]['id'] == 'caeb0592-8c95-4461-b9a5-5fde7f2ccbb3'  # noqa

    results = p.query(sortby=[{'property': 'title', 'order': 'A'}])
    assert results['features'][0]['id'] == '1687cac6-ee13-4866-ab8a-114c2ede7b13'  # noqa

    results = p.query(sortby=[{'property': 'title', 'order': 'D'}])
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
