# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2022 Tom Kralidis
# Copyright (c) 2023 Francesco Bartoli
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

import click
import json
import logging
import os
import typing
from pathlib import Path

import yaml
from jsonschema import validate as jsonschema_validate

from pygeoapi.util import to_json, yaml_load, TEMPLATES, THISDIR

LOGGER = logging.getLogger(__name__)


def get_config(raw: bool = False) -> typing.Dict[str, typing.Dict]:
    """
    Get pygeoapi configurations

    :param raw: `bool` over interpolation during config loading

    :returns: `dict` of pygeoapi configuration
    """
    provided_config = {}
    try:
        with Path(os.getenv('PYGEOAPI_CONFIG')).open(encoding='utf-8') as fh:
            if raw:
                provided_config = yaml.safe_load(fh)
            else:
                provided_config = yaml_load(fh)
    except TypeError:
        LOGGER.warning(
            'PYGEOAPI_CONFIG environment variable not set, using default '
            'configuration'
        )
    except FileNotFoundError:
        LOGGER.warning(
            'PYGEOAPI_CONFIG environment variable points to non-existent '
            'file, using default configuration'
        )
    print(f'{provided_config=}')
    default_config = _get_default_config()
    merged_config = {
        'server': {
            **default_config['server'],
            **provided_config.get('server', {}),
        },
        'logging': {
            **default_config['logging'],
            **provided_config.get('logging', {}),
        },
        'metadata': {
            **default_config['metadata'],
            **provided_config.get('metadata', {}),
        },
        'resources': {
            **default_config['resources'],
            **provided_config.get('resources', {}),
        },
    }
    return merged_config


def load_schema() -> dict:
    """ Reads the JSON schema YAML file. """

    schema_file = THISDIR / 'schemas' / 'config' / 'pygeoapi-config-0.x.yml'

    with schema_file.open() as fh2:
        return yaml_load(fh2)


def validate_config(instance_dict: dict) -> bool:
    """
    Validate pygeoapi configuration against pygeoapi schema

    :param instance_dict: dict of configuration

    :returns: `bool` of validation
    """

    jsonschema_validate(json.loads(to_json(instance_dict)), load_schema())

    return True


@click.group()
def config():
    """Configuration management"""
    pass


@click.command()
@click.pass_context
@click.option('--config', '-c', 'config_file', help='configuration file')
def validate(ctx, config_file):
    """Validate configuration"""

    if config_file is None:
        raise click.ClickException('--config/-c required')

    with open(config_file) as ff:
        click.echo(f'Validating {config_file}')
        instance = yaml_load(ff)
        validate_config(instance)
        click.echo('Valid configuration')


config.add_command(validate)


def _get_default_config() -> typing.Dict[str, typing.Dict]:
    """Returns a default configuration for pygeoapi."""
    return {
        'server': {
            'admin': False,
            'bind': {
                'host': '0.0.0.0',
                'port': 5000,
            },
            'url': 'http://localhost:5000',
            'mimetype': 'application/json; charset=UTF-8',
            'encoding': 'utf-8',
            'gzip': False,
            'languages': [
                "en-US",
                "fr-CA",
            ],
            'cors': True,
            'pretty_print': False,
            'limit': 10,
            'templates': {
                'path': str(TEMPLATES),
                'static': str(Path(__file__).parent / 'static'),
            },
            'map': {
                'url': 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                'attribution': (
                    '&copy; <a href="https://openstreetmap.org/copyright">'
                    'OpenStreetMap contributors</a>'
                ),
            },
            'manager': {
                'name': 'TinyDB',
                'connection': '/tmp/pygeoapi-process-manager.db',
                'output_dir': '/tmp',
            },
            # 'ogc_schemas_location': '/opt/schemas/opengis.net',
        },
        'logging': {
            'level': 'ERROR',
            # 'logfile': '/tmp/pygeoapi.log',
        },
        'metadata': {
            'identification': {
                'title': 'pygeoapi default instance',
                'description': 'pygeoapi provides an API to geospatial data',
                'keywords': [
                    'geospatial',
                    'data',
                    'api',
                ],
                'keywords_type': 'theme',
                'terms_of_service': (
                    'https://creativecommons.org/licenses/by/4.0/'),
                'url': 'https://example.org',
            },
            'license': {
                'name': 'CC-BY 4.0 license',
                'url': 'https://creativecommons.org/licenses/by/4.0/',
            },
            'provider': {
                'name': 'Organization name',
                'url': 'https://pygeoapi.io',
            },
            'contact': {
                'name': 'Lastname, Firstname',
                'position': 'Position Title',
                'address': 'Mailing Address',
                'city': 'City',
                'stateorprovince': 'Administrative Area',
                'postalcode': 'Zip or Postal Code',
                'country': 'Country',
                'phone': '+xx - xxx - xxx - xxxx',
                'fax': '+xx - xxx - xxx - xxxx',
                'email': 'you@example.org',
                'url': 'Contact URL',
                'hours': 'Mo - Fr 08: 00 - 17:00',
                'instructions': 'During hours of service. Off on weekends.',
                'role': 'pointOfContact',
            },
        },
        'resources': {},
    }
