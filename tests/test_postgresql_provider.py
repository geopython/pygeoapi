# =================================================================
#
# Authors: Just van den Broecke <justb4@gmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2019 Just van den Broecke
# Copyright (c) 2024 Tom Kralidis
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
# Copyright (c) 2023 Francesco Bartoli
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
# See pygeoapi/provider/postgresql.py for instructions on setting up
# test database in Docker

import os
import json
import pytest
import pyproj
from http import HTTPStatus

from pygeofilter.parsers.ecql import parse

from pygeoapi.api import API
from pygeoapi.api.itemtypes import (
    get_collection_items, get_collection_item, post_collection_items
)
from pygeoapi.provider.base import (
    ProviderConnectionError,
    ProviderItemNotFoundError,
    ProviderQueryError
)
from pygeoapi.provider.postgresql import PostgreSQLProvider
import pygeoapi.provider.postgresql as postgresql_provider_module

from pygeoapi.util import (yaml_load, geojson_to_geom,
                           get_transform_from_crs, get_crs_from_uri)

from .util import get_test_file_path, mock_api_request

PASSWORD = os.environ.get('POSTGRESQL_PASSWORD', 'postgres')
DEFAULT_CRS = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'


@pytest.fixture()
def config():
    return {
        'name': 'PostgreSQL',
        'type': 'feature',
        'data': {'host': '127.0.0.1',
                 'dbname': 'test',
                 'user': 'postgres',
                 'password': PASSWORD,
                 'search_path': ['osm', 'public']
                 },
        'options': {
                        'connect_timeout': 10
                   },
        'id_field': 'osm_id',
        'table': 'hotosm_bdi_waterways',
        'geom_field': 'foo_geom'
    }


@pytest.fixture()
def config_types():
    return {
        'name': 'PostgreSQL',
        'type': 'feature',
        'data': {'host': '127.0.0.1',
                 'dbname': 'test',
                 'user': 'postgres',
                 'password': PASSWORD,
                 'search_path': ['public']
                 },
        'options': {
                        'connect_timeout': 10
                   },
        'id_field': 'id',
        'table': 'foo',
        'geom_field': 'the_geom'
    }


@pytest.fixture()
def openapi():
    with open(get_test_file_path('pygeoapi-test-openapi.yml')) as fh:
        return yaml_load(fh)


# API using PostgreSQL provider
@pytest.fixture()
def pg_api_(openapi):
    with open(get_test_file_path('pygeoapi-test-config-postgresql.yml')) as fh:
        config = yaml_load(fh)
        return API(config, openapi)


def test_valid_connection_options(config):
    if config.get('options'):
        keys = list(config['options'].keys())
        for key in keys:
            assert key in ['connect_timeout', 'tcp_user_timeout', 'keepalives',
                           'keepalives_idle', 'keepalives_count',
                           'keepalives_interval']


def test_query(config):
    """Testing query for a valid JSON object with geometry"""
    p = PostgreSQLProvider(config)
    feature_collection = p.query()
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert features is not None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    geometry = feature.get('geometry')
    assert geometry is not None


def test_query_materialised_view(config):
    """Testing query using a materialised view"""
    config_materialised_view = config.copy()
    config_materialised_view['table'] = 'hotosm_bdi_drains'
    provider = PostgreSQLProvider(config_materialised_view)

    # Only ID, width and depth properties should be available
    assert set(provider.get_fields().keys()) == {"osm_id", "width", "depth"}


def test_query_with_property_filter(config):
    """Test query valid features when filtering by property"""
    p = PostgreSQLProvider(config)
    feature_collection = p.query(properties=[("waterway", "stream")])
    features = feature_collection.get('features')
    stream_features = list(
        filter(lambda feature: feature['properties']['waterway'] == 'stream',
               features))
    assert len(features) == len(stream_features)

    feature_collection = p.query(limit=50)
    features = feature_collection.get('features')
    stream_features = list(
        filter(lambda feature: feature['properties']['waterway'] == 'stream',
               features))
    other_features = list(
        filter(lambda feature: feature['properties']['waterway'] != 'stream',
               features))
    assert len(features) != len(stream_features)
    assert len(other_features) != 0
    assert feature_collection['numberMatched'] == 14776
    assert feature_collection['numberReturned'] == 50


