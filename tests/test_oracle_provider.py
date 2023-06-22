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
from pygeoapi.provider.oracle import OracleProvider

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
        bbox,
        source_crs,
        properties,
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

    def process_create(
        self,
        db,
        sql_query,
        bind_variables,
        sql_manipulator_options,
        request_data,
    ):
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
        return sql_query, bind_variables

    def process_delete(
        self,
        db,
        sql_query,
        bind_variables,
        sql_manipulator_options,
        identifier,
    ):
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
def config_manipulator():
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
        "sql_manipulator": "tests.test_oracle_provider.SqlManipulator",
        "sql_manipulator_options": {"foo": "bar"},
        "editable": True,
    }


@pytest.fixture()
def config_properties():
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
        "properties": ["id", "name", "wiki_link"],
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


def test_sql_manipulator(config_manipulator):
    """Test SQL manipulator"""
    p = OracleProvider(config_manipulator)
    feature_collection = p.query()
    features = feature_collection.get("features")

    assert len(features) == 1
    assert features[0].get("id") == 10


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


def test_get_fields_properties(config_properties):
    """Test get_fields"""
    expected_fields = {
        "id": {"type": "NUMBER"},
        "name": {"type": "VARCHAR2"},
        "wiki_link": {"type": "VARCHAR2"},
    }

    provider = OracleProvider(config_properties)
    provided_fields = provider.get_fields()
    print(provided_fields)

    assert provided_fields == expected_fields
    assert provider.fields == expected_fields


def test_query_with_property_filter(config):
    """Test query valid features when filtering by property"""
    p = OracleProvider(config)
    feature_collection = p.query(properties=[("name", "Aral Sea")])
    features = feature_collection.get("features")

    assert len(features) == 1
    assert features[0].get("id") == 12


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


def test_create(config, create_geojson):
    """Test create"""
    p = OracleProvider(config)
    result = p.create(create_geojson)

    assert result == 26


def test_update(config, update_geojson):
    """Test update"""
    p = OracleProvider(config)
    identifier = 26
    result = p.update(identifier, update_geojson)

    assert result

    data = p.get(identifier)

    print(data)

    assert data.get("properties").get("area") == 536000
    assert data.get("properties").get("volume") == 48000


def test_update_properties(config_properties, config, update_geojson):
    """
    Test update with filtered columnlist in configuration
    In this case, the columns area and volume cannot be updated!
    """
    p = OracleProvider(config_properties)
    identifier = 26

    update_geojson["properties"]["area"] = 4711
    update_geojson["properties"]["volume"] = 4711

    result = p.update(identifier, update_geojson)

    assert result

    p2 = OracleProvider(config)
    data = p2.get(identifier)

    print(data)

    assert data.get("properties").get("area") == 536000
    assert data.get("properties").get("volume") == 48000


def test_delete(config):
    """Simple test for delete"""
    p = OracleProvider(config)
    identifier = 26

    result = p.delete(identifier)

    assert result

    down = p.query(sortby=[{"property": "id", "order": "-"}])
    assert down["features"][0]["id"] == 25
