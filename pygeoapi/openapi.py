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

from copy import deepcopy
import logging
import os

import click
import yaml

from pygeoapi.plugin import load_plugin
from pygeoapi.util import (filter_dict_by_key_value, get_provider_by_type,
                           yaml_load)

LOGGER = logging.getLogger(__name__)

OPENAPI_YAML = {
    'oapif': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml',  # noqa
    'oapip': 'https://raw.githubusercontent.com/opengeospatial/wps-rest-binding/master/core/openapi'  # noqa
}


def get_ogc_schemas_location(server_config):

    osl = server_config.get('ogc_schemas_location', None)

    value = 'http://schemas.opengis.net'

    if osl is not None:
        if osl.startswith('http'):
            value = osl
        elif osl.startswith('/'):
            value = os.path.join(server_config['url'], 'schemas')

    return value


# TODO: remove this function once OGC API - Processing is final
def gen_media_type_object(media_type, api_type, path):
    """
    Generates an OpenAPI Media Type Object

    :param media_type: MIME type
    :param api_type: OGC API type
    :param path: local path of OGC API parameter or schema definition

    :returns: `dict` of media type object
    """

    ref = '{}/{}'.format(OPENAPI_YAML[api_type], path)

    content = {
        media_type: {
            'schema': {
                '$ref': ref
            }
        }
    }

    return content


# TODO: remove this function once OGC API - Processing is final
def gen_response_object(description, media_type, api_type, path):
    """
    Generates an OpenAPI Response Object

    :param description: text description of response
    :param media_type: MIME type
    :param api_type: OGC API type

    :returns: `dict` of response object
    """

    response = {
        'description': description,
        'content': gen_media_type_object(media_type, api_type, path)
    }

    return response


