# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
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

import os
import logging
import pytest
from pygeoapi.openapi import get_ogc_schemas_location
from pygeoapi.openapi import get_oas_30
from pygeoapi.util import (filter_dict_by_key_value,
                           yaml_load,
                           get_provider_by_type,
                           get_extension_by_type)

LOGGER = logging.getLogger(__name__)


def test_str2bool():
    """
    Get OGC schema location
    """

    default = {
        'url': 'http://localhost:5000'
    }

    osl = get_ogc_schemas_location(default)
    assert osl == 'http://schemas.opengis.net'

    default['ogc_schemas_location'] = 'http://example.org/schemas'
    osl = get_ogc_schemas_location(default)
    assert osl == 'http://example.org/schemas'

    default['ogc_schemas_location'] = '/opt/schemas.opengis.net'
    osl = get_ogc_schemas_location(default)


def get_test_file_path(filename):
    """
    Helper function to open test file safely

    :param filename: file path

    :returns: corrected file path
    """

    if os.path.isfile(filename):
        return filename
    return 'tests/{}'.format(filename)


@pytest.fixture()
def config():
    """
    Get the OpenAPI Document configuration

    :returns: OpenAPI configuration YAML dict
    """
    with open(get_test_file_path('pygeoapi-test-openapi-config.yml')) as config_file:  # noqa
        return yaml_load(config_file)


@pytest.fixture()
def get_oas_30_(config):
    """
    Get the generated OpenAPI 3.0 Document

    :param config: configuration object

    :returns: OpenAPI definition YAML dict
    """
    return get_oas_30(config)


@pytest.fixture()
def get_collections(config):
    """
    Get the collection resources from config file

    :param config: configuration object

    :returns: list of collection objects
    """
    collections = filter_dict_by_key_value(config['resources'], 'type', 'collection')  # noqa
    return collections


@pytest.fixture()
def get_cql_collections(get_collections):
    """
    Get dict for the collection resources with provider supporting cql or not

    :param get_collections: list of collection objects

    :returns: dict with resource supporting cql or not
    """
    cql_collections_dict = {}
    for k, _ in get_collections.items():
        providers = get_provider_by_type(get_collections[k]['providers'],
                                         'feature')
        cql_extension = get_extension_by_type(providers, 'CQL')
        cql_collections_dict[k] = cql_extension['filters']
    return cql_collections_dict


@pytest.fixture()
def is_cql(get_cql_collections):
    """
    Checks whether any colelction resource supports feature filter

    :param get_collections: collection object

    :returns: boolean value
    """
    for _, v in get_cql_collections.items():
        if v:
            return True
    return False


@pytest.fixture()
def get_cql_components(get_oas_30_):
    """
    Get the generated OpenAPI 3.0 Document

    :param get_oas_30_: OpenAPI 3.0 Document object

    :returns: OpenAPI Document components YAML dict
    """
    openapi_components = get_oas_30_.get('components', None)
    return openapi_components


@pytest.fixture()
def get_cql_schemas(get_cql_components):
    """
    Get the schemas from OpenAPI 3.0 Document

    :param get_cql_components: OpenAPI 3.0 Document components object

    :returns: OpenAPI Document schemas YAML dict
    """
    openapi_schemas = get_cql_components.get('schemas', None)
    return openapi_schemas


