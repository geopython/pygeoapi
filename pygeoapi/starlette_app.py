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


def get_response(result: tuple) -> Response:
    """ Creates a Starlette Response object and updates matching headers.

    :param result:  The result of the API call.
                    This should be a tuple of (headers, status, content).
    :returns:       A Response instance.
    """
    headers, status, content = result
    response = Response(content=content, status_code=status)
    if headers is not None:
        response.headers.update(headers)
    return response


@app.route('/')
async def landing_page(request: Request):
    """
    OGC API landing page endpoint

    :param request: Starlette Request instance

    :returns: Starlette HTTP Response
    """
    return get_response(api_.landing_page(request))


@app.route('/openapi')
@app.route('/openapi/')
async def openapi(request: Request):
    """
    OpenAPI endpoint

    :param request: Starlette Request instance

    :returns: Starlette HTTP Response
    """
    with open(os.environ.get('PYGEOAPI_OPENAPI'), encoding='utf8') as ff:
        if os.environ.get('PYGEOAPI_OPENAPI').endswith(('.yaml', '.yml')):
            openapi_ = yaml_load(ff)
        else:  # JSON file, do not transform
            openapi_ = ff

    return get_response(api_.openapi(request, openapi_))


@app.route('/conformance')
@app.route('/conformance/')
async def conformance(request: Request):
    """
    OGC API conformance endpoint

    :param request: Starlette Request instance

    :returns: Starlette HTTP Response
    """
    return get_response(api_.conformance(request))


@app.route('/collections')
@app.route('/collections/')
@app.route('/collections/{collection_id}')
@app.route('/collections/{collection_id}/')
async def collections(request: Request, collection_id=None):
    """
    OGC API collections endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    return get_response(api_.describe_collections(request, collection_id))


@app.route('/collections/{collection_id}/queryables')
@app.route('/collections/{collection_id}/queryables/')
async def collection_queryables(request: Request, collection_id=None):
    """
    OGC API collections queryables endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    return get_response(api_.get_collection_queryables(request, collection_id))


@app.route('/collections/{name}/tiles')
@app.route('/collections/{name}/tiles/')
async def get_collection_tiles(request: Request, name=None):
    """
    OGC open api collections tiles access point

    :param request: Starlette Request instance
    :param name: identifier of collection name

    :returns: Starlette HTTP Response
    """
    if 'name' in request.path_params:
        name = request.path_params['name']
    return get_response(api_.get_collection_tiles(request, name))


@app.route('/collections/{name}/tiles/\
    {tileMatrixSetId}/{tile_matrix}/{tileRow}/{tileCol}')
@app.route('/collections/{name}/tiles/\
    {tileMatrixSetId}/{tile_matrix}/{tileRow}/{tileCol}/')
async def get_collection_items_tiles(request: Request, name=None,
                                     tileMatrixSetId=None, tile_matrix=None,
                                     tileRow=None, tileCol=None):
    """
    OGC open api collection tiles service

    :param request: Starlette Request instance
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
    return get_response(api_.get_collection_tiles_data(
        request, name, tileMatrixSetId, tile_matrix, tileRow, tileCol))


@app.route('/collections/{collection_id}/items')
@app.route('/collections/{collection_id}/items/')
@app.route('/collections/{collection_id}/items/{item_id}')
@app.route('/collections/{collection_id}/items/{item_id}/')
async def collection_items(request: Request, collection_id=None, item_id=None):
    """
    OGC API collections items endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier
    :param item_id: item identifier

    :returns: Starlette HTTP Response
    """
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    if 'item_id' in request.path_params:
        item_id = request.path_params['item_id']
    if item_id is None:
        return get_response(api_.get_collection_items(
            request, collection_id, pathinfo=request.scope['path']))
    else:
        return get_response(api_.get_collection_item(
            request, collection_id, item_id))


@app.route('/collections/{collection_id}/coverage')
async def collection_coverage(request: Request, collection_id):
    """
    OGC API - Coverages coverage endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    return get_response(api_.get_collection_coverage(request, collection_id))


@app.route('/collections/{collection_id}/coverage/domainset')
async def collection_coverage_domainset(request: Request, collection_id):
    """
    OGC API - Coverages coverage domainset endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    return get_response(api_.get_collection_coverage_domainset(
        request, collection_id))


@app.route('/collections/{collection_id}/coverage/rangetype')
async def collection_coverage_rangetype(request: Request, collection_id):
    """
    OGC API - Coverages coverage rangetype endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    return get_response(api_.get_collection_coverage_rangetype(
        request, collection_id))


