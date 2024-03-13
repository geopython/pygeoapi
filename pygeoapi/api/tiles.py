# =================================================================

# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Sander Schaminee <sander.schaminee@geocat.net>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#          Bernhard Mallinger <bernhard.mallinger@eox.at>
#
# Copyright (c) 2023 Tom Kralidis
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

from pygeoapi.provider.base import (
    ProviderConnectionError, ProviderNotFoundError,
)
from pygeoapi.util import (
    get_provider_by_type, to_json, filter_dict_by_key_value,
    render_j2_template,
)

from . import APIRequest, API, FORMAT_TYPES, F_JSON, F_HTML


LOGGER = logging.getLogger(__name__)


@gzip
@pre_process
@jsonldify
def get_collection_tiles(self, request: Union[APIRequest, Any],
                         dataset=None) -> Tuple[dict, int, str]:
    """
    Provide collection tiles

    :param request: A request object
    :param dataset: name of collection

    :returns: tuple of headers, status code, content
    """

    if not request.is_valid():
        return self.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE,
                                           **self.api_headers)
    if any([dataset is None,
            dataset not in self.config['resources'].keys()]):

        msg = 'Collection not found'
        return self.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Creating collection tiles')
    LOGGER.debug('Loading provider')
    try:
        t = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'tile')
        p = load_plugin('provider', t)
    except (KeyError, ProviderTypeError):
        msg = 'Invalid collection tiles'
        return self.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)
    except ProviderGenericError as err:
        LOGGER.error(err)
        return self.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    tiles = {
        'links': [],
        'tilesets': []
    }

    tiles['links'].append({
        'type': FORMAT_TYPES[F_JSON],
        'rel': request.get_linkrel(F_JSON),
        'title': 'This document as JSON',
        'href': f'{self.get_collections_url()}/{dataset}/tiles?f={F_JSON}'
    })
    tiles['links'].append({
        'type': FORMAT_TYPES[F_JSONLD],
        'rel': request.get_linkrel(F_JSONLD),
        'title': 'This document as RDF (JSON-LD)',
        'href': f'{self.get_collections_url()}/{dataset}/tiles?f={F_JSONLD}'  # noqa
    })
    tiles['links'].append({
        'type': FORMAT_TYPES[F_HTML],
        'rel': request.get_linkrel(F_HTML),
        'title': 'This document as HTML',
        'href': f'{self.get_collections_url()}/{dataset}/tiles?f={F_HTML}'
    })

    tile_services = p.get_tiles_service(
        baseurl=self.base_url,
        servicepath=f'{self.get_collections_url()}/{dataset}/tiles/{{tileMatrixSetId}}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}?f={p.format_type}'  # noqa
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
            'title': f'{matrix.tileMatrixSet} TileMatrixSet definition (as {F_JSON})', # noqa
            'href': f'{self.base_url}/TileMatrixSets/{matrix.tileMatrixSet}?f={F_JSON}'  # noqa
        })
        tile_matrix['links'].append({
            'type': FORMAT_TYPES[F_JSON],
            'rel': request.get_linkrel(F_JSON),
            'title': f'{dataset} - {matrix.tileMatrixSet} - {F_JSON}',
            'href': f'{self.get_collections_url()}/{dataset}/tiles/{matrix.tileMatrixSet}?f={F_JSON}'  # noqa
        })
        tile_matrix['links'].append({
            'type': FORMAT_TYPES[F_HTML],
            'rel': request.get_linkrel(F_HTML),
            'title': f'{dataset} - {matrix.tileMatrixSet} - {F_HTML}',
            'href': f'{self.get_collections_url()}/{dataset}/tiles/{matrix.tileMatrixSet}?f={F_HTML}'  # noqa
        })

        tiles['tilesets'].append(tile_matrix)

    if request.format == F_HTML:  # render
        tiles['id'] = dataset
        tiles['title'] = l10n.translate(
            self.config['resources'][dataset]['title'], SYSTEM_LOCALE)
        tiles['tilesets'] = [
            scheme.tileMatrixSet for scheme in p.get_tiling_schemes()]
        tiles['bounds'] = \
            self.config['resources'][dataset]['extents']['spatial']['bbox']
        tiles['minzoom'] = p.options['zoom']['min']
        tiles['maxzoom'] = p.options['zoom']['max']
        tiles['collections_path'] = self.get_collections_url()
        tiles['tile_type'] = p.tile_type

        content = render_j2_template(self.tpl_config,
                                     'collections/tiles/index.html', tiles,
                                     request.locale)

        return headers, HTTPStatus.OK, content

    return headers, HTTPStatus.OK, to_json(tiles, self.pretty_print)

