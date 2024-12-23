# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
# Authors: Benjamin Webb <benjamin.miller.webb@gmail.com>
# Authors: Bernhard Mallinger <bernhard.mallinger@eox.at>
#
# Copyright (c) 2024 Tom Kralidis
# Copyright (c) 2023 Benjamin Webb
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

from datetime import datetime
import json
import os

from pathlib import Path
import pytest

from pygeoapi.util import yaml_load
from pygeoapi.admin import (
    Admin, delete_resource, get_config_, get_resource,
    get_resources, patch_config, patch_resource, post_resource,
    put_config, put_resource)

from tests.util import mock_api_request

THISDIR = Path(__file__).resolve().parent


@pytest.fixture()
def admin_config_path(tmp_path, monkeypatch):
    # create a temporary config file because the test will modify it in place
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        (Path(THISDIR) / "pygeoapi-test-config-admin.yml").read_text()
    )

    # get_config() reads the config directly, so we need to patch os.environ
    monkeypatch.setitem(os.environ, "PYGEOAPI_CONFIG", str(config_path))

    return config_path


def reload_api(config_path, monkeypatch, openapi):
    # initialize admin api with current config contents
    with config_path.open() as config_handle:
        admin = Admin(yaml_load(config_handle), openapi)

    # the config paths are set on a class level, so they are set before
    # we can patch os.environ and need to patch them directly
    monkeypatch.setattr(admin, "PYGEOAPI_CONFIG", str(config_path))
    openapi_filename = str(config_path).replace("config.yml", "openapi.yml")
    monkeypatch.setattr(admin, "PYGEOAPI_OPENAPI", openapi_filename)

    return admin


def test_admin(monkeypatch, admin_config_path, openapi):

    admin_api = reload_api(admin_config_path, monkeypatch, openapi)

    req = mock_api_request()
    headers, status_code, content = get_config_(admin_api, req)

    keys = {'logging', 'metadata', 'resources', 'server'}
    assert set(json.loads(content).keys()) == keys

    # PUT configuration
    with get_abspath('admin-put.json').open() as fh:
        put = fh.read()
    req = mock_api_request(data=put)
    headers, status_code, content = put_config(admin_api, req)
    assert status_code == 204

    admin_api = reload_api(admin_config_path, monkeypatch, openapi)

    req = mock_api_request()
    headers, status_code, content = get_config_(admin_api, req)
    assert json.loads(content)['logging']['level'] == 'INFO'

    # PATCH configuration
    with get_abspath('admin-patch.json').open() as fh:
        patch = fh.read()

    req = mock_api_request(data=patch)
    headers, status_code, content = patch_config(admin_api, req)
    assert status_code == 204

    admin_api = reload_api(admin_config_path, monkeypatch, openapi)

    assert json.loads(content)['logging']['level'] == 'DEBUG'


def test_resources_crud(monkeypatch, admin_config_path, openapi):
    admin_api = reload_api(admin_config_path, monkeypatch, openapi)

    empty_req = mock_api_request()
    headers, status_code, content = get_resources(admin_api, empty_req)
    assert len(json.loads(content).keys()) == 1

    # POST a new resource
    with get_abspath('resource-post.json').open() as fh:
        post_data = fh.read()

    req = mock_api_request(data=post_data)
    headers, status_code, content = post_resource(admin_api, req)
    assert status_code == 201
    assert content == 'Location: //data2'

    admin_api = reload_api(admin_config_path, monkeypatch, openapi)

    headers, status_code, content = get_resources(admin_api, empty_req)
    assert len(json.loads(content).keys()) == 2

    d = yaml_load(admin_config_path.read_text())
    temporal_extent_begin = d['resources']['data2']['extents']['temporal']['begin']  # noqa
    assert isinstance(temporal_extent_begin, datetime)

    # PUT an existing resource
    with get_abspath('resource-put.json').open() as fh:
        post_data = fh.read()

    req = mock_api_request(data=post_data)
    headers, status_code, content = put_resource(admin_api, req, 'data2')
    assert status_code == 204

    headers, status_code, content = get_resource(admin_api, empty_req, 'data2')
    assert (
        json.loads(content)['title']['en'] ==
        'Data assets, updated by HTTP PUT'
    )

    # PATCH an existing resource
    with get_abspath('resource-patch.json').open() as fh:
        post_data = fh.read()

    req = mock_api_request(data=post_data)
    headers, status_code, content = patch_resource(admin_api, req, 'data2')
    assert status_code == 204

    headers, status_code, content = get_resource(admin_api, empty_req, 'data2')
    assert (
        json.loads(content)['title']['en'] ==
        'Data assets, updated by HTTP PATCH'
    )

    # DELETE an existing new resource
    headers, status_code, content = \
        delete_resource(admin_api, empty_req, 'data2')
    assert status_code == 204

    headers, status_code, content = get_resources(admin_api, empty_req)
    assert len(json.loads(content).keys()) == 1


def get_abspath(filepath):
    """helper function absolute file access"""

    return Path(THISDIR) / 'data' / 'admin' / filepath
