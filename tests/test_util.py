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
from contextlib import nullcontext as does_not_raise
from copy import deepcopy
from io import StringIO
from unittest import mock
import uuid

import pytest
from pyproj.exceptions import CRSError
import pygeofilter.ast
from pygeofilter.parsers.ecql import parse
from pygeofilter.values import Geometry
from shapely.geometry import Point

from pygeoapi import util
from pygeoapi.api import __version__
from pygeoapi.provider.base import ProviderTypeError

from .util import get_test_file_path


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return util.yaml_load(fh)


@pytest.fixture()
def config_with_rules() -> dict:
    """ Returns a pygeoapi configuration with default API rules. """
    with open(get_test_file_path('pygeoapi-test-config-apirules.yml')) as fh:
        return util.yaml_load(fh)


def test_get_typed_value():
    value = util.get_typed_value('2')
    assert isinstance(value, int)

    value = util.get_typed_value('1.2')
    assert isinstance(value, float)

    value = util.get_typed_value('1.c2')
    assert isinstance(value, str)


def test_yaml_load(config):
    assert isinstance(config, dict)
    with pytest.raises(FileNotFoundError):
        with open(get_test_file_path('404.yml')) as fh:
            util.yaml_load(fh)


@pytest.mark.parametrize('env,input_config,expected', [
    pytest.param({}, 'foo: something', {'foo': 'something'}, id='no-env-expansion'),  # noqa E501
    pytest.param({'FOO': 'this'}, 'foo: ${FOO}', {'foo': 'this'}),  # noqa E501
    pytest.param({'FOO': 'this'}, 'foo: the value is ${FOO}', {'foo': 'the value is this'}, id='no-need-for-yaml-tag'),  # noqa E501
    pytest.param({}, 'foo: ${FOO:-some default}', {'foo': 'some default'}),  # noqa E501
    pytest.param({'FOO': 'this', 'BAR': 'that'}, 'composite: ${FOO}:${BAR}', {'composite': 'this:that'}),  # noqa E501
    pytest.param({}, 'composite: ${FOO:-default-foo}:${BAR:-default-bar}', {'composite': 'default-foo:default-bar'}),  # noqa E501
    pytest.param(
        {
            'HOST': 'fake-host',
            'USER': 'fake',
            'PASSWORD': 'fake-pass',
            'DB': 'fake-db'
        },
        'connection: postgres://${USER}:${PASSWORD}@${HOST}:${PORT:-5432}/${DB}',  # noqa E501
        {
            'connection': 'postgres://fake:fake-pass@fake-host:5432/fake-db'
        },
        id='multiple-no-need-yaml-tag'
    ),
])
def test_yaml_load_with_env_variables(
        env: dict[str, str], input_config: str, expected):

    def mock_get_env(env_var_name):
        result = env.get(env_var_name)
        return result

    with mock.patch('pygeoapi.util.os') as mock_os:
        mock_os.getenv.side_effect = mock_get_env
        loaded_config = util.yaml_load(StringIO(input_config))
        assert loaded_config == expected


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

    d = uuid.UUID('12345678-1234-5678-1234-567812345678')
    assert util.json_serial(d) == '12345678-1234-5678-1234-567812345678'

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


def test_filter_dict_by_key_value(config):
    collections = util.filter_dict_by_key_value(config['resources'],
                                                'type', 'collection')
    assert len(collections) == 9

    notfound = util.filter_dict_by_key_value(config['resources'],
                                             'type', 'foo')

    assert len(notfound) == 0


def test_get_provider_by_type(config):
    p = util.get_provider_by_type(config['resources']['obs']['providers'],
                                  'feature')

    assert isinstance(p, dict)
    assert p['type'] == 'feature'
    assert p['name'] == 'CSV'

    with pytest.raises(ProviderTypeError):
        p = util.get_provider_by_type(config['resources']['obs']['providers'],
                                      'something-else')


def test_get_provider_default(config):
    pd = util.get_provider_default(config['resources']['obs']['providers'])

    assert pd['type'] == 'feature'
    assert pd['name'] == 'CSV'

    pd = util.get_provider_default(config['resources']['obs']['providers'])


