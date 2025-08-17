# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2025 Francesco Bartoli
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

import json
from http import HTTPStatus

import pytest


from pygeoapi.provider.base import (
    BaseProvider, ProviderTypeError,
    ProviderItemNotFoundError, ProviderInvalidDataError,
    ProviderInvalidQueryError, ProviderRequestEntityTooLargeError,
    ProviderConnectionError, ProviderGenericError, ProviderQueryError,
    ProviderNoDataError, SchemaType
)


def test_valid_initialization(basic_provider_def):
    """Test BaseProvider initialization with valid config"""
    provider = BaseProvider(basic_provider_def)

    # Test required fields
    assert provider.name == "test_provider"
    assert provider.type == "feature"
    assert provider.data == "/path/to/data.geojson"


def test_initialization_with_optional_fields(extended_provider_def):
    """Test BaseProvider initialization with optional fields"""
    provider = BaseProvider(extended_provider_def)

    # Test required fields
    assert provider.name == "test_provider"
    assert provider.type == "feature"
    assert provider.data == "/path/to/data.geojson"

    # Test optional fields
    assert provider.editable is True
    assert provider.options == {"some_option": "value"}
    assert provider.id_field == "feature_id"
    assert provider.uri_field == "uri"
    assert provider.x_field == "longitude"
    assert provider.y_field == "latitude"
    assert provider.time_field == "timestamp"
    assert provider.title_field == "title"
    assert provider.properties == ["prop1", "prop2"]
    assert provider.file_types == [".geojson", ".json"]


def test_default_values(basic_provider):
    """Test default values for optional fields"""
    # Test default values
    assert basic_provider.editable is False
    assert basic_provider.options is None
    assert basic_provider.id_field is None
    assert basic_provider.uri_field is None
    assert basic_provider.x_field is None
    assert basic_provider.y_field is None
    assert basic_provider.time_field is None
    assert basic_provider.title_field is None
    assert basic_provider.properties == []
    assert basic_provider.file_types == []
    assert basic_provider._fields == {}
    assert basic_provider.filename is None
    assert basic_provider.axes == []
    assert basic_provider.crs is None
    assert basic_provider.num_bands is None


@pytest.mark.parametrize("missing_field,config", [
    ("name", {"type": "feature", "data": "/path"}),
    ("type", {"name": "test", "data": "/path"}),
    ("data", {"name": "test", "type": "feature"}),
    ("all", {})
])
def test_missing_required_fields(missing_field, config):
    """Test that missing required fields raise RuntimeError"""
    with pytest.raises(RuntimeError, match="name/type/data are required"):
        BaseProvider(config)


def test_repr_method(basic_provider):
    """Test __repr__ method"""
    assert repr(basic_provider) == "<BaseProvider> feature"


# Test Functions for BaseProvider Methods

def test_get_fields_not_implemented(basic_provider):
    """Test that get_fields raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        basic_provider.get_fields()


@pytest.mark.parametrize("schema_type", [
    None,  # Default
    SchemaType.item,
    SchemaType.create,
    SchemaType.update,
    SchemaType.replace
])
def test_get_schema_not_implemented(basic_provider, schema_type):
    """Test that get_schema raises NotImplementedError."""
    if schema_type is None:
        with pytest.raises(NotImplementedError):
            basic_provider.get_schema()
    else:
        with pytest.raises(NotImplementedError):
            basic_provider.get_schema(schema_type)


def test_get_data_path_not_implemented(basic_provider):
    """Test that get_data_path raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        basic_provider.get_data_path("http://example.com", "/path", "/dir")


def test_get_metadata_not_implemented(basic_provider):
    """Test that get_metadata raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        basic_provider.get_metadata()


@pytest.mark.parametrize("properties,current", [
    ([], False),  # Default
    (["prop1", "prop2"], True),
    ([], True),
    (["prop1"], False)
])
def test_get_domains_not_implemented(basic_provider, properties, current):
    """Test that get_domains raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        basic_provider.get_domains(properties, current)