def test_query_with_paging(config):
    """Test query valid features with paging"""
    p = PostgreSQLProvider(config)
    feature_collection = p.query(limit=50)

    assert feature_collection['numberMatched'] == 14776
    assert feature_collection['numberReturned'] == 50

    offset = feature_collection['numberMatched'] - 10

    feature_collection = p.query(offset=offset)
    assert feature_collection['numberMatched'] == 14776
    assert feature_collection['numberReturned'] == 10


def test_query_with_config_properties(config):
    """
    Test that query is restricted by properties in the config.
    No properties should be returned that are not requested.
    Note that not all requested properties have to exist in the query result.
    """
    properties_subset = ['name', 'waterway', 'width', 'does_not_exist']
    config.update({'properties': properties_subset})
    provider = PostgreSQLProvider(config)
    assert provider.properties == properties_subset
    result = provider.query()
    feature = result.get('features')[0]
    properties = feature.get('properties')
    for property_name in properties.keys():
        assert property_name in config["properties"]


@pytest.mark.parametrize("property_filter, expected", [
    ([], 14776),
    ([("waterway", "stream")], 13930),
    ([("waterway", "this does not exist")], 0),
])
def test_query_hits_with_property_filter(config, property_filter, expected):
    """Test query resulttype=hits"""
    provider = PostgreSQLProvider(config)
    results = provider.query(properties=property_filter, resulttype="hits")
    assert results["numberMatched"] == expected


def test_query_bbox(config):
    """Test query with a specified bounding box"""
    psp = PostgreSQLProvider(config)
    boxed_feature_collection = psp.query(
        bbox=[29.3373, -3.4099, 29.3761, -3.3924]
    )
    assert len(boxed_feature_collection['features']) == 5


def test_query_sortby(config):
    """Test query with sorting"""
    psp = PostgreSQLProvider(config)
    up = psp.query(sortby=[{'property': 'osm_id', 'order': '+'}])
    assert up['features'][0]['id'] == 13990765
    down = psp.query(sortby=[{'property': 'osm_id', 'order': '-'}])
    assert down['features'][0]['id'] == 620735702

    name = psp.query(sortby=[{'property': 'name', 'order': '+'}])
    assert name['features'][0]['properties']['name'] == 'Agasasa'


def test_query_skip_geometry(config):
    """Test query without geometry"""
    provider = PostgreSQLProvider(config)
    result = provider.query(skip_geometry=True)
    feature = result['features'][0]
    assert feature['geometry'] is None


@pytest.mark.parametrize('properties', [
    ['name'],
    ['name', 'waterway'],
    ['name', 'waterway', 'this does not exist']
])
def test_query_select_properties(config, properties):
    """Test query with selected properties"""
    provider = PostgreSQLProvider(config)
    result = provider.query(select_properties=properties)
    feature = result['features'][0]

    expected = set(provider.get_fields().keys()).intersection(properties)
    assert set(feature['properties'].keys()) == expected


@pytest.mark.parametrize('id_, prev, next_', [
    (29701937, 29698243, 29704504),
    (13990765, 13990765, 25469515),  # First item, prev should be id_
    (620735702, 620420337, 620735702),  # Last item, next should be id_
])
def test_get_simple(config, id_, prev, next_):
    """Testing query for a specific object and identifying prev/next"""
    p = PostgreSQLProvider(config)
    result = p.get(id_)
    assert result['id'] == id_
    assert 'geometry' in result
    assert 'properties' in result
    assert result['type'] == 'Feature'
    assert 'foo_geom' not in result['properties']  # geometry is separate

    assert result['prev'] == prev
    assert result['next'] == next_


def test_get_with_config_properties(config):
    """
    Test that get is restricted by properties in the config.
    No properties should be returned that are not requested.
    Note that not all requested properties have to exist in the query result.
    """
    properties_subset = ['name', 'waterway', 'width', 'does_not_exist']
    config.update({'properties': properties_subset})
    provider = PostgreSQLProvider(config)
    assert provider.properties == properties_subset
    result = provider.get(80835483)
    properties = result.get('properties')
    for property_name in properties.keys():
        assert property_name in config["properties"]


