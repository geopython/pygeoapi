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

import click
import json
from jsonschema import validate as jsonschema_validate
import logging
from pathlib import Path

from pygeoapi.util import to_json, yaml_load

LOGGER = logging.getLogger(__name__)

THISDIR = Path(__file__).parent.resolve()


def validate_config(instance_dict: dict) -> bool:
    """
    Validate pygeoapi configuration against pygeoapi schema

    :param instance_dict: dict of configuration

    :returns: `bool` of validation
    """

    schema_file = THISDIR / 'schemas' / 'config' / 'pygeoapi-config-0.x.yml'

    with schema_file.open() as fh2:
        schema_dict = yaml_load(fh2)
        jsonschema_validate(json.loads(to_json(instance_dict)), schema_dict)

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
