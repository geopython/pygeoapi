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
import gzip
from http import HTTPStatus
from importlib import reload
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from flask.testing import FlaskClient
import pytest

from pygeoapi import __version__
from pygeoapi.api import API

from pygeoapi.formats import FORMAT_TYPES, F_GZIP, F_JSON, F_JSONLD, F_HTML
from pygeoapi.util import yaml_load, get_api_rules, get_base_url
from ..util import get_test_file_path


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def openapi():
    with open(get_test_file_path('pygeoapi-test-openapi.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def api_(config, openapi):
    return API(config, openapi)


@pytest.fixture()
def config_with_rules() -> dict:
    """
    Returns a pygeoapi configuration with default API rules.
    """
    with open(get_test_file_path('pygeoapi-test-config-apirules.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def rules_api(config_with_rules, openapi):
    """
    Returns an API instance with URL prefix and strict slashes policy.
    The API version is extracted from the current version here.
    """
    return API(config_with_rules, openapi)


@contextmanager
def mock_flask(config_file: str = 'pygeoapi-test-config.yml',
               openapi_file: str = 'pygeoapi-test-openapi.yml',
               **kwargs) -> FlaskClient:
    """
    Mocks a Flask client so we can test the API routing with applied API rules.
    Does not follow redirects by default. Set `follow_redirects=True` option
    on individual requests to enable.

    :param config_file: Optional configuration YAML file to use.
                        If not set, the default test configuration is used.

    :param openapi_file: Optional OpenAPI YAML file to use.
    """
    flask_app = None
    env_conf = os.getenv('PYGEOAPI_CONFIG')
    env_openapi = os.getenv('PYGEOAPI_OPENAPI')
    try:
        # Temporarily override environment variable so we can import Flask app
        os.environ['PYGEOAPI_CONFIG'] = get_test_file_path(config_file)
        os.environ['PYGEOAPI_OPENAPI'] = get_test_file_path(openapi_file)

        # Import current pygeoapi Flask app module
        from pygeoapi import flask_app

        # Force a module reload to make sure we really use another config
        reload(flask_app)

        # Set server root path
        url_parts = urlsplit(flask_app.CONFIG['server']['url'])
        app_root = url_parts.path.rstrip('/') or '/'
        flask_app.APP.config['SERVER_NAME'] = url_parts.netloc
        flask_app.APP.config['APPLICATION_ROOT'] = app_root

        # Create and return test client
        client = flask_app.APP.test_client(**kwargs)
        yield client

    finally:
        if env_conf is None and env_openapi is None:
            # Remove env variable again if it was not set initially
            del os.environ['PYGEOAPI_CONFIG']
            del os.environ['PYGEOAPI_OPENAPI']
            # Unload Flask app module
            del sys.modules['pygeoapi.flask_app']
        else:
            # Restore env variable to its original value and reload Flask app
            os.environ['PYGEOAPI_CONFIG'] = env_conf
            os.environ['PYGEOAPI_OPENAPI'] = env_openapi
            if flask_app:
                reload(flask_app)
        del client


def test_get_collection_tiles_data_traversal():
    # a file outside the tile directory with the tile format's extension
    secret = Path('tests/data/tiles/SECRET.pbf')
    secret.write_text('TOPSECRET')
    try:
        with mock_flask('pygeoapi-test-config.yml') as client:
            response = client.get(
                '/collections/naturalearth/lakes/tiles/WorldCRS84Quad/'
                '%2e%2e/SECRET/%2e?f=mvt')
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert b'TOPSECRET' not in response.data
    finally:
        secret.unlink()


def test_apirules_active(config_with_rules, rules_api):
    rules = get_api_rules(config_with_rules)
    base_url = get_base_url(config_with_rules)

    # Test Flask
    flask_prefix = rules.get_url_prefix('flask')
    with mock_flask('pygeoapi-test-config-apirules.yml') as flask_client:
        # Test happy path
        response = flask_client.get(f'{flask_prefix}/conformance')
        assert response.status_code == 200
        assert response.headers['X-API-Version'] == __version__
        assert response.request.url == \
               flask_client.application.url_for('pygeoapi.conformance')
        response = flask_client.get(f'{flask_prefix}/static/img/pygeoapi.png')
        assert response.status_code == 200
        # Test that static resources also work without URL prefix
        response = flask_client.get('/static/img/pygeoapi.png')
        assert response.status_code == 200

        # Test strict slashes
        response = flask_client.get(f'{flask_prefix}/conformance/')
        assert response.status_code == 404
        # For the landing page ONLY, trailing slashes are actually preferred.
        # See https://docs.opengeospatial.org/is/17-069r4/17-069r4.html#_api_landing_page  # noqa
        # Omitting the trailing slash should lead to a redirect.
        response = flask_client.get(f'{flask_prefix}/')
        assert response.status_code == 200
        response = flask_client.get(flask_prefix)
        assert response.status_code in (307, 308)
        # Ensure that the expose-headers are set regardless of
        # whether apirules are active or not
        assert response.headers['Access-Control-Expose-Headers'] == '*'

        # Test links on landing page for correct URLs
        response = flask_client.get(flask_prefix, follow_redirects=True)
        assert response.status_code == 200
        assert response.is_json
        links = response.json['links']
        assert links[0]['rel'] == 'about'
        assert all(
            href.startswith(base_url) for href in (rel['href'] for rel in links[1:])  # noqa
        )


def test_apirules_inactive(config, api_):
    rules = get_api_rules(config)

    # Test Flask
    flask_prefix = rules.get_url_prefix('flask')
    assert flask_prefix == ''
    with mock_flask('pygeoapi-test-config.yml') as flask_client:
        response = flask_client.get('')
        assert response.status_code == 200
        response = flask_client.get('/conformance')
        assert response.status_code == 200
        assert 'X-API-Version' not in response.headers
        assert response.request.url == \
               flask_client.application.url_for('pygeoapi.conformance')
        response = flask_client.get('/static/img/pygeoapi.png')
        assert response.status_code == 200
        # Ensure that the expose-headers are set regardless of
        # whether apirules are active or not
        assert response.headers['Access-Control-Expose-Headers'] == '*'

        # Test trailing slashes
        response = flask_client.get('/')
        assert response.status_code == 200
        response = flask_client.get('/conformance/')
        assert response.status_code == 200
        assert 'X-API-Version' not in response.headers


def test_api_exception(config, api_):
    with mock_flask('pygeoapi-test-config.yml') as flask_client:
        response = flask_client.get('?f=foo')
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.headers['Content-Language'] == 'en-US'

        # When a language is set, the exception should still be English
        response = flask_client.get('?f=foo&lang=fr')
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.headers['Content-Language'] == 'en-US'


def test_gzip(config, api_):
    common = {'Accept_Encoding': F_GZIP}
    headers_gzip_json = {**common, 'Accept': FORMAT_TYPES[F_JSON]}
    headers_gzip_jsonld = {**common, 'Accept': FORMAT_TYPES[F_JSONLD]}
    headers_gzip_html = {**common, 'Accept': FORMAT_TYPES[F_HTML]}
    headers_gzip_gzip = {**common, 'Accept': 'application/gzip'}

    with mock_flask('pygeoapi-test-config.yml') as flask_client:
        response_json = flask_client.get("", headers=headers_gzip_json)
        assert response_json.headers['Content-Type'] == FORMAT_TYPES[F_JSON]

        response_jsonld = flask_client.get("", headers=headers_gzip_jsonld)
        assert response_jsonld.headers['Content-Type'] == \
            FORMAT_TYPES[F_JSONLD]

        response_html = flask_client.get("", headers=headers_gzip_html)
        assert response_html.headers['Content-Type'] == FORMAT_TYPES[F_HTML]

        response_gzip = flask_client.get("", headers=headers_gzip_gzip)
        assert response_gzip.headers['Content-Type'] == FORMAT_TYPES[F_JSON]

    with mock_flask('pygeoapi-test-config-enc16.yml') as flask_client:
        enc_16 = 'utf-16'

        response = flask_client.get("", headers=headers_gzip_json)
        # Validate compressed json response
        assert response.headers['Content-Type'] == \
            f'{FORMAT_TYPES[F_JSON]}; charset={enc_16}'
        assert response.headers['Content-Encoding'] == F_GZIP
        parsed_gzip_json = gzip.decompress(response.data).decode(enc_16)
        assert isinstance(parsed_gzip_json, str)
        parsed_gzip_json = json.loads(parsed_gzip_json)
        assert isinstance(parsed_gzip_json, dict)
        assert parsed_gzip_json == response_json.json

        # Validate compressed jsonld response
        response = flask_client.get("", headers=headers_gzip_jsonld)
        assert response.headers['Content-Type'] == \
            f'{FORMAT_TYPES[F_JSONLD]}; charset={enc_16}'
        assert response.headers['Content-Encoding'] == F_GZIP
        parsed_gzip_jsonld = gzip.decompress(response.data).decode(enc_16)
        assert isinstance(parsed_gzip_jsonld, str)
        parsed_gzip_jsonld = json.loads(parsed_gzip_jsonld)
        assert isinstance(parsed_gzip_jsonld, dict)
        assert parsed_gzip_jsonld == response_jsonld.json

        # Validate compressed html response
        response = flask_client.get("", headers=headers_gzip_html)
        assert response.headers['Content-Type'] == \
            f'{FORMAT_TYPES[F_HTML]}; charset={enc_16}'
        assert response.headers['Content-Encoding'] == F_GZIP
        parsed_gzip_html = gzip.decompress(response.data).decode(enc_16)
        assert isinstance(parsed_gzip_html, str)
        assert parsed_gzip_html == response_html.text

        # Validate compressed gzip response
        response = flask_client.get("", headers=headers_gzip_gzip)
        assert response.headers['Content-Type'] == \
            f'{FORMAT_TYPES[F_GZIP]}; charset={enc_16}'
        assert response.headers['Content-Encoding'] == F_GZIP
        parsed_gzip_gzip = gzip.decompress(response.data).decode(enc_16)
        assert isinstance(parsed_gzip_gzip, str)
        parsed_gzip_gzip = json.loads(parsed_gzip_gzip)
        assert isinstance(parsed_gzip_gzip, dict)
