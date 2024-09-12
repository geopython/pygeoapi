# =================================================================

# Authors: Joana Simoes <jo@doublebyte.net>
#
# Copyright (c) 2024 Joana Simoes
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

from pygeoapi.util import to_json

from . import APIRequest, API, F_JSON, SYSTEM_LOCALE

LOGGER = logging.getLogger(__name__)

CONFORMANCE_CLASSES = [
    'http://www.opengis.net/spec/ogcapi-styles-1/0.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-styles-1/0.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-styles-1/0.0/conf/mapbox-style'
]


def get_styles(api: API, request: APIRequest) -> Tuple[dict, int, str]:
    """
    Fetches the set of styles available. 
    For each style it returns the id, a title, links to the stylesheet of the style in each supported encoding, 
    and the link to the metadata.

    :param request: A request object

    :returns: tuple of headers, status code, content
    """

    format_ = request.format or F_JSON

    # Force response content type and language (en-US only) headers
    headers = request.get_response_headers(SYSTEM_LOCALE, **api.api_headers)

    # TODO: implement this

    data = '{"styles": [{"title": "night", "id": "night"}]}'

    if format_ == F_JSON:
        headers['Content-Type'] = 'application/json'
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

    from pygeoapi.openapi import OPENAPI_YAML

    paths = {}

    paths['/styles'] = {
        'get': {
            'summary': 'lists the available styles',
            'description': 'This operation fetches the set of styles available.',
            'tags': ['Discover and fetch styles'],
            'operationId': 'getStyles',
            'externalDocs': { 
                'description': 'The specification that describes this operation: OGC API - Styles (DRAFT)',
                 'url': 'https://docs.ogc.org/DRAFTS/20-009.html'
                },
            'parameters': [
                {'$ref': '#/components/parameters/access_token'},
                {'$ref': '#/components/parameters/fStyles'}
            ],
            'responses': {
                '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/Features"},  # noqa
                '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                # TODO: add 406
                '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
            }
        }
    }

    return [{'name': 'styles'}], {'paths': paths}