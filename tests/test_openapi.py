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

import pytest

from jsonschema.exceptions import ValidationError

from pygeoapi.openapi import (get_oas, get_ogc_schemas_location,
                              validate_openapi_document)
from pygeoapi.util import yaml_load

from .util import get_test_file_path


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def config_hidden_resources():
    filename = 'pygeoapi-test-config-hidden-resources.yml'
    with open(get_test_file_path(filename)) as fh:
        return yaml_load(fh)


@pytest.fixture()
def openapi():
    with open(get_test_file_path('pygeoapi-test-openapi.yml')) as fh:
        return yaml_load(fh)


def test_str2bool():

    default = {
        'url': 'http://localhost:5000'
    }

    osl = get_ogc_schemas_location(default)
    assert osl == 'https://schemas.opengis.net'

    default['ogc_schemas_location'] = 'http://example.org/schemas'
    osl = get_ogc_schemas_location(default)
    assert osl == 'http://example.org/schemas'

    default['ogc_schemas_location'] = '/opt/schemas.opengis.net'
    osl = get_ogc_schemas_location(default)


def test_get_oas(config, openapi):
    openapi_doc = get_oas(config)

    assert isinstance(openapi_doc, dict)

    is_valid = validate_openapi_document(openapi_doc)

    assert is_valid


def test_validate_openapi_document(openapi):
    is_valid = validate_openapi_document(openapi)
    assert is_valid

    with pytest.raises(ValidationError):
        is_valid = validate_openapi_document({'foo': 'bar'})


def test_hidden_resources(config_hidden_resources):
    openapi_doc = get_oas(config_hidden_resources)

    assert '/collections/obs' not in openapi_doc['paths']
    assert '/collections/obs/items' not in openapi_doc['paths']