def test_read_data():
    data = util.read_data(get_test_file_path('pygeoapi-test-config.yml'))

    assert isinstance(data, bytes)


def test_url_join():
    f = util.url_join
    assert f('http://localhost:5000') == 'http://localhost:5000'
    assert f('http://localhost:5000/') == 'http://localhost:5000'
    assert f('http://localhost:5000', '') == 'http://localhost:5000'
    assert f('http://localhost:5000/', '') == 'http://localhost:5000'
    assert f('http://localhost:5000/', '/') == 'http://localhost:5000'
    assert f('http://localhost:5000/api', '/') == 'http://localhost:5000/api'
    assert f('http://localhost:5000/api', '/v0') == 'http://localhost:5000/api/v0'  # noqa
    assert f('http://localhost:5000/api', '/v0/') == 'http://localhost:5000/api/v0'  # noqa
    assert f('http://localhost:5000', 'api', 'v0') == 'http://localhost:5000/api/v0'  # noqa


def test_get_base_url(config, config_with_rules):
    assert util.get_base_url(config) == 'http://localhost:5000'
    assert util.get_base_url(config_with_rules) == 'http://localhost:5000/api/v0'  # noqa


def test_get_api_rules(config, config_with_rules):
    # Test unset/default rules
    rules = util.get_api_rules(config)
    assert not rules.strict_slashes
    assert not rules.url_prefix
    assert rules.api_version == __version__
    assert rules.version_header == ''
    assert rules.get_url_prefix() == ''
    assert rules.response_headers == {}

    # Test configured rules
    rules = util.get_api_rules(config_with_rules)
    assert rules.strict_slashes
    assert rules.url_prefix
    assert rules.api_version == __version__
    assert rules.version_header == 'X-API-Version'
    assert rules.response_headers == {'X-API-Version': __version__}

    # Test specific version override
    config_changed = deepcopy(config_with_rules)
    config_changed['server']['api_rules']['api_version'] = '1.2.3'
    rules = util.get_api_rules(config_changed)
    assert rules.api_version == '1.2.3'
    assert rules.get_url_prefix() == 'v1'
    assert rules.get_url_prefix('flask') == '/v1'
    assert rules.get_url_prefix('starlette') == '/v1'
    assert rules.get_url_prefix('django') == r'^v1/'

    # Test prefix without version
    config_changed = deepcopy(config_with_rules)
    config_changed['server']['api_rules']['url_prefix'] = 'test'
    rules = util.get_api_rules(config_changed)
    assert rules.get_url_prefix() == 'test'
    assert rules.get_url_prefix('flask') == '/test'
    assert rules.get_url_prefix('starlette') == '/test'
    assert rules.get_url_prefix('django') == r'^test/'


def test_get_transform_from_crs():
    crs_in = util.get_crs_from_uri(
        'http://www.opengis.net/def/crs/EPSG/0/4258'
    )
    crs_out = util.get_crs_from_uri(
        'http://www.opengis.net/def/crs/EPSG/0/25833'
    )
    transform_func = util.get_transform_from_crs(crs_in, crs_out)
    p_in = Point((67.278972, 14.394493))
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


