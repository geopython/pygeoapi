# Needs to be run like: python3 -m pytest

import logging

import pytest

from pygeoapi.provider.ogr import OGRProvider

LOGGER = logging.getLogger(__name__)


# Testing with Shapefiles with identical features
# (all 2481 addresses in Otterlo Netherlands)
# in different projections.

@pytest.fixture()
def config_shapefile_4326():
    return {
        'name': 'OGR',
        'data': {
            'source_type': 'ESRI Shapefile',
            'source':
                './tests/data/dutch_addresses_shape_4326/inspireadressen.shp',
            'source_capabilities': {
                'paging': True
            },
        },
        'id_field': 'id'
    }


# Note that this Shapefile is zipped, as OGR supports /vsizip/!
@pytest.fixture()
def config_shapefile_28992():
    return {
        'name': 'OGR',
        'data': {
            'source_type': 'ESRI Shapefile',
            'source':
                '/vsizip/./tests/data/dutch_addresses_shape_28992.zip',
            'source_srs': 'EPSG:28992',
            'target_srs': 'EPSG:4326',
            'source_capabilities': {
                'paging': True
            },
        },
        'id_field': 'id'
    }


def test_get_fields_4326(config_shapefile_4326):
    """Testing field types"""
    p = OGRProvider(config_shapefile_4326)
    results = p.get_fields()
    assert results['straatnaam'] == 'string'
    assert results['huisnummer'] == 'string'


def test_get_28992(config_shapefile_28992):
    """Testing query for a specific object"""
    p = OGRProvider(config_shapefile_28992)
    result = p.get('inspireadressen.1747652')
    assert result['id'] == 'inspireadressen.1747652'
    assert 'Mosselsepad' in result['properties']['straatnaam']


def test_get_4326(config_shapefile_4326):
    """Testing query for a specific object"""
    p = OGRProvider(config_shapefile_4326)
    result = p.get('inspireadressen.1747652')
    assert result['id'] == 'inspireadressen.1747652'
    assert 'Mosselsepad' in result['properties']['straatnaam']


def test_query_hits_28992(config_shapefile_28992):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_shapefile_28992)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) is 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    assert hits == 2481


def test_query_hits_4326(config_shapefile_4326):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_shapefile_4326)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) is 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    assert hits == 2481


def test_query_bbox_hits_4326(config_shapefile_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_4326)
    # feature_collection = p.query(
    # bbox=[120000, 480000, 124000, 487000], resulttype='hits')
    feature_collection = p.query(
        bbox=[5.763409, 52.060197, 5.769256, 52.061976], resulttype='hits')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) is 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    print('hits={}'.format(hits))
    assert hits is 1


def test_query_bbox_hits_28992(config_shapefile_28992):
    """Testing query for a valid JSON object with geometry, single address"""

    p = OGRProvider(config_shapefile_28992)
    # feature_collection = p.query(
    #     bbox=(180800, 452500, 181200, 452700), resulttype='hits')
    feature_collection = p.query(
        bbox=[5.763409, 52.060197, 5.769256, 52.061976], resulttype='hits')

    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) is 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    print('hits={}'.format(hits))
    assert hits is 1


def test_query_bbox_28992(config_shapefile_28992):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_28992)
    # feature_collection = p.query(
    #     bbox=[180800, 452500, 181200, 452700], resulttype='results')
    feature_collection = p.query(
        bbox=(5.763409, 52.060197, 5.769256, 52.061976), resulttype='results')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) == 1
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None
    assert properties['straatnaam'] == 'Planken Wambuisweg'


def test_query_bbox_4326(config_shapefile_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_4326)
    # feature_collection = p.query(
    #     bbox=[180800, 452500, 181200, 452700], resulttype='results')
    feature_collection = p.query(
        bbox=(5.763409, 52.060197, 5.769256, 52.061976), resulttype='results')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) == 1
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None
    assert properties['straatnaam'] == 'Planken Wambuisweg'


def test_query_with_limit_28992(config_shapefile_28992):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_28992)
    feature_collection = p.query(limit=2, resulttype='results')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) == 2
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None


def test_query_with_limit_4326(config_shapefile_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_shapefile_4326)
    feature_collection = p.query(limit=5, resulttype='results')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) == 5
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None