def test_get_not_existing_item_raise_exception(config):
    """Testing query for a not existing object"""
    p = PostgreSQLProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get(-1)


@pytest.mark.parametrize('cql, expected_ids', [
    ("osm_id BETWEEN 80800000 AND 80900000",
        [80827787, 80827793, 80835468, 80835470, 80835472, 80835474,
         80835475, 80835478, 80835483, 80835486]),
    ("osm_id BETWEEN 80800000 AND 80900000 AND waterway = 'stream'",
        [80835470]),
    ("osm_id BETWEEN 80800000 AND 80900000 AND waterway ILIKE 'sTrEam'",
        [80835470]),
    ("osm_id BETWEEN 80800000 AND 80900000 AND waterway LIKE 's%'",
        [80835470]),
    ("osm_id BETWEEN 80800000 AND 80900000 AND name IN ('Muhira', 'Mpanda')",
        [80835468, 80835472, 80835475, 80835478]),
    ("osm_id BETWEEN 80800000 AND 80900000 AND name IS NULL",
        [80835474, 80835483]),
    ("osm_id BETWEEN 80800000 AND 80900000 AND BBOX(foo_geom, 29, -2.8, 29.2, -2.9)",  # noqa
        [80827793, 80835470, 80835472, 80835483, 80835489]),
    ("osm_id BETWEEN 80800000 AND 80900000 AND "
        "CROSSES(foo_geom,  LINESTRING(29.091 -2.731, 29.253 -2.845))",
        [80835470, 80835472, 80835489])
])
def test_query_cql(config, cql, expected_ids):
    """Test a variety of CQL queries"""
    ast = parse(cql)
    provider = PostgreSQLProvider(config)

    feature_collection = provider.query(filterq=ast)
    assert feature_collection.get('type') == 'FeatureCollection'

    features = feature_collection.get('features')
    ids = [feature["id"] for feature in features]
    assert ids == expected_ids


def test_query_cql_properties_bbox_filters(config):
    """Test query with CQL, properties and bbox filters"""
    # Arrange
    properties = [('waterway', 'stream')]
    bbox = [29, -2.8, 29.2, -2.9]
    filterq = parse("osm_id BETWEEN 80800000 AND 80900000")
    expected_ids = [80835470]

    # Act
    provider = PostgreSQLProvider(config)
    feature_collection = provider.query(filterq=filterq,
                                        properties=properties,
                                        bbox=bbox)

    # Assert
    ids = [feature["id"] for feature in feature_collection.get('features')]
    assert ids == expected_ids


def test_get_fields_types(config_types):
    provider = PostgreSQLProvider(config_types)

    expected_fields = {
        'id': {'type': 'integer', 'format': None},
        'field1': {'type': 'number', 'format': None},
        'field2': {'type': 'string', 'format': None},
        'field3': {'type': 'number', 'format': None},
        'dt': {'type': 'string', 'format': 'date-time'}
    }

    assert provider.get_fields() == expected_fields
    assert provider.fields == expected_fields  # API uses .fields attribute


def test_get_fields(config):
    # Arrange
    expected_fields = {
        'blockage': {'type': 'string', 'format': None},
        'covered': {'type': 'string', 'format': None},
        'depth': {'type': 'string', 'format': None},
        'layer': {'type': 'string', 'format': None},
        'name': {'type': 'string', 'format': None},
        'natural': {'type': 'string', 'format': None},
        'osm_id': {'type': 'integer', 'format': None},
        'tunnel': {'type': 'string', 'format': None},
        'water': {'type': 'string', 'format': None},
        'waterway': {'type': 'string', 'format': None},
        'width': {'type': 'string', 'format': None},
        'z_index': {'type': 'string', 'format': None}
    }

    # Act
    provider = PostgreSQLProvider(config)

    # Assert
    assert provider.get_fields() == expected_fields
    assert provider.fields == expected_fields  # API uses .fields attribute


def test_instantiation(config):
    """Test attributes are correctly set during instantiation."""
    # Act
    provider = PostgreSQLProvider(config)

    # Assert
    assert provider.name == "PostgreSQL"
    assert provider.table == "hotosm_bdi_waterways"
    assert provider.id_field == "osm_id"


