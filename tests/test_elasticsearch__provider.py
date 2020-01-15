# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
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

from pygeoapi.provider.elasticsearch_ import ElasticsearchProvider


@pytest.fixture()
def config():
    return {
        'name': 'Elasticsearch',
        'data': 'http://localhost:9200/ne_110m_populated_places_simple',  # noqa
        'id_field': 'geonameid'
    }


def test_query(config):
    p = ElasticsearchProvider(config)
    results = p.query()
    assert len(results['features']) == 10
    assert results['numberMatched'] == 242
    assert results['numberReturned'] == 10
    assert results['features'][0]['id'] == 6691831
    assert results['features'][0]['properties']['nameascii'] == 'Vatican City'

    results = p.query(properties=[('nameascii', 'Vatican City')])
    assert len(results['features']) == 4
    assert results['numberMatched'] == 4
    assert results['numberReturned'] == 4

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == 6691831

    results = p.query(startindex=2, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == 3168070

    results = p.query(sortby=[{'property': 'nameascii', 'order': 'A'}])
    assert results['features'][0]['properties']['nameascii'] == 'Abidjan'

    results = p.query(sortby=[{'property': 'nameascii', 'order': 'D'}])
    assert results['features'][0]['properties']['nameascii'] == 'Zagreb'

    results = p.query(sortby=[{'property': 'scalerank', 'order': 'A'}])
    assert results['features'][0]['properties']['scalerank'] == 0

    results = p.query(sortby=[{'property': 'scalerank', 'order': 'D'}])
    assert results['features'][0]['properties']['scalerank'] == 8

    assert len(results['features'][0]['properties']) == 37

    results = p.query(sortby=[{'property': 'nameascii', 'order': 'D'}],
                      limit=10001)
    assert results['features'][0]['properties']['nameascii'] == 'Zagreb'
    assert len(results['features']) == 242
    assert results['numberMatched'] == 242
    assert results['numberReturned'] == 242

    config['properties'] = ['nameascii']
    p = ElasticsearchProvider(config)
    results = p.query()
    assert len(results['features'][0]['properties']) == 1


def test_get(config):
    p = ElasticsearchProvider(config)
    results = p.get('404')
    assert results is None

    result = p.get('3413829')
    assert result['id'] == 3413829
    assert result['properties']['ls_name'] == 'Reykjavik'
