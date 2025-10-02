# =================================================================
#
# Authors: Benjamin Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2025 Benjamin Webb
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
import logging

import pytest
from shapely.geometry import (Point, MultiPoint, Polygon,
                              MultiPolygon, LineString, MultiLineString)

from pygeoapi.linked_data import (
    geojson2jsonld,
    geom2schemageo,
    jsonldify_geometry
)


LOGGER = logging.getLogger(__name__)


@pytest.fixture
def feature():
    return {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [125.6, 10.1]
        },
        'properties': {
            'name': 'Test Point'
        },
        'id': 'test1',
        'links': []
    }


def test_geojson2jsonld_single_feature(api_, feature):
    """Test conversion of single GeoJSON feature to JSON-LD"""

    result = geojson2jsonld(api_, feature,
                            'obs', 'http://example.org/feature/1')
    result_dict = json.loads(result)

    assert '@context' in result_dict
    assert len(result_dict['@context']) == 2
    assert 'stn_id' in result_dict['@context'][1]

    assert result_dict['@id'] == 'http://example.org/feature/1'
    assert 'schema:geo' in result_dict


def test_geom2schemageo():
    """Test conversion of various geometry types to schema.org geometry"""

    # Test Point
    point = Point(125.6, 10.1)
    point_result = geom2schemageo(point)
    assert point_result['@type'] == 'schema:GeoCoordinates'
    assert point_result['schema:longitude'] == 125.6
    assert point_result['schema:latitude'] == 10.1

    # Test LineString
    line = LineString([(0, 0), (1, 1)])
    line_result = geom2schemageo(line)
    assert line_result['@type'] == 'schema:GeoShape'
    assert 'schema:line' in line_result

    # Test Polygon
    polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    poly_result = geom2schemageo(polygon)
    assert poly_result['@type'] == 'schema:GeoShape'
    assert 'schema:polygon' in poly_result


def test_jsonldify_geometry(feature):
    """Test addition of multiple geometry encodings to a feature"""

    jsonldify_geometry(feature)

    assert feature['type'] == 'schema:Place'
    assert 'gsp:hasGeometry' in feature
    assert 'schema:geo' in feature
    assert feature['schema:geo']['@type'] == 'schema:GeoCoordinates'


def test_jsonldify_invalid_geometry(feature):
    """Test invalid geometry encodings to a feature"""
    feature['geometry']['type'] = 'MultiPolygon'
    feature['geometry']['coordinates'] = []
    jsonldify_geometry(feature)

    assert feature['type'] == 'schema:Place'
    assert 'schema:geo' not in feature


@pytest.mark.parametrize('geom_type,coords', [
    ('Point', [125.6, 10.1]),
    ('LineString', [(0, 0), (1, 1)]),
    ('Polygon', [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]),
    ('MultiPoint', [(0, 0), (1, 1)]),
    ('MultiLineString', [[(0, 0), (1, 1)], [(2, 2), (3, 3)]]),
    ('MultiPolygon', [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)],
                      [(2, 2), (3, 2), (3, 3), (2, 3), (2, 2)]])
])
def test_geometry_conversions(geom_type, coords):
    """Test conversion of different geometry types"""
    if geom_type == 'Point':
        geom = Point(coords)
    elif geom_type == 'LineString':
        geom = LineString(coords)
    elif geom_type == 'Polygon':
        geom = Polygon(coords)
    elif geom_type == 'MultiPoint':
        geom = MultiPoint(coords)
    elif geom_type == 'MultiLineString':
        geom = MultiLineString(coords)
    elif geom_type == 'MultiPolygon':
        geom = MultiPolygon([Polygon(poly) for poly in coords])

    result = geom2schemageo(geom)
    assert result['@type'] in ['schema:GeoCoordinates', 'schema:GeoShape']


def test_render_item_template(api_, feature):
    """Test conversion rendering of item template"""

    # Use 'objects' collection which has item json-ld template
    result = geojson2jsonld(api_, deepcopy(feature),
                            'objects', 'http://example.org/feature/1')

    # Ensure item template is renderable
    assert json.loads(result)


def test_render_items_template(api_, feature):
    """Test conversion rendering of items template"""

    fc = {
        'features': [deepcopy(feature) for _ in range(5)],
        'links': []
    }

    result = geojson2jsonld(api_, fc, 'objects')
    feature_list = json.loads(result)

    assert len(feature_list['features']) == len(fc['features'])

    for fld, f in zip(feature_list['features'], fc['features']):
        assert ['@type', '@id'] == list(fld.keys())
        assert f['id'] in fld['@id']
