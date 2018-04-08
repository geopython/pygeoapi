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

from pygeoapi.provider.csv_ import CSVProvider


path = '/tmp/pygeoapi-test.csv'


@pytest.fixture()
def fixture():
    data = """id,stn_id,datetime,value,geom
371,35,"2001-10-30T14:24:55Z",89.9,POINT(-75 45)
377,35,"2002-10-30T18:31:38Z",93.9,POINT(-75 45)
238,2147,"2007-10-30T08:57:29Z",103.5,POINT(-79 43)
297,2147,"2003-10-30T07:37:29Z",93.5,POINT(-79 43)
964,604,"2000-10-30T18:24:39Z",99.9,POINT(-122 49)
"""
    with open(path, 'w') as fh:
        fh.write(data)
    return path


@pytest.fixture()
def config():
    return {
        'name': 'CSV',
        'data': path,
        'id_field': 'id'
    }


def test_query(fixture, config):
    p = CSVProvider(config)
    results = p.query()
    assert len(results['features']) == 5
    assert results['features'][0]['ID'] == '371'
    assert results['features'][0]['properties']['value'] == '89.9'

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['ID'] == '371'

    results = p.query(startindex=2, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['ID'] == '238'


def test_get(fixture, config):
    p = CSVProvider(config)
    results = p.get('404')
    assert results is None

    result = p.get('964')
    assert result['ID'] == '964'
    assert result['properties']['value'] == '99.9'
