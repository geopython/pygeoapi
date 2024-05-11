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


from http import HTTPStatus
import logging
from typing import Tuple

from shapely.errors import WKTReadingError
from shapely.wkt import loads as shapely_loads

from pygeoapi.plugin import load_plugin, PLUGINS
from pygeoapi.provider.base import ProviderGenericError
from pygeoapi.util import (
    filter_providers_by_type, get_provider_by_type, render_j2_template,
    to_json, filter_dict_by_key_value
)

from . import APIRequest, API, F_HTML, validate_datetime, validate_bbox

LOGGER = logging.getLogger(__name__)

CONFORMANCE_CLASSES = [
    'http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/core'
]


def get_collection_edr_query(api: API, request: APIRequest,
                             dataset, instance, query_type,
                             location_id=None) -> Tuple[dict, int, str]:
    """
    Queries collection EDR

    :param request: APIRequest instance with query params
    :param dataset: dataset name
    :param instance: instance name
    :param query_type: EDR query type
    :param location_id: location id of a /location/<location_id> query

    :returns: tuple of headers, status code, content
    """

    if not request.is_valid(PLUGINS['formatter'].keys()):
        return api.get_format_exception(request)
    headers = request.get_response_headers(api.default_locale,
                                           **api.api_headers)
    collections = filter_dict_by_key_value(api.config['resources'],
                                           'type', 'collection')

    if dataset not in collections.keys():
        msg = 'Collection not found'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Processing query parameters')

    LOGGER.debug('Processing datetime parameter')
    datetime_ = request.params.get('datetime')
    try:
        datetime_ = validate_datetime(collections[dataset]['extents'],
                                      datetime_)
    except ValueError as err:
        msg = str(err)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    LOGGER.debug('Processing parameter-name parameter')
    parameternames = request.params.get('parameter-name') or []
    if isinstance(parameternames, str):
        parameternames = parameternames.split(',')

    bbox = None
    if query_type in ['cube', 'locations']:
        LOGGER.debug('Processing cube bbox')
        try:
            bbox = validate_bbox(request.params.get('bbox'))
            if not bbox and query_type == 'cube':
                raise ValueError('bbox parameter required by cube queries')
        except ValueError as err:
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', str(err))

    LOGGER.debug('Processing coords parameter')
    wkt = request.params.get('coords')

    if wkt:
        try:
            wkt = shapely_loads(wkt)
        except WKTReadingError:
            msg = 'invalid coords parameter'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    elif query_type not in ['cube', 'locations']:
        msg = 'missing coords parameter'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    within = within_units = None
    if query_type == 'radius':
        LOGGER.debug('Processing within / within-units parameters')
        within = request.params.get('within')
        within_units = request.params.get('within-units')

    LOGGER.debug('Processing z parameter')
    z = request.params.get('z')

    LOGGER.debug('Loading provider')
    try:
        p = load_plugin('provider', get_provider_by_type(
            collections[dataset]['providers'], 'edr'))
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    if instance is not None and not p.get_instance(instance):
        msg = 'Invalid instance identifier'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers,
            request.format, 'InvalidParameterValue', msg)

    if query_type not in p.get_query_types():
        msg = 'Unsupported query type'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    if parameternames and not any((fld in parameternames)
                                  for fld in p.get_fields().keys()):
        msg = 'Invalid parameter-name'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    query_args = dict(
        query_type=query_type,
        instance=instance,
        format_=request.format,
        datetime_=datetime_,
        select_properties=parameternames,
        wkt=wkt,
        z=z,
        bbox=bbox,
        within=within,
        within_units=within_units,
        limit=int(api.config['server']['limit']),
        location_id=location_id,
    )

    try:
        data = p.query(**query_args)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    if request.format == F_HTML:  # render
        content = render_j2_template(api.tpl_config,
                                     'collections/edr/query.html', data,
                                     api.default_locale)
    else:
        content = to_json(data, api.pretty_print)

    return headers, HTTPStatus.OK, content


