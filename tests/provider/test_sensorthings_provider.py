# =================================================================
#
# Authors: Benjamin Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2025 Benjamin Webb
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

from pygeoapi.provider.base import ProviderInvalidDataError
from pygeoapi.provider.sensorthings import SensorThingsProvider


@pytest.fixture()
def config():
    return {
        'name': 'SensorThings',
        'type': 'feature',
        'data': 'http://localhost:8888/FROST-Server/v1.1/Datastreams',
        'rel_link': 'http://localhost:5000',
        'intralink': True,
        'time_field': 'phenomenonTime'
    }


@pytest.fixture()
def post_body():
    return {
        '@iot.id': 121,
        'name': 'Temperature Datastream',
        'description': 'Datastream for measuring temperature in Celsius.',
        'observationType': 'http://www.opengis.net/def/observationType/OGC-OM/2.0/OM_Measurement', # noqa
        'unitOfMeasurement': {
            'name': 'Degree Celsius',
            'symbol': 'degC',
            'definition': 'http://www.qudt.org/qudt/owl/1.0.0/unit/Instances.html#DegreeCelsius' # noqa
        },
        'Thing': {'@iot.id': 2},
        'ObservedProperty': {'@iot.id': 3},
        'Sensor': {'@iot.id': 5},
        'properties': {
            'uri': 'https://geoconnex.us/test/datastream'
        }
    }


def test_query_datastreams(config):
    p = SensorThingsProvider(config)
    fields = p.get_fields()
    assert len(fields) == 16
    assert fields['Thing']['type'] == 'number'
    assert fields['Observations']['type'] == 'number'
    assert fields['@iot.id']['type'] == 'number'
    assert fields['name']['type'] == 'string'

    results = p.query()
    assert len(results['features']) == 10
    assert results['numberReturned'] == 10
    assert len(results['features'][0]['properties']['Observations']) == 17

    assert results['features'][0]['geometry']['coordinates'][0] == -108.7483
    assert results['features'][0]['geometry']['coordinates'][1] == 35.6711

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '1'

    results = p.query(offset=2, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == '3'

    assert len(results['features'][0]['properties']) == 19

    results = p.query(bbox=[-109, 36, -106, 37])
    assert results['numberReturned'] == 8

    results = p.query(select_properties=['Thing'])
    assert len(results['features'][0]['properties']) == 1

    results = p.query(select_properties=['Thing', 'Observations'])
    assert len(results['features'][0]['properties']) == 2

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None


def test_query_observations(config):
    config['properties'] = ['Datastream', 'phenomenonTime',
                            'FeatureOfInterest', 'result']
    config['data'] = 'http://localhost:8888/FROST-Server/v1.1/'
    config['entity'] = 'Observations'
    p = SensorThingsProvider(config)

    results = p.query(limit=10, resulttype='hits')
    assert results['numberMatched'] == 5298

    r = p.query(bbox=[-109, 36, -106, 37], resulttype='hits')
    assert r['numberMatched'] == 222

    results = p.query(limit=10001, resulttype='hits')
    assert results['numberMatched'] == 5298

    results = p.query(properties=[('result', 7475), ])
    assert results['features'][0]['properties']['result'] == 7475

    results = p.query()
    assert len(results['features'][0]['properties']) == 4

    results = p.query(sortby=[{'property': 'phenomenonTime', 'order': '+'}])
    assert results['features'][0]['properties'][
        'phenomenonTime'] == '1944-10-14T12:00:00Z'

    results = p.query(sortby=[{'property': 'phenomenonTime', 'order': '-'}])
    assert results['features'][0]['properties'][
        'phenomenonTime'] == '2021-02-09T15:55:01Z'

    results = p.query(sortby=[{'property': 'result', 'order': '+'}])
    assert results['features'][0]['properties']['result'] == 0.0091

    results = p.query(sortby=[{'property': 'result', 'order': '-'}])
    assert results['features'][0]['properties']['result'] == 7476

    results = p.query(datetime_='../2000-01-01T00:00:00Z',
                      sortby=[{'property': 'phenomenonTime', 'order': '-'}])
    assert results['features'][0]['properties'][
        'phenomenonTime'] == '1999-12-29T00:00:00Z'

    results = p.query(datetime_='2000-01-01T00:00:00.00Z/..',
                      sortby=[{'property': 'phenomenonTime', 'order': '+'}])
    assert results['features'][0]['properties'][
        'phenomenonTime'] == '2000-02-07T22:45:00Z'


def test_get(config):
    p = SensorThingsProvider(config)

    result = p.get('9')
    assert result['id'] == '9'
    assert result['properties']['name'] == 'Depth Below Surface'
    assert isinstance(result['properties']['Thing'], dict)


def test_custom_expand(config):
    p = SensorThingsProvider(config)
    fields = p.get_fields()
    assert 'Observations' in fields
    assert 'ObservedProperty' in fields
    assert 'Sensor' in fields

    config['expand'] = 'Thing/Locations'
    p = SensorThingsProvider(config)
    fields = p.get_fields()
    assert len(fields) == 12
    assert 'Observations' not in fields
    assert 'ObservedProperty' not in fields
    assert 'Sensor' not in fields

    config['expand'] = 'Thing/Locations,Observations'
    p = SensorThingsProvider(config)
    fields = p.get_fields()
    assert len(fields) == 14
    assert 'Observations' in fields
    assert 'ObservedProperty' not in fields
    assert 'Sensor' not in fields


def test_custom_uri_field(config):
    config['uri_field'] = 'uri'
    config['properties'] = ['name']
    p = SensorThingsProvider(config)

    result = p.get('9')
    assert result['id'] == '9'
    assert result['properties']['name'] == 'Depth Below Surface'
    assert result['properties']['uri'] == \
        'https://geoconnex.us/iow/sta-demo/timeseries/9'
    assert len(result['properties']) == 2

    config['uri_field'] = 'bad_uri'
    p = SensorThingsProvider(config)
    with pytest.raises(ProviderInvalidDataError,
                       match=".*Unable to find uri field: bad_uri"):
        result = p.get('9')


def test_transactions(config, post_body):
    p = SensorThingsProvider(config)
    results = p.query(resulttype='hits')
    assert results['numberMatched'] == 120

    id = p.create(post_body)
    assert id == 121
    results = p.query(resulttype='hits')
    assert results['numberMatched'] == 121

    datastream = p.get(121)
    assert datastream['properties']['name'] == 'Temperature Datastream'

    post_body['name'] = 'Temperature'
    result = p.update(id, post_body)
    assert result is True

    datastream = p.get(121)
    assert datastream['properties']['name'] == 'Temperature'

    assert p.delete(id) is True
    results = p.query(resulttype='hits')
    assert results['numberMatched'] == 120
