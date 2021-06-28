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

import pytest

from pygeoapi.util import yaml_load

from .util import get_test_file_path


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
            config = yaml_load(fh)