def get_oas_30(cfg: dict, locale: str) -> tuple[list[dict[str, str]], dict[str, dict]]:  # noqa
    """
    Get OpenAPI fragments

    :param cfg: `dict` of configuration
    :param locale: `str` of locale

    :returns: `tuple` of `list` of tag objects, and `dict` of path objects
    """

    from pygeoapi.openapi import OPENAPI_YAML, get_visible_collections

    LOGGER.debug('setting up edr endpoints')

    paths = {}

    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')

    for k, v in get_visible_collections(cfg).items():
        edr_extension = filter_providers_by_type(
            collections[k]['providers'], 'edr')

        if edr_extension:
            collection_name_path = f'/collections/{k}'

            ep = load_plugin('provider', edr_extension)

            edr_query_endpoints = []

            for qt in [qt for qt in ep.get_query_types() if qt != 'locations']:
                edr_query_endpoints.append({
                    'path': f'{collection_name_path}/{qt}',
                    'qt': qt,
                    'op_id': f'query{qt.capitalize()}{k.capitalize()}'
                })
                if ep.instances:
                    edr_query_endpoints.append({
                        'path': f'{collection_name_path}/instances/{{instanceId}}/{qt}',  # noqa
                        'qt': qt,
                        'op_id': f'query{qt.capitalize()}Instance{k.capitalize()}'  # noqa
                    })

            for eqe in edr_query_endpoints:
                if eqe['qt'] == 'cube':
                    spatial_parameter = 'bbox'
                else:
                    spatial_parameter = f"{eqe['qt']}Coords"
                paths[eqe['path']] = {
                    'get': {
                        'summary': f"query {v['description']} by {eqe['qt']}",
                        'description': v['description'],
                        'tags': [k],
                        'operationId': eqe['op_id'],
                        'parameters': [
                            {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/{spatial_parameter}.yaml"},  # noqa
                            {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/datetime"},  # noqa
                            {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/parameter-name.yaml"},  # noqa
                            {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/z.yaml"},  # noqa
                            {'$ref': '#/components/parameters/f'}
                        ],
                        'responses': {
                            '200': {
                                'description': 'Response',
                                'content': {
                                    'application/prs.coverage+json': {
                                        'schema': {
                                            '$ref': f"{OPENAPI_YAML['oaedr']}/schemas/coverageJSON.yaml"  # noqa
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            if 'locations' in ep.get_query_types():
                paths[f'{collection_name_path}/locations'] = {
                    'get': {
                        'summary': f"Get pre-defined locations of {v['description']}",  # noqa
                        'description': v['description'],
                        'tags': [k],
                        'operationId': f'queryLOCATIONS{k.capitalize()}',
                        'parameters': [
                            {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/bbox.yaml"},  # noqa
                            {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/datetime"},  # noqa
                            {'$ref': '#/components/parameters/f'}
                        ],
                        'responses': {
                            '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/Features"},  # noqa
                            '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                            '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                        }
                    }
                }
                paths[f'{collection_name_path}/locations/{{locId}}'] = {
                    'get': {
                        'summary': f"query {v['description']} by location",
                        'description': v['description'],
                        'tags': [k],
                        'operationId': f'queryLOCATIONSBYID{k.capitalize()}',
                        'parameters': [
                            {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/{spatial_parameter}.yaml"},  # noqa
                            {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/locationId.yaml"},  # noqa
                            {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/datetime"},  # noqa
                            {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/parameter-name.yaml"},  # noqa
                            {'$ref': f"{OPENAPI_YAML['oaedr']}/parameters/z.yaml"},  # noqa
                            {'$ref': '#/components/parameters/f'}
                        ],
                        'responses': {
                            '200': {
                                'description': 'Response',
                                'content': {
                                    'application/prs.coverage+json': {
                                        'schema': {
                                            '$ref': f"{OPENAPI_YAML['oaedr']}/schemas/coverageJSON.yaml"  # noqa
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

    return [{'name': 'edr'}], {'paths': paths}
