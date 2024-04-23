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
from pygeoapi.models.provider.base import (TilesMetadataFormat,
                                           TileMatrixSetEnum)
from pygeoapi.provider.base import (
    ProviderGenericError, ProviderTypeError
)

from pygeoapi.util import (
    get_provider_by_type, to_json, filter_dict_by_key_value,
    filter_providers_by_type, render_j2_template
)

from . import (
    APIRequest, API, FORMAT_TYPES, F_JSON, F_HTML, SYSTEM_LOCALE, F_JSONLD
)

LOGGER = logging.getLogger(__name__)

CONFORMANCE_CLASSES = [
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/mvt',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/tileset',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/tilesets-list',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/oas30',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/geodata-tilesets'
]


def get_collection_tiles(api: API, request: APIRequest,
                         dataset=None) -> Tuple[dict, int, str]:
    """
    Provide collection tiles

    :param request: A request object
    :param dataset: name of collection

    :returns: tuple of headers, status code, content
    """

    headers = request.get_response_headers(SYSTEM_LOCALE,
                                           **api.api_headers)
    if any([dataset is None,
            dataset not in api.config['resources'].keys()]):

        msg = 'Collection not found'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Creating collection tiles')
    LOGGER.debug('Loading provider')
    try:
        t = get_provider_by_type(
                api.config['resources'][dataset]['providers'], 'tile')
        p = load_plugin('provider', t)
    except (KeyError, ProviderTypeError):
        msg = 'Invalid collection tiles'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    tiles = {
        'links': [],
        'tilesets': []
    }

    tiles['links'].append({
        'type': FORMAT_TYPES[F_JSON],
        'rel': request.get_linkrel(F_JSON),
        'title': l10n.translate('This document as JSON', request.locale),
        'href': f'{api.get_collections_url()}/{dataset}/tiles?f={F_JSON}'
    })
    tiles['links'].append({
        'type': FORMAT_TYPES[F_JSONLD],
        'rel': request.get_linkrel(F_JSONLD),
        'title': l10n.translate('This document as RDF (JSON-LD)', request.locale),  # noqa
        'href': f'{api.get_collections_url()}/{dataset}/tiles?f={F_JSONLD}'
    })
    tiles['links'].append({
        'type': FORMAT_TYPES[F_HTML],
        'rel': request.get_linkrel(F_HTML),
        'title': l10n.translate('This document as HTML', request.locale),
        'href': f'{api.get_collections_url()}/{dataset}/tiles?f={F_HTML}'
    })

    tile_services = p.get_tiles_service(
        baseurl=api.base_url,
        servicepath=f'{api.get_collections_url()}/{dataset}/tiles/{{tileMatrixSetId}}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}?f={p.format_type}'  # noqa
    )

    for service in tile_services['links']:
        tiles['links'].append(service)

    tiling_schemes = p.get_tiling_schemes()

    for matrix in tiling_schemes:
        tile_matrix = {
            'title': dataset,
            'tileMatrixSetURI': matrix.tileMatrixSetURI,
            'crs': matrix.crs,
            'dataType': 'vector',
            'links': []
        }
        tile_matrix['links'].append({
            'type': FORMAT_TYPES[F_JSON],
            'rel': 'http://www.opengis.net/def/rel/ogc/1.0/tiling-scheme',
            'title': l10n.translate('TileMatrixSet definition in JSON', request.locale),  # noqa
            'href': f'{api.base_url}/TileMatrixSets/{matrix.tileMatrixSet}?f={F_JSON}'  # noqa
        })
        tile_matrix['links'].append({
            'type': FORMAT_TYPES[F_JSON],
            'rel': request.get_linkrel(F_JSON),
            'title': f'{dataset} - {matrix.tileMatrixSet} - {F_JSON}',
            'href': f'{api.get_collections_url()}/{dataset}/tiles/{matrix.tileMatrixSet}?f={F_JSON}'  # noqa
        })
        tile_matrix['links'].append({
            'type': FORMAT_TYPES[F_HTML],
            'rel': request.get_linkrel(F_HTML),
            'title': f'{dataset} - {matrix.tileMatrixSet} - {F_HTML}',
            'href': f'{api.get_collections_url()}/{dataset}/tiles/{matrix.tileMatrixSet}?f={F_HTML}'  # noqa
        })

        tiles['tilesets'].append(tile_matrix)

    if request.format == F_HTML:  # render
        tiles['id'] = dataset
        tiles['title'] = l10n.translate(
            api.config['resources'][dataset]['title'], SYSTEM_LOCALE)
        tiles['tilesets'] = [
            scheme.tileMatrixSet for scheme in p.get_tiling_schemes()]
        tiles['bounds'] = \
            api.config['resources'][dataset]['extents']['spatial']['bbox']
        tiles['minzoom'] = p.options['zoom']['min']
        tiles['maxzoom'] = p.options['zoom']['max']
        tiles['collections_path'] = api.get_collections_url()
        tiles['tile_type'] = p.tile_type

        content = render_j2_template(api.tpl_config,
                                     'collections/tiles/index.html', tiles,
                                     request.locale)

        return headers, HTTPStatus.OK, content

    return headers, HTTPStatus.OK, to_json(tiles, api.pretty_print)