@app.route('/processes')
@app.route('/processes/')
@app.route('/processes/{process_id}')
@app.route('/processes/{process_id}/')
async def get_processes(request: Request, process_id=None):
    """
    OGC API - Processes description endpoint

    :param request: Starlette Request instance
    :param process_id: identifier of process to describe

    :returns: Starlette HTTP Response
    """
    if 'process_id' in request.path_params:
        process_id = request.path_params['process_id']

    return get_response(api_.describe_processes(request, process_id))


@app.route('/processes/{process_id}/jobs', methods=['GET', 'POST'])
@app.route('/processes/{process_id}/jobs/', methods=['GET', 'POST'])
@app.route('/processes/{process_id}/jobs/{job_id}', methods=['GET', 'DELETE'])
@app.route('/processes/{process_id}/jobs/{job_id}/', methods=['GET', 'DELETE'])
async def get_process_jobs(request: Request, process_id=None, job_id=None):
    """
    OGC API - Processes jobs endpoint

    :param request: Starlette Request instance
    :param process_id: process identifier
    :param job_id: job identifier

    :returns: Starlette HTTP Response
    """

    if 'process_id' in request.path_params:
        process_id = request.path_params['process_id']
    if 'job_id' in request.path_params:
        job_id = request.path_params['job_id']

    if job_id is None:  # list of submit job
        if request.method == 'GET':
            return get_response(api_.get_process_jobs(request, process_id))
        elif request.method == 'POST':
            return get_response(api_.execute_process(request, process_id))
    else:  # get or delete job
        if request.method == 'DELETE':
            return get_response(api_.delete_process_job(process_id, job_id))
        else:  # Return status of a specific job
            return get_response(api_.get_process_jobs(
                request, process_id, job_id))


@app.route('/processes/{process_id}/jobs/{job_id}/results', methods=['GET'])
@app.route('/processes/{process_id}/jobs/{job_id}/results/', methods=['GET'])
async def get_process_job_result(request: Request, process_id=None,
                                 job_id=None):
    """
    OGC API - Processes job result endpoint

    :param request: Starlette Request instance
    :param process_id: process identifier
    :param job_id: job identifier

    :returns: HTTP response
    """

    if 'process_id' in request.path_params:
        process_id = request.path_params['process_id']
    if 'job_id' in request.path_params:
        job_id = request.path_params['job_id']

    return get_response(api_.get_process_job_result(
        request, process_id, job_id))


@app.route('/processes/{process_id}/jobs/{job_id}/results/{resource}',
           methods=['GET'])
@app.route('/processes/{process_id}/jobs/{job_id}/results/{resource}/',
           methods=['GET'])
async def get_process_job_result_resource(request: Request, process_id=None,
                                          job_id=None, resource=None):
    """
    OGC API - Processes job result resource endpoint

    :param request: Starlette Request instance
    :param process_id: process identifier
    :param job_id: job identifier
    :param resource: job resource

    :returns: HTTP response
    """

    if 'process_id' in request.path_params:
        process_id = request.path_params['process_id']
    if 'job_id' in request.path_params:
        job_id = request.path_params['job_id']
    if 'resource' in request.path_params:
        resource = request.path_params['resource']

    return get_response(api_.get_process_job_result_resource(
        request, process_id, job_id, resource))


@app.route('/collections/{collection_id}/position')
@app.route('/collections/{collection_id}/area')
@app.route('/collections/{collection_id}/cube')
@app.route('/collections/{collection_id}/trajectory')
@app.route('/collections/{collection_id}/corridor')
@app.route('/collections/{collection_id}/instances/{instance_id}/position')
@app.route('/collections/{collection_id}/instances/{instance_id}/area')
@app.route('/collections/{collection_id}/instances/{instance_id}/cube')
@app.route('/collections/{collection_id}/instances/{instance_id}/trajectory')
@app.route('/collections/{collection_id}/instances/{instance_id}/corridor')
async def get_collection_edr_query(request: Request, collection_id=None, instance_id=None):  # noqa
    """
    OGC EDR API endpoints

    :param collection_id: collection identifier
    :param instance_id: instance identifier

    :returns: HTTP response
    """

    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    if 'instance_id' in request.path_params:
        instance_id = request.path_params['instance_id']

    query_type = request.path.split('/')[-1]  # noqa
    return get_response(api_.get_collection_edr_query(request, collection_id,
                                                      instance_id, query_type))


@app.route('/stac')
async def stac_catalog_root(request: Request):
    """
    STAC root endpoint

    :param request: Starlette Request instance

    :returns: Starlette HTTP response
    """
    return get_response(api_.get_stac_root(request))


@app.route('/stac/{path:path}')
async def stac_catalog_path(request: Request):
    """
    STAC endpoint

    :param request: Starlette Request instance

    :returns: Starlette HTTP response
    """
    path = request.path_params["path"]
    return get_response(api_.get_stac_path(request, path))


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
