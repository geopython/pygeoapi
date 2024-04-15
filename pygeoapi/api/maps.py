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


from copy import deepcopy
from http import HTTPStatus
import logging
from typing import Tuple

from pygeoapi.openapi import get_oas_30_parameters
from pygeoapi.plugin import load_plugin
from pygeoapi.provider.base import ProviderGenericError
from pygeoapi.util import (
    get_provider_by_type, to_json, filter_providers_by_type,
    filter_dict_by_key_value
)

from . import APIRequest, API, validate_datetime

LOGGER = logging.getLogger(__name__)

CONFORMANCE_CLASSES = [
    'http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/core'
]


def get_collection_map(api: API, request: APIRequest,
                       dataset, style=None) -> Tuple[dict, int, str]:
    """
    Returns a subset of a collection map

    :param request: A request object
    :param dataset: dataset name
    :param style: style name

    :returns: tuple of headers, status code, content
    """

    query_args = {
        'crs': 'CRS84'
    }

    format_ = request.format or 'png'
    headers = request.get_response_headers(**api.api_headers)
    LOGGER.debug('Processing query parameters')

    LOGGER.debug('Loading provider')
    try:
        collection_def = get_provider_by_type(
            api.config['resources'][dataset]['providers'], 'map')

        p = load_plugin('provider', collection_def)
    except KeyError:
        exception = {
            'code': 'InvalidParameterValue',
            'description': 'collection does not exist'
        }
        headers['Content-type'] = 'application/json'
        LOGGER.error(exception)
        return headers, HTTPStatus.NOT_FOUND, to_json(
            exception, api.pretty_print)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    query_args['format_'] = request.params.get('f', 'png')
    query_args['style'] = style
    query_args['crs'] = request.params.get('bbox-crs', 4326)
    query_args['transparent'] = request.params.get('transparent', True)

    try:
        query_args['width'] = int(request.params.get('width', 500))
        query_args['height'] = int(request.params.get('height', 300))
    except ValueError:
        exception = {
            'code': 'InvalidParameterValue',
            'description': 'invalid width/height'
        }
        headers['Content-type'] = 'application/json'
        LOGGER.error(exception)
        return headers, HTTPStatus.BAD_REQUEST, to_json(
            exception, api.pretty_print)

    LOGGER.debug('Processing bbox parameter')
    try:
        bbox = request.params.get('bbox').split(',')
        if len(bbox) != 4:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'bbox values should be minx,miny,maxx,maxy'
            }
            headers['Content-type'] = 'application/json'
            LOGGER.error(exception)
            return headers, HTTPStatus.BAD_REQUEST, to_json(
                exception, api.pretty_print)
    except AttributeError:
        bbox = api.config['resources'][dataset]['extents']['spatial']['bbox']  # noqa
    try:
        query_args['bbox'] = [float(c) for c in bbox]
    except ValueError:
        exception = {
            'code': 'InvalidParameterValue',
            'description': 'bbox values must be numbers'
        }
        headers['Content-type'] = 'application/json'
        LOGGER.error(exception)
        return headers, HTTPStatus.BAD_REQUEST, to_json(
            exception, api.pretty_print)

    LOGGER.debug('Processing datetime parameter')
    datetime_ = request.params.get('datetime')
    try:
        query_args['datetime_'] = validate_datetime(
            api.config['resources'][dataset]['extents'], datetime_)
    except ValueError as err:
        msg = str(err)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    LOGGER.debug('Generating map')
    try:
        data = p.query(**query_args)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    mt = collection_def['format']['name']

    if format_ == mt:
        headers['Content-Type'] = collection_def['format']['mimetype']
        return headers, HTTPStatus.OK, data
    elif format_ in [None, 'html']:
        headers['Content-Type'] = collection_def['format']['mimetype']
        return headers, HTTPStatus.OK, data
    else:
        exception = {
            'code': 'InvalidParameterValue',
            'description': 'invalid format parameter'
        }
        LOGGER.error(exception)
        return headers, HTTPStatus.BAD_REQUEST, to_json(
            data, api.pretty_print)


