# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2025 Tom Kralidis
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

from click.testing import CliRunner
import json
from jsonschema.exceptions import ValidationError
import pytest
import os
import yaml

from pygeoapi.openapi import (get_oas, get_ogc_schemas_location,
                              validate_openapi_document, generate, validate)
from pygeoapi.util import yaml_load

from ..util import get_test_file_path

os.environ['PYGEOAPI_URL'] = 'http://localhost:5000'


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def config_admin_empty_resources():
    with open(
        get_test_file_path('pygeoapi-test-config-admin-empty-resources.yml')
    ) as fh:
        return yaml_load(fh)


@pytest.fixture()
def config_hidden_resources():
    filename = 'pygeoapi-test-config-hidden-resources.yml'
    with open(get_test_file_path(filename)) as fh:
        return yaml_load(fh)


@pytest.fixture()
def config_i18n():
    filename = 'pygeoapi-test-config-i18n.yml'
    with open(get_test_file_path(filename)) as fh:
        return yaml_load(fh)


@pytest.fixture()
def openapi():
    with open(get_test_file_path('pygeoapi-test-openapi.yml')) as fh:
        return yaml_load(fh)


def test_get_ogc_schemas_location():

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


def test_get_oas(config):
    openapi_doc = get_oas(config)

    assert isinstance(openapi_doc, dict)

    is_valid = validate_openapi_document(openapi_doc)

    assert is_valid


def test_get_oas_ogc_service_contact(config):

    ogc_service_contact = {
        'addresses': [{
            'administrativeArea': 'Country',
            'city': 'City',
            'deliveryPoint': ['Mailing Address']
        }],
        'contactInstructions': 'During hours of service.  Off on weekends.',
        'emails': [{
            'value': 'you@example.org'
        }],
        'hoursOfService': 'pointOfContact',
        'links': [{
            'href': 'Contact URL',
            'type': 'text/html'
        }],
        'name': 'Lastname, Firstname',
        'phones': [{
            'type': 'main',
            'value': '+xx-xxx-xxx-xxxx'
        }, {
            'type': 'fax',
            'value': '+xx-xxx-xxx-xxxx'
        }],
        'position': 'Position Title'
    }

    openapi_doc = get_oas(config)

    assert isinstance(openapi_doc, dict)

    assert openapi_doc['info']['contact']['x-ogc-serviceContact'] == ogc_service_contact  # noqa


def test_validate_openapi_document(openapi):
    is_valid = validate_openapi_document(openapi)
    assert is_valid

    with pytest.raises(ValidationError):
        is_valid = validate_openapi_document({'foo': 'bar'})


def test_hidden_resources(config_hidden_resources):
    openapi_doc = get_oas(config_hidden_resources)

    assert '/collections/obs' not in openapi_doc['paths']
    assert '/collections/obs/items' not in openapi_doc['paths']


def test_i18n(config_i18n):
    openapi_doc = get_oas(config_i18n)

    assert isinstance(openapi_doc['info']['contact']['name'], str)
    assert openapi_doc['info']['contact']['name'] == 'Organization Name'


def test_admin_empty_resources(config_admin_empty_resources):
    openapi_doc = get_oas(config_admin_empty_resources)
    assert '/admin/config' in openapi_doc['paths']


def test_generate_openapi_document():
    runner = CliRunner()
    file_path = get_test_file_path('pygeoapi-test-config.yml')
    file_success = b'Generating tests/pygeoapi-test-openapi.yml'

    # Basic functionality
    result = runner.invoke(generate, ['-c', file_path])
    assert result.stderr_bytes == b''
    assert file_success in result.stdout_bytes
    assert b'Done' in result.stdout_bytes

    os.environ['PYGEOAPI_CONFIG'] = file_path
    result2 = runner.invoke(generate)
    assert result2.stderr_bytes == b''
    assert file_success in result2.stdout_bytes
    assert b'Done' in result2.stdout_bytes

    assert result.stdout_bytes == result2.stdout_bytes

    # Format is ignored when writing to file
    result = runner.invoke(generate, ['-c', file_path, '-f', 'json'])

    assert result.stderr_bytes == b''
    assert file_success in result.stdout_bytes
    assert b'Done' in result.stdout_bytes


def test_validate():
    # Run and validate openapi document from CLI
    runner = CliRunner()
    runner.invoke(generate)
    result = runner.invoke(validate)
    assert result.stderr_bytes == b''
    assert result.stdout_bytes.endswith(b'Valid OpenAPI document\n')


def test_generate_openapi_stdout():
    runner = CliRunner()
    file_path = get_test_file_path('pygeoapi-test-config.yml')
    # Ensure openapi var not in env
    openapi_ = os.environ.pop('PYGEOAPI_OPENAPI')

    # Format is recognized JSON
    result = runner.invoke(generate, ['-c', file_path, '-f', 'json'])
    assert result.stderr_bytes == b''
    assert result.stdout_bytes.startswith(b'{')
    assert result.stdout_bytes.endswith(b'}\n')
    result2 = json.loads(result.stdout_bytes[:])

    # Format is recognized YAML
    result = runner.invoke(generate, ['-c', file_path, '-f', 'yaml'])
    assert result.stderr_bytes == b''
    assert result.stdout_bytes.startswith(b'components')
    result3 = yaml.safe_load(result.stdout_bytes[:])

    # Ensure parity between JSON to YAML
    assert result2 == result3

    # Add openapi var back to environment
    os.environ['PYGEOAPI_OPENAPI'] = openapi_
