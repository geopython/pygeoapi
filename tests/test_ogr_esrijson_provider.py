# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
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

# https://sampleserver6.arcgisonline.com/arcgis/rest/services/CommunityAddressing/FeatureServer/0

import logging
import random

import pytest

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.ogr import OGRProvider


LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def config_ArcGIS_ESRIJSON():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'ESRIJSON',
            'source': 'https://sampleserver6.arcgisonline.com/arcgis/rest/services/CommunityAddressing/FeatureServer/0/query?where=objectid+%3D+objectid&outfields=*&orderByFields=objectid+ASC&f=json', # noqa
            # 'source_srs': 'EPSG:4326',
            # 'target_srs': 'EPSG:4326',
            'source_capabilities': {
                'paging': True
            },
            'open_options': {
                'FEATURE_SERVER_PAGING': 'YES',
            },
            'gdal_ogr_options': {
                'EMPTY_AS_NULL': 'NO',
                'GDAL_CACHEMAX': '64',
                'CPL_DEBUG': 'NO'
            },
        },
        'id_field': 'objectid',
        'layer': 'ESRIJSON'
    }


@pytest.fixture()
def config_random_id(config_ArcGIS_ESRIJSON):
    p = OGRProvider(config_ArcGIS_ESRIJSON)
    # Get bunch of features to randomly have an id
    feature_collection = p.query(offset=0, limit=10, resulttype='results')
    features = feature_collection.get('features')
    features_list = []
    for feature in features:
        features_list.append(feature['id'])
    selected_id = random.choice(features_list)
    fulladdr = p.get(selected_id)['properties']['fulladdr']
    return (selected_id, fulladdr.split(' ')[0])


def test_get_fields_agol(config_ArcGIS_ESRIJSON):
    """Testing field types"""

    p = OGRProvider(config_ArcGIS_ESRIJSON)
    results = p.get_fields()
    assert results['fulladdr']['type'] == 'string'
    assert results['municipality']['type'] == 'string'


def test_get_agol(config_ArcGIS_ESRIJSON, config_random_id):
    """Testing query for a specific object"""

    p = OGRProvider(config_ArcGIS_ESRIJSON)
    id, addr_number = config_random_id
    result = p.get(id)
    assert result['id'] == id
    assert addr_number in result['properties']['fulladdr']


def test_get_agol_not_existing_feature_raise_exception(
    config_ArcGIS_ESRIJSON
):
    """Testing query for a not existing object"""
    p = OGRProvider(config_ArcGIS_ESRIJSON)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_query_hits_agol(config_ArcGIS_ESRIJSON):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_ArcGIS_ESRIJSON)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits > 100


# def test_query_bbox_hits_agol(config_ArcGIS_ESRIJSON):
#     """Testing query for a valid JSON object with geometry"""

#     p = OGRProvider(config_ArcGIS_ESRIJSON)
#     feature_collection = p.query(
#         bbox=[-9822165.181154, 5112669.004249,
#               -9807305.104750, 5133712.297986],
#         resulttype='hits')
#     assert feature_collection.get('type') == 'FeatureCollection'
#     features = feature_collection.get('features')
#     assert len(features) == 0
#     hits = feature_collection.get('numberMatched')
#     assert hits is not None
#     assert hits > 1


def test_query_with_limit_agol(config_ArcGIS_ESRIJSON):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_ArcGIS_ESRIJSON)
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


def test_query_with_offset(config_ArcGIS_ESRIJSON):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_ArcGIS_ESRIJSON)
    feature_collection = p.query(offset=10, limit=10, resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 10
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    assert properties['fulladdr'] is not None
    geometry = feature.get('geometry')
    assert geometry is not None
