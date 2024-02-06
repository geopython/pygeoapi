# =================================================================
#
# Authors: Just van den Broecke <justb4@gmail.com>
# Authors: Francesco Bartoli <xbartolone@gmail.com>
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2019 Just van den Broecke
# Copyright (c) 2020 Francesco Bartoli
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

from pygeoapi.provider.base import (ProviderItemNotFoundError)
from pygeoapi.provider.ogr import OGRProvider


LOGGER = logging.getLogger(__name__)


# we don't run these tests by default because they depend on
# external servers which is slow and sometimes fails
pytest.skip("skipping live tests", allow_module_level=True)


@pytest.fixture()
def config_MapServer_WFS_cities():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'WFS',
            'source': 'WFS:https://demo.mapserver.org/cgi-bin/wfs',
            # 'source_srs': 'EPSG:4326',
            # 'target_srs': 'EPSG:4326',
            'source_capabilities': {
                'paging': True
            },
            'source_options': {
                'OGR_WFS_VERSION': '2.0.0',
                'OGR_WFS_LOAD_MULTIPLE_LAYER_DEFN': 'NO'
            },
            'gdal_ogr_options': {
                'GDAL_CACHEMAX': '64',
                'GDAL_HTTP_VERSION': '1.1',
                'GDAL_HTTP_UNSAFESSL': 'YES',
                # 'GDAL_HTTP_PROXY': (optional proxy)
                # 'GDAL_PROXY_AUTH': (optional auth for remote WFS)
                'CPL_DEBUG': 'NO'
            },
        },
        'id_field': 'gml_id',
        'layer': 'cities'
    }


@pytest.fixture()
def config_MapServer_WFS_continents():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'WFS',
            'source': 'WFS:https://demo.mapserver.org/cgi-bin/wfs',
            # 'source_srs': 'EPSG:4326',
            # 'target_srs': 'EPSG:4326',
            'source_capabilities': {
                'paging': True
            },
            'source_options': {
                'OGR_WFS_VERSION': '2.0.0',
                'OGR_WFS_LOAD_MULTIPLE_LAYER_DEFN': 'NO'
            },
            'gdal_ogr_options': {
                'GDAL_CACHEMAX': '64',
                'GDAL_HTTP_VERSION': '1.1',
                'GDAL_HTTP_UNSAFESSL': 'YES',
                # 'GDAL_HTTP_PROXY': (optional proxy)
                # 'GDAL_PROXY_AUTH': (optional auth for remote WFS)
                'CPL_DEBUG': 'NO'
            },
        },
        'id_field': 'gml_id',
        'layer': 'continents'
    }


@pytest.fixture()
def config_geosol_gs_WFS():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'WFS',
            'source':
                'WFS:https://gs-stable.geosolutionsgroup.com/geoserver/wfs?',
            # 'source_srs': 'EPSG:32632',
            # 'target_srs': 'EPSG:4326',
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
        'crs': [
             'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
             'http://www.opengis.net/def/crs/EPSG/0/32632'
         ],
        'storageCRS': 'http://www.opengis.net/def/crs/EPSG/0/32632',
        'id_field': 'gml_id',
        'layer': 'unesco:Unesco_point',
    }


@pytest.fixture()
def config_geonode_gs_WFS():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'WFS',
            'source':
                'WFS:https://geonode.wfp.org/geoserver/wfs',
            # 'source_srs': 'EPSG:4326',
            # 'target_srs': 'EPSG:4326',
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


def test_get_fields_gs(config_MapServer_WFS_continents):
    """Testing field types"""

    p = OGRProvider(config_MapServer_WFS_continents)
    results = p.get_fields()
    assert results['NA2DESC']['type'] == 'string'
    assert results['NA3DESC']['type'] == 'string'


def test_get_ms(config_MapServer_WFS_cities):
    """Testing query for a specific object"""

    p = OGRProvider(config_MapServer_WFS_cities)
    result = p.get('cities.8338')
    assert result['id'] == 'cities.8338'
    assert 'Buenos Aires' in result['properties']['NAME']


