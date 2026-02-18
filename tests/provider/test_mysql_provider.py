# =================================================================
#
# Authors: Colton Loftus <cloftus@lincolninst.edu>
#
# Copyright (c) 2025 Colton Loftus
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

import os
import pytest
from pygeoapi.provider.base import (
    ProviderItemNotFoundError,
)
from pygeoapi.provider.sql import MySQLProvider

PASSWORD = os.environ.get('MYSQL_PASSWORD', 'mysql')


# Testing local MySQL with docker:
'''
docker run --name mysql-test \
    -e MYSQL_ROOT_PASSWORD=mysql \
    -e MYSQL_USER=pygeoapi \
    -e MYSQL_PASSWORD=mysql \
    -e MYSQL_DATABASE=test_geo_app \
    -p 3306:3306 \
    -v ./tests/data/mysql_data.sql:/docker-entrypoint-initdb.d/init.sql:ro \
    -d mysql:8
'''


@pytest.fixture(params=['default', 'connection_string'])
def config(request):
    config_ = {
        'name': 'MySQL',
        'type': 'feature',
        'options': {'connect_timeout': 10},
        'id_field': 'locationID',
        'table': 'location',
        'geom_field': 'locationCoordinates'
    }
    if request.param == 'default':
        config_['data'] = {
            'host': 'localhost',
            'dbname': 'test_geo_app',
            'user': 'root',
            'port': 3306,
            'password': PASSWORD,
            'search_path': ['test_geo_app']
        }
    elif request.param == 'connection_string':
        config_['data'] = (
            f'mysql+pymysql://root:{PASSWORD}@localhost:3306/test_geo_app'
        )
        config_['options']['search_path'] = ['test_geo_app']

    return config_


def test_valid_connection_options(config):
    if config.get('options'):
        keys = list(config['options'].keys())
        for key in keys:
            assert key in [
                'connect_timeout',
                'tcp_user_timeout',
                'keepalives',
                'keepalives_idle',
                'keepalives_count',
                'keepalives_interval',
                'search_path'
            ]


def test_query(config):
    """Testing query for a valid JSON object with geometry"""
    p = MySQLProvider(config)
    feature_collection = p.query()
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert features is not None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    geometry = feature.get('geometry')
    assert geometry is not None


def test_fields(config):
    p = MySQLProvider(config)
    fields = p.get_fields()
    expectedFields = [
        'locationID',
        'locationName',
        'description',
        'created_at'
    ]
    for field in expectedFields:
        assert field in fields


def test_query_with_paging(config):
    """Test query valid features with paging"""
    p = MySQLProvider(config)
    feature_collection = p.query(limit=2)

    ALL_ITEMS_IN_DB = 5
    assert feature_collection['numberMatched'] == ALL_ITEMS_IN_DB
    assert feature_collection['numberReturned'] == 2

    feature_collection = p.query(offset=3)
    assert feature_collection['numberMatched'] == ALL_ITEMS_IN_DB
    assert feature_collection['numberReturned'] == ALL_ITEMS_IN_DB - 3


def test_query_bbox(config):
    """Test query with a specified bounding box"""
    p = MySQLProvider(config)
    boxed_feature_collection = p.query(bbox=[0, 0, 0, 0])
    assert len(boxed_feature_collection['features']) == 0

    nyc_bbox = [-73.9754, 40.7729, -73.9554, 40.7929]

    boxed_feature_collection = p.query(bbox=nyc_bbox)
    assert len(boxed_feature_collection['features']) == 1
    assert boxed_feature_collection['features'][0]['id'] == 1


def test_query_sortby(config):
    """Test query with sorting"""
    psp = MySQLProvider(config)
    up = psp.query(sortby=[{'property': 'locationName', 'order': '+'}])
    firstItem = up['features'][0]['properties']['locationName']
    assert firstItem == 'Central Park'
    secondItem = up['features'][1]['properties']['locationName']
    assert secondItem == 'Christ the Redeemer'
    assert firstItem < secondItem


def test_query_skip_geometry(config):
    """Test query without geometry"""
    provider = MySQLProvider(config)
    result = provider.query(skip_geometry=True)
    feature = result['features'][0]
    assert feature['geometry'] is None


def test_get_not_existing_item_raise_exception(config):
    """Testing query for a not existing object"""
    p = MySQLProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)
