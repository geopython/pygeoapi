# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#          Abdulazeez Abdulazeez Adeshina <youngestdev@gmail.com>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2020 Francesco Bartoli
# Copyright (c) 2022 Tom Kralidis
# Copyright (c) 2022 Abdulazeez Abdulazeez Adeshina
# Copyright (c) 2023 Ricardo Garcia Silva
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
import logging
from typing import Union
from pathlib import Path

import click

from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.datastructures import URL
from starlette.types import ASGIApp, Scope, Send, Receive
from starlette.responses import (
    Response, JSONResponse, HTMLResponse, RedirectResponse
)
from uvicorn.workers import UvicornWorker

import pygeoapi.util
from pygeoapi.api import API
from pygeoapi.models import config as config_models

LOGGER = logging.getLogger(__name__)


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


async def landing_page(request: Request):
    """
    OGC API landing page endpoint

    :param request: Starlette Request instance

    :returns: Starlette HTTP Response
    """
    api_ = request.app.state.PYGEOAPI
    return get_response(api_.landing_page(request))


async def openapi(request: Request):
    """
    OpenAPI endpoint

    :param request: Starlette Request instance

    :returns: Starlette HTTP Response
    """
    api_ = request.app.state.PYGEOAPI
    return get_response(api_.openapi_(request))


async def conformance(request: Request):
    """
    OGC API conformance endpoint

    :param request: Starlette Request instance

    :returns: Starlette HTTP Response
    """
    api_ = request.app.state.PYGEOAPI
    return get_response(api_.conformance(request))


async def collection_queryables(request: Request, collection_id=None):
    """
    OGC API collections queryables endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    api_ = request.app.state.PYGEOAPI
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    return get_response(api_.get_collection_queryables(request, collection_id))


async def get_collection_tiles(request: Request, collection_id=None):
    """
    OGC open api collections tiles access point

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    api_ = request.app.state.PYGEOAPI
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    return get_response(api_.get_collection_tiles(
        request, collection_id))


async def get_collection_tiles_metadata(request: Request, collection_id=None,
                                        tileMatrixSetId=None):
    """
    OGC open api collection tiles service metadata

    :param collection_id: collection identifier
    :param tileMatrixSetId: identifier of tile matrix set

    :returns: HTTP response
    """
    api_ = request.app.state.PYGEOAPI
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    if 'tileMatrixSetId' in request.path_params:
        tileMatrixSetId = request.path_params['tileMatrixSetId']
    return get_response(api_.get_collection_tiles_metadata(
        request, collection_id, tileMatrixSetId))


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
    api_ = request.app.state.PYGEOAPI
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


async def collection_items(request: Request, collection_id=None, item_id=None):
    """
    OGC API collections items endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier
    :param item_id: item identifier

    :returns: Starlette HTTP Response
    """

    api_ = request.app.state.PYGEOAPI
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
        elif request.method == 'OPTIONS':
            return get_response(
                api_.manage_collection_item(request, 'options', collection_id))

    elif request.method == 'DELETE':
        return get_response(
            api_.manage_collection_item(request, 'delete',
                                        collection_id, item_id))
    elif request.method == 'PUT':
        return get_response(
            api_.manage_collection_item(request, 'update',
                                        collection_id, item_id))
    elif request.method == 'OPTIONS':
        return get_response(
            api_.manage_collection_item(request, 'options',
                                        collection_id, item_id))
    else:
        return get_response(api_.get_collection_item(
            request, collection_id, item_id))


async def collection_coverage(request: Request, collection_id=None):
    """
    OGC API - Coverages coverage endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    api_ = request.app.state.PYGEOAPI
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    return get_response(api_.get_collection_coverage(request, collection_id))


async def collection_coverage_domainset(request: Request, collection_id=None):
    """
    OGC API - Coverages coverage domainset endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    api_ = request.app.state.PYGEOAPI
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    return get_response(api_.get_collection_coverage_domainset(
        request, collection_id))


