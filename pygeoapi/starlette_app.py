# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#
#
# Copyright (c) 2020 Francesco Bartoli
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

CONFIG = None

if 'PYGEOAPI_CONFIG' not in os.environ:
    raise RuntimeError('PYGEOAPI_CONFIG environment variable not set')

with open(os.environ.get('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
    CONFIG = yaml_load(fh)

STATIC_DIR = '{}{}static'.format(os.path.dirname(os.path.realpath(__file__)),
                                 os.sep)
if 'templates' in CONFIG['server']:
    STATIC_DIR = CONFIG['server']['templates'].get('static', STATIC_DIR)

app = Starlette()
app.mount('/static', StaticFiles(directory=STATIC_DIR))

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
        if os.environ.get('PYGEOAPI_OPENAPI').endswith(('.yaml', '.yml')):
            openapi = yaml_load(ff)
        else:  # JSON file, do not transform
            openapi = ff

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


@app.route('/collections/{name}/tiles')
@app.route('/collections/{name}/tiles/')
async def get_collection_tiles(request: Request, name=None):
    """
    OGC open api collections tiles access point

    :param name: identifier of collection name

    :returns: Starlette HTTP Response
    """

    if 'name' in request.path_params:
        name = request.path_params['name']
    headers, status_code, content = api_.get_collection_tiles(
        request.headers, request.query_params, name)

    response = Response(content=content, status_code=status_code)
    if headers:
        response.headers.update(headers)

    return response


@app.route('/collections/{name}/tiles/\
    {tileMatrixSetId}/{tile_matrix}/{tileRow}/{tileCol}')
@app.route('/collections/{name}/tiles/\
    {tileMatrixSetId}/{tile_matrix}/{tileRow}/{tileCol}/')
def get_collection_items_tiles(request: Request, name=None,
                               tileMatrixSetId=None, tile_matrix=None,
                               tileRow=None, tileCol=None):
    """
    OGC open api collection tiles service

    :param name: identifier of collection name
    :param tileMatrixSetId: identifier of tile matrix set
    :param tile_matrix: identifier of {z} matrix index
    :param tileRow: identifier of {y} matrix index
    :param tileCol: identifier of {x} matrix index

    :returns: HTTP response
    """

    if 'name' in request.path_params:
        name = request.path_params['name']
    if 'tileMatrixSetId' in request.path_params:
        tileMatrixSetId = request.path_params['tileMatrixSetId']
    if 'tile_matrix' in request.path_params:
        tile_matrix = request.path_params['tile_matrix']
    if 'tileRow' in request.path_params:
        tileRow = request.path_params['tileRow']
    if 'tileCol' in request.path_params:
        tileCol = request.path_params['tileCol']
    headers, status_code, content = api_.get_collection_items_tiles(
        request.headers, request.query_params, name, tileMatrixSetId,
        tile_matrix, tileRow, tileCol)

    response = Response(content=content, status_code=status_code)
    if headers:
        response.headers.update(headers)

    return response


@app.route('/collections/{collection_id}/items')
@app.route('/collections/{collection_id}/items/')
@app.route('/collections/{collection_id}/items/{item_id}')
@app.route('/collections/{collection_id}/items/{item_id}/')
async def collection_items(request: Request, collection_id=None, item_id=None):
    """
    OGC API collections items endpoint

    :param collection_id: collection identifier
    :param item_id: item identifier

    :returns: Starlette HTTP Response
    """

    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    if 'item_id' in request.path_params:
        item_id = request.path_params['item_id']
    if item_id is None:
        headers, status_code, content = api_.get_collection_items(
            request.headers, request.query_params,
            collection_id, pathinfo=request.scope['path'])
    else:
        headers, status_code, content = api_.get_collection_item(
            request.headers, request.query_params, collection_id, item_id)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response


@app.route('/collections/{collection_id}/coverage')
def collection_coverage(request: Request, collection_id):
    """
    OGC API - Coverages coverage endpoint

    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """

    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    headers, status_code, content = api_.get_collection_coverage(
        request.headers, request.query_params, collection_id)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response


@app.route('/collections/{collection_id}/coverage/domainset')
def collection_coverage_domainset(request: Request, collection_id):
    """
    OGC API - Coverages coverage domainset endpoint

    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """

    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    headers, status_code, content = api_.get_collection_coverage_domainset(
        request.headers, request.query_params, collection_id)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response


@app.route('/collections/{collection_id}/coverage/rangetype')
def collection_coverage_rangetype(request: Request, collection_id):
    """
    OGC API - Coverages coverage rangetype endpoint

    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """

    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    headers, status_code, content = api_.get_collection_coverage_rangetype(
        request.headers, request.query_params, collection_id)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response


@app.route('/processes')
@app.route('/processes/')
@app.route('/processes/{process_id}')
@app.route('/processes/{process_id}/')
async def get_processes(request: Request, process_id=None):
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
@app.route('/processes/{process_id}/jobs/{job_id}', methods=['GET', 'DELETE'])
@app.route('/processes/{process_id}/jobs/{job_id}/', methods=['GET', 'DELETE'])
async def get_process_jobs(request: Request, process_id=None, job_id=None):
    """
    OGC API - Processes jobs endpoint

    :param process_id: process identifier
    :param job_id: job identifier

    :returns: Starlette HTTP Response
    """

    if job_id is None:  # list of submit job
        if request.method == 'GET':
            headers, status_code, content = api_.get_process_jobs(
                request.headers, request.query_params, process_id)
        elif request.method == 'POST':
            headers, status_code, content = api_.execute_process(
                request.headers, request.query_params, request.data,
                process_id)
    else:  # get or delete job
        if request.method == 'DELETE':
            headers, status_code, content = api_.delete_process_job(
                process_id, job_id)
        else:  # Return status of a specific job
            headers, status_code, content = api_.get_process_job_status(
                request.headers, request.args, process_id, job_id)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response


@app.route('/processes/{process_id}/jobs/{job_id}/results', methods=['GET'])
@app.route('/processes/{process_id}/jobs/{job_id}/results/', methods=['GET'])
async def get_process_job_result(request: Request, process_id=None,
                                 job_id=None):
    """
    OGC API - Processes job result endpoint

    :param process_id: process identifier
    :param job_id: job identifier

    :returns: HTTP response
    """

    headers, status_code, content = api_.get_process_job_result(
        request.headers, request.args, process_id, job_id)

    response = Response(content=content, status_code=status_code)

    if headers:
        response.headers.update(headers)

    return response


@app.route('/processes/{process_id}/jobs/{job_id}/results/{resource}',
           methods=['GET'])
@app.route('/processes/{process_id}/jobs/{job_id}/results/{resource}/',
           methods=['GET'])
async def get_process_job_result_resource(request: Request, process_id=None,
                                          job_id=None, resource=None):
    """
    OGC API - Processes job result resource endpoint

    :param process_id: process identifier
    :param job_id: job identifier
    :param resource: job resource

    :returns: HTTP response
    """

    headers, status_code, content = api_.get_process_job_result_resource(
        request.headers, request.args, process_id, job_id, resource)

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

#    setup_logger(CONFIG['logging'])
    uvicorn.run(
        app, debug=True,
        host=api_.config['server']['bind']['host'],
        port=api_.config['server']['bind']['port'])


if __name__ == "__main__":  # run locally, for testing
    serve()
