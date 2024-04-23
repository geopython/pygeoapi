# =================================================================

# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Sander Schaminee <sander.schaminee@geocat.net>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#          Bernhard Mallinger <bernhard.mallinger@eox.at>
#
# Copyright (c) 2024 Tom Kralidis
# Copyright (c) 2022 Francesco Bartoli
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
# Copyright (c) 2023 Ricardo Garcia Silva
# Copyright (c) 2024 Bernhard Mallinger
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


import logging
from http import HTTPStatus
from typing import Tuple

from pygeoapi import l10n
from pygeoapi.plugin import load_plugin
from pygeoapi.provider.base import ProviderGenericError, ProviderTypeError
from pygeoapi.util import (
    filter_dict_by_key_value, get_provider_by_type, to_json
)

from . import (
    APIRequest, API, F_JSON, SYSTEM_LOCALE, validate_bbox, validate_datetime,
    validate_subset
)

LOGGER = logging.getLogger(__name__)

CONFORMANCE_CLASSES = [
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/oas30',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/geodata-coverage',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-subset',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-rangesubset',  # noqa
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-bbox',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-datetime'
]


def get_collection_coverage(
        api: API, request: APIRequest, dataset) -> Tuple[dict, int, str]:
    """
    Returns a subset of a collection coverage

    :param request: A request object
    :param dataset: dataset name

    :returns: tuple of headers, status code, content
    """

    query_args = {}
    format_ = request.format or F_JSON

    # Force response content type and language (en-US only) headers
    headers = request.get_response_headers(SYSTEM_LOCALE, **api.api_headers)

    LOGGER.debug('Loading provider')
    try:
        collection_def = get_provider_by_type(
            api.config['resources'][dataset]['providers'], 'coverage')

        p = load_plugin('provider', collection_def)
    except KeyError:
        msg = 'collection does not exist'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, format_,
            'InvalidParameterValue', msg)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    LOGGER.debug('Processing bbox parameter')

    bbox = request.params.get('bbox')

    if bbox is None:
        bbox = []
    else:
        try:
            bbox = validate_bbox(bbox)
        except ValueError as err:
            msg = str(err)
            return api.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, format_,
                'InvalidParameterValue', msg)

    query_args['bbox'] = bbox

    LOGGER.debug('Processing bbox-crs parameter')

    bbox_crs = request.params.get('bbox-crs')
    if bbox_crs is not None:
        query_args['bbox_crs'] = bbox_crs

    LOGGER.debug('Processing datetime parameter')

    datetime_ = request.params.get('datetime')

    try:
        datetime_ = validate_datetime(
            api.config['resources'][dataset]['extents'], datetime_)
    except ValueError as err:
        msg = str(err)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, format_,
            'InvalidParameterValue', msg)

    query_args['datetime_'] = datetime_
    query_args['format_'] = format_

    properties = request.params.get('properties')
    if properties:
        LOGGER.debug('Processing properties parameter')
        query_args['properties'] = [rs for
                                    rs in properties.split(',') if rs]
        LOGGER.debug(f"Fields: {query_args['properties']}")

        for a in query_args['properties']:
            if a not in p.fields:
                msg = 'Invalid field specified'
                return api.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, format_,
                    'InvalidParameterValue', msg)

    if 'subset' in request.params:
        LOGGER.debug('Processing subset parameter')
        try:
            subsets = validate_subset(request.params['subset'] or '')
        except (AttributeError, ValueError) as err:
            msg = f'Invalid subset: {err}'
            return api.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, format_,
                    'InvalidParameterValue', msg)

        if not set(subsets.keys()).issubset(p.axes):
            msg = 'Invalid axis name'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, format_,
                'InvalidParameterValue', msg)

        query_args['subsets'] = subsets
        LOGGER.debug(f"Subsets: {query_args['subsets']}")

    LOGGER.debug('Querying coverage')
    try:
        data = p.query(**query_args)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    mt = collection_def['format']['name']
    if format_ == mt:  # native format
        if p.filename is not None:
            cd = f'attachment; filename="{p.filename}"'
            headers['Content-Disposition'] = cd

        headers['Content-Type'] = collection_def['format']['mimetype']
        return headers, HTTPStatus.OK, data
    elif format_ == F_JSON:
        headers['Content-Type'] = 'application/prs.coverage+json'
        return headers, HTTPStatus.OK, to_json(data, api.pretty_print)
    else:
        return api.get_format_exception(request)


def get_oas_30(cfg: dict, locale: str) -> tuple[list[dict[str, str]], dict[str, dict]]:  # noqa
    """
    Get OpenAPI fragments

    :param cfg: `dict` of configuration
    :param locale: `str` of locale

    :returns: `tuple` of `list` of tag objects, and `dict` of path objects
    """

    from pygeoapi.openapi import OPENAPI_YAML, get_visible_collections

    paths = {}

    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')

    for k, v in get_visible_collections(cfg).items():
        try:
            load_plugin('provider', get_provider_by_type(
                        collections[k]['providers'], 'coverage'))
        except ProviderTypeError:
            LOGGER.debug('collection is not coverage based')
            continue

        coverage_path = f'/collections/{k}/coverage'
        title = l10n.translate(v['title'], locale)
        description = l10n.translate(v['description'], locale)

        paths[coverage_path] = {
            'get': {
                'summary': f'Get {title} coverage',
                'description': description,
                'tags': [k],
                'operationId': f'get{k.capitalize()}Coverage',
                'parameters': [
                    {'$ref': '#/components/parameters/lang'},
                    {'$ref': '#/components/parameters/f'},
                    {'$ref': '#/components/parameters/bbox'},
                    {'$ref': '#/components/parameters/bbox-crs'}
                ],
                'responses': {
                    '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/Features"},  # noqa
                    '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                    '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                    '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                }
            }
        }

    return [{'name': 'coverages'}], {'paths': paths}
