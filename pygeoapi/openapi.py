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

    url = 'http://{}'.format(cfg['server']['host'])
    if cfg['server']['port'] not in [80, 443]:
        url = '{}:{}'.format(url, cfg['server']['port'])
    oas['servers'] = [{
        'url': url,
        'description': cfg['metadata']['identification']['description']
    }]

    paths['/'] = {
        'get': {
            'summary': 'Feature Collections',
            'descriptions': 'Feature Collections',
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
    paths['/api/conformance'] = {
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
        oas['tags'].append(tag)
        paths['/{}'.format(k)] = {
            'get': {
                'summary': 'Get {} features'.format(v['title']),
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


@click.command()
@click.pass_context
@click.option('--config', '-c', 'config_file', help='configuration file')
def generate_openapi_document(ctx, config_file):
    """Generate OpenAPI Document"""

    if config_file is None:
        raise click.ClickException('--config/-c required')
    with open(config_file) as ff:
        s = yaml.load(ff)
        click.echo(yaml.dump(get_oas(s), default_flow_style=False))
