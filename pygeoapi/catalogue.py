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

import copy
import logging

import click
from elasticsearch import Elasticsearch

from pygeoapi.util import yaml_load

LOGGER = logging.getLogger(__name__)


def create_catalogue(config):
    index_name = 'pygeoapi-catalogue'
    type_name = 'FeatureCollection'
    settings = {
        'mappings': {
            'FeatureCollection': {
                'properties': {
                    'geometry': {
                        'type': 'geo_shape'
                    }
                }
            }
        }
    }

    es = Elasticsearch()

    if es.indices.exists(index_name):
        es.indices.delete(index_name)

    # create index
    es.indices.create(index=index_name, body=settings, request_timeout=90)

    es = Elasticsearch()

    for k, v in config['datasets'].items():
        ds = copy.deepcopy(v)
        ds.pop('provider', None)

        ds['id'] = k

        minx, miny, maxx, maxy = ds['extents']['spatial']['bbox']

        ds['geometry'] = {
            'type': 'Polygon',
            'coordinates': [[
                [minx, miny],
                [minx, maxy],
                [maxx, maxy],
                [maxx, miny],
                [minx, miny]
            ]],
        },

        try:
            es.index(index=index_name, doc_type=type_name,
                     id=ds['id'], body=ds)
        except Exception as err:
            print(ds)
            print(err)


@click.command('generate-catalogue')
@click.pass_context
@click.option('--config', '-c', 'config_file', help='configuration file')
def generate_catalogue(ctx, config_file):
    """Generate catalogue from configuration"""

    if config_file is None:
        raise click.ClickException('--config/-c required')
    with open(config_file) as ff:
        s = yaml_load(ff)
        create_catalogue(s)
#        click.echo(yaml.safe_dump(get_oas(s), default_flow_style=False))