def get_collection_map_legend(api: API, request: APIRequest,
                              dataset, style=None) -> Tuple[dict, int, str]:
    """
    Returns a subset of a collection map legend

    :param request: A request object
    :param dataset: dataset name
    :param style: style name

    :returns: tuple of headers, status code, content
    """

    format_ = 'png'
    headers = request.get_response_headers(**api.api_headers)
    LOGGER.debug('Processing query parameters')

    LOGGER.debug('Loading provider')
    try:
        collection_def = get_provider_by_type(
            api.config['resources'][dataset]['providers'], 'map')

        p = load_plugin('provider', collection_def)
    except KeyError:
        exception = {
            'code': 'InvalidParameterValue',
            'description': 'collection does not exist'
        }
        LOGGER.error(exception)
        return headers, HTTPStatus.NOT_FOUND, to_json(
            exception, api.pretty_print)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    LOGGER.debug('Generating legend')
    try:
        data = p.get_legend(style, request.params.get('f', 'png'))
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    mt = collection_def['format']['name']

    if format_ == mt:
        headers['Content-Type'] = collection_def['format']['mimetype']
        return headers, HTTPStatus.OK, data
    else:
        exception = {
            'code': 'InvalidParameterValue',
            'description': 'invalid format parameter'
        }
        LOGGER.error(exception)
        return headers, HTTPStatus.BAD_REQUEST, to_json(
            data, api.pretty_print)


def get_oas_30(cfg: dict, locale: str) -> tuple[list[dict[str, str]], dict[str, dict]]:  # noqa
    """
    Get OpenAPI fragments

    :param cfg: `dict` of configuration
    :param locale: `str` of locale

    :returns: `tuple` of `list` of tag objects, and `dict` of path objects
    """

    from pygeoapi.openapi import OPENAPI_YAML, get_visible_collections

    LOGGER.debug('setting up maps endpoints')

    paths = {}

    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')

    parameters = get_oas_30_parameters(cfg, locale)
    for k, v in get_visible_collections(cfg).items():
        map_extension = filter_providers_by_type(
            collections[k]['providers'], 'map')

        if map_extension:
            mp = load_plugin('provider', map_extension)

            map_f = deepcopy(parameters['f'])
            map_f['schema']['enum'] = [map_extension['format']['name']]
            map_f['schema']['default'] = map_extension['format']['name']

            pth = f'/collections/{k}/map'
            paths[pth] = {
                'get': {
                    'summary': 'Get map',
                    'description': f"{v['description']} map",
                    'tags': [k],
                    'operationId': 'getMap',
                    'parameters': [
                        {'$ref': '#/components/parameters/bbox'},
                        {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/datetime"},  # noqa
                        {
                            'name': 'width',
                            'in': 'query',
                            'description': 'Response image width',
                            'required': False,
                            'schema': {
                                'type': 'integer',
                            },
                            'style': 'form',
                            'explode': False
                        },
                        {
                            'name': 'height',
                            'in': 'query',
                            'description': 'Response image height',
                            'required': False,
                            'schema': {
                                'type': 'integer',
                            },
                            'style': 'form',
                            'explode': False
                        },
                        {
                            'name': 'transparent',
                            'in': 'query',
                            'description': 'Background transparency of map (default=true).',  # noqa
                            'required': False,
                            'schema': {
                                'type': 'boolean',
                                'default': True,
                            },
                            'style': 'form',
                            'explode': False
                        },
                        {'$ref': '#/components/parameters/bbox-crs-epsg'},
                        map_f
                    ],
                    'responses': {
                        '200': {
                            'description': 'Response',
                            'content': {
                                'application/json': {}
                            }
                        },
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"},  # noqa
                    }
                }
            }
            if mp.time_field is not None:
                paths[pth]['get']['parameters'].append(
                    {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/datetime"})  # noqa

    return [{'name': 'maps'}], {'paths': paths}
