# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Sander Schaminee <sander.schaminee@geocat.net>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2024 Tom Kralidis
# Copyright (c) 2022 Francesco Bartoli
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
# Copyright (c) 2023 Ricardo Garcia Silva
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
from datetime import datetime
from http import HTTPStatus
import logging
from typing import Any, Tuple, Union, Optional
import urllib.parse

from pygeofilter.parsers.ecql import parse as parse_ecql_text
from pygeofilter.parsers.cql_json import parse as parse_cql_json
from pyproj.exceptions import CRSError

from pygeoapi import l10n
from pygeoapi.formatter.base import FormatterSerializationError
from pygeoapi.linked_data import geojson2jsonld
from pygeoapi.plugin import load_plugin, PLUGINS
from pygeoapi.provider.base import (
    ProviderGenericError, ProviderTypeError, SchemaType)

from pygeoapi.models.cql import CQLModel
from pygeoapi.util import (CrsTransformSpec, filter_providers_by_type,
                           filter_dict_by_key_value, get_crs_from_uri,
                           get_provider_by_type, get_supported_crs_list,
                           modify_pygeofilter, render_j2_template, str2bool,
                           to_json, transform_bbox)

from . import (
    APIRequest, API, SYSTEM_LOCALE, F_JSON, FORMAT_TYPES, F_HTML, F_JSONLD,
    validate_bbox, validate_datetime
)

LOGGER = logging.getLogger(__name__)

OGC_RELTYPES_BASE = 'http://www.opengis.net/def/rel/ogc/1.0'

DEFAULT_CRS_LIST = [
    'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
    'http://www.opengis.net/def/crs/OGC/1.3/CRS84h',
]

DEFAULT_CRS = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
DEFAULT_STORAGE_CRS = DEFAULT_CRS

CONFORMANCE_CLASSES_FEATURES = [
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/req/oas30',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson',
    'http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs',
    'http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/queryables',
    'http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/queryables-query-parameters',  # noqa
    'http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/create-replace-delete',  # noqa
    'http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/schemas',
    'http://www.opengis.net/spec/ogcapi-features-5/1.0/req/core-roles-features'
]

CONFORMANCE_CLASSES_RECORDS = [
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/sorting',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/opensearch',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/json',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/html'
]


def get_collection_queryables(api: API, request: Union[APIRequest, Any],
                              dataset=None) -> Tuple[dict, int, str]:
    """
    Provide collection queryables

    :param request: A request object
    :param dataset: name of collection

    :returns: tuple of headers, status code, content
    """

    headers = request.get_response_headers(**api.api_headers)

    if any([dataset is None,
            dataset not in api.config['resources'].keys()]):

        msg = 'Collection not found'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Creating collection queryables')
    try:
        LOGGER.debug('Loading feature provider')
        p = load_plugin('provider', get_provider_by_type(
            api.config['resources'][dataset]['providers'], 'feature'))
    except ProviderTypeError:
        try:
            LOGGER.debug('Loading coverage provider')
            p = load_plugin('provider', get_provider_by_type(
                api.config['resources'][dataset]['providers'], 'coverage'))  # noqa
        except ProviderTypeError:
            LOGGER.debug('Loading record provider')
            p = load_plugin('provider', get_provider_by_type(
                api.config['resources'][dataset]['providers'], 'record'))
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    queryables = {
        'type': 'object',
        'title': l10n.translate(
            api.config['resources'][dataset]['title'], request.locale),
        'properties': {},
        '$schema': 'http://json-schema.org/draft/2019-09/schema',
        '$id': f'{api.get_collections_url()}/{dataset}/queryables'
    }

    if p.fields:
        queryables['properties']['geometry'] = {
            '$ref': 'https://geojson.org/schema/Geometry.json',
            'x-ogc-role': 'primary-geometry'
        }

    for k, v in p.fields.items():
        show_field = False
        if p.properties:
            if k in p.properties:
                show_field = True
        else:
            show_field = True

        if show_field:
            queryables['properties'][k] = {
                'title': k,
                'type': v['type']
            }
            if v.get('format') is not None:
                queryables['properties'][k]['format'] = v['format']
            if 'values' in v:
                queryables['properties'][k]['enum'] = v['values']

            if k == p.id_field:
                queryables['properties'][k]['x-ogc-role'] = 'id'
            if k == p.time_field:
                queryables['properties'][k]['x-ogc-role'] = 'primary-instant'  # noqa

    if request.format == F_HTML:  # render
        queryables['title'] = l10n.translate(
            api.config['resources'][dataset]['title'], request.locale)

        queryables['collections_path'] = api.get_collections_url()

        content = render_j2_template(api.tpl_config,
                                     'collections/queryables.html',
                                     queryables, request.locale)

        return headers, HTTPStatus.OK, content

    headers['Content-Type'] = 'application/schema+json'

    return headers, HTTPStatus.OK, to_json(queryables, api.pretty_print)


