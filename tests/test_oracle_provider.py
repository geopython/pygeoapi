# =================================================================
#
# Authors: Andreas Kosubek <andreas.kosubek@ama.gv.at>
#
# Copyright (c) 2023 Andreas Kosubek
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
# Create testdata: python3 load_oracle_data.py

import os
import pytest
from pygeoapi.provider.base import ProviderInvalidQueryError
from pygeoapi.provider.oracle import OracleProvider, DatabaseConnection

USERNAME = os.environ.get("PYGEOAPI_ORACLE_USER", "geo_test")
PASSWORD = os.environ.get("PYGEOAPI_ORACLE_PASSWD", "geo_test")
SERVICE_NAME = os.environ.get("PYGEOAPI_ORACLE_SERVICE_NAME", "XEPDB1")
HOST = os.environ.get("PYGEOAPI_ORACLE_HOST", "127.0.0.1")
PORT = os.environ.get("PYGEOAPI_ORACLE_PORT", "1521")


class SqlManipulator:
    def process_query(
        self,
        db,
        sql_query,
        bind_variables,
        sql_manipulator_options,
        offset,
        limit,
        resulttype,
        bbox,
        datetime_,
        properties,
        sortby,
        skip_geometry,
        select_properties,
        crs_transform_spec,
        q,
        language,
        filterq,
    ):
        sql = "ID = 10 AND :foo != :bar"

        if sql_query.find(" WHERE ") == -1:
            sql_query = sql_query.replace("#WHERE#", f" WHERE {sql}")
        else:
            sql_query = sql_query.replace("#WHERE#", f" AND {sql}")

        bind_variables = {
            **bind_variables,
            "foo": "foo",
            "bar": sql_manipulator_options.get("foo"),
        }

        return sql_query, bind_variables

    def process_get(
        self,
        db,
        sql_query,
        bind_variables,
        sql_manipulator_options,
        identifier,
    ):
        sql_query = f"{sql_query} AND 'auth' = 'you arent allowed'"

        return sql_query, bind_variables

    def process_create(
        self,
        db,
        sql_query,
        bind_variables,
        sql_manipulator_options,
        request_data,
    ):
        bind_variables["name"] = "overwritten"

        return sql_query, bind_variables

    def process_update(
        self,
        db,
        sql_query,
        bind_variables,
        sql_manipulator_options,
        identifier,
        request_data,
    ):
        bind_variables["area"] = 42
        bind_variables["volume"] = 42

        return sql_query, bind_variables

    def process_delete(
        self,
        db,
        sql_query,
        bind_variables,
        sql_manipulator_options,
        identifier,
    ):
        sql_query = f"{sql_query} AND 'auth' = 'you arent allowed'"

        return sql_query, bind_variables


@pytest.fixture()
def config():
    return {
        "name": "Oracle",
        "type": "feature",
        "data": {
            "host": HOST,
            "port": PORT,
            "service_name": SERVICE_NAME,
            "user": USERNAME,
            "password": PASSWORD,
        },
        "id_field": "id",
        "table": "lakes",
        "geom_field": "geometry",
        "editable": True,
    }


@pytest.fixture()
def config_db_conn():
    return {
        "conn_dic": {
            "host": HOST,
            "port": PORT,
            "service_name": SERVICE_NAME,
            "user": USERNAME,
            "password": PASSWORD,
        },
        "table": "lakes",
    }


@pytest.fixture()
def config_public_synonym():
    return {
        "name": "Oracle",
        "type": "feature",
        "data": {
            "host": HOST,
            "port": PORT,
            "service_name": SERVICE_NAME,
            "user": USERNAME,
            "password": PASSWORD,
        },
        "id_field": "id",
        "table": "lakes_public_syn",
        "geom_field": "geometry",
        "editable": True,
    }


@pytest.fixture()
def config_private_synonym():
    return {
        "name": "Oracle",
        "type": "feature",
        "data": {
            "host": HOST,
            "port": PORT,
            "service_name": SERVICE_NAME,
            "user": USERNAME,
            "password": PASSWORD,
        },
        "id_field": "id",
        "table": "lakes_private_syn",
        "geom_field": "geometry",
        "editable": True,
    }