def test_cql_paths(config, get_oas_30_, get_collections,
                   is_cql, get_cql_collections):
    """
    Assertions for CQL paths in OpenAPI 3.0 Document

    :param config: configuration object
    :param get_oas_30_: OpenAPI 3.0 Document object
    :param get_collections: collection object
    :param is_cql: boolean value
    """
    assert isinstance(config, dict)
    assert isinstance(get_oas_30_, dict)

    cql_paths = get_oas_30_.get('paths', None)
    # assertion for get paths
    assert cql_paths is not None

    if is_cql:

        for k, _ in get_collections.items():
            references = []
            _k = '/collections/{}/items'.format(k)
            for items_parameters in cql_paths[_k]['get']['parameters']:  # noqa
                if '$ref' in items_parameters:
                    references.append(items_parameters['$ref'])
                if 'name' in items_parameters\
                        and items_parameters['name'] == 'filter-lang':
                    references.append(items_parameters['name'])
                    cql_lang = items_parameters['schema']['enum']
                    cql_lang_default = items_parameters['schema']['default']

            # if the resource support filter
            if get_cql_collections[k]:
                assert '#/components/parameters/filter' in references  # noqa
                assert 'filter-lang' in references  # noqa
                provider_filter_lang = get_cql_collections[k]
                assert cql_lang == provider_filter_lang
                assert 'cql-text' == cql_lang_default

            # if the resource does not support filter
            else:
                assert '#/components/parameters/filter' not in references  # noqa
                assert 'filter-lang' not in references  # noqa


def test_cql_filters_parameters(get_cql_components, is_cql):
    """
    Assertions for CQL parameters in OpenAPI 3.0 Document

    :param get_cql_components: OpenAPI 3.0 Document components
    :param is_cql: boolean value
    """
    if is_cql:

        cql_parameters = get_cql_components.get('parameters', None)

        # assertion for filter parameter
        openapi_filter = cql_parameters.get('filter', None)
        assert openapi_filter is not None

        # assertion for filter and filter-lang attributes
        param_attributes = ['name', 'in', 'description', 'required',
                            'schema', 'style', 'explode']
        for attributes in param_attributes:
            assert attributes in openapi_filter

        assert 'type' in openapi_filter['schema']
        assert openapi_filter['name'] == 'filter'
        assert openapi_filter['in'] == 'query'
        assert not openapi_filter['required']
        assert openapi_filter['schema']['type'] == 'string'


def test_cql_filters_logical_expressions(get_cql_schemas, is_cql):
    """
    Assertions for CQL logical expressions schema in OpenAPI 3.0 Document

    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for logical expressions
        assert 'logicalExpression' in get_cql_schemas is not None
        assert get_cql_schemas.get('logicalExpression') is not None

        logical_expressions = ['and', 'or', 'not']
        for logical_expression in logical_expressions:
            assert logical_expression in \
                   get_cql_schemas['logicalExpression']['properties']

        # assertion for the definition of different logical expressions
        for logical_expression in logical_expressions:
            assert logical_expression in get_cql_schemas is not None


def test_cql_filters_comparison_expressions(get_cql_schemas, is_cql):
    """
    Assertions for CQL comparison expressions schema in OpenAPI 3.0 Document

    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for comparison expressions
        assert 'comparisonExpressions' in get_cql_schemas is not None
        assert get_cql_schemas.get('comparisonExpressions', None) is not None

        comparison_expressions = ['eq', 'lt', 'gt', 'lte', 'gte',
                                  'between', 'like', 'in']
        for comparison_expression in comparison_expressions:
            assert comparison_expression in \
                   get_cql_schemas['comparisonExpressions']['properties']

        # assertion for the definition of different comparison expressions
        for comparison_expression in comparison_expressions:
            assert comparison_expression in get_cql_schemas is not None


