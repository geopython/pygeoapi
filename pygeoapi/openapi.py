# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Tom Kralidis
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
import json
import logging
import os

import click
from jsonschema import validate as jsonschema_validate
import yaml

from pygeoapi import __version__
from pygeoapi import l10n
from pygeoapi.plugin import load_plugin
from pygeoapi.provider.base import ProviderTypeError
from pygeoapi.util import (filter_dict_by_key_value, get_provider_by_type,
                           filter_providers_by_type, to_json, yaml_load)

LOGGER = logging.getLogger(__name__)

OPENAPI_YAML = {
    'oapif': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml',  # noqa
    'oapip': 'http://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi',
    'oacov': 'https://raw.githubusercontent.com/tomkralidis/ogcapi-coverages-1/fix-cis/yaml-unresolved',  # noqa
    'oapit': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-tiles/master/openapi/swaggerhub/tiles.yaml',  # noqa
    'oapimt': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-tiles/master/openapi/swaggerhub/map-tiles.yaml',  # noqa
    'oapir': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-records/master/core/openapi',  # noqa
    'oaedr': 'http://schemas.opengis.net/ogcapi/edr/1.0/openapi', # noqa
    'oat': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-tiles/master/openapi/swaggerHubUnresolved/ogc-api-tiles.yaml', # noqa
}