def get_collection_items(
        api: API, request: Union[APIRequest, Any],
        dataset) -> Tuple[dict, int, str]:
    """
    Queries collection

    :param request: A request object
    :param dataset: dataset name

    :returns: tuple of headers, status code, content
    """

    if not request.is_valid(PLUGINS['formatter'].keys()):
        return api.get_format_exception(request)

    # Set Content-Language to system locale until provider locale
    # has been determined
    headers = request.get_response_headers(SYSTEM_LOCALE,
                                           **api.api_headers)

    properties = []
    reserved_fieldnames = ['bbox', 'bbox-crs', 'crs', 'f', 'lang', 'limit',
                           'offset', 'resulttype', 'datetime', 'sortby',
                           'properties', 'skipGeometry', 'q',
                           'filter', 'filter-lang', 'filter-crs']

    collections = filter_dict_by_key_value(api.config['resources'],
                                           'type', 'collection')

    if dataset not in collections.keys():
        msg = 'Collection not found'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Processing query parameters')

    LOGGER.debug('Processing offset parameter')
    try:
        offset = int(request.params.get('offset'))
        if offset < 0:
            msg = 'offset value should be positive or zero'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        offset = 0
    except ValueError:
        msg = 'offset value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    LOGGER.debug('Processing limit parameter')
    try:
        limit = int(request.params.get('limit'))
        # TODO: We should do more validation, against the min and max
        #       allowed by the server configuration
        if limit <= 0:
            msg = 'limit value should be strictly positive'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        limit = int(api.config['server']['limit'])
    except ValueError:
        msg = 'limit value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    resulttype = request.params.get('resulttype') or 'results'

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
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

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

    LOGGER.debug('processing q parameter')
    q = request.params.get('q') or None

    LOGGER.debug('Loading provider')

    provider_def = None
    try:
        provider_type = 'feature'
        provider_def = get_provider_by_type(
            collections[dataset]['providers'], provider_type)
        p = load_plugin('provider', provider_def)
    except ProviderTypeError:
        try:
            provider_type = 'record'
            provider_def = get_provider_by_type(
                collections[dataset]['providers'], provider_type)
            p = load_plugin('provider', provider_def)
        except ProviderTypeError:
            msg = 'Invalid provider type'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'NoApplicableCode', msg)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    crs_transform_spec = None
    if provider_type == 'feature':
        # crs query parameter is only available for OGC API - Features
        # right now, not for OGC API - Records.
        LOGGER.debug('Processing crs parameter')
        query_crs_uri = request.params.get('crs')
        try:
            crs_transform_spec = create_crs_transform_spec(
                provider_def, query_crs_uri,
            )
        except (ValueError, CRSError) as err:
            msg = str(err)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
        set_content_crs_header(headers, provider_def, query_crs_uri)

    LOGGER.debug('Processing bbox-crs parameter')
    bbox_crs = request.params.get('bbox-crs')
    if bbox_crs is not None:
        # Validate bbox-crs parameter
        if len(bbox) == 0:
            msg = 'bbox-crs specified without bbox parameter'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'NoApplicableCode', msg)

        if len(bbox_crs) == 0:
            msg = 'bbox-crs specified but is empty'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'NoApplicableCode', msg)

        supported_crs_list = get_supported_crs_list(provider_def, DEFAULT_CRS_LIST) # noqa
        if bbox_crs not in supported_crs_list:
            msg = f'bbox-crs {bbox_crs} not supported for this collection'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'NoApplicableCode', msg)
    elif len(bbox) > 0:
        # bbox but no bbox-crs param: assume bbox is in default CRS
        bbox_crs = DEFAULT_CRS

    # Transform bbox to storageCRS
    # when bbox-crs different from storageCRS.
    if len(bbox) > 0:
        try:
            # Get a pyproj CRS instance for the Collection's Storage CRS
            storage_crs = provider_def.get('storage_crs', DEFAULT_STORAGE_CRS) # noqa

            # Do the (optional) Transform to the Storage CRS
            bbox = transform_bbox(bbox, bbox_crs, storage_crs)
        except CRSError as e:
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'NoApplicableCode', str(e))

    LOGGER.debug('processing property parameters')
    for k, v in request.params.items():
        if k not in reserved_fieldnames and k in list(p.fields.keys()):
            LOGGER.debug(f'Adding property filter {k}={v}')
            properties.append((k, v))

    LOGGER.debug('processing sort parameter')
    val = request.params.get('sortby')

    if val is not None:
        sortby = []
        sorts = val.split(',')
        for s in sorts:
            prop = s
            order = '+'
            if s[0] in ['+', '-']:
                order = s[0]
                prop = s[1:]

            if prop not in p.fields.keys():
                msg = 'bad sort property'
                return api.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)

            sortby.append({'property': prop, 'order': order})
    else:
        sortby = []

    LOGGER.debug('processing properties parameter')
    val = request.params.get('properties')

    if val is not None:
        select_properties = val.split(',')
        properties_to_check = set(p.properties) | set(p.fields.keys())

        if (len(list(set(select_properties) -
                     set(properties_to_check))) > 0):
            msg = 'unknown properties specified'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    else:
        select_properties = []

    LOGGER.debug('processing skipGeometry parameter')
    val = request.params.get('skipGeometry')
    if val is not None:
        skip_geometry = str2bool(val)
    else:
        skip_geometry = False

    LOGGER.debug('Processing filter-crs parameter')
    filter_crs_uri = request.params.get('filter-crs', DEFAULT_CRS)
    LOGGER.debug('processing filter parameter')
    cql_text = request.params.get('filter')
    if cql_text is not None:
        try:
            filter_ = parse_ecql_text(cql_text)
            filter_ = modify_pygeofilter(
                filter_,
                filter_crs_uri=filter_crs_uri,
                storage_crs_uri=provider_def.get('storage_crs'),
                geometry_column_name=provider_def.get('geom_field'),
            )
        except Exception:
            msg = f'Bad CQL string : {cql_text}'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    else:
        filter_ = None

    LOGGER.debug('Processing filter-lang parameter')
    filter_lang = request.params.get('filter-lang')
    # Currently only cql-text is handled, but it is optional
    if filter_lang not in [None, 'cql-text']:
        msg = 'Invalid filter language'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)
    # Get provider locale (if any)
    prv_locale = l10n.get_plugin_locale(provider_def, request.raw_locale)

    LOGGER.debug('Querying provider')
    LOGGER.debug(f'offset: {offset}')
    LOGGER.debug(f'limit: {limit}')
    LOGGER.debug(f'resulttype: {resulttype}')
    LOGGER.debug(f'sortby: {sortby}')
    LOGGER.debug(f'bbox: {bbox}')
    if provider_type == 'feature':
        LOGGER.debug(f'crs: {query_crs_uri}')
    LOGGER.debug(f'datetime: {datetime_}')
    LOGGER.debug(f'properties: {properties}')
    LOGGER.debug(f'select properties: {select_properties}')
    LOGGER.debug(f'skipGeometry: {skip_geometry}')
    LOGGER.debug(f'language: {prv_locale}')
    LOGGER.debug(f'q: {q}')
    LOGGER.debug(f'cql_text: {cql_text}')
    LOGGER.debug(f'filter_: {filter_}')
    LOGGER.debug(f'filter-lang: {filter_lang}')
    LOGGER.debug(f'filter-crs: {filter_crs_uri}')

    try:
        content = p.query(offset=offset, limit=limit,
                          resulttype=resulttype, bbox=bbox,
                          datetime_=datetime_, properties=properties,
                          sortby=sortby, skip_geometry=skip_geometry,
                          select_properties=select_properties,
                          crs_transform_spec=crs_transform_spec,
                          q=q, language=prv_locale, filterq=filter_)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    serialized_query_params = ''
    for k, v in request.params.items():
        if k not in ('f', 'offset'):
            serialized_query_params += '&'
            serialized_query_params += urllib.parse.quote(k, safe='')
            serialized_query_params += '='
            serialized_query_params += urllib.parse.quote(str(v), safe=',')

    # TODO: translate titles
    uri = f'{api.get_collections_url()}/{dataset}/items'
    content['links'] = [{
        'type': 'application/geo+json',
        'rel': request.get_linkrel(F_JSON),
        'title': l10n.translate('This document as GeoJSON', request.locale),
        'href': f'{uri}?f={F_JSON}{serialized_query_params}'
    }, {
        'rel': request.get_linkrel(F_JSONLD),
        'type': FORMAT_TYPES[F_JSONLD],
        'title': l10n.translate('This document as RDF (JSON-LD)', request.locale),  # noqa
        'href': f'{uri}?f={F_JSONLD}{serialized_query_params}'
    }, {
        'type': FORMAT_TYPES[F_HTML],
        'rel': request.get_linkrel(F_HTML),
        'title': l10n.translate('This document as HTML', request.locale),
        'href': f'{uri}?f={F_HTML}{serialized_query_params}'
    }]

    if offset > 0:
        prev = max(0, offset - limit)
        content['links'].append(
            {
                'type': 'application/geo+json',
                'rel': 'prev',
                'title': l10n.translate('Items (prev)', request.locale),
                'href': f'{uri}?offset={prev}{serialized_query_params}'
            })

    if 'numberMatched' in content:
        if content['numberMatched'] > (limit + offset):
            next_ = offset + limit
            next_href = f'{uri}?offset={next_}{serialized_query_params}'
            content['links'].append(
                {
                    'type': 'application/geo+json',
                    'rel': 'next',
                    'title': l10n.translate('Items (next)', request.locale),
                    'href': next_href
                })

    content['links'].append(
        {
            'type': FORMAT_TYPES[F_JSON],
            'title': l10n.translate(
                collections[dataset]['title'], request.locale),
            'rel': 'collection',
            'href': '/'.join(uri.split('/')[:-1])
        })

    content['timeStamp'] = datetime.utcnow().strftime(
        '%Y-%m-%dT%H:%M:%S.%fZ')

    # Set response language to requested provider locale
    # (if it supports language) and/or otherwise the requested pygeoapi
    # locale (or fallback default locale)
    l10n.set_response_language(headers, prv_locale, request.locale)

    if request.format == F_HTML:  # render
        # For constructing proper URIs to items

        content['items_path'] = uri
        content['dataset_path'] = '/'.join(uri.split('/')[:-1])
        content['collections_path'] = api.get_collections_url()

        content['offset'] = offset

        content['id_field'] = p.id_field
        if p.uri_field is not None:
            content['uri_field'] = p.uri_field
        if p.title_field is not None:
            content['title_field'] = l10n.translate(p.title_field,
                                                    request.locale)
            # If title exists, use it as id in html templates
            content['id_field'] = content['title_field']
        content = render_j2_template(api.tpl_config,
                                     'collections/items/index.html',
                                     content, request.locale)
        return headers, HTTPStatus.OK, content
    elif request.format == 'csv':  # render
        formatter = load_plugin('formatter',
                                {'name': 'CSV', 'geom': True})

        try:
            content = formatter.write(
                data=content,
                options={
                    'provider_def': get_provider_by_type(
                                        collections[dataset]['providers'],
                                        'feature')
                }
            )
        except FormatterSerializationError:
            msg = 'Error serializing output'
            return api.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)

        headers['Content-Type'] = formatter.mimetype

        if p.filename is None:
            filename = f'{dataset}.csv'
        else:
            filename = f'{p.filename}'

        cd = f'attachment; filename="{filename}"'
        headers['Content-Disposition'] = cd

        return headers, HTTPStatus.OK, content

    elif request.format == F_JSONLD:
        content = geojson2jsonld(
            api, content, dataset, id_field=(p.uri_field or 'id')
        )

    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def post_collection_items(
        api: API, request: APIRequest, dataset) -> Tuple[dict, int, str]:
    """
    Queries collection or filter an item

    :param request: A request object
    :param dataset: dataset name

    :returns: tuple of headers, status code, content
    """

    request_headers = request.headers

    if not request.is_valid(PLUGINS['formatter'].keys()):
        return api.get_format_exception(request)

    # Set Content-Language to system locale until provider locale
    # has been determined
    headers = request.get_response_headers(SYSTEM_LOCALE, **api.api_headers)

    properties = []
    reserved_fieldnames = ['bbox', 'f', 'limit', 'offset',
                           'resulttype', 'datetime', 'sortby',
                           'properties', 'skipGeometry', 'q',
                           'filter-lang', 'filter-crs']

    collections = filter_dict_by_key_value(api.config['resources'],
                                           'type', 'collection')

    if dataset not in collections.keys():
        msg = 'Invalid collection'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    LOGGER.debug('Processing query parameters')

    LOGGER.debug('Processing offset parameter')
    try:
        offset = int(request.params.get('offset'))
        if offset < 0:
            msg = 'offset value should be positive or zero'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        offset = 0
    except ValueError:
        msg = 'offset value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    LOGGER.debug('Processing limit parameter')
    try:
        limit = int(request.params.get('limit'))
        # TODO: We should do more validation, against the min and max
        # allowed by the server configuration
        if limit <= 0:
            msg = 'limit value should be strictly positive'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        limit = int(api.config['server']['limit'])
    except ValueError:
        msg = 'limit value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    resulttype = request.params.get('resulttype') or 'results'

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
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

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

    LOGGER.debug('processing q parameter')
    val = request.params.get('q')

    q = None
    if val is not None:
        q = val

    LOGGER.debug('Loading provider')

    try:
        provider_def = get_provider_by_type(
            collections[dataset]['providers'], 'feature')
    except ProviderTypeError:
        try:
            provider_def = get_provider_by_type(
                collections[dataset]['providers'], 'record')
        except ProviderTypeError:
            msg = 'Invalid provider type'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'NoApplicableCode', msg)

    try:
        p = load_plugin('provider', provider_def)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    LOGGER.debug('processing property parameters')
    for k, v in request.params.items():
        if k not in reserved_fieldnames and k not in p.fields.keys():
            msg = f'unknown query parameter: {k}'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
        elif k not in reserved_fieldnames and k in p.fields.keys():
            LOGGER.debug(f'Add property filter {k}={v}')
            properties.append((k, v))

    LOGGER.debug('processing sort parameter')
    val = request.params.get('sortby')

    if val is not None:
        sortby = []
        sorts = val.split(',')
        for s in sorts:
            prop = s
            order = '+'
            if s[0] in ['+', '-']:
                order = s[0]
                prop = s[1:]

            if prop not in p.fields.keys():
                msg = 'bad sort property'
                return api.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)

            sortby.append({'property': prop, 'order': order})
    else:
        sortby = []

    LOGGER.debug('processing properties parameter')
    val = request.params.get('properties')

    if val is not None:
        select_properties = val.split(',')
        properties_to_check = set(p.properties) | set(p.fields.keys())

        if (len(list(set(select_properties) -
                     set(properties_to_check))) > 0):
            msg = 'unknown properties specified'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    else:
        select_properties = []

    LOGGER.debug('processing skipGeometry parameter')
    val = request.params.get('skipGeometry')
    if val is not None:
        skip_geometry = str2bool(val)
    else:
        skip_geometry = False

    LOGGER.debug('Processing filter-crs parameter')
    filter_crs = request.params.get('filter-crs', DEFAULT_CRS)
    LOGGER.debug('Processing filter-lang parameter')
    filter_lang = request.params.get('filter-lang')
    if filter_lang != 'cql-json':  # @TODO add check from the configuration
        msg = 'Invalid filter language'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    LOGGER.debug('Querying provider')
    LOGGER.debug(f'offset: {offset}')
    LOGGER.debug(f'limit: {limit}')
    LOGGER.debug(f'resulttype: {resulttype}')
    LOGGER.debug(f'sortby: {sortby}')
    LOGGER.debug(f'bbox: {bbox}')
    LOGGER.debug(f'datetime: {datetime_}')
    LOGGER.debug(f'properties: {select_properties}')
    LOGGER.debug(f'skipGeometry: {skip_geometry}')
    LOGGER.debug(f'q: {q}')
    LOGGER.debug(f'filter-lang: {filter_lang}')
    LOGGER.debug(f'filter-crs: {filter_crs}')

    LOGGER.debug('Processing headers')

    LOGGER.debug('Processing request content-type header')
    if (request_headers.get(
        'Content-Type') or request_headers.get(
            'content-type')) != 'application/query-cql-json':
        msg = ('Invalid body content-type')
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidHeaderValue', msg)

    LOGGER.debug('Processing body')

    if not request.data:
        msg = 'missing request data'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'MissingParameterValue', msg)

    filter_ = None
    try:
        # Parse bytes data, if applicable
        data = request.data.decode()
        LOGGER.debug(data)
    except UnicodeDecodeError:
        msg = 'Unicode error in data'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    # FIXME: remove testing backend in use once CQL support is normalized
    if p.name == 'PostgreSQL':
        LOGGER.debug('processing PostgreSQL CQL_JSON data')
        try:
            filter_ = parse_cql_json(data)
            filter_ = modify_pygeofilter(
                filter_,
                filter_crs_uri=filter_crs,
                storage_crs_uri=provider_def.get('storage_crs'),
                geometry_column_name=provider_def.get('geom_field')
            )
        except Exception:
            msg = f'Bad CQL string : {data}'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    else:
        LOGGER.debug('processing Elasticsearch CQL_JSON data')
        try:
            filter_ = CQLModel.parse_raw(data)
        except Exception:
            msg = f'Bad CQL string : {data}'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

    try:
        content = p.query(offset=offset, limit=limit,
                          resulttype=resulttype, bbox=bbox,
                          datetime_=datetime_, properties=properties,
                          sortby=sortby,
                          select_properties=select_properties,
                          skip_geometry=skip_geometry,
                          q=q,
                          filterq=filter_)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def manage_collection_item(
        api: API, request: APIRequest,
        action, dataset, identifier=None) -> Tuple[dict, int, str]:
    """
    Adds an item to a collection

    :param request: A request object
    :param action: an action among 'create', 'update', 'delete', 'options'
    :param dataset: dataset name

    :returns: tuple of headers, status code, content
    """

    if not request.is_valid(PLUGINS['formatter'].keys()):
        return api.get_format_exception(request)

    # Set Content-Language to system locale until provider locale
    # has been determined
    headers = request.get_response_headers(SYSTEM_LOCALE, **api.api_headers)

    collections = filter_dict_by_key_value(api.config['resources'],
                                           'type', 'collection')

    if dataset not in collections.keys():
        msg = 'Collection not found'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Loading provider')
    try:
        provider_def = get_provider_by_type(
            collections[dataset]['providers'], 'feature')
        p = load_plugin('provider', provider_def)
    except ProviderTypeError:
        try:
            provider_def = get_provider_by_type(
                collections[dataset]['providers'], 'record')
            p = load_plugin('provider', provider_def)
        except ProviderTypeError:
            msg = 'Invalid provider type'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

    if action == 'options':
        headers['Allow'] = 'HEAD, GET'
        if p.editable:
            if identifier is None:
                headers['Allow'] += ', POST'
            else:
                headers['Allow'] += ', PUT, DELETE'
        return headers, HTTPStatus.OK, ''

    if not p.editable:
        msg = 'Collection is not editable'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    if action in ['create', 'update'] and not request.data:
        msg = 'No data found'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    if action == 'create':
        LOGGER.debug('Creating item')
        try:
            identifier = p.create(request.data)
        except TypeError as err:
            msg = str(err)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
        except ProviderGenericError as err:
            return api.get_exception(
                err.http_status_code, headers, request.format,
                err.ogc_exception_code, err.message)

        headers['Location'] = f'{api.get_collections_url()}/{dataset}/items/{identifier}'  # noqa

        return headers, HTTPStatus.CREATED, ''

    if action == 'update':
        LOGGER.debug('Updating item')
        try:
            _ = p.update(identifier, request.data)
        except TypeError as err:
            msg = str(err)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
        except ProviderGenericError as err:
            return api.get_exception(
                err.http_status_code, headers, request.format,
                err.ogc_exception_code, err.message)

        return headers, HTTPStatus.NO_CONTENT, ''

    if action == 'delete':
        LOGGER.debug('Deleting item')
        try:
            _ = p.delete(identifier)
        except ProviderGenericError as err:
            return api.get_exception(
                err.http_status_code, headers, request.format,
                err.ogc_exception_code, err.message)

        return headers, HTTPStatus.OK, ''