async def collection_coverage_rangetype(request: Request, collection_id=None):
    """
    OGC API - Coverages coverage rangetype endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """

    api_ = request.app.state.PYGEOAPI
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    return get_response(api_.get_collection_coverage_rangetype(
        request, collection_id))


async def collection_map(request: Request, collection_id, style_id=None):
    """
    OGC API - Maps map render endpoint

    :param collection_id: collection identifier
    :param style_id: style identifier

    :returns: HTTP response
    """

    api_ = request.app.state.PYGEOAPI
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    if 'style_id' in request.path_params:
        style_id = request.path_params['style_id']

    return get_response(api_.get_collection_map(
        request, collection_id, style_id))


async def get_processes(request: Request, process_id=None):
    """
    OGC API - Processes description endpoint

    :param request: Starlette Request instance
    :param process_id: identifier of process to describe

    :returns: Starlette HTTP Response
    """
    api_ = request.app.state.PYGEOAPI
    if 'process_id' in request.path_params:
        process_id = request.path_params['process_id']

    return get_response(api_.describe_processes(request, process_id))


async def get_jobs(request: Request, job_id=None):
    """
    OGC API - Processes jobs endpoint

    :param request: Starlette Request instance
    :param job_id: job identifier

    :returns: Starlette HTTP Response
    """

    api_ = request.app.state.PYGEOAPI
    if 'job_id' in request.path_params:
        job_id = request.path_params['job_id']

    if job_id is None:  # list of submit job
        return get_response(api_.get_jobs(request))
    else:  # get or delete job
        if request.method == 'DELETE':
            return get_response(api_.delete_job(job_id))
        else:  # Return status of a specific job
            return get_response(api_.get_jobs(request, job_id))


async def execute_process_jobs(request: Request, process_id=None):
    """
    OGC API - Processes jobs endpoint

    :param request: Starlette Request instance
    :param process_id: process identifier

    :returns: Starlette HTTP Response
    """

    api_ = request.app.state.PYGEOAPI
    if 'process_id' in request.path_params:
        process_id = request.path_params['process_id']

    return get_response(api_.execute_process(request, process_id))


async def get_job_result(request: Request, job_id=None):
    """
    OGC API - Processes job result endpoint

    :param request: Starlette Request instance
    :param job_id: job identifier

    :returns: HTTP response
    """

    api_ = request.app.state.PYGEOAPI
    if 'job_id' in request.path_params:
        job_id = request.path_params['job_id']

    return get_response(api_.get_job_result(request, job_id))


async def get_job_result_resource(request: Request,
                                  job_id=None, resource=None):
    """
    OGC API - Processes job result resource endpoint

    :param request: Starlette Request instance
    :param job_id: job identifier
    :param resource: job resource

    :returns: HTTP response
    """

    api_ = request.app.state.PYGEOAPI
    if 'job_id' in request.path_params:
        job_id = request.path_params['job_id']
    if 'resource' in request.path_params:
        resource = request.path_params['resource']

    return get_response(api_.get_job_result_resource(
        request, job_id, resource))


async def get_collection_edr_query(request: Request, collection_id=None, instance_id=None):  # noqa
    """
    OGC EDR API endpoints

    :param collection_id: collection identifier
    :param instance_id: instance identifier

    :returns: HTTP response
    """

    api_ = request.app.state.PYGEOAPI
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']

    if 'instance_id' in request.path_params:
        instance_id = request.path_params['instance_id']

    query_type = request["path"].split('/')[-1]  # noqa
    return get_response(api_.get_collection_edr_query(request, collection_id,
                                                      instance_id, query_type))


async def collections(request: Request, collection_id=None):
    """
    OGC API collections endpoint

    :param request: Starlette Request instance
    :param collection_id: collection identifier

    :returns: Starlette HTTP Response
    """
    api_ = request.app.state.PYGEOAPI
    if 'collection_id' in request.path_params:
        collection_id = request.path_params['collection_id']
    return get_response(api_.describe_collections(request, collection_id))


