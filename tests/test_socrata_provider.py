# =================================================================
#
# Authors: Benjamin Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2022 Benjamin Webb
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

from pygeoapi.provider.socrata import SODAServiceProvider


@pytest.fixture()
def config():
    # USGS Earthquakes
    # source: [USGS](http://usgs.gov)
    # URL: https://soda.demo.socrata.com/dataset/emdb-u46w
    # License: CC0 3.0 https://creativecommons.org/licenses/by-sa/3.0/
    return {
        'name': 'SODAServiceProvider',
        'type': 'feature',
        'data': 'https://soda.demo.socrata.com/',
        'resource_id': 'emdb-u46w',
        'id_field': 'earthquake_id',
        'time_field': 'datetime',
        'geom_field': 'location'
    }


def test_query(config):
    p = SODAServiceProvider(config)

    results = p.query()
    assert results['features'][0]['id'] == '00388610'
    assert results['numberReturned'] == 10

    results = p.query(limit=50)
    assert results['numberReturned'] == 50
    feature_10 = results['features'][10]

    results = p.query(offset=10)
    assert results['features'][0] == feature_10
    assert results['numberReturned'] == 10

    results = p.query(limit=10)
    assert len(results['features']) == 10
    assert results['numberMatched'] == 1006

    results = p.query(limit=10001, resulttype='hits')
    assert results['numberMatched'] == 1006


def test_geometry(config):
    p = SODAServiceProvider(config)

    results = p.query()
    geometry = results['features'][0]['geometry']
    assert geometry['coordinates'] == [-117.6135, 41.1085]

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None

    bbox = [-109, 37, -102, 41]
    results = p.query(bbox=bbox)
    assert results['numberMatched'] == 0

    bbox = [-178.2, 18.9, -66.9, 71.4]
    results = p.query(bbox=bbox)
    assert results['numberMatched'] == 817

    feature = results['features'][0]
    x, y = feature['geometry']['coordinates']
    xmin, ymin, xmax, ymax = bbox
    assert xmin <= x <= xmax
    assert ymin <= y <= ymax


def test_query_properties(config):
    p = SODAServiceProvider(config)

    results = p.query()
    assert len(results['features'][0]['properties']) == 11

    # Query by property
    results = p.query(properties=[('region', 'Nevada'), ])
    assert results['numberMatched'] == 19

    results = p.query(properties=[('region', 'Northern California'), ])
    assert results['numberMatched'] == 119

    # Query for property
    results = p.query(select_properties=['magnitude', ])
    assert len(results['features'][0]['properties']) == 1
    assert 'magnitude' in results['features'][0]['properties']

    # Query with configured properties
    config['properties'] = ['region', 'datetime', 'magnitude']
    p = SODAServiceProvider(config)

    results = p.query()
    props = results['features'][0]['properties']
    assert all(p in props for p in config['properties'])
    assert len(props) == 3

    results = p.query(properties=[('region', 'Central California'), ])
    assert results['numberMatched'] == 92

    results = p.query(select_properties=['region', ])
    assert len(results['features'][0]['properties']) == 1


def test_query_sortby_datetime(config):
    p = SODAServiceProvider(config)

    results = p.query(sortby=[{'property': 'datetime', 'order': '+'}])
    dt = results['features'][0]['properties']['datetime']
    assert dt == '2012-09-07T23:00:42.000'

    results = p.query(sortby=[{'property': 'datetime', 'order': '-'}])
    dt = results['features'][0]['properties']['datetime']
    assert dt == '2012-09-14T22:38:01.000'

    results = p.query(datetime_='../2012-09-10T00:00:00.00Z',
                      sortby=[{'property': 'datetime', 'order': '-'}])
    dt = results['features'][0]['properties']['datetime']
    assert dt == '2012-09-09T23:57:50.000'

    results = p.query(datetime_='2012-09-10T00:00:00.00Z/..',
                      sortby=[{'property': 'datetime', 'order': '+'}])
    dt = results['features'][0]['properties']['datetime']
    assert dt == '2012-09-10T00:04:44.000'


def test_get(config):
    p = SODAServiceProvider(config)

    result = p.get('00388610')
    assert result['id'] == '00388610'
    assert result['properties']['magnitude'] == '2.7'
