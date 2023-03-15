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

from datetime import datetime, date, time
from decimal import Decimal

import pytest
from pyproj.exceptions import CRSError
from shapely.geometry import Point

from pygeoapi import util
from pygeoapi.provider.base import ProviderTypeError

from .util import get_test_file_path


def test_get_typed_value():
    value = util.get_typed_value('2')
    assert isinstance(value, int)

    value = util.get_typed_value('1.2')
    assert isinstance(value, float)

    value = util.get_typed_value('1.c2')
    assert isinstance(value, str)


def test_yaml_load():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        d = util.yaml_load(fh)
        assert isinstance(d, dict)
    with pytest.raises(FileNotFoundError):
        with open(get_test_file_path('404.yml')) as fh:
            d = util.yaml_load(fh)


def test_str2bool():
    assert not util.str2bool(False)
    assert not util.str2bool('0')
    assert not util.str2bool('no')
    assert util.str2bool('yes')
    assert util.str2bool('1')
    assert util.str2bool(True)
    assert util.str2bool('true')
    assert util.str2bool('True')
    assert util.str2bool('TRUE')
    assert util.str2bool('tRuE')
    assert util.str2bool('on')
    assert util.str2bool('On')
    assert not util.str2bool('off')


def test_json_serial():
    d = datetime(1972, 10, 30)
    assert util.json_serial(d) == '1972-10-30T00:00:00'

    d = date(2010, 7, 31)
    assert util.json_serial(d) == '2010-07-31'

    d = time(11)
    assert util.json_serial(d) == '11:00:00'

    d = Decimal(1.0)
    assert util.json_serial(d) == 1.0

    with pytest.raises(TypeError):
        util.json_serial('foo')


def test_mimetype():
    assert util.get_mimetype('file.xml') == 'application/xml'
    assert util.get_mimetype('file.yml') == 'text/plain'
    assert util.get_mimetype('file.yaml') == 'text/plain'


def test_get_breadcrumbs():
    path = '/dataset/model-run/forecast-hour/variable.grib2'
    breadcrumbs = util.get_breadcrumbs(path)

    assert len(breadcrumbs) == 5
    assert breadcrumbs[3]['href'] == 'dataset/model-run/forecast-hour'


def test_path_basename():
    assert util.get_path_basename('/path/to/file.txt') == 'file.txt'
    assert util.get_path_basename('/path/to/dir') == 'dir'


def test_filter_dict_by_key_value():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        d = util.yaml_load(fh)

    collections = util.filter_dict_by_key_value(d['resources'],
                                                'type', 'collection')
    assert len(collections) == 8

    notfound = util.filter_dict_by_key_value(d['resources'],
                                             'type', 'foo')

    assert len(notfound) == 0


def test_get_provider_by_type():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        d = util.yaml_load(fh)

    p = util.get_provider_by_type(d['resources']['obs']['providers'],
                                  'feature')

    assert isinstance(p, dict)
    assert p['type'] == 'feature'
    assert p['name'] == 'CSV'

    with pytest.raises(ProviderTypeError):
        p = util.get_provider_by_type(d['resources']['obs']['providers'],
                                      'something-else')


def test_get_provider_default():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        d = util.yaml_load(fh)

    pd = util.get_provider_default(d['resources']['obs']['providers'])

    assert pd['type'] == 'feature'
    assert pd['name'] == 'CSV'

    pd = util.get_provider_default(d['resources']['obs']['providers'])


def test_read_data():
    data = util.read_data(get_test_file_path('pygeoapi-test-config.yml'))

    assert isinstance(data, bytes)


def test_get_transform_from_crs():
    crs_in = util.get_crs_from_uri(
        'http://www.opengis.net/def/crs/EPSG/0/4258'
    )
    crs_out = util.get_crs_from_uri(
        'http://www.opengis.net/def/crs/EPSG/0/25833'
    )
    transform_func = util.get_transform_from_crs(crs_in, crs_out)
    p_in = Point((14.394493, 67.278972))
    p_out = Point((473901.6105, 7462606.8762))
    assert p_out.equals_exact(transform_func(p_in), 1e-3)


def test_get_supported_crs_list():
    DEFAULT_CRS_LIST = [
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84h'
    ]
    DUTCH_CRS = 'http://www.opengis.net/def/crs/EPSG/0/28992'

    # Make various combinations of configs
    CONFIGS = \
        [
            dict(),
            {'crs': ['http://www.opengis.net/def/crs/OGC/1.3/CRS84']},
            {'crs': ['http://www.opengis.net/def/crs/OGC/1.3/CRS84h']},
            {'crs': ['http://www.opengis.net/def/crs/EPSG/0/4326',
                     'http://www.opengis.net/def/crs/OGC/1.3/CRS84']},
            {'crs': ['http://www.opengis.net/def/crs/EPSG/0/4326',
                     DUTCH_CRS]},
        ]
    # Apply all configs to util function
    for config in CONFIGS:
        crs_list = util.get_supported_crs_list(config, DEFAULT_CRS_LIST)

        # Whatever config: a default should be present
        contains_default = False
        for crs in crs_list:
            if crs in DEFAULT_CRS_LIST:
                contains_default = True
        assert contains_default

        # Extra CRSs supplied should also be present
        if DUTCH_CRS in config:
            assert DUTCH_CRS in crs_list


def test_get_crs_from_uri():
    with pytest.raises(CRSError):
        util.get_crs_from_uri('http://www.opengis.net/not/a/valid/crs/uri')
    with pytest.raises(CRSError):
        util.get_crs_from_uri('http://www.opengis.net/def/crs/EPSG/0/0')
    CRS_DICT = {
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84': 'OGC:CRS84',
        'http://www.opengis.net/def/crs/EPSG/0/4326': 'EPSG:4326',
        'http://www.opengis.net/def/crs/EPSG/0/28992': 'EPSG:28992'
    }
    for key in CRS_DICT:
        crs_obj = util.get_crs_from_uri(key)
        assert crs_obj.srs == CRS_DICT[key]


def test_transform_bbox():
    # Use rounded values as fractions may differ
    result = [59742, 446645, 129005, 557074]

    bbox = [4, 52, 5, 53]
    from_crs = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
    to_crs = 'http://www.opengis.net/def/crs/EPSG/0/28992'
    bbox_trans = util.transform_bbox(bbox, from_crs, to_crs)
    for n in range(4):
        assert round(bbox_trans[n]) == result[n]

    bbox = [52, 4, 53, 5]
    from_crs = 'http://www.opengis.net/def/crs/EPSG/0/4326'
    bbox_trans = util.transform_bbox(bbox, from_crs, to_crs)
    for n in range(4):
        assert round(bbox_trans[n]) == result[n]


def test_prefetcher():
    prefetcher = util.UrlPrefetcher()
    assert prefetcher.get_headers('bad_url') == {}
    # URL below will redirect once
    url = 'https://github.com/geopython/pygeoapi/raw/4a18393662583e53b8c7d591130246d9cd2c3f3f/pygeoapi/static/img/pygeoapi.png'  # noqa
    headers = prefetcher.get_headers(url)
    length = int(headers.get('content-length', 0))
    assert length > 0
    # Test without redirect
    headers = prefetcher.get_headers(url, allow_redirects=False)
    assert headers.get('content-length') in (0, '0', None)
    assert headers.get('content-type') != 'image/png'
    # Test using redirect location from header
    headers = prefetcher.get_headers(headers['location'])
    assert int(headers.get('content-length', 0)) == length
    assert headers.get('content-type') == 'image/png'
