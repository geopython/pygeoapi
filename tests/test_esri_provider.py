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

TIME_FIELD = 'START_DATE'


@pytest.fixture()
def config():
    # WATERS Mapping Services
    # source: EPA Water Mapping Services
    # URL: https://www.epa.gov/waterdata/waters-mapping-services
    # License: https://edg.epa.gov/EPA_Data_License.html
    return {
        'name': 'ESRI',
        'type': 'feature',
        'data': 'https://watersgeo.epa.gov/arcgis/rest/services/OWRAD_NP21/TMDL_NP21/MapServer/0', # noqa
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
    assert results['numberMatched'] == 2496

    results = p.query(limit=10001, resulttype='hits')
    assert results['numberMatched'] == 2496


def test_geometry(config):
    p = ESRIServiceProvider(config)

    results = p.query()
    geometry = results['features'][0]['geometry']
    assert geometry['coordinates'] == [-71.22138524800965, 43.83429729362349]

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None

    config['crs'] = 3857
    p = ESRIServiceProvider(config)
    results = p.query()
    geometry = results['features'][0]['geometry']
    assert geometry['coordinates'] == [-7928328.339400001, 5439835.013800003]

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None


def test_query_bbox(config):
    p = ESRIServiceProvider(config)

    bbox = [-109, 37, -102, 41]
    results = p.query(bbox=bbox)
    assert results['numberReturned'] == 1

    feature = results['features'][0]
    assert feature['properties']['GEOGSTATE'] == 'CO'

    x, y = feature['geometry']['coordinates']
    xmin, ymin, xmax, ymax = bbox
    assert xmin <= x <= xmax
    assert ymin <= y <= ymax


def test_query_properties(config):
    p = ESRIServiceProvider(config)

    results = p.query()
    assert len(results['features'][0]['properties']) == 26

    # Query by property
    results = p.query(properties=[('GEOGSTATE', 'CO'), ])
    assert results['features'][0]['properties']['GEOGSTATE'] == 'CO'

    results = p.query(properties=[('GEOGSTATE', 'CO'), ], resulttype='hits')
    assert results['numberMatched'] == 1

    # Query for property
    results = p.query(select_properties=['GEOGSTATE', ])
    assert len(results['features'][0]['properties']) == 1
    assert 'GEOGSTATE' in results['features'][0]['properties']

    # Query with configured properties
    config['properties'] = ['OBJECTID', 'GEOGSTATE', 'CYCLE_YEAR']
    p = ESRIServiceProvider(config)

    results = p.query()
    props = results['features'][0]['properties']
    assert all(p in props for p in config['properties'])
    assert len(props) == 3

    results = p.query(properties=[('GEOGSTATE', 'CO'), ])
    assert results['features'][0]['properties']['GEOGSTATE'] == 'CO'

    results = p.query(select_properties=['GEOGSTATE', ])
    assert len(results['features'][0]['properties']) == 1


def test_query_sortby_datetime(config):

    p = ESRIServiceProvider(config)

    results = p.query(sortby=[{'property': 'CYCLE_YEAR', 'order': '+'}])
    assert results['features'][0]['properties']['CYCLE_YEAR'] == '1998'

    results = p.query(sortby=[{'property': 'CYCLE_YEAR', 'order': '-'}])
    assert results['features'][0]['properties']['CYCLE_YEAR'] == '2012'

    def feature_time(r):
        props = r['features'][0]['properties']
        timestamp = props[TIME_FIELD]/1000
        timestamp = datetime.fromtimestamp(timestamp)
        return timestamp.strftime(DATETIME_FORMAT)

    results = p.query(sortby=[{'property': TIME_FIELD, 'order': '+'}])
    assert feature_time(results) == '1998-04-01T00:00:00.000000Z'

    results = p.query(sortby=[{'property': TIME_FIELD, 'order': '-'}])
    assert feature_time(results) == '2012-04-01T00:00:00.000000Z'

    results = p.query(datetime_='../2000-01-01T00:00:00.00Z',
                      sortby=[{'property': TIME_FIELD, 'order': '-'}])
    assert feature_time(results) == '1998-04-01T00:00:00.000000Z'

    results = p.query(datetime_='2000-01-01T00:00:00.00Z/..',
                      sortby=[{'property': TIME_FIELD, 'order': '+'}])
    assert feature_time(results) == '2000-04-01T00:00:00.000000Z'


def test_get(config):
    p = ESRIServiceProvider(config)

    result = p.get(6)
    assert result['id'] == 6
    assert result['properties']['GEOGSTATE'] == 'DC'
