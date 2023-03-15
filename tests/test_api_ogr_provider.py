# =================================================================
#
# Authors: Just van den Broecke <justb4@gmail.com>
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2019 Just van den Broecke
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

import json
import logging
import pytest
from pygeoapi.api import (API)
from pygeoapi.util import yaml_load

from .util import get_test_file_path, mock_request

LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config-ogr.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def api_(config):
    return API(config)


def test_get_collection_items_bbox_crs(config, api_):
    CRS_BBOX_DICT = {
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84': '5.71484, 52.12122, 5.71486, 52.12123', # noqa
        'http://www.opengis.net/def/crs/EPSG/0/4326': '52.12122, 5.71484, 52.12123, 5.71486', # noqa
        'http://www.opengis.net/def/crs/EPSG/0/28992': '177430,	459268, 177440,	459278' # noqa
    }

    COLLECTIONS = ['dutch_addresses_4326', 'dutch_addresses_28992']
    for coll in COLLECTIONS:
        # bbox-crs full extent
        req = mock_request({'bbox': '5.670670, 52.042700, 5.829110, 52.123700', 'bbox-crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'}) # noqa
        rsp_headers, code, response = api_.get_collection_items(req, coll) # noqa
        features = json.loads(response)['features']

        assert len(features) == 10

        # bbox-crs partial extent, 1 feature, request with multiple CRSs
        for crs in CRS_BBOX_DICT:
            req = mock_request({'bbox': CRS_BBOX_DICT[crs], 'bbox-crs': crs}) # noqa
            rsp_headers, code, response = api_.get_collection_items(req, coll) # noqa
            features = json.loads(response)['features']

            assert len(features) == 1
            properties = features[0]['properties']
            assert properties['straatnaam'] == 'Willinkhuizersteeg'
            assert properties['huisnummer'] == '2'

        # bbox-crs outside extent
        req = mock_request({'bbox': '5, 51.9, 5.1, 52.0', 'bbox-crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'}) # noqa
        rsp_headers, code, response = api_.get_collection_items(req, coll) # noqa
        features = json.loads(response)['features']

        assert len(features) == 0

        # bbox-crs outside extent
        req = mock_request({'bbox': '130000, 440000, 140000, 450000', 'bbox-crs': 'http://www.opengis.net/def/crs/EPSG/0/28992'}) # noqa
        rsp_headers, code, response = api_.get_collection_items(req, coll) # noqa
        features = json.loads(response)['features']

        assert len(features) == 0

        # bbox-crs outside extent - axis reversed CRS
        req = mock_request({'bbox': '51.9, 5, 52.0, 5.1', 'bbox-crs': 'http://www.opengis.net/def/crs/EPSG/0/4326'}) # noqa
        rsp_headers, code, response = api_.get_collection_items(req, coll) # noqa
        features = json.loads(response)['features']

        assert len(features) == 0

        # bbox-crs full extent - axis reversed CRS
        req = mock_request({'bbox': '52.042700, 5.670670, 52.123700, 5.829110', 'bbox-crs': 'http://www.opengis.net/def/crs/EPSG/0/4326'}) # noqa
        rsp_headers, code, response = api_.get_collection_items(req, coll) # noqa
        features = json.loads(response)['features']

        assert len(features) == 10