def test_cql_filters_spatial_expressions(get_cql_schemas, is_cql):
    """
    Assertions for CQL spatial expressions schema in OpenAPI 3.0 Document

    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for spatial expressions
        assert 'spatialExpressions' in get_cql_schemas is not None
        assert get_cql_schemas.get('spatialExpressions', None) is not None

        spatial_expressions = ['equals', 'disjoint', 'touches',
                               'within', 'overlaps', 'crosses',
                               'intersects', 'contains']
        for spatial_expression in spatial_expressions:
            assert spatial_expression in \
                   get_cql_schemas['spatialExpressions']['properties']

        # assertion for the definition of different spatial expressions
        for spatial_expression in spatial_expressions:
            assert spatial_expression in get_cql_schemas is not None

        # assertion for spatial operands
        assert 'spatialOperands' in get_cql_schemas is not None
        assert get_cql_schemas.get('spatialOperands', None) is not None

        spatial_operands = ['property', 'function', 'value']
        for props in spatial_operands:
            assert props in get_cql_schemas['spatialOperands']['properties']


def test_cql_filters_temporal_expressions(get_cql_schemas, is_cql):
    """
    Assertions for CQL temporal expressions schema in OpenAPI 3.0 Document

    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for temporal expressions
        assert 'temporalExpressions' in get_cql_schemas is not None
        assert get_cql_schemas.get('temporalExpressions', None) is not None

        temporal_expressions = ['after', 'before', 'begins', 'begunby',
                                'tcontains', 'during', 'endedby', 'ends',
                                'tequals', 'meets', 'metby', 'toverlaps',
                                'overlappedby']
        for temporal_expression in temporal_expressions:
            assert temporal_expression in \
                   get_cql_schemas['temporalExpressions']['properties']

        # assertion for the definition of different temporal expressions
        for temporal_expression in temporal_expressions:
            assert temporal_expression in get_cql_schemas is not None

        # assertion for temporal operands
        assert 'temporalOperands' in get_cql_schemas is not None
        assert get_cql_schemas.get('temporalOperands', None) is not None

        temporal_operands = ['property', 'function', 'value']
        for props in temporal_operands:
            assert props in get_cql_schemas['temporalOperands']['properties']

        # assertion for temporal value definition
        assert 'temporalLiteral' in get_cql_schemas is not None
        assert 'timeLiteral' in get_cql_schemas is not None
        assert 'periodLiteral' in get_cql_schemas is not None


def test_cql_filters_arithmetic_operands(get_cql_schemas, is_cql):
    """
    Assertions for CQL arithmetic operands schema in OpenAPI 3.0 Document

    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for arithmetic operands
        assert 'arithmeticOperands' in get_cql_schemas is not None
        assert get_cql_schemas.get('arithmeticOperands', None) is not None

        arithmetic_operands = ['property', 'function', 'value',
                               '+', '-', '*', '/']
        for props in arithmetic_operands:
            assert props in get_cql_schemas['arithmeticOperands']['properties']

        # assertion for scalar operands
        assert 'scalarOperands' in get_cql_schemas is not None
        assert get_cql_schemas.get('scalarOperands', None) is not None

        scalar_operands = ['property', 'function', 'value', '+', '-', '*', '/']
        for props in scalar_operands:
            assert props in get_cql_schemas['scalarOperands']['properties']

        # assertion for +,-,*,/ definition
        arithmetic_operators = ['add', 'sub', 'mul', 'div']
        for arithmetic_operator in arithmetic_operators:
            assert arithmetic_operator in get_cql_schemas is not None

        # assertion for value definition
        assert 'scalarLiteral' in get_cql_schemas is not None


def test_cql_filters_functions(get_cql_schemas, is_cql):
    """
    Assertions for CQL functions schema in OpenAPI 3.0 Document

    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for functions
        assert 'function' in get_cql_schemas is not None
        assert get_cql_schemas.get('function', None) is not None

        function = ['name', 'arguments']
        for props in function:
            assert props in get_cql_schemas['function']['properties']


