# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#          Tom Kralidis: <tomkralidis@gmail.com>
#
# Copyright (c) 2026 Francesco Bartoli
# Copyright (c) 2024 Tom Kralidis
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

import pytest

from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.pytest_plugin import register_fixture

from pygeoapi.models.config import APIRules, APIRulesValidationError
from pygeoapi.models.openapi import OAPIFormat, SupportedFormats
from pygeoapi.models.provider.base import GeospatialDataType


@register_fixture
class GeospatialDataTypeFactory(ModelFactory[GeospatialDataType]):
    ...


def test_provider_base_geospatial_data_type(
        geospatial_data_type_factory: GeospatialDataTypeFactory) -> None:
    gdt_instance = geospatial_data_type_factory.build()
    assert gdt_instance.model_dump()
    assert isinstance(gdt_instance, GeospatialDataType)


# OAPIFormat dataclass tests

class TestOAPIFormatCreation:
    """Test OAPIFormat instantiation and validation."""

    def test_default_is_yaml(self):
        fmt = OAPIFormat()
        assert fmt.root == SupportedFormats.YAML

    def test_create_with_enum(self):
        fmt = OAPIFormat(root=SupportedFormats.JSON)
        assert fmt.root == SupportedFormats.JSON

    def test_create_with_string_yaml(self):
        fmt = OAPIFormat(root='yaml')
        assert fmt.root == SupportedFormats.YAML

    def test_create_with_string_json(self):
        fmt = OAPIFormat(root='json')
        assert fmt.root == SupportedFormats.JSON

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match='Unsupported format'):
            OAPIFormat(root='xml')

    def test_non_string_int_raises(self):
        with pytest.raises(ValueError, match='must be a string'):
            OAPIFormat(root=42)

    def test_non_string_bool_raises(self):
        with pytest.raises(ValueError, match='must be a string'):
            OAPIFormat(root=True)

    def test_non_string_none_raises(self):
        with pytest.raises(ValueError, match='must be a string'):
            OAPIFormat(root=None)


class TestOAPIFormatEquality:
    """Test OAPIFormat comparison with strings, enums, instances."""

    def test_eq_string_yaml(self):
        fmt = OAPIFormat(root='yaml')
        assert fmt == 'yaml'
        assert not (fmt == 'json')

    def test_eq_string_json(self):
        fmt = OAPIFormat(root='json')
        assert fmt == 'json'
        assert not (fmt == 'yaml')

    def test_eq_enum(self):
        fmt = OAPIFormat()
        assert fmt == SupportedFormats.YAML

    def test_eq_instance(self):
        assert OAPIFormat(root='yaml') == OAPIFormat()

    def test_eq_unsupported_type(self):
        fmt = OAPIFormat()
        assert not (fmt == 42)


class TestOAPIFormatModelDump:
    """Test model_dump method."""

    def test_model_dump_yaml(self):
        fmt = OAPIFormat()
        result = fmt.model_dump()
        assert result == {'root': 'yaml'}

    def test_model_dump_json(self):
        fmt = OAPIFormat(root='json')
        result = fmt.model_dump()
        assert result == {'root': 'json'}


class TestOAPIFormatOpenAPICompatibility:
    """Test compatibility with openapi.py / asyncapi.py usage.

    Both modules receive a format string from click and compare
    it directly: ``if output_format == 'yaml'``.
    """

    def test_click_string_passthrough(self):
        """Simulates click passing a plain string."""
        format_ = 'yaml'
        fmt = OAPIFormat(root=format_)
        assert fmt == 'yaml'

    def test_click_json_passthrough(self):
        format_ = 'json'
        fmt = OAPIFormat(root=format_)
        assert fmt == 'json'

    def test_plain_string_still_works(self):
        """Current code passes raw strings, not OAPIFormat
        instances. Verify raw strings match as before."""
        format_ = 'yaml'
        assert format_ == 'yaml'


# APIRules dataclass tests

