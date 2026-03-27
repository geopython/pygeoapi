# =================================================================
#
# Authors: Joana Simoes <doublebyte@doublebyte.net>
#
#
# Copyright (c) 2026 Joana Simoes
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

from pygeoapi.provider.base import ProviderQueryError
from pygeoapi.provider.wms_facade import WMSFacadeProvider

@pytest.fixture()
def config():
    return {
        'name': 'WMSFacade',
        'type': 'map',
        'data': 'https://demo.mapserver.org/cgi-bin/msautotest',
        'options': {
            'layer': 'world_latlong',
            'style': 'default'
        },
        'format': {
            'name': 'png',
            'mimetype': 'image/png'
        }
    }

def test_query(config):
    p = WMSFacadeProvider(config)

    results = p.query()
    assert len(results) > 0

    # an invalid CRS should return the default bbox (4326)
    results2 = p.query(crs='http://www.opengis.net/def/crs/EPSG/0/1111')
    assert len(results2) == len(results)

    results3 = p.query(crs='http://www.opengis.net/def/crs/EPSG/0/3857')
    assert len(results3) != len(results)

def test_invalid_bbox_exception(config):
    """Testing query for a invalid bounding box"""
    p = WMSFacadeProvider(config)

    with pytest.raises(ProviderQueryError) as exc_info:
        p.query(bbox=[-2000, -90, 180, 90])
        assert "Invalid bounding box" in str(exc_info.value)