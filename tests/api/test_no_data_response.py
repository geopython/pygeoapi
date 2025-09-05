import pytest
from unittest.mock import MagicMock
from http import HTTPStatus
from pygeoapi.api import API
from pygeoapi.provider.base import ProviderNoDataError
from pygeoapi.api.itemtypes import get_collection_items
from pygeoapi.util import yaml_load
from tests.util import mock_api_request, get_test_file_path


@pytest.fixture()
def config():
    """Mock configuration"""

    return {
        "server": {"url": "http://localhost:5000", "language": "en-US"},
        "logging": {"level": "INFO"},
        "resources": {
            "test-collection": {
                "type": "collection",
                "extents": {
                    "spatial": {
                        "bbox": [-180, -90, 180, 90],
                        "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                    }
                },
                "providers": [
                    {"name": "dummy", "type": "feature", "data": "dummy_data"}
                ],
            }
        },
    }


@pytest.fixture()
def openapi():
    with open(get_test_file_path("pygeoapi-test-openapi.yml")) as fh:
        return yaml_load(fh)


def test_get_collection_items_no_data(config, openapi, monkeypatch):
    """Test that a ProviderNoDataError returns a 204 No Content"""

    # Mock the provider to raise ProviderNoDataError
    mock_provider = MagicMock()

    mock_provider.query.side_effect = ProviderNoDataError

    # Mock load_plugin to return our mock provider
    mock_load_plugin = MagicMock(return_value=mock_provider)

    monkeypatch.setattr("pygeoapi.api.itemtypes.load_plugin", mock_load_plugin)

    # Create an API instance
    api_ = API(config, openapi)

    req = mock_api_request()

    # Call the API function that should raise the error
    _, status_code, response_body = get_collection_items(
        api_, req, "test-collection"
    )

    assert status_code == HTTPStatus.NO_CONTENT

    assert response_body == "", "response body should be empty"
