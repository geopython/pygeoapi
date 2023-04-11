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

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.ogr import OGRProvider


LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def config_poi_portugal():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'GPKG',
            'source': './tests/data/poi_portugal.gpkg',
            # 'source_srs': 'EPSG:4326',
            # 'target_srs': 'EPSG:4326',
            'source_capabilities': {
                'paging': True
            },
        },
        'id_field': 'osm_id',
        'layer': 'poi_portugal'
    }


def test_query(config_poi_portugal):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_poi_portugal)
    feature_collection = p.query()
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert features is not None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    geometry = feature.get('geometry')
    assert geometry is not None


def test_get(config_poi_portugal):
    p = OGRProvider(config_poi_portugal)
    result = p.get(536678593)
    assert result['id'] == 536678593
    assert 'cafe' in result['properties']['fclass']


def test_get_not_existing_feature_raise_exception(
    config_poi_portugal
):
    """Testing query for a not existing object"""
    p = OGRProvider(config_poi_portugal)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


# Testing with GeoPackage files with identical features
# (all 2481 addresses in Otterlo Netherlands)
# in different projections.

@pytest.fixture()
def config_gpkg_4326():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'GPKG',
            'source':
                './tests/data/dutch_addresses_4326.gpkg',
            # 'source_srs': 'EPSG:4326',
            # 'target_srs': 'EPSG:4326',
            'source_capabilities': {
                'paging': True
            },
        },
        'id_field': 'id',
        'layer': 'OGRGeoJSON'
    }


# Note that this Shapefile is zipped, as OGR supports /vsizip/!
@pytest.fixture()
def config_gpkg_28992():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'GPKG',
            'source':
                './tests/data/dutch_addresses_28992.gpkg',
            # 'source_srs': 'EPSG:28992',
            # 'target_srs': 'EPSG:4326',
            'source_capabilities': {
                'paging': True
            },
        },
        'crs': [
             'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
             'http://www.opengis.net/def/crs/EPSG/0/28992'
         ],
        'storageCRS': 'http://www.opengis.net/def/crs/EPSG/0/28992',
        'id_field': 'id',
        'layer': 'OGRGeoJSON'
    }


def test_get_fields_4326(config_gpkg_4326):
    """Testing field types"""
    p = OGRProvider(config_gpkg_4326)
    results = p.get_fields()
    assert results['straatnaam']['type'] == 'string'
    assert results['huisnummer']['type'] == 'string'


def test_get_28992(config_gpkg_28992):
    """Testing query for a specific object"""
    p = OGRProvider(config_gpkg_28992)
    result = p.get('inspireadressen.1747652')
    assert result['id'] == 'inspireadressen.1747652'
    assert 'Mosselsepad' in result['properties']['straatnaam']


def test_get_4326(config_gpkg_4326):
    """Testing query for a specific object"""
    p = OGRProvider(config_gpkg_4326)
    result = p.get('inspireadressen.1747652')
    assert result['id'] == 'inspireadressen.1747652'
    assert 'Mosselsepad' in result['properties']['straatnaam']


def test_query_hits_28992(config_gpkg_28992):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_gpkg_28992)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits == 2481


def test_query_hits_4326(config_gpkg_4326):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_gpkg_4326)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits == 2481


def test_query_bbox_hits_4326(config_gpkg_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_gpkg_4326)
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


def test_query_bbox_hits_28992(config_gpkg_28992):
    """Testing query for a valid JSON object with geometry, single address"""

    p = OGRProvider(config_gpkg_28992)
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


def test_query_bbox_28992(config_gpkg_28992):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_gpkg_28992)
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


def test_query_bbox_4326(config_gpkg_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_gpkg_4326)
    # feature_collection = p.query(
    #     bbox=[180800, 452500, 181200, 452700], resulttype='results')
    feature_collection = p.query(
        bbox=(5.763409, 52.060197, 5.769256, 52.061976), resulttype='results')
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


def test_query_with_limit_28992(config_gpkg_28992):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_gpkg_28992)
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


def test_query_with_limit_4326(config_gpkg_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_gpkg_4326)
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


def test_query_with_offset_28992(config_gpkg_28992):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_gpkg_28992)
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


def test_query_with_offset_4326(config_gpkg_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_gpkg_4326)
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


def test_query_bbox_with_offset_28992(config_gpkg_28992):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_gpkg_28992)
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


def test_query_bbox_with_offset_4326(config_gpkg_4326):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_gpkg_4326)
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


def test_query_with_property_filtering(config_gpkg_4326):
    """Testing query with property filtering"""

    p = OGRProvider(config_gpkg_4326)

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
