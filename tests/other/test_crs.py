# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2025 Tom Kralidis
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

from contextlib import nullcontext as does_not_raise

import pytest
from pyproj.exceptions import CRSError
import pygeofilter.ast
from pygeofilter.parsers.ecql import parse
from pygeofilter.values import Geometry
from shapely.geometry import Point

from pygeoapi import crs


def test_get_transform_from_crs():
    crs_in = crs.get_crs_from_uri(
        'http://www.opengis.net/def/crs/EPSG/0/4258'
    )
    crs_out = crs.get_crs_from_uri(
        'http://www.opengis.net/def/crs/EPSG/0/25833'
    )
    transform_func = crs.get_transform_from_crs(crs_in, crs_out)
    p_in = Point((67.278972, 14.394493))
    p_out = Point((473901.6105, 7462606.8762))
    assert p_out.equals_exact(transform_func(p_in), 1e-3)


def test_get_supported_crs_list():
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
        crs_list = crs.get_supported_crs_list(config, crs.DEFAULT_CRS_LIST)

        # Whatever config: a default should be present
        contains_default = False
        for crs_ in crs_list:
            if crs_ in crs.DEFAULT_CRS_LIST:
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
        crs_ = crs.get_crs_from_uri(uri)
        assert crs_.srs.upper() == expected


def test_transform_bbox():
    # Use rounded values as fractions may differ
    result = [59742, 446645, 129005, 557074]

    bbox = [4, 52, 5, 53]
    from_crs = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
    to_crs = 'http://www.opengis.net/def/crs/EPSG/0/28992'
    bbox_trans = crs.transform_bbox(bbox, from_crs, to_crs)
    for n in range(4):
        assert round(bbox_trans[n]) == result[n]

    bbox = [52, 4, 53, 5]
    from_crs = 'http://www.opengis.net/def/crs/EPSG/0/4326'
    bbox_trans = crs.transform_bbox(bbox, from_crs, to_crs)
    for n in range(4):
        assert round(bbox_trans[n]) == result[n]


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
            Geometry({'type': 'Point', 'coordinates': (2313681.808628421, 4641307.939955416), 'crs': {'properties': {'name': 'urn:ogc:def:crs:EPSG::3004'}}}) # noqa
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
            Geometry({'type': 'Point', 'coordinates': (2313681.808628421, 4641307.939955416), 'crs': {'properties': {'name': 'urn:ogc:def:crs:EPSG::3004'}}}) # noqa
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
            Geometry({'type': 'Point', 'coordinates': (2313681.808628421, 4641307.939955416), 'crs': {'properties': {'name': 'urn:ogc:def:crs:EPSG::3004'}}}) # noqa
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
    result = crs.modify_pygeofilter(
        parsed_filter,
        filter_crs_uri=filter_crs,
        storage_crs_uri=storage_crs,
        geometry_column_name=geometry_colum_name
    )
    assert result == expected
