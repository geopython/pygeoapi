# =================================================================
#
# Authors: Francesco Bartoli <francesco.bartoli@geobeyond.it>
#          Luca Delucchi <lucadeluge@gmail.com>
#          Krishna Lodha <krishnaglodha@gmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Francesco Bartoli
# Copyright (c) 2022 Luca Delucchi
# Copyright (c) 2022 Krishna Lodha
# Copyright (c) 2024 Tom Kralidis
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

"""Integration module for Django"""

from typing import Tuple, Dict, Mapping, Optional, Union

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from pygeoapi.api import API, APIRequest, apply_gzip
import pygeoapi.api.coverages as coverages_api
import pygeoapi.api.environmental_data_retrieval as edr_api
import pygeoapi.api.itemtypes as itemtypes_api
import pygeoapi.api.maps as maps_api
import pygeoapi.api.processes as processes_api
import pygeoapi.api.stac as stac_api
import pygeoapi.api.tiles as tiles_api


def landing_page(request: HttpRequest) -> HttpResponse:
    """
    OGC API landing page endpoint

    :request Django HTTP Request

    :returns: Django HTTP Response
    """

    response_ = _feed_response(request, 'landing_page')
    response = _to_django_response(*response_)

    return response


def openapi(request: HttpRequest) -> HttpResponse:
    """
    OpenAPI endpoint

    :request Django HTTP Request

    :returns: Django HTTP Response
    """

    response_ = _feed_response(request, 'openapi_')
    response = _to_django_response(*response_)

    return response


def conformance(request: HttpRequest) -> HttpResponse:
    """
    OGC API conformance endpoint

    :request Django HTTP Request

    :returns: Django HTTP Response
    """

    response_ = _feed_response(request, 'conformance')
    response = _to_django_response(*response_)

    return response