async def stac_catalog_root(request: Request):
    """
    STAC root endpoint

    :param request: Starlette Request instance

    :returns: Starlette HTTP response
    """
    api_ = request.app.state.PYGEOAPI
    return get_response(api_.get_stac_root(request))


async def stac_catalog_path(request: Request):
    """
    STAC endpoint

    :param request: Starlette Request instance

    :returns: Starlette HTTP response
    """
    api_ = request.app.state.PYGEOAPI
    path = request.path_params["path"]
    return get_response(api_.get_stac_path(request, path))


class PygeoapiUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {
        # this parameter is set because the starlette implementation uses
        # nest_asyncio, which only works with asyncio
        'loop': 'asyncio'
    }


class ApiRulesMiddleware:
    """ Custom middleware to properly deal with trailing slashes.
    See https://github.com/encode/starlette/issues/869.
    """
    def __init__(
            self,
            app: ASGIApp,
            *,
            api_rules: config_models.APIRules,
    ) -> None:
        self.app = app
        # self.prefix = API_RULES.get_url_prefix('starlette')
        self.prefix = api_rules.get_url_prefix('starlette')
        self.strict_slashes = api_rules.strict_slashes

    async def __call__(self, scope: Scope,
                       receive: Receive, send: Send) -> None:
        # if scope['type'] == "http" and API_RULES.strict_slashes:
        if scope['type'] == "http" and self.strict_slashes:
            path = scope['path']
            if path == self.prefix:
                # If the root (landing page) is requested without a trailing
                # slash, redirect to landing page with trailing slash.
                # Starlette will otherwise throw a 404, as it does not like
                # empty Route paths.
                url = URL(scope=scope).replace(path=f"{path}/")
                response = RedirectResponse(url)
                await response(scope, receive, send)
                return
            elif path != f"{self.prefix}/" and path.endswith('/'):
                # Resource paths should NOT have trailing slashes
                response = Response(status_code=404)
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


api_routes = [
    Route('/', landing_page),
    Route('/openapi', openapi),
    Route('/conformance', conformance),
    Route('/collections/{collection_id:path}/queryables', collection_queryables),  # noqa
    Route('/collections/{collection_id:path}/tiles', get_collection_tiles),
    Route('/collections/{collection_id:path}/tiles/{tileMatrixSetId}', get_collection_tiles_metadata),  # noqa
    Route('/collections/{collection_id:path}/tiles/{tileMatrixSetId}/metadata', get_collection_tiles_metadata),  # noqa
    Route('/collections/{collection_id:path}/tiles/{tileMatrixSetId}/{tile_matrix}/{tileRow}/{tileCol}', get_collection_items_tiles),  # noqa
    Route('/collections/{collection_id:path}/items', collection_items, methods=['GET', 'POST', 'OPTIONS']),  # noqa
    Route('/collections/{collection_id:path}/items/{item_id:path}', collection_items, methods=['GET', 'PUT', 'DELETE', 'OPTIONS']),  # noqa
    Route('/collections/{collection_id:path}/coverage', collection_coverage),  # noqa
    Route('/collections/{collection_id:path}/coverage/domainset', collection_coverage_domainset),  # noqa
    Route('/collections/{collection_id:path}/coverage/rangetype', collection_coverage_rangetype),  # noqa
    Route('/collections/{collection_id:path}/map', collection_map),
    Route('/collections/{collection_id:path}/styles/{style_id:path}/map', collection_map),  # noqa
    Route('/processes', get_processes),
    Route('/processes/{process_id}', get_processes),
    Route('/jobs', get_jobs),
    Route('/jobs/{job_id}', get_jobs, methods=['GET', 'DELETE']),
    Route('/processes/{process_id}/execution', execute_process_jobs, methods=['POST']),  # noqa
    Route('/jobs/{job_id}/results', get_job_result),
    Route('/jobs/{job_id}/results/{resource}', get_job_result_resource),
    Route('/collections/{collection_id:path}/position', get_collection_edr_query),  # noqa
    Route('/collections/{collection_id:path}/area', get_collection_edr_query),
    Route('/collections/{collection_id:path}/cube', get_collection_edr_query),
    Route('/collections/{collection_id:path}/radius', get_collection_edr_query),  # noqa
    Route('/collections/{collection_id:path}/trajectory', get_collection_edr_query),  # noqa
    Route('/collections/{collection_id:path}/corridor', get_collection_edr_query),  # noqa
    Route('/collections/{collection_id:path}/instances/{instance_id}/position', get_collection_edr_query),  # noqa
    Route('/collections/{collection_id:path}/instances/{instance_id}/area', get_collection_edr_query),  # noqa
    Route('/collections/{collection_id:path}/instances/{instance_id}/cube', get_collection_edr_query),  # noqa
    Route('/collections/{collection_id:path}/instances/{instance_id}/radius', get_collection_edr_query),  # noqa
    Route('/collections/{collection_id:path}/instances/{instance_id}/trajectory', get_collection_edr_query),  # noqa
    Route('/collections/{collection_id:path}/instances/{instance_id}/corridor', get_collection_edr_query),  # noqa
    Route('/collections', collections),
    Route('/collections/{collection_id:path}', collections),
    Route('/stac', stac_catalog_root),
    Route('/stac/{path:path}', stac_catalog_path),
]