@pytest.fixture()
def config_manipulator(config):
    return {
        **config,
        "sql_manipulator": "tests.test_oracle_provider.SqlManipulator",
        "sql_manipulator_options": {"foo": "bar"},
    }


@pytest.fixture()
def config_properties(config):
    return {
        **config,
        "properties": ["id", "name", "wiki_link"],
    }


@pytest.fixture()
def config_extra_properties(config):
    return {
        **config,
        "extra_properties": ["'Here the name is ' || name || '!' as tooltip"],
    }


@pytest.fixture()
def create_geojson():
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [9.012050, 47.841512],
                    [9.803470, 47.526461],
                    [9.476940, 47.459178],
                    [8.918151, 47.693253],
                    [9.012050, 47.841512],
                ]
            ],
        },
        "properties": {
            "name": "Lake Constance",
            "wiki_link": "https://en.wikipedia.org/wiki/Lake_Constance",
            "foo": "bar",
        },
    }


@pytest.fixture()
def create_point_geojson():
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [9.603316032965449, 47.48872063967191],
        },
        "properties": {"name": "Yachthafen Fischerinsel", "wiki_link": None},
    }


@pytest.fixture()
def update_geojson():
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [9.012050, 47.841512],
                    [9.803470, 47.526461],
                    [9.476940, 47.459178],
                    [8.918151, 47.693253],
                    [9.012050, 47.841512],
                ]
            ],
        },
        "properties": {
            "name": "Lake Constance",
            "wiki_link": "https://en.wikipedia.org/wiki/Lake_Constance",
            "foo": "bar",
            "area": 536000,
            "volume": 48000,
        },
        "id": 26,
    }


def test_query(config):
    """Test query for a valid JSON object with geometry"""
    p = OracleProvider(config)
    feature_collection = p.query()
    assert feature_collection.get("type") == "FeatureCollection"
    features = feature_collection.get("features")
    assert features is not None
    feature = features[0]
    properties = feature.get("properties")
    assert properties is not None
    geometry = feature.get("geometry")
    assert geometry is not None


def test_get_fields(config):
    """Test get_fields"""
    expected_fields = {
        "id": {"type": "NUMBER"},
        "area": {"type": "NUMBER"},
        "volume": {"type": "NUMBER"},
        "name": {"type": "VARCHAR2"},
        "wiki_link": {"type": "VARCHAR2"},
    }

    provider = OracleProvider(config)

    assert provider.get_fields() == expected_fields
    assert provider.fields == expected_fields


def test_get_fields_private_synonym(config_private_synonym):
    """Test get_fields from private synonym"""
    expected_fields = {
        "id": {"type": "NUMBER"},
        "area": {"type": "NUMBER"},
        "volume": {"type": "NUMBER"},
        "name": {"type": "VARCHAR2"},
        "wiki_link": {"type": "VARCHAR2"},
    }

    provider = OracleProvider(config_private_synonym)

    assert provider.get_fields() == expected_fields
    assert provider.fields == expected_fields


def test_get_fields_public_synonym(config_public_synonym):
    """Test get_fields from public synonym"""
    expected_fields = {
        "id": {"type": "NUMBER"},
        "area": {"type": "NUMBER"},
        "volume": {"type": "NUMBER"},
        "name": {"type": "VARCHAR2"},
        "wiki_link": {"type": "VARCHAR2"},
    }

    provider = OracleProvider(config_public_synonym)

    assert provider.get_fields() == expected_fields
    assert provider.fields == expected_fields


