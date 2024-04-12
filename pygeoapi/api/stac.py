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

from pygeoapi import l10n
from pygeoapi.plugin import load_plugin

from pygeoapi.provider.base import (
    ProviderConnectionError, ProviderNotFoundError
)
from pygeoapi.util import (
    get_provider_by_type, to_json, filter_dict_by_key_value,
    render_j2_template
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
        content['links'].append({
            'rel': 'child',
            'href': f'{stac_url}/{key}?f={F_JSON}',
            'type': FORMAT_TYPES[F_JSON]
        })
        content['links'].append({
            'rel': 'child',
            'href': f'{stac_url}/{key}',
            'type': FORMAT_TYPES[F_HTML]
        })

    if request.format == F_HTML:  # render
        content = render_j2_template(api.tpl_config,
                                     'stac/collection.html',
                                     content, request.locale)
        return headers, HTTPStatus.OK, content

    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


# TODO: no tests for this?
def get_stac_path(api: API, request: APIRequest,
                  path) -> Tuple[dict, int, str]:
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
                        api.tpl_config,
                        'stac/collection_base.html',
                        content,
                        request.locale
                    )
                elif content['type'] == 'Feature':
                    content = render_j2_template(
                        api.tpl_config,
                        'stac/item.html',
                        content,
                        request.locale
                    )
                else:
                    msg = f'Unknown STAC type {content.type}'
                    return api.get_exception(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        headers,
                        request.format,
                        'NoApplicableCode',
                        msg)
            else:
                content = render_j2_template(api.tpl_config,
                                             'stac/catalog.html',
                                             content, request.locale)

            return headers, HTTPStatus.OK, content

        return headers, HTTPStatus.OK, to_json(content, api.pretty_print)

    else:  # send back file
        headers.pop('Content-Type', None)
        return headers, HTTPStatus.OK, stac_data


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
        paths['/stac'] = {
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