def create_app(pygeoapi_config_path: str, pygeoapi_openapi_path: str) -> Starlette:
    """Create the pygeoapi starlette application"""
    pygeoapi_config = pygeoapi.util.get_config_from_path(
        Path(pygeoapi_config_path))
    pygeoapi_openapi_document = pygeoapi.util.get_openapi_from_path(
        Path(pygeoapi_openapi_path))
    api_rules = pygeoapi.util.get_api_rules(pygeoapi_config)
    url_prefix = api_rules.get_url_prefix('starlette')
    static_dir = Path(__file__).parent.resolve() / 'static'
    app = Starlette(
        routes=[
            Mount(
                f'{url_prefix}/static', StaticFiles(directory=static_dir)),
            Mount(url_prefix or '/', routes=api_routes)
        ]
    )
    if url_prefix:
        # If a URL prefix is in effect, Flask allows the static resource URLs
        # to be written both with or without that prefix (200 in both cases).
        # Starlette does not allow this, so for consistency we'll add a static
        # mount here WITHOUT the URL prefix (due to router order).
        app.mount(
            '/static', StaticFiles(directory=static_dir),
        )

    # If API rules require strict slashes, do not redirect
    if api_rules.strict_slashes:
        app.router.redirect_slashes = False
        app.add_middleware(ApiRulesMiddleware, api_rules=api_rules)

    # CORS: optionally enable from config.
    if pygeoapi_config.get('server', {}).get('cors', False):
        from starlette.middleware.cors import CORSMiddleware
        app.add_middleware(CORSMiddleware, allow_origins=['*'])

    ogc_schemas_location = pygeoapi_config.get(
        'server', {}).get('ogc_schemas_location')
    if ogc_schemas_location is not None:
        if not ogc_schemas_location.startswith('http'):
            schemas_dir = Path(ogc_schemas_location)
            if schemas_dir.is_dir():
                app.mount(
                    f'{url_prefix}/schemas',
                    StaticFiles(directory=schemas_dir)
                )
            else:
                raise RuntimeError('OGC schemas misconfigured')
        else:
            LOGGER.warning(
                "OGC SCHEMAS are configured as a remote resource - "
                "cannot serve locally"
            )
    else:
        LOGGER.warning('OGC SCHEMAS are not configured - cannot serve locally')

    if (ogc_schemas_location is not None and
            not ogc_schemas_location.name.startswith('http')):
        if not ogc_schemas_location.exists():
            raise RuntimeError('OGC schemas misconfigured')
        app.mount(
            f'{url_prefix}/schemas', StaticFiles(directory=ogc_schemas_location)
        )
    app.state.PYGEOAPI = API(config=pygeoapi_config, openapi=pygeoapi_openapi_document)
    return app
