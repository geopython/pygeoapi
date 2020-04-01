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
from pygeoapi.util import yaml_load

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
async def root(request: Request):
    """
    HTTP root content of pygeoapi. Intro page access point
    :returns: Starlette HTTP Response
    """
    headers, status_code, content = api_.root(
        request.headers, request.query_params)

    response = Response(content=content, status_code=status_code)
    if headers:
        response.headers.update(headers)

    return response


@app.route('/openapi')
@app.route('/openapi/')
async def openapi(request: Request):
    """
    OpenAPI access point

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
    OGC open api conformance access point

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
@app.route('/collections/{name}')
@app.route('/collections/{name}/')
async def describe_collections(request: Request, name=None):
    """
    OGC open api collections  access point

    :param name: identifier of collection name
    :returns: Starlette HTTP Response
    """

    if 'name' in request.path_params:
        name = request.path_params['name']
    headers, status_code, content = api_.describe_collections(
        request.headers, request.query_params, name)

    response = Response(content=content, status_code=status_code)
    if headers:
        response.headers.update(headers)

    return response


@app.route('/collections/{feature_collection}/items')
@app.route('/collections/{feature_collection}/items/')
@app.route('/collections/{feature_collection}/items/{feature}')
@app.route('/collections/{feature_collection}/items/{feature}/')
async def dataset(request: Request, feature_collection=None, feature=None):
    """
    OGC open api collections/{dataset}/items/{feature}  access point

    :returns: Starlette HTTP Response
    """

    if 'feature_collection' in request.path_params:
        feature_collection = request.path_params['feature_collection']
    if 'feature' in request.path_params:
        feature = request.path_params['feature']
    if feature is None:
        headers, status_code, content = api_.get_collection_items(
            request.headers, request.query_params,
            feature_collection, pathinfo=request.scope['path'])
    else:
        headers, status_code, content = api_.get_collection_item(
            request.headers, request.query_params, feature_collection, feature)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response


@app.route('/stac')
async def stac_catalog_root(request: Request):
    """
    STAC access point
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
    STAC access point
    :returns: Starlette HTTP response
    """

    path = request.path_params["path"]

    headers, status_code, content = api_.get_stac_path(
        request.headers, request.query_params, path)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response


@app.route('/processes')
@app.route('/processes/')
@app.route('/processes/{name}')
@app.route('/processes/{name}/')
async def describe_processes(request: Request, name=None):
    """
    OGC open api processes access point (experimental)

    :param name: identifier of process to describe
    :returns: Starlette HTTP Response
    """
    headers, status_code, content = api_.describe_processes(
        request.headers, request.query_params, name)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response


@app.route('/processes/{name}/jobs', methods=['GET', 'POST'])
@app.route('/processes/{name}/jobs/', methods=['GET', 'POST'])
async def execute_process(request: Request, name=None):
    """
    OGC open api jobs from processes access point (experimental)

    :param name: identifier of process to execute
    :returns: Starlette HTTP Response
    """

    if request.method == 'GET':
        headers, status_code, content = ({}, 200, "[]")
    elif request.method == 'POST':
        headers, status_code, content = api_.execute_process(
            request.headers, request.query_params, request.data, name)

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
    :returns void
    """

#    setup_logger(CONFIG['logging'])
    uvicorn.run(
        app, debug=True,
        host=api_.config['server']['bind']['host'],
        port=api_.config['server']['bind']['port'])


if __name__ == "__main__":  # run locally, for testing
    serve()
