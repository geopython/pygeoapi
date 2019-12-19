# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2019 Tom Kralidis
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

import click
import yaml

from pygeoapi.plugin import load_plugin
from pygeoapi.util import yaml_load

LOGGER = logging.getLogger(__name__)

# TODO: handle this better once schemas are public/final
# allow also for schema caching
OPENAPI_YAML = {
    'oapif': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml',  # noqa
    'oapip': 'https://raw.githubusercontent.com/opengeospatial/wps-rest-binding/master/core/openapi'  # noqa
}


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
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                200: {'$ref': '{}#/components/responses/LandingPage'.format(OPENAPI_YAML['oapif'])},  # noqa
                400: {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                500: {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
            }
        }
    }

    paths['/openapi'] = {
        'get': {
            'summary': 'This document',
            'description': 'This document',
            'tags': ['server'],
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                200: {'$ref': '#/components/responses/200'},
                400: {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                'default': {'$ref': '#/components/responses/default'}
            }
        }
    }

    paths['/conformance'] = {
        'get': {
            'summary': 'API conformance definition',
            'description': 'API conformance definition',
            'tags': ['server'],
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                200: {'$ref': '{}#/components/responses/ConformanceDeclaration'.format(OPENAPI_YAML['oapif'])},  # noqa
                400: {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                500: {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
            }
        }
    }

    paths['/collections'] = {
        'get': {
            'summary': 'Feature Collections',
            'description': 'Feature Collections',
            'tags': ['server'],
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                200: {'$ref': '{}#/components/responses/Collections'.format(OPENAPI_YAML['oapif'])},  # noqa
                400: {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                500: {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
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

    oas['components'] = {
        'responses': {
            '200': {
                'description': 'successful operation',
            },
            'default': {
               'description': 'Unexpected error',
               'content': gen_media_type_object('application/json', 'oapip', 'schemas/exception.yaml')  # noqa
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
        }
    }

    items_f = deepcopy(oas['components']['parameters']['f'])
    items_f['schema']['enum'].append('csv')

    LOGGER.debug('setting up datasets')
    for k, v in cfg['datasets'].items():
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
                'summary': 'Get feature collection metadata'.format(v['title']),  # noqa
                'description': v['description'],
                'tags': [k],
                'parameters': [
                    {'$ref': '#/components/parameters/f'}
                ],
                'responses': {
                    200: {'$ref': '{}#/components/responses/Collection'.format(OPENAPI_YAML['oapif'])},  # noqa
                    400: {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    404: {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    500: {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

        items_path = '{}/items'.format(collection_name_path)

        paths[items_path] = {
            'get': {
                'summary': 'Get {} features'.format(v['title']),
                'description': v['description'],
                'tags': [k],
                'parameters': [
                    items_f,
                    {'$ref': '{}#/components/parameters/bbox'.format(OPENAPI_YAML['oapif'])},  # noqa
                    {'$ref': '{}#/components/parameters/limit'.format(OPENAPI_YAML['oapif'])},  # noqa
                    {'$ref': '#/components/parameters/sortby'},
                    {'$ref': '#/components/parameters/startindex'}
                ],
                'responses': {
                    200: {'$ref': '{}#/components/responses/Features'.format(OPENAPI_YAML['oapif'])},  # noqa
                    400: {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    404: {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    500: {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

        p = load_plugin('provider', cfg['datasets'][k]['provider'])

        if p.time_field is not None:
            paths[items_path]['get']['parameters'].append(
                {'$ref': '{}#/components/parameters/datetime'.format(OPENAPI_YAML['oapif'])})  # noqa

        for k2, v2 in p.fields.items():
            if p.properties and k2 in p.properties:
                path_ = '{}/items'.format(collection_name_path)

                if v2['type'] == 'date':
                    schema = {
                        'type': 'string',
                        'format': 'date'
                    }
                elif v2['type'] == 'float':
                    schema = {
                        'type': 'number',
                        'format': 'float'
                    }
                elif v2['type'] == 'long':
                    schema = {
                        'type': 'integer',
                        'format': 'int64'
                    }
                else:
                    schema = {
                        'type': v2['type']
                    }

                paths['{}'.format(path_)]['get']['parameters'].append({
                    'name': k2,
                    'in': 'query',
                    'required': False,
                    'schema': schema,
                    'style': 'form',
                    'explode': False
                })

        paths['{}/items/{{featureId}}'.format(collection_name_path)] = {
            'get': {
                'summary': 'Get {} feature by id'.format(v['title']),
                'description': v['description'],
                'tags': [k],
                'parameters': [
                    {'$ref': '{}#/components/parameters/featureId'.format(OPENAPI_YAML['oapif'])},  # noqa
                    {'$ref': '#/components/parameters/f'}
                ],
                'responses': {
                    200: {'$ref': '{}#/components/responses/Feature'.format(OPENAPI_YAML['oapif'])},  # noqa
                    400: {'$ref': '{}#/components/responses/InvalidParameter'.format(OPENAPI_YAML['oapif'])},  # noqa
                    404: {'$ref': '{}#/components/responses/NotFound'.format(OPENAPI_YAML['oapif'])},  # noqa
                    500: {'$ref': '{}#/components/responses/ServerError'.format(OPENAPI_YAML['oapif'])}  # noqa
                }
            }
        }

    paths['/processes'] = {
        'get': {
            'summary': 'Processes',
            'description': 'Processes',
            'tags': ['server'],
            'parameters': [
                {'$ref': '#/components/parameters/f'}
            ],
            'responses': {
                200: {'$ref': '#/components/responses/200'},
                'default': {'$ref': '#/components/responses/default'}
            }
        }
    }

    LOGGER.debug('setting up processes')

    processes = cfg.get('processes', {})

    if processes:
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
                    'summary': 'Get process metadata'.format(
                        p.metadata['title']),
                    'description': p.metadata['description'],
                    'tags': [k],
                    'parameters': [
                        {'$ref': '#/components/parameters/f'}
                    ],
                    'responses': {
                        200: {'$ref': '#/components/responses/200'},
                        'default': {'$ref': '#/components/responses/default'}
                    }
                }
            }
            paths['{}/jobs'.format(process_name_path)] = {
                'get': {
                    'summary': 'Retrieve job list for process',
                    'description': p.metadata['description'],
                    'tags': [k],
                    'responses': {
                        200: {'$ref': '#/components/responses/200'},
                        'default': {'$ref': '#/components/responses/default'}
                    }
                },
                'post': {
                    'summary': 'Process {} execution'.format(
                        p.metadata['title']),
                    'description': p.metadata['description'],
                    'tags': [k],
                    'parameters': [],
                    'responses': {
                        200: {'$ref': '#/components/responses/200'},
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
    """Generate OpenAPI Document"""

    if config_file is None:
        raise click.ClickException('--config/-c required')
    with open(config_file) as ff:
        s = yaml_load(ff)
        click.echo(yaml.safe_dump(get_oas(s), default_flow_style=False))
