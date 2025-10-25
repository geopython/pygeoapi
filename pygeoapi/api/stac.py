# =================================================================

# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Sander Schaminee <sander.schaminee@geocat.net>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#          Bernhard Mallinger <bernhard.mallinger@eox.at>
#
# Copyright (c) 2025 Tom Kralidis
# Copyright (c) 2025 Francesco Bartoli
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
import json
import logging
from typing import Any, Tuple, Union
from urllib.parse import urlencode

from shapely import from_geojson

from pygeoapi import l10n
from pygeoapi import api as ogc_api
from pygeoapi.api import itemtypes as itemtypes_api
from pygeoapi.plugin import load_plugin

from pygeoapi.provider.base import (
    ProviderConnectionError, ProviderNotFoundError, ProviderTypeError
)
from pygeoapi.util import (
    filter_dict_by_key_value, get_current_datetime, get_provider_by_type,
    render_j2_template, to_json
)

from . import APIRequest, API, FORMAT_TYPES, F_JSON, F_HTML


LOGGER = logging.getLogger(__name__)


CONFORMANCE_CLASSES = []


# TODO: no tests for this?
def get_stac_root(api: API, request: APIRequest) -> Tuple[dict, int, str]:
    """
    Provide STAC root page

    :param request: APIRequest instance with query params

    :returns: tuple of headers, status code, content
    """
    headers = request.get_response_headers(**api.api_headers)

    id_ = 'pygeoapi-stac'
    stac_version = '1.0.0-rc.2'
    stac_url = f'{api.base_url}/stac'

    content = {
        'id': id_,
        'type': 'Catalog',
        'stac_version': stac_version,
        'title': l10n.translate(
            api.config['metadata']['identification']['title'],
            request.locale),
        'description': l10n.translate(
            api.config['metadata']['identification']['description'],
            request.locale),
        'links': []
    }

    stac_collections = filter_dict_by_key_value(api.config['resources'],
                                                'type', 'stac-collection')

    for key, value in stac_collections.items():
        try:
            _ = load_plugin('provider', get_provider_by_type(
                            value['providers'], 'stac'))
        except ProviderTypeError:
            LOGGER.debug('Not a STAC-based provider; skipping')
            continue

        content['links'].append({
            'rel': 'child',
            'href': f'{stac_url}/{key}?f={F_JSON}',
            'type': FORMAT_TYPES[F_JSON],
            'title': key,
            'description': value['description']
        })
        content['links'].append({
            'rel': 'child',
            'href': f'{stac_url}/{key}',
            'type': FORMAT_TYPES[F_HTML],
            'title': key,
            'description': value['description']
        })

    if request.format == F_HTML:  # render
        content = render_j2_template(
            api.tpl_config, api.config['server']['templates'],
            'stac/collection.html', content, request.locale)

        return headers, HTTPStatus.OK, content

    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


# TODO: no tests for this?
def get_stac_path(api: API, request: APIRequest,
                  path: str) -> Tuple[dict, int, str]:
    """
    Provide STAC resource path

    :param request: APIRequest instance with query params

    :returns: tuple of headers, status code, content
    """
    headers = request.get_response_headers(**api.api_headers)

    dataset = None
    LOGGER.debug(f'Path: {path}')
    dir_tokens = path.split('/')
    if dir_tokens:
        dataset = dir_tokens[0]

    stac_collections = filter_dict_by_key_value(api.config['resources'],
                                                'type', 'stac-collection')

    if dataset not in stac_collections:
        msg = 'Collection not found'
        return api.get_exception(HTTPStatus.NOT_FOUND, headers,
                                 request.format, 'NotFound', msg)

    LOGGER.debug('Loading provider')
    try:
        p = load_plugin('provider', get_provider_by_type(
            stac_collections[dataset]['providers'], 'stac'))
    except ProviderConnectionError:
        msg = 'connection error (check logs)'
        return api.get_exception(
            HTTPStatus.INTERNAL_SERVER_ERROR, headers,
            request.format, 'NoApplicableCode', msg)

    id_ = f'{dataset}-stac'
    stac_version = '1.0.0-rc.2'

    content = {
        'id': id_,
        'type': 'Catalog',
        'stac_version': stac_version,
        'description': l10n.translate(
            stac_collections[dataset]['description'], request.locale),
        'links': []
    }
    try:
        stac_data = p.get_data_path(
            f'{api.base_url}/stac',
            path,
            path.replace(dataset, '', 1)
        )
    except ProviderNotFoundError:
        msg = 'resource not found'
        return api.get_exception(HTTPStatus.NOT_FOUND, headers,
                                 request.format, 'NotFound', msg)
    except Exception:
        msg = 'data query error'
        return api.get_exception(
            HTTPStatus.INTERNAL_SERVER_ERROR, headers,
            request.format, 'NoApplicableCode', msg)

    if isinstance(stac_data, dict):
        content.update(stac_data)
        content['links'].extend(
            stac_collections[dataset].get('links', []))

        if request.format == F_HTML:  # render
            content['path'] = path
            if 'assets' in content:  # item view
                if content['type'] == 'Collection':
                    content = render_j2_template(
                        api.tpl_config, api.config['server']['templates'],
                        'stac/collection_base.html',
                        content, request.locale)
                elif content['type'] == 'Feature':
                    content = render_j2_template(
                        api.tpl_config, api.config['server']['templates'],
                        'stac/item.html', content, request.locale)
                else:
                    msg = f'Unknown STAC type {content.type}'
                    return api.get_exception(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        headers,
                        request.format,
                        'NoApplicableCode',
                        msg)
            else:
                content = render_j2_template(
                        api.tpl_config, api.config['server']['templates'],
                        'stac/catalog.html', content, request.locale)

            return headers, HTTPStatus.OK, content

        return headers, HTTPStatus.OK, to_json(content, api.pretty_print)

    else:  # send back file
        headers.pop('Content-Type', None)
        return headers, HTTPStatus.OK, stac_data


