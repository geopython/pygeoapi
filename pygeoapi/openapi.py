# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
# Authors: Francesco Bartoli <xbartolone@gmail.com>
# Authors: Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2022 Tom Kralidis
# Copyright (c) 2022 Francesco Bartoli
# Copyright (c) 2023 Ricardo Garcia Silva
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
import io
import json
import logging
import os
from pathlib import Path
from typing import Union

import click
from jsonschema import validate as jsonschema_validate
import yaml

from pygeoapi import l10n
from pygeoapi.models.openapi import OAPIFormat
from pygeoapi.plugin import load_plugin
from pygeoapi.process.manager.base import get_manager
from pygeoapi.provider.base import ProviderTypeError, SchemaType
from pygeoapi.util import (filter_dict_by_key_value, get_provider_by_type,
                           filter_providers_by_type, to_json, yaml_load,
                           get_api_rules, get_base_url)

LOGGER = logging.getLogger(__name__)

OPENAPI_YAML = {
    'oapif-1': 'https://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml',  # noqa
    'oapif-2': 'https://schemas.opengis.net/ogcapi/features/part2/1.0/openapi/ogcapi-features-2.yaml', # noqa
    'oapip': 'https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi',
    'oacov': 'https://raw.githubusercontent.com/tomkralidis/ogcapi-coverages-1/fix-cis/yaml-unresolved',  # noqa
    'oapit': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-tiles/master/openapi/swaggerhub/tiles.yaml',  # noqa
    'oapimt': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-tiles/master/openapi/swaggerhub/map-tiles.yaml',  # noqa
    'oapir': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-records/master/core/openapi',  # noqa
    'oaedr': 'https://schemas.opengis.net/ogcapi/edr/1.0/openapi', # noqa
    'oat': 'https://schemas.opengis.net/ogcapi/tiles/part1/1.0/openapi/ogcapi-tiles-1.yaml'  # noqa
}

THISDIR = os.path.dirname(os.path.realpath(__file__))