def test_get_fields_properties(config_properties):
    """
    Test get_fields with subset of columns.
    Test of property configuration.
    """
    # NOTE: properties does not influence fields because
    #       the fields are also used for filtering
    expected_fields = {
        "id": {"type": "NUMBER"},
        "name": {"type": "VARCHAR2"},
        "wiki_link": {"type": "VARCHAR2"},
        "area": {"type": "NUMBER"},
        "volume": {"type": "NUMBER"},
    }

    provider = OracleProvider(config_properties)
    provided_fields = provider.get_fields()

    assert provided_fields == expected_fields
    assert provider.fields == expected_fields


def test_query_with_property_filter(config):
    """Test query valid features when filtering by property"""
    p = OracleProvider(config)
    feature_collection = p.query(properties=[("name", "Aral Sea")])
    features = feature_collection.get("features")

    assert len(features) == 1
    assert features[0].get("id") == 12


def test_query_with_extra_properties(config_extra_properties):
    p = OracleProvider(config_extra_properties)

    feature_collection = p.query(properties=[("name", "Aral Sea")])
    features = feature_collection.get("features")

    assert features[0]["properties"]["tooltip"] == "Here the name is Aral Sea!"


def test_query_bbox(config):
    """Test query with a specified bounding box"""
    p = OracleProvider(config)
    feature_collection = p.query(bbox=[50, 40, 60, 50])
    features = feature_collection.get("features")

    assert len(features) == 1
    assert features[0]["properties"]["name"] == "Aral Sea"


def test_query_sortby(config):
    """Test query with sorting"""
    p = OracleProvider(config)
    up = p.query(sortby=[{"property": "id", "order": "+"}])
    assert up["features"][0]["id"] == 1
    down = p.query(sortby=[{"property": "id", "order": "-"}])
    assert down["features"][0]["id"] == 25

    name = p.query(sortby=[{"property": "name", "order": "+"}])
    assert name["features"][0]["properties"]["name"] == "Aral Sea"
    name = p.query(sortby=[{"property": "name", "order": "-"}])
    assert name["features"][0]["properties"]["name"] == "Vänern"


def test_query_skip_geometry(config):
    """Test query without geometry"""
    p = OracleProvider(config)
    result = p.query(skip_geometry=True)
    feature = result["features"][0]

    assert feature.get("geometry") is None


def test_query_hits(config):
    """Test query number of hits"""
    p = OracleProvider(config)
    result = p.query(bbox=[0, 0, 70, 60], resulttype="hits")

    assert result.get("numberMatched") == 5


def test_get(config):
    """Test simple get"""
    p = OracleProvider(config)
    result = p.get(5)

    assert result.get("id") == 5
    assert result.get("prev") == 4
    assert result.get("next") == 6


def test_get_with_extra_properties(config_extra_properties):
    """Test simple get"""
    p = OracleProvider(config_extra_properties)
    result = p.get(5)

    assert (
        result["properties"]["tooltip"] ==
        "Here the name is L. Erie!"
    )


def test_create(config, create_geojson):
    """Test simple create"""
    p = OracleProvider(config)
    result = p.create(create_geojson)

    assert result == 26

    data = p.get(26)

    assert data.get("properties").get("name") == "Lake Constance"


def test_update(config, update_geojson):
    """Test simple update"""
    p = OracleProvider(config)
    identifier = 26
    result = p.update(identifier, update_geojson)

    assert result

    data = p.get(identifier)

    assert data.get("properties").get("area") == 536000
    assert data.get("properties").get("volume") == 48000


def test_update_properties(config_properties, config, update_geojson):
    """
    Test update with filtered columnlist in configuration
    In this case, the columns area and volume shouldn't be updated!
    """
    p = OracleProvider(config_properties)
    identifier = 26

    update_geojson["properties"]["area"] = 42
    update_geojson["properties"]["volume"] = 42

    result = p.update(identifier, update_geojson)

    assert result

    p2 = OracleProvider(config)
    data = p2.get(identifier)

    assert data.get("properties").get("area") == 536000
    assert data.get("properties").get("volume") == 48000


def test_delete(config):
    """Test simple delete"""
    p = OracleProvider(config)
    identifier = 26

    result = p.delete(identifier)

    assert result

    down = p.query(sortby=[{"property": "id", "order": "-"}])
    assert down["features"][0]["id"] == 25


