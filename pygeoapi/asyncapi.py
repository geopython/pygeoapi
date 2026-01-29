# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2026 Tom Kralidis
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
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import click
from jsonschema import validate as jsonschema_validate
import yaml

from pygeoapi import __version__, l10n
from pygeoapi.models.openapi import OAPIFormat
from pygeoapi.util import to_json, yaml_load, remove_url_auth

LOGGER = logging.getLogger(__name__)

THISDIR = os.path.dirname(os.path.realpath(__file__))


def gen_asyncapi(cfg: dict) -> dict:
    """
    Generate an AsyncAPI document

    :param cfg: `dict` of pygeoapi configuration

    :returns: `dict` of AsyncAPI document
    """

    server_locales = l10n.get_locales(cfg)
    locale_ = server_locales[0]

    LOGGER.debug('Generating AsyncAPI document')

    title = l10n.translate(cfg['metadata']['identification']['title'], locale_)  # noqa
    description = l10n.translate(cfg['metadata']['identification']['description'], locale_)  # noqa
    tags = l10n.translate(cfg['metadata']['identification']['keywords'], locale_)  # noqa

    u = cfg['pubsub']['broker']['url']
    up = urlparse(u)
    protocol = up.scheme
    url = remove_url_auth(u).replace(f'{protocol}://', '')

    a = {
        'asyncapi': '3.0.0',
        'id': cfg['server']['url'],
        'defaultContentType': 'application/json',
        'info': {
            'version': __version__,
            'title': title,
            'description': description,
            'license': {
                'name': cfg['metadata']['license']['name'],
                'url': cfg['metadata']['license']['url']
            },
            'contact': {
                'name': cfg['metadata']['contact']['name'],
                'email': cfg['metadata']['contact']['email']
            },
            'tags': [{'name': tag} for tag in tags],
            'externalDocs': {
                'url': cfg['metadata']['identification']['url']
            },
        },
        'servers': {
            'default': {
                'host': url,
                'protocol': protocol,
                'description': description
            }
        },
        'channels': {},
        'operations': {}
    }
    if cfg['metadata']['contact']['url'].startswith('http'):
        a['info']['contact']['url'] = cfg['metadata']['contact']['url']

    if cfg['pubsub']['broker'].get('channel') is not None:
        channel_prefix = cfg['pubsub']['broker']['channel']
    else:
        channel_prefix = ''

    LOGGER.debug('Generating channels foreach collection')
    for key, value in cfg['resources'].items():
        if value['type'] not in ['collection']:
            LOGGER.debug('Skipping')
            continue

        title = l10n.translate(value['title'], locale_)
        channel_address = f'{channel_prefix}/collections/{key}'

        channel = {
            'description': title,
            'address': channel_address,
            'messages': {
                'DefaultMessage': {
                    'payload': {
                        '$ref': 'https://raw.githubusercontent.com/wmo-im/wis2-monitoring-events/refs/heads/main/schemas/cloudevents-v1.0.2.yaml'  # noqa
                    }
                }
            }
        }

        operation = {
            f'publish-{key}': {
                'action': 'send',
                'channel': {
                    '$ref': f'#/channels/notify-{key}'
                }
            },
            f'consume-{key}': {
                'action': 'receive',
                'channel': {
                    '$ref': f'#/channels/notify-{key}'
                }
            }
        }

        a['channels'][f'notify-{key}'] = channel
        a['operations'].update(operation)

    return a


def get_asyncapi(cfg, version='3.0'):
    """
    Stub to generate AsyncAPI Document

    :param cfg: configuration object
    :param version: version of AsyncAPI (default 3.0)

    :returns: AsyncAPI definition YAML dict
    """

    if version == '3.0':
        return gen_asyncapi(cfg)
    else:
        raise RuntimeError('AsyncAPI version not supported')


def validate_asyncapi_document(instance_dict):
    """
    Validate an AsyncAPI document against the AsyncAPI schema

    :param instance_dict: dict of AsyncAPI instance

    :returns: `bool` of validation
    """

    schema_file = os.path.join(
        THISDIR, 'resources', 'schemas', 'asyncapi', 'asyncapi-3.0.0.json')

    LOGGER.debug(f'Validating against {schema_file}')
    with open(schema_file) as fh2:
        schema_dict = json.load(fh2)
        jsonschema_validate(instance_dict, schema_dict)

        return True


def generate_asyncapi_document(cfg: dict, output_format: OAPIFormat):
    """
    Generate an AsyncAPI document from the configuration file

    :param cfg: `dict` of configuration
    :param output_format: output format for AsyncAPI document

    :returns: content of the AsyncAPI document in the output
              format requested
    """

    pretty_print = cfg['server'].get('pretty_print', False)

    if output_format == 'yaml':
        content = yaml.safe_dump(get_asyncapi(cfg), default_flow_style=False)
    else:
        content = to_json(get_asyncapi(cfg), pretty=pretty_print)
    return content


def load_asyncapi_document() -> dict:
    """
    Open AsyncAPI document from `PYGEOAPI_ASYNCAPI` environment variable

    :returns: `dict` of AsyncAPI document
    """

    pygeoapi_asyncapi = os.environ.get('PYGEOAPI_ASYNCAPI')

    if pygeoapi_asyncapi is None:
        LOGGER.debug('PYGEOAPI_ASYNCAPI environment not set')
        return {}

    if not os.path.exists(pygeoapi_asyncapi):
        msg = (f'AsyncAPI document {pygeoapi_asyncapi} does not exist.  '
               'Please generate before starting pygeoapi')
        LOGGER.warning(msg)
        return {}

    with open(pygeoapi_asyncapi, encoding='utf8') as ff:
        if pygeoapi_asyncapi.endswith(('.yaml', '.yml')):
            asyncapi_ = yaml_load(ff)
        else:  # JSON string, do not transform
            asyncapi_ = ff.read()

    return asyncapi_


@click.group()
def asyncapi():
    """AsyncAPI management"""
    pass


@click.command()
@click.pass_context
@click.argument('config_file', type=click.File(encoding='utf-8'))
@click.option('--format', '-f', 'format_', type=click.Choice(['json', 'yaml']),
              default='yaml', help='output format (json|yaml)')
@click.option('--output-file', '-of', type=click.File('w', encoding='utf-8'),
              help='Name of output file')
def generate(ctx, config_file, output_file, format_='yaml'):
    """Generate AsyncAPI Document"""

    if config_file is None:
        raise click.ClickException('--config/-c required')

    if isinstance(config_file, Path):
        with config_file.open(mode='r') as cf:
            cfg = yaml_load(cf)
    else:
        cfg = yaml_load(config_file)

    if 'pubsub' not in cfg:
        click.echo('pubsub not configured; aborting')
        ctx.exit(1)

    content = generate_asyncapi_document(cfg, format_)

    if output_file is None:
        click.echo(content)
    else:
        click.echo(f'Generating {output_file.name}')
        output_file.write(content)
        click.echo('Done')


@click.command()
@click.pass_context
@click.argument('asyncapi_file', type=click.File())
def validate(ctx, asyncapi_file):
    """Validate AsyncAPI Document"""

    if asyncapi_file is None:
        raise click.ClickException('--asyncapi/-o required')

    click.echo(f'Validating {asyncapi_file.name}')
    instance = yaml_load(asyncapi_file)
    validate_asyncapi_document(instance)
    click.echo('Valid AsyncAPI document')


asyncapi.add_command(generate)
asyncapi.add_command(validate)