def test_query_not_implemented(basic_provider):
    """Test that query raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        basic_provider.query()


@pytest.mark.parametrize("identifier,kwargs", [
    ("test_id", {}),
    ("test_id", {"some_param": "value"}),
    ("another_id", {"param1": "value1", "param2": "value2"})
])
def test_get_not_implemented(basic_provider, identifier, kwargs):
    """Test that get raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        basic_provider.get(identifier, **kwargs)


def test_create_not_implemented(basic_provider):
    """Test that create raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        basic_provider.create({"type": "Feature"})


def test_update_not_implemented(basic_provider):
    """Test that update raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        basic_provider.update("test_id", {"type": "Feature"})


def test_delete_not_implemented(basic_provider):
    """Test that delete raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        basic_provider.delete("test_id")


def test_fields_property_with_empty_fields(basic_provider):
    """Test fields property when _fields is empty."""

    result = basic_provider.fields
    assert result == {}
    assert result is basic_provider._fields


def test_fields_property_with_populated_fields(basic_provider):
    """Test fields property when _fields is populated."""
    # Populate _fields manually
    test_fields = {
        'id': {'type': 'string'},
        'name': {'type': 'string'},
        'geometry': {'type': 'geometry'}
    }
    basic_provider._fields = test_fields
    assert basic_provider.fields == test_fields


def test_fields_property_without_fields_attribute():
    """Test fields property when _fields attribute doesn't exist."""
    # Delete _fields to simulate NotImplementedError
    provider_def = {
        'name': 'test_provider',
        'type': 'feature',
        'data': '/path/to/data.geojson'
    }
    provider = BaseProvider(provider_def)
    delattr(provider, '_fields')
    assert not hasattr(provider, '_fields')

    # get_fields() gets called and raises NotImplementedError
    with pytest.raises(NotImplementedError):
        _ = provider.fields


def test_load_and_prepare_item_valid_geojson(
    mock_provider_with_get, valid_geojson_item, remove_stdout
):
    """Test loading valid GeoJSON item."""
    with remove_stdout():
        identifier, data = mock_provider_with_get._load_and_prepare_item(
            valid_geojson_item)

        assert identifier == "test_id"
        assert data["type"] == "Feature"
        assert data["id"] == "test_id"
        assert "geometry" in data
        assert "properties" in data


def test_load_and_prepare_item_identifier_in_properties(
    mock_provider_with_get, geojson_item_with_props_id, remove_stdout
):
    """Test loading item with identifier in properties."""
    with remove_stdout():
        identifier, data = mock_provider_with_get._load_and_prepare_item(
            geojson_item_with_props_id)

        assert identifier == "props_id"
        assert data["properties"]["identifier"] == "props_id"


def test_load_and_prepare_item_invalid_json(
    mock_provider_with_get, remove_stdout
):
    """Test loading invalid JSON."""
    invalid_json = "{ invalid json }"

    with remove_stdout():
        with pytest.raises(
            ProviderInvalidDataError,
            match="Invalid JSON data"
        ):
            mock_provider_with_get._load_and_prepare_item(invalid_json)


def test_load_and_prepare_item_invalid_data_type(
    mock_provider_with_get, remove_stdout
):
    """Test loading invalid data type."""
    with remove_stdout():
        with pytest.raises(ProviderInvalidDataError, match="Invalid data"):
            mock_provider_with_get._load_and_prepare_item(123)


def test_load_and_prepare_item_missing_identifier(
    mock_provider_with_get, remove_stdout
):
    """Test loading item without identifier."""
    item_no_id = json.dumps({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"name": "Test Feature"}
    })

    with remove_stdout():
        with pytest.raises(
            ProviderInvalidDataError,
            match="Missing identifier \\(id or properties.identifier\\)"
        ):
            mock_provider_with_get._load_and_prepare_item(item_no_id)


