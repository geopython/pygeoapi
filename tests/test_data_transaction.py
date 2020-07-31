import json
import os
import logging

import pytest

from werkzeug.test import create_environ
from werkzeug.wrappers import Request
from pygeoapi.api import API
from pygeoapi.util import yaml_load

LOGGER = logging.getLogger(__name__)


def get_test_file_path(filename):
    """helper function to open test file safely"""

    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


def make_req_headers(**kwargs):
    environ = create_environ('/collections/obs/items',
                             'http://localhost:5000/')
    environ.update(kwargs)
    request = Request(environ)
    return request.headers


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def openapi():
    with open(get_test_file_path('pygeoapi-test-openapi.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def api_(config):
    return API(config)


def test_create_collection_item(config, api_):
    post_payload = {
        "type": "Feature",
        "id": 99,
        "geometry": {
            "type": "Point",
            "coordinates": [
                -75.0,
                45.0
            ]
        },
        "properties": {
            "value": 100
        }
    }

    headers, status_code, content = \
        api_.create_collection_item(post_payload, 'obs')

    assert status_code == 201
    assert headers['Content-Type'] == 'application/json'
    assert headers['Location'] == \
        '/collections/obs/items/99'

    get_res = api_.get_collection_item(make_req_headers(),
                                       {'f': 'json'}, 'obs', '99')
    assert json.loads(get_res[2])['properties']['value'] == '100'


def test_create_existing_item_raise_exception(config, api_):
    post_payload = {
        "type": "Feature",
        "id": 377,
        "geometry": {
            "type": "Point",
            "coordinates": [
                -75.0,
                45.0
            ]
        },
        "properties": {
            "value": 100
        }
    }
    headers, status_code, content = \
        api_.create_collection_item(post_payload, 'obs')
    assert status_code == 400


def test_create_invalid_schema_raise_exception(config, api_):
    post_payload = {
        "type": "Feature",
        "id": 377,
        "geometry": {
            "type": "Point",
            "coordinates": [
                -75.0,
                45.0
            ]
        },
        "properties": {
            "value": 100,
            "i_am_an_alien": 1

        }
    }
    headers, status_code, content = \
        api_.create_collection_item(post_payload, 'obs')
    assert status_code == 400


def test_replace_collection_item(config, api_):
    put_payload = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [
                -75.0,
                45.0
            ]
        },
        "properties": {
            "value": 120,
            "datetime": "2003-10-30T07:37:29Z"
        }
    }
    headers, status_code, content = \
        api_.replace_collection_item(put_payload, 'obs', '99')
    assert status_code == 200
    get_res = api_.get_collection_item(make_req_headers(),
                                       {'f': 'json'}, 'obs', '99')
    assert json.loads(get_res[2])['properties']['value'] == '120'


def test_replace_non_existing_item_raise_exception(config, api_):
    put_payload = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [
                -75.0,
                45.0
            ]
        },
        "properties": {
            "value": 120,
            "datetime": "2003-10-30T07:37:29Z"
        }
    }
    headers, status_code, content = \
        api_.replace_collection_item(put_payload, 'obs', 'i_dont_exist')
    assert status_code == 404


def test_replace_invalid_schema_raise_exception(config, api_):
    put_payload = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [
                -75.0,
                45.0
            ]
        },
        "properties": {
            "value": 120,
            "datetime": "2003-10-30T07:37:29Z",
            "i_am_an_alien": 1
        }
    }
    headers, status_code, content = \
        api_.replace_collection_item(put_payload, 'obs', '99')
    assert status_code == 400


def test_update_collection_item(config, api_):
    patch_payload = {
        "add": [{"name": "idx", "value": 1}],
        "modify": [{"name": "value", "value": 150}],
        "remove": ["datetime"]
    }

    headers, status_code, content = \
        api_.update_collection_item(patch_payload, 'obs', '99')

    assert status_code == 200
    assert headers['Content-Type'] == 'application/geo+json'
    assert headers['Location'] == \
        '/collections/obs/items/99'
    assert 'idx' in content['properties']
    assert content['properties']['idx'] == '1'
    assert content['properties']["value"] == '150'
    assert 'datetime' not in content['properties']

    get_res = api_.get_collection_item(make_req_headers(),
                                       {'f': 'json'}, 'obs', '99')
    properties = json.loads(get_res[2])['properties']
    assert 'idx' in properties
    assert properties['idx'] == '1'
    assert properties["value"] == '150'
    assert 'datetime' not in content['properties']


def test_update_non_existing_item_raise_exception(config, api_):
    patch_payload = {
        "add": [{"name": "idy", "value": 1}],
        "modify": [],
        "remove": []
    }
    headers, status_code, content = \
        api_.update_collection_item(patch_payload, 'obs', 'i_dont_exist')
    assert status_code == 404


def test_update_invalid_schema_raise_exception(config, api_):
    patch_payload = {
        "add": [],
        "modify": [],
        "remove": ["i_dont_exist"]
    }
    headers, status_code, content = \
        api_.update_collection_item(patch_payload, 'obs', '99')
    assert status_code == 400


def test_remove_collection_item(config, api_):

    headers, status_code, content = \
        api_.remove_collection_item('obs', '99')
    assert status_code == 200
    get_res = api_.get_collection_item(make_req_headers(),
                                       {'f': 'json'}, 'obs', '99')
    assert get_res[1] == 404


def test_remove_non_existing_item_raise_exception(config, api_):

    headers, status_code, content = \
        api_.remove_collection_item('obs', 'i_dont_exist')
    assert status_code == 404
