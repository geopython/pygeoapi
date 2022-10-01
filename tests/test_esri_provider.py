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

from datetime import datetime
import pytest

from pygeoapi.provider.esri import ESRIServiceProvider
from pygeoapi.util import DATETIME_FORMAT

TIME_FIELD = 'Date_Time'


@pytest.fixture()
def config():
    #  National Hurricane Center ()
    # source: ESRI, NOAA/National Weather Service
    return {
        'name': 'ESRI',
        'type': 'feature',
        'data': 'https://sampleserver6.arcgisonline.com/arcgis/rest/services/Hurricanes/MapServer/0', # noqa
        'id_field': 'OBJECTID',
        'time_field': TIME_FIELD
    }


def test_query(config):
    p = ESRIServiceProvider(config)

    results = p.query()
    assert results['features'][0]['id'] == 1
    assert results['numberReturned'] == 10

    results = p.query(limit=50)
    assert results['numberReturned'] == 50

    results = p.query(offset=10)
    assert results['features'][0]['id'] == 11
    assert results['numberReturned'] == 10

    results = p.query(limit=10)
    assert len(results['features']) == 10
    assert results['numberMatched'] == 406

    results = p.query(limit=10001, resulttype='hits')
    assert results['numberMatched'] == 406


def test_geometry(config):
    p = ESRIServiceProvider(config)

    results = p.query()
    geometry = results['features'][0]['geometry']
    assert geometry['coordinates'] == [-17.99999999990007, 10.800000000099885]

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None

    config['crs'] = 3857
    p = ESRIServiceProvider(config)
    results = p.query()
    geometry = results['features'][0]['geometry']
    assert geometry['coordinates'] == [-2003750.8342678, 1209433.8422282021]

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None


def test_query_bbox(config):
    p = ESRIServiceProvider(config)

    bbox = [-171, 18, -67, 71]
    results = p.query(bbox=bbox)
    assert results['numberReturned'] == 10
    assert results['numberMatched'] == 128

    feature = results['features'][0]
    assert feature['properties']['EVENTID'] == 'Beryl'

    x, y = feature['geometry']['coordinates']
    xmin, ymin, xmax, ymax = bbox
    assert xmin <= x <= xmax
    assert ymin <= y <= ymax


def test_query_properties(config):
    p = ESRIServiceProvider(config)

    results = p.query()
    assert len(results['features'][0]['properties']) == 10

    # Query by property
    results = p.query(properties=[('EVENTID', 'Beryl'), ])
    assert results['features'][0]['properties']['EVENTID'] == 'Beryl'

    results = p.query(properties=[('EVENTID', 'Alberto'), ], resulttype='hits')
    assert results['numberMatched'] == 87

    # Query for property
    results = p.query(select_properties=['WINDSPEED', 'PRESSURE'])
    assert len(results['features'][0]['properties']) == 2
    assert 'WINDSPEED' in results['features'][0]['properties']

    # Query with configured properties
    config['properties'] = ['OBJECTID', 'EVENTID', 'TIME']
    p = ESRIServiceProvider(config)

    results = p.query()
    props = results['features'][0]['properties']
    assert all(p in props for p in config['properties'])
    assert len(props) == 3

    results = p.query(properties=[('EVENTID', 'Beryl'), ])
    assert results['features'][0]['properties']['EVENTID'] == 'Beryl'

    results = p.query(select_properties=['GEOGSTATE', ])
    assert len(results['features'][0]['properties']) == 1


def test_query_sortby_datetime(config):

    p = ESRIServiceProvider(config)

    results = p.query(sortby=[{'property': 'EVENTID', 'order': '+'}])
    assert results['features'][0]['properties']['EVENTID'] == 'Alberto'

    results = p.query(sortby=[{'property': 'EVENTID', 'order': '-'}])
    assert results['features'][0]['properties']['EVENTID'] == 'Nadine'

    def feature_time(r):
        props = r['features'][0]['properties']
        timestamp = props[TIME_FIELD]/1000
        timestamp = datetime.fromtimestamp(timestamp)
        return timestamp.strftime(DATETIME_FORMAT)

    results = p.query(sortby=[{'property': TIME_FIELD, 'order': '+'}])
    assert results['features'][0]['properties'][TIME_FIELD] == 965354400000

    results = p.query(sortby=[{'property': TIME_FIELD, 'order': '-'}])
    assert results['features'][0]['properties'][TIME_FIELD] == 972244800000

    results = p.query(datetime_='../2000-09-01',
                      sortby=[{'property': TIME_FIELD, 'order': '-'}])
    assert results['features'][0]['properties'][TIME_FIELD] == 967212000000

    results = p.query(datetime_='2000-09-01/..',
                      sortby=[{'property': TIME_FIELD, 'order': '+'}])
    assert results['features'][0]['properties'][TIME_FIELD] == 967838400000


def test_get(config):
    p = ESRIServiceProvider(config)

    result = p.get(6)
    assert result['id'] == 6
    assert result['properties']['EVENTID'] == 'Alberto'