def get_oas_30(cfg):
    """
    Generates an OpenAPI 3.0 Document

    :param cfg: configuration object
    :returns: OpenAPI definition YAML dict

    """

    paths = {}

    osl = get_ogc_schemas_location(cfg['server'])
    OPENAPI_YAML['oapif'] = os.path.join(osl, 'ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml')  # noqa

    LOGGER.debug('setting up server info')
    oas = {
        'openapi': '3.0.2',
        'tags': []
    }
    info = {
        'title': cfg['metadata']['identification']['title'],
        'description': cfg['metadata']['identification']['description'],
        'x-keywords': cfg['metadata']['identification']['keywords'],
        'termsOfService':
            cfg['metadata']['identification']['terms_of_service'],
        'contact': {
            'name': cfg['metadata']['provider']['name'],
            'url': cfg['metadata']['provider']['url'],
            'email': cfg['metadata']['contact']['email']
        },
        'license': {
            'name': cfg['metadata']['license']['name'],
            'url': cfg['metadata']['license']['url']
        },
        'version': '3.0.2'
    }
    oas['info'] = info

    oas['servers'] = [{
        'url': cfg['server']['url'],
        'description': cfg['metadata']['identification']['description']
    }]

    paths['/'] = {
        'get': {
            'summary': 'Landing page',
            'description': 'Landing page',
            'tags': ['server'],
            'operationId': 'getLandingPage',
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                '200': {'$ref': '{}#/components/responses/LandingPage'.format(OPENAPI_YAML['oapif'])},  # noqa
                '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
            }
        }
    }

    paths['/openapi'] = {
        'get': {
            'summary': 'This document',
            'description': 'This document',
            'tags': ['server'],
            'operationId': 'getOpenapi',
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                '200': {'$ref': '#/components/responses/200'},
                '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                'default': {'$ref': '#/components/responses/default'}
            }
        }
    }

    paths['/conformance'] = {
        'get': {
            'summary': 'API conformance definition',
            'description': 'API conformance definition',
            'tags': ['server'],
            'operationId': 'getConformanceDeclaration',
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                '200': {'$ref': '{}#/components/responses/ConformanceDeclaration'.format(OPENAPI_YAML['oapif'])},  # noqa
                '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
            }
        }
    }

    paths['/collections'] = {
        'get': {
            'summary': 'Collections',
            'description': 'Collections',
            'tags': ['server'],
            'operationId': 'getCollections',
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                '200': {'$ref': '{}#/components/responses/Collections'.format(OPENAPI_YAML['oapif'])},  # noqa
                '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
            }
        }
    }

    oas['tags'].append({
            'name': 'server',
            'description': cfg['metadata']['identification']['description'],
            'externalDocs': {
                'description': 'information',
                'url': cfg['metadata']['identification']['url']}
        }
    )
    oas['tags'].append({
            'name': 'stac',
            'description': 'SpatioTemporal Asset Catalog'
        }
    )

    oas['components'] = {
        'responses': {
            '200': {
                'description': 'successful operation',
            },
            'default': {
                'description': 'Unexpected error',
                'content': gen_media_type_object('application/json', 'oapip', 'schemas/exception.yaml')  # noqa
            },
            'Queryables': {
                'description': 'successful queryables operation',
                'content': {
                    'application/json': {
                        'schema': {'$ref': '#/components/schemas/queryables'}
                    }
                }
            }
        },
        'parameters': {
            'f': {
                'name': 'f',
                'in': 'query',
                'description': 'The optional f parameter indicates the output format which the server shall provide as part of the response document.  The default format is GeoJSON.',  # noqa
                'required': False,
                'schema': {
                    'type': 'string',
                    'enum': ['json', 'html', 'jsonld'],
                    'default': 'json'
                },
                'style': 'form',
                'explode': False
            },
            'sortby': {
                'name': 'sortby',
                'in': 'query',
                'description': 'The optional sortby parameter indicates the sort property and order on which the server shall present results in the response document using the convention `sortby=PROPERTY:X`, where `PROPERTY` is the sort property and `X` is the sort order (`A` is ascending, `D` is descending). Sorting by multiple properties is supported by providing a comma-separated list.',  # noqa
                'required': False,
                'schema': {
                    'type': 'string',
                },
                'style': 'form',
                'explode': False
            },
            'startindex': {
                'name': 'startindex',
                'in': 'query',
                'description': 'The optional startindex parameter indicates the index within the result set from which the server shall begin presenting results in the response document.  The first element has an index of 0 (default).',  # noqa
                'required': False,
                'schema': {
                    'type': 'integer',
                    'minimum': 0,
                    'default': 0
                },
                'style': 'form',
                'explode': False
            }
        },
        'schemas': {
            # TODO: change this schema once OGC will definitively publish it
            'queryable': {
                'type': 'object',
                'required': [
                    'queryable',
                    'type'
                ],
                'properties': {
                    'queryable': {
                        'description': 'the token that may be used in a CQL predicate', # noqa
                        'type': 'string'
                    },
                    'title': {
                        'description': 'a human readable title for the queryable', # noqa
                        'type': 'string'
                    },
                    'description': {
                        'description': 'a human-readable narrative describing the queryable', # noqa
                        'type': 'string'
                    },
                    'language': {
                        'description': 'the language used for the title and description', # noqa
                        'type': 'string',
                        'default': [
                            'en'
                        ]
                    },
                    'type': {
                        'description': 'the data type of the queryable', # noqa
                        'type': 'string'
                    },
                    'type-ref': {
                        'description': 'a reference to the formal definition of the type', # noqa
                        'type': 'string',
                        'format': 'url'
                    }
                }
            },
            'queryables': {
                'type': 'object',
                'required': [
                    'queryables'
                ],
                'properties': {
                    'queryables': {
                        'type': 'array',
                        'items': {'$ref': '#/components/schemas/queryable'}
                    }
                }
            }
        }
    }

    cql_filter_exists = False

    items_f = deepcopy(oas['components']['parameters']['f'])
    items_f['schema']['enum'].append('csv')

    LOGGER.debug('setting up datasets')
    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')

    for k, v in collections.items():
        collection_name_path = '/collections/{}'.format(k)
        tag = {
            'name': k,
            'description': v['description'],
            'externalDocs': {}
        }
        for link in v['links']:
            if link['type'] == 'information':
                tag['externalDocs']['description'] = link['type']
                tag['externalDocs']['url'] = link['url']
                break
        if len(tag['externalDocs']) == 0:
            del tag['externalDocs']

        oas['tags'].append(tag)

        paths[collection_name_path] = {
            'get': {
                'summary': 'Get collection metadata'.format(v['title']),  # noqa
                'description': v['description'],
                'tags': [k],
                'operationId': 'describe{}Collection'.format(k.capitalize()),
                'parameters': [
                    {'$ref': '#/components/parameters/f'}
                ],
                'responses': {
                    '200': {'$ref': '{}#/components/responses/Collection'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

        items_path = '{}/items'.format(collection_name_path)

        paths[items_path] = {
            'get': {
                'summary': 'Get {} items'.format(v['title']),
                'description': v['description'],
                'tags': [k],
                'operationId': 'get{}Features'.format(k.capitalize()),
                'parameters': [
                    items_f,
                    {'$ref': '{}#/components/parameters/bbox'.format(OPENAPI_YAML['oapif'])},  # noqa
                    {'$ref': '{}#/components/parameters/limit'.format(OPENAPI_YAML['oapif'])},  # noqa
                    {'$ref': '#/components/parameters/sortby'},
                    {'$ref': '#/components/parameters/startindex'}
                ],
                'responses': {
                    '200': {'$ref': '{}#/components/responses/Features'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

        # if CQL filter available for collection
        if 'filters' in collections[k]:
            paths[items_path]['get']['parameters'].\
                append({'$ref': '#/components/parameters/filter'})
            paths[items_path]['get']['parameters'].\
                append({'$ref': '#/components/parameters/filter-lang'})
            cql_filter_exists = True

        p = load_plugin('provider', get_provider_by_type(
                        collections[k]['providers'], 'feature'))

        if p.fields:
            queryables_path = '{}/queryables'.format(collection_name_path)

            paths[queryables_path] = {
                'get': {
                    'summary': 'Get {} queryables'.format(v['title']),
                    'description': v['description'],
                    'tags': [k],
                    'operationId': 'get{}Queryables'.format(k.capitalize()),
                    'parameters': [
                        {'$ref': '#/components/parameters/f'}
                    ],
                    'responses': {
                        '200': {'$ref': '#/components/responses/Queryables'},
                        '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                    }
                }
            }

        if p.time_field is not None:
            paths[items_path]['get']['parameters'].append(
                {'$ref': '{}#/components/parameters/datetime'.format(OPENAPI_YAML['oapif'])})  # noqa

        for field, type in p.fields.items():

            if p.properties and field not in p.properties:
                LOGGER.debug('Provider specified not to advertise property')
                continue

            if type == 'date':
                schema = {
                    'type': 'string',
                    'format': 'date'
                }
            elif type == 'float':
                schema = {
                    'type': 'number',
                    'format': 'float'
                }
            elif type == 'long':
                schema = {
                    'type': 'integer',
                    'format': 'int64'
                }
            else:
                schema = {
                    'type': type
                }

            path_ = '{}/items'.format(collection_name_path)
            paths['{}'.format(path_)]['get']['parameters'].append({
                'name': field,
                'in': 'query',
                'required': False,
                'schema': schema,
                'style': 'form',
                'explode': False
            })

        paths['{}/items/{{featureId}}'.format(collection_name_path)] = {
            'get': {
                'summary': 'Get {} item by id'.format(v['title']),
                'description': v['description'],
                'tags': [k],
                'operationId': 'get{}Feature'.format(k.capitalize()),
                'parameters': [
                    {'$ref': '{}#/components/parameters/featureId'.format(OPENAPI_YAML['oapif'])},  # noqa
                    {'$ref': '#/components/parameters/f'}
                ],
                'responses': {
                    '200': {'$ref': '{}#/components/responses/Feature'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

    # if CQL filter is applicable
    if cql_filter_exists:
        paths['/queryables'] = {
            'get': {
                'summary': 'Feature Queryables',
                'description': 'Feature Queryables',
                'tags': ['server'],
                'parameters': [
                    {'$ref': '#/components/parameters/f'}
                ],
                'responses': {
                    '200': {'$ref': '#/components/responses/Queryables'},  # noqa
                    '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

        filter_lang_enum = ['cql-text', 'cql-json']

        filter_extension = {
            'description': 'The optional filter parameter to provide filters on the collection items', # noqa
            'explode': False,
            'in': 'query',
            'name': 'filter',
            'required': False,
            'schema': {
                'type': 'string'
            },
            'style': 'form'
        }

        filter_lang_extension = {
            'description': 'The optional parameter to provide filter lang',
            'explode': False,
            'in': 'query',
            'name': 'filter-lang',
            'required': False,
            'schema': {
                'type': 'string',
                'enum': filter_lang_enum,
                'default': 'cql-text'
            },
            'style': 'form'
        }

        cql_schemas = {
            'predicates': {
                'allOf': [
                    {
                        '$ref': '#/components/schemas/logicalExpression'
                    },
                    {
                        '$ref': '#/components/schemas/comparisonExpressions'
                    },
                    {
                        '$ref': '#/components/schemas/spatialExpressions'
                    },
                    {
                        '$ref': '#/components/schemas/temporalExpressions'
                    }
                ],
                'minProperties': 1,
                'maxProperties': 1,
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'logicalExpression': {
                'properties': {
                    'and': {
                        '$ref': '#/components/schemas/and'
                    },
                    'or': {
                        '$ref': '#/components/schemas/or'
                    },
                    'not': {
                        '$ref': '#/components/schemas/not'
                    }
                },
                'minProperties': 1,
                'maxProperties': 1,
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'comparisonExpressions': {
                'properties': {
                    'eq': {
                        '$ref': '#/components/schemas/eq'
                    },
                    'lt': {
                        '$ref': '#/components/schemas/lt'
                    },
                    'gt': {
                        '$ref': '#/components/schemas/gt'
                    },
                    'lte': {
                        '$ref': '#/components/schemas/lte'
                    },
                    'gte': {
                        '$ref': '#/components/schemas/gte'
                    },
                    'between': {
                        '$ref': '#/components/schemas/between'
                    },
                    'like': {
                        '$ref': '#/components/schemas/like'
                    },
                    'in': {
                        '$ref': '#/components/schemas/in'
                    }
                },
                'minProperties': 1,
                'maxProperties': 1,
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'spatialExpressions': {
                'properties': {
                    'equals': {
                        '$ref': '#/components/schemas/equals'
                    },
                    'disjoint': {
                        '$ref': '#/components/schemas/disjoint'
                    },
                    'touches': {
                        '$ref': '#/components/schemas/touches'
                    },
                    'within': {
                        '$ref': '#/components/schemas/within'
                    },
                    'overlaps': {
                        '$ref': '#/components/schemas/overlaps'
                    },
                    'crosses': {
                        '$ref': '#/components/schemas/crosses'
                    },
                    'intersects': {
                        '$ref': '#/components/schemas/intersects'
                    },
                    'contains': {
                        '$ref': '#/components/schemas/contains'
                    }
                },
                'minProperties': 1,
                'maxProperties': 1,
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'temporalExpressions': {
                'properties': {
                    'after': {
                        '$ref': '#/components/schemas/after'
                    },
                    'before': {
                        '$ref': '#/components/schemas/before'
                    },
                    'begins': {
                        '$ref': '#/components/schemas/begins'
                    },
                    'begunby': {
                        '$ref': '#/components/schemas/begunby'
                    },
                    'tcontains': {
                        '$ref': '#/components/schemas/tcontains'
                    },
                    'during': {
                        '$ref': '#/components/schemas/during'
                    },
                    'endedby': {
                        '$ref': '#/components/schemas/endedby'
                    },
                    'ends': {
                        '$ref': '#/components/schemas/ends'
                    },
                    'tequals': {
                        '$ref': '#/components/schemas/tequals'
                    },
                    'meets': {
                        '$ref': '#/components/schemas/meets'
                    },
                    'metby': {
                        '$ref': '#/components/schemas/metby'
                    },
                    'toverlaps': {
                        '$ref': '#/components/schemas/toverlaps'
                    },
                    'overlappedby': {
                        '$ref': '#/components/schemas/overlappedby'
                    }
                },
                'minProperties': 1,
                'maxProperties': 1,
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'and': {
                '$ref': '#/components/schemas/booleanOperands'
            },
            'or': {
                '$ref': '#/components/schemas/booleanOperands'
            },
            'not': {
                '$ref': '#/components/schemas/predicates'
            },
            'eq': {
                '$ref': '#/components/schemas/scalarOperands'
            },
            'lt': {
                '$ref': '#/components/schemas/scalarOperands'
            },
            'gt': {
                '$ref': '#/components/schemas/scalarOperands'
            },
            'lte': {
                '$ref': '#/components/schemas/scalarOperands'
            },
            'gte': {
                '$ref': '#/components/schemas/scalarOperands'
            },
            'between': {
                'properties': {
                    'property': {
                        'nullable': False,
                        'type': 'string'
                    },
                    'lower': {
                        '$ref': '#/components/schemas/scalarLiteral'
                    },
                    'upper': {
                        '$ref': '#/components/schemas/scalarLiteral'
                    }
                },
                'required': [
                    'property',
                    'lower',
                    'upper'
                ],
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'like': {
                'properties': {
                    'wildcard': {
                        'default': '%',
                        'nullable': False,
                        'type': 'string'
                    },
                    'singleChar': {
                        'default': '_',
                        'nullable': False,
                        'type': 'string'
                    },
                    'escape': {
                        'default': '\\\\',
                        'nullable': False,
                        'type': 'string'
                    },
                    'nocase': {
                        'default': True,
                        'nullable': False,
                        'type': 'boolean'
                    },
                    'property': {
                        'nullable': False,
                        'type': 'string'
                    },
                    'value': {
                        '$ref': '#/components/schemas/scalarLiteral'
                    }
                },
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'in': {
                'properties': {
                    'nocase': {
                        'default': True,
                        'nullable': False,
                        'type': 'boolean'
                    },
                    'property': {
                        'nullable': False,
                        'type': 'string'
                    },
                    'values': {
                        'items': {
                            '$ref': '#/components/schemas/scalarLiteral'
                        },
                        'nullable': False,
                        'type': 'array'
                    }
                },
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'equals': {
                '$ref': '#/components/schemas/spatialOperands'
            },
            'disjoint': {
                '$ref': '#/components/schemas/spatialOperands'
            },
            'touches': {
                '$ref': '#/components/schemas/spatialOperands'
            },
            'within': {
                '$ref': '#/components/schemas/spatialOperands'
            },
            'overlaps': {
                '$ref': '#/components/schemas/spatialOperands'
            },
            'crosses': {
                '$ref': '#/components/schemas/spatialOperands'
            },
            'intersects': {
                '$ref': '#/components/schemas/spatialOperands'
            },
            'contains': {
                '$ref': '#/components/schemas/spatialOperands'
            },
            'after': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'before': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'begins': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'begunby': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'tcontains': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'during': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'endedby': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'ends': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'tequals': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'meets': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'metby': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'toverlaps': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'overlappedby': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'anyinteracts': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'tintersects': {
                '$ref': '#/components/schemas/temporalOperands'
            },
            'booleanOperands': {
                'items': {
                    '$ref': '#/components/schemas/predicates',
                    'minItems': 2
                },
                'nullable': False,
                'type': 'array'
            },
            'arithmeticOperands': {
                'properties': {
                    'property': {
                        'nullable': False,
                        'type': 'string'
                    },
                    'function': {
                        '$ref': '#/components/schemas/function'
                    },
                    'value': {
                        'nullable': False,
                        'type': 'number'
                    },
                    '+': {
                        '$ref': '#/components/schemas/add'
                    },
                    '-': {
                        '$ref': '#/components/schemas/sub'
                    },
                    '*': {
                        '$ref': '#/components/schemas/mul'
                    },
                    '/': {
                        '$ref': '#/components/schemas/div'
                    }
                },
                'minProperties': 2,
                'maxProperties': 2,
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'add': {
                '$ref': '#/components/schemas/arithmeticOperands'
            },
            'sub': {
                '$ref': '#/components/schemas/arithmeticOperands'
            },
            'mul': {
                '$ref': '#/components/schemas/arithmeticOperands'
            },
            'div': {
                '$ref': '#/components/schemas/arithmeticOperands'
            },
            'scalarOperands': {
                'properties': {
                    'property': {
                        'nullable': False,
                        'type': 'string'
                    },
                    'function': {
                        '$ref': '#/components/schemas/function'
                    },
                    'value': {
                        '$ref': '#/components/schemas/scalarLiteral'
                    },
                    '+': {
                        '$ref': '#/components/schemas/add'
                    },
                    '-': {
                        '$ref': '#/components/schemas/sub'
                    },
                    '*': {
                        '$ref': '#/components/schemas/mul'
                    },
                    '/': {
                        '$ref': '#/components/schemas/div'
                    }
                },
                'minProperties': 2,
                'maxProperties': 2,
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'spatialOperands': {
                'properties': {
                    'property': {
                        'nullable': False,
                        'type': 'string'
                    },
                    'function': {
                        '$ref': '#/components/schemas/function'
                    },
                    'value': {
                        '$ref': '#/components/schemas/geometryLiteral'
                    }
                },
                'minProperties': 2,
                'maxProperties': 2,
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'temporalOperands': {
                'properties': {
                    'property': {
                        'nullable': False,
                        'type': 'string'
                    },
                    'function': {
                        '$ref': '#/components/schemas/function'
                    },
                    'value': {
                        '$ref': '#/components/schemas/temporalLiteral'
                    }
                },
                'minProperties': 2,
                'maxProperties': 2,
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'function': {
                'properties': {
                    'name': {
                        'nullable': False,
                        'type': 'string'
                    },
                    'arguments': {
                        'items': {
                            'oneOf': [
                                {
                                    'nullable': False,
                                    'type': 'string'
                                },
                                {
                                    'nullable': False,
                                    'type': 'number'
                                },
                                {
                                    'nullable': False,
                                    'type': 'boolean'
                                },
                                {
                                    '$ref': '#/components/schemas/functionObjectArgument' # noqa
                                }
                            ]
                        },
                        'nullable': False,
                        'type': 'array'
                    }
                },
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'functionObjectArgument': {
                'properties': {
                    'property': {
                        'nullable': False,
                        'type': 'string'
                    },
                    'function': {
                        '$ref': '#/components/schemas/function'
                    },
                    'geometry': {
                        '$ref': '#/components/schemas/geometryLiteral'
                    },
                    'bbox': {
                        '$ref': '#/components/schemas/bbox'
                    },
                    'temporalValue': {
                        '$ref': '#/components/schemas/temporalLiteral'
                    },
                    '+': {
                        '$ref': '#/components/schemas/add'
                    },
                    '-': {
                        '$ref': '#/components/schemas/sub'
                    },
                    '*': {
                        '$ref': '#/components/schemas/mul'
                    },
                    '/': {
                        '$ref': '#/components/schemas/div'
                    }
                },
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'scalarLiteral': {
                'oneOf': [
                    {
                        'nullable': False,
                        'type': 'string'
                    },
                    {
                        'nullable': False,
                        'type': 'number'
                    },
                    {
                        'nullable': False,
                        'type': 'boolean'
                    }
                ]
            },
            'geometryLiteral': {
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'bbox': {
                'items': {
                    'minItems': 4,
                    'maxItems': 6,
                    'nullable': False,
                    'type': 'number'
                },
                'nullable': False,
                'type': 'array'
            },
            'envelopeLiteral': {
                'properties': {
                    'bbox': {
                        '$ref': '#/components/schemas/bbox'
                    }
                },
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            },
            'temporalLiteral': {
                'oneOf': [
                    {
                        '$ref': '#/components/schemas/timeLiteral'
                    },
                    {
                        '$ref': '#/components/schemas/periodLiteral'
                    }
                ]
            },
            'timeLiteral': {
                'pattern': '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-9][0-9](T[0-2][0-9]:[0-5][0-9]:[0-5][0-9](.[0-9]*)?)?', # noqa
                'nullable': False,
                'type': 'string'
            },
            'periodLiteral': {
                'items': {
                    '$ref': '#/components/schemas/timeLiteral',
                    'minItems': 2,
                    'maxItems': 2
                },
                'nullable': False,
                'type': 'array'
            },
            'capabilities-assertion': {
                'type': 'object',
                'required': [
                    'name',
                    'operators'
                ],
                'properties': {
                    'name': {
                        'type': 'string',
                        'enum': [
                            'logical',
                            'comparison',
                            'spatial',
                            'temporal',
                            'arithmetic'
                        ]
                    },
                    'operators': {
                        'type': 'array',
                        'items': {
                            'type': 'string'
                        }
                    },
                    'operands': {
                        'type': 'array',
                        'items': {
                            'type': 'string'
                        }
                    }
                }
            },
            'functionDescription': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string'
                    },
                    'returns': {
                        'type': 'object',
                        'properties': {
                            'type': {
                                'type': 'string'
                            },
                            'typeRef': {
                                'type': 'string',
                                'format': 'uri'
                            }
                        }
                    },
                    'arguments': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name': {
                                    'type': 'string'
                                },
                                'type': {
                                    'type': 'string'
                                },
                                'typeRef': {
                                    'type': 'string',
                                    'format': 'uri'
                                }
                            }
                        }
                    }
                }
            },
            'filter-capabilities': {
                'required': [
                    'conformance-classes',
                    'capabilites'
                ],
                'properties': {
                    'conformance-classes': {
                        'items': {
                            'format': 'uri',
                            'nullable': False,
                            'type': 'string'
                        },
                        'nullable': False,
                        'type': 'array'
                    },
                    'capabilities': {
                        'items': {
                            '$ref': '#/components/schemas/capabilities-assertion' # noqa
                        },
                        'nullable': False,
                        'type': 'array'
                    },
                    'functions': {
                        'items': {
                            '$ref': '#/components/schemas/functionDescription'
                        },
                        'nullable': False,
                        'type': 'array'
                    }
                },
                'nullable': False,
                'type': 'object',
                'additionalProperties': True
            }
        }

        oas['components']['parameters']['filter-lang'] = filter_lang_extension
        oas['components']['parameters']['filter'] = filter_extension
        oas['components']['schemas'].update(cql_schemas)

    LOGGER.debug('setting up STAC')
    stac_collections = filter_dict_by_key_value(cfg['resources'],
                                                'type', 'stac-collection')
    if stac_collections:
        paths['/stac'] = {
            'get': {
                'summary': 'SpatioTemporal Asset Catalog',
                'description': 'SpatioTemporal Asset Catalog',
                'tags': ['stac'],
                'operationId': 'getStacCatalog',
                'parameters': [],
                'responses': {
                    '200': {'$ref': '#/components/responses/200'},
                    'default': {'$ref': '#/components/responses/default'}
                }
            }
        }

    LOGGER.debug('setting up processes')
    processes = filter_dict_by_key_value(cfg['resources'], 'type', 'process')

    if processes:
        paths['/processes'] = {
            'get': {
                'summary': 'Processes',
                'description': 'Processes',
                'tags': ['server'],
                'operationId': 'getProcesses',
                'parameters': [
                    {'$ref': '#/components/parameters/f'}
                ],
                'responses': {
                    '200': {'$ref': '{}/responses/ProcessList.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                    'default': {'$ref': '#/components/responses/default'}
                }
            }
        }

        for k, v in processes.items():
            p = load_plugin('process', v['processor'])

            process_name_path = '/processes/{}'.format(k)
            tag = {
                'name': k,
                'description': p.metadata['description'],
                'externalDocs': {}
            }
            for link in p.metadata['links']:
                if link['type'] == 'information':
                    tag['externalDocs']['description'] = link['type']
                    tag['externalDocs']['url'] = link['url']
                    break
            if len(tag['externalDocs']) == 0:
                del tag['externalDocs']

            oas['tags'].append(tag)

            paths[process_name_path] = {
                'get': {
                    'summary': 'Get process metadata',
                    'description': p.metadata['description'],
                    'tags': [k],
                    'operationId': 'describe{}Process'.format(k.capitalize()),
                    'parameters': [
                        {'$ref': '#/components/parameters/f'}
                    ],
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        'default': {'$ref': '#/components/responses/default'}
                    }
                }
            }
            paths['{}/jobs'.format(process_name_path)] = {
                'get': {
                    'summary': 'Retrieve job list for process',
                    'description': p.metadata['description'],
                    'tags': [k],
                    'operationId': 'get{}Jobs'.format(k.capitalize()),
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        '404': {'$ref': '{}/responses/NotFound.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        'default': {'$ref': '#/components/responses/default'}
                    }
                },
                'post': {
                    'summary': 'Process {} execution'.format(
                        p.metadata['title']),
                    'description': p.metadata['description'],
                    'tags': [k],
                    'operationId': 'execute{}Job'.format(k.capitalize()),
                    'parameters': [{
                        'name': 'response',
                        'in': 'query',
                        'description': 'Response type',
                        'required': False,
                        'schema': {
                            'type': 'string',
                            'enum': ['raw', 'document'],
                            'default': 'document'
                        }
                    }],
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        '201': {'$ref': '{}/responses/ExecuteAsync.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        '404': {'$ref': '{}/responses/NotFound.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        '500': {'$ref': '{}/responses/ServerError.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        'default': {'$ref': '#/components/responses/default'}
                    },
                    'requestBody': {
                        'description': 'Mandatory execute request JSON',
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    '$ref': '{}/schemas/execute.yaml'.format(OPENAPI_YAML['oapip'])  # noqa
                                }
                            }
                        }
                    }
                }
            }
            if 'example' in p.metadata:
                paths['{}/jobs'.format(process_name_path)]['post']['requestBody']['content']['application/json']['example'] = p.metadata['example']  # noqa

    oas['paths'] = paths

    return oas


def get_oas(cfg, version='3.0'):
    """
    Stub to generate OpenAPI Document

    :param cfg: configuration object
    :param version: version of OpenAPI (default 3.0)

    :returns: OpenAPI definition YAML dict
    """

    if version == '3.0':
        return get_oas_30(cfg)
    else:
        raise RuntimeError('OpenAPI version not supported')


@click.command('generate-openapi-document')
@click.pass_context
@click.option('--config', '-c', 'config_file', help='configuration file')
def generate_openapi_document(ctx, config_file):
    """
    Generate OpenAPI Document
    """

    if config_file is None:
        raise click.ClickException('--config/-c required')
    with open(config_file) as ff:
        s = yaml_load(ff)
        click.echo(yaml.safe_dump(get_oas(s), default_flow_style=False))
