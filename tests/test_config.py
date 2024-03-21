# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2021 Tom Kralidis
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

import os
from copy import deepcopy
from unittest import mock

from jsonschema.exceptions import ValidationError
import pytest

import pygeoapi.config
from pygeoapi.util import yaml_load

from .util import get_test_file_path


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


def test_config_envvars():
    os.environ['PYGEOAPI_PORT'] = '5001'
    os.environ['PYGEOAPI_TITLE'] = 'my title'

    with open(get_test_file_path('pygeoapi-test-config-envvars.yml')) as fh:
        config = yaml_load(fh)

    assert isinstance(config, dict)
    assert config['server']['bind']['port'] == 5001
    assert config['metadata']['identification']['title'] == \
        'pygeoapi default instance my title'

    os.environ.pop('PYGEOAPI_PORT')

    with pytest.raises(EnvironmentError):
        with open(get_test_file_path('pygeoapi-test-config-envvars.yml')) as fh:  # noqa
            yaml_load(fh)


def test_validate_config(config):
    is_valid = pygeoapi.config.validate_config(config)
    assert is_valid

    with pytest.raises(ValidationError):
        pygeoapi.config.validate_config({'foo': 'bar'})

    # Test API rules
    cfg_copy = deepcopy(config)
    cfg_copy['server']['api_rules'] = {
        'api_version': '1.2.3',
        'strict_slashes': True,
        'url_prefix': 'v{major_version}',
        'version_header': 'API-Version'
    }
    assert pygeoapi.config.validate_config(cfg_copy)

    cfg_copy['server']['api_rules'] = {
        'api_version': 123,
        'url_prefix': 0,
        'strict_slashes': 'bad_value'
    }
    with pytest.raises(ValidationError):
        pygeoapi.config.validate_config(cfg_copy)


def test_get_config_no_env():
    with mock.patch('pygeoapi.config.os') as mock_os:
        mock_os.getenv.return_value = None
        default_conf = pygeoapi.config._get_default_config()
        conf = pygeoapi.config.get_config()
        assert conf == default_conf


def test_get_config_merge_with_default():
    # this test has some complex setup:
    # - create a partial configuration
    # - mock the response of os.getenv, pathlib.Path.open and yaml_load
    #   in order to have pygeoapi think it is loading our partial config
    #   from a file
    # - ensure the partial config is merged with the default config by
    #   asserting the value of the final config
    fake_config = {'server': {'limit': 'fake_limit'}}
    with \
            mock.patch('pygeoapi.config.os') as mock_os, \
            mock.patch('pygeoapi.config.Path') as mock_path, \
            mock.patch('pygeoapi.config.yaml_load') as mock_yaml_load:
        mock_os.getenv.return_value = 'something'
        mock_path_instance = mock.MagicMock()
        mock_path.return_value = mock_path_instance
        mock_open = mock.Mock()
        mock_open.__enter__ = mock.Mock()
        mock_open.__exit__ = mock.Mock()
        mock_path_instance.open.return_value = mock_open
        mock_path_instance.__truediv__.return_value = mock.Mock()
        mock_yaml_load.return_value = fake_config
        conf = pygeoapi.config.get_config(raw=False)
        assert conf['server']['limit'] == fake_config['server']['limit']
