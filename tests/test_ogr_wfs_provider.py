# Needs to be run like: python3 -m pytest

import logging

import pytest
from pygeoapi.provider.ogr import OGRProvider

LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def config_MapServer_WFS():
    return {
        'name': 'OGR',
        'data': {
            'source_type': 'WFS',
            'source': 'WFS:http://geodata.nationaalgeoregister.nl/rdinfo/wfs?',
            'source_srs': 'EPSG:28992',
            'target_srs': 'EPSG:4326',
            'source_capabilities': {
                'paging': True
            },
            'source_options': {
                'OGR_WFS_LOAD_MULTIPLE_LAYER_DEFN': 'NO'
            },
            'gdal_ogr_options': {

                'GDAL_CACHEMAX': '64',
                # 'GDAL_HTTP_PROXY': (optional proxy)
                # 'GDAL_PROXY_AUTH': (optional auth for remote WFS)
                'CPL_DEBUG': 'NO'
            },
        },
        'id_field': 'gml_id',
        'layer': 'rdinfo:stations'
    }


@pytest.fixture()
def config_GeoServer_WFS():
    return {
        'name': 'OGR',
        'data': {
            'source_type': 'WFS',
            'source':
                'WFS:https://geodata.nationaalgeoregister.nl'
                + '/inspireadressen/wfs?',
            'source_srs': 'EPSG:28992',
            'target_srs': 'EPSG:28992',
            'source_capabilities': {
                'paging': True
            },
            'source_options': {
                'OGR_WFS_LOAD_MULTIPLE_LAYER_DEFN': 'NO'
            },
            'gdal_ogr_options': {

                'GDAL_CACHEMAX': '64',
                # 'GDAL_HTTP_PROXY': (optional proxy)
                # 'GDAL_PROXY_AUTH': (optional auth for remote WFS)
                'CPL_DEBUG': 'NO'
            },
        },
        'id_field': 'gml_id',
        'layer': 'inspireadressen:inspireadressen'
    }


@pytest.fixture()
def config_geosol_gs_WFS():
    return {
        'name': 'OGR',
        'data': {
            'source_type': 'WFS',
            'source':
                'WFS:https://demo.geo-solutions.it/geoserver/wfs?',
            'source_srs': 'EPSG:32632',
            'target_srs': 'EPSG:4326',
            'source_capabilities': {
                'paging': True
            },
            'source_options': {
                'OGR_WFS_LOAD_MULTIPLE_LAYER_DEFN': 'NO'
            },
            'gdal_ogr_options': {

                'GDAL_CACHEMAX': '64',
                # 'GDAL_HTTP_PROXY': (optional proxy)
                # 'GDAL_PROXY_AUTH': (optional auth for remote WFS)
                'CPL_DEBUG': 'NO'
            },
        },
        'id_field': 'gml_id',
        'layer': 'unesco:Unesco_point'
    }


def test_get_fields_gs(config_GeoServer_WFS):
    """Testing field types"""
    p = OGRProvider(config_GeoServer_WFS)
    results = p.get_fields()
    assert results['straatnaam'] == 'string'
    assert results['huisnummer'] == 'integer'


def test_get_ms(config_MapServer_WFS):
    """Testing query for a specific object"""
    p = OGRProvider(config_MapServer_WFS)
    result = p.get('stations.4403')
    assert result['id'] == 'stations.4403'
    assert "01" in result['properties']['station']


def test_get_geosol_gs(config_geosol_gs_WFS):
    """Testing query for a specific object"""
    p = OGRProvider(config_geosol_gs_WFS)
    result = p.get('Unesco_point.123')
    assert result['id'] == 'Unesco_point.123'
    assert "Centro storico di San Gimignano" in result['properties']['sito']


def test_get_gs(config_GeoServer_WFS):
    """Testing query for a specific object"""
    p = OGRProvider(config_GeoServer_WFS)
    result = p.get('inspireadressen.1747652')
    assert result['id'] == 'inspireadressen.1747652'
    assert "Mosselsepad" in result['properties']['straatnaam']


def test_query_hits_ms(config_MapServer_WFS):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_MapServer_WFS)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type', None) == "FeatureCollection"
    features = feature_collection.get('features', None)
    assert len(features) is 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    assert hits > 5000


def test_query_hits_geosol_gs(config_geosol_gs_WFS):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_geosol_gs_WFS)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type', None) == "FeatureCollection"
    features = feature_collection.get('features', None)
    assert len(features) is 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    assert hits == 186


# OK, but backend WFS takes too much time....
# def test_query_hits_gs(config_GeoServer_WFS):
#     """Testing query on entire collection for hits"""
#
#     p = OGRProvider(config_GeoServer_WFS)
#     feature_collection = p.query(resulttype='hits')
#     assert feature_collection.get('type', None) == "FeatureCollection"
#     features = feature_collection.get('features', None)
#     assert len(features) is 0
#     hits = feature_collection.get('numberMatched', None)
#     assert hits is not None
#     assert hits > 8000000