# TODO: no test for this function?
def get_collection_tiles_data(
        api: API, request: APIRequest,
        dataset=None, matrix_id=None,
        z_idx=None, y_idx=None, x_idx=None) -> Tuple[dict, int, str]:
    """
    Get collection items tiles

    :param request: A request object
    :param dataset: dataset name
    :param matrix_id: matrix identifier
    :param z_idx: z index
    :param y_idx: y index
    :param x_idx: x index

    :returns: tuple of headers, status code, content
    """

    format_ = request.format
    if not format_:
        return api.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE,
                                           **api.api_headers)
    LOGGER.debug('Processing tiles')

    collections = filter_dict_by_key_value(api.config['resources'],
                                           'type', 'collection')

    if dataset not in collections.keys():
        msg = 'Collection not found'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Loading tile provider')
    try:
        t = get_provider_by_type(
            api.config['resources'][dataset]['providers'], 'tile')
        p = load_plugin('provider', t)

        format_ = p.format_type
        headers['Content-Type'] = format_

        LOGGER.debug(f'Fetching tileset id {matrix_id} and tile {z_idx}/{y_idx}/{x_idx}')  # noqa
        content = p.get_tiles(layer=p.get_layer(), tileset=matrix_id,
                              z=z_idx, y=y_idx, x=x_idx, format_=format_)
        if content is None:
            msg = 'identifier not found'
            return api.get_exception(
                HTTPStatus.NOT_FOUND, headers, format_, 'NotFound', msg)
        else:
            return headers, HTTPStatus.OK, content

    # @TODO: figure out if the spec requires to return json errors
    except KeyError:
        msg = 'Invalid collection tiles'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, format_,
            'InvalidParameterValue', msg)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)


# TODO: no test for this function?
def get_collection_tiles_metadata(
    api: API, request: APIRequest,
        dataset=None, matrix_id=None) -> Tuple[dict, int, str]:
    """
    Get collection items tiles

    :param request: A request object
    :param dataset: dataset name
    :param matrix_id: matrix identifier

    :returns: tuple of headers, status code, content
    """

    if not request.is_valid([TilesMetadataFormat.TILEJSON]):
        return api.get_format_exception(request)
    headers = request.get_response_headers(**api.api_headers)

    if any([dataset is None,
            dataset not in api.config['resources'].keys()]):

        msg = 'Collection not found'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Creating collection tiles')
    LOGGER.debug('Loading provider')
    try:
        t = get_provider_by_type(
            api.config['resources'][dataset]['providers'], 'tile')
        p = load_plugin('provider', t)
    except KeyError:
        msg = 'Invalid collection tiles'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    # Get provider language (if any)
    prv_locale = l10n.get_plugin_locale(t, request.raw_locale)

    # Set response language to requested provider locale
    # (if it supports language) and/or otherwise the requested pygeoapi
    # locale (or fallback default locale)
    l10n.set_response_language(headers, prv_locale, request.locale)

    tiles_metadata = p.get_metadata(
        dataset=dataset, server_url=api.base_url,
        layer=p.get_layer(), tileset=matrix_id,
        metadata_format=request._format, title=l10n.translate(
            api.config['resources'][dataset]['title'],
            request.locale),
        description=l10n.translate(
            api.config['resources'][dataset]['description'],
            request.locale),
        language=prv_locale)

    if request.format == F_HTML:  # render
        content = render_j2_template(api.tpl_config,
                                     'collections/tiles/metadata.html',
                                     tiles_metadata, request.locale)

        return headers, HTTPStatus.OK, content
    else:
        return headers, HTTPStatus.OK, tiles_metadata


def tilematrixsets(api: API,
                   request: APIRequest) -> Tuple[dict, int, str]:
    """
    Provide tileMatrixSets definition

    :param request: A request object

    :returns: tuple of headers, status code, content
    """

    headers = request.get_response_headers(**api.api_headers)

    # Retrieve available TileMatrixSets
    enums = [e.value for e in TileMatrixSetEnum]

    tms = {"tileMatrixSets": []}

    for e in enums:
        tms['tileMatrixSets'].append({
            "title": e.title,
            "id": e.tileMatrixSet,
            "uri": e.tileMatrixSetURI,
            "links": [
                {
                   "rel": "self",
                   "type": "text/html",
                   "title": f"The HTML representation of the {e.tileMatrixSet} tile matrix set", # noqa
                   "href": f"{api.base_url}/TileMatrixSets/{e.tileMatrixSet}?f=html" # noqa
                },
                {
                   "rel": "self",
                   "type": "application/json",
                   "title": f"The JSON representation of the {e.tileMatrixSet} tile matrix set", # noqa
                   "href": f"{api.base_url}/TileMatrixSets/{e.tileMatrixSet}?f=json" # noqa
                }
            ]
        })

    tms['links'] = [{
        "rel": "alternate",
        "type": "text/html",
        "title": l10n.translate('This document as HTML', request.locale),
        "href": f"{api.base_url}/tileMatrixSets?f=html"
    }, {
        "rel": "self",
        "type": "application/json",
        "title": l10n.translate('This document as JSON', request.locale),
        "href": f"{api.base_url}/tileMatrixSets?f=json"
    }]

    if request.format == F_HTML:  # render
        content = render_j2_template(api.tpl_config,
                                     'tilematrixsets/index.html',
                                     tms, request.locale)
        return headers, HTTPStatus.OK, content

    return headers, HTTPStatus.OK, to_json(tms, api.pretty_print)


