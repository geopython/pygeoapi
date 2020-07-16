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

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.csv_ import CSVProvider


path = '/tmp/pygeoapi-test.csv'


@pytest.fixture()
def fixture():
    data = """id,stn_id,datetime,value,lat,long
371,35,"2001-10-30T14:24:55Z",89.9,45,-75
377,35,"2002-10-30T18:31:38Z",93.9,45,-75
238,2147,"2007-10-30T08:57:29Z",103.5,43,-79
297,2147,"2003-10-30T07:37:29Z",93.5,43,-79
964,604,"2000-10-30T18:24:39Z",99.9,49,-122
"""
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
    assert fields['value'] == 'string'
    assert fields['stn_id'] == 'string'

    results = p.query()
    assert len(results['features']) == 5
    assert results['numberMatched'] == 5
    assert results['numberReturned'] == 5
    assert results['features'][0]['id'] == '371'
    assert results['features'][0]['properties']['value'] == '89.9'

    assert results['features'][0]['geometry']['coordinates'][0] == -75.0
    assert results['features'][0]['geometry']['coordinates'][1] == 45.0

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '371'

    results = p.query(startindex=2, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '238'

    assert len(results['features'][0]['properties']) == 3

    # ===========================
    # Sample CQL filter test case

    results = p.query(filter_expression='stn_id < 2147 AND id > 377')
    assert len(results['features']) == 1

    results = p.query(filter_expression='stn_id < 2147 OR id > 377')
    assert len(results['features']) == 3

    results = p.query(filter_expression='stn_id = 35')
    assert len(results['features']) == 2

    results = p.query(filter_expression='stn_id <> 35')
    assert len(results['features']) == 3

    results = p.query(filter_expression='stn_id <> 35 AND id >= 238 OR id <= 964') # noqa
    assert len(results['features']) == 3

    results = p.query(filter_expression='stn_id <> 35 AND id > 238 AND id < 964') # noqa
    assert len(results['features']) == 1
    # ===========================

    config['properties'] = ['value', 'stn_id']
    p = CSVProvider(config)
    results = p.query()
    assert len(results['features'][0]['properties']) == 2


def test_get(fixture, config):
    p = CSVProvider(config)

    result = p.get('964')
    assert result['id'] == '964'
    assert result['properties']['value'] == '99.9'


def test_get_not_existing_item_raise_exception(fixture, config):
    """Testing query for a not existing object"""
    p = CSVProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get('404')