def get_ogc_schemas_location(server_config):

    osl = server_config.get('ogc_schemas_location')

    value = 'https://schemas.opengis.net'

    if osl is not None:
        if osl.startswith('http'):
            value = osl
        elif osl.startswith('/'):
            base_url = get_base_url({'server': server_config})
            value = f'{base_url}/schemas'

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

    ref = f'{OPENAPI_YAML[api_type]}/{path}'

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

    api_rules = get_api_rules(cfg)

    osl = get_ogc_schemas_location(cfg['server'])
    OPENAPI_YAML['oapif-1'] = os.path.join(osl, 'ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml')  # noqa
    OPENAPI_YAML['oapif-2'] = os.path.join(osl, 'ogcapi/features/part2/1.0/openapi/ogcapi-features-2.yaml') # noqa

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
        'version': api_rules.api_version
    }
    oas['info'] = info

    oas['servers'] = [{
        'url': get_base_url(cfg),
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
                '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/LandingPage"},  # noqa
                '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
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
                '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
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
                '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/LandingPage"},  # noqa
                '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
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
                '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/LandingPage"},  # noqa
                '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
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
            'crs': {
                'name': 'crs',
                'in': 'query',
                'description': 'Indicates the coordinate reference system for the results.',  # noqa
                'style': 'form',
                'required': False,
                'explode': False,
                'schema': {
                    'format': 'uri',
                    'type': 'string'
                }
            },
            'bbox': {
                'name': 'bbox',
                'in': 'query',
                'description': 'Only features that have a geometry that intersects the bounding box are selected.'  # noqa
                               'The bounding box is provided as four or six numbers, depending on whether the '  # noqa
                               'coordinate reference system includes a vertical axis (height or depth).',  # noqa
                'required': False,
                'style': 'form',
                'explode': False,
                'schema': {
                    'type': 'array',
                    'minItems': 4,
                    'maxItems': 6,
                    'items': {
                        'type': 'number'
                    }
                }
            },
            'bbox-crs': {
                'name': 'bbox-crs',
                'in': 'query',
                'description': 'Indicates the coordinate reference system for the given bbox coordinates.',  # noqa
                'style': 'form',
                'required': False,
                'explode': False,
                'schema': {
                    'format': 'uri',
                    'type': 'string'
                }
            },
            # FIXME: This is not compatible with the bbox-crs definition in
            #        OGCAPI Features Part 2!
            #        We need to change the mapscript provider and
            #        get_collection_map() method in the API!
            #        So this is for de map-provider only.
            'bbox-crs-epsg': {
                'name': 'bbox-crs',
                'in': 'query',
                'description': 'Indicates the EPSG for the given bbox coordinates.',  # noqa
                'required': False,
                'style': 'form',
                'explode': False,
                'schema': {
                    'type': 'integer',
                    'default': 4326
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
        if v.get('visibility', 'default') == 'hidden':
            LOGGER.debug(f'Skipping hidden layer: {k}')
            continue
        name = l10n.translate(k, locale_)
        title = l10n.translate(v['title'], locale_)
        desc = l10n.translate(v['description'], locale_)
        collection_name_path = f'/collections/{k}'
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
                'summary': f'Get {title} metadata',
                'description': desc,
                'tags': [name],
                'operationId': f'describe{name.capitalize()}Collection',
                'parameters': [
                    {'$ref': '#/components/parameters/f'},
                    {'$ref': '#/components/parameters/lang'}
                ],
                'responses': {
                    '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/Collection"},  # noqa
                    '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                    '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                    '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
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

            items_path = f'{collection_name_path}/items'

            coll_properties = deepcopy(oas['components']['parameters']['properties'])  # noqa

            coll_properties['schema']['items']['enum'] = list(p.fields.keys())

            paths[items_path] = {
                'get': {
                    'summary': f'Get {title} items',
                    'description': desc,
                    'tags': [name],
                    'operationId': f'get{name.capitalize()}Features',
                    'parameters': [
                        items_f,
                        items_l,
                        {'$ref': '#/components/parameters/bbox'},
                        {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/limit"},  # noqa
                        {'$ref': '#/components/parameters/crs'},  # noqa
                        {'$ref': '#/components/parameters/bbox-crs'},  # noqa
                        coll_properties,
                        {'$ref': '#/components/parameters/vendorSpecificParameters'},  # noqa
                        {'$ref': '#/components/parameters/skipGeometry'},
                        {'$ref': f"{OPENAPI_YAML['oapir']}/parameters/sortby.yaml"},  # noqa
                        {'$ref': '#/components/parameters/offset'},
                    ],
                    'responses': {
                        '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/Features"},  # noqa
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }
            }

            if p.editable:
                LOGGER.debug('Provider is editable; adding post')

                paths[items_path]['post'] = {
                    'summary': f'Add {title} items',
                    'description': desc,
                    'tags': [name],
                    'operationId': f'add{name.capitalize()}Features',
                    'requestBody': {
                        'description': 'Adds item to collection',
                        'content': {
                            'application/geo+json': {
                                'schema': {}
                            }
                        },
                        'required': True
                    },
                    'responses': {
                        '201': {'description': 'Successful creation'},
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }

                try:
                    schema_ref = p.get_schema(SchemaType.create)
                    paths[items_path]['post']['requestBody']['content'][schema_ref[0]] = {  # noqa
                        'schema': schema_ref[1]
                    }
                except Exception as err:
                    LOGGER.debug(err)

            if ptype == 'record':
                paths[items_path]['get']['parameters'].append(
                    {'$ref': f"{OPENAPI_YAML['oapir']}/parameters/q.yaml"})
            if p.fields:
                queryables_path = f'{collection_name_path}/queryables'

                paths[queryables_path] = {
                    'get': {
                        'summary': f'Get {title} queryables',
                        'description': desc,
                        'tags': [name],
                        'operationId': f'get{name.capitalize()}Queryables',
                        'parameters': [
                            items_f,
                            items_l
                        ],
                        'responses': {
                            '200': {'$ref': '#/components/responses/Queryables'},  # noqa
                            '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                            '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                            '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"},  # noqa
                        }
                    }
                }

            if p.time_field is not None:
                paths[items_path]['get']['parameters'].append(
                    {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/datetime"})  # noqa

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

                path_ = f'{collection_name_path}/items'
                paths[path_]['get']['parameters'].append({
                    'name': field,
                    'in': 'query',
                    'required': False,
                    'schema': schema,
                    'style': 'form',
                    'explode': False
                })

            paths[f'{collection_name_path}/items/{{featureId}}'] = {
                'get': {
                    'summary': f'Get {title} item by id',
                    'description': desc,
                    'tags': [name],
                    'operationId': f'get{name.capitalize()}Feature',
                    'parameters': [
                        {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/featureId"},  # noqa
                        {'$ref': '#/components/parameters/crs'},  # noqa
                        {'$ref': '#/components/parameters/f'},
                        {'$ref': '#/components/parameters/lang'}
                    ],
                    'responses': {
                        '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/Feature"},  # noqa
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }
            }

            try:
                schema_ref = p.get_schema()
                paths[f'{collection_name_path}/items/{{featureId}}']['get']['responses']['200'] = {  # noqa
                    'content': {
                        schema_ref[0]: {
                            'schema': schema_ref[1]
                        }
                    }
                }
            except Exception as err:
                LOGGER.debug(err)

            if p.editable:
                LOGGER.debug('Provider is editable; adding put/delete')
                put_path = f'{collection_name_path}/items/{{featureId}}'  # noqa
                paths[put_path]['put'] = {  # noqa
                    'summary': f'Update {title} items',
                    'description': desc,
                    'tags': [name],
                    'operationId': f'update{name.capitalize()}Features',
                    'parameters': [
                        {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/featureId"}  # noqa
                    ],
                    'requestBody': {
                        'description': 'Updates item in collection',
                        'content': {
                            'application/geo+json': {
                                'schema': {}
                            }
                        },
                        'required': True
                    },
                    'responses': {
                        '204': {'description': 'Successful update'},
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }

                try:
                    schema_ref = p.get_schema(SchemaType.replace)
                    paths[put_path]['put']['requestBody']['content'][schema_ref[0]] = {  # noqa
                        'schema': schema_ref[1]
                    }
                except Exception as err:
                    LOGGER.debug(err)

                paths[f'{collection_name_path}/items/{{featureId}}']['delete'] = {  # noqa
                    'summary': f'Delete {title} items',
                    'description': desc,
                    'tags': [name],
                    'operationId': f'delete{name.capitalize()}Features',
                    'parameters': [
                        {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/featureId"},  # noqa
                    ],
                    'responses': {
                        '200': {'description': 'Successful delete'},
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }

        except ProviderTypeError:
            LOGGER.debug('collection is not feature based')

        LOGGER.debug('setting up coverage endpoints')
        try:
            load_plugin('provider', get_provider_by_type(
                        collections[k]['providers'], 'coverage'))

            coverage_path = f'{collection_name_path}/coverage'

            paths[coverage_path] = {
                'get': {
                    'summary': f'Get {title} coverage',
                    'description': desc,
                    'tags': [name],
                    'operationId': f'get{name.capitalize()}Coverage',
                    'parameters': [
                        items_f,
                        items_l,
                        {'$ref': '#/components/parameters/bbox'},
                        {'$ref': '#/components/parameters/bbox-crs'},  # noqa
                    ],
                    'responses': {
                        '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/Features"},  # noqa
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }
            }

            coverage_domainset_path = f'{collection_name_path}/coverage/domainset'  # noqa

            paths[coverage_domainset_path] = {
                'get': {
                    'summary': f'Get {title} coverage domain set',
                    'description': desc,
                    'tags': [name],
                    'operationId': f'get{name.capitalize()}CoverageDomainSet',
                    'parameters': [
                        items_f,
                        items_l
                    ],
                    'responses': {
                        '200': {'$ref': f"{OPENAPI_YAML['oacov']}/schemas/cis_1.1/domainSet.yaml"},  # noqa
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }
            }

            coverage_rangetype_path = f'{collection_name_path}/coverage/rangetype'  # noqa

            paths[coverage_rangetype_path] = {
                'get': {
                    'summary': f'Get {title} coverage range type',
                    'description': desc,
                    'tags': [name],
                    'operationId': f'get{name.capitalize()}CoverageRangeType',
                    'parameters': [
                        items_f,
                        items_l
                    ],
                    'responses': {
                        '200': {'$ref': f"{OPENAPI_YAML['oacov']}/schemas/cis_1.1/rangeType.yaml"},  # noqa
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
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
                                'items': {'$ref': f"{OPENAPI_YAML['oapit']}#/components/schemas/link"}  # noqa
                            }
                        }
                    }
                }
            )

            tiles_path = f'{collection_name_path}/tiles'

            paths[tiles_path] = {
                'get': {
                    'summary': f'Fetch a {title} tiles description',
                    'description': desc,
                    'tags': [name],
                    'operationId': f'describe{name.capitalize()}Tiles',
                    'parameters': [
                        items_f,
                        # items_l  TODO: is this useful?
                    ],
                    'responses': {
                        '200': {'$ref': '#/components/responses/Tiles'},
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }
            }

            tiles_data_path = f'{collection_name_path}/tiles/{{tileMatrixSetId}}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}'  # noqa

            paths[tiles_data_path] = {
                'get': {
                    'summary': f'Get a {title} tile',
                    'description': desc,
                    'tags': [name],
                    'operationId': f'get{name.capitalize()}Tiles',
                    'parameters': [
                        {'$ref': f"{OPENAPI_YAML['oat']}#/components/parameters/tileMatrixSetId"}, # noqa
                        {'$ref': f"{OPENAPI_YAML['oat']}#/components/parameters/tileMatrix"},  # noqa
                        {'$ref': f"{OPENAPI_YAML['oat']}#/components/parameters/tileRow"},  # noqa
                        {'$ref': f"{OPENAPI_YAML['oat']}#/components/parameters/tileCol"},  # noqa
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
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
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

        LOGGER.debug('setting up edr endpoints')
        edr_extension = filter_providers_by_type(
            collections[k]['providers'], 'edr')

        if edr_extension:
            ep = load_plugin('provider', edr_extension)

            edr_query_endpoints = []

            for qt in ep.get_query_types():
                edr_query_endpoints.append({
                    'path': f'{collection_name_path}/{qt}',
                    'qt': qt,
                    'op_id': f'query{qt.capitalize()}{k.capitalize()}'
                })
                if ep.instances:
                    edr_query_endpoints.append({
                        'path': f'{collection_name_path}/instances/{{instanceId}}/{qt}',  # noqa
                        'qt': qt,
                        'op_id': f'query{qt.capitalize()}Instance{k.capitalize()}'  # noqa
                    })

            for eqe in edr_query_endpoints:
                paths[eqe['path']] = {
                    'get': {
                        'summary': f"query {v['description']} by {eqe['qt']}",  # noqa
                        'description': v['description'],
                        'tags': [k],
                        'operationId': eqe['op_id'],
                        'parameters': [
                            {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/{eqe['qt']}Coords.yaml"},  # noqa
                            {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/datetime"},  # noqa
                            {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/parameter-name.yaml"},  # noqa
                            {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/z.yaml"},  # noqa
                            {'$ref': '#/components/parameters/f'}
                        ],
                        'responses': {
                            '200': {
                                'description': 'Response',
                                'content': {
                                    'application/prs.coverage+json': {
                                        'schema': {
                                            '$ref': f"{OPENAPI_YAML['oaedr']}/schemas/coverageJSON.yaml"  # noqa
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

        LOGGER.debug('setting up maps endpoints')
        map_extension = filter_providers_by_type(
            collections[k]['providers'], 'map')

        if map_extension:
            mp = load_plugin('provider', map_extension)

            map_f = deepcopy(oas['components']['parameters']['f'])
            map_f['schema']['enum'] = [map_extension['format']['name']]
            map_f['schema']['default'] = map_extension['format']['name']

            pth = f'/collections/{k}/map'
            paths[pth] = {
                'get': {
                    'summary': 'Get map',
                    'description': f"{v['description']} map",
                    'tags': [k],
                    'operationId': 'getMap',
                    'parameters': [
                        {'$ref': '#/components/parameters/bbox'},
                        {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/datetime"},  # noqa
                        {
                            'name': 'width',
                            'in': 'query',
                            'description': 'Response image width',
                            'required': False,
                            'schema': {
                                'type': 'integer',
                            },
                            'style': 'form',
                            'explode': False
                        },
                        {
                            'name': 'height',
                            'in': 'query',
                            'description': 'Response image height',
                            'required': False,
                            'schema': {
                                'type': 'integer',
                            },
                            'style': 'form',
                            'explode': False
                        },
                        {
                            'name': 'transparent',
                            'in': 'query',
                            'description': 'Background transparency of map (default=true).',  # noqa
                            'required': False,
                            'schema': {
                                'type': 'boolean',
                                'default': True,
                            },
                            'style': 'form',
                            'explode': False
                        },
                        {'$ref': '#/components/parameters/bbox-crs-epsg'},
                        map_f
                    ],
                    'responses': {
                        '200': {
                            'description': 'Response',
                            'content': {
                                'application/json': {}
                            }
                        },
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"},  # noqa
                    }
                }
            }
            if mp.time_field is not None:
                paths[pth]['get']['parameters'].append(
                    {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/datetime"})  # noqa

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

    process_manager = get_manager(cfg)

    if len(process_manager.processes) > 0:
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
                    '200': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/ProcessList.yaml"},  # noqa
                    'default': {'$ref': '#/components/responses/default'}
                }
            }
        }
        LOGGER.debug('setting up processes')

        for k, v in process_manager.processes.items():
            if k.startswith('_'):
                LOGGER.debug(f'Skipping hidden layer: {k}')
                continue
            name = l10n.translate(k, locale_)
            p = process_manager.get_processor(k)
            md_desc = l10n.translate(p.metadata['description'], locale_)
            process_name_path = f'/processes/{name}'
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
                    'operationId': f'describe{name.capitalize()}Process',
                    'parameters': [
                        {'$ref': '#/components/parameters/f'}
                    ],
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        'default': {'$ref': '#/components/responses/default'}
                    }
                }
            }

            paths[f'{process_name_path}/execution'] = {
                'post': {
                    'summary': f"Process {l10n.translate(p.metadata['title'], locale_)} execution",  # noqa
                    'description': md_desc,
                    'tags': [name],
                    'operationId': f'execute{name.capitalize()}Job',
                    'responses': {
                        '200': {'$ref': '#/components/responses/200'},
                        '201': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/ExecuteAsync.yaml"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/NotFound.yaml"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/ServerError.yaml"},  # noqa
                        'default': {'$ref': '#/components/responses/default'}
                    },
                    'requestBody': {
                        'description': 'Mandatory execute request JSON',
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    '$ref': f"{OPENAPI_YAML['oapip']}/schemas/execute.yaml"  # noqa
                                }
                            }
                        }
                    }
                }
            }
            if 'example' in p.metadata:
                paths[f'{process_name_path}/execution']['post']['requestBody']['content']['application/json']['example'] = p.metadata['example']  # noqa

            name_in_path = {
                'name': 'jobId',
                'in': 'path',
                'description': 'job identifier',
                'required': True,
                'schema': {
                    'type': 'string'
                }
            }

        paths['/jobs'] = {
            'get': {
                'summary': 'Retrieve jobs list',
                'description': 'Retrieve a list of jobs',
                'tags': ['jobs'],
                'operationId': 'getJobs',
                'responses': {
                    '200': {'$ref': '#/components/responses/200'},
                    '404': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/NotFound.yaml"},  # noqa
                    'default': {'$ref': '#/components/responses/default'}
                }
            }
        }

        paths['/jobs/{jobId}'] = {
            'get': {
                'summary': 'Retrieve job details',
                'description': 'Retrieve job details',
                'tags': ['jobs'],
                'parameters': [
                    name_in_path,
                    {'$ref': '#/components/parameters/f'}
                ],
                'operationId': 'getJob',
                'responses': {
                    '200': {'$ref': '#/components/responses/200'},
                    '404': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/NotFound.yaml"},  # noqa
                    'default': {'$ref': '#/components/responses/default'}  # noqa
                }
            },
            'delete': {
                'summary': 'Cancel / delete job',
                'description': 'Cancel / delete job',
                'tags': ['jobs'],
                'parameters': [
                    name_in_path
                ],
                'operationId': 'deleteJob',
                'responses': {
                    '204': {'$ref': '#/components/responses/204'},
                    '404': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/NotFound.yaml"},  # noqa
                    'default': {'$ref': '#/components/responses/default'}  # noqa
                }
            },
        }

        paths['/jobs/{jobId}/results'] = {
            'get': {
                'summary': 'Retrieve job results',
                'description': 'Retrive job resiults',
                'tags': ['jobs'],
                'parameters': [
                    name_in_path,
                    {'$ref': '#/components/parameters/f'}
                ],
                'operationId': 'getJobResults',
                'responses': {
                    '200': {'$ref': '#/components/responses/200'},
                    '404': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/NotFound.yaml"},  # noqa
                    'default': {'$ref': '#/components/responses/default'}  # noqa
                }
            }
        }

        tag = {
            'name': 'jobs',
            'description': 'Process jobs',
        }
        oas['tags'].insert(1, tag)

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


def generate_openapi_document(cfg_file: Union[Path, io.TextIOWrapper],
                              output_format: OAPIFormat):
    """
    Generate an OpenAPI document from the configuration file

    :param cfg_file: configuration Path instance
    :param output_format: output format for OpenAPI document

    :returns: content of the OpenAPI document in the output
              format requested
    """
    if isinstance(cfg_file, Path):
        with cfg_file.open(mode="r") as cf:
            s = yaml_load(cf)
    else:
        s = yaml_load(cfg_file)
    pretty_print = s['server'].get('pretty_print', False)

    if output_format == 'yaml':
        content = yaml.safe_dump(get_oas(s), default_flow_style=False)
    else:
        content = to_json(get_oas(s), pretty=pretty_print)
    return content


@click.group()
def openapi():
    """OpenAPI management"""
    pass


@click.command()
@click.pass_context
@click.argument('config_file', type=click.File(encoding='utf-8'))
@click.option('--format', '-f', 'format_', type=click.Choice(['json', 'yaml']),
              default='yaml', help='output format (json|yaml)')
@click.option('--output-file', '-of', type=click.File('w', encoding='utf-8'),
              help='Name of output file')
def generate(ctx, config_file, output_file, format_='yaml'):
    """Generate OpenAPI Document"""

    if config_file is None:
        raise click.ClickException('--config/-c required')

    content = generate_openapi_document(config_file, format_)

    if output_file is None:
        click.echo(content)
    else:
        click.echo(f'Generating {output_file.name}')
        output_file.write(content)
        click.echo('Done')


@click.command()
@click.pass_context
@click.argument('openapi_file', type=click.File())
def validate(ctx, openapi_file):
    """Validate OpenAPI Document"""

    if openapi_file is None:
        raise click.ClickException('--openapi/-o required')

    click.echo(f'Validating {openapi_file}')
    instance = yaml_load(openapi_file)
    validate_openapi_document(instance)
    click.echo('Valid OpenAPI document')


openapi.add_command(generate)
openapi.add_command(validate)