def get_collection_item(api: API, request: APIRequest,
                        dataset, identifier) -> Tuple[dict, int, str]:
    """
    Get a single collection item

    :param request: A request object
    :param dataset: dataset name
    :param identifier: item identifier

    :returns: tuple of headers, status code, content
    """

    # Set Content-Language to system locale until provider locale
    # has been determined
    headers = request.get_response_headers(SYSTEM_LOCALE, **api.api_headers)

    LOGGER.debug('Processing query parameters')

    collections = filter_dict_by_key_value(api.config['resources'],
                                           'type', 'collection')

    if dataset not in collections.keys():
        msg = 'Collection not found'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Loading provider')

    try:
        provider_type = 'feature'
        provider_def = get_provider_by_type(
            collections[dataset]['providers'], provider_type)
        p = load_plugin('provider', provider_def)
    except ProviderTypeError:
        try:
            provider_type = 'record'
            provider_def = get_provider_by_type(
                collections[dataset]['providers'], provider_type)
            p = load_plugin('provider', provider_def)
        except ProviderTypeError:
            msg = 'Invalid provider type'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    crs_transform_spec = None
    if provider_type == 'feature':
        # crs query parameter is only available for OGC API - Features
        # right now, not for OGC API - Records.
        LOGGER.debug('Processing crs parameter')
        query_crs_uri = request.params.get('crs')
        try:
            crs_transform_spec = create_crs_transform_spec(
                provider_def, query_crs_uri,
            )
        except (ValueError, CRSError) as err:
            msg = str(err)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
        set_content_crs_header(headers, provider_def, query_crs_uri)

    # Get provider language (if any)
    prv_locale = l10n.get_plugin_locale(provider_def, request.raw_locale)

    try:
        LOGGER.debug(f'Fetching id {identifier}')
        content = p.get(
            identifier,
            language=prv_locale,
            crs_transform_spec=crs_transform_spec,
        )
    except ProviderGenericError as err:
        return api.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    if content is None:
        msg = 'identifier not found'
        return api.get_exception(HTTPStatus.BAD_REQUEST, headers,
                                 request.format, 'NotFound', msg)

    uri = content['properties'].get(p.uri_field) if p.uri_field else \
        f'{api.get_collections_url()}/{dataset}/items/{identifier}'

    if 'links' not in content:
        content['links'] = []

    content['links'].extend([{
        'type': FORMAT_TYPES[F_JSON],
        'rel': 'root',
        'title': l10n.translate('The landing page of this server as JSON', request.locale),  # noqa
        'href': f"{api.base_url}?f={F_JSON}"
        }, {
        'type': FORMAT_TYPES[F_HTML],
        'rel': 'root',
        'title': l10n.translate('The landing page of this server as HTML', request.locale),  # noqa
        'href': f"{api.base_url}?f={F_HTML}"
        }, {
        'rel': request.get_linkrel(F_JSON),
        'type': 'application/geo+json',
        'title': l10n.translate('This document as JSON', request.locale),
        'href': f'{uri}?f={F_JSON}'
        }, {
        'rel': request.get_linkrel(F_JSONLD),
        'type': FORMAT_TYPES[F_JSONLD],
        'title': l10n.translate('This document as RDF (JSON-LD)', request.locale),  # noqa
        'href': f'{uri}?f={F_JSONLD}'
        }, {
        'rel': request.get_linkrel(F_HTML),
        'type': FORMAT_TYPES[F_HTML],
        'title': l10n.translate('This document as HTML', request.locale),
        'href': f'{uri}?f={F_HTML}'
        }, {
        'rel': 'collection',
        'type': FORMAT_TYPES[F_JSON],
        'title': l10n.translate(collections[dataset]['title'],
                                request.locale),
        'href': f'{api.get_collections_url()}/{dataset}'
    }])

    link_request_format = (
        request.format if request.format is not None else F_JSON
    )
    if 'prev' in content:
        content['links'].append({
            'rel': 'prev',
            'type': FORMAT_TYPES[link_request_format],
            'href': f"{api.get_collections_url()}/{dataset}/items/{content['prev']}?f={link_request_format}"  # noqa
        })
    if 'next' in content:
        content['links'].append({
            'rel': 'next',
            'type': FORMAT_TYPES[link_request_format],
            'href': f"{api.get_collections_url()}/{dataset}/items/{content['next']}?f={link_request_format}"  # noqa
        })

    # Set response language to requested provider locale
    # (if it supports language) and/or otherwise the requested pygeoapi
    # locale (or fallback default locale)
    l10n.set_response_language(headers, prv_locale, request.locale)

    if request.format == F_HTML:  # render
        content['title'] = l10n.translate(collections[dataset]['title'],
                                          request.locale)
        content['id_field'] = p.id_field
        if p.uri_field is not None:
            content['uri_field'] = p.uri_field
        if p.title_field is not None:
            content['title_field'] = l10n.translate(p.title_field,
                                                    request.locale)
        content['collections_path'] = api.get_collections_url()

        content = render_j2_template(api.tpl_config,
                                     'collections/items/item.html',
                                     content, request.locale)
        return headers, HTTPStatus.OK, content

    elif request.format == F_JSONLD:
        content = geojson2jsonld(
            api, content, dataset, uri, (p.uri_field or 'id')
        )

    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def create_crs_transform_spec(
        config: dict, query_crs_uri: Optional[str] = None) -> Union[None, CrsTransformSpec]:  # noqa
    """
    Create a `CrsTransformSpec` instance based on provider config and
    *crs* query parameter.

    :param config: Provider config dictionary.
    :type config: dict
    :param query_crs_uri: Uniform resource identifier of the coordinate
        reference system (CRS) specified in query parameter (if specified).
    :type query_crs_uri: str, optional

    :raises ValueError: Error raised if the CRS specified in the query
        parameter is not in the list of supported CRSs of the provider.
    :raises `CRSError`: Error raised if no CRS could be identified from the
        query *crs* parameter (URI).

    :returns: `CrsTransformSpec` instance if the CRS specified in query
        parameter differs from the storage CRS, else `None`.
    :rtype: Union[None, CrsTransformSpec]
    """

    # Get storage/default CRS for Collection.
    storage_crs_uri = config.get('storage_crs', DEFAULT_STORAGE_CRS)

    if not query_crs_uri:
        if storage_crs_uri in DEFAULT_CRS_LIST:
            # Could be that storageCRS is
            # http://www.opengis.net/def/crs/OGC/1.3/CRS84h
            query_crs_uri = storage_crs_uri
        else:
            query_crs_uri = DEFAULT_CRS
        LOGGER.debug(f'no crs parameter, using default: {query_crs_uri}')

    supported_crs_list = get_supported_crs_list(config, DEFAULT_CRS_LIST)
    # Check that the crs specified by the query parameter is supported.
    if query_crs_uri not in supported_crs_list:
        raise ValueError(
            f'CRS {query_crs_uri!r} not supported for this '
            'collection. List of supported CRSs: '
            f'{", ".join(supported_crs_list)}.'
        )
    crs_out = get_crs_from_uri(query_crs_uri)

    storage_crs = get_crs_from_uri(storage_crs_uri)
    # Check if the crs specified in query parameter differs from the
    # storage crs.
    if str(storage_crs) != str(crs_out):
        LOGGER.debug(
            f'CRS transformation: {storage_crs} -> {crs_out}'
        )
        return CrsTransformSpec(
            source_crs_uri=storage_crs_uri,
            source_crs_wkt=storage_crs.to_wkt(),
            target_crs_uri=query_crs_uri,
            target_crs_wkt=crs_out.to_wkt(),
        )
    else:
        LOGGER.debug('No CRS transformation')
        return None