def test_get_geosol_gs(config_geosol_gs_WFS):
    """Testing query for a specific object"""

    p = OGRProvider(config_geosol_gs_WFS)
    result = p.get('Unesco_point.123')
    assert result['id'] == 'Unesco_point.123'
    assert 'Centro storico di San Gimignano' in result['properties']['sito']


def test_get_gs(config_MapServer_WFS_continents):
    """Testing query for a specific object"""

    p = OGRProvider(config_MapServer_WFS_continents)
    result = p.get('continents.23774')
    assert result['id'] == 'continents.23774'
    assert result['properties']['NA2DESC'] == 'Canada'
    assert result['properties']['NA3DESC'] == 'North America'


# def test_gs_not_getting_gml_id(config_geonode_gs_WFS):
#     """Testing query not returning gml_id for a specific object"""
#
#     p = OGRProvider(config_geonode_gs_WFS)
#     assert p.open_options is not None
#     result = p.get_fields()
#     assert result.get('gml_id') is None
#
#
# def test_gs_force_getting_gml_id(config_geonode_gs_WFS):
#     """Testing query forcing to return gml_id for a specific object"""
#
#     p = OGRProvider(config_geonode_gs_WFS)
#     assert p.open_options is not None
#     p.open_options['EXPOSE_GML_ID'] = 'YES'
#     result = p.get_fields()
#     assert result.get('gml_id')
#
#
# def test_get_gs_with_geojson_output_too_complex_raise_exception(
#     config_geonode_gs_WFS
# ):
#     """Testing query for a specific object with too complex geojson"""
#     p = OGRProvider(config_geonode_gs_WFS)
#     assert p.open_options.get('URL') is None
#     p.open_options[
#         'URL'] = 'https://geonode.wfp.org/geoserver/wfs?outputformat=json'
#     with pytest.raises(ProviderQueryError):
#         p.get(272)


def test_get_gs_not_existing_feature_raise_exception(
    config_MapServer_WFS_continents
):
    """Testing query for a not existing object"""
    p = OGRProvider(config_MapServer_WFS_continents)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_get_ms_not_existing_feature_raise_exception(
    config_MapServer_WFS_cities
):
    """Testing query for a not existing object"""
    p = OGRProvider(config_MapServer_WFS_cities)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_query_hits_ms(config_MapServer_WFS_cities):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_MapServer_WFS_cities)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits > 5000


def test_query_hits_geosol_gs(config_geosol_gs_WFS):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_geosol_gs_WFS)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits == 186


# OK, but backend WFS takes too much time....
# def test_query_hits_gs(config_MapServer_WFS_continents):
#     """Testing query on entire collection for hits"""
#
#     p = OGRProvider(config_MapServer_WFS_continents)
#     feature_collection = p.query(resulttype='hits')
#     assert feature_collection.get('type') == 'FeatureCollection'
#     features = feature_collection.get('features')
#     assert len(features) == 0
#     hits = feature_collection.get('numberMatched')
#     assert hits is not None
#     assert hits > 8000000


def test_query_bbox_hits_ms(config_MapServer_WFS_cities):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS_cities)
    feature_collection = p.query(
        bbox=[-47, -24, -45, -22], resulttype='hits')

    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits > 1


def test_query_bbox_hits_gs(config_MapServer_WFS_continents):
    """Testing query for a valid JSON object with geometry, single address"""

    p = OGRProvider(config_MapServer_WFS_continents)
    feature_collection = p.query(bbox=[-61, 46, -60, 47], resulttype='hits')

    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits == 3


def test_query_bbox_hits_geosol_gs(config_geosol_gs_WFS):
    """Testing query for a valid JSON object with geometry, single address"""

    p = OGRProvider(config_geosol_gs_WFS)
    feature_collection = p.query(
        bbox=(957858, 4561555, 957862, 4561557), resulttype='hits')
    # feature_collection = p.query(bbox=(
    # 5.763409, 52.060197, 5.769256, 52.061976), resulttype='hits')

    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits == 1


