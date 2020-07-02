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
from pygeoapi.util import filter_dict_by_key_value, yaml_load


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
    with open(get_test_file_path('pygeoapi-test-openapi-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def get_oas_30_(config):
    """
    Get the generated OpenAPI 3.0 Document

    :param config: configuration object

    :returns: OpenAPI definition YAML dict
    """
    return get_oas_30(config)


@pytest.fixture()
def is_cql(config):
    """
    Checks whether any resource supports feature filter

    :param config: configuration object

    :returns: Boolean value
    """
    collections = filter_dict_by_key_value(config['resources'],
                                           'type', 'collection')
    for k, _ in collections.items():
        if 'filters' in collections[k]:
            return True
    return False


@pytest.fixture()
def cql_components(get_oas_30_):
    """
    Get the generated OpenAPI 3.0 Document

    :param get_oas_30_: OpenAPI 3.0 Document object

    :returns: OpenAPI Document components YAML dict
    """
    openapi_components = get_oas_30_.get('components', None)
    return openapi_components


@pytest.fixture()
def cql_schemas(cql_components):
    """
    Get the schemas from OpenAPI 3.0 Document

    :param cql_components: OpenAPI 3.0 Document components object

    :returns: OpenAPI Document schemas YAML dict
    """
    openapi_schemas = cql_components.get('schemas', None)
    return openapi_schemas


@pytest.fixture()
def cql_parameters(cql_components):
    """
    Get the parameters from OpenAPI 3.0 Document

    :param cql_components: OpenAPI 3.0 Document components object

    :returns: OpenAPI Document parameters YAML dict
    """
    openapi_parameters = cql_components.get('parameters', None)
    return openapi_parameters


@pytest.fixture()
def cql_responses(cql_components):
    """
    Get the responses from OpenAPI 3.0 Document

    :param cql_components: OpenAPI 3.0 Document components object

    :returns: OpenAPI Document responses YAML dict
    """
    openapi_responses = cql_components.get('responses', None)
    return openapi_responses


@pytest.fixture()
def cql_paths(get_oas_30_):
    """
    Get the paths from OpenAPI 3.0 Document

    :param get_oas_30_: OpenAPI 3.0 Document object

    :returns: OpenAPI Document paths YAML dict
    """
    openapi_paths = get_oas_30_.get('paths', None)
    return openapi_paths


def test_dict(config, get_oas_30_):
    """
    Added assertions for YAML dictionaries

    :param config: configuration object
    :param get_oas_30_: OpenAPI 3.0 Document object
    """
    assert isinstance(config, dict)
    assert isinstance(get_oas_30_, dict)


def test_cql_filters(is_cql, cql_components, cql_responses,
                     cql_parameters, cql_schemas):
    """
    Assertions for CQL extension in OpenAPI 3.0 Document

    :param is_cql: boolean value
    :param cql_components: OpenAPI 3.0 Document components
    :param cql_responses: OpenAPI 3.0 Document responses
    :param cql_parameters: OpenAPI 3.0 Document responses
    :param cql_schemas: OpenAPI 3.0 Document responses
    """
    if is_cql:
        # assertion for components
        assert cql_components is not None

        # assertion for responses
        assert cql_responses is not None

        # assertion for parameters
        assert cql_parameters is not None

        # assertion for cql schemas
        assert cql_schemas is not None


def test_cql_paths(config, cql_paths, is_cql):
    """
    Assertions for CQL paths in OpenAPI 3.0 Document

    :param config: configuration object
    :param cql_paths: OpenAPI 3.0 Document paths
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for get paths
        assert cql_paths is not None

        # assertion for queryables paths
        assert '/queryables' in cql_paths is not None

        assert isinstance(cql_paths['/queryables'], dict)

        collections = filter_dict_by_key_value(config['resources'],
                                               'type', 'collection')

        for k, _ in collections.items():
            if 'filters' in collections[k]:
                references = []
                for items_parameters in \
                        cql_paths['/collections/' + k +
                                  '/items']['get']['parameters']:

                    if '$ref' in items_parameters:
                        references.append(items_parameters['$ref'])

                assert '#/components/parameters/filter' in references is not None # noqa
                assert '#/components/parameters/filter-lang' in references is not None # noqa

            assert isinstance(cql_paths['/collections/'+k+'/queryables'], dict)

            # assertion for queryables path attributes
            get_path_attributes = ['summary', 'description', 'tags',
                                   'parameters', 'responses']
            for get_path_attribute in get_path_attributes:
                assert get_path_attribute in cql_paths['/queryables']['get']
                assert get_path_attribute in \
                    cql_paths['/collections/'+k+'/queryables']['get']

            # assertion for queryables response attributes
            responses = [200, 400, 404, 500]
            for response in responses:
                assert response in cql_paths['/queryables']['get']['responses']
                assert response in \
                    cql_paths['/collections/' + k +
                              '/queryables']['get']['responses']


def test_cql_queryables(cql_responses, cql_schemas, is_cql):
    """
    Assertions for CQL queryables in OpenAPI 3.0 Document

    :param cql_responses: OpenAPI 3.0 Document responses
    :param cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for Queryables response
        assert 'Queryables' in cql_responses is not None

        # assertion for queryables schema
        assert 'queryables' in cql_schemas is not None


def test_cql_filters_parameters(cql_parameters, is_cql):
    """
    Assertions for CQL parameters in OpenAPI 3.0 Document

    :param cql_parameters: OpenAPI 3.0 Document parameters
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for filter-lang parameter
        openapi_filter_lang = cql_parameters.get('filter-lang', None)
        assert openapi_filter_lang is not None

        # assertion for filter parameter
        openapi_filter = cql_parameters.get('filter', None)
        assert openapi_filter is not None

        # assertion for filter and filter-lang attributes
        param_attributes = ['name', 'in', 'description', 'required',
                            'schema', 'style', 'explode']
        for attributes in param_attributes:
            assert attributes in openapi_filter_lang
            assert attributes in openapi_filter

        filter_lang_schemas = ['type', 'default', 'enum']
        for filter_lang_schema in filter_lang_schemas:
            assert filter_lang_schema in openapi_filter_lang['schema']
        assert openapi_filter_lang['name'] == 'filter-lang'
        assert openapi_filter_lang['in'] == 'query'
        assert not openapi_filter_lang['required']
        assert openapi_filter_lang['schema']['type'] == 'string'
        assert openapi_filter_lang['schema']['default'] == 'cql-text'
        assert openapi_filter_lang['schema']['enum'] == ['cql-text',
                                                         'cql-json']
        assert 'type' in openapi_filter['schema']
        assert openapi_filter['name'] == 'filter'
        assert openapi_filter['in'] == 'query'
        assert not openapi_filter['required']
        assert openapi_filter['schema']['type'] == 'string'


def test_cql_filters_logical_expressions(cql_schemas, is_cql):
    """
    Assertions for CQL logical expressions schema in OpenAPI 3.0 Document

    :param cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for logical expressions
        assert 'logicalExpression' in cql_schemas is not None
        assert cql_schemas.get('logicalExpression') is not None

        logical_expressions = ['and', 'or', 'not']
        for logical_expression in logical_expressions:
            assert logical_expression in \
                   cql_schemas['logicalExpression']['properties']

        # assertion for the definition of different logical expressions
        for logical_expression in logical_expressions:
            assert logical_expression in cql_schemas is not None


def test_cql_filters_comparison_expressions(cql_schemas, is_cql):
    """
    Assertions for CQL comparison expressions schema in OpenAPI 3.0 Document

    :param cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for comparison expressions
        assert 'comparisonExpressions' in cql_schemas is not None
        assert cql_schemas.get('comparisonExpressions', None) is not None

        comparison_expressions = ['eq', 'lt', 'gt', 'lte', 'gte',
                                  'between', 'like', 'in']
        for comparison_expression in comparison_expressions:
            assert comparison_expression in \
                   cql_schemas['comparisonExpressions']['properties']

        # assertion for the definition of different comparison expressions
        for comparison_expression in comparison_expressions:
            assert comparison_expression in cql_schemas is not None


def test_cql_filters_spatial_expressions(cql_schemas, is_cql):
    """
    Assertions for CQL spatial expressions schema in OpenAPI 3.0 Document

    :param cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for spatial expressions
        assert 'spatialExpressions' in cql_schemas is not None
        assert cql_schemas.get('spatialExpressions', None) is not None

        spatial_expressions = ['equals', 'disjoint', 'touches',
                               'within', 'overlaps', 'crosses',
                               'intersects', 'contains']
        for spatial_expression in spatial_expressions:
            assert spatial_expression in \
                   cql_schemas['spatialExpressions']['properties']

        # assertion for the definition of different spatial expressions
        for spatial_expression in spatial_expressions:
            assert spatial_expression in cql_schemas is not None

        # assertion for spatial operands
        assert 'spatialOperands' in cql_schemas is not None
        assert cql_schemas.get('spatialOperands', None) is not None

        spatial_operands = ['property', 'function', 'value']
        for props in spatial_operands:
            assert props in cql_schemas['spatialOperands']['properties']


def test_cql_filters_temporal_expressions(cql_schemas, is_cql):
    """
    Assertions for CQL temporal expressions schema in OpenAPI 3.0 Document

    :param cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for temporal expressions
        assert 'temporalExpressions' in cql_schemas is not None
        assert cql_schemas.get('temporalExpressions', None) is not None

        temporal_expressions = ['after', 'before', 'begins', 'begunby',
                                'tcontains', 'during', 'endedby', 'ends',
                                'tequals', 'meets', 'metby', 'toverlaps',
                                'overlappedby']
        for temporal_expression in temporal_expressions:
            assert temporal_expression in \
                   cql_schemas['temporalExpressions']['properties']

        # assertion for the definition of different temporal expressions
        for temporal_expression in temporal_expressions:
            assert temporal_expression in cql_schemas is not None

        # assertion for temporal operands
        assert 'temporalOperands' in cql_schemas is not None
        assert cql_schemas.get('temporalOperands', None) is not None

        temporal_operands = ['property', 'function', 'value']
        for props in temporal_operands:
            assert props in cql_schemas['temporalOperands']['properties']

        # assertion for temporal value definition
        assert 'temporalLiteral' in cql_schemas is not None
        assert 'timeLiteral' in cql_schemas is not None
        assert 'periodLiteral' in cql_schemas is not None


def test_cql_filters_arithmetic_operands(cql_schemas, is_cql):
    """
    Assertions for CQL arithmetic operands schema in OpenAPI 3.0 Document

    :param cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for arithmetic operands
        assert 'arithmeticOperands' in cql_schemas is not None
        assert cql_schemas.get('arithmeticOperands', None) is not None

        arithmetic_operands = ['property', 'function', 'value',
                               '+', '-', '*', '/']
        for props in arithmetic_operands:
            assert props in cql_schemas['arithmeticOperands']['properties']

        # assertion for scalar operands
        assert 'scalarOperands' in cql_schemas is not None
        assert cql_schemas.get('scalarOperands', None) is not None

        scalar_operands = ['property', 'function', 'value', '+', '-', '*', '/']
        for props in scalar_operands:
            assert props in cql_schemas['scalarOperands']['properties']

        # assertion for +,-,*,/ definition
        arithmetic_operators = ['add', 'sub', 'mul', 'div']
        for arithmetic_operator in arithmetic_operators:
            assert arithmetic_operator in cql_schemas is not None

        # assertion for value definition
        assert 'scalarLiteral' in cql_schemas is not None


def test_cql_filters_functions(cql_schemas, is_cql):
    """
    Assertions for CQL functions schema in OpenAPI 3.0 Document

    :param cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for functions
        assert 'function' in cql_schemas is not None
        assert cql_schemas.get('function', None) is not None

        function = ['name', 'arguments']
        for props in function:
            assert props in cql_schemas['function']['properties']


def test_cql_filters_function_obj_args(cql_schemas, is_cql):
    """
    Assertions for CQL function object arguments schema in OpenAPI 3.0 Document

    :param cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for function Object Arguments
        assert 'functionObjectArgument' in cql_schemas is not None
        assert cql_schemas.get('functionObjectArgument', None) is not None

        function_object_argument = ['property', 'function',
                                    'geometry', 'bbox',
                                    'temporalValue', '+', '-',
                                    '*', '/']
        for props in function_object_argument:
            assert props in cql_schemas['functionObjectArgument']['properties']

        # assertion for bbox
        assert 'bbox' in cql_schemas is not None
        # assertion for envelope definition
        assert 'envelopeLiteral' in cql_schemas is not None
        # assertion for geometry definition
        assert 'geometryLiteral' in cql_schemas is not None


def test_cql_filters_capabilities_assertion(cql_schemas, is_cql):
    """
    Assertions for CQL capabilities assertion schema in OpenAPI 3.0 Document

    :param cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for capabilities assertion
        assert 'capabilities-assertion' in cql_schemas is not None
        assert cql_schemas.get('capabilities-assertion', None) is not None

        capabilities_assertion = ['name', 'operators', 'operands']
        for props in capabilities_assertion:
            assert props in cql_schemas['capabilities-assertion']['properties']


def test_cql_filters_function_description(cql_schemas, is_cql):
    """
    Assertions for CQL function description schema in OpenAPI 3.0 Document

    :param cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """

    if is_cql:
        # assertion for function description
        assert 'functionDescription' in cql_schemas is not None
        assert cql_schemas.get('functionDescription', None) is not None

        function_description = ['name', 'returns', 'arguments']
        for props in function_description:
            assert props in cql_schemas['functionDescription']['properties']


def test_cql_filters_capabilities(cql_schemas, is_cql):
    """
    Assertions for CQL filter capabilities schema in OpenAPI 3.0 Document

    :param cql_schemas: OpenAPI 3.0 Document schemas
    :param is_cql: boolean value
    """
    if is_cql:
        # assertion for filter capabilities
        assert 'filter-capabilities' in cql_schemas is not None
        assert cql_schemas.get('filter-capabilities', None) is not None

        filter_capabilities = ['conformance-classes',
                               'capabilities', 'functions']
        for props in filter_capabilities:
            assert props in cql_schemas['filter-capabilities']['properties']