def test_query_sql_manipulator(config_manipulator):
    """Test SQL manipulator"""
    p = OracleProvider(config_manipulator)
    feature_collection = p.query()
    features = feature_collection.get("features")

    assert len(features) == 1
    assert features[0].get("id") == 10


def test_get_sql_manipulator(config_manipulator):
    """
    Test get with SQL manipulator that throws
    an authorization error.
    """
    p = OracleProvider(config_manipulator)

    with pytest.raises(Exception):
        p.get(5)


def test_create_sql_manipulator(config_manipulator, config, create_geojson):
    """
    Test create with SQL Manipulator call.
    Field name should be overwritten with the string "overwritten"
    """
    expected_identifier = 27

    p = OracleProvider(config_manipulator)
    result = p.create(create_geojson)

    assert result == expected_identifier

    p2 = OracleProvider(config)
    data = p2.get(expected_identifier)

    assert data.get("properties").get("name") == "overwritten"


def test_update_sql_manipulator(config_manipulator, config, update_geojson):
    """
    Test update with SQL Manipulator call
    Field names area and volume should be overwritten with the answer to
    life the universe and everything
    """
    identifier = 27

    p = OracleProvider(config_manipulator)
    result = p.update(identifier, update_geojson)

    assert result

    p2 = OracleProvider(config)
    data = p2.get(identifier)

    assert data.get("properties").get("area") == 42
    assert data.get("properties").get("volume") == 42


def test_delete_sql_manipulator(config_manipulator, config):
    """
    Test for delete with SQL Manipulator call
    Where clause is overwritten by the manipulator to not
    match to any record. No record should be deleted.
    """
    identifier = 27

    p = OracleProvider(config_manipulator)

    result = p.delete(identifier)

    assert not result

    p2 = OracleProvider(config)

    down = p2.query(sortby=[{"property": "id", "order": "-"}])
    assert down["features"][0]["id"] == identifier


def test_create_point(config, create_point_geojson):
    """Test simple create"""
    p = OracleProvider(config)
    result = p.create(create_point_geojson)

    assert result == 28

    data = p.get(28)

    assert data.get("geometry").get("type") == "Point"


def test_query_can_mandate_properties_which_are_not_returned(config):
    config = {
        **config,
        # 'name' has to be filtered, but only 'wiki_link' is returned
        "properties": ["id", "wiki_link"],
        "mandatory_properties": ["name"]
    }

    p = OracleProvider(config)
    result = p.query(properties=[("name", "Aral Sea")])

    (feature,) = result['features']
    # id is handled separately, so only wiki link and not name must be here
    assert feature['properties'].keys() == {"wiki_link"}


def test_query_mandatory_properties_must_be_specified(config):
    config = {
        **config,
        "mandatory_properties": ["name"]
    }

    p = OracleProvider(config)
    with pytest.raises(ProviderInvalidQueryError):
        p.query(properties=[("id", "123")])


@pytest.fixture()
def database_connection_pool(config_db_conn):
    os.environ["ORACLE_POOL_MIN"] = "2"  # noqa: F841
    os.environ["ORACLE_POOL_MAX"] = "10"  # noqa: F841
    yield
    if 'ORACLE_POOL_MIN' in os.environ:
        del os.environ["ORACLE_POOL_MIN"]
    if 'ORACLE_POOL_MAX' in os.environ:
        del os.environ["ORACLE_POOL_MAX"]


def test_oracle_pool(config_db_conn, database_connection_pool):
    """
    Test whether an oracle session pool is created when there are
    the required env variables.
    """
    db_conn = DatabaseConnection(**config_db_conn)
    assert db_conn.pool
    assert db_conn.pool.max == int(os.environ.get("ORACLE_POOL_MAX"))


def test_query_pool(config, database_connection_pool):
    """Test query using a DB Session Pool for a valid JSON object with geometry"""   # noqa
    # Run query test again with session pool
    test_query(config)