def landing_page(api: API,
                 request: APIRequest) -> Tuple[dict, int, str]:
    """
    Provide API landing page

    :param request: A request object

    :returns: tuple of headers, status code, content
    """

    request._format = F_JSON

    headers, status, content = ogc_api.landing_page(api, request)

    content = json.loads(content)

    content['id'] = 'pygeoapi-catalogue'
    content['stac_version'] = '1.0.0'
    content['conformsTo'] = [
        'https://api.stacspec.org/v1.0.0/core',
        'https://api.stacspec.org/v1.0.0/item-search',
        'https://api.stacspec.org/v1.0.0/item-search#sort'
    ]
    content['type'] = 'Catalog'

    content['links'] = [{
        'rel': request.get_linkrel(F_JSON),
        'type': FORMAT_TYPES[F_JSON],
        'title': l10n.translate('This document as JSON', request.locale),
        'href': f"{api.base_url}/stac-api?f={F_JSON}"
    }, {
        'rel': 'root',
        'type': FORMAT_TYPES[F_JSON],
        'title': l10n.translate('This document as JSON', request.locale),
        'href': f"{api.base_url}/stac-api?f={F_JSON}"
    }, {
        'rel': 'service-desc',
        'type': 'application/vnd.oai.openapi+json;version=3.0',
        'title': l10n.translate('The OpenAPI definition as JSON', request.locale),  # noqa
        'href': f"{api.base_url}/openapi"
    }, {
        'rel': 'service-doc',
        'type': FORMAT_TYPES[F_HTML],
        'title': l10n.translate('The OpenAPI definition as HTML', request.locale),  # noqa
        'href': f"{api.base_url}/openapi?f={F_HTML}",
        'hreflang': api.default_locale
    }, {
        'rel': 'search',
        'type': FORMAT_TYPES[F_JSON],
        'title': l10n.translate('STAC API search', request.locale),
        'href': f"{api.base_url}/stac-api//search?f={F_JSON}"
    }]

    return headers, status, to_json(content, api.pretty_print)