THISDIR = os.path.dirname(os.path.realpath(__file__))


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

    # TODO: make openapi multilingual (default language only for now)
    server_locales = l10n.get_locales(cfg)
    locale_ = server_locales[0]

    osl = get_ogc_schemas_location(cfg['server'])
    OPENAPI_YAML['oapif'] = os.path.join(osl, 'ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml')  # noqa

    LOGGER.debug('setting up server info')
    oas = {
        'openapi': '3.0.2',
        'tags': []
    }
    info = {
        'title': l10n.translate(cfg['metadata']['identification']['title'], locale_),  # noqa
        'description': l10n.translate(cfg['metadata']['identification']['description'], locale_),  # noqa
        'x-keywords': l10n.translate(cfg['metadata']['identification']['keywords'], locale_),  # noqa
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
        'description': l10n.translate(cfg['metadata']['identification']['description'], locale_)  # noqa
    }]

    paths['/'] = {
        'get': {
            'summary': 'Landing page',
            'description': 'Landing page',
            'tags': ['server'],
            'operationId': 'getLandingPage',
            'parameters': [
                {'$ref': '#/components/parameters/f'},
                {'$ref': '#/components/parameters/lang'}
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
                {'$ref': '#/components/parameters/f'},
                {'$ref': '#/components/parameters/lang'},
                {
                    'name': 'ui',
                    'in': 'query',
                    'description': 'UI to render the OpenAPI document',
                    'required': False,
                    'schema': {
                        'type': 'string',
                        'enum': ['swagger', 'redoc'],
                        'default': 'swagger'
                    },
                    'style': 'form',
                    'explode': False
                },
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
                {'$ref': '#/components/parameters/f'},
                {'$ref': '#/components/parameters/lang'}
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
                {'$ref': '#/components/parameters/f'},
                {'$ref': '#/components/parameters/lang'}
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
            'description': l10n.translate(cfg['metadata']['identification']['description'], locale_),  # noqa
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
            'lang': {
                'name': 'lang',
                'in': 'query',
                'description': 'The optional lang parameter instructs the server return a response in a certain language, if supported.  If the language is not among the available values, the Accept-Language header language will be used if it is supported. If the header is missing, the default server language is used. Note that providers may only support a single language (or often no language at all), that can be different from the server language.  Language strings can be written in a complex (e.g. "fr-CA,fr;q=0.9,en-US;q=0.8,en;q=0.7"), simple (e.g. "de") or locale-like (e.g. "de-CH" or "fr_BE") fashion.',  # noqa
                'required': False,
                'schema': {
                    'type': 'string',
                    'enum': [l10n.locale2str(sl) for sl in server_locales],
                    'default': l10n.locale2str(locale_)
                }
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
            'offset': {
                'name': 'offset',
                'in': 'query',
                'description': 'The optional offset parameter indicates the index within the result set from which the server shall begin presenting results in the response document.  The first element has an index of 0 (default).',  # noqa
                'required': False,
                'schema': {
                    'type': 'integer',
                    'minimum': 0,
                    'default': 0
                },
                'style': 'form',
                'explode': False
            },
            'vendorSpecificParameters': {
                'name': 'vendorSpecificParameters',
                'in': 'query',
                'description': 'Additional "free-form" parameters that are not explicitly defined',  # noqa
                'schema': {
                    'type': 'object',
                    'additionalProperties': True
                },
                'style': 'form'
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
    items_l = deepcopy(oas['components']['parameters']['lang'])

    LOGGER.debug('setting up datasets')
    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')

    for k, v in collections.items():
        name = l10n.translate(k, locale_)
        title = l10n.translate(v['title'], locale_)
        desc = l10n.translate(v['description'], locale_)
        collection_name_path = '/collections/{}'.format(k)
        tag = {
            'name': name,
            'description': desc,
            'externalDocs': {}
        }
        for link in l10n.translate(v['links'], locale_):
            if link['type'] == 'information':
                tag['externalDocs']['description'] = link['type']
                tag['externalDocs']['url'] = link['url']
                break
        if len(tag['externalDocs']) == 0:
            del tag['externalDocs']

        oas['tags'].append(tag)

        paths[collection_name_path] = {
            'get': {
                'summary': 'Get {} metadata'.format(title),
                'description': desc,
                'tags': [name],
                'operationId': 'describe{}Collection'.format(name.capitalize()),  # noqa
                'parameters': [
                    {'$ref': '#/components/parameters/f'},
                    {'$ref': '#/components/parameters/lang'}
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
                    'summary': 'Get {} items'.format(title),  # noqa
                    'description': desc,
                    'tags': [name],
                    'operationId': 'get{}Features'.format(name.capitalize()),
                    'parameters': [
                        items_f,
                        items_l,
                        {'$ref': '{}#/components/parameters/bbox'.format(OPENAPI_YAML['oapif'])},  # noqa
                        {'$ref': '{}#/components/parameters/limit'.format(OPENAPI_YAML['oapif'])},  # noqa
                        coll_properties,
                        {'$ref': '#/components/parameters/vendorSpecificParameters'},  # noqa
                        {'$ref': '#/components/parameters/skipGeometry'},
                        {'$ref': '{}/parameters/sortby.yaml'.format(OPENAPI_YAML['oapir'])},  # noqa
                        {'$ref': '#/components/parameters/offset'},
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
                        'summary': 'Get {} queryables'.format(title),
                        'description': desc,
                        'tags': [name],
                        'operationId': 'get{}Queryables'.format(
                            name.capitalize()),
                        'parameters': [
                            items_f,
                            items_l
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

            for field, type_ in p.fields.items():

                if p.properties and field not in p.properties:
                    LOGGER.debug('Provider specified not to advertise property')  # noqa
                    continue

                if field == 'q' and ptype == 'record':
                    LOGGER.debug('q parameter already declared, skipping')
                    continue

                if type_ == 'date':
                    schema = {
                        'type': 'string',
                        'format': 'date'
                    }
                elif type_ == 'float':
                    schema = {
                        'type': 'number',
                        'format': 'float'
                    }
                elif type_ == 'long':
                    schema = {
                        'type': 'integer',
                        'format': 'int64'
                    }
                else:
                    schema = type_

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
                    'summary': 'Get {} item by id'.format(title),
                    'description': desc,
                    'tags': [name],
                    'operationId': 'get{}Feature'.format(name.capitalize()),
                    'parameters': [
                        {'$ref': '{}#/components/parameters/featureId'.format(OPENAPI_YAML['oapif'])},  # noqa
                        {'$ref': '#/components/parameters/f'},
                        {'$ref': '#/components/parameters/lang'}
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
                    'summary': 'Get {} coverage'.format(title),
                    'description': desc,
                    'tags': [name],
                    'operationId': 'get{}Coverage'.format(name.capitalize()),
                    'parameters': [
                        items_f,
                        items_l
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
                    'summary': 'Get {} coverage domain set'.format(title),
                    'description': desc,
                    'tags': [name],
                    'operationId': 'get{}CoverageDomainSet'.format(
                        name.capitalize()),
                    'parameters': [
                        items_f,
                        items_l
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
                    'summary': 'Get {} coverage range type'.format(title),
                    'description': desc,
                    'tags': [name],
                    'operationId': 'get{}CoverageRangeType'.format(
                        name.capitalize()),
                    'parameters': [
                        items_f,
                        items_l
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
                    'summary': 'Fetch a {} tiles description'.format(title), # noqa
                    'description': desc,
                    'tags': [name],
                    'operationId': 'describe{}Tiles'.format(name.capitalize()),
                    'parameters': [
                        items_f,
                        # items_l  TODO: is this useful?
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
                    'summary': 'Get a {} tile'.format(title),
                    'description': desc,
                    'tags': [name],
                    'operationId': 'get{}Tiles'.format(name.capitalize()),
                    'parameters': [
                        {'$ref': '{}#/components/parameters/tileMatrixSetId'.format(OPENAPI_YAML['oat'])},  # noqa
                        {'$ref': '{}#/components/parameters/tileMatrix'.format(OPENAPI_YAML['oat'])},  # noqa
                        {'$ref': '{}#/components/parameters/tileRow'.format(OPENAPI_YAML['oat'])},  # noqa
                        {'$ref': '{}#/components/parameters/tileCol'.format(OPENAPI_YAML['oat'])},  # noqa
                        {
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
                        }
                    ],
                    'responses': {
                        '400': {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '404': {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                        '500': {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                    }
                }
            }
            mimetype = tile_extension['format']['mimetype']
            paths[tiles_data_path]['get']['responses']['200'] = {
                'description': 'successful operation',
                'content': {
                    mimetype: {
                        'schema': {
                            'type': 'string',
                            'format': 'binary'
                        }
                    }
                }
            }

        LOGGER.debug('setting up tiles endpoints')
        edr_extension = filter_providers_by_type(
            collections[k]['providers'], 'edr')

        if edr_extension:
            ep = load_plugin('provider', edr_extension)

            edr_query_endpoints = []

            for qt in ep.get_query_types():
                edr_query_endpoints.append({
                    'path': '{}/{}'.format(collection_name_path, qt),
                    'qt': qt,
                    'op_id': 'query{}{}'.format(qt.capitalize(), k.capitalize())  # noqa
                })
                if ep.instances:
                    edr_query_endpoints.append({
                        'path': '{}/instances/{{instanceId}}/{}'.format(collection_name_path, qt),  # noqa
                        'qt': qt,
                        'op_id': 'query{}Instance{}'.format(qt.capitalize(), k.capitalize())  # noqa
                    })

            for eqe in edr_query_endpoints:
                paths[eqe['path']] = {
                    'get': {
                        'summary': 'query {} by {}'.format(v['description'], eqe['qt']),  # noqa
                        'description': v['description'],
                        'tags': [k],
                        'operationId': eqe['op_id'],
                        'parameters': [
                            {'$ref': '{}/parameters/{}Coords.yaml'.format(OPENAPI_YAML['oaedr'], eqe['qt'])},  # noqa
                            {'$ref': '{}#/components/parameters/datetime'.format(OPENAPI_YAML['oapif'])},  # noqa
                            {'$ref': '{}/parameters/parameter-name.yaml'.format(OPENAPI_YAML['oaedr'])},  # noqa
                            {'$ref': '{}/parameters/z.yaml'.format(OPENAPI_YAML['oaedr'])},  # noqa
                            {'$ref': '#/components/parameters/f'}
                        ],
                        'responses': {
                            '200': {
                                'description': 'Response',
                                'content': {
                                    'application/prs.coverage+json': {
                                        'schema': {
                                            '$ref': '{}/schemas/coverageJSON.yaml'.format(OPENAPI_YAML['oaedr'])}  # noqa
                                        }
                                    }
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
            name = l10n.translate(k, locale_)
            p = load_plugin('process', v['processor'])

            md_desc = l10n.translate(p.metadata['description'], locale_)
            process_name_path = '/processes/{}'.format(name)
            tag = {
                'name': name,
                'description': md_desc,  # noqa
                'externalDocs': {}
            }
            for link in l10n.translate(p.metadata['links'], locale_):
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
                    'description': md_desc,
                    'tags': [name],
                    'operationId': 'describe{}Process'.format(name.capitalize()),  # noqa
                    'parameters': [
                        {'$ref': '#/components/parameters/f'}
                    ],
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        'default': {'$ref': '#/components/responses/default'}
                    }
                }
            }

            paths['{}/execution'.format(process_name_path)] = {
                'post': {
                    'summary': 'Process {} execution'.format(
                        l10n.translate(p.metadata['title'], locale_)),
                    'description': md_desc,
                    'tags': [name],
                    'operationId': 'execute{}Job'.format(name.capitalize()),
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
                paths['{}/execution'.format(process_name_path)]['post']['requestBody']['content']['application/json']['example'] = p.metadata['example']  # noqa

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
            paths['/jobs'] = {
                'get': {
                    'summary': 'Retrieve jobs list',
                    'description': 'Retrieve a list of jobs',
                    'tags': ['server'],
                    'operationId': 'getJobs',
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        '404': {'$ref': '{}/responses/NotFound.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        'default': {'$ref': '#/components/responses/default'}
                    }
                }
            }

            paths['/jobs/{jobId}'] = {
                'get': {
                    'summary': 'Retrieve job details',
                    'description': 'Retrieve job details',
                    'tags': ['server'],
                    'parameters': [
                        name_in_path,
                        {'$ref': '#/components/parameters/f'}
                    ],
                    'operationId': 'getJob',
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        '404': {'$ref': '{}/responses/NotFound.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        'default': {'$ref': '#/components/responses/default'}  # noqa
                    }
                },
                'delete': {
                    'summary': 'Cancel / delete job',
                    'description': 'Cancel / delete job',
                    'tags': ['server'],
                    'parameters': [
                        name_in_path
                    ],
                    'operationId': 'deleteJob',
                    'responses': {
                        '204': {'$ref': '#/components/responses/204'},
                        '404': {'$ref': '{}/responses/NotFound.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        'default': {'$ref': '#/components/responses/default'}  # noqa
                    }
                },
            }

            paths['/jobs/{jobId}/results'] = {
                'get': {
                    'summary': 'Retrieve job results',
                    'description': 'Retrive job resiults',
                    'tags': ['server'],
                    'parameters': [
                        name_in_path,
                        {'$ref': '#/components/parameters/f'}
                    ],
                    'operationId': 'getJobResults',
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        '404': {'$ref': '{}/responses/NotFound.yaml'.format(OPENAPI_YAML['oapip'])},  # noqa
                        'default': {'$ref': '#/components/responses/default'}  # noqa
                    }
                }
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


def validate_openapi_document(instance_dict):
    """
    Validate an OpenAPI document against the OpenAPI schema

    :param instance_dict: dict of OpenAPI instance

    :returns: `bool` of validation
    """

    schema_file = os.path.join(THISDIR, 'schemas', 'openapi',
                               'openapi-3.0.x.json')

    with open(schema_file) as fh2:
        schema_dict = json.load(fh2)
        jsonschema_validate(instance_dict, schema_dict)

        return True


@click.group()
def openapi():
    """OpenAPI management"""
    pass


@click.command()
@click.pass_context
@click.argument('config_file', type=click.File())
@click.option('--format', '-f', 'format_', type=click.Choice(['json', 'yaml']),
              default='yaml', help='output format (json|yaml)')
def generate(ctx, config_file, format_='yaml'):
    """Generate OpenAPI Document"""

    if config_file is None:
        raise click.ClickException('--config/-c required')

    s = yaml_load(config_file)
    pretty_print = s['server'].get('pretty_print', False)
    if format_ == 'yaml':
        click.echo(yaml.safe_dump(get_oas(s), default_flow_style=False))
    else:
        click.echo(to_json(get_oas(s), pretty=pretty_print))


@click.command()
@click.pass_context
@click.argument('openapi_file', type=click.File())
def validate(ctx, openapi_file):
    """Validate OpenAPI Document"""

    if openapi_file is None:
        raise click.ClickException('--openapi/-o required')

    click.echo('Validating {}'.format(openapi_file))
    instance = yaml_load(openapi_file)
    validate_openapi_document(instance)
    click.echo('Valid OpenAPI document')


openapi.add_command(generate)
openapi.add_command(validate)
