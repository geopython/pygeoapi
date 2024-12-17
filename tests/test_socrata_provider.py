# =================================================================
#
# Authors: Benjamin Webb <bwebb@lincolninst.edu>
# Authors: Bernhard Mallinger <bernhard.mallinger@eox.at>
#
# Copyright (c) 2022 Benjamin Webb
# Copyright (c) 2024 Bernhard Mallinger
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

import copy
from unittest import mock

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
        'data': 'https://example.com/',
        'resource_id': 'emdb-u46w',
        'id_field': 'earthquake_id',
        'time_field': 'datetime',
        'geom_field': 'location'
    }


@pytest.fixture
def mock_socrata(dataset):

    def fake_get(*args, **kwargs):
        if kwargs.get('select') == 'count(*)':
            count = 19 if kwargs.get('where') == 'region = "Nevada"' else 1006
            return [{'count': str(count)}]
        else:
            # get features
            if kwargs.get('order') == 'datetime ASC':
                dt = '2012-09-07T23:00:42.000'
            else:
                dt = '2012-09-14T22:38:01.000'
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-117.6135, 41.1085],
                },
                'properties': {
                    'earthquake_id': '00388610',
                    'datetime': dt,
                    'magnitude': '2.7',
                },
            }
            return {
                'type': 'FeatureCollection',
                'features': [
                    copy.deepcopy(feature)
                    for _ in range(kwargs.get('limit', 10))
                ],
                'crs': {
                    'type': 'name',
                    'properties': {
                        'name': 'urn:ogc:def:crs:OGC:1.3:CRS84',
                    }
                }
            }

    with mock.patch(
        'sodapy.socrata.Socrata.get', new=fake_get,
    ) as mock_get, mock.patch(
        'sodapy.socrata.Socrata.datasets', return_value=[dataset],
    ):
        yield mock_get


@pytest.fixture()
def dataset():
    return {
        'resource': {
            'columns_datatype': ['Point',
                                 'Text',
                                 'Text',
                                 'Text',
                                 'Text',
                                 'Number',
                                 'Text',
                                 'Number',
                                 'Number',
                                 'Calendar date'],
            'columns_description': ['',
                                    '',
                                    '',
                                    '',
                                    '',
                                    'This column was automatically created '
                                    'in order to record in what polygon from '
                                    "the dataset 'Zip Codes' (k83t-ady5) the "
                                    "point in column 'location' is located. "
                                    'This enables the creation of region '
                                    'maps (choropleths) in the visualization '
                                    'canvas and data lens.',
                                    '',
                                    '',
                                    '',
                                    ''],
            'columns_field_name': ['location',
                                   'earthquake_id',
                                   'location_zip',
                                   'location_city',
                                   'location_address',
                                   ':@computed_region_k83t_ady5',
                                   'location_state',
                                   'depth',
                                   'magnitude',
                                   'datetime'],
            'columns_format': [{},
                               {},
                               {},
                               {},
                               {},
                               {},
                               {},
                               {},
                               {},
                               {}],
            'columns_name': ['Location',
                             'Earthquake ID',
                             'Location (zip)',
                             'Location (city)',
                             'Location (address)',
                             'Zip Codes',
                             'Location (state)',
                             'Depth',
                             'Magnitude',
                             'Datetime'],
            'contact_email': None,
            'type': 'dataset',
            'updatedAt': '2019-02-13T23:37:38.000Z'
        }
    }


def test_query(config, mock_socrata):
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


def test_geometry(config, mock_socrata):
    p = SODAServiceProvider(config)

    results = p.query()
    geometry = results['features'][0]['geometry']
    assert geometry['coordinates'] == [-117.6135, 41.1085]

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None


def test_query_properties(config, mock_socrata):
    p = SODAServiceProvider(config)

    results = p.query()
    assert len(results['features'][0]['properties']) == 2

    # Query by property
    results = p.query(properties=[('region', 'Nevada'), ])
    assert results['numberMatched'] == 19


def test_query_sortby_datetime(config, mock_socrata):
    p = SODAServiceProvider(config)

    results = p.query(sortby=[{'property': 'datetime', 'order': '+'}])
    dt = results['features'][0]['properties']['datetime']
    assert dt == '2012-09-07T23:00:42.000'

    results = p.query(sortby=[{'property': 'datetime', 'order': '-'}])
    dt = results['features'][0]['properties']['datetime']
    assert dt == '2012-09-14T22:38:01.000'


def test_get(config, mock_socrata):
    p = SODAServiceProvider(config)

    result = p.get('00388610')
    assert result['id'] == '00388610'
    assert result['properties']['magnitude'] == '2.7'