def set_content_crs_header(
        headers: dict, config: dict, query_crs_uri: Optional[str] = None):
    """
    Set the *Content-Crs* header in responses from providers of Feature type.

    :param headers: Response headers dictionary.
    :type headers: dict
    :param config: Provider config dictionary.
    :type config: dict
    :param query_crs_uri: Uniform resource identifier of the coordinate
        reference system specified in query parameter (if specified).
    :type query_crs_uri: str, optional

    :returns: None
    """

    if query_crs_uri:
        content_crs_uri = query_crs_uri
    else:
        # If empty use default CRS
        storage_crs_uri = config.get('storage_crs', DEFAULT_STORAGE_CRS)
        if storage_crs_uri in DEFAULT_CRS_LIST:
            # Could be that storageCRS is one of the defaults like
            # http://www.opengis.net/def/crs/OGC/1.3/CRS84h
            content_crs_uri = storage_crs_uri
        else:
            content_crs_uri = DEFAULT_CRS

    headers['Content-Crs'] = f'<{content_crs_uri}>'


def get_oas_30(cfg: dict, locale: str) -> tuple[list[dict[str, str]], dict[str, dict]]:  # noqa
    """
    Get OpenAPI fragments

    :param cfg: `dict` of configuration
    :param locale: `str` of locale

    :returns: `tuple` of `list` of tag objects, and `dict` of path objects
    """

    from pygeoapi.openapi import OPENAPI_YAML, get_visible_collections

    properties = {
        'name': 'properties',
        'in': 'query',
        'description': 'The properties that should be included for each feature. The parameter value is a comma-separated list of property names.',  # noqa
        'required': False,
        'style': 'form',
        'explode': False,
        'schema': {
            'type': 'array',
            'items': {
                'type': 'string'
            }
        }
    }

    LOGGER.debug('setting up collection endpoints')
    paths = {}

    collections = filter_dict_by_key_value(cfg['resources'],
                                           'type', 'collection')

    for k, v in get_visible_collections(cfg).items():
        try:
            ptype = None

            if filter_providers_by_type(
                    collections[k]['providers'], 'feature'):
                ptype = 'feature'

            if filter_providers_by_type(
                    collections[k]['providers'], 'record'):
                ptype = 'record'

            p = load_plugin('provider', get_provider_by_type(
                            collections[k]['providers'], ptype))

            collection_name_path = f'/collections/{k}'
            items_path = f'/collections/{k}/items'
            title = l10n.translate(v['title'], locale)
            description = l10n.translate(v['description'], locale)

            coll_properties = deepcopy(properties)

            coll_properties['schema']['items']['enum'] = list(p.fields.keys())

            paths[items_path] = {
                'get': {
                    'summary': f'Get {title} items',
                    'description': description,
                    'tags': [k],
                    'operationId': f'get{k.capitalize()}Features',
                    'parameters': [
                        {'$ref': '#/components/parameters/f'},
                        {'$ref': '#/components/parameters/lang'},
                        {'$ref': '#/components/parameters/bbox'},
                        {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/limit"},  # noqa
                        {'$ref': '#/components/parameters/crs'},  # noqa
                        {'$ref': '#/components/parameters/bbox-crs'},
                        coll_properties,
                        {'$ref': '#/components/parameters/vendorSpecificParameters'},  # noqa
                        {'$ref': '#/components/parameters/skipGeometry'},
                        {'$ref': f"{OPENAPI_YAML['oapir']}/parameters/sortby.yaml"},  # noqa
                        {'$ref': '#/components/parameters/offset'}
                    ],
                    'responses': {
                        '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/Features"},  # noqa
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                },
                'options': {
                    'summary': f'Options for {title} items',
                    'description': description,
                    'tags': [k],
                    'operationId': f'options{k.capitalize()}Features',
                    'responses': {
                        '200': {'description': 'options response'}
                    }
                }
            }

            if p.editable:
                LOGGER.debug('Provider is editable; adding post')

                paths[items_path]['post'] = {
                    'summary': f'Add {title} items',
                    'description': description,
                    'tags': [k],
                    'operationId': f'add{k.capitalize()}Features',
                    'requestBody': {
                        'description': 'Adds item to collection',
                        'content': {
                            'application/geo+json': {
                                'schema': {}
                            }
                        },
                        'required': True
                    },
                    'responses': {
                        '201': {'description': 'Successful creation'},
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }

                try:
                    schema_ref = p.get_schema(SchemaType.create)
                    paths[items_path]['post']['requestBody']['content'][schema_ref[0]] = {  # noqa
                        'schema': schema_ref[1]
                    }
                except Exception as err:
                    LOGGER.debug(err)

            if ptype == 'record':
                paths[items_path]['get']['parameters'].append(
                    {'$ref': f"{OPENAPI_YAML['oapir']}/parameters/q.yaml"})
            if p.fields:
                schema_path = f'{collection_name_path}/schema'

                paths[schema_path] = {
                    'get': {
                        'summary': f'Get {title} schema',
                        'description': description,
                        'tags': [k],
                        'operationId': f'get{k.capitalize()}Schema',
                        'parameters': [
                            {'$ref': '#/components/parameters/f'},
                            {'$ref': '#/components/parameters/lang'}
                        ],
                        'responses': {
                            '200': {'$ref': '#/components/responses/Queryables'},  # noqa
                            '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                            '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                            '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"},  # noqa
                        }
                    }
                }

                queryables_path = f'{collection_name_path}/queryables'

                paths[queryables_path] = {
                    'get': {
                        'summary': f'Get {title} queryables',
                        'description': description,
                        'tags': [k],
                        'operationId': f'get{k.capitalize()}Queryables',
                        'parameters': [
                            {'$ref': '#/components/parameters/f'},
                            {'$ref': '#/components/parameters/lang'}
                        ],
                        'responses': {
                            '200': {'$ref': '#/components/responses/Queryables'},  # noqa
                            '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                            '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                            '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"},  # noqa
                        }
                    }
                }

            if p.time_field is not None:
                paths[items_path]['get']['parameters'].append(
                    {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/datetime"})  # noqa

            for field, type_ in p.fields.items():

                if p.properties and field not in p.properties:
                    LOGGER.debug('Provider specified not to advertise property')  # noqa
                    continue

                if field == 'q' and ptype == 'record':
                    LOGGER.debug('q parameter already declared, skipping')
                    continue

                if type_ == 'date':
                    schema = {
                        'type': 'string',
                        'format': 'date'
                    }
                elif type_ == 'float':
                    schema = {
                        'type': 'number',
                        'format': 'float'
                    }
                elif type_ == 'long':
                    schema = {
                        'type': 'integer',
                        'format': 'int64'
                    }
                else:
                    schema = type_

                if schema.get('format') is None:
                    schema.pop('format', None)

                path_ = f'{collection_name_path}/items'
                paths[path_]['get']['parameters'].append({
                    'name': field,
                    'in': 'query',
                    'required': False,
                    'schema': schema,
                    'style': 'form',
                    'explode': False
                })

            paths[f'{collection_name_path}/items/{{featureId}}'] = {
                'get': {
                    'summary': f'Get {title} item by id',
                    'description': description,
                    'tags': [k],
                    'operationId': f'get{k.capitalize()}Feature',
                    'parameters': [
                        {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/featureId"},  # noqa
                        {'$ref': '#/components/parameters/crs'},  # noqa
                        {'$ref': '#/components/parameters/f'},
                        {'$ref': '#/components/parameters/lang'}
                    ],
                    'responses': {
                        '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/Feature"},  # noqa
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '404': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/NotFound"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                },
                'options': {
                    'summary': f'Options for {title} item by id',
                    'description': description,
                    'tags': [k],
                    'operationId': f'options{k.capitalize()}Feature',
                    'parameters': [
                        {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/featureId"}  # noqa
                    ],
                    'responses': {
                        '200': {'description': 'options response'}
                    }
                }
            }

            try:
                schema_ref = p.get_schema()
                paths[f'{collection_name_path}/items/{{featureId}}']['get']['responses']['200'] = {  # noqa
                    'content': {
                        schema_ref[0]: {
                            'schema': schema_ref[1]
                        }
                    }
                }
            except Exception as err:
                LOGGER.debug(err)

            if p.editable:
                LOGGER.debug('Provider is editable; adding put/delete')
                put_path = f'{collection_name_path}/items/{{featureId}}'  # noqa
                paths[put_path]['put'] = {  # noqa
                    'summary': f'Update {title} items',
                    'description': description,
                    'tags': [k],
                    'operationId': f'update{k.capitalize()}Features',
                    'parameters': [
                        {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/featureId"}  # noqa
                    ],
                    'requestBody': {
                        'description': 'Updates item in collection',
                        'content': {
                            'application/geo+json': {
                                'schema': {}
                            }
                        },
                        'required': True
                    },
                    'responses': {
                        '204': {'$ref': '#/components/responses/204'},
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }

                try:
                    schema_ref = p.get_schema(SchemaType.replace)
                    paths[put_path]['put']['requestBody']['content'][schema_ref[0]] = {  # noqa
                        'schema': schema_ref[1]
                    }
                except Exception as err:
                    LOGGER.debug(err)

                paths[f'{collection_name_path}/items/{{featureId}}']['delete'] = {  # noqa
                    'summary': f'Delete {title} items',
                    'description': description,
                    'tags': [k],
                    'operationId': f'delete{k.capitalize()}Features',
                    'parameters': [
                        {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/parameters/featureId"},  # noqa
                    ],
                    'responses': {
                        '200': {'description': 'Successful delete'},
                        '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                        '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                    }
                }

        except ProviderTypeError:
            LOGGER.debug('collection is not feature/item based')

    return [{'name': 'records'}, {'name': 'features'}], {'paths': paths}
