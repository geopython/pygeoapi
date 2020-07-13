# =================================================================
#
# Authors: Just van den Broecke <justb4@gmail.com>
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2019 Just van den Broecke
# Copyright (c) 2020 Francesco Bartoli
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

from pygeoapi.provider.base import (
    ProviderQueryError, ProviderItemNotFoundError)
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


@pytest.fixture()
def config_geonode_gs_WFS():
    return {
        'name': 'OGR',
        'data': {
            'source_type': 'WFS',
            'source':
                'WFS:https://geonode.wfp.org/geoserver/wfs',
            'source_srs': 'EPSG:4326',
            'target_srs': 'EPSG:4326',
            'source_capabilities': {
                'paging': True
            },
            'source_options': {
                'OGR_WFS_LOAD_MULTIPLE_LAYER_DEFN': 'NO'
            },
            'open_options': {
                'EXPOSE_GML_ID': 'NO',
                # Comment the line below cause it converts
                # automatically MULTISURFACE to MULTIPOLYGON
                # geometries server side
                # 'URL': 'https://geonode.wfp.org/geoserver/wfs?\
                # outputformat=json'
            },
            'gdal_ogr_options': {
                'EMPTY_AS_NULL': 'NO',
                'GDAL_CACHEMAX': '64',
                'CPL_DEBUG': 'NO',
                'GDAL_HTTP_UNSAFESSL': 'YES'
            },
        },
        'id_field': 'adm0_id',
        'layer': 'geonode:wld_bnd_adm0'
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
    assert '01' in result['properties']['station']


def test_get_geosol_gs(config_geosol_gs_WFS):
    """Testing query for a specific object"""

    p = OGRProvider(config_geosol_gs_WFS)
    result = p.get('Unesco_point.123')
    assert result['id'] == 'Unesco_point.123'
    assert 'Centro storico di San Gimignano' in result['properties']['sito']


def test_get_gs(config_GeoServer_WFS):
    """Testing query for a specific object"""

    p = OGRProvider(config_GeoServer_WFS)
    result = p.get('inspireadressen.1747652')
    assert result['id'] == 'inspireadressen.1747652'
    assert 'Mosselsepad' in result['properties']['straatnaam']


def test_gs_not_getting_gml_id(config_geonode_gs_WFS):
    """Testing query not returning gml_id for a specific object"""

    p = OGRProvider(config_geonode_gs_WFS)
    assert p.open_options is not None
    result = p.get_fields()
    assert result.get('gml_id') is None


def test_gs_force_getting_gml_id(config_geonode_gs_WFS):
    """Testing query forcing to return gml_id for a specific object"""

    p = OGRProvider(config_geonode_gs_WFS)
    assert p.open_options is not None
    p.open_options['EXPOSE_GML_ID'] = 'YES'
    result = p.get_fields()
    assert result.get('gml_id')


def test_get_gs_with_geojson_output_too_complex_raise_exception(
    config_geonode_gs_WFS
):
    """Testing query for a specific object with too complex geojson"""
    p = OGRProvider(config_geonode_gs_WFS)
    assert p.open_options.get('URL') is None
    p.open_options[
        'URL'] = 'https://geonode.wfp.org/geoserver/wfs?outputformat=json'
    with pytest.raises(ProviderQueryError):
        p.get(272)


def test_get_gs_not_existing_feature_raise_exception(
    config_GeoServer_WFS
):
    """Testing query for a not existing object"""
    p = OGRProvider(config_GeoServer_WFS)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_get_ms_not_existing_feature_raise_exception(
    config_MapServer_WFS
):
    """Testing query for a not existing object"""
    p = OGRProvider(config_MapServer_WFS)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_query_hits_ms(config_MapServer_WFS):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_MapServer_WFS)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) == 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    assert hits > 5000


def test_query_hits_geosol_gs(config_geosol_gs_WFS):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_geosol_gs_WFS)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) == 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    assert hits == 186


# OK, but backend WFS takes too much time....
# def test_query_hits_gs(config_GeoServer_WFS):
#     """Testing query on entire collection for hits"""
#
#     p = OGRProvider(config_GeoServer_WFS)
#     feature_collection = p.query(resulttype='hits')
#     assert feature_collection.get('type', None) == 'FeatureCollection'
#     features = feature_collection.get('features', None)
#     assert len(features) == 0
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
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) == 0
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

    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) == 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    print('hits={}'.format(hits))
    assert hits == 1


