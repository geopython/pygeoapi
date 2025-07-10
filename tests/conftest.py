# =================================================================
#
# Authors: Bernhard Mallinger <bernhard.mallinger@eox.at>
#
# Copyright (c) 2024 Bernhard Mallinger
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
import io
import json
import sys

import pytest

from pygeoapi.api import API
from pygeoapi.provider.base import BaseProvider, ProviderItemNotFoundError
from pygeoapi.util import yaml_load

from tests.util import get_test_file_path


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def openapi():
    with open(get_test_file_path('pygeoapi-test-openapi.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def api_(config, openapi):
    return API(config, openapi)


@pytest.fixture
def basic_provider_def():
    """Basic provider definition for testing."""
    return {
        "name": "test_provider",
        "type": "feature",
        "data": "/path/to/data.geojson"
    }


@pytest.fixture
def extended_provider_def():
    """Extended provider definition with all optional fields."""
    return {
        "name": "test_provider",
        "type": "feature",
        "data": "/path/to/data.geojson",
        "editable": True,
        "options": {"some_option": "value"},
        "id_field": "feature_id",
        "uri_field": "uri",
        "x_field": "longitude",
        "y_field": "latitude",
        "time_field": "timestamp",
        "title_field": "title",
        "properties": ["prop1", "prop2"],
        "file_types": [".geojson", ".json"]
    }


@pytest.fixture
def basic_provider(basic_provider_def):
    """Basic BaseProvider instance."""
    return BaseProvider(basic_provider_def)


@pytest.fixture
def extended_provider(extended_provider_def):
    """Extended BaseProvider instance."""
    return BaseProvider(extended_provider_def)


@pytest.fixture
def mock_provider_with_get():
    """Mock provider that implements get() method."""
    class MockProvider(BaseProvider):
        def get(self, identifier, **kwargs):
            if identifier == "mock_id":
                return {"type": "Feature", "id": identifier}
            else:
                raise ProviderItemNotFoundError("Not found")

    provider_def = {
        "name": "mock_provider",
        "type": "feature",
        "data": "/path/to/data.geojson"
    }
    return MockProvider(provider_def)


@pytest.fixture
def valid_geojson_item():
    """Valid GeoJSON item for testing."""
    return json.dumps({
        "type": "Feature",
        "id": "test_id",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"name": "Test Feature"}
    })


@pytest.fixture
def geojson_item_with_props_id():
    """GeoJSON item with identifier in properties."""
    return json.dumps({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"identifier": "props_id", "name": "Test"}
    })


@pytest.fixture
def remove_stdout():
    """Fixture to remove standard output during tests."""
    class RemoveStdout:
        def __enter__(self):
            self.original_stdout = sys.stdout
            sys.stdout = io.StringIO()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            sys.stdout = self.original_stdout

    return RemoveStdout
