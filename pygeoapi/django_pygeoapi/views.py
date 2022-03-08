"""Integration module for Django"""
from typing import Tuple, Dict, Mapping, Optional
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from pygeoapi.api import API
from pygeoapi.openapi import get_oas


def landing_page(request: HttpRequest) -> HttpResponse:
    """
    OGC API landing page endpoint

    :request Django HTTP Request

    :returns: Django HTTP Response
    """

    response_ = _feed_response(request, "landing_page")
    response = _to_django_response(*response_)

    return response


def openapi(request: HttpRequest) -> HttpResponse:
    """
    OpenAPI endpoint

    :request Django HTTP Request

    :returns: Django HTTP Response
    """

    openapi_config = get_oas(settings.PYGEOAPI_CONFIG)
    response_ = _feed_response(request, "openapi", openapi_config)
    response = _to_django_response(*response_)

    return response


def conformance(request: HttpRequest) -> HttpResponse:
    """
    OGC API conformance endpoint

    :request Django HTTP Request

    :returns: Django HTTP Response
    """

    response_ = _feed_response(request, "conformance")
    response = _to_django_response(*response_)

    return response


def collections(
    request: HttpRequest,
    collection_id: Optional[str] = None,
) -> HttpResponse:
    """
    OGC API collections endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP Response
    """

    response_ = _feed_response(request, "describe_collections", collection_id)
    response = _to_django_response(*response_)

    return response


def collection_queryables(
    request: HttpRequest,
    collection_id: Optional[str] = None,
) -> HttpResponse:
    """
    OGC API collections queryables endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP Response
    """

    response_ = _feed_response(
        request, "get_collection_queryables", collection_id
    )
    response = _to_django_response(*response_)

    return response


def collection_items(
    request: HttpRequest,
    collection_id: str,
) -> HttpResponse:
    """
    OGC API collections items endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(
        request,
        "get_collection_items",
        collection_id,
        pathinfo=request.path_info,
    )
    response = _to_django_response(*response_)

    return response


def collection_item(
    request: HttpRequest,
    collection_id: str,
    item_id: str,
) -> HttpResponse:
    """
    OGC API collections items endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier
    :param item_id: item identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(
        request, "get_collection_item", collection_id, item_id
    )
    response = _to_django_response(*response_)

    return response


def collection_coverage(
    request: HttpRequest,
    collection_id: str,
) -> HttpResponse:
    """
    OGC API - Coverages coverage endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(
        request, "get_collection_coverage", collection_id
    )
    response = _to_django_response(*response_)

    return response


def collection_coverage_domainset(
    request: HttpRequest,
    collection_id: str,
) -> HttpResponse:
    """
    OGC API - Coverages coverage domainset endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(
        request, "get_collection_coverage_domainset", collection_id
    )
    response = _to_django_response(*response_)

    return response


def collection_coverage_rangetype(
    request: HttpRequest,
    collection_id: str,
) -> HttpResponse:
    """
    OGC API - Coverages coverage rangetype endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(
        request, "get_collection_coverage_rangetype", collection_id
    )
    response = _to_django_response(*response_)

    return response


def collection_tiles(
    request: HttpRequest,
    collection_id: str,
) -> HttpResponse:
    """
    OGC API - Tiles collection tiles endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(request, "get_collection_tiles", collection_id)
    response = _to_django_response(*response_)

    return response


def collection_tiles_metadata(
    request: HttpRequest,
    collection_id: str,
    tileMatrixSetId: str,
) -> HttpResponse:
    """
    OGC API - Tiles collection tiles metadata endpoint

    :request Django HTTP Request
    :param collection_id: collection identifier
    :param tileMatrixSetId: identifier of tile matrix set

    :returns: Django HTTP response
    """

    response_ = _feed_response(
        request,
        "get_collection_tiles_metadata",
        collection_id,
        tileMatrixSetId,
    )
    response = _to_django_response(*response_)

    return response


def collection_item_tiles(
    request: HttpRequest,
    collection_id: str,
    tileMatrixSetId: str,
    tileMatrix: str,
    tileRow: str,
    tileCol: str,
) -> HttpResponse:
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
        "get_collection_tiles_metadata",
        collection_id,
        tileMatrixSetId,
        tileMatrix,
        tileRow,
        tileCol,
    )
    response = _to_django_response(*response_)

    return response


def processes(
    request: HttpRequest,
    process_id: Optional[str] = None,
) -> HttpResponse:
    """
    OGC API - Processes description endpoint

    :request Django HTTP Request
    :param process_id: process identifier

    :returns: Django HTTP response
    """

    response_ = _feed_response(request, "describe_processes", process_id)
    response = _to_django_response(*response_)

    return response


def process_jobs(
    request: HttpRequest,
    process_id: str,
    job_id: Optional[str] = None,
) -> HttpResponse:
    """
    OGC API - Processes jobs endpoint

    :request Django HTTP Request
    :param process_id: process identifier
    :param job_id: job identifier

    :returns: Django HTTP response
    """
    pass


def process_job_results(
    request: HttpRequest,
    process_id: str,
    job_id: Optional[str] = None,
) -> HttpResponse:
    """
    OGC API - Processes job result endpoint

    :request Django HTTP Request
    :param process_id: process identifier
    :param job_id: job identifier

    :returns: Django HTTP response
    """
    pass


def process_job_results_resource(
    request: HttpRequest,
    process_id: str,
    job_id: str,
    resource: str,
) -> HttpResponse:
    """
    OGC API - Processes job result resource endpoint

    :request Django HTTP Request
    :param process_id: process identifier
    :param job_id: job identifier
    :param resource: job resource

    :returns: Django HTTP response
    """
    pass


def stac_catalog_root(request: HttpRequest) -> HttpResponse:
    """
    STAC root endpoint

    :request Django HTTP Request

    :returns: Django HTTP response
    """

    response_ = _feed_response(request, "get_stac_root")
    response = _to_django_response(*response_)

    return response


def stac_catalog_path(
    request: HttpRequest,
    path: str,
) -> HttpResponse:
    """
    STAC path endpoint

    :request Django HTTP Request
    :param path: path

    :returns: Django HTTP response
    """

    response_ = _feed_response(request, "get_stac_root", path)
    response = _to_django_response(*response_)

    return response


def stac_catalog_search(request: HttpRequest) -> HttpResponse:
    pass


def _feed_response(
    request: HttpRequest, api_definition: str, *args, **kwargs
) -> Tuple[Dict, int, str]:
    """Use pygeoapi api to process the input request"""
    api_ = API(settings.PYGEOAPI_CONFIG)
    api = getattr(api_, api_definition)
    return api(request.headers, request.GET, *args, **kwargs)


def _to_django_response(
    headers: Mapping,
    status_code: int,
    content: str,
) -> HttpResponse:
    """Convert API payload to a django response"""
    response = HttpResponse(content, status=status_code)
    for key, value in headers.items():
        response[key] = value
    return response
