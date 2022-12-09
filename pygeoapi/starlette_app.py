# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#          Abdulazeez Abdulazeez Adeshina <youngestdev@gmail.com>
#
# Copyright (c) 2020 Francesco Bartoli
# Copyright (c) 2022 Tom Kralidis
# Copyright (c) 2022 Abdulazeez Abdulazeez Adeshina
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
from typing import Union
from pathlib import Path

import click

from starlette.staticfiles import StaticFiles
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response, JSONResponse, HTMLResponse
import uvicorn

from pygeoapi.api import API
from pygeoapi.util import yaml_load

CONFIG = None

if 'PYGEOAPI_CONFIG' not in os.environ:
    raise RuntimeError('PYGEOAPI_CONFIG environment variable not set')

with open(os.environ.get('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
    CONFIG = yaml_load(fh)

p = Path(__file__)

app = Starlette(debug=True)
STATIC_DIR = Path(p).parent.resolve() / 'static'

try:
    STATIC_DIR = Path(CONFIG['server']['templates']['static'])
except KeyError:
    pass

app = Starlette()
app.mount('/static', StaticFiles(directory=STATIC_DIR))

# CORS: optionally enable from config.
if CONFIG['server'].get('cors', False):
    from starlette.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=['*'])

try:
    OGC_SCHEMAS_LOCATION = Path(CONFIG['server']['ogc_schemas_location'])
except KeyError:
    OGC_SCHEMAS_LOCATION = None

if (OGC_SCHEMAS_LOCATION is not None and
        not OGC_SCHEMAS_LOCATION.name.startswith('http')):
    if not OGC_SCHEMAS_LOCATION.exists():
        raise RuntimeError('OGC schemas misconfigured')
    app.mount('/schemas', StaticFiles(directory=OGC_SCHEMAS_LOCATION))

api_ = API(CONFIG)


def get_response(result: tuple) -> Union[Response, JSONResponse, HTMLResponse]:
    """
    Creates a Starlette Response object and updates matching headers.

    :param result: The result of the API call.
                   This should be a tuple of (headers, status, content).

    :returns: A Response instance.
    """

    headers, status, content = result
    if headers['Content-Type'] == 'text/html':
        response = HTMLResponse(content=content, status_code=status)
    else:
        if isinstance(content, dict):
            response = JSONResponse(content, status_code=status)
        else:
            response = Response(content, status_code=status)

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


@app.route('/collections/{collection_id:path}/queryables')
@app.route('/collections/{collection_id:path}/queryables/')
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


@app.route('/collections/{collection_id:path}/tiles')
@app.route('/collections/{collection_id:path}/tiles/')
async def get_collection_tiles(request: Request, collection_id=None):
    """
    OGC open api collections tiles access point

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    return get_response(api_.get_collection_tiles(
        request, collection_id))


@app.route('/collections/{collection_id:path}/tiles/{tileMatrixSetId}')
@app.route('/collections/{collection_id:path}/tiles/{tileMatrixSetId}/')
@app.route('/collections/{collection_id:path}/tiles/{tileMatrixSetId}/metadata')  # noqa
@app.route('/collections/{collection_id:path}/tiles/{tileMatrixSetId}/metadata/')  # noqa
async def get_collection_tiles_metadata(request: Request, collection_id=None,
                                        tileMatrixSetId=None):
    """
    OGC open api collection tiles service metadata

    :param collection_id: collection identifier
    :param tileMatrixSetId: identifier of tile matrix set

    :returns: HTTP response
    """
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    if 'tileMatrixSetId' in request.path_params:
        tileMatrixSetId = request.path_params['tileMatrixSetId']
    return get_response(api_.get_collection_tiles_metadata(
        request, collection_id, tileMatrixSetId))


@app.route('/collections/{collection_id:path}/tiles/{tileMatrixSetId}/{tile_matrix}/{tileRow}/{tileCol}')  # noqa
@app.route('/collections/{collection_id:path}/tiles/{tileMatrixSetId}/{tile_matrix}/{tileRow}/{tileCol}/')  # noqa
async def get_collection_items_tiles(request: Request, collection_id=None,
                                     tileMatrixSetId=None, tile_matrix=None,
                                     tileRow=None, tileCol=None):
    """
    OGC open api collection tiles service

    :param request: Starlette Request instance
    :param collection_id: collection identifier
    :param tileMatrixSetId: identifier of tile matrix set
    :param tile_matrix: identifier of {z} matrix index
    :param tileRow: identifier of {y} matrix index
    :param tileCol: identifier of {x} matrix index

    :returns: HTTP response
    """
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    if 'tileMatrixSetId' in request.path_params:
        tileMatrixSetId = request.path_params['tileMatrixSetId']
    if 'tile_matrix' in request.path_params:
        tile_matrix = request.path_params['tile_matrix']
    if 'tileRow' in request.path_params:
        tileRow = request.path_params['tileRow']
    if 'tileCol' in request.path_params:
        tileCol = request.path_params['tileCol']
    return get_response(api_.get_collection_tiles_data(
        request, collection_id, tileMatrixSetId,
        tile_matrix, tileRow, tileCol))


@app.route('/collections/{collection_id:path}/items', methods=['GET', 'POST'])
@app.route('/collections/{collection_id:path}/items/', methods=['GET', 'POST'])
@app.route('/collections/{collection_id:path}/items/{item_id}',
           methods=['GET', 'PUT', 'DELETE'])
@app.route('/collections/{collection_id:path}/items/{item_id}/',
           methods=['GET', 'PUT', 'DELETE'])
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
        if request.method == 'GET':  # list items
            return get_response(
                api_.get_collection_items(
                    request, collection_id))
        elif request.method == 'POST':  # filter or manage items
            content_type = request.headers.get('content-type')
            if content_type is not None:
                if content_type == 'application/geo+json':
                    return get_response(
                        api_.manage_collection_item(request, 'create',
                                                    collection_id))
                else:
                    return get_response(
                        api_.post_collection_items(request, collection_id))

    elif request.method == 'DELETE':
        return get_response(
            api_.manage_collection_item(request, 'delete',
                                        collection_id, item_id))
    elif request.method == 'PUT':
        return get_response(
            api_.manage_collection_item(request, 'update',
                                        collection_id, item_id))
    else:
        return get_response(api_.get_collection_item(
            request, collection_id, item_id))


@app.route('/collections/{collection_id:path}/coverage')
async def collection_coverage(request: Request, collection_id=None):
    """
    OGC API - Coverages coverage endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    return get_response(api_.get_collection_coverage(request, collection_id))


@app.route('/collections/{collection_id:path}/coverage/domainset')
async def collection_coverage_domainset(request: Request, collection_id=None):
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


@app.route('/collections/{collection_id:path}/coverage/rangetype')
async def collection_coverage_rangetype(request: Request, collection_id=None):
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


@app.route('/collections/{collection_id:path}/map')
@app.route('/collections/{collection_id:path}/styles/{style_id:path}/map')
async def collection_map(request: Request, collection_id, style_id=None):
    """
    OGC API - Maps map render endpoint

    :param collection_id: collection identifier
    :param style_id: style identifier

    :returns: HTTP response
    """

    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    if 'style_id' in request.path_params:
        style_id = request.path_params['style_id']

    return get_response(api_.get_collection_map(
        request, collection_id, style_id))


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


@app.route('/jobs')
@app.route('/jobs/{job_id}', methods=['GET', 'DELETE'])
@app.route('/jobs/{job_id}/', methods=['GET', 'DELETE'])
async def get_jobs(request: Request, job_id=None):
    """
    OGC API - Processes jobs endpoint

    :param request: Starlette Request instance
    :param job_id: job identifier

    :returns: Starlette HTTP Response
    """

    if 'job_id' in request.path_params:
        job_id = request.path_params['job_id']

    if job_id is None:  # list of submit job
        return get_response(api_.get_jobs(request))
    else:  # get or delete job
        if request.method == 'DELETE':
            return get_response(api_.delete_job(job_id))
        else:  # Return status of a specific job
            return get_response(api_.get_jobs(request, job_id))


@app.route('/processes/{process_id}/execution', methods=['POST'])
@app.route('/processes/{process_id}/execution/', methods=['POST'])
async def execute_process_jobs(request: Request, process_id=None):
    """
    OGC API - Processes jobs endpoint

    :param request: Starlette Request instance
    :param process_id: process identifier

    :returns: Starlette HTTP Response
    """

    if 'process_id' in request.path_params:
        process_id = request.path_params['process_id']

    return get_response(api_.execute_process(request, process_id))


@app.route('/jobs/{job_id}/results', methods=['GET'])
@app.route('/jobs/{job_id}/results/', methods=['GET'])
async def get_job_result(request: Request, job_id=None):
    """
    OGC API - Processes job result endpoint

    :param request: Starlette Request instance
    :param job_id: job identifier

    :returns: HTTP response
    """

    if 'job_id' in request.path_params:
        job_id = request.path_params['job_id']

    return get_response(api_.get_job_result(request, job_id))


@app.route('/jobs/{job_id}/results/{resource}',
           methods=['GET'])
@app.route('/jobs/{job_id}/results/{resource}/',
           methods=['GET'])
async def get_job_result_resource(request: Request,
                                  job_id=None, resource=None):
    """
    OGC API - Processes job result resource endpoint

    :param request: Starlette Request instance
    :param job_id: job identifier
    :param resource: job resource

    :returns: HTTP response
    """

    if 'job_id' in request.path_params:
        job_id = request.path_params['job_id']
    if 'resource' in request.path_params:
        resource = request.path_params['resource']

    return get_response(api_.get_job_result_resource(
        request, job_id, resource))


@app.route('/collections/{collection_id:path}/position')
@app.route('/collections/{collection_id:path}/area')
@app.route('/collections/{collection_id:path}/cube')
@app.route('/collections/{collection_id:path}/trajectory')
@app.route('/collections/{collection_id:path}/corridor')
@app.route('/collections/{collection_id:path}/instances/{instance_id}/position')  # noqa
@app.route('/collections/{collection_id:path}/instances/{instance_id}/area')
@app.route('/collections/{collection_id:path}/instances/{instance_id}/cube')
@app.route('/collections/{collection_id:path}/instances/{instance_id}/trajectory')  # noqa
@app.route('/collections/{collection_id:path}/instances/{instance_id}/corridor')  # noqa
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

    query_type = request["path"].split('/')[-1]  # noqa
    return get_response(api_.get_collection_edr_query(request, collection_id,
                                                      instance_id, query_type))


@app.route('/collections')
@app.route('/collections/')
@app.route('/collections/{collection_id:path}')
@app.route('/collections/{collection_id:path}/')
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
    :param debug: `bool` of whether to run in debug mode,
                    default log level is INFO

    :returns: void
    """

    log_level = 'info'
    if debug:
        log_level = 'debug'
    uvicorn.run(
        "pygeoapi.starlette_app:app",
        reload=True,
        log_level=log_level,
        loop='asyncio',
        host=api_.config['server']['bind']['host'],
        port=api_.config['server']['bind']['port'])


if __name__ == "__main__":  # run locally, for testing
    serve()
