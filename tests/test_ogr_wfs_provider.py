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
from unittest import mock

import pytest

from pygeoapi.provider.base import (ProviderItemNotFoundError)
from pygeoapi.provider.ogr import OGRProvider


LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def config_MapServer_WFS_cities():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'WFS',
            'source': 'WFS:https://www.example.com/wfs',
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
def mock_ogr_layer():
    # NOTE; this is a bit brittle and might break on many changes in the actual
    #       code. However updating this fixture should be enough to fix the
    #       tests.
    with mock.patch("pygeoapi.provider.ogr.osgeo_ogr") as ogr:
        layer = ogr.GetDriverByName().Open().GetLayerByName()
        yield layer


def test_get_fields(config_MapServer_WFS_cities, mock_ogr_layer):
    """Testing field types"""
    field_defn = mock_ogr_layer.GetLayerDefn().GetFieldDefn()
    field_defn.GetName.return_value = "NA2DESC"
    field_defn.GetFieldTypeName.return_value = "string"

    p = OGRProvider(config_MapServer_WFS_cities)
    results = p.get_fields()
    assert results['NA2DESC']['type'] == 'string'


def test_get(config_MapServer_WFS_cities, mock_ogr_layer):
    """Testing query for a specific object"""
    feature = mock_ogr_layer.GetNextFeature()
    feature.items().values.return_value = ['cities.8338']
    feature.ExportToJson.return_value = {'id': 'cities.8338'}

    p = OGRProvider(config_MapServer_WFS_cities)
    result = p.get('cities.8338')
    assert result['id'] == 'cities.8338'


def test_get_not_existing_feature_raise_exception(
    config_MapServer_WFS_cities, mock_ogr_layer,
):
    """Testing query for a not existing object"""
    mock_ogr_layer.GetFeatureCount.return_value = 0

    p = OGRProvider(config_MapServer_WFS_cities)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_query_hits(config_MapServer_WFS_cities, mock_ogr_layer):
    """Testing query on entire collection for hits"""
    mock_ogr_layer.GetFeatureCount.return_value = 5001

    p = OGRProvider(config_MapServer_WFS_cities)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits > 5000


def test_query_bbox_hits(config_MapServer_WFS_cities, mock_ogr_layer):
    """Testing query for a valid JSON object with geometry"""
    mock_ogr_layer.GetFeatureCount.return_value = 2

    p = OGRProvider(config_MapServer_WFS_cities)
    feature_collection = p.query(
        bbox=[-47, -24, -45, -22], resulttype='hits')

    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits > 1

    mock_ogr_layer.SetSpatialFilter.assert_called()


def test_query_bboxs(config_MapServer_WFS_cities, mock_ogr_layer):
    """Testing query for a valid JSON object with geometry"""
    mock_ogr_layer.GetFeatureCount.return_value = 2

    p = OGRProvider(config_MapServer_WFS_cities)
    feature_collection = p.query(
        bbox=[4.874016, 52.306852, 4.932020, 52.370004], resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) > 0
    hits = feature_collection.get('numberMatched')
    assert hits is None


def test_query_with_property_filtering(
    config_MapServer_WFS_cities, mock_ogr_layer,
):
    """Testing query with property filtering on geoserver backend"""

    p = OGRProvider(config_MapServer_WFS_cities)

    p.query(
        properties=[
            ('NA2DESC', 'Greece'),
            ('NA3DESC', 'Europe'),
        ]
    )

    mock_ogr_layer.SetAttributeFilter.assert_called_with(
        "NA2DESC = 'Greece' and NA3DESC = 'Europe'"
    )
