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
# Copyright (c) 2022 Tom Kralidis
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

from typing import Tuple, Dict, Mapping, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from pygeoapi.api import API


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

    response = None

    if tilematrixset_id is None:
        response_ = _feed_response(request, 'tilematrixsets')
    else:
        response_ = _feed_response(request, 'tilematrixset', tilematrixset_id)
    response = _to_django_response(*response_)

    return response


def collections(request: HttpRequest,
                collection_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API collections endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP Response
    """

    response_ = _feed_response(request, 'describe_collections', collection_id)
    response = _to_django_response(*response_)

    return response


def collection_schema(request: HttpRequest,
                      collection_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API collections schema endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP Response
    """

    response_ = _feed_response(
        request, 'get_collection_schema', collection_id
    )
    response = _to_django_response(*response_)

    return response


def collection_queryables(request: HttpRequest,
                          collection_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API collections queryables endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP Response
    """

    response_ = _feed_response(
        request, 'get_collection_queryables', collection_id
    )
    response = _to_django_response(*response_)

    return response


def collection_items(request: HttpRequest, collection_id: str) -> HttpResponse:
    """
    OGC API collections items endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP response
    """

    if request.method == 'GET':
        response_ = _feed_response(
            request,
            'get_collection_items',
            collection_id,
        )
    elif request.method == 'POST':
        if request.content_type is not None:
            if request.content_type == 'application/geo+json':
                response_ = _feed_response(request, 'manage_collection_item',
                                           request, 'create', collection_id)
            else:
                response_ = _feed_response(request, 'post_collection_items',
                                           request, collection_id)
    elif request.method == 'OPTIONS':
        response_ = _feed_response(request, 'manage_collection_item',
                                   request, 'options', collection_id)

    response = _to_django_response(*response_)

    return response


def collection_map(request: HttpRequest, collection_id: str):
    """
    OGC API - Maps map render endpoint

    :param collection_id: collection identifier

    :returns: HTTP response
    """

    response_ = _feed_response(request, 'get_collection_map', collection_id)

    response = _to_django_response(*response_)

    return response


def collection_style_map(request: HttpRequest, collection_id: str,
                         style_id: str = None):
    """
    OGC API - Maps map render endpoint

    :param collection_id: collection identifier
    :param collection_id: style identifier

    :returns: HTTP response
    """

    response_ = _feed_response(request, 'get_collection_map',
                               collection_id, style_id)

    response = _to_django_response(*response_)

    return response


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
        response_ = _feed_response(
            request, 'get_collection_item', collection_id, item_id
        )
    elif request.method == 'PUT':
        response_ = _feed_response(
            request, 'manage_collection_item', request, 'update',
            collection_id, item_id
        )
    elif request.method == 'DELETE':
        response_ = _feed_response(
            request, 'manage_collection_item', request, 'delete',
            collection_id, item_id
        )
    elif request.method == 'OPTIONS':
        response_ = _feed_response(
            request, 'manage_collection_item', request, 'options',
            collection_id, item_id)

    response = _to_django_response(*response_)

    return response


def collection_coverage(request: HttpRequest,
                        collection_id: str) -> HttpResponse:
    """
    OGC API - Coverages coverage endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(
        request, 'get_collection_coverage', collection_id
    )
    response = _to_django_response(*response_)

    return response


def collection_tiles(request: HttpRequest, collection_id: str) -> HttpResponse:
    """
    OGC API - Tiles collection tiles endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(request, 'get_collection_tiles', collection_id)
    response = _to_django_response(*response_)

    return response


def collection_tiles_metadata(request: HttpRequest, collection_id: str,
                              tileMatrixSetId: str) -> HttpResponse:
    """
    OGC API - Tiles collection tiles metadata endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier
    :param tileMatrixSetId: identifier of tile matrix set

    :returns: Django HTTP response
    """

    response_ = _feed_response(
        request,
        'get_collection_tiles_metadata',
        collection_id,
        tileMatrixSetId,
    )
    response = _to_django_response(*response_)

    return response


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

    response_ = _feed_response(
        request,
        'get_collection_tiles_data',
        collection_id,
        tileMatrixSetId,
        tileMatrix,
        tileRow,
        tileCol,
    )
    response = _to_django_response(*response_)

    return response


def processes(request: HttpRequest,
              process_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API - Processes description endpoint

    :request Django HTTP Request
    :param process_id: process identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(request, 'describe_processes', process_id)
    response = _to_django_response(*response_)

    return response


def jobs(request: HttpRequest, job_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API - Jobs endpoint

    :request Django HTTP Request
    :param process_id: process identifier
    :param job_id: job identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(request, 'get_jobs', job_id)
    response = _to_django_response(*response_)

    return response


def job_results(request: HttpRequest,
                job_id: Optional[str] = None) -> HttpResponse:
    """
    OGC API - Job result endpoint

    :request Django HTTP Request
    :param job_id: job identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(request, 'get_job_result', job_id)
    response = _to_django_response(*response_)

    return response


def job_results_resource(request: HttpRequest, process_id: str, job_id: str,
                         resource: str) -> HttpResponse:
    """
    OGC API - Job result resource endpoint

    :request Django HTTP Request
    :param job_id: job identifier
    :param resource: job resource

    :returns: Django HTTP response
    """

    response_ = _feed_response(
        request,
        'get_job_result_resource',
        job_id,
        resource
    )
    response = _to_django_response(*response_)

    return response


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
    response_ = _feed_response(
        request,
        'get_collection_edr_query',
        collection_id,
        instance_id,
        query_type,
        location_id
    )
    response = _to_django_response(*response_)

    return response


def stac_catalog_root(request: HttpRequest) -> HttpResponse:
    """
    STAC root endpoint

    :request Django HTTP Request

    :returns: Django HTTP response
    """

    response_ = _feed_response(request, 'get_stac_root')
    response = _to_django_response(*response_)

    return response


def stac_catalog_path(request: HttpRequest, path: str) -> HttpResponse:
    """
    STAC path endpoint

    :request Django HTTP Request
    :param path: path

    :returns: Django HTTP response
    """

    response_ = _feed_response(request, 'get_stac_path', path)
    response = _to_django_response(*response_)

    return response


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


def _to_django_response(headers: Mapping, status_code: int,
                        content: str) -> HttpResponse:
    """Convert API payload to a django response"""

    response = HttpResponse(content, status=status_code)

    for key, value in headers.items():
        response[key] = value
    return response