@pytest.mark.parametrize('bad_data, exception, match', [
    ({'table': 'bad_table'}, ProviderQueryError,
     'Table.*not found in schema.*'),
    ({'data': {'bad': 'data'}}, ProviderConnectionError,
     r'Could not connect to postgresql\+psycopg2:\/\/:5432 \(password hidden\).'), # noqa
    ({'id_field': 'bad_id'}, ProviderQueryError,
     r'No such id_field column \(bad_id\) on osm.hotosm_bdi_waterways.'),
])
def test_instantiation_with_bad_config(config, bad_data, exception, match):
    # Arrange
    config.update(bad_data)
    # Make sure we don't use a cached connection or model in the tests
    postgresql_provider_module._ENGINE_STORE = {}
    postgresql_provider_module._TABLE_MODEL_STORE = {}

    # Act and assert
    with pytest.raises(exception, match=match):
        PostgreSQLProvider(config)


def test_instantiation_with_bad_credentials(config):
    # Arrange
    config['data'].update({'user': 'bad_user'})
    match = r'Could not connect to .*bad_user:\*\*\*@'
    # Make sure we don't use a cached connection in the tests
    postgresql_provider_module._ENGINE_STORE = {}

    # Act and assert
    with pytest.raises(ProviderConnectionError, match=match):
        PostgreSQLProvider(config)


def test_engine_and_table_model_stores(config):
    provider0 = PostgreSQLProvider(config)

    # Same config should return same engine and table_model
    provider1 = PostgreSQLProvider(config)
    assert repr(provider1._engine) == repr(provider0._engine)
    assert provider1._engine is provider0._engine
    assert provider1.table_model is provider0.table_model

    # Same database connection details, but different table
    different_table = config.copy()
    different_table.update(table="hotosm_bdi_drains")
    provider2 = PostgreSQLProvider(different_table)
    assert repr(provider2._engine) == repr(provider0._engine)
    assert provider2._engine is provider0._engine
    assert provider2.table_model is not provider0.table_model

    # Although localhost is 127.0.0.1, this should get different engine
    # and also a different table_model, as two databases may have different
    # tables with the same name
    different_host = config.copy()
    different_host["data"]["host"] = "localhost"
    provider3 = PostgreSQLProvider(different_host)
    assert provider3._engine is not provider0._engine
    assert provider3.table_model is not provider0.table_model


