# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2019 Tom Kralidis
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
import os

import pytest
import yaml

from pygeoapi.api import API, check_format


def get_test_file_path(filename):
    """helper function to open test file safely"""

    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


@pytest.fixture()
def headers():
    return {
        'User-Agent': 'some test client'
    }


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml.load(fh)


@pytest.fixture()
def openapi():
    with open(get_test_file_path('pygeoapi-test-openapi.yml')) as fh:
        return yaml.load(fh)


@pytest.fixture()
def api_(config):
    return API(config)


def test_api(config, api_, openapi, headers):
    assert api_.config == config
    assert isinstance(api_.config, dict)

    headers_, code, response = api_.api(headers, {}, openapi)
    assert headers_['Content-Type'] == 'application/openapi+json;version=3.0'
    root = json.loads(response)

    assert isinstance(root, dict)


def test_api_exception(config, api_, headers):
    headers_, code, response = api_.root(headers, {'f': 'foo'})
    assert code == 400


def test_root(config, api_, headers):
    headers_, code, response = api_.root(headers, {})
    root = json.loads(response)

    assert headers_['Content-Type'] == 'application/json'
    assert headers_['X-Powered-By'].startswith('pygeoapi')

    assert isinstance(root, dict)
    assert 'links' in root
    assert len(root['links']) == 4

    headers_, code, response = api_.root(headers, {'f': 'html'})
    assert headers_['Content-Type'] == 'text/html'


def test_api_conformance(config, api_, headers):
    headers_, code, response = api_.api_conformance(headers, {})
    root = json.loads(response)

    assert isinstance(root, dict)
    assert 'conformsTo' in root
    assert len(root['conformsTo']) == 4

    headers_, code, response = api_.api_conformance(headers, {'f': 'foo'})
    assert code == 400

    headers_, code, response = api_.api_conformance(headers, {'f': 'html'})
    assert headers_['Content-Type'] == 'text/html'


def test_describe_collections(config, api_, headers):
    headers_, code, response = api_.describe_collections(headers, {'f': 'foo'})
    assert code == 400

    headers_, code, response = api_.describe_collections(
        headers, {'f': 'html'})
    assert headers_['Content-Type'] == 'text/html'

    headers_, code, response = api_.describe_collections(headers, {})
    collections = json.loads(response)

    assert len(collections) == 1

    headers_, code, response = api_.describe_collections(headers, {}, 'foo')
    collection = json.loads(response)

    assert code == 400

    headers_, code, response = api_.describe_collections(headers, {}, 'obs')
    collection = json.loads(response)

    assert collection['name'] == 'obs'
    assert collection['title'] == 'Observations'
    assert collection['description'] == 'Observations'
    assert len(collection['links']) == 2

    headers_, code, response = api_.describe_collections(
        headers, {'f': 'html'}, 'obs')
    assert headers_['Content-Type'] == 'text/html'


def test_get_features(config, api_, headers):
    headers_, code, response = api_.get_features(headers, {}, 'foo')
    features = json.loads(response)

    assert code == 400

    headers_, code, response = api_.get_features(headers, {'f': 'foo'}, 'obs')
    features = json.loads(response)

    assert code == 400

    headers_, code, response = api_.get_features(
        headers, {'bbox': '1,2,3'}, 'obs')
    features = json.loads(response)

    assert code == 400

    headers_, code, response = api_.get_features(headers, {'f': 'html'}, 'obs')
    assert headers_['Content-Type'] == 'text/html'

    headers_, code, response = api_.get_features(headers, {}, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 5

    headers_, code, response = api_.get_features(
        headers, {'resulttype': 'hits'}, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 0

    headers_, code, response = api_.get_features(
        headers, {'limit': 2}, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 2
    assert features['features'][1]['properties']['stn_id'] == '35'

    headers_, code, response = api_.get_features(
        headers, {'startindex': 2}, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 3
    assert features['features'][1]['properties']['stn_id'] == '2147'

    headers_, code, response = api_.get_features(
        headers, {'sortby': 'stn_id', 'stn_id': '35'}, 'obs')

    assert code == 400

    headers_, code, response = api_.get_features(
        headers, {'sortby': 'stn_id:FOO', 'stn_id': '35', 'value': '89.9'},
        'obs')

    assert code == 400

    headers_, code, response = api_.get_features(
        headers, {'sortby': 'stn_id:A'}, 'obs')

    assert features['features'][1]['properties']['stn_id'] == '2147'

    headers_, code, response = api_.get_features(
        headers, {'f': 'csv'}, 'obs')

    assert headers_['Content-Type'] == 'text/csv; charset=utf-8'


def test_get_feature(config, api_, headers):
    headers_, code, response = api_.get_feature(
        headers, {'f': 'foo'}, 'obs', '371')

    assert code == 400

    headers_, code, response = api_.get_feature(headers, {}, 'foo', '371')

    assert code == 400

    headers_, code, response = api_.get_feature(headers, {}, 'obs', 'notfound')

    assert code == 404

    headers_, code, response = api_.get_feature(
        headers, {'f': 'html'}, 'obs', '371')

    assert headers_['Content-Type'] == 'text/html'

    headers_, code, response = api_.get_feature(headers, {}, 'obs', '371')
    features = json.loads(response)

    assert features['properties']['stn_id'] == '35'


def test_describe_processes(config, api_, headers):
    headers_, code, response = api_.describe_processes(headers, {}, 'foo')
    processes = json.loads(response)

    assert code == 404

    headers_, code, response = api_.describe_processes(headers, {})
    processes = json.loads(response)

    assert len(processes['processes']) == 1

    headers_, code, response = api_.describe_processes(
        headers, {}, 'hello-world')
    process = json.loads(response)

    assert process['id'] == 'hello-world'
    assert process['title'] == 'Hello World process'
    assert process['description'] == 'Hello World process'
    assert len(process['links']) == 1
    assert len(process['inputs']) == 1
    assert len(process['outputs']) == 1
    assert len(process['outputTransmission']) == 1
    assert len(process['jobControlOptions']) == 1


def test_execute_process(config, api_, headers):
    request = {
        'inputs': [{
            'id': 'name',
            'value': 'test'
        }]
    }

    headers_, code, response = api_.execute_process(
        headers, {}, '', 'hello-world')
    response = json.loads(response)
    assert code == 400

    headers_, code, response = api_.execute_process(
        headers, {}, json.dumps(request), 'foo')
    response = json.loads(response)

    assert code == 404

    headers_, code, response = api_.execute_process(
        headers, {}, json.dumps(request), 'hello-world')
    response = json.loads(response)

    assert response['outputs'][0]['value'] == 'test'


def test_check_format(headers):
    args = {
        'f': 'html'
    }

    headers_ = headers.copy()

    assert check_format({}, headers_) is None

    assert check_format(args, headers_) == 'html'

    args['f'] = 'json'
    assert check_format(args, headers_) == 'json'

    headers_['Accept'] = 'text/html'
    assert check_format({}, headers_) == 'html'

    headers_['Accept'] = 'application/json'
    assert check_format({}, headers_) == 'json'

    headers_['accept'] = 'text/html'
    assert check_format({}, headers_) == 'html'
