# =================================================================
#
# Authors: Bernhard Mallinger <bernhard.mallinger@eox.at>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2024 Bernhard Mallinger
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


from http import HTTPStatus
import json
import os
import sys
from unittest import mock
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import django
from django.test import Client
import pytest

from pygeoapi.api import API, APIRequest
from pygeoapi.api.stac import search
from pygeoapi.util import yaml_load

from ..util import get_test_file_path


@pytest.fixture
@mock.patch.dict(os.environ, {
    "DJANGO_SETTINGS_MODULE": "django_.settings",
    "PYGEOAPI_CONFIG": get_test_file_path('pygeoapi-test-config.yml'),
    "PYGEOAPI_OPENAPI": get_test_file_path('pygeoapi-test-openapi.yml')
})
@mock.patch.object(sys, "path", sys.path + ["./pygeoapi"])
def django_():
    django.setup()
    return django


def test_django_landing_page_loads(django_):
    response = Client(SERVER_NAME="localhost").get("/")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["title"] == "pygeoapi default instance"


def test_django_edr_without_instance_id(django_):
    edr_position_query = ("/collections/icoads-sst/position?coords="
                          "POINT(12.779895 55.783523)&f=json")
    response = Client(SERVER_NAME="localhost").get(edr_position_query)

    assert response.status_code == HTTPStatus.OK
    # Validate CoverageJSON is returned
    response_json = response.json()
    assert response_json["type"] == "Coverage"
    assert response_json["domain"]["domainType"] == "PointSeries"


@pytest.fixture
def stac_api(openapi):
    with open(get_test_file_path('pygeoapi-test-stac-api-config.yml')) as fh:
        return API(yaml_load(fh), openapi)


@pytest.mark.parametrize('post_data,limit', [(None, 3), ({'limit': 2}, 2)])
def test_search_django_query_params(stac_api, post_data, limit, monkeypatch):
    """Django query values stay scalar in POST overrides and paging links."""
    django_http = pytest.importorskip('django.http')
    monkeypatch.setattr(django_http.request, 'settings', SimpleNamespace(
        DATA_UPLOAD_MAX_NUMBER_FIELDS=1000))
    params = django_http.QueryDict(
        'limit=1&limit=3&offset=2&bbox=-180,-90,180,90', encoding='utf-8')
    request = SimpleNamespace(
        GET=params, headers={}, path_info='/stac-api/search',
        body=json.dumps(post_data).encode() if post_data else b'')
    req = APIRequest.from_django(request, stac_api.locales)

    _, code, response = search(stac_api, req)
    assert code == 200
    response = json.loads(response)
    assert response['numberMatched'] == 10
    assert response['numberReturned'] == limit
    links = {link['rel']: link['href'] for link in response['links']}
    for rel, offset in [('prev', None), ('next', [str(2 + limit)])]:
        query = parse_qs(urlsplit(links[rel]).query)
        assert query['limit'] == [str(limit)]
        assert query['bbox'] == ['-180,-90,180,90']
        assert query.get('offset') == offset
    assert params.getlist('limit') == ['1', '3']
    assert params['offset'] == '2'