@pytest.mark.parametrize('uri, expected_raise, expected', [
    pytest.param('http://www.opengis.net/not/a/valid/crs/uri', pytest.raises(CRSError), None),  # noqa
    pytest.param('http://www.opengis.net/def/crs/EPSG/0/0', pytest.raises(CRSError), None),  # noqa
    pytest.param('http://www.opengis.net/def/crs/OGC/1.3/CRS84', does_not_raise(), 'OGC:CRS84'),  # noqa
    pytest.param('http://www.opengis.net/def/crs/EPSG/0/4326', does_not_raise(), 'EPSG:4326'),  # noqa
    pytest.param('http://www.opengis.net/def/crs/EPSG/0/28992', does_not_raise(), 'EPSG:28992'),  # noqa
    pytest.param('urn:ogc:def:crs:not:a:valid:crs:urn', pytest.raises(CRSError), None),  # noqa
    pytest.param('urn:ogc:def:crs:epsg:0:0', pytest.raises(CRSError), None),
    pytest.param('urn:ogc:def:crs:epsg::0', pytest.raises(CRSError), None),
    pytest.param('urn:ogc:def:crs:OGC::0', pytest.raises(CRSError), None),
    pytest.param('urn:ogc:def:crs:OGC:0:0', pytest.raises(CRSError), None),
    pytest.param('urn:ogc:def:crs:OGC:0:CRS84', does_not_raise(), "OGC:CRS84"),
    pytest.param('urn:ogc:def:crs:OGC::CRS84', does_not_raise(), "OGC:CRS84"),
    pytest.param('urn:ogc:def:crs:EPSG:0:4326', does_not_raise(), "EPSG:4326"),
    pytest.param('urn:ogc:def:crs:EPSG::4326', does_not_raise(), "EPSG:4326"),
    pytest.param('urn:ogc:def:crs:epsg:0:4326', does_not_raise(), "EPSG:4326"),
    pytest.param('urn:ogc:def:crs:epsg:0:28992', does_not_raise(), "EPSG:28992"),  # noqa
])
def test_get_crs_from_uri(uri, expected_raise, expected):
    with expected_raise:
        crs = util.get_crs_from_uri(uri)
        assert crs.srs.upper() == expected


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


