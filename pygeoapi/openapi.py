# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
# Authors: Francesco Bartoli <xbartolone@gmail.com>
# Authors: Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2024 Tom Kralidis
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
from pygeoapi.api import all_apis
from pygeoapi.models.openapi import OAPIFormat
from pygeoapi.util import (filter_dict_by_key_value, to_json, yaml_load,
                           get_api_rules, get_base_url)

LOGGER = logging.getLogger(__name__)

OPENAPI_YAML = {
    'oapif-1': 'https://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml',  # noqa
    'oapif-2': 'https://schemas.opengis.net/ogcapi/features/part2/1.0/openapi/ogcapi-features-2.yaml', # noqa
    'oapip': 'https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi',
    'oacov': 'https://raw.githubusercontent.com/tomkralidis/ogcapi-coverages-1/fix-cis/yaml-unresolved',  # noqa
    'oapir': 'https://raw.githubusercontent.com/opengeospatial/ogcapi-records/master/core/openapi',  # noqa
    'oaedr': 'https://schemas.opengis.net/ogcapi/edr/1.0/openapi', # noqa
    'oapit': 'https://schemas.opengis.net/ogcapi/tiles/part1/1.0/openapi/ogcapi-tiles-1.yaml',  # noqa
    'pygeoapi': 'https://raw.githubusercontent.com/geopython/pygeoapi/master/pygeoapi/schemas/config/pygeoapi-config-0.x.yml'  # noqa
}

THISDIR = os.path.dirname(os.path.realpath(__file__))


def get_ogc_schemas_location(server_config: dict) -> str:
    """
    Determine OGC schemas location

    :param server_config: `dict` of server configuration

    :returns: `str` of OGC schemas location
    """

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
def gen_media_type_object(media_type: str, api_type: str, path: str) -> dict:
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
def gen_response_object(description: str, media_type: str,
                        api_type: str, path: str) -> dict:
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