# START: EXTERNAL API TESTS
def test_get_collection_items_postgresql_cql(pg_api_):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.
    """
    # Arrange
    cql_query = 'osm_id BETWEEN 80800000 AND 80900000 AND name IS NULL'
    expected_ids = [80835474, 80835483]

    # Act
    req = mock_api_request({
        'filter-lang': 'cql-text',
        'filter': cql_query
    })
    rsp_headers, code, response = get_collection_items(
        pg_api_, req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.OK
    features = json.loads(response)
    ids = [item['id'] for item in features['features']]
    assert ids == expected_ids

    # Act, no filter-lang
    req = mock_api_request({
        'filter': cql_query
    })
    rsp_headers, code, response = get_collection_items(
        pg_api_, req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.OK
    features = json.loads(response)
    ids = [item['id'] for item in features['features']]
    assert ids == expected_ids


def test_get_collection_items_postgresql_cql_invalid_filter_language(pg_api_):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.

    Test for invalid filter language
    """
    # Arrange
    cql_query = 'osm_id BETWEEN 80800000 AND 80900000 AND name IS NULL'

    # Act
    req = mock_api_request({
        'filter-lang': 'cql-json',  # Only cql-text is valid for GET
        'filter': cql_query
    })
    rsp_headers, code, response = get_collection_items(
        pg_api_, req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.BAD_REQUEST
    error_response = json.loads(response)
    assert error_response['code'] == 'InvalidParameterValue'
    assert error_response['description'] == 'Invalid filter language'


@pytest.mark.parametrize("bad_cql", [
    'id IN (1, ~)',
    'id EATS (1, 2)',  # Valid CQL relations only
    'id IN (1, 2'  # At some point this may return UnexpectedEOF
])
def test_get_collection_items_postgresql_cql_bad_cql(pg_api_, bad_cql):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.

    Test for bad cql
    """
    # Act
    req = mock_api_request({
        'filter': bad_cql
    })
    rsp_headers, code, response = get_collection_items(
        pg_api_, req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.BAD_REQUEST
    error_response = json.loads(response)
    assert error_response['code'] == 'InvalidParameterValue'
    assert error_response['description'] == f'Bad CQL string : {bad_cql}'


def test_post_collection_items_postgresql_cql(pg_api_):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.
    """
    # Arrange
    cql = {"and": [{"between": {"value": {"property": "osm_id"},
                                "lower": 80800000,
                                "upper": 80900000}},
                   {"isNull": {"property": "name"}}]}
    # werkzeug requests use a value of CONTENT_TYPE 'application/json'
    # to create Content-Type in the Request object. So here we need to
    # overwrite the default CONTENT_TYPE with the required one.
    headers = {'CONTENT_TYPE': 'application/query-cql-json'}
    expected_ids = [80835474, 80835483]

    # Act
    req = mock_api_request({
        'filter-lang': 'cql-json'
    }, data=cql, **headers)
    rsp_headers, code, response = post_collection_items(
        pg_api_, req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.OK
    features = json.loads(response)
    ids = [item['id'] for item in features['features']]
    assert ids == expected_ids


def test_post_collection_items_postgresql_cql_invalid_filter_language(pg_api_):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.

    Test for invalid filter language
    """
    # Arrange
    # CQL should never be parsed
    cql = {"in": {"value": {"property": "id"}, "list": [1, 2]}}
    headers = {'CONTENT_TYPE': 'application/query-cql-json'}

    # Act
    req = mock_api_request({
        'filter-lang': 'cql-text'  # Only cql-json is valid for POST
    }, data=cql, **headers)
    rsp_headers, code, response = post_collection_items(
        pg_api_, req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.BAD_REQUEST
    error_response = json.loads(response)
    assert error_response['code'] == 'InvalidParameterValue'
    assert error_response['description'] == 'Invalid filter language'


@pytest.mark.parametrize("bad_cql", [
    # Valid CQL relations only
    {"eats": {"value": {"property": "id"}, "list": [1, 2]}},
    # At some point this may return UnexpectedEOF
    '{"in": {"value": {"property": "id"}, "list": [1, 2}}'
])
def test_post_collection_items_postgresql_cql_bad_cql(pg_api_, bad_cql):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.

    Test for bad cql
    """
    # Arrange
    headers = {'CONTENT_TYPE': 'application/query-cql-json'}

    # Act
    req = mock_api_request({
        'filter-lang': 'cql-json'
    }, data=bad_cql, **headers)
    rsp_headers, code, response = post_collection_items(
        pg_api_, req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.BAD_REQUEST
    error_response = json.loads(response)
    assert error_response['code'] == 'InvalidParameterValue'
    assert error_response['description'].startswith('Bad CQL string')


def test_get_collection_items_postgresql_crs(pg_api_):
    """Test the coordinates transformation implementation of
    PostgreSQLProvider when using the crs parameter.
    """
    storage_crs = DEFAULT_CRS
    crs_32735 = 'http://www.opengis.net/def/crs/EPSG/0/32735'

    # Without CRS query parameter -> no coordinates transformation
    req = mock_api_request({'bbox': '29.0,-2.85,29.05,-2.8'})
    rsp_headers, code, response = get_collection_items(
        pg_api_, req, 'hot_osm_waterways')

    assert code == HTTPStatus.OK

    features_orig = json.loads(response)
    assert rsp_headers['Content-Crs'] == f'<{DEFAULT_CRS}>'

    # With CRS query parameter not resulting in coordinates transformation
    # (i.e. 'crs' query parameter is the same as 'storage_crs')
    req = mock_api_request(
        {'crs': storage_crs, 'bbox': '29.0,-2.85,29.05,-2.8'})
    rsp_headers, code, response = get_collection_items(
        pg_api_, req, 'hot_osm_waterways')

    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Crs'] == f'<{storage_crs}>'

    features_storage_crs = json.loads(response)

    # With CRS query parameter resulting in coordinates transformation
    req = mock_api_request({'crs': crs_32735, 'bbox': '29.0,-2.85,29.05,-2.8'})
    rsp_headers, code, response = get_collection_items(
        pg_api_, req, 'hot_osm_waterways')

    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Crs'] == f'<{crs_32735}>'

    features_32735 = json.loads(response)

    # Make sure that we compare the same features
    assert (
        sorted(f['id'] for f in features_orig['features'])
        == sorted(f['id'] for f in features_storage_crs['features'])
        == sorted(f['id'] for f in features_32735['features'])
    )

    # Without 'crs' query parameter or with 'crs' set to 'storage_crs', the
    # geometries of the returned features should be the same
    for feat_orig in features_orig['features']:
        id_ = feat_orig['id']
        for feat_storage_crs in features_storage_crs['features']:
            if id_ == feat_storage_crs['id']:
                assert feat_orig['geometry'] == feat_storage_crs['geometry']
                break

    transform_func = get_transform_from_crs(
        get_crs_from_uri(DEFAULT_CRS),
        pyproj.CRS.from_epsg(32735),
        always_xy=False,
    )
    # Check that the coordinates of returned features were transformed
    for feat_orig in features_orig['features']:
        id_ = feat_orig['id']
        geom_orig = geojson_to_geom(feat_orig['geometry'])
        for feat_32735 in features_32735['features']:
            if id_ == feat_32735['id']:
                geom_32735 = geojson_to_geom(feat_32735['geometry'])

                assert geom_32735.equals_exact(transform_func(geom_orig), 1)
                break


def test_get_collection_item_postgresql_crs(pg_api_):
    """Test the coordinates transformation implementation of
    PostgreSQLProvider when using the crs parameter.
    """
    storage_crs = DEFAULT_CRS
    crs_32735 = 'http://www.opengis.net/def/crs/EPSG/0/32735'
    # List of feature IDs located in UTM zone 35S
    fid_list = [
        '439338397',
        '198190856',
        '93063941',
        '586449587',
        '80827793',
        '587350255',
        '586994284',
        '587960337',
        '586449586',
        '422440125',
    ]
    for fid in fid_list:
        # Without CRS query parameter -> no coordinates transformation
        req = mock_api_request({'f': 'json'})
        rsp_headers, code, response = get_collection_item(
            pg_api_, req, 'hot_osm_waterways', fid)

        assert code == HTTPStatus.OK
        assert rsp_headers['Content-Crs'] == f'<{DEFAULT_CRS}>'

        feat_orig = json.loads(response)
        geom_orig = geojson_to_geom(feat_orig['geometry'])

        # With CRS query parameter not resulting in coordinates transformation
        # (i.e. 'crs' query parameter is the same as 'storage_crs')
        req = mock_api_request({'f': 'json', 'crs': storage_crs})
        rsp_headers, code, response = get_collection_item(
            pg_api_, req, 'hot_osm_waterways', fid)

        assert code == HTTPStatus.OK
        assert rsp_headers['Content-Crs'] == f'<{storage_crs}>'

        feat_storage_crs = json.loads(response)

        # Without 'crs' query parameter or with 'crs' set to 'storage_crs', the
        # geometries should be identical, when storage CRS is WGS84 lon,lat.
        assert feat_orig['geometry'] == feat_storage_crs['geometry']

        # With CRS query parameter resulting in coordinates transformation
        req = mock_api_request({'f': 'json', 'crs': crs_32735})
        rsp_headers, code, response = get_collection_item(
            pg_api_, req, 'hot_osm_waterways', fid)

        assert code == HTTPStatus.OK
        assert rsp_headers['Content-Crs'] == f'<{crs_32735}>'

        feat_32735 = json.loads(response)
        geom_32735 = geojson_to_geom(feat_32735['geometry'])

        transform_func = get_transform_from_crs(
            get_crs_from_uri(DEFAULT_CRS),
            pyproj.CRS.from_epsg(32735),
            always_xy=False,
        )
        # Check that the coordinates of returned feature were transformed
        assert geom_32735.equals_exact(transform_func(geom_orig), 1)


def test_get_collection_items_postgresql_automap_naming_conflicts(pg_api_):
    """
    Test that PostgreSQLProvider can handle naming conflicts when automapping
    classes and relationships from database schema.
    """
    req = mock_api_request()
    rsp_headers, code, response = get_collection_items(
        pg_api_, req, 'dummy_naming_conflicts')

    assert code == HTTPStatus.OK
    features = json.loads(response).get('features')
    assert len(features) == 0
