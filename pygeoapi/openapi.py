# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2021 Tom Kralidis
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

from pygeoapi import __version__
from pygeoapi.plugin import load_plugin
from pygeoapi.provider.base import ProviderTypeError
from pygeoapi.util import (filter_dict_by_key_value, get_provider_by_type,
                           filter_providers_by_type, yaml_load)

LOGGER = logging.getLogger(__name__)

OPENAPI_YAML = {
    'oapif': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml',  # noqa
    'oapip': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-processes/master/core/openapi',  # noqa
    'oacov': 'https://raw.githubusercontent.com/tomkralidis/ogcapi-coverages-1/fix-cis/yaml-unresolved',  # noqa
    'oapit': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-tiles/master/openapi/swaggerhub/tiles.yaml',  # noqa
    'oapimt': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-tiles/master/openapi/swaggerhub/map-tiles.yaml',  # noqa
    'oapir': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-records/master/core/openapi'  # noqa
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
        'version': __version__
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
            'properties': {
                'name': 'properties',
                'in': 'query',
                'description': 'The properties that should be included for each feature. The parameter value is a comma-separated list of property names.',  # noqa
                'required': False,
                'style': 'form',
                'explode': False,
                'schema': {
                    'type': 'array',
                    'items': {
                        'type': 'string'
                    }
                }
            },
            'skipGeometry': {
                'name': 'skipGeometry',
                'in': 'query',
                'description': 'This option can be used to skip response geometries for each feature.',  # noqa
                'required': False,
                'style': 'form',
                'explode': False,
                'schema': {
                    'type': 'boolean',
                    'default': False
                }
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

        LOGGER.debug('setting up collection endpoints')
        try:
            ptype = None

            if filter_providers_by_type(
                    collections[k]['providers'], 'feature'):
                ptype = 'feature'

            if filter_providers_by_type(
                    collections[k]['providers'], 'record'):
                ptype = 'record'

            p = load_plugin('provider', get_provider_by_type(
                            collections[k]['providers'], ptype))

            items_path = '{}/items'.format(collection_name_path)

            coll_properties = deepcopy(oas['components']['parameters']['properties'])  # noqa

            coll_properties['schema']['items']['enum'] = list(p.fields.keys())

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
                        coll_properties,
                        {'$ref': '#/components/parameters/skipGeometry'},
                        {'$ref': '{}/parameters/sortby.yaml'.format(OPENAPI_YAML['oapir'])},  # noqa
                        {'$ref': '#/components/parameters/startindex'},
                    ],
                    'responses': {
                        '200': {'$ref': '{}#/components/responses/Features'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                    }
                }
            }

            if ptype == 'record':
                paths[items_path]['get']['parameters'].append(
                    {'$ref': '{}/parameters/q.yaml'.format(OPENAPI_YAML['oapir'])})  # noqa
            if p.fields:
                queryables_path = '{}/queryables'.format(collection_name_path)

                paths[queryables_path] = {
                    'get': {
                        'summary': 'Get {} queryables'.format(v['title']),
                        'description': v['description'],
                        'tags': [k],
                        'operationId': 'get{}Queryables'.format(
                            k.capitalize()),
                        'parameters': [
                            items_f,
                        ],
                        'responses': {
                            '200': {'$ref': '#/components/responses/Queryables'},  # noqa
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
                    LOGGER.debug('Provider specified not to advertise property')  # noqa
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
        except ProviderTypeError:
            LOGGER.debug('collection is not feature based')

        LOGGER.debug('setting up coverage endpoints')
        try:
            load_plugin('provider', get_provider_by_type(
                        collections[k]['providers'], 'coverage'))

            coverage_path = '{}/coverage'.format(collection_name_path)

            paths[coverage_path] = {
                'get': {
                    'summary': 'Get {} coverage'.format(v['title']),
                    'description': v['description'],
                    'tags': [k],
                    'operationId': 'get{}Coverage'.format(k.capitalize()),
                    'parameters': [
                        items_f,
                    ],
                    'responses': {
                        '200': {'$ref': '{}#/components/responses/Features'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                    }
                }
            }

            coverage_domainset_path = '{}/coverage/domainset'.format(
                collection_name_path)

            paths[coverage_domainset_path] = {
                'get': {
                    'summary': 'Get {} coverage domain set'.format(v['title']),
                    'description': v['description'],
                    'tags': [k],
                    'operationId': 'get{}CoverageDomainSet'.format(
                        k.capitalize()),
                    'parameters': [
                        items_f,
                    ],
                    'responses': {
                        '200': {'$ref': '{}/schemas/cis_1.1/domainSet.yaml'.format(OPENAPI_YAML['oacov'])},  # noqa
                        '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                    }
                }
            }

            coverage_rangetype_path = '{}/coverage/rangetype'.format(
                collection_name_path)

            paths[coverage_rangetype_path] = {
                'get': {
                    'summary': 'Get {} coverage range type'.format(v['title']),
                    'description': v['description'],
                    'tags': [k],
                    'operationId': 'get{}CoverageRangeType'.format(
                        k.capitalize()),
                    'parameters': [
                        items_f,
                    ],
                    'responses': {
                        '200': {'$ref': '{}/schemas/cis_1.1/rangeType.yaml'.format(OPENAPI_YAML['oacov'])},  # noqa
                        '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                    }
                }
            }
        except ProviderTypeError:
            LOGGER.debug('collection is not coverage based')

        LOGGER.debug('setting up tiles endpoints')
        tile_extension = filter_providers_by_type(
            collections[k]['providers'], 'tile')

        if tile_extension:
            tp = load_plugin('provider', tile_extension)
            oas['components']['responses'].update({
                    'Tiles': {
                        'description': 'Retrieves the tiles description for this collection', # noqa
                        'content': {
                            'application/json': {
                                'schema': {
                                    '$ref': '#/components/schemas/tiles'
                                }
                            }
                        }
                    }
                }
            )

            oas['components']['schemas'].update({
                    'tilematrixsetlink': {
                        'type': 'object',
                        'required': ['tileMatrixSet'],
                        'properties': {
                            'tileMatrixSet': {
                                'type': 'string'
                            },
                            'tileMatrixSetURI': {
                                'type': 'string'
                            }
                        }
                    },
                    'tiles': {
                        'type': 'object',
                        'required': [
                            'tileMatrixSetLinks',
                            'links'
                        ],
                        'properties': {
                            'tileMatrixSetLinks': {
                                'type': 'array',
                                'items': {
                                    '$ref': '#/components/schemas/tilematrixsetlink' # noqa
                                }
                            },
                            'links': {
                                'type': 'array',
                                'items': {'$ref': '{}#/components/schemas/link'.format(OPENAPI_YAML['oapit'])},  # noqa
                            }
                        }
                    }
                }
            )

            tiles_path = '{}/tiles'.format(collection_name_path)

            paths[tiles_path] = {
                'get': {
                    'summary': 'Fetch a {} tiles description'.format(v['title']), # noqa
                    'description': v['description'],
                    'tags': [k],
                    'operationId': 'describe{}Tiles'.format(k.capitalize()),
                    'parameters': [
                        items_f,
                    ],
                    'responses': {
                        '200': {'$ref': '#/components/responses/Tiles'},
                        '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                    }
                }
            }

            tiles_data_path = '{}/tiles/{{tileMatrixSetId}}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}'.format(collection_name_path)  # noqa

            paths[tiles_data_path] = {
                'get': {
                    'summary': 'Get a {} tile'.format(v['title']),
                    'description': v['description'],
                    'tags': [k],
                    'operationId': 'get{}Tiles'.format(k.capitalize()),
                    'parameters': [{
                        'name': 'f',
                        'in': 'query',
                        'description': 'The optional f parameter indicates the output format which the server shall provide as part of the response document.',  # noqa
                        'required': False,
                        'schema': {
                            'type': 'string',
                            'enum': [tp.format_type],
                            'default': tp.format_type
                        },
                        'style': 'form',
                        'explode': False
                    }],
                    'responses': {
                        '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                    }
                }
            }
            mimetype = tile_extension['format']['mimetype']
            paths[tiles_data_path]['get']['responses']['200'] = {
                'content': {
                    mimetype: {
                        'schema': {
                            'type': 'string',
                            'format': 'binary'
                        }
                    }
                }
            }

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

    processes = filter_dict_by_key_value(cfg['resources'], 'type', 'process')

    has_manager = 'manager' in cfg['server']

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
        LOGGER.debug('setting up processes')

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

            name_in_path = {
                'name': 'jobId',
                'in': 'path',
                'description': 'job identifier',
                'required': True,
                'schema': {
                    'type': 'string'
                }
            }

            if has_manager:
                # TODO: define jobId as parameter in dict
                paths[f'{process_name_path}/jobs/{{jobId}}'] = {
                    'get': {
                        'summary': 'Retrieve job details',
                        'description': '',
                        'tags': [k],
                        'parameters': [
                            name_in_path,
                            {'$ref': '#/components/parameters/f'}
                        ],
                        'operationId': f'get{k.capitalize()}Job',
                        'responses': {
                            '200': {'$ref': '#/components/responses/200'},
                            '404': {'$ref': '{}/responses/NotFound.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                            'default': {'$ref': '#/components/responses/default'}  # noqa
                        }
                    },
                    'delete': {
                        'summary': 'Cancel / delete job',
                        'description': '',
                        'tags': [k],
                        'parameters': [
                            name_in_path
                        ],
                        'operationId': f'delete{k.capitalize()}Job',
                        'responses': {
                            '204': {'$ref': '#/components/responses/204'},
                            '404': {'$ref': '{}/responses/NotFound.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                            'default': {'$ref': '#/components/responses/default'}  # noqa
                        }
                    },
                }

                paths[f'{process_name_path}/jobs/{{jobId}}/results'] = {
                    'get': {
                        'summary': 'Retrieve job results',
                        'description': '',
                        'tags': [k],
                        'parameters': [
                            name_in_path,
                            {'$ref': '#/components/parameters/f'}
                        ],
                        'operationId': f'get{k.capitalize()}JobResults',
                        'responses': {
                            '200': {'$ref': '#/components/responses/200'},
                            '404': {'$ref': '{}/responses/NotFound.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                            'default': {'$ref': '#/components/responses/default'}  # noqa
                        }
                    },
                }

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
    """Generate OpenAPI Document"""

    if config_file is None:
        raise click.ClickException('--config/-c required')
    with open(config_file) as ff:
        s = yaml_load(ff)
        click.echo(yaml.safe_dump(get_oas(s), default_flow_style=False))
