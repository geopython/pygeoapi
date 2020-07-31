# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#
#
# Copyright (c) 2019 Francesco Bartoli
# Copyright (c) 2020 Tom Kralidis
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
""" Starlette module providing the route paths to the api"""

import os

import click

from starlette.staticfiles import StaticFiles
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
import uvicorn

from pygeoapi.api import API
from pygeoapi.util import yaml_load, filter_dict_by_key_value

import re
from json import JSONDecodeError

app = Starlette()
app.mount('/static', StaticFiles(
    directory='{}{}static'.format(os.path.dirname(os.path.realpath(__file__)),
                                  os.sep)))
CONFIG = None

if 'PYGEOAPI_CONFIG' not in os.environ:
    raise RuntimeError('PYGEOAPI_CONFIG environment variable not set')

with open(os.environ.get('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
    CONFIG = yaml_load(fh)

# CORS: optionally enable from config.
if CONFIG['server'].get('cors', False):
    from starlette.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=['*'])

OGC_SCHEMAS_LOCATION = CONFIG['server'].get('ogc_schemas_location', None)

if (OGC_SCHEMAS_LOCATION is not None and
        not OGC_SCHEMAS_LOCATION.startswith('http')):
    if not os.path.exists(OGC_SCHEMAS_LOCATION):
        raise RuntimeError('OGC schemas misconfigured')
    app.mount('/schemas', StaticFiles(directory=OGC_SCHEMAS_LOCATION))

api_ = API(CONFIG)


@app.route('/')
async def landing_page(request: Request):
    """
    OGC API landing page endpoint

    :returns: Starlette HTTP Response
    """

    headers, status_code, content = api_.landing_page(
        request.headers, request.query_params)

    response = Response(content=content, status_code=status_code)
    if headers:
        response.headers.update(headers)

    return response


@app.route('/openapi')
@app.route('/openapi/')
async def openapi(request: Request):
    """
    OpenAPI endpoint

    :returns: Starlette HTTP Response
    """

    with open(os.environ.get('PYGEOAPI_OPENAPI'), encoding='utf8') as ff:
        openapi = yaml_load(ff)

    headers, status_code, content = api_.openapi(
        request.headers, request.query_params, openapi)

    response = Response(content=content, status_code=status_code)
    if headers:
        response.headers.update(headers)

    return response


@app.route('/conformance')
@app.route('/conformance/')
async def conformance(request: Request):
    """
    OGC API conformance endpoint

    :returns: Starlette HTTP Response
    """

    headers, status_code, content = api_.conformance(
        request.headers, request.query_params)

    response = Response(content=content, status_code=status_code)
    if headers:
        response.headers.update(headers)

    return response


@app.route('/collections')
@app.route('/collections/')
@app.route('/collections/{collection_id}')
@app.route('/collections/{collection_id}/')
async def collections(request: Request, collection_id=None):
    """
    OGC API collections endpoint

    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """

    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    headers, status_code, content = api_.describe_collections(
        request.headers, request.query_params, collection_id)

    response = Response(content=content, status_code=status_code)
    if headers:
        response.headers.update(headers)

    return response


@app.route('/collections/{collection_id}/queryables')
@app.route('/collections/{collection_id}/queryables/')
async def collection_queryables(request: Request, collection_id=None):
    """
    OGC API collections queryables endpoint

    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """

    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    headers, status_code, content = api_.get_collection_queryables(
        request.headers, request.query_params, collection_id)

    response = Response(content=content, status_code=status_code)
    if headers:
        response.headers.update(headers)

    return response


def supports_transactions(collection):
    """
    Check if given collection supports transactions

    :param collection: collection dict

    :returns: boolean value
    """
    if 'extensions' not in CONFIG['resources'][collection]:
        return False
    if 'transactions' not in CONFIG['resources'][collection]['extensions']:
        return False
    return CONFIG['resources'][collection]['extensions']['transactions']


async def collection_items(request: Request, item_id=None):
    """
    OGC API collections items endpoint

    :param collection_id: collection identifier
    :param item_id: item identifier
    """
    path = request.scope['path']
    coll_id_pattern = re.compile("/collections/(.*)/items")
    collection_id = coll_id_pattern.findall(path)[0]
    if 'item_id' in request.path_params:
        item_id = request.path_params['item_id']

    verb = request.method

    if verb == 'GET':
        if item_id is None:
            headers, status_code, content = api_.get_collection_items(
                request.headers, request.query_params,
                collection_id, pathinfo=request.scope['path'])
        else:
            headers, status_code, content = api_.get_collection_item(
                request.headers, request.query_params, collection_id, item_id)

    else:
        try:
            req_body = await request.json()
        except JSONDecodeError:
            pass

    if verb == 'POST':
        headers, status_code, content = api_.create_collection_item(
                req_body, collection_id)

    if verb == 'PUT':
        headers, status_code, content = api_.replace_collection_item(
                req_body, collection_id, item_id)

    if verb == 'PATCH':
        headers, status_code, content = api_.update_collection_item(
                req_body, collection_id, item_id)

    if verb == 'DELETE':
        headers, status_code, content = api_.remove_collection_item(
                collection_id, item_id)

    response = Response(content=str(content), status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response

#  dynamic routing based on transactions flag
coll = filter_dict_by_key_value(CONFIG['resources'],
                                'type', 'collection')
coll_support_trans = list(filter(supports_transactions, coll))
for collection_id in coll:
    app.add_route('/collections/'+collection_id+'/items', collection_items,
                  methods=['GET'])
    app.add_route('/collections/'+collection_id+'/items/', collection_items,
                  methods=['GET'])
    app.add_route('/collections/'+collection_id+'/items/{item_id}',
                  collection_items, methods=['GET'])
    app.add_route('/collections/'+collection_id+'/items/{item_id}/',
                  collection_items, methods=['GET'])
for collection_id in coll_support_trans:
    app.add_route('/collections/'+collection_id+'/items',
                  collection_items, methods=['POST'])
    app.add_route('/collections/'+collection_id+'/items/',
                  collection_items, methods=['POST'])
    app.add_route('/collections/'+collection_id+'/items/{item_id}',
                  collection_items, methods=['PATCH', 'PUT', 'DELETE'])
    app.add_route('/collections/'+collection_id+'/items/{item_id}/',
                  collection_items, methods=['PATCH', 'PUT', 'DELETE'])


@app.route('/processes/{process_id}/')
@app.route('/processes/{process_id}')
@app.route('/processes/')
@app.route('/processes')
async def processes(request: Request, process_id=None):
    """
    OGC API - Processes description endpoint

    :param process_id: identifier of process to describe

    :returns: Starlette HTTP Response
    """

    headers, status_code, content = api_.describe_processes(
        request.headers, request.query_params, process_id)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)
    return response


@app.route('/processes/{process_id}/jobs', methods=['GET', 'POST'])
@app.route('/processes/{process_id}/jobs/', methods=['GET', 'POST'])
async def process_jobs(request: Request, process_id=None):
    """
    OGC API - Processes jobs endpoint

    :param process_id: identifier of process to execute

    :returns: Starlette HTTP Response
    """

    if request.method == 'GET':
        headers, status_code, content = ({}, 200, "[]")
    elif request.method == 'POST':
        headers, status_code, content = api_.execute_process(
            request.headers, request.query_params, request.data, process_id)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response


@app.route('/stac')
async def stac_catalog_root(request: Request):
    """
    STAC root endpoint

    :returns: Starlette HTTP response
    """

    headers, status_code, content = api_.get_stac_root(
        request.headers, request.query_params)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response


@app.route('/stac/{path:path}')
async def stac_catalog_path(request: Request):
    """
    STAC endpoint

    :param path: path

    :returns: Starlette HTTP response
    """

    path = request.path_params["path"]

    headers, status_code, content = api_.get_stac_path(
        request.headers, request.query_params, path)

    response = Response(content=content, status_code=status_code)
    if headers:
        response.headers.update(headers)
    return response


@click.command()
@click.pass_context
@click.option('--debug', '-d', default=False, is_flag=True, help='debug')
def serve(ctx, server=None, debug=False):
    """
    Serve pygeoapi via Starlette. Runs pygeoapi
    as a uvicorn server. Not recommend for production.

    :param server: `string` of server type
    :param debug: `bool` of whether to run in debug mode

    :returns: void
    """

    # setup_logger(CONFIG['logging'])
    uvicorn.run(
        app, debug=True,
        host=api_.config['server']['bind']['host'],
        port=api_.config['server']['bind']['port'])


if __name__ == "__main__":  # run locally, for testing
    serve()