def test_query_bbox_hits_geosol_gs(config_geosol_gs_WFS):
    """Testing query for a valid JSON object with geometry, single address"""

    p = OGRProvider(config_geosol_gs_WFS)
    feature_collection = p.query(
        bbox=(681417.0, 4849032.0, 681417.3, 4849032.3), resulttype='hits')
    # feature_collection = p.query(bbox=(
    # 5.763409, 52.060197, 5.769256, 52.061976), resulttype='hits')

    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) == 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is not None
    print('hits={}'.format(hits))
    assert hits == 1


def test_query_bbox_ms(config_MapServer_WFS):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS)
    # feature_collection = p.query(
    # bbox=[120000, 480000, 124000, 487000], resulttype='results')
    feature_collection = p.query(
        bbox=[4.874016, 52.306852, 4.932020, 52.370004], resulttype='results')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) > 0
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    geometry = feature.get('geometry', None)
    assert geometry is not None


def test_query_bbox_gs(config_GeoServer_WFS):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_GeoServer_WFS)
    feature_collection = p.query(
        bbox=[180800, 452500, 181200, 452700], resulttype='results')
    # feature_collection = p.query(
    # bbox=(5.763409, 52.060197, 5.769256, 52.061976), resulttype='results')
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


def test_query_bbox_geosol_gs(config_geosol_gs_WFS):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_geosol_gs_WFS)
    # feature_collection = p.query(
    # bbox=[120000, 480000, 124000, 487000], resulttype='results')
    feature_collection = p.query(
        bbox=(681417.0, 4849032.0, 681417.3, 4849032.3),
        resulttype='results')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) == 1
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    assert properties['sito'] == 'Centro storico di Firenze'
    geometry = feature.get('geometry', None)
    assert geometry is not None


def test_query_with_limit_ms(config_MapServer_WFS):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS)
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


def test_query_with_startindex(config_MapServer_WFS):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS)
    feature_collection = p.query(startindex=20, limit=5, resulttype='results')
    assert feature_collection.get('type', None) == 'FeatureCollection'
    features = feature_collection.get('features', None)
    assert len(features) == 5
    hits = feature_collection.get('numberMatched', None)
    assert hits is None
    feature = features[0]
    properties = feature.get('properties', None)
    assert properties is not None
    assert feature['id'] == 'stations.21'
    assert '101696.68' in properties['xrd']
    geometry = feature.get('geometry', None)
    assert geometry is not None


def test_query_with_property_filtering_gs(config_GeoServer_WFS):
    """Testing query with property filtering on geoserver backend"""

    p = OGRProvider(config_GeoServer_WFS)

    feature_collection = p.query(
        properties=[
            ('postcode', '9711LM'),
            ('huisnummer', 106),
        ]
    )

    for feature in feature_collection['features']:
        assert 'properties' in feature
        assert 'postcode' in feature['properties']
        assert 'huisnummer' in feature['properties']

        assert feature['properties']['postcode'] == '9711LM'
        assert feature['properties']['huisnummer'] == 106


def test_query_with_property_filtering_ms(config_MapServer_WFS):
    """Testing query with property filtering on mapserver backend"""

    p = OGRProvider(config_MapServer_WFS)

    feature_collection = p.query(
        properties=[
            ('station', '21'),
        ]
    )

    for feature in feature_collection['features']:
        assert 'properties' in feature
        assert 'station' in feature['properties']

        assert feature['properties']['station'] == '21'

#
# # OK, but backend GeoServer PDOK WFS takes too much time....
# # def test_query_with_limit_gs(config_GeoServer_WFS):
# #
# #     p = OGRProvider(config_GeoServer_WFS)
# #     feature_collection = p.query(limit=5, resulttype='results')
# #     assert feature_collection.get('type', None) == 'FeatureCollection'
# #     features = feature_collection.get('features', None)
# #     assert len(features) == 5
# #     hits = feature_collection.get('numberMatched', None)
# #     assert hits is None
# #     feature = features[0]
# #     properties = feature.get('properties', None)
# #     assert properties is not None
# #     geometry = feature.get('geometry', None)
# #     assert geometry is not None
