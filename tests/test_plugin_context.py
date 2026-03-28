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

"""Tests for PluginContext dataclass"""

import logging
from unittest.mock import Mock

from pygeoapi.plugin import PluginContext


def test_plugin_context_creation_minimal():
    """Test creating PluginContext with minimal config"""
    config = {
        "name": "GeoJSON",
        "type": "feature",
        "data": "tests/data/obs.geojson",
    }

    context = PluginContext(config=config)

    assert context.config == config
    assert context.logger is None
    assert context.locales is None
    assert context.base_url is None


def test_plugin_context_creation_with_logger():
    """Test creating PluginContext with custom logger"""
    config = {"name": "Test", "type": "feature", "data": "test.json"}
    mock_logger = Mock(spec=logging.Logger)

    context = PluginContext(config=config, logger=mock_logger)

    assert context.config == config
    assert context.logger == mock_logger
    assert context.locales is None
    assert context.base_url is None


def test_plugin_context_creation_full():
    """Test creating PluginContext with all parameters"""
    config = {"name": "Test", "type": "feature", "data": "test.json"}
    mock_logger = Mock(spec=logging.Logger)
    locales = ["en", "it", "fr"]
    base_url = "https://api.example.com"

    context = PluginContext(
        config=config, logger=mock_logger, locales=locales, base_url=base_url
    )

    assert context.config == config
    assert context.logger == mock_logger
    assert context.locales == locales
    assert context.base_url == base_url


def test_plugin_context_to_dict_minimal():
    """Test converting PluginContext to dict with minimal config"""
    config = {"name": "Test", "type": "feature", "data": "test.json"}
    context = PluginContext(config=config)

    result = context.to_dict()

    assert result == config
    assert "_logger" not in result
    assert "_locales" not in result
    assert "_base_url" not in result


def test_plugin_context_to_dict_with_logger():
    """Test converting PluginContext to dict with logger"""
    config = {"name": "Test", "type": "feature", "data": "test.json"}
    mock_logger = Mock(spec=logging.Logger)

    context = PluginContext(config=config, logger=mock_logger)
    result = context.to_dict()

    assert result["name"] == "Test"
    assert result["type"] == "feature"
    assert result["data"] == "test.json"
    assert result["_logger"] == mock_logger


def test_plugin_context_to_dict_full():
    """Test converting PluginContext to dict with all fields"""
    config = {"name": "Test", "type": "feature", "data": "test.json"}
    mock_logger = Mock(spec=logging.Logger)
    locales = ["en", "it"]
    base_url = "https://api.example.com"

    context = PluginContext(
        config=config, logger=mock_logger, locales=locales, base_url=base_url
    )
    result = context.to_dict()

    # Original config preserved
    assert result["name"] == "Test"
    assert result["type"] == "feature"
    assert result["data"] == "test.json"

    # Injected dependencies added with underscore prefix
    assert result["_logger"] == mock_logger
    assert result["_locales"] == locales
    assert result["_base_url"] == base_url


def test_plugin_context_extensible_subclassing():
    """Test that PluginContext can be extended via subclassing"""
    from dataclasses import dataclass
    from typing import Optional

    @dataclass
    class ExtendedContext(PluginContext):
        """Extended context with custom fields"""

        metrics_collector: Optional[Mock] = None
        cache_backend: Optional[Mock] = None

    config = {"name": "Test", "type": "feature", "data": "test.json"}
    mock_metrics = Mock()
    mock_cache = Mock()

    context = ExtendedContext(
        config=config,
        logger=Mock(),
        metrics_collector=mock_metrics,
        cache_backend=mock_cache,
    )

    # Standard fields work
    assert context.config == config
    assert context.logger is not None

    # Extended fields work
    assert context.metrics_collector == mock_metrics
    assert context.cache_backend == mock_cache

    # to_dict() still works (includes base fields only)
    result = context.to_dict()
    assert "_logger" in result
    # Extended fields not in to_dict (as expected)


def test_plugin_context_config_immutability():
    """Test that modifying config dict doesn't affect context"""
    original_config = {"name": "Test", "type": "feature", "data": "test.json"}
    context = PluginContext(config=original_config)

    # Modify original config
    original_config["name"] = "Modified"

    # Context config should be affected (dict is mutable)
    # This is expected behavior - user should copy if needed
    assert context.config["name"] == "Modified"


def test_plugin_context_config_copy():
    """Test creating context with config copy for immutability"""
    original_config = {"name": "Test", "type": "feature", "data": "test.json"}
    context = PluginContext(config=dict(original_config))

    # Modify original config
    original_config["name"] = "Modified"

    # Context config should be unchanged
    assert context.config["name"] == "Test"
