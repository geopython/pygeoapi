# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Tom Kralidis
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

import sys
import logging
import os.path
from urllib.parse import urlsplit
from importlib import reload
from contextlib import contextmanager

from flask.testing import FlaskClient
from starlette.testclient import TestClient as StarletteClient
from werkzeug.test import create_environ
from werkzeug.wrappers import Request
from werkzeug.datastructures import ImmutableMultiDict

from pygeoapi.api import APIRequest

LOGGER = logging.getLogger(__name__)


def get_test_file_path(filename: str) -> str:
    """helper function to open test file safely"""

    if os.path.isfile(filename):
        return filename
    else:
        return f'tests/{filename}'


def mock_request(params: dict = None, data=None, **headers) -> Request:
    """
    Mocks a Request object so the @pre_process decorator can inject it
    as an APIRequest.

    :param params: Optional query parameter dict for the request.
                   Will be set to {} if omitted.
    :param data: Optional data/body to send with the request.
                 Can be text/bytes or a JSON dictionary.
    :param headers: Optional request HTTP headers to set.
    :returns: A Werkzeug Request instance.
    """
    params = params or {}
    # TODO: We are not setting a path in the create_environ() call.
    #       This is fine as long as an API test does not need the URL path.
    if isinstance(data, dict):
        environ = create_environ(base_url='http://localhost:5000/', json=data)
    else:
        environ = create_environ(base_url='http://localhost:5000/', data=data)
    environ.update(headers)
    request = Request(environ)
    request.args = ImmutableMultiDict(params.items())  # noqa
    return request


def mock_api_request(params: dict | None = None, data=None, **headers
                     ) -> APIRequest:
    """
    Mocks an APIRequest

    :param params: Optional query parameter dict for the request.
                   Will be set to {} if omitted.
    :param data: Optional data/body to send with the request.
                 Can be text/bytes or a JSON dictionary.
    :param headers: Optional request HTTP headers to set.
    :returns: APIRequest instance
    """
    return APIRequest.from_flask(
        mock_request(params=params, data=data, **headers),
        # NOTE: could also read supported_locales from test config
        supported_locales=['en-US', 'fr-CA'],
    )


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
