# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2025 Tom Kralidis
# Copyright (c) 2025 Francesco Bartoli
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
from jsonschema import validate as jsonschema_validate
import logging
import os
from pathlib import Path
import yaml

from pygeoapi.util import SCHEMASDIR, to_json, yaml_load

LOGGER = logging.getLogger(__name__)


def get_config(file_path: str | None = None, raw: bool = False) -> dict:
    """
    Read pygeoapi configuration document

    :param file_path: `str` of path to configuration file; if `None`,
                      reads from `PYGEOAPI_CONFIG` environment variable
    :param raw: `bool` over interpolation during config loading

    :returns: `dict` of pygeoapi configuration
    """

    if file_path is None:
        file_path = os.environ.get('PYGEOAPI_CONFIG')

    if not file_path:
        msg = 'PYGEOAPI_CONFIG file not specified'
        LOGGER.error(msg)
        raise RuntimeError(msg)

    if not os.path.exists(file_path):
        msg = (f'pygeoapi configuration {file_path} does not exist. '
               'Please create before starting pygeoapi')
        LOGGER.error(msg)
        raise RuntimeError(msg)

    with open(file_path, encoding='utf8') as fh:
        if raw:
            config_ = yaml.safe_load(fh)
        else:
            config_ = yaml_load(fh)

    return config_


def get_config_schema() -> dict:
    """Reads the JSON schema YAML file."""

    schema_file = SCHEMASDIR / 'config' / 'pygeoapi-config-0.x.yml'

    with schema_file.open() as fh:
        return yaml_load(fh)


def validate_config_document(instance_dict: dict) -> bool:
    """
    Validate pygeoapi configuration against pygeoapi schema

    :param instance_dict: dict of configuration

    :returns: `bool` of validation
    """

    # Load as simple JSON
    config = json.loads(to_json(instance_dict))
    jsonschema_validate(config, get_config_schema())

    return True


cli_config = click.option(
    '--config',
    '--config-file',
    '-c',
    'config_file',
    # required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    envvar='PYGEOAPI_CONFIG',
    help='Name of configuration document (env: PYGEOAPI_CONFIG)'
)


@click.group()
def config():
    """Configuration management"""
    pass


@click.command()
@click.pass_context
@cli_config
def validate(ctx, config_file):
    """Validate configuration"""

    click.echo(f'Validating {config_file.name}')
    instance = get_config(config_file)
    if validate_config_document(instance):
        click.echo('Valid configuration')


config.add_command(validate)