def test_load_and_prepare_item_accept_missing_identifier(
    mock_provider_with_get, remove_stdout
):
    """Test loading item without identifier when accepting missing."""
    item_no_id = json.dumps({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"name": "Test Feature"}
    })

    with remove_stdout():
        identifier, data = mock_provider_with_get._load_and_prepare_item(
            item_no_id,
            accept_missing_identifier=True
        )

        assert identifier is None
        assert data["type"] == "Feature"


@pytest.mark.parametrize("item_data", [
    {
        "type": "Feature",
        "id": "test_id",
        "properties": {"name": "Test Feature"}
    },
    {
        "type": "Feature",
        "id": "test_id",
        "geometry": {"type": "Point", "coordinates": [0, 0]}
    }
])
def test_load_and_prepare_item_missing_geojson_parts(
    mock_provider_with_get, item_data, remove_stdout
):
    """Test loading item without required GeoJSON parts."""
    item_json = json.dumps(item_data)

    with remove_stdout():
        with pytest.raises(
            ProviderInvalidDataError,
            match="Missing core GeoJSON geometry or properties"
        ):
            mock_provider_with_get._load_and_prepare_item(item_json)


# Test Functions for Provider Exceptions

@pytest.mark.parametrize("exception_class,expected_msg", [
    (ProviderGenericError, "generic error (check logs)"),
    (ProviderConnectionError, "connection error (check logs)"),
    (ProviderTypeError, "invalid provider type"),
    (ProviderInvalidQueryError, "query error"),
    (ProviderQueryError, "query error (check logs)"),
    (ProviderItemNotFoundError, "identifier not found"),
    (ProviderNoDataError, "No data found")
])
def test_provider_exceptions_default_messages(exception_class, expected_msg):
    """Test provider exception default messages."""
    error = exception_class()
    assert error.default_msg == expected_msg


@pytest.mark.parametrize("exception_class,expected_code", [
    (ProviderTypeError, HTTPStatus.BAD_REQUEST),
    (ProviderInvalidQueryError, HTTPStatus.BAD_REQUEST),
    (ProviderItemNotFoundError, HTTPStatus.NOT_FOUND),
    (ProviderNoDataError, HTTPStatus.NO_CONTENT),
    (ProviderRequestEntityTooLargeError, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
])
def test_provider_exceptions_http_status_codes(exception_class, expected_code):
    """Test provider exception HTTP status codes."""
    error = exception_class()
    assert error.http_status_code == expected_code


@pytest.mark.parametrize("exception_class,expected_code", [
    (ProviderInvalidQueryError, "InvalidQuery"),
    (ProviderItemNotFoundError, "NotFound"),
    (ProviderNoDataError, "InvalidParameterValue")
])
def test_provider_exceptions_status_codes(exception_class, expected_code):
    """Test provider exception status codes"""
    error = exception_class()
    assert error.ogc_exception_code == expected_code


def test_provider_request_entity_too_large_error_with_message():
    """Test ProviderRequestEntityTooLargeError with message."""
    error = ProviderRequestEntityTooLargeError("Too large")
    assert error.http_status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE


@pytest.mark.parametrize("schema_type,expected_value", [
    (SchemaType.item, "item"),
    (SchemaType.create, "create"),
    (SchemaType.update, "update"),
    (SchemaType.replace, "replace")
])
def test_schema_type_values(schema_type, expected_value):
    """Test SchemaType enum values."""
    assert schema_type.value == expected_value


def test_unique_subclass_query_types():
    from pygeoapi.provider.base_edr import BaseEDRProvider
    assert BaseEDRProvider.query_types == []

    from pygeoapi.provider.xarray_edr import XarrayEDRProvider
    assert BaseEDRProvider.query_types != XarrayEDRProvider.query_types
    assert XarrayEDRProvider.query_types == ['position', 'cube']

    from pygeoapi.provider.sensorthings_edr import SensorThingsEDRProvider
    assert BaseEDRProvider.query_types != SensorThingsEDRProvider.query_types
    assert SensorThingsEDRProvider.query_types == \
        ['items', 'locations', 'cube', 'area']
