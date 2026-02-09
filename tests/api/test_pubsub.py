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

from copy import deepcopy
import json

import pytest

from pygeoapi.api import API, landing_page
from pygeoapi.util import yaml_load

from tests.util import get_test_file_path, mock_api_request


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config-pubsub.yml')) as fh:
        return yaml_load(fh)


def test_landing_page(config, openapi, asyncapi):
    api_ = API(config, openapi, asyncapi)

    broker_link = None

    req = mock_api_request()
    rsp_headers, code, response = landing_page(api_, req)

    content = json.loads(response)

    assert len(content['links']) == 15

    for link in content['links']:
        if link.get('rel') == 'hub':
            broker_link = link

    assert broker_link is not None
    assert broker_link['href'] == 'mqtt://localhost:1883'
    assert broker_link['channel'] == 'my/channel'

    config2 = deepcopy(config)
    config2['pubsub']['broker']['hidden'] = True

    api_ = API(config2, openapi)

    broker_link = None

    req = mock_api_request()
    rsp_headers, code, response = landing_page(api_, req)

    content = json.loads(response)

    assert len(content['links']) == 12

    for link in content['links']:
        if link.get('rel') == 'hub':
            broker_link = link

    assert broker_link is None

    config2 = deepcopy(config)
    config2['pubsub']['broker'].pop('channel', None)

    api_ = API(config2, openapi, asyncapi)

    broker_link = None

    req = mock_api_request()
    rsp_headers, code, response = landing_page(api_, req)

    content = json.loads(response)

    assert len(content['links']) == 15

    for link in content['links']:
        if link.get('rel') == 'hub':
            broker_link = link

    assert broker_link is not None
    assert 'channel' not in broker_link