def test_cql_filters_function_obj_args(get_cql_schemas, is_cql):
    """
    Assertions for CQL function object arguments schema in OpenAPI 3.0 Document

    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for function Object Arguments
        assert 'functionObjectArgument' in get_cql_schemas is not None
        assert get_cql_schemas.get('functionObjectArgument', None) is not None

        function_object_argument = ['property', 'function',
                                    'geometry', 'bbox',
                                    'temporalValue', '+', '-',
                                    '*', '/']
        for props in function_object_argument:
            assert props in get_cql_schemas['functionObjectArgument']['properties']  # noqa

        # assertion for bbox
        assert 'bbox' in get_cql_schemas is not None
        # assertion for envelope definition
        assert 'envelopeLiteral' in get_cql_schemas is not None
        # assertion for geometry definition
        assert 'geometryLiteral' in get_cql_schemas is not None


def test_cql_filters_capabilities_assertion(get_cql_schemas, is_cql):
    """
    Assertions for CQL capabilities assertion schema in OpenAPI 3.0 Document

    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for capabilities assertion
        assert 'capabilities-assertion' in get_cql_schemas is not None
        assert get_cql_schemas.get('capabilities-assertion', None) is not None

        capabilities_assertion = ['name', 'operators', 'operands']
        for props in capabilities_assertion:
            assert props in get_cql_schemas['capabilities-assertion']['properties']  # noqa


def test_cql_filters_function_description(get_cql_schemas, is_cql):
    """
    Assertions for CQL function description schema in OpenAPI 3.0 Document

    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """

    if is_cql:
        # assertion for function description
        assert 'functionDescription' in get_cql_schemas is not None
        assert get_cql_schemas.get('functionDescription', None) is not None

        function_description = ['name', 'returns', 'arguments']
        for props in function_description:
            assert props in get_cql_schemas['functionDescription']['properties']  # noqa


def test_cql_filters_capabilities(get_cql_schemas, is_cql):
    """
    Assertions for CQL filter capabilities schema in OpenAPI 3.0 Document

    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for filter capabilities
        assert 'filter-capabilities' in get_cql_schemas is not None
        assert get_cql_schemas.get('filter-capabilities', None) is not None

        filter_capabilities = ['conformance-classes',
                               'capabilities', 'functions']
        for props in filter_capabilities:
            assert props in get_cql_schemas['filter-capabilities']['properties']  # noqa


def test_cql_queryables_path(get_oas_30_, get_collections, is_cql):
    """
    Assertions for queryable paths

    :param get_oas_30_: OpenAPI 3.0 Document object
    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    cql_paths = get_oas_30_.get('paths', None)

    if is_cql:
        # assertion for root queryables path
        assert '/queryables' in cql_paths is not None
        assert isinstance(cql_paths['/queryables'], dict)
    else:
        # assertion for non filter collections
        assert '/queryables' not in cql_paths

    # assertion for local queryables path
    for k, _ in get_collections.items():
        _k = '/collections/{}/queryables'.format(k)
        assert _k in cql_paths is not None
        assert isinstance(cql_paths[_k], dict)

        # assertion for queryables path attributes
        get_path_attributes = ['summary', 'description', 'tags', 'parameters', 'responses']  # noqa
        for get_path_attribute in get_path_attributes:
            if is_cql:
                # root queryables
                assert get_path_attribute in cql_paths['/queryables']['get']
            # local queryables
            assert get_path_attribute in cql_paths[_k]['get']  # noqa

        # assertion for queryables responses attributes
        responses = ['200', '400', '404', '500']
        for response in responses:
            if is_cql:
                # root queryables
                assert response in cql_paths['/queryables']['get']['responses']
            # local queryables
            assert response in \
                   cql_paths[_k]['get']['responses']  # noqa


