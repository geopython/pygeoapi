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
from jsonschema import validate as jsonschema_validate
import logging
from pathlib import Path

import pygeoapi.util

LOGGER = logging.getLogger(__name__)

THISDIR = Path(__file__).parent.resolve()


def load_schema() -> dict:
    """ Reads the JSON schema YAML file. """
    schema_file = THISDIR / 'schemas' / 'config' / 'pygeoapi-config-0.x.yml'

    with schema_file.open() as fh2:
        return pygeoapi.util.yaml_load(fh2)


def validate_config(instance_dict: dict) -> bool:
    """
    Validate pygeoapi configuration against pygeoapi schema

    :param instance_dict: dict of configuration

    :returns: `bool` of validation
    """
    jsonschema_validate(
        json.loads(pygeoapi.util.to_json(instance_dict)),
        load_schema()
    )

    return True


@click.group()
def config():
    """Configuration management"""
    pass


@click.command()
@click.pass_context
def validate(ctx):
    """Validate configuration"""

    click.echo(f'Validating {ctx.obj["pygeoapi_config_path"]}...')
    validate_config(ctx.obj['pygeoapi_config'])
    click.echo('Valid configuration')


config.add_command(validate)