def tilematrixsets(request: HttpRequest,
                   tilematrixset_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API tilematrixsets endpoint

    :request Django HTTP Request
    :param tilematrixset_id: tile matrix set identifier

    :returns: Django HTTP Response
    """

    if tilematrixset_id is None:
        response_ = execute_from_django(tiles_api.tilematrixsets, request)
    else:
        response_ = execute_from_django(tiles_api.tilematrixsets, request,
                                        tilematrixset_id)

    return response_


def collections(request: HttpRequest,
                collection_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API collections endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP Response
    """

    response_ = _feed_response(request, 'describe_collections', collection_id)

    return _to_django_response(*response_)


def collection_schema(request: HttpRequest,
                      collection_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API collections schema endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP Response
    """

    return execute_from_django(itemtypes_api.get_collection_schema, request,
                               collection_id)


def collection_queryables(request: HttpRequest,
                          collection_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API collections queryables endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP Response
    """

    return execute_from_django(
        itemtypes_api.get_collection_queryables, request, collection_id
    )


def collection_items(request: HttpRequest, collection_id: str) -> HttpResponse:
    """
    OGC API collections items endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP response
    """

    if request.method == 'GET':
        response_ = execute_from_django(
            itemtypes_api.get_collection_items,
            request,
            collection_id,
            skip_valid_check=True,
        )
    elif request.method == 'POST':
        if request.content_type is not None:
            if request.content_type == 'application/geo+json':
                response_ = execute_from_django(
                    itemtypes_api.manage_collection_item, request,
                    'create', collection_id, skip_valid_check=True)
            else:
                response_ = execute_from_django(
                    itemtypes_api.post_collection_items,
                    request, collection_id, skip_valid_check=True,)
    elif request.method == 'OPTIONS':
        response_ = execute_from_django(itemtypes_api.manage_collection_item,
                                        request, 'options', collection_id,
                                        skip_valid_check=True)

    return response_


def collection_map(request: HttpRequest, collection_id: str):
    """
    OGC API - Maps map render endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """

    return execute_from_django(
        maps_api.get_collection_map, request, collection_id
    )


def collection_style_map(request: HttpRequest, collection_id: str,
                         style_id: str = None):
    """
    OGC API - Maps map render endpoint

    :param collection_id: collection identifier
    :param collection_id: style identifier

    :returns: HTTP response
    """

    return execute_from_django(maps_api.get_collection_map, request,
                               collection_id, style_id)


def collection_item(request: HttpRequest,
                    collection_id: str, item_id: str) -> HttpResponse:
    """
    OGC API collections items endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier
    :param item_id: item identifier

    :returns: Django HTTP response
    """

    if request.method == 'GET':
        response_ = execute_from_django(itemtypes_api.get_collection_item,
                                        request, collection_id, item_id)
    elif request.method == 'PUT':
        response_ = execute_from_django(itemtypes_api.manage_collection_item,
                                        request, 'update', collection_id,
                                        item_id, skip_valid_check=True)
    elif request.method == 'DELETE':
        response_ = execute_from_django(itemtypes_api.manage_collection_item,
                                        request, 'delete', collection_id,
                                        item_id, skip_valid_check=True)
    elif request.method == 'OPTIONS':
        response_ = execute_from_django(itemtypes_api.manage_collection_item,
                                        request, 'options', collection_id,
                                        item_id, skip_valid_check=True)

    return response_


def collection_coverage(request: HttpRequest,
                        collection_id: str) -> HttpResponse:
    """
    OGC API - Coverages coverage endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP response
    """

    return execute_from_django(
        coverages_api.get_collection_coverage, request, collection_id,
        skip_valid_check=True
    )


def collection_tiles(request: HttpRequest, collection_id: str) -> HttpResponse:
    """
    OGC API - Tiles collection tiles endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP response
    """

    return execute_from_django(tiles_api.get_collection_tiles, request,
                               collection_id)


def collection_tiles_metadata(request: HttpRequest, collection_id: str,
                              tileMatrixSetId: str) -> HttpResponse:
    """
    OGC API - Tiles collection tiles metadata endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier
    :param tileMatrixSetId: identifier of tile matrix set

    :returns: Django HTTP response
    """

    return execute_from_django(
        tiles_api.get_collection_tiles_metadata,
        request, collection_id, tileMatrixSetId,
        skip_valid_check=True
    )


def collection_item_tiles(request: HttpRequest, collection_id: str,
                          tileMatrixSetId: str, tileMatrix: str,
                          tileRow: str, tileCol: str) -> HttpResponse:
    """
    OGC API - Tiles collection tiles data endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier
    :param tileMatrixSetId: identifier of tile matrix set
    :param tileMatrix: identifier of {z} matrix index
    :param tileRow: identifier of {y} matrix index
    :param tileCol: identifier of {x} matrix index

    :returns: Django HTTP response
    """

    return execute_from_django(
        tiles_api.get_collection_tiles_data,
        request,
        collection_id,
        tileMatrixSetId,
        tileMatrix,
        tileRow,
        tileCol,
        skip_valid_check=True
    )


def processes(request: HttpRequest,
              process_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API - Processes description endpoint

    :request Django HTTP Request
    :param process_id: process identifier

    :returns: Django HTTP response
    """

    return execute_from_django(processes_api.describe_processes, request,
                               process_id)


def process_execution(request: HttpRequest, process_id: str) -> HttpResponse:
    """
    OGC API - Processes execution endpoint

    :request Django HTTP Request
    :param process_id: process identifier

    :returns: Django HTTP response
    """

    return execute_from_django(processes_api.execute_process, request,
                               process_id)


def jobs(request: HttpRequest, job_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API - Jobs endpoint

    :request Django HTTP Request
    :param process_id: process identifier
    :param job_id: job identifier

    :returns: Django HTTP response
    """

    if job_id is None:
        response_ = execute_from_django(processes_api.get_jobs, request)
    else:
        if request.method == 'DELETE':  # dismiss job
            response_ = execute_from_django(processes_api.delete_job, request,
                                            job_id)
        else:  # Return status of a specific job
            response_ = execute_from_django(processes_api.get_jobs, request,
                                            job_id)

    return response_


def job_results(request: HttpRequest,
                job_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API - Job result endpoint

    :request Django HTTP Request
    :param job_id: job identifier

    :returns: Django HTTP response
    """

    return execute_from_django(processes_api.get_job_result, request, job_id)


def job_results_resource(request: HttpRequest, process_id: str, job_id: str,
                         resource: str) -> HttpResponse:
    """
    OGC API - Job result resource endpoint

    :request Django HTTP Request
    :param job_id: job identifier
    :param resource: job resource

    :returns: Django HTTP response
    """

    # TODO: this api method does not exist
    return execute_from_django(processes_api.get_job_result_resource,
                               request, job_id, resource)


def get_collection_edr_query(
        request: HttpRequest, collection_id: str,
        instance_id: Optional[str] = None,
        location_id: Optional[str] = None
) -> HttpResponse:
    """
    OGC API - EDR endpoint

    :param request: Django HTTP Request
    :param collection_id: collection identifier
    :param instance_id: optional instance identifier. default is None
    :param location_id: optional location identifier. default is None

    :returns: Django HTTP response
    """

    if location_id:
        query_type = 'locations'
    else:
        query_type = request.path.split('/')[-1]

    return execute_from_django(
        edr_api.get_collection_edr_query,
        request,
        collection_id,
        instance_id,
        query_type,
        location_id,
        skip_valid_check=True
    )


def stac_catalog_root(request: HttpRequest) -> HttpResponse:
    """
    STAC root endpoint

    :request Django HTTP Request

    :returns: Django HTTP response
    """

    return execute_from_django(stac_api.get_stac_root, request)


def stac_catalog_path(request: HttpRequest, path: str) -> HttpResponse:
    """
    STAC path endpoint

    :request Django HTTP Request
    :param path: path

    :returns: Django HTTP response
    """

    return execute_from_django(stac_api.get_stac_path, request, path)


def admin_config(request: HttpRequest) -> HttpResponse:
    """
    Admin landing page endpoint

    :returns: HTTP response
    """

    if request.method == 'GET':
        return _feed_response(request, 'get_admin_config')

    elif request.method == 'PUT':
        return _feed_response(request, 'put_admin_config')

    elif request.method == 'PATCH':
        return _feed_response(request, 'patch_admin_config')


def admin_config_resources(request: HttpRequest) -> HttpResponse:
    """
    Resource landing page endpoint

    :returns: HTTP response
    """

    if request.method == 'GET':
        return _feed_response(request, 'get_admin_config_resources')

    elif request.method == 'POST':
        return _feed_response(request, 'put_admin_config_resources')


def admin_config_resource(request: HttpRequest,
                          resource_id: str) -> HttpResponse:
    """
    Resource landing page endpoint

    :returns: HTTP response
    """

    if request.method == 'GET':
        return _feed_response(request, 'put_admin_config_resource',
                              resource_id)

    elif request.method == 'DELETE':
        return _feed_response(request, 'delete_admin_config_resource',
                              resource_id)

    elif request.method == 'PUT':
        return _feed_response(request, 'put_admin_config_resource',
                              resource_id)

    elif request.method == 'PATCH':
        return _feed_response(request, 'patch_admin_config_resource',
                              resource_id)


# TODO: remove this when all views have been refactored
def _feed_response(request: HttpRequest, api_definition: str,
                   *args, **kwargs) -> Tuple[Dict, int, str]:
    """Use pygeoapi api to process the input request"""

    if 'admin' in api_definition and settings.PYGEOAPI_CONFIG['server'].get('admin'):  # noqa
        from pygeoapi.admin import Admin
        api_ = Admin(settings.PYGEOAPI_CONFIG, settings.OPENAPI_DOCUMENT)
    else:
        api_ = API(settings.PYGEOAPI_CONFIG, settings.OPENAPI_DOCUMENT)

    api = getattr(api_, api_definition)

    return api(request, *args, **kwargs)


def execute_from_django(api_function, request: HttpRequest, *args,
                        skip_valid_check=False) -> HttpResponse:

    api_: API | "Admin"
    if settings.PYGEOAPI_CONFIG['server'].get('admin'):  # noqa
        from pygeoapi.admin import Admin
        api_ = Admin(settings.PYGEOAPI_CONFIG, settings.OPENAPI_DOCUMENT)
    else:
        api_ = API(settings.PYGEOAPI_CONFIG, settings.OPENAPI_DOCUMENT)

    api_request = APIRequest.from_django(request, api_.locales)
    content: Union[str, bytes]
    if not skip_valid_check and not api_request.is_valid():
        headers, status, content = api_.get_format_exception(api_request)
    else:

        headers, status, content = api_function(api_, api_request, *args)
        content = apply_gzip(headers, content)

    return _to_django_response(headers, status, content)


# TODO: inline this to execute_from_django after refactoring
def _to_django_response(headers: Mapping, status_code: int,
                        content: Union[str, bytes]) -> HttpResponse:
    """Convert API payload to a django response"""

    response = HttpResponse(content, status=status_code)

    for key, value in headers.items():
        response[key] = value
    return response