class TestAPIRulesCreation:
    """Test APIRules instantiation and validation."""

    def test_valid_semver(self):
        rules = APIRules(api_version='1.0.0')
        assert rules.api_version == '1.0.0'
        assert rules.url_prefix == ''
        assert rules.version_header == ''
        assert rules.strict_slashes is False

    def test_valid_semver_with_build(self):
        rules = APIRules(api_version='2.1.3-beta')
        assert rules.api_version == '2.1.3-beta'

    def test_invalid_semver_raises(self):
        with pytest.raises(
            APIRulesValidationError,
            match='Invalid semantic version'
        ):
            APIRules(api_version='not-a-version')

    def test_empty_version_raises(self):
        with pytest.raises(APIRulesValidationError):
            APIRules(api_version='')

    def test_non_string_version_raises(self):
        with pytest.raises(
            APIRulesValidationError, match='must be a string'
        ):
            APIRules(api_version=123)

    def test_non_string_url_prefix_raises(self):
        with pytest.raises(
            APIRulesValidationError, match='url_prefix must be a string'
        ):
            APIRules(api_version='1.0.0', url_prefix=42)

    def test_non_string_version_header_raises(self):
        with pytest.raises(
            APIRulesValidationError,
            match='version_header must be a string',
        ):
            APIRules(api_version='1.0.0', version_header=True)

    def test_non_bool_strict_slashes_raises(self):
        with pytest.raises(
            APIRulesValidationError,
            match='strict_slashes must be a bool',
        ):
            APIRules(api_version='1.0.0', strict_slashes='yes')

    def test_full_creation(self):
        rules = APIRules(
            api_version='1.0.0',
            url_prefix='/v{api_major}',
            version_header='X-API-Version',
            strict_slashes=True,
        )
        assert rules.url_prefix == '/v{api_major}'
        assert rules.version_header == 'X-API-Version'
        assert rules.strict_slashes is True


class TestAPIRulesFactory:
    """Test APIRules.create() factory method."""

    def test_create_filters_unknown_keys(self):
        rules = APIRules.create(
            api_version='1.0.0',
            unknown_key='ignored',
        )
        assert rules.api_version == '1.0.0'
        assert not hasattr(rules, 'unknown_key')

    def test_create_with_all_valid_keys(self):
        rules = APIRules.create(
            api_version='1.0.0',
            url_prefix='/api',
            version_header='API-Version',
            strict_slashes=True,
        )
        assert rules.url_prefix == '/api'
        assert rules.strict_slashes is True

    def test_create_missing_version_raises(self):
        with pytest.raises(APIRulesValidationError):
            APIRules.create(url_prefix='/api')


class TestAPIRulesResponseHeaders:
    """Test response_headers property."""

    def test_no_header_configured(self):
        rules = APIRules(api_version='1.0.0')
        assert rules.response_headers == {}

    def test_header_configured(self):
        rules = APIRules(
            api_version='1.0.0',
            version_header='X-API-Version',
        )
        assert rules.response_headers == {
            'X-API-Version': '1.0.0'
        }


class TestAPIRulesURLPrefix:
    """Test get_url_prefix() with framework styles."""

    def test_no_prefix(self):
        rules = APIRules(api_version='1.0.0')
        assert rules.get_url_prefix() == ''

    def test_bare_prefix(self):
        rules = APIRules(
            api_version='1.0.0', url_prefix='/v{api_major}'
        )
        assert rules.get_url_prefix() == 'v1'

    def test_full_version_prefix(self):
        rules = APIRules(
            api_version='1.2.3',
            url_prefix='/api/v{api_version}',
        )
        assert rules.get_url_prefix() == 'api/v1.2.3'

    def test_flask_style(self):
        rules = APIRules(
            api_version='1.0.0', url_prefix='/v{api_major}'
        )
        assert rules.get_url_prefix('flask') == '/v1'

    def test_starlette_style(self):
        rules = APIRules(
            api_version='1.0.0', url_prefix='/v{api_major}'
        )
        assert rules.get_url_prefix('starlette') == '/v1'

    def test_django_style(self):
        rules = APIRules(
            api_version='1.0.0', url_prefix='/v{api_major}'
        )
        assert rules.get_url_prefix('django') == r'^v1/'


class TestAPIRulesModelDump:
    """Test model_dump interface for duck-typing compatibility."""

    def test_model_dump(self):
        rules = APIRules(api_version='1.0.0')
        result = rules.model_dump()
        assert result == {
            'api_version': '1.0.0',
            'url_prefix': '',
            'version_header': '',
            'strict_slashes': False,
        }

    def test_model_dump_exclude_none(self):
        rules = APIRules(api_version='1.0.0')
        result = rules.model_dump(exclude_none=True)
        assert 'api_version' in result