@pre_process
def get_collection_tiles_data(
        self, request: Union[APIRequest, Any],
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
        return self.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE,
                                           **self.api_headers)
    LOGGER.debug('Processing tiles')

    collections = filter_dict_by_key_value(self.config['resources'],
                                           'type', 'collection')

    if dataset not in collections.keys():
        msg = 'Collection not found'
        return self.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Loading tile provider')
    try:
        t = get_provider_by_type(
            self.config['resources'][dataset]['providers'], 'tile')
        p = load_plugin('provider', t)

        format_ = p.format_type
        headers['Content-Type'] = format_

        LOGGER.debug(f'Fetching tileset id {matrix_id} and tile {z_idx}/{y_idx}/{x_idx}')  # noqa
        content = p.get_tiles(layer=p.get_layer(), tileset=matrix_id,
                              z=z_idx, y=y_idx, x=x_idx, format_=format_)
        if content is None:
            msg = 'identifier not found'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers, format_, 'NotFound', msg)
        else:
            return headers, HTTPStatus.OK, content

    # @TODO: figure out if the spec requires to return json errors
    except KeyError:
        msg = 'Invalid collection tiles'
        return self.get_exception(
            HTTPStatus.BAD_REQUEST, headers, format_,
            'InvalidParameterValue', msg)
    except ProviderGenericError as err:
        LOGGER.error(err)
        return self.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

@gzip
@pre_process
@jsonldify
def get_collection_tiles_metadata(
        self, request: Union[APIRequest, Any],
        dataset=None, matrix_id=None) -> Tuple[dict, int, str]:
    """
    Get collection items tiles

    :param request: A request object
    :param dataset: dataset name
    :param matrix_id: matrix identifier

    :returns: tuple of headers, status code, content
    """

    if not request.is_valid([TilesMetadataFormat.TILEJSON]):
        return self.get_format_exception(request)
    headers = request.get_response_headers(**self.api_headers)

    if any([dataset is None,
            dataset not in self.config['resources'].keys()]):

        msg = 'Collection not found'
        return self.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Creating collection tiles')
    LOGGER.debug('Loading provider')
    try:
        t = get_provider_by_type(
            self.config['resources'][dataset]['providers'], 'tile')
        p = load_plugin('provider', t)
    except KeyError:
        msg = 'Invalid collection tiles'
        return self.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)
    except ProviderGenericError as err:
        LOGGER.error(err)
        return self.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    # Get provider language (if any)
    prv_locale = l10n.get_plugin_locale(t, request.raw_locale)

    # Set response language to requested provider locale
    # (if it supports language) and/or otherwise the requested pygeoapi
    # locale (or fallback default locale)
    l10n.set_response_language(headers, prv_locale, request.locale)

    tiles_metadata = p.get_metadata(
        dataset=dataset, server_url=self.base_url,
        layer=p.get_layer(), tileset=matrix_id,
        metadata_format=request._format, title=l10n.translate(
            self.config['resources'][dataset]['title'],
            request.locale),
        description=l10n.translate(
            self.config['resources'][dataset]['description'],
            request.locale),
        language=prv_locale)

    if request.format == F_HTML:  # render
        content = render_j2_template(self.tpl_config,
                                     'collections/tiles/metadata.html',
                                     tiles_metadata, request.locale)

        return headers, HTTPStatus.OK, content
    else:
        return headers, HTTPStatus.OK, tiles_metadata