def tilematrixset(api: API,
                  request: APIRequest,
                  tileMatrixSetId) -> Tuple[dict,
                                            int, str]:
    """
    Provide tile matrix definition

    :param request: A request object

    :returns: tuple of headers, status code, content
    """

    headers = request.get_response_headers(**api.api_headers)

    # Retrieve relevant TileMatrixSet
    enums = [e.value for e in TileMatrixSetEnum]
    enum = None

    try:
        for e in enums:
            if tileMatrixSetId == e.tileMatrixSet:
                enum = e
        if not enum:
            raise ValueError('could not find this tilematrixset')
    except ValueError as err:
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', str(err))

    tms = {
        "title": enum.tileMatrixSet,
        "crs": enum.crs,
        "id": enum.tileMatrixSet,
        "uri": enum.tileMatrixSetURI,
        "orderedAxes": enum.orderedAxes,
        "wellKnownScaleSet": enum.wellKnownScaleSet,
        "tileMatrices": enum.tileMatrices
    }

    if request.format == F_HTML:  # render
        content = render_j2_template(api.tpl_config,
                                     'tilematrixsets/tilematrixset.html',
                                     tms, request.locale)
        return headers, HTTPStatus.OK, content

    return headers, HTTPStatus.OK, to_json(tms, api.pretty_print)


def get_oas_30(cfg: dict, locale: str) -> tuple[list[dict[str, str]], dict[str, dict]]:  # noqa
    """
    Get OpenAPI fragments

    :param cfg: `dict` of configuration
    :param locale: `str` of locale

    :returns: `tuple` of `list` of tag objects, and `dict` of path objects
    """

    from pygeoapi.openapi import OPENAPI_YAML, get_visible_collections

    paths = {}

    LOGGER.debug('setting up tiles endpoints')
    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')

    for k, v in get_visible_collections(cfg).items():
        tile_extension = filter_providers_by_type(
            collections[k]['providers'], 'tile')

        if tile_extension:
            tp = load_plugin('provider', tile_extension)

            tiles_path = f'/collections/{k}/tiles'
            title = l10n.translate(v['title'], locale)
            description = l10n.translate(v['description'], locale)

            paths[tiles_path] = {
                'get': {
                    'summary': f'Fetch a {title} tiles description',
                    'description': description,
                    'tags': [k],
                    'operationId': f'describe{k.capitalize()}Tiles',
                    'parameters': [
                        {'$ref': '#/components/parameters/f'},
                        {'$ref': '#/components/parameters/lang'}
                    ],
                    'responses': {
                        '200': {'$ref': '#/components/responses/Tiles'},
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }
            }

            tiles_data_path = f'{tiles_path}/{{tileMatrixSetId}}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}'  # noqa

            paths[tiles_data_path] = {
                'get': {
                    'summary': f'Get a {title} tile',
                    'description': description,
                    'tags': [k],
                    'operationId': f'get{k.capitalize()}Tiles',
                    'parameters': [
                        {'$ref': f"{OPENAPI_YAML['oapit']}#/components/parameters/tileMatrixSetId"}, # noqa
                        {'$ref': f"{OPENAPI_YAML['oapit']}#/components/parameters/tileMatrix"},  # noqa
                        {'$ref': f"{OPENAPI_YAML['oapit']}#/components/parameters/tileRow"},  # noqa
                        {'$ref': f"{OPENAPI_YAML['oapit']}#/components/parameters/tileCol"},  # noqa
                        {
                            'name': 'f',
                            'in': 'query',
                            'description': 'The optional f parameter indicates the output format which the server shall provide as part of the response document.',  # noqa
                            'required': False,
                            'schema': {
                                'type': 'string',
                                'enum': [tp.format_type],
                                'default': tp.format_type
                            },
                            'style': 'form',
                            'explode': False
                        }
                    ],
                    'responses': {
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }
            }
            mimetype = tile_extension['format']['mimetype']
            paths[tiles_data_path]['get']['responses']['200'] = {
                'description': 'successful operation',
                'content': {
                    mimetype: {
                        'schema': {
                            'type': 'string',
                            'format': 'binary'
                        }
                    }
                }
            }

    return [{'name': 'tiles'}], {'paths': paths}