def search(api: API, request: Union[APIRequest, Any]) -> Tuple[dict, int, str]:
    """
    STAC API Queries stac-collection

    :param request: A request object
    :param dataset: dataset name

    :returns: tuple of headers, status code, content
    """

    stac_api_collections = {}

    request._format = F_JSON

    headers = request.get_response_headers(**api.api_headers)

    LOGGER.debug('Checking for STAC collections')
    collections = filter_dict_by_key_value(api.config['resources'],
                                           'type', 'stac-collection')

    if not collections:
        return api.get_exception(
            HTTPStatus.NOT_IMPLEMENTED, headers, F_JSON, 'NotImplemented',
            'No configured STAC searchable collection')

    LOGGER.debug('Checking for STAC collections with features or records')
    for key, value in collections.items():
        found_collection = False
        for fr in ['feature', 'record']:
            try:
                _ = get_provider_by_type(value['providers'], fr)
                found_collection = True
                break
            except ProviderTypeError:
                pass

        if found_collection:
            stac_api_collections[key] = value

    if not stac_api_collections:
        msg = 'No STAC API collections configured'
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers,
                                 request.format, 'NotApplicable', msg)

    if request.data:
        LOGGER.debug('Intercepting STAC POST request into query args')
        request_data = json.loads(request.data)
        request_params = deepcopy(dict(request.params))

        for qp in ['bbox', 'datetime', 'limit', 'offset']:
            if qp in request_data:
                if qp == 'bbox' and isinstance(request_data[qp], list):
                    request_params[qp] = ','.join(str(b) for b in request_data[qp])  # noqa
                else:
                    request_params[qp] = request_data[qp]

        request._args = request_params
        request._data = None

    stac_api_response = {
        'type': 'FeatureCollection',
        'features': [],
        'numberMatched': 0,
        'links': []
    }

    for key, value in stac_api_collections.items():
        api.config['resources'][key]['type'] = 'collection'
        headers, status, content = itemtypes_api.get_collection_items(
            api, request, key)
        api.config['resources'][key]['type'] = 'stac-collection'

        if status != HTTPStatus.OK:
            return headers, status, to_json(content, api.pretty_print)

        content = json.loads(content)
        stac_api_response['numberMatched'] += content.get('numberMatched', 0)

        if len(content.get('features', [])) > 0:
            for feature in content['features']:
                if 'stac_version' not in feature:
                    feature['stac_version'] = '1.0.0'
                feature['properties'].update(get_temporal(feature))
                stac_api_response['features'].append(feature)

                if feature.get('geometry') is not None and 'bbox' not in feature:  # noqa
                    geom = from_geojson(json.dumps(feature['geometry']))
                    feature['bbox'] = geom.bounds

                for la in ['links', 'assets']:
                    if feature.get(la) is None:
                        feature[la] = []

    stac_api_response['numberReturned'] = len(stac_api_response['features'])

    stac_api_response['links'].append({
        'rel': 'root',
        'type': FORMAT_TYPES[F_JSON],
        'title': l10n.translate('STAC API landing page', request.locale),
        'href': f"{api.base_url}/stac-api?f={F_JSON}"
    })

    LOGGER.debug('Generating paging links')

    next_link = False
    prev_link = False
    request_params = deepcopy(dict(request._args))
    limit = itemtypes_api.evaluate_limit(
        request_params.get('limit'),
        api.config['server'].get('limits', {}), {})
    offset = int(request_params.get('offset', 0))

    if stac_api_response.get('numberMatched', -1) > (limit + offset):
        next_link = True
    elif len(stac_api_response['features']) == limit:
        next_link = True

    if offset > 0:
        prev_link = True

    if prev_link:
        request_params['offset'] = max(0, offset - limit)
        if request_params['offset'] == 0:
            request_params.pop('offset')

        request_params_qs = urlencode(request_params)

        stac_api_response['links'].append({
            'rel': 'prev',
            'type': FORMAT_TYPES[F_JSON],
            'title': l10n.translate('Items (prev)', request.locale),
            'href': f"{api.base_url}/stac-api/search?{request_params_qs}"
        })

    if next_link:
        request_params['offset'] = offset + limit
        request_params_qs = urlencode(request_params)

        stac_api_response['links'].append({
            'rel': 'next',
            'type': FORMAT_TYPES[F_JSON],
            'title': l10n.translate('Items (next)', request.locale),
            'href': f"{api.base_url}/stac-api/search?{request_params_qs}"
        })

    return headers, HTTPStatus.OK, to_json(stac_api_response, api.pretty_print)


def get_oas_30(cfg: dict, locale: str) -> tuple[list[dict[str, str]], dict[str, dict]]:  # noqa
    """
    Get OpenAPI fragments

    :param cfg: `dict` of configuration
    :param locale: `str` of locale

    :returns: `tuple` of `list` of tag objects, and `dict` of path objects
    """

    LOGGER.debug('setting up STAC')
    stac_collections = filter_dict_by_key_value(cfg['resources'],
                                                'type', 'stac-collection')
    paths = {}
    if stac_collections:
        paths['/stac/catalog'] = {
            'get': {
                'summary': 'SpatioTemporal Asset Catalog',
                'description': 'SpatioTemporal Asset Catalog',
                'tags': ['stac'],
                'operationId': 'getStacCatalog',
                'parameters': [],
                'responses': {
                    '200': {'$ref': '#/components/responses/200'},
                    'default': {'$ref': '#/components/responses/default'}
                }
            }
        }
    return [{'name': 'stac'}], {'paths': paths}


def get_temporal(feature: dict) -> dict:
    """
    Helper function to try and derive a useful temporal
    definition on a non-STAC item

    :param feature: `dict` of GeoJSON feature

    :returns: `dict` of `datetime` or `start_datetime` and `end_datetime`
    """

    value = {}

    datetime_ = feature['properties'].get('datetime')
    start_datetime = feature['properties'].get('start_datetime')
    end_datetime = feature['properties'].get('end_datetime')

    if datetime_ is None and None not in [start_datetime, end_datetime]:
        LOGGER.debug('Temporal range partially exists')
    elif datetime_ is not None:
        LOGGER.debug('Temporal instant exists')

    LOGGER.debug('Attempting to derive temporal from GeoJSON feature')
    LOGGER.debug(feature)
    if feature.get('time') is not None:
        if feature['time'].get('timestamp') is not None:
            value['datetime'] = feature['time']['timestamp']
        if feature['time'].get('interval') is not None:
            value['start_datetime'] = feature['time']['interval'][0]
            value['end_datetime'] = feature['time']['interval'][1]

    if feature['properties'].get('created') is not None:
        value['datetime'] = feature['properties']['created']

    if not value:
        value['datetime'] = get_current_datetime()

    return value
