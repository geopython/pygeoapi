# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Bernhard Mallinger <bernhard.mallinger@eox.at>
#
# Copyright (c) 2025 Tom Kralidis
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
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


import json
from http import HTTPStatus

from pygeoapi.api import describe_collections
from pygeoapi.api.environmental_data_retrieval import get_collection_edr_query

from tests.util import mock_api_request


def test_get_collection_edr_query(config, api_):
    # edr resource
    req = mock_api_request()
    rsp_headers, code, response = describe_collections(api_, req, 'icoads-sst')
    collection = json.loads(response)
    parameter_names = list(collection['parameter_names'].keys())
    parameter_names.sort()
    assert len(parameter_names) == 4
    assert parameter_names == ['AIRT', 'SST', 'UWND', 'VWND']

    # no coords parameter
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.BAD_REQUEST

    # bad query type
    req = mock_api_request({'coords': 'POINT(11 11)'})
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'corridor')
    assert code == HTTPStatus.BAD_REQUEST

    # bad coords parameter
    req = mock_api_request({'coords': 'gah'})
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.BAD_REQUEST

    # bad parameter-name parameter
    req = mock_api_request({
        'coords': 'POINT(11 11)', 'parameter-name': 'bad'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.BAD_REQUEST

    # all parameters
    req = mock_api_request({'coords': 'POINT(11 11)'})
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.OK

    data = json.loads(response)

    axes = list(data['domain']['axes'].keys())
    axes.sort()
    assert len(axes) == 3
    assert axes == ['t', 'x', 'y']

    assert isinstance(data['domain']['axes']['x'], dict)
    assert isinstance(data['domain']['axes']['x']['values'], list)
    assert data['domain']['axes']['x']['values'][0] == 11.0
    assert data['domain']['axes']['y']['values'][0] == 11.0

    parameters = list(data['parameters'].keys())
    parameters.sort()
    assert len(parameters) == 4
    assert parameters == ['AIRT', 'SST', 'UWND', 'VWND']

    # single parameter
    req = mock_api_request({
        'coords': 'POINT(11 11)', 'parameter-name': 'SST'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.OK

    data = json.loads(response)

    assert len(data['parameters'].keys()) == 1
    assert list(data['parameters'].keys())[0] == 'SST'

    # Zulu time zone
    req = mock_api_request({
        'coords': 'POINT(11 11)',
        'datetime': '2000-01-17T00:00:00Z/2000-06-16T23:00:00Z'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.OK

    # bounded date range
    req = mock_api_request({
        'coords': 'POINT(11 11)',
        'datetime': '2000-01-17/2000-06-16'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.OK

    data = json.loads(response)
    time_dict = data['domain']['axes']['t']
    assert isinstance(time_dict, dict)
    assert isinstance(time_dict['values'], list)

    t_values = [
        '2000-02-15T16:29:05.999999999',
        '2000-03-17T02:58:12.000000000',
        '2000-04-16T13:27:18.000000000',
        '2000-05-16T23:56:24.000000000',
        '2000-06-16T10:25:30.000000000'
    ]

    assert sorted(time_dict['values']) == t_values

    # unbounded date range - start
    req = mock_api_request({
        'coords': 'POINT(11 11)',
        'datetime': '../2000-06-16'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.OK

    data = json.loads(response)
    time_dict = data['domain']['axes']['t']
    assert isinstance(time_dict, dict)
    assert isinstance(time_dict['values'], list)

    t_values = [
        '2000-01-16T06:00:00.000000000',
        '2000-02-15T16:29:05.999999999',
        '2000-03-17T02:58:12.000000000',
        '2000-04-16T13:27:18.000000000',
        '2000-05-16T23:56:24.000000000',
        '2000-06-16T10:25:30.000000000'
    ]

    assert sorted(time_dict['values']) == t_values

    # unbounded date range - end
    req = mock_api_request({
        'coords': 'POINT(11 11)',
        'datetime': '2000-06-16/..'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.OK

    data = json.loads(response)
    time_dict = data['domain']['axes']['t']
    assert isinstance(time_dict, dict)
    assert isinstance(time_dict['values'], list)

    t_values = [
        '2000-06-16T10:25:30.000000000',
        '2000-07-16T20:54:36.000000000',
        '2000-08-16T07:23:42.000000000',
        '2000-09-15T17:52:48.000000000',
        '2000-10-16T04:21:54.000000000',
        '2000-11-15T14:51:00.000000000',
        '2000-12-16T01:20:05.999999996'
    ]

    assert sorted(time_dict['values']) == t_values

    # some data
    req = mock_api_request({
        'coords': 'POINT(11 11)', 'datetime': '2000-01-16'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.OK

    # no data
    req = mock_api_request({
        'coords': 'POINT(11 11)', 'datetime': '2000-01-17'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.NO_CONTENT

    # position no coords
    req = mock_api_request({
        'datetime': '2000-01-17'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.BAD_REQUEST

    # cube bbox parameter 4 dimensional
    req = mock_api_request({
        'bbox': '0,0,10,10'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'cube')
    assert code == HTTPStatus.OK

    # cube bad bbox parameter
    req = mock_api_request({
        'bbox': '0,0,10'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'cube')
    assert code == HTTPStatus.BAD_REQUEST

    # cube no bbox parameter
    req = mock_api_request({})
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'cube')
    assert code == HTTPStatus.BAD_REQUEST

    # cube decreasing latitude coords and S3
    req = mock_api_request({
        'bbox': '-100,40,-99,45',
        'parameter-name': 'tmn',
        'datetime': '1994-01-01/1994-12-31',
    })

    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'usgs-prism', None, 'cube')
    assert code == HTTPStatus.OK


def test_get_collection_edr_query_crs(config, api_):
    # Invalid CRS query parameter (not a URI)
    req = mock_api_request({'coords': 'POINT(11 11)', 'crs': '4326'})
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.BAD_REQUEST

    # Valid CRS parameter (default CRS)
    req = mock_api_request({
        'coords': 'POINT(11 11)',
        'crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
    })
    rsp_headers, code, response = get_collection_edr_query(
        api_, req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.OK
    assert 'Content-Crs' in rsp_headers
    expected_crs = '<http://www.opengis.net/def/crs/OGC/1.3/CRS84>'
    assert rsp_headers['Content-Crs'] == expected_crs
