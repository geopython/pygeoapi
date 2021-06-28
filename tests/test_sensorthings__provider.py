# =================================================================
#
# Authors: Benjamin Webb <benjamin.miller.webb@gmail.com>
#
# Copyright (c) 2021 Benjamin Webb
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

from pygeoapi.provider.sensorthings import SensorthingsProvider


@pytest.fixture()
def config():
    return {
        'name': 'Sensorthings',
        'type': 'feature',
        'data': 'https://sta-demo.internetofwater.dev/api/v1.1/',
        'rel_link': 'http://localhost:5000',
        'entity': 'Datastreams',
        'intralink': True,
        'time_field': 'phenomenonTime'
    }


def test_query(config):
    p = SensorthingsProvider(config)

    fields = p.get_fields()
    assert len(fields) == 15
    assert fields['Thing']['type'] == 'number'
    assert fields['Observations']['type'] == 'number'
    assert fields['@iot.id']['type'] == 'number'
    assert fields['name']['type'] == 'string'

    results = p.query()
    assert len(results['features']) == 10
    assert results['numberReturned'] == 10
    assert len(results['features'][0]['properties']['Thing']) == 2
    assert len(results['features'][0]['properties']['Observations']) == 18

    assert results['features'][0]['geometry']['coordinates'][0] == -105.581
    assert results['features'][0]['geometry']['coordinates'][1] == 36.713

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '9'

    results = p.query(startindex=2, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '11'

    assert len(results['features'][0]['properties']) == 17

    results = p.query(resulttype='hits')
    assert results['numberMatched'] == 100

    results = p.query(bbox=[-109, 36, -106, 37])
    assert results['numberReturned'] == 8

    results = p.query(select_properties=['Thing'])
    assert len(results['features'][0]['properties']) == 1

    results = p.query(select_properties=['Thing', 'Observations'])
    assert len(results['features'][0]['properties']) == 2

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None

    config['properties'] = ['Datastream', 'phenomenonTime',
                            'FeatureOfInterest', 'result']
    config['entity'] = 'Observations'
    p = SensorthingsProvider(config)

    results = p.query(properties=[('result', 4), ])
    assert results['features'][0]['properties']['result'] == 4

    results = p.query()
    assert len(results['features'][0]['properties']) == 4

    results = p.query(sortby=[{'property': 'phenomenonTime', 'order': '+'}])
    assert results['features'][0]['properties'][
        'phenomenonTime'] == '1944-10-14T12:00:00.000Z'

    results = p.query(sortby=[{'property': 'phenomenonTime', 'order': '-'}])
    assert results['features'][0]['properties'][
        'phenomenonTime'] == '2021-02-09T15:55:01.000Z'

    results = p.query(sortby=[{'property': 'result', 'order': '+'}])
    assert results['features'][0]['properties']['result'] == 0.0051

    results = p.query(sortby=[{'property': 'result', 'order': '-'}])
    assert results['features'][0]['properties']['result'] == 7476

    results = p.query(datetime_='../2000-01-01T00:00:00.00Z',
                      sortby=[{'property': 'phenomenonTime', 'order': '-'}])
    assert results['features'][0]['properties'][
        'phenomenonTime'] == '2000-01-01T00:00:00.000Z'

    results = p.query(datetime_='2000-01-01T00:00:00.00Z/..',
                      sortby=[{'property': 'phenomenonTime', 'order': '+'}])
    assert results['features'][0]['properties'][
        'phenomenonTime'] == '2000-01-01T00:00:00.000Z'


def test_get(config):
    p = SensorthingsProvider(config)

    result = p.get('9')
    assert result['id'] == '9'
    assert result['properties']['name'] == 'Depth Below Surface'
