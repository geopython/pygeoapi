# =================================================================
#
# Authors: Francesco Bartoli <francesco.bartoli@geobeyond.it>
#
# Copyright (c) 2026 Francesco Bartoli
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

"""Tests for dependency injection in plugin loading"""

import logging
from pathlib import Path
from unittest.mock import Mock

import pytest

from pygeoapi.plugin import PluginContext, load_plugin


@pytest.fixture
def geojson_config():
    """Fixture for GeoJSON provider config"""
    return {
        "name": "GeoJSON",
        "type": "feature",
        "data": str(Path(__file__).parent / "data" / "obs.geojson"),
        "id_field": "id",
    }


@pytest.fixture
def mock_logger():
    """Fixture for mock logger"""
    return Mock(spec=logging.Logger)


def test_load_plugin_legacy_without_context(geojson_config):
    """Test loading plugin without context (backwards compatibility)"""
    # This is the current behavior - should still work
    provider = load_plugin("provider", geojson_config)

    assert provider is not None
    assert provider.name == "GeoJSON"
    assert provider.type == "feature"


def test_load_plugin_with_context_none(geojson_config):
    """Test loading plugin with context=None (explicit)"""
    # Explicitly passing None should work like legacy mode
    provider = load_plugin("provider", geojson_config, context=None)

    assert provider is not None
    assert provider.name == "GeoJSON"


def test_load_plugin_with_context_minimal(geojson_config):
    """Test loading plugin with minimal context"""
    context = PluginContext(config=geojson_config)

    # Provider should load even if it doesn't support context
    # (will fall back to legacy constructor)
    provider = load_plugin("provider", geojson_config, context=context)

    assert provider is not None
    assert provider.name == "GeoJSON"


def test_load_plugin_with_context_logger(geojson_config, mock_logger):
    """Test loading plugin with context containing logger"""
    context = PluginContext(config=geojson_config, logger=mock_logger)

    provider = load_plugin("provider", geojson_config, context=context)

    assert provider is not None
    # Note: Current providers don't support context yet
    # This test verifies load_plugin handles context gracefully


def test_load_plugin_with_context_full(geojson_config, mock_logger):
    """Test loading plugin with full context"""
    context = PluginContext(
        config=geojson_config,
        logger=mock_logger,
        locales=["en", "it", "fr"],
        base_url="https://api.example.com",
    )

    provider = load_plugin("provider", geojson_config, context=context)

    assert provider is not None
    assert provider.name == "GeoJSON"


def test_load_plugin_invalid_plugin_type():
    """Test loading plugin with invalid type raises error"""
    config = {"name": "Test", "data": "test.json"}

    with pytest.raises(Exception):  # Should raise InvalidPluginError
        load_plugin("invalid_type", config)


def test_load_plugin_invalid_plugin_name():
    """Test loading plugin with invalid name raises error"""
    config = {
        "name": "NonExistentProvider",
        "type": "feature",
        "data": "test.json",
    }

    with pytest.raises(Exception):  # Should raise InvalidPluginError
        load_plugin("provider", config)


def test_load_plugin_multiple_providers_with_context(mock_logger):
    """Test loading multiple providers with different contexts"""
    # Create two different contexts
    context1 = PluginContext(
        config={
            "name": "GeoJSON",
            "type": "feature",
            "data": str(Path(__file__).parent / "data" / "obs.geojson"),
        },
        logger=mock_logger,
        base_url="https://api1.example.com",
    )

    context2 = PluginContext(
        config={
            "name": "CSV",
            "type": "feature",
            "data": str(Path(__file__).parent / "data" / "obs.csv"),
            "id_field": "id",
            "geometry": {"x_field": "long", "y_field": "lat"},
        },
        logger=mock_logger,
        base_url="https://api2.example.com",
    )

    # Load two providers with different contexts
    provider1 = load_plugin("provider", context1.config, context=context1)
    provider2 = load_plugin("provider", context2.config, context=context2)

    # Both should load successfully
    assert provider1.name == "GeoJSON"
    assert provider2.name == "CSV"

    # They should be different instances
    assert provider1 is not provider2


def test_load_plugin_process_without_context():
    """Test loading process without context (backwards compatibility)"""
    config = {"name": "HelloWorld"}

    processor = load_plugin("process", config)

    assert processor is not None


def test_load_plugin_process_with_context(mock_logger):
    """Test loading process with context"""
    context = PluginContext(config={"name": "HelloWorld"}, logger=mock_logger)

    processor = load_plugin("process", context.config, context=context)

    assert processor is not None


def test_load_plugin_process_manager_without_context():
    """Test loading process manager without context"""
    config = {"name": "Dummy"}

    manager = load_plugin("process_manager", config)

    assert manager is not None


def test_load_plugin_process_manager_with_context(mock_logger):
    """Test loading process manager with context"""
    context = PluginContext(config={"name": "Dummy"}, logger=mock_logger)

    manager = load_plugin("process_manager", context.config, context=context)

    assert manager is not None


def test_load_plugin_custom_plugin_with_dotted_path():
    """Test loading custom plugin using dotted path notation"""
    # This tests that context works with custom plugins too
    config = {
        "name": "pygeoapi.provider.geojson.GeoJSONProvider",
        "type": "feature",
        "data": str(Path(__file__).parent / "data" / "obs.geojson"),
    }

    context = PluginContext(config=config)
    provider = load_plugin("provider", config, context=context)

    assert provider is not None


def test_context_extensibility_in_plugin_loading(mock_logger):
    """Test that extended context works with load_plugin"""
    from dataclasses import dataclass
    from typing import Optional

    @dataclass
    class ExtendedContext(PluginContext):
        """Extended context for testing"""

        custom_field: Optional[str] = None

    config = {
        "name": "GeoJSON",
        "type": "feature",
        "data": str(Path(__file__).parent / "data" / "obs.geojson"),
    }

    context = ExtendedContext(
        config=config, logger=mock_logger, custom_field="test_value"
    )

    # Should work even with extended context
    provider = load_plugin("provider", config, context=context)

    assert provider is not None
    assert provider.name == "GeoJSON"


@pytest.mark.parametrize(
    "plugin_type,config",
    [
        (
            "provider",
            {"name": "GeoJSON", "type": "feature", "data": "test.geojson"},
        ),
        ("process", {"name": "HelloWorld"}),
        ("process_manager", {"name": "Dummy"}),
    ],
)
def test_load_plugin_context_backwards_compatible(
    plugin_type, config, mock_logger
):
    """Test that context doesn't break any plugin type"""
    context = PluginContext(config=config, logger=mock_logger)

    # Should load without errors (may fall back to legacy constructor)
    plugin = load_plugin(plugin_type, config, context=context)

    assert plugin is not None
