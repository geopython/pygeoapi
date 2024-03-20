# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Bernhard Mallinger <bernhard.mallinger@eox.at>
#
# Copyright (c) 2024 Tom Kralidis
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
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


import json
from http import HTTPStatus

from pygeoapi.api import FORMAT_TYPES, F_HTML
from pygeoapi.api.tiles import (
    get_collection_tiles, tilematrixset, tilematrixsets,
)
from pygeoapi.models.provider.base import TileMatrixSetEnum

from tests.util import mock_api_request


def test_get_collection_tiles(config, api_):
    req = mock_api_request()
    rsp_headers, code, response = get_collection_tiles(api_, req, 'obs')
    assert code == HTTPStatus.BAD_REQUEST

    rsp_headers, code, response = get_collection_tiles(
        api_, req, 'naturalearth/lakes')
    assert code == HTTPStatus.OK

    # Language settings should be ignored (return system default)
    req = mock_api_request({'lang': 'fr'})
    rsp_headers, code, response = get_collection_tiles(
        api_, req, 'naturalearth/lakes')
    assert rsp_headers['Content-Language'] == 'en-US'
    content = json.loads(response)
    assert len(content['links']) > 0
    assert len(content['tilesets']) > 0


def test_tilematrixsets(config, api_):
    req = mock_api_request()
    rsp_headers, code, response = tilematrixsets(api_, req)
    root = json.loads(response)

    assert isinstance(root, dict)
    assert 'tileMatrixSets' in root
    assert len(root['tileMatrixSets']) == 2
    assert 'http://www.opengis.net/def/tilematrixset/OGC/1.0/WorldCRS84Quad' \
           in root['tileMatrixSets'][0]['uri']
    assert 'http://www.opengis.net/def/tilematrixset/OGC/1.0/WebMercatorQuad' \
           in root['tileMatrixSets'][1]['uri']

    req = mock_api_request({'f': 'html'})
    rsp_headers, code, response = tilematrixsets(api_, req)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    # No language requested: should be set to default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'


def test_tilematrixset(config, api_):
    req = mock_api_request()

    enums = [e.value for e in TileMatrixSetEnum]
    enum = None

    for e in enums:
        enum = e.tileMatrixSet
        rsp_headers, code, response = tilematrixset(api_, req, enum)
        root = json.loads(response)

        assert isinstance(root, dict)
        assert 'id' in root
        assert root['id'] == enum
        assert 'tileMatrices' in root
        assert len(root['tileMatrices']) == 30

    rsp_headers, code, response = tilematrixset(api_, req, 'foo')
    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'f': 'html'})
    rsp_headers, code, response = tilematrixset(api_, req, enum)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    # No language requested: should be set to default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'
