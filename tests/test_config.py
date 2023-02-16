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

from jsonschema.exceptions import ValidationError
import pytest

from pygeoapi.config import validate_config
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
    is_valid = validate_config(config)
    assert is_valid

    with pytest.raises(ValidationError):
        validate_config({'foo': 'bar'})

    # Test API rules
    cfg_copy = deepcopy(config)
    cfg_copy['server']['api_rules'] = {
        'api_version': '1.2.3',
        'strict_slashes': True,
        'url_prefix': 'v{major_version}',
        'version_header': 'API-Version'
    }
    assert validate_config(cfg_copy)

    cfg_copy['server']['api_rules'] = {
        'api_version': 123,
        'url_prefix': 0,
        'strict_slashes': 'bad_value'
    }
    with pytest.raises(ValidationError):
        validate_config(cfg_copy)