def test_cql_queryables_response(get_cql_components, get_cql_schemas):
    """
    Assertions for queryable responses and schemas

    :param get_cql_components: OpenAPI 3.0 Document components
    :param get_collections: collection object
    :param is_cql: boolean value
    """
    cql_responses = get_cql_components.get('responses', None)
    # assertion for responses
    assert cql_responses is not None

    queryables_response = cql_responses.get('Queryables', None)
    # assertion for queryables response
    assert queryables_response is not None

    assert isinstance(queryables_response, dict)

    queryables_response_keys = ['description', 'content']
    # assertion for queryables response keys
    for queryables_response_key in queryables_response_keys:
        assert queryables_response_key in queryables_response

    # assertion for queryables schema reference
    queryables_response_schema = queryables_response['content']['application/json']['schema']['$ref']  # noqa
    assert '#/components/schemas/queryables' in queryables_response_schema

    queryables_schema = get_cql_schemas.get('queryables', None)
    # assertion for queryables schema
    assert queryables_schema is not None

    assert isinstance(queryables_schema, dict)

    queryables_schema_keys = ['type', 'required', 'properties']
    # assertion for queryables schema keys
    for queryables_schema_key in queryables_schema_keys:
        assert queryables_schema_key in queryables_schema

    # assertion for queryables schema properties
    assert 'queryables' in queryables_schema['properties']
    assert queryables_schema['properties']['queryables'].get('type', None) is not None  # noqa
    assert queryables_schema['properties']['queryables'].get('items', None) is not None  # noqa

    assert '#/components/schemas/queryable' in queryables_schema['properties']['queryables']['items']['$ref']  # noqa

    queryable_schema = get_cql_schemas.get('queryable', None)
    # assertion for queryable schema
    assert queryable_schema is not None

    assert isinstance(queryable_schema, dict)

    queryable_schema_keys = ['type', 'required', 'properties']
    # assertion for queryable schema keys
    for queryable_schema_key in queryable_schema_keys:
        assert queryable_schema_key in queryable_schema  # noqa

    # assertion for queryable schema properties
    queryable_schema_prop = queryable_schema['properties']

    params = ['queryable', 'title', 'description', 'language', 'type', 'type-ref']  # noqa
    for param in params:
        assert param in queryable_schema_prop
        param_props = ['description', 'type']
        for param_prop in param_props:
            assert param_prop in queryable_schema_prop[param]
            if param == 'language':
                assert 'default' in queryable_schema_prop[param]
            if param == 'type-ref':
                assert 'format' in queryable_schema_prop[param]
                assert queryable_schema_prop[param]['format'] == 'url'


def test_auxiliary_openapi_extensions(get_cql_components, get_cql_schemas, is_cql):  # noqa
    """
    Assertions for auxiliary extensions in OpenAPI 3.0 Document

    :param get_cql_components: OpenAPI 3.0 Document components
    :param get_cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    # assertion for components
    assert get_cql_components is not None

    # assertion for parameters
    assert get_cql_components.get('parameters', None) is not None

    # assertion for responses
    assert get_cql_components.get('responses', None) is not None

    # assertion for schemas
    assert get_cql_schemas is not None

    # assertion if filter is not supported
    if not is_cql:
        # assertion for non existance of filter parameters
        assert get_cql_components['parameters'].get('filter', None) is None
        assert get_cql_components['parameters'].get('filter-lang', None) is None  # noqa

        # assertion for non existance of filter schemas
        filter_schemas = ['predicates', 'logicalExpression',
                          'comparisonExpressions',
                          'spatialExpressions', 'temporalExpressions',
                          'and', 'or', 'not',
                          'eq', 'lt', 'gt', 'lte', 'gte', 'between',
                          'like', 'in', 'equals',
                          'disjoint', 'touches', 'within', 'overlaps',
                          'crosses', 'intersects',
                          'contains', 'after', 'before', 'begins',
                          'begunby', 'tcontains', 'during',
                          'endedby', 'ends', 'tequals', 'meets',
                          'metby', 'toverlaps', 'overlappedby',
                          'anyinteracts', 'tintersects',
                          'booleanOperands', 'arithmeticOperands',
                          'add', 'sub', 'mul', 'div',
                          'scalarOperands', 'spatialOperands',
                          'temporalOperands', 'function',
                          'functionObjectArgument', 'scalarLiteral',
                          'geometryLiteral', 'bbox',
                          'envelopeLiteral', 'temporalLiteral',
                          'timeLiteral', 'periodLiteral',
                          'capabilities-assertion', 'functionDescription',
                          'filter-capabilities']
        for filter in filter_schemas:
            assert get_cql_schemas.get(filter, None) is None