def test_query_bbox_hits_ms(config_MapServer_WFS):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS)
    # feature_collection = p.query(
    # bbox=[120000, 480000, 124000, 487000], resulttype='hits')
    feature_collection = p.query(
        bbox=[4.874016, 52.306852, 4.932020, 52.370004], resulttype='hits')
    assert feature_collection.get('type', None) == "FeatureCollection"
    features = feature_collection.get('features', None)
    assert len(features) is 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    print('hits={}'.format(hits))
    assert hits > 1


def test_query_bbox_hits_gs(config_GeoServer_WFS):
    """Testing query for a valid JSON object with geometry, single address"""

    p = OGRProvider(config_GeoServer_WFS)
    feature_collection = p.query(
        bbox=(180800, 452500, 181200, 452700), resulttype='hits')
    # feature_collection = p.query(bbox=(
    # 5.763409, 52.060197, 5.769256, 52.061976), resulttype='hits')

    assert feature_collection.get('type', None) == "FeatureCollection"
    features = feature_collection.get('features', None)
    assert len(features) is 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    print('hits={}'.format(hits))
    assert hits is 1


def test_query_bbox_hits_geosol_gs(config_geosol_gs_WFS):
    """Testing query for a valid JSON object with geometry, single address"""

    p = OGRProvider(config_geosol_gs_WFS)
    feature_collection = p.query(
        bbox=(681417.0, 4849032.0, 681417.3, 4849032.3), resulttype='hits')
    # feature_collection = p.query(bbox=(
    # 5.763409, 52.060197, 5.769256, 52.061976), resulttype='hits')

    assert feature_collection.get('type', None) == "FeatureCollection"
    features = feature_collection.get('features', None)
    assert len(features) is 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    print('hits={}'.format(hits))
    assert hits is 1


def test_query_bbox_ms(config_MapServer_WFS):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS)
    # feature_collection = p.query(
    # bbox=[120000, 480000, 124000, 487000], resulttype='results')
    feature_collection = p.query(
        bbox=[4.874016, 52.306852, 4.932020, 52.370004], resulttype='results')
    assert feature_collection.get('type', None) == "FeatureCollection"
    features = feature_collection.get('features', None)
    assert len(features) > 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get("properties", None)
    assert properties is not None
    geometry = feature.get("geometry", None)
    assert geometry is not None


def test_query_bbox_gs(config_GeoServer_WFS):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_GeoServer_WFS)
    feature_collection = p.query(
        bbox=[180800, 452500, 181200, 452700], resulttype='results')
    # feature_collection = p.query(
    # bbox=(5.763409, 52.060197, 5.769256, 52.061976), resulttype='results')
    assert feature_collection.get('type', None) == "FeatureCollection"
    features = feature_collection.get('features', None)
    assert len(features) == 1
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get("properties", None)
    assert properties is not None
    geometry = feature.get("geometry", None)
    assert geometry is not None
    assert properties['straatnaam'] == 'Planken Wambuisweg'


def test_query_bbox_geosol_gs(config_geosol_gs_WFS):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_geosol_gs_WFS)
    # feature_collection = p.query(
    # bbox=[120000, 480000, 124000, 487000], resulttype='results')
    feature_collection = p.query(
        bbox=(681417.0, 4849032.0, 681417.3, 4849032.3),
        resulttype='results')
    assert feature_collection.get('type', None) == "FeatureCollection"
    features = feature_collection.get('features', None)
    assert len(features) == 1
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get("properties", None)
    assert properties is not None
    assert properties['sito'] == 'Centro storico di Firenze'
    geometry = feature.get("geometry", None)
    assert geometry is not None


def test_query_with_limit_ms(config_MapServer_WFS):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS)
    feature_collection = p.query(limit=2, resulttype='results')
    assert feature_collection.get('type', None) == "FeatureCollection"
    features = feature_collection.get('features', None)
    assert len(features) == 2
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get("properties", None)
    assert properties is not None
    geometry = feature.get("geometry", None)
    assert geometry is not None


def test_query_with_startindex(config_MapServer_WFS):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS)
    feature_collection = p.query(startindex=20, limit=5, resulttype='results')
    assert feature_collection.get('type', None) == "FeatureCollection"
    features = feature_collection.get('features', None)
    assert len(features) == 5
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get("properties", None)
    assert properties is not None
    assert feature['id'] == 'stations.21'
    assert "101696.68" in properties['xrd']
    geometry = feature.get("geometry", None)
    assert geometry is not None
#
# # OK, but backend GeoServer PDOK WFS takes too much time....
# # def test_query_with_limit_gs(config_GeoServer_WFS):
# #     """Testing query for a valid JSON object with geometry"""
# #
# #     p = OGRProvider(config_GeoServer_WFS)
# #     feature_collection = p.query(limit=5, resulttype='results')
# #     assert feature_collection.get('type', None) == "FeatureCollection"
# #     features = feature_collection.get('features', None)
# #     assert len(features) == 5
# #     hits = feature_collection.get('numberMatched', None)
# #     assert hits is None
# #     feature = features[0]
# #     properties = feature.get("properties", None)
# #     assert properties is not None
# #     geometry = feature.get("geometry", None)
# #     assert geometry is not None
