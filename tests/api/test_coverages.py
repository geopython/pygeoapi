# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#
# Copyright (c) 2024 Tom Kralidis
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

import pytest

from pygeoapi.api.coverages import get_collection_coverage
from pygeoapi.api import describe_collections, get_collection_schema
from pygeoapi.util import yaml_load

from tests.util import get_test_file_path, mock_api_request


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


def test_describe_collections(config, api_):

    req = mock_api_request()
    rsp_headers, code, response = describe_collections(
        api_, req, 'gdps-temperature')

    collection = json.loads(response)

    assert collection['id'] == 'gdps-temperature'
    assert len(collection['links']) == 10
    assert collection['extent']['spatial']['grid'][0]['cellsCount'] == 2400
    assert collection['extent']['spatial']['grid'][0]['resolution'] == 0.15000000000000002  # noqa
    assert collection['extent']['spatial']['grid'][1]['cellsCount'] == 1201
    assert collection['extent']['spatial']['grid'][1]['resolution'] == 0.15


def test_get_collection_schema(config, api_):
    req = mock_api_request({'f': 'html'})
    rsp_headers, code, response = get_collection_schema(
        api_, req, 'gdps-temperature')

    assert rsp_headers['Content-Type'] == 'text/html'

    req = mock_api_request({'f': 'json'})
    rsp_headers, code, response = get_collection_schema(
        api_, req, 'gdps-temperature')

    assert rsp_headers['Content-Type'] == 'application/schema+json'
    schema = json.loads(response)

    assert 'properties' in schema
    assert len(schema['properties']) == 1

    req = mock_api_request({'f': 'json'})
    rsp_headers, code, response = get_collection_schema(
        api_, req, 'gdps-temperature')
    assert rsp_headers['Content-Type'] == 'application/schema+json'
    schema = json.loads(response)

    assert 'properties' in schema
    assert len(schema['properties']) == 1
    assert schema['properties']['1']['type'] == 'number'
    assert schema['properties']['1']['title'] == 'Temperature [C]'


def test_get_collection_coverage(config, api_):
    req = mock_api_request()
    rsp_headers, code, response = get_collection_coverage(
        api_, req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'properties': '12'})
    rsp_headers, code, response = get_collection_coverage(
        api_, req, 'gdps-temperature')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'subset': 'bad_axis(10:20)'})
    rsp_headers, code, response = get_collection_coverage(
        api_, req, 'gdps-temperature')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'f': 'blah'})
    rsp_headers, code, response = get_collection_coverage(
        api_, req, 'gdps-temperature')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'f': 'html'})
    rsp_headers, code, response = get_collection_coverage(
        api_, req, 'gdps-temperature')

    assert code == HTTPStatus.BAD_REQUEST
    assert rsp_headers['Content-Type'] == 'text/html'

    req = mock_api_request(HTTP_ACCEPT='text/html')
    rsp_headers, code, response = get_collection_coverage(
        api_, req, 'gdps-temperature')

    # NOTE: This test used to assert the code to be 200 OK,
    #       but it requested HTML, which is not available,
    #       so it should be 400 Bad Request
    assert code == HTTPStatus.BAD_REQUEST
    assert rsp_headers['Content-Type'] == 'text/html'

    req = mock_api_request({'subset': 'Lat(5:10),Long(5:10)'})
    rsp_headers, code, response = get_collection_coverage(
        api_, req, 'gdps-temperature')

    assert code == HTTPStatus.OK
    content = json.loads(response)

    assert content['domain']['axes']['x']['num'] == 35
    assert content['domain']['axes']['y']['num'] == 35
    assert 'TMP' in content['parameters']
    assert 'TMP' in content['ranges']
    assert content['ranges']['TMP']['axisNames'] == ['y', 'x']

    req = mock_api_request({'bbox': '-79,45,-75,49'})
    rsp_headers, code, response = get_collection_coverage(
        api_, req, 'gdps-temperature')

    assert code == HTTPStatus.OK
    content = json.loads(response)

    assert content['domain']['axes']['x']['start'] == -79.0
    assert content['domain']['axes']['x']['stop'] == -75.0
    assert content['domain']['axes']['y']['start'] == 49.0
    assert content['domain']['axes']['y']['stop'] == 45.0

    req = mock_api_request({
        'subset': 'Lat(5:10),Long(5:10)',
        'f': 'GRIB'
    })
    rsp_headers, code, response = get_collection_coverage(
        api_, req, 'gdps-temperature')

    assert code == HTTPStatus.OK
    assert isinstance(response, bytes)

    req = mock_api_request(HTTP_ACCEPT='application/x-netcdf')
    rsp_headers, code, response = get_collection_coverage(
        api_, req, 'cmip5')

    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == 'application/x-netcdf'