def test_query_bbox_ms(config_MapServer_WFS_cities):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS_cities)
    feature_collection = p.query(
        bbox=[4.874016, 52.306852, 4.932020, 52.370004], resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) > 0
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    geometry = feature.get('geometry')
    assert geometry is not None


def test_query_bbox_gs(config_MapServer_WFS_continents):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS_continents)
    feature_collection = p.query(bbox=(5, 52, 6, 53), resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 4
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    geometry = feature.get('geometry')
    assert geometry is not None
    assert properties['NA2DESC'] == 'Netherlands'
    assert properties['NA3DESC'] == 'Europe'


def test_query_bbox_geosol_gs(config_geosol_gs_WFS):
    """Testing query for a valid JSON object with geometry
       <wfs:member>
        <unesco:Unesco_point gml:id="Unesco_point.59">
            <gml:boundedBy>
                <gml:Envelope srsName="urn:ogc:def:crs:EPSG::32632"
                srsDimension="2">
                    <gml:lowerCorner>957860.4622 4561556.7274</gml:lowerCorner>
                    <gml:upperCorner>957860.4622 4561556.7274</gml:upperCorner>
                </gml:Envelope>
            </gml:boundedBy>
            <unesco:the_geom>
                <gml:Point srsName="urn:ogc:def:crs:EPSG::32632"
                srsDimension="2" gml:id="Unesco_point.59.the_geom">
                    <gml:pos>957860.4622 4561556.7274</gml:pos>
                </gml:Point>
            </unesco:the_geom>
            <unesco:cod_unesco>IT_174</unesco:cod_unesco>
            <unesco:sito>Centro storico di Firenze</unesco:sito>
            <unesco:seriale>0</unesco:seriale>
            <unesco:tipo_area>sito</unesco:tipo_area>
        </unesco:Unesco_point>
    </wfs:member>

    """

    p = OGRProvider(config_geosol_gs_WFS)
    feature_collection = p.query(
        bbox=(957858, 4561555, 957862, 4561557),
        resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 1
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    assert properties['sito'] == 'Centro storico di Firenze'
    geometry = feature.get('geometry')
    assert geometry is not None


def test_query_with_limit_ms(config_MapServer_WFS_cities):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS_cities)
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


def test_query_with_offset(config_MapServer_WFS_cities):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_MapServer_WFS_cities)
    feature_collection = p.query(offset=20, limit=5, resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 5
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    assert feature['id'] == 'cities.411'
    assert '6610764' in properties['POPULATION']
    geometry = feature.get('geometry')
    assert geometry is not None


def test_query_with_property_filtering_gs(config_MapServer_WFS_continents):
    """Testing query with property filtering on geoserver backend"""

    p = OGRProvider(config_MapServer_WFS_continents)

    feature_collection = p.query(
        properties=[
            ('NA2DESC', 'Greece'),
            ('NA3DESC', 'Europe'),
        ]
    )

    for feature in feature_collection['features']:
        assert 'properties' in feature
        assert 'NA2DESC' in feature['properties']
        assert 'NA3DESC' in feature['properties']

        assert feature['properties']['NA2DESC'] == 'Greece'
        assert feature['properties']['NA3DESC'] == 'Europe'


def test_query_with_property_filtering_ms(config_MapServer_WFS_cities):
    """Testing query with property filtering on mapserver backend"""

    p = OGRProvider(config_MapServer_WFS_cities)

    feature_collection = p.query(
        properties=[
            ('NAME', 'Seoul'),
        ]
    )

    assert len(feature_collection['features']) == 1

    feature = feature_collection['features'][0]

    assert 'properties' in feature
    assert 'NAME' in feature['properties']
    assert feature['properties']['NAME'] == 'Seoul'
