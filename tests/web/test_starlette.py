# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2026 Tom Kralidis
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

from contextlib import contextmanager
from http import HTTPStatus
from importlib import reload
import os
from pathlib import Path
import sys

import pytest

from starlette.testclient import TestClient as StarletteClient

from pygeoapi import __version__
from pygeoapi.api import API
from pygeoapi.util import get_api_rules, get_base_url, yaml_load

from ..util import get_test_file_path


@pytest.fixture()
def config_with_rules() -> dict:
    """ Returns a pygeoapi configuration with default API rules. """
    with open(get_test_file_path('pygeoapi-test-config-apirules.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def rules_api(config_with_rules, openapi):
    """ Returns an API instance with URL prefix and strict slashes policy.
    The API version is extracted from the current version here.
    """
    return API(config_with_rules, openapi)


@contextmanager
def mock_starlette(config_file: str = 'pygeoapi-test-config.yml',
                   openapi_file: str = 'pygeoapi-test-openapi.yml',
                   **kwargs) -> StarletteClient:
    """
    Mocks a Starlette client so we can test the API routing with applied
    API rules.
    Does not follow redirects by default. Set `follow_redirects=True` option
    on individual requests to enable.

    :param config_file: Optional configuration YAML file to use.
                        If not set, the default test configuration is used.

    :param openapi_file: Optional OpenAPI YAML file to use.
    """

    starlette_app = None
    env_conf = os.getenv('PYGEOAPI_CONFIG')
    env_openapi = os.getenv('PYGEOAPI_OPENAPI')
    try:
        # Temporarily override environment variable to import Starlette app
        os.environ['PYGEOAPI_CONFIG'] = get_test_file_path(config_file)
        os.environ['PYGEOAPI_OPENAPI'] = get_test_file_path(openapi_file)

        # Import current pygeoapi Starlette app module
        from pygeoapi import starlette_app

        # Force a module reload to make sure we really use another config
        reload(starlette_app)

        # Create and return test client
        # Note: setting the 'root_path' does NOT really work and
        # does not have the same effect as Flask's APPLICATION_ROOT
        client = StarletteClient(starlette_app.APP, **kwargs)
        # Override follow_redirects so behavior is the same as Flask mock
        client.follow_redirects = False
        yield client

    finally:
        if env_conf is None and env_openapi is None:
            # Remove env variable again if it was not set initially
            del os.environ['PYGEOAPI_CONFIG']
            del os.environ['PYGEOAPI_OPENAPI']
            # Unload Starlette app module
            del sys.modules['pygeoapi.starlette_app']
        else:
            # Restore env variable to original value and reload Starlette app
            os.environ['PYGEOAPI_CONFIG'] = env_conf
            os.environ['PYGEOAPI_OPENAPI'] = env_openapi
            if starlette_app:
                reload(starlette_app)
        del client


def test_get_collection_tiles_data_traversal():
    # a file outside the tile directory with the tile format's extension
    secret = Path('tests/data/tiles/SECRET.pbf')
    secret.write_text('TOPSECRET')
    try:
        with mock_starlette('pygeoapi-test-config.yml') as client:
            response = client.get(
                '/collections/naturalearth/lakes/tiles/WorldCRS84Quad/'
                '%2e%2e/SECRET/%2e?f=mvt')
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert b'TOPSECRET' not in response.content
    finally:
        secret.unlink()


def test_apirules_active(config_with_rules, rules_api):
    rules = get_api_rules(config_with_rules)
    base_url = get_base_url(config_with_rules)

    starlette_prefix = rules.get_url_prefix('starlette')
    with mock_starlette('pygeoapi-test-config-apirules.yml') as starlette_client:  # noqa
        # Test happy path
        response = starlette_client.get(f'{starlette_prefix}/conformance')
        assert response.status_code == 200
        assert response.headers['X-API-Version'] == __version__
        response = starlette_client.get(f'{starlette_prefix}/static/img/pygeoapi.png')  # noqa
        assert response.status_code == 200
        # Test that static resources also work without URL prefix
        response = starlette_client.get('/static/img/pygeoapi.png')
        assert response.status_code == 200

        # Test strict slashes
        response = starlette_client.get(f'{starlette_prefix}/conformance/')
        assert response.status_code == 404
        # For the landing page ONLY, trailing slashes are actually preferred.
        # See https://docs.opengeospatial.org/is/17-069r4/17-069r4.html#_api_landing_page  # noqa
        # Omitting the trailing slash should lead to a redirect.
        response = starlette_client.get(f'{starlette_prefix}/')
        assert response.status_code == 200
        response = starlette_client.get(starlette_prefix)
        assert response.status_code in (307, 308)

        # Test links on landing page for correct URLs
        response = starlette_client.get(starlette_prefix, follow_redirects=True)  # noqa
        assert response.status_code == 200
        links = response.json()['links']
        assert links[0]['rel'] == 'about'
        assert all(
            href.startswith(base_url) for href in (rel['href'] for rel in links[1:])  # noqa
        )


def test_apirules_inactive(config, api_):
    rules = get_api_rules(config)

    starlette_prefix = rules.get_url_prefix('starlette')
    assert starlette_prefix == ''
    with mock_starlette('pygeoapi-test-config.yml') as starlette_client:
        response = starlette_client.get('')
        assert response.status_code == 200
        response = starlette_client.get('/conformance')
        assert response.status_code == 200
        assert 'X-API-Version' not in response.headers
        assert str(response.url) == f"{starlette_client.base_url}/conformance"
        response = starlette_client.get('/static/img/pygeoapi.png')
        assert response.status_code == 200

        # Test trailing slashes
        response = starlette_client.get('/')
        assert response.status_code == 200
        response = starlette_client.get('/conformance/', follow_redirects=True)
        assert response.status_code == 200
        assert 'X-API-Version' not in response.headers


def test_api_exception(config, api_):
    with mock_starlette('pygeoapi-test-config.yml') as starlette_client:
        response = starlette_client.get('?f=foo')

        with starlette_client.stream('GET', '?f=foo') as response:
            print("STATUS:", response.status_code)
            print("HEADERS:", dict(response.headers))
            print("RAW BODY:", response.read())

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.headers['Content-Language'] == 'en-US'

    with mock_starlette('pygeoapi-test-config.yml') as starlette_client:
        # When a language is set, the exception should still be English
        response = starlette_client.get('?f=foo&lang=fr')
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.headers['Content-Language'] == 'en-US'
