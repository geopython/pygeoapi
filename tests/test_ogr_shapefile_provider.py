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

# Needs to be run like: python3 -m pytest

import logging

import pytest
import pyproj

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.ogr import OGRProvider
from pygeoapi.util import (
    CrsTransformSpec, get_transform_from_crs, geojson_to_geom,
)

LOGGER = logging.getLogger(__name__)


# Testing with Shapefiles with identical features
# (all 2481 addresses in Otterlo Netherlands)
# in different projections.

@pytest.fixture()
def config_shapefile_4326():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'ESRI Shapefile',
            'source':
                './tests/data/dutch_addresses_shape_4326/inspireadressen.shp',
            'source_capabilities': {
                'paging': True
            },
        },
        'id_field': 'id',
        'layer': 'inspireadressen'
    }


# Note that this Shapefile is zipped, as OGR supports /vsizip/!
@pytest.fixture()
def config_shapefile_28992():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'ESRI Shapefile',
            'source':
                '/vsizip/./tests/data/dutch_addresses_shape_28992.zip',
            'source_capabilities': {
                'paging': True
            },
        },
        'crs': [
            'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
            'http://www.opengis.net/def/crs/EPSG/0/28992'
        ],
        'storage_crs': 'http://www.opengis.net/def/crs/EPSG/0/28992',
        'id_field': 'id',
        'layer': 'inspireadressen'
    }


@pytest.fixture()
def crs_transform_spec():
    return CrsTransformSpec(
        source_crs_uri='http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        source_crs_wkt=pyproj.CRS.from_epsg(4326),
        target_crs_uri='http://www.opengis.net/def/crs/EPSG/0/28992',
        target_crs_wkt=pyproj.CRS.from_epsg(28992),
    )


def test_get_fields_4326(config_shapefile_4326):
    """Testing field types"""
    p = OGRProvider(config_shapefile_4326)
    results = p.get_fields()
    assert results['straatnaam']['type'] == 'string'
    assert results['huisnummer']['type'] == 'string'


def test_get_28992(config_shapefile_28992):
    """Testing query for a specific object"""
    p = OGRProvider(config_shapefile_28992)
    result = p.get('inspireadressen.1747652')
    assert result['id'] == 'inspireadressen.1747652'
    assert 'Mosselsepad' in result['properties']['straatnaam']


def test_get_crs_4326(config_shapefile_4326, crs_transform_spec):
    """Testing query with and without crs parameter for a specific object"""
    # Query without CRS parameter
    p = OGRProvider(config_shapefile_4326)
    result_orig = p.get('inspireadressen.1747652')
    geom_orig = geojson_to_geom(result_orig['geometry'])
    assert result_orig['id'] == 'inspireadressen.1747652'
    assert 'Mosselsepad' in result_orig['properties']['straatnaam']

    # Query with CRS parameter
    result_28992 = p.get(
        'inspireadressen.1747652', crs_transform_spec=crs_transform_spec,
    )
    geom_28992 = geojson_to_geom(result_28992['geometry'])
    assert result_28992['id'] == 'inspireadressen.1747652'
    assert 'Mosselsepad' in result_28992['properties']['straatnaam']

    transform_func = get_transform_from_crs(
        pyproj.CRS.from_epsg(4326),
        pyproj.CRS.from_epsg(28992),
        always_xy=True
    )
    geom_28992_from_orig = transform_func(geom_orig)
    assert geom_28992.equals_exact(geom_28992_from_orig, 1)


def test_get_not_existing_feature_raise_exception(
    config_shapefile_4326
):
    """Testing query for a not existing object"""
    p = OGRProvider(config_shapefile_4326)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_query_hits_28992(config_shapefile_28992):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_shapefile_28992)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits == 2481


def test_query_hits_4326(config_shapefile_4326):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_shapefile_4326)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits == 2481


def test_query_bbox_hits_4326(config_shapefile_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_4326)
    # feature_collection = p.query(
    # bbox=[120000, 480000, 124000, 487000], resulttype='hits')
    feature_collection = p.query(
        bbox=[5.763409, 52.060197, 5.769256, 52.061976], resulttype='hits')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits == 1


def test_query_bbox_hits_28992(config_shapefile_28992):
    """Testing query for a valid JSON object with geometry, single address"""

    p = OGRProvider(config_shapefile_28992)
    # feature_collection = p.query(
    #     bbox=(180800, 452500, 181200, 452700), resulttype='hits')
    feature_collection = p.query(
        bbox=[180800, 452500, 181200, 452700], resulttype='hits')

    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits == 1


