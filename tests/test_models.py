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

from polyfactory.factories.dataclass_factory import DataclassFactory
from polyfactory.pytest_plugin import register_fixture

from pygeoapi.models.config import APIRules, APIRulesValidationError
from pygeoapi.models.openapi import OAPIFormat, SupportedFormats
from pygeoapi.models.provider.mvt import MVTTilesJson, VectorLayers
from pygeoapi.models.provider.base import (
    GeospatialDataType,
    LinkType,
    TileMatrixLimitsType,
    TileMatrixSetEnumType,
    TilePointType,
    TileSetMetadata,
    TwoDBoundingBoxType,
    StyleType,
    DataTypeEnum,
)


@register_fixture
class GeospatialDataTypeFactory(DataclassFactory[GeospatialDataType]):
    ...


def test_provider_base_geospatial_data_type(
        geospatial_data_type_factory: GeospatialDataTypeFactory
) -> None:
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
        with pytest.raises(ValueError, match='must be a'):
            OAPIFormat(root=42)

    def test_non_string_bool_raises(self):
        with pytest.raises(ValueError, match='must be a'):
            OAPIFormat(root=True)

    def test_non_string_none_raises(self):
        with pytest.raises(ValueError, match='must be a'):
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
            APIRulesValidationError, match='must be a str'
        ):
            APIRules(api_version=123)

    def test_non_string_url_prefix_raises(self):
        with pytest.raises(
            APIRulesValidationError, match='url_prefix must be a str'
        ):
            APIRules(api_version='1.0.0', url_prefix=42)

    def test_non_string_version_header_raises(self):
        with pytest.raises(
            APIRulesValidationError,
            match='version_header must be a str',
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


# Tile models dataclass tests

class TestTileMatrixSetEnumTypeValidation:
    """Test TileMatrixSetEnumType type validation."""

    def test_valid_creation(self):
        tms_enum = TileMatrixSetEnumType(
            tileMatrixSet='WebMercatorQuad',
            tileMatrixSetURI='http://example.com',
            crs='EPSG:3857',
            title='Web Mercator',
            orderedAxes=['X', 'Y'],
            wellKnownScaleSet='GoogleMaps',
            tileMatrices=[{'id': '0'}],
        )
        assert tms_enum.tileMatrixSet == 'WebMercatorQuad'

    def test_non_string_tileMatrixSet_raises(self):
        with pytest.raises(ValueError):
            TileMatrixSetEnumType(tileMatrixSet=123)

    def test_non_list_orderedAxes_raises(self):
        with pytest.raises(ValueError):
            TileMatrixSetEnumType(orderedAxes='X,Y')

    def test_model_dump(self):
        tms_enum = TileMatrixSetEnumType(
            tileMatrixSet='Test', crs='EPSG:4326',
            title='Test', tileMatrixSetURI='http://x',
            orderedAxes=['X', 'Y'],
            tileMatrices=[],
        )
        result = tms_enum.model_dump()
        assert result['tileMatrixSet'] == 'Test'
        assert result['crs'] == 'EPSG:4326'


class TestTileMatrixLimitsTypeValidation:
    """Test TileMatrixLimitsType type validation."""

    def test_valid_creation(self):
        tm_limits = TileMatrixLimitsType(
            tileMatrix='0', minTileRow=0,
            maxTileRow=1, minTileCol=0, maxTileCol=1,
        )
        assert tm_limits.tileMatrix == '0'

    def test_non_string_tileMatrix_raises(self):
        with pytest.raises(ValueError):
            TileMatrixLimitsType(tileMatrix=0)

    def test_non_int_minTileRow_raises(self):
        with pytest.raises(ValueError):
            TileMatrixLimitsType(
                tileMatrix='0', minTileRow='zero'
            )

    def test_model_dump(self):
        tm_limits = TileMatrixLimitsType(
            tileMatrix='0', minTileRow=0,
            maxTileRow=10, minTileCol=0, maxTileCol=10,
        )
        result = tm_limits.model_dump()
        assert result['maxTileRow'] == 10


class TestTwoDBoundingBoxTypeValidation:
    """Test TwoDBoundingBoxType type validation."""

    def test_valid_creation(self):
        bbox = TwoDBoundingBoxType(
            lowerLeft=[-180.0, -90.0],
            upperRight=[180.0, 90.0],
        )
        assert bbox.lowerLeft == [-180.0, -90.0]

    def test_non_list_lowerLeft_raises(self):
        with pytest.raises(ValueError):
            TwoDBoundingBoxType(lowerLeft='not a list')

    def test_non_optional_str_crs_raises(self):
        with pytest.raises(ValueError):
            TwoDBoundingBoxType(crs=42)

    def test_model_dump_exclude_none(self):
        bbox = TwoDBoundingBoxType(
            lowerLeft=[-180.0, -90.0],
            upperRight=[180.0, 90.0],
        )
        result = bbox.model_dump(exclude_none=True)
        assert 'crs' not in result


class TestLinkTypeValidation:
    """Test LinkType type validation."""

    def test_valid_creation(self):
        link = LinkType(
            href='http://example.com',
            rel='item',
            type_='application/json',
        )
        assert link.href == 'http://example.com'

    def test_non_string_href_raises(self):
        with pytest.raises(ValueError):
            LinkType(href=42)

    def test_non_string_rel_raises(self):
        with pytest.raises(ValueError):
            LinkType(href='http://x', rel=123)

    def test_non_int_length_raises(self):
        with pytest.raises(ValueError):
            LinkType(href='http://x', length='big')

    def test_model_dump_renames_type(self):
        link = LinkType(
            href='http://x', rel='item',
            type_='application/json',
        )
        result = link.model_dump(exclude_none=True)
        assert 'type' in result
        assert 'type_' not in result

    def test_model_dump_exclude_none(self):
        link = LinkType(href='http://x')
        result = link.model_dump(exclude_none=True)
        assert 'href' in result
        assert 'rel' not in result
        assert 'title' not in result


class TestGeospatialDataTypeValidation:
    """Test GeospatialDataType type validation."""

    def test_valid_creation(self):
        geo_dt = GeospatialDataType(
            id='layer1', title='Layer 1',
            dataType=DataTypeEnum.VECTOR,
        )
        assert geo_dt.id == 'layer1'

    def test_non_string_id_raises(self):
        with pytest.raises(ValueError):
            GeospatialDataType(id=123)

    def test_model_dump_enum_value(self):
        geo_dt = GeospatialDataType(
            id='layer1', dataType=DataTypeEnum.VECTOR,
        )
        result = geo_dt.model_dump(exclude_none=True)
        assert result['dataType'] == 'vector'


class TestStyleTypeValidation:
    """Test StyleType type validation."""

    def test_valid_creation(self):
        style = StyleType(id='default', title='Default')
        assert style.id == 'default'

    def test_non_string_id_raises(self):
        with pytest.raises(ValueError):
            StyleType(id=42)


class TestTilePointTypeValidation:
    """Test TilePointType type validation."""

    def test_valid_creation(self):
        tp = TilePointType(
            crs='EPSG:4326', tileMatrix='0',
            coordinates=[0.0, 0.0],
        )
        assert tp.crs == 'EPSG:4326'

    def test_non_string_crs_raises(self):
        with pytest.raises(ValueError):
            TilePointType(crs=42)

    def test_non_string_tileMatrix_raises(self):
        with pytest.raises(ValueError):
            TilePointType(crs='EPSG:4326', tileMatrix=0)


class TestTileSetMetadataValidation:
    """Test TileSetMetadata type validation."""

    def test_valid_creation(self):
        ts_meta = TileSetMetadata(
            title='Test', crs='EPSG:4326',
        )
        assert ts_meta.title == 'Test'

    def test_non_string_title_raises(self):
        with pytest.raises(ValueError):
            TileSetMetadata(title=42)

    def test_non_string_crs_raises(self):
        with pytest.raises(ValueError):
            TileSetMetadata(crs=123)

    def test_model_dump_renames_license(self):
        ts_meta = TileSetMetadata(license_='MIT')
        result = ts_meta.model_dump(exclude_none=True)
        assert 'license' in result
        assert 'license_' not in result

    def test_model_dump_nested_links(self):
        link = LinkType(
            href='http://x', rel='item',
            type_='application/json',
        )
        ts_meta = TileSetMetadata(links=[link])
        result = ts_meta.model_dump(exclude_none=True)
        assert isinstance(result['links'][0], dict)
        assert result['links'][0]['href'] == 'http://x'
        assert 'type' in result['links'][0]

    def test_model_dump_exclude_none(self):
        ts_meta = TileSetMetadata(title='Test')
        result = ts_meta.model_dump(exclude_none=True)
        assert 'title' in result
        assert 'description' not in result
        assert 'version' not in result


# MVT models dataclass tests

class TestVectorLayersValidation:
    """Test VectorLayers type validation."""

    def test_valid_creation(self):
        vector_lyr = VectorLayers(
            id='layer1', description='A layer',
            minzoom=0, maxzoom=14,
            fields={'name': 'String'},
        )
        assert vector_lyr.id == 'layer1'

    def test_non_string_id_raises(self):
        with pytest.raises(ValueError):
            VectorLayers(id=42)

    def test_non_int_minzoom_raises(self):
        with pytest.raises(ValueError):
            VectorLayers(id='layer1', minzoom='zero')

    def test_model_dump(self):
        vector_lyr = VectorLayers(
            id='layer1', minzoom=0, maxzoom=14,
        )
        result = vector_lyr.model_dump(exclude_none=True)
        assert result['id'] == 'layer1'
        assert result['minzoom'] == 0
        assert 'description' not in result

    def test_model_dump_all_fields(self):
        vector_lyr = VectorLayers(
            id='layer1', description='desc',
            minzoom=0, maxzoom=14,
            fields={'name': 'String'},
        )
        result = vector_lyr.model_dump()
        assert result['fields'] == {'name': 'String'}


class TestMVTTilesJsonValidation:
    """Test MVTTilesJson type validation."""

    def test_valid_creation_defaults(self):
        mvt_tj = MVTTilesJson()
        assert mvt_tj.tilejson == '3.0.0'
        assert mvt_tj.name is None

    def test_valid_creation_full(self):
        mvt_tj = MVTTilesJson(
            tilejson='3.0.0',
            name='test',
            tiles='http://example.com/{z}/{x}/{y}.pbf',
            minzoom=0, maxzoom=14,
            description='Test tileset',
        )
        assert mvt_tj.name == 'test'

    def test_non_string_tilejson_raises(self):
        with pytest.raises(ValueError):
            MVTTilesJson(tilejson=3)

    def test_non_string_name_raises(self):
        with pytest.raises(ValueError):
            MVTTilesJson(name=42)

    def test_non_int_minzoom_raises(self):
        with pytest.raises(ValueError):
            MVTTilesJson(minzoom='zero')

    def test_kwargs_from_dict(self):
        """Test instantiation from dict, as used in providers."""
        data = {
            'tilejson': '3.0.0',
            'name': 'test',
            'tiles': 'http://example.com/{z}/{x}/{y}.pbf',
        }
        mvt_tj = MVTTilesJson(**data)
        assert mvt_tj.name == 'test'

    def test_kwargs_ignores_unknown_keys(self):
        """Extra keys in JSON metadata are silently ignored."""
        data = {
            'tilejson': '3.0.0',
            'name': 'test',
            'version': 2,
            'format': 'pbf',
            'json': '{}',
        }
        mvt_tj = MVTTilesJson(**data)
        assert mvt_tj.name == 'test'
        assert not hasattr(mvt_tj, 'format')

    def test_str_to_int_coercion(self):
        """String zoom values are coerced to int."""
        mvt_tj = MVTTilesJson(minzoom='0', maxzoom='14')
        assert mvt_tj.minzoom == 0
        assert mvt_tj.maxzoom == 14

    def test_model_dump(self):
        mvt_tj = MVTTilesJson(
            name='test',
            tiles='http://example.com',
        )
        result = mvt_tj.model_dump()
        assert result['tilejson'] == '3.0.0'
        assert result['name'] == 'test'

    def test_model_dump_exclude_none(self):
        mvt_tj = MVTTilesJson()
        result = mvt_tj.model_dump(exclude_none=True)
        assert 'tilejson' in result
        assert 'name' not in result

    def test_model_dump_with_vector_layers(self):
        vector_lyr = VectorLayers(id='layer1', minzoom=0, maxzoom=14)
        mvt_tj = MVTTilesJson(vector_layers=[vector_lyr])
        result = mvt_tj.model_dump(exclude_none=True)
        assert isinstance(result['vector_layers'][0], dict)
        assert result['vector_layers'][0]['id'] == 'layer1'

    def test_field_assignment_after_creation(self):
        """Test that fields can be set after init,
        as done in mvt_tippecanoe.py."""
        mvt_tj = MVTTilesJson()
        mvt_tj.tiles = 'http://example.com'
        mvt_tj.vector_layers = [
            VectorLayers(id='l1', minzoom=0, maxzoom=5)
        ]
        assert mvt_tj.tiles == 'http://example.com'
        result = mvt_tj.model_dump(exclude_none=True)
        assert result['vector_layers'][0]['id'] == 'l1'