@pytest.mark.parametrize('original_filter, filter_crs, storage_crs, geometry_colum_name, expected', [  # noqa
    pytest.param(
        'INTERSECTS(geometry, POINT(1 1))',
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        None,
        None,
        pygeofilter.ast.GeometryIntersects(
            pygeofilter.ast.Attribute(name='geometry'),
            Geometry({'type': 'Point', 'coordinates': (1, 1)})
        ),
        id='passthrough'
    ),
    pytest.param(
        "INTERSECTS(geometry, POINT(1 1))",
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        None,
        'custom_geom_name',
        pygeofilter.ast.GeometryIntersects(
            pygeofilter.ast.Attribute(name='custom_geom_name'),
            Geometry({'type': 'Point', 'coordinates': (1, 1)})
        ),
        id='unnested-geometry-name'
    ),
    pytest.param(
        "some_attribute = 10 AND INTERSECTS(geometry, POINT(1 1))",
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        None,
        'custom_geom_name',
        pygeofilter.ast.And(
            pygeofilter.ast.Equal(
                pygeofilter.ast.Attribute(name='some_attribute'), 10),
            pygeofilter.ast.GeometryIntersects(
                pygeofilter.ast.Attribute(name='custom_geom_name'),
                Geometry({'type': 'Point', 'coordinates': (1, 1)})
            ),
        ),
        id='nested-geometry-name'
    ),
    pytest.param(
        "(some_attribute = 10 AND INTERSECTS(geometry, POINT(1 1))) OR "
        "DWITHIN(geometry, POINT(2 2), 10, meters)",
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        None,
        'custom_geom_name',
        pygeofilter.ast.Or(
            pygeofilter.ast.And(
                pygeofilter.ast.Equal(
                    pygeofilter.ast.Attribute(name='some_attribute'), 10),
                pygeofilter.ast.GeometryIntersects(
                    pygeofilter.ast.Attribute(name='custom_geom_name'),
                    Geometry({'type': 'Point', 'coordinates': (1, 1)})
                ),
            ),
            pygeofilter.ast.DistanceWithin(
                pygeofilter.ast.Attribute(name='custom_geom_name'),
                Geometry({'type': 'Point', 'coordinates': (2, 2)}),
                distance=10,
                units='meters',
            )
        ),
        id='complex-filter-name'
    ),
    pytest.param(
        "INTERSECTS(geometry, POINT(12.512829 41.896698))",
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        'http://www.opengis.net/def/crs/EPSG/0/3004',
        None,
        pygeofilter.ast.GeometryIntersects(
            pygeofilter.ast.Attribute(name='geometry'),
            Geometry({'type': 'Point', 'coordinates': (2313682.387730346, 4641308.550187246)})  # noqa
        ),
        id='unnested-geometry-transformed-coords'
    ),
    pytest.param(
        "some_attribute = 10 AND INTERSECTS(geometry, POINT(12.512829 41.896698))",  # noqa
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        'http://www.opengis.net/def/crs/EPSG/0/3004',
        None,
        pygeofilter.ast.And(
            pygeofilter.ast.Equal(
                pygeofilter.ast.Attribute(name='some_attribute'), 10),
            pygeofilter.ast.GeometryIntersects(
                pygeofilter.ast.Attribute(name='geometry'),
                Geometry({'type': 'Point', 'coordinates': (2313682.387730346, 4641308.550187246)})  # noqa
            ),
        ),
        id='nested-geometry-transformed-coords'
    ),
    pytest.param(
        "(some_attribute = 10 AND INTERSECTS(geometry, POINT(12.512829 41.896698))) OR "  # noqa
        "DWITHIN(geometry, POINT(12 41), 10, meters)",
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        'http://www.opengis.net/def/crs/EPSG/0/3004',
        None,
        pygeofilter.ast.Or(
            pygeofilter.ast.And(
                pygeofilter.ast.Equal(
                    pygeofilter.ast.Attribute(name='some_attribute'), 10),
                pygeofilter.ast.GeometryIntersects(
                    pygeofilter.ast.Attribute(name='geometry'),
                    Geometry({'type': 'Point', 'coordinates': (2313682.387730346, 4641308.550187246)})  # noqa
                ),
            ),
            pygeofilter.ast.DistanceWithin(
                pygeofilter.ast.Attribute(name='geometry'),
                Geometry({'type': 'Point', 'coordinates': (2267681.8892602, 4543101.513292163)}),  # noqa
                distance=10,
                units='meters',
            )
        ),
        id='complex-filter-transformed-coords'
    ),
    pytest.param(
        "INTERSECTS(geometry, SRID=3857;POINT(1392921 5145517))",
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        'http://www.opengis.net/def/crs/EPSG/0/3004',
        None,
        pygeofilter.ast.GeometryIntersects(
            pygeofilter.ast.Attribute(name='geometry'),
            Geometry({'type': 'Point', 'coordinates': (2313681.8086284213, 4641307.939955416)})  # noqa
        ),
        id='unnested-geometry-transformed-coords-explicit-input-crs-ewkt'
    ),
    pytest.param(
        "INTERSECTS(geometry, POINT(1392921 5145517))",
        'http://www.opengis.net/def/crs/EPSG/0/3857',
        'http://www.opengis.net/def/crs/EPSG/0/3004',
        None,
        pygeofilter.ast.GeometryIntersects(
            pygeofilter.ast.Attribute(name='geometry'),
            Geometry({'type': 'Point', 'coordinates': (2313681.8086284213, 4641307.939955416)})  # noqa
        ),
        id='unnested-geometry-transformed-coords-explicit-input-crs-filter-crs'
    ),
    pytest.param(
        "INTERSECTS(geometry, SRID=3857;POINT(1392921 5145517))",
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        'http://www.opengis.net/def/crs/EPSG/0/3004',
        None,
        pygeofilter.ast.GeometryIntersects(
            pygeofilter.ast.Attribute(name='geometry'),
            Geometry({'type': 'Point', 'coordinates': (2313681.8086284213, 4641307.939955416)})  # noqa
        ),
        id='unnested-geometry-transformed-coords-ewkt-crs-overrides-filter-crs'
    ),
    pytest.param(
        "INTERSECTS(geometry, POINT(12.512829 41.896698))",
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        'http://www.opengis.net/def/crs/EPSG/0/3004',
        'custom_geom_name',
        pygeofilter.ast.GeometryIntersects(
            pygeofilter.ast.Attribute(name='custom_geom_name'),
            Geometry({'type': 'Point', 'coordinates': (2313682.387730346, 4641308.550187246)})  # noqa
        ),
        id='unnested-geometry-name-and-transformed-coords'
    ),
])
def test_modify_pygeofilter(
        original_filter,
        filter_crs,
        storage_crs,
        geometry_colum_name,
        expected
):
    parsed_filter = parse(original_filter)
    result = util.modify_pygeofilter(
        parsed_filter,
        filter_crs_uri=filter_crs,
        storage_crs_uri=storage_crs,
        geometry_column_name=geometry_colum_name
    )
    assert result == expected