def test_query_bbox_28992(config_shapefile_28992):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_28992)
    # feature_collection = p.query(
    #     bbox=[180800, 452500, 181200, 452700], resulttype='results')
    feature_collection = p.query(
        bbox=(180800, 452500, 181200, 452700), resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 1
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    geometry = feature.get('geometry')
    assert geometry is not None
    assert properties['straatnaam'] == 'Planken Wambuisweg'


def test_query_crs_and_bbox_4326(config_shapefile_4326, crs_transform_spec):
    """Testing query for a valid JSON object with bbox and with/without crs"""

    p = OGRProvider(config_shapefile_4326)
    # feature_collection = p.query(
    #     bbox=[180800, 452500, 181200, 452700], resulttype='results')
    # Query without CRS parameter
    fc_orig = p.query(
        bbox=(5.763409, 52.060197, 5.769256, 52.061976), resulttype='results')
    assert fc_orig.get('type') == 'FeatureCollection'
    features_orig = fc_orig.get('features')
    assert len(features_orig) == 1
    hits = fc_orig.get('numberMatched')
    assert hits is None
    feature = features_orig[0]
    properties = feature.get('properties')
    assert properties is not None
    geojson_geom_orig = feature.get('geometry')
    assert geojson_geom_orig is not None
    assert properties['straatnaam'] == 'Planken Wambuisweg'

    # Query with CRS parameter
    fc_28992 = p.query(
        bbox=(5.763409, 52.060197, 5.769256, 52.061976),
        resulttype='results',
        crs_transform_spec=crs_transform_spec,
    )
    assert fc_28992.get('type') == 'FeatureCollection'
    features_28992 = fc_28992.get('features')
    assert len(features_28992) == 1
    hits = fc_28992.get('numberMatched')
    assert hits is None
    feature = features_28992[0]
    properties = feature.get('properties')
    assert properties is not None
    geojson_geom_28992 = feature.get('geometry')
    assert geojson_geom_28992 is not None
    assert properties['straatnaam'] == 'Planken Wambuisweg'

    transform_func = get_transform_from_crs(
        pyproj.CRS.from_epsg(4326),
        pyproj.CRS.from_epsg(28992),
        always_xy=True,
    )
    geom_orig = geojson_to_geom(geojson_geom_orig)
    geom_28992 = geojson_to_geom(geojson_geom_28992)
    geom_orig_to_28992 = transform_func(geom_orig)
    assert geom_28992.equals_exact(geom_orig_to_28992, 1)


def test_query_with_limit_28992(config_shapefile_28992):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_28992)
    feature_collection = p.query(limit=2, resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 2
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    geometry = feature.get('geometry')
    assert geometry is not None


def test_query_with_limit_4326(config_shapefile_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_4326)
    feature_collection = p.query(limit=5, resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 5
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    geometry = feature.get('geometry')
    assert geometry is not None


def test_query_with_offset_28992(config_shapefile_28992):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_28992)
    feature_collection = p.query(offset=20, limit=5, resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 5
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    assert feature['id'] == 'inspireadressen.1744969'
    assert 'Egypte' in properties['straatnaam']
    geometry = feature.get('geometry')
    assert geometry is not None


def test_query_with_offset_4326(config_shapefile_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_4326)
    feature_collection = p.query(offset=20, limit=5, resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 5
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    assert feature['id'] == 'inspireadressen.1744969'
    assert 'Egypte' in properties['straatnaam']
    geometry = feature.get('geometry')
    assert geometry is not None


def test_query_bbox_with_offset_28992(config_shapefile_28992):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_28992)
    feature_collection = p.query(
        offset=10, limit=5,
        bbox=(181000, 456000, 182000, 457000),
        resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 5
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    geometry = feature.get('geometry')
    assert geometry is not None
    assert properties['straatnaam'] == 'Arnhemseweg'
    assert properties['huisnummer'] == '99'


def test_query_bbox_with_offset_4326(config_shapefile_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_4326)
    feature_collection = p.query(
        offset=1, limit=5,
        bbox=(5.742, 52.053, 5.773, 52.098),
        resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 5
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    geometry = feature.get('geometry')
    assert geometry is not None
    assert properties['straatnaam'] == 'Egypte'
    assert properties['huisnummer'] == '6'


def test_query_with_property_filtering(config_shapefile_4326):
    """Testing query with property filtering"""

    p = OGRProvider(config_shapefile_4326)

    feature_collection = p.query(
        properties=[
            ('straatnaam', 'Arnhemseweg')
        ]
    )

    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) > 1

    for feature in features:
        assert 'properties' in feature
        assert 'straatnaam' in feature['properties']

        assert feature['properties']['straatnaam'] == 'Arnhemseweg'
