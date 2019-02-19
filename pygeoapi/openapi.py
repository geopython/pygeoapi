# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2018 Tom Kralidis
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

import logging

import click
import yaml

from pygeoapi.provider import load_provider

LOGGER = logging.getLogger(__name__)


def get_oas_30(cfg):
    """
    Generates an OpenAPI 3.0 Document

    :param cfg: configuration object

    :returns: OpenAPI definition YAML dict
    """

    paths = {}
    LOGGER.debug('setting up server info')
    oas = {
        'openapi': '3.0.1',
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
        'version': '3.0.1'
    }
    oas['info'] = info

    oas['servers'] = [{
        'url': cfg['server']['url'],
        'description': cfg['metadata']['identification']['description']
    }]

    paths['/'] = {
        'get': {
            'summary': 'API',
            'description': 'API',
            'tags': ['server'],
            'responses': {
                200: {
                    'description': 'successful operation'
                }
            }
        }
    }

    paths['/api'] = {
        'get': {
            'summary': 'This document',
            'description': 'This document',
            'tags': ['server'],
            'responses': {
                200: {
                    'description': 'successful operation'
                }
            }
        }
    }

    paths['/conformance'] = {
        'get': {
            'summary': 'API conformance definition',
            'description': 'API conformance definition',
            'tags': ['server'],
            'responses': {
                200: {
                    'description': 'successful operation'
                }
            }
        }
    }

    paths['/collections'] = {
        'get': {
            'summary': 'Feature Collections',
            'description': 'Feature Collections',
            'tags': ['server'],
            'responses': {
                200: {
                    'description': 'successful operation'
                }
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
                'responses': {
                    200: {
                        'description': 'successful operation'
                    },
                    400: {
                        'description': 'Invalid ID supplied'
                    },
                    404: {
                        'description': 'not found'
                    }
                }
            }
        }

        paths['{}/items'.format(collection_name_path)] = {
            'get': {
                'summary': 'Get {} features'.format(v['title']),
                'description': v['description'],
                'tags': [k],
                'parameters': [
                    {'$ref': '#/components/parameters/limit'}
                ],
                'responses': {
                    200: {
                        'description': 'successful operation'
                    },
                    400: {
                        'description': 'Invalid ID supplied'
                    },
                    404: {
                        'description': 'not found'
                    }
                }
            }
        }

        p = load_provider(cfg['datasets'][k]['provider'])

        for k2, v2 in p.fields.items():
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

        paths['{}/items/{{id}}'.format(collection_name_path)] = {
            'get': {
                'summary': 'Get {} feature by ID'.format(v['title']),
                'description': v['description'],
                'tags': [k],
                'parameters': [
                    {'$ref': '#/components/parameters/id'}
                ],
                'responses': {
                    200: {
                        'description': 'successful operation'
                    },
                    400: {
                        'description': 'Invalid ID supplied'
                    },
                    404: {
                        'description': 'not found'
                    }
                }
            }
        }
    oas['paths'] = paths

    oas['components'] = {
        'parameters': {
            'id': {
                'name': 'id',
                'in': 'path',
                'description': 'The id of a feature',
                'required': True,
                'schema': {
                    'type': 'string'
                }
            },
            'limit': {
                'name': 'limit',
                'in': 'query',
                'description': 'The optional limit parameter limits the number of items that are presented in the response document. Only items are counted that are on the first level of the collection in the response document. Nested objects contained within the explicitly requested items shall not be counted. Minimum = 1. Maximum = 10000. Default = {}.'.format(cfg['server']['limit']),  # noqa
                'required': False,
                'schema': {
                    'type': 'integer',
                    'minimum': 1,
                    'maximum': 10000,
                    'default': cfg['server']['limit']
                },
                'style': 'form',
                'explode': False
            }
        }
    }

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
        s = yaml.load(ff)
        click.echo(yaml.safe_dump(get_oas(s), default_flow_style=False))