def get_oas_30(cfg: dict, fail_on_invalid_collection: bool = True) -> dict:
    """
    Generates an OpenAPI 3.0 Document

    :param cfg: configuration object
    :param fail_on_invalid_collection: `bool` of whether to fail on an invalid
                                       collection

    :returns: dict of OpenAPI definition
    """

    paths = {}

    # TODO: make openapi multilingual (default language only for now)
    locale_ = l10n.get_locales(cfg)[0]

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

    oas['components'] = {
        'responses': {
            '200': {
                'description': 'successful operation'
            },
            '204': {
                'description': 'no content'
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
        'parameters': get_oas_30_parameters(cfg=cfg, locale_=locale_),
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

    for k, v in get_visible_collections(cfg).items():
        name = l10n.translate(k, locale_)
        title = l10n.translate(v['title'], locale_)
        desc = l10n.translate(v['description'], locale_)
        collection_name_path = f'/collections/{k}'
        tag = {
            'name': name,
            'description': desc,
            'externalDocs': {}
        }
        for link in l10n.translate(v.get('links', []), locale_):
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

    oas['paths'] = paths

    for api_name, api_module in all_apis().items():
        LOGGER.debug(f'Adding OpenAPI definitions for {api_name}')

        try:
            sub_tags, sub_paths = api_module.get_oas_30(cfg, locale_)
            oas['paths'].update(sub_paths['paths'])
            oas['tags'].extend(sub_tags)
        except Exception as err:
            if fail_on_invalid_collection:
                raise
            else:
                LOGGER.warning(f'Resource not added to OpenAPI: {err}')

    if cfg['server'].get('admin', False):
        schema_dict = get_config_schema()
        oas['definitions'] = schema_dict['definitions']
        LOGGER.debug('Adding admin endpoints')
        oas['paths'].update(get_admin())

    return oas


def get_oas_30_parameters(cfg: dict, locale_: str):
    server_locales = l10n.get_locales(cfg)
    return {
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
            },
            'resourceId': {
                'name': 'resourceId',
                'in': 'path',
                'description': 'Configuration resource identifier',
                'required': True,
                'schema': {
                    'type': 'string'
                 }
            }
        }


def get_visible_collections(cfg: dict) -> dict:
    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')

    return {
        k: v
        for k, v in collections.items()
        if v.get('visibility', 'default') != 'hidden'
    }


def get_config_schema():
    schema_file = os.path.join(THISDIR, 'schemas', 'config',
                               'pygeoapi-config-0.x.yml')

    with open(schema_file) as fh2:
        return yaml_load(fh2)


def get_admin():

    schema_dict = get_config_schema()

    paths = {}

    paths['/admin/config'] = {
        'get': {
            'summary': 'Get admin configuration',
            'description': 'Get admin configuration',
            'tags': ['admin'],
            'operationId': 'getAdminConfig',
            'parameters': [
                {'$ref': '#/components/parameters/f'},
                {'$ref': '#/components/parameters/lang'}
            ],
            'responses': {
                '200': {
                    'description': 'Successful response',
                    'content': {
                        'application/json': {
                            'schema': schema_dict
                        }
                    }
                }
            }
        },
        'put': {
            'summary': 'Update admin configuration full',
            'description': 'Update admin configuration full',
            'tags': ['admin'],
            'operationId': 'putAdminConfig',
            'requestBody': {
                'description': 'Updates admin configuration',
                'content': {
                    'application/json': {
                        'schema': schema_dict
                    }
                },
                'required': True
            },
            'responses': {
                '204': {'$ref': '#/components/responses/204'},
                '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
            }
        },
        'patch': {
            'summary': 'Partially update admin configuration',
            'description': 'Partially update admin configuration',
            'tags': ['admin'],
            'operationId': 'patchAdminConfig',
            'requestBody': {
                'description': 'Updates admin configuration',
                'content': {
                    'application/json': {
                        'schema': schema_dict
                    }
                },
                'required': True
            },
            'responses': {
                '204': {'$ref': '#/components/responses/204'},
                '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
            }
        }
    }
    paths['/admin/config/resources'] = {
        'get': {
            'summary': 'Get admin configuration resources',
            'description': 'Get admin configuration resources',
            'tags': ['admin'],
            'operationId': 'getAdminConfigResources',
            'parameters': [
                {'$ref': '#/components/parameters/f'},
                {'$ref': '#/components/parameters/lang'}
            ],
            'responses': {
                '200': {
                    'description': 'Successful response',
                    'content': {
                        'application/json': {
                            'schema': schema_dict['properties']['resources']['patternProperties']['^.*$']  # noqa
                        }
                    }
                }
            }
        },
        'post': {
            'summary': 'Create admin configuration resource',
            'description': 'Create admin configuration resource',
            'tags': ['admin'],
            'operationId': 'postAdminConfigResource',
            'requestBody': {
                'description': 'Adds resource to configuration',
                'content': {
                    'application/json': {
                        'schema': schema_dict['properties']['resources']['patternProperties']['^.*$']  # noqa
                    }
                },
                'required': True
            },
            'responses': {
                '201': {'description': 'Successful creation'},
                '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
            }
        },
    }
    paths['/admin/config/resources/{resourceId}'] = {
        'get': {
            'summary': 'Get admin configuration resource',
            'description': 'Get admin configuration resource',
            'tags': ['admin'],
            'operationId': 'getAdminConfigResource',
            'parameters': [
                {'$ref': '#/components/parameters/resourceId'},
                {'$ref': '#/components/parameters/f'},
                {'$ref': '#/components/parameters/lang'}
            ],
            'responses': {
                '200': {
                    'description': 'Successful response',
                    'content': {
                        'application/json': {
                            'schema': schema_dict['properties']['resources']['patternProperties']['^.*$']  # noqa
                        }
                    }
                }
            }
        },
        'put': {
            'summary': 'Update admin configuration resource',
            'description': 'Update admin configuration resource',
            'tags': ['admin'],
            'operationId': 'putAdminConfigResource',
            'parameters': [
                {'$ref': '#/components/parameters/resourceId'},
            ],
            'requestBody': {
                'description': 'Updates admin configuration resource',
                'content': {
                    'application/json': {
                        'schema': schema_dict['properties']['resources']['patternProperties']['^.*$']  # noqa
                    }
                },
                'required': True
            },
            'responses': {
                '204': {'$ref': '#/components/responses/204'},
                '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
            }
        },
        'patch': {
            'summary': 'Partially update admin configuration resource',
            'description': 'Partially update admin configuration resource',
            'tags': ['admin'],
            'operationId': 'patchAdminConfigResource',
            'parameters': [
                {'$ref': '#/components/parameters/resourceId'},
            ],
            'requestBody': {
                'description': 'Updates admin configuration resource',
                'content': {
                    'application/json': {
                        'schema': schema_dict['properties']['resources']['patternProperties']['^.*$']  # noqa
                    }
                },
                'required': True
            },
            'responses': {
                '204': {'$ref': '#/components/responses/204'},
                '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
            }
        },
        'delete': {
            'summary': 'Delete admin configuration resource',
            'description': 'Delete admin configuration resource',
            'tags': ['admin'],
            'operationId': 'deleteAdminConfigResource',
            'parameters': [
                {'$ref': '#/components/parameters/resourceId'},
            ],
            'responses': {
                '204': {'$ref': '#/components/responses/204'},
                '404': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/NotFound.yaml"},  # noqa
                'default': {'$ref': '#/components/responses/default'}  # noqa
            }
        }
    }

    return paths


def get_oas(cfg: dict, fail_on_invalid_collection: bool = True,
            version='3.0') -> dict:
    """
    Stub to generate OpenAPI Document

    :param cfg: `dict` configuration
    :param fail_on_invalid_collection: `bool` of whether to fail on an
                                       invalid collection
    :param version: version of OpenAPI (default 3.0)

    :returns: `dict` of OpenAPI definition
    """

    if version == '3.0':
        return get_oas_30(
            cfg, fail_on_invalid_collection=fail_on_invalid_collection)
    else:
        raise RuntimeError('OpenAPI version not supported')


def validate_openapi_document(instance_dict: dict) -> bool:
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
                              output_format: OAPIFormat,
                              fail_on_invalid_collection: bool = True) -> str:
    """
    Generate an OpenAPI document from the configuration file

    :param cfg_file: configuration Path instance (`str` of filepath
                     or parsed `dict`)
    :param output_format: output format for OpenAPI document
    :param fail_on_invalid_collection: `bool` of whether to fail on an
                                       invalid collection

    :returns: `str` of the OpenAPI document in the output format requested
    """

    LOGGER.debug(f'Loading configuration {cfg_file}')

    if isinstance(cfg_file, Path):
        with cfg_file.open(mode="r") as cf:
            s = yaml_load(cf)
    else:
        s = yaml_load(cfg_file)

    pretty_print = s['server'].get('pretty_print', False)

    oas = get_oas(s, fail_on_invalid_collection=fail_on_invalid_collection)

    if output_format == 'yaml':
        content = yaml.safe_dump(oas, default_flow_style=False)
    else:
        content = to_json(oas, pretty=pretty_print)
    return content


def load_openapi_document() -> dict:
    """
    Open OpenAPI document from `PYGEOAPI_OPENAPI` environment variable

    :returns: `dict` of OpenAPI document
    """

    pygeoapi_openapi = os.environ.get('PYGEOAPI_OPENAPI')

    with open(pygeoapi_openapi, encoding='utf8') as ff:
        if pygeoapi_openapi.endswith(('.yaml', '.yml')):
            openapi_ = yaml_load(ff)
        else:  # JSON string, do not transform
            openapi_ = ff.read()

    return openapi_


@click.group()
def openapi():
    """OpenAPI management"""
    pass


@click.command()
@click.pass_context
@click.argument('config_file', type=click.File(encoding='utf-8'))
@click.option('--fail-on-invalid-collection/--no-fail-on-invalid-collection',
              '-fic', default=True, help='Fail on invalid collection')
@click.option('--format', '-f', 'format_', type=click.Choice(['json', 'yaml']),
              default='yaml', help='output format (json|yaml)')
@click.option('--output-file', '-of', type=click.File('w', encoding='utf-8'),
              help='Name of output file')
def generate(ctx, config_file, output_file, format_='yaml',
             fail_on_invalid_collection=True):
    """Generate OpenAPI Document"""

    if config_file is None:
        raise click.ClickException('--config/-c required')

    content = generate_openapi_document(
        config_file, format_, fail_on_invalid_collection)

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
