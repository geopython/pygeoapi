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

import pytest

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.ogr import OGRProvider


LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def config_vsicurl_csv():
    return {
        'name': 'OGR',
        'type': 'feature',
        'data': {
            'source_type': 'CSV',
            'source': '/vsicurl/https://raw.githubusercontent.com/pcm-dpc/COVID-19/master/dati-regioni/dpc-covid19-ita-regioni.csv', # noqa
            # 'source_srs': 'EPSG:4326',
            # 'target_srs': 'EPSG:4326',
            'source_capabilities': {
                'paging': True
            },
            'open_options': {
                'X_POSSIBLE_NAMES': 'long',
                'Y_POSSIBLE_NAMES': 'lat',
            },
            'gdal_ogr_options': {
                'EMPTY_AS_NULL': 'NO',
                'GDAL_CACHEMAX': '64',
                'CPL_DEBUG': 'NO'
            },
        },
        'id_field': 'fid',
        'time_field': 'data',
        'layer': 'dpc-covid19-ita-regioni'
    }


def test_get_fields_vsicurl(config_vsicurl_csv):
    """Testing field types"""

    p = OGRProvider(config_vsicurl_csv)
    results = p.get_fields()
    assert results['denominazione_regione']['type'] == 'string'
    assert results['totale_positivi']['type'] == 'string'


def test_get_vsicurl(config_vsicurl_csv):
    """Testing query for a specific object"""

    p = OGRProvider(config_vsicurl_csv)
    result = p.get('32')
    assert result['id'] == 32
    assert '14' in result['properties']['codice_regione']


def test_get_not_existing_feature_raise_exception(
    config_vsicurl_csv
):
    """Testing query for a not existing object"""
    p = OGRProvider(config_vsicurl_csv)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


def test_query_hits_vsicurl(config_vsicurl_csv):
    """Testing query on entire collection for hits"""

    p = OGRProvider(config_vsicurl_csv)
    feature_collection = p.query(resulttype='hits')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits > 100


def test_query_bbox_hits_vsicurl(config_vsicurl_csv):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_vsicurl_csv)
    feature_collection = p.query(
        bbox=[10.497565, 41.520355, 15.111823, 43.308645],
        resulttype='hits')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 0
    hits = feature_collection.get('numberMatched')
    assert hits is not None
    assert hits > 1


def test_query_with_limit_vsicurl(config_vsicurl_csv):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_vsicurl_csv)
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


def test_query_with_offset_vsicurl(config_vsicurl_csv):
    """Testing query for a valid JSON object with geometry"""

    p = OGRProvider(config_vsicurl_csv)
    feature_collection = p.query(offset=20, limit=10, resulttype='results')
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 10
    hits = feature_collection.get('numberMatched')
    assert hits is None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    assert feature['id'] == 21
    assert 'Veneto' in properties['denominazione_regione']
    geometry = feature.get('geometry')
    assert geometry is not None


def test_query_with_property_vsicurl(config_vsicurl_csv):
    """Testing query for a valid JSON object with property filter"""

    p = OGRProvider(config_vsicurl_csv)
    feature_collection = p.query(
        offset=20, limit=10, resulttype='results',
        properties=[('denominazione_regione', 'Lazio')])
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert len(features) == 10
    for feature in features:
        assert 'Lazio' in feature['properties']['denominazione_regione']


def test_query_with_skip_geometry_vsicurl(config_vsicurl_csv):
    """Testing query for a valid JSON object with property filter"""

    p = OGRProvider(config_vsicurl_csv)
    feature_collection = p.query(skip_geometry=True)
    for feature in feature_collection['features']:
        assert feature['geometry'] is None
