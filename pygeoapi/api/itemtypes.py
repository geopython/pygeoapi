# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Sander Schaminee <sander.schaminee@geocat.net>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2025 Tom Kralidis
# Copyright (c) 2025 Francesco Bartoli
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

from collections import ChainMap
from copy import deepcopy
from datetime import datetime
from http import HTTPStatus
import logging
from typing import Any, Tuple, Union
import urllib.parse

from pygeofilter.parsers.ecql import parse as parse_ecql_text
from pygeofilter.parsers.cql2_json import parse as parse_cql2_json
from pyproj.exceptions import CRSError

from pygeoapi import l10n
from pygeoapi.api import evaluate_limit
from pygeoapi.crs import (DEFAULT_CRS, DEFAULT_STORAGE_CRS,
                          create_crs_transform_spec, get_supported_crs_list,
                          modify_pygeofilter, transform_bbox,
                          set_content_crs_header)
from pygeoapi.formatter.base import FormatterSerializationError
from pygeoapi.linked_data import geojson2jsonld
from pygeoapi.plugin import load_plugin, PLUGINS
from pygeoapi.provider.base import (
    ProviderGenericError, ProviderTypeError, SchemaType)

from pygeoapi.util import (filter_providers_by_type, to_json,
                           filter_dict_by_key_value, str2bool,
                           get_provider_by_type, render_j2_template)

from . import (
    APIRequest, API, SYSTEM_LOCALE, F_JSON, FORMAT_TYPES, F_HTML, F_JSONLD,
    validate_bbox, validate_datetime
)

LOGGER = logging.getLogger(__name__)

OGC_RELTYPES_BASE = 'http://www.opengis.net/def/rel/ogc/1.0'


CONFORMANCE_CLASSES_FEATURES = [
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson',
    'http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs',
    'http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/queryables',
    'http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/queryables-query-parameters',  # noqa
    'http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/create-replace-delete',  # noqa
    'http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/schemas',
    'http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/core-roles-features'  # noqa
]

CONFORMANCE_CLASSES_RECORDS = [
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/sorting',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/opensearch',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/json',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/html'
]


def get_collection_queryables(api: API, request: Union[APIRequest, Any],
                              dataset: str | None = None
                              ) -> Tuple[dict, int, str]:
    """
    Provide collection queryables

    :param request: A request object
    :param dataset: name of collection

    :returns: tuple of headers, status code, content
    """

    domains = {}
    headers = request.get_response_headers(**api.api_headers)

    if any([dataset is None,
            dataset not in api.config['resources'].keys()]):

        msg = 'Collection not found'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Creating collection queryables')

    p = None
    for pt in ['feature', 'coverage', 'record']:
        try:
            LOGGER.debug(f'Loading {pt} provider')
            p = load_plugin('provider', get_provider_by_type(
                api.config['resources'][dataset]['providers'], pt))
            break
        except ProviderTypeError:
            LOGGER.debug(f'Providing type {pt} not found')

    if p is None:
        msg = 'queryables not available for this collection'
        return api.get_exception(

            HTTPStatus.BAD_REQUEST, headers, request.format,
            'NoApplicableError', msg)

    LOGGER.debug('Processing profile')
    profile = request.params.get('profile', '')

    LOGGER.debug('Processing properties')
    val = request.params.get('properties')
    if val is not None:
        properties = [x for x in val.split(',') if x]
        properties_to_check = set(p.properties) | set(p.fields.keys())

        if len(list(set(properties) - set(properties_to_check))) > 0:
            msg = 'unknown properties specified'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    else:
        properties = []

    queryables_id = f'{api.get_collections_url()}/{dataset}/queryables'

    if request.params:
        queryables_id += '?' + urllib.parse.urlencode(request.params)

    queryables = {
        'type': 'object',
        'title': l10n.translate(
            api.config['resources'][dataset]['title'], request.locale),
        'properties': {},
        '$schema': 'http://json-schema.org/draft/2019-09/schema',
        '$id': queryables_id
    }

    if p.fields:
        queryables['properties']['geometry'] = {
            'format': 'geometry-any',
            'x-ogc-role': 'primary-geometry'
        }

    if profile == 'actual-domain':
        try:
            domains, _ = p.get_domains(properties)
        except NotImplementedError:
            LOGGER.debug('Domains are not suported by this provider')
            domains = {}

    for k, v in p.fields.items():
        show_field = False
        if properties and k not in properties:
            continue
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
            if v['type'] == 'float':
                queryables['properties'][k]['type'] = 'number'
            if v.get('format') is not None:
                queryables['properties'][k]['format'] = v['format']
            if 'values' in v:
                queryables['properties'][k]['enum'] = v['values']

            if k == p.id_field:
                queryables['properties'][k]['x-ogc-role'] = 'id'
            if k == p.time_field:
                queryables['properties'][k]['x-ogc-role'] = 'primary-instant'  # noqa
            if domains.get(k):
                queryables['properties'][k]['enum'] = domains[k]

    if request.format == F_HTML:  # render
        tpl_config = api.get_dataset_templates(dataset)

        queryables['title'] = l10n.translate(
            api.config['resources'][dataset]['title'], request.locale)

        queryables['collections_path'] = api.get_collections_url()
        queryables['dataset_path'] = f'{api.get_collections_url()}/{dataset}'

        content = render_j2_template(api.tpl_config, tpl_config,
                                     'collections/queryables.html',
                                     queryables, request.locale)

        return headers, HTTPStatus.OK, content

    headers['Content-Type'] = 'application/schema+json'

    return headers, HTTPStatus.OK, to_json(queryables, api.pretty_print)


def get_collection_items(
        api: API, request: Union[APIRequest, Any],
        dataset: str | None = None) -> Tuple[dict, int, str]:
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
    except ValueError:
        msg = 'offset value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        offset = 0

    LOGGER.debug('Processing limit parameter')
    if api.config['server'].get('limit') is not None:
        msg = ('server.limit is no longer supported! '
               'Please use limits at the server or collection '
               'level (RFC5)')
        LOGGER.warning(msg)
    try:
        limit = evaluate_limit(request.params.get('limit'),
                               api.config['server'].get('limits', {}),
                               collections[dataset].get('limits', {}))
    except ValueError as err:
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', str(err))

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
                provider_def, query_crs_uri
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

        supported_crs_list = get_supported_crs_list(provider_def)
        if bbox_crs not in supported_crs_list:
            msg = f'bbox-crs {bbox_crs} not supported for this collection'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'NoApplicableCode', msg)
    elif len(bbox) > 0:
        # bbox but no bbox-crs param: assume bbox is in default CRS
        bbox_crs = DEFAULT_STORAGE_CRS

    # Transform bbox to storage_crs
    # when bbox-crs different from storage_crs.
    if len(bbox) > 0:
        try:
            # Get a pyproj CRS instance for the Collection's Storage CRS
            storage_crs = provider_def.get('storage_crs', DEFAULT_STORAGE_CRS)

            # Do the (optional) Transform to the Storage CRS
            bbox = transform_bbox(bbox, bbox_crs, storage_crs)
        except CRSError as e:
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'NoApplicableCode', str(e))

    LOGGER.debug('processing property parameters')
    for k, v in request.params.items():
        include_query_param = False
        if k not in reserved_fieldnames:
            if k in list(p.fields.keys()) or p.include_extra_query_parameters:
                include_query_param = True

        if include_query_param:
            LOGGER.debug(f'Including query parameter {k}={v}')
            properties.append((k, v))
        else:
            LOGGER.debug(f'Discarding query parameter {k}={v}')

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
            msg = 'Bad CQL text'
            LOGGER.error(f'{msg}: {cql_text}')
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    elif request.data:
        try:
            request_data = request.data.decode()
            filter_ = parse_cql2_json(request_data)
            filter_ = modify_pygeofilter(
                filter_,
                filter_crs_uri=filter_crs_uri,
                storage_crs_uri=provider_def.get('storage_crs'),
                geometry_column_name=provider_def.get('geom_field'),
            )
        except Exception:
            msg = 'Bad CQL JSON'
            LOGGER.error(f'{msg}: {request_data}')
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    else:
        filter_ = None

    LOGGER.debug('Processing filter-lang parameter')
    filter_lang = request.params.get('filter-lang')
    # Currently only cql-text is handled, but it is optional
    if filter_lang not in [None, 'cql-json', 'cql-text']:
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

    if 'links' not in content:
        content['links'] = []

    # TODO: translate titles
    uri = f'{api.get_collections_url()}/{dataset}/items'
    content['links'].extend([{
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
    }])

    next_link = False
    prev_link = False

    if 'next' in [link['rel'] for link in content['links']]:
        LOGGER.debug('Using next link from provider')
    else:
        if content.get('numberMatched', -1) > (limit + offset):
            next_link = True
        elif len(content['features']) == limit:
            next_link = True

        if offset > 0:
            prev_link = True

    if prev_link:
        prev = max(0, offset - limit)
        content['links'].append(
            {
                'type': 'application/geo+json',
                'rel': 'prev',
                'title': l10n.translate('Items (prev)', request.locale),
                'href': f'{uri}?offset={prev}{serialized_query_params}'
            })

    if next_link:
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
        tpl_config = api.get_dataset_templates(dataset)
        # For constructing proper URIs to items

        content['itemtype'] = p.type
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
        content = render_j2_template(api.tpl_config, tpl_config,
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

        return headers, HTTPStatus.OK, content

    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def manage_collection_item(
        api: API, request: APIRequest,
        action: str, dataset: str,
        identifier: str | None = None) -> Tuple[dict, int, str]:
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
                        dataset: str, identifier: str
                        ) -> Tuple[dict, int, str]:
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
                provider_def, query_crs_uri
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
        tpl_config = api.get_dataset_templates(dataset)
        content['title'] = l10n.translate(collections[dataset]['title'],
                                          request.locale)
        content['id_field'] = p.id_field
        if p.uri_field is not None:
            content['uri_field'] = p.uri_field
        if p.title_field is not None:
            content['title_field'] = l10n.translate(p.title_field,
                                                    request.locale)
        content['collections_path'] = api.get_collections_url()

        content = render_j2_template(api.tpl_config, tpl_config,
                                     'collections/items/item.html',
                                     content, request.locale)
        return headers, HTTPStatus.OK, content

    elif request.format == F_JSONLD:
        content = geojson2jsonld(
            api, content, dataset, uri, (p.uri_field or 'id')
        )

        return headers, HTTPStatus.OK, content

    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


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

    limit = {
        'name': 'limit',
        'in': 'query',
        'description': 'The optional limit parameter limits the number of items that are presented in the response document',  # noqa
        'required': False,
        'schema': {
            'type': 'integer',
            'minimum': 1,
            'maximum': 10000,
            'default': 100
        },
        'style': 'form',
        'explode': False
    }

    profile = {
        'name': 'profile',
        'in': 'query',
        'description': 'The profile to be applied to a given request',
        'required': False,
        'style': 'form',
        'explode': False,
        'schema': {
            'type': 'string',
            'enum': ['actual-domain', 'valid-domain']
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

            coll_limit = _derive_limit(
                deepcopy(limit), cfg['server'].get('limits', {}),
                v.get('limits', {})
            )

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
                        coll_limit,
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

            # TODO: update feature POSTs once updated in OGC API - Features
            # https://github.com/opengeospatial/ogcapi-features/issues/771
            paths[items_path]['post'] = {
                'summary': f'Get {title} items with CQL2',
                'description': description,
                'tags': [k],
                'operationId': f'getCQL2{k.capitalize()}Features',
                'requestBody': {
                    'description': 'Get items with CQL2',
                    'content': {
                        'application/json': {  # CQL2
                            'schema': {
                                '$ref': OPENAPI_YAML['cql2']
                            }
                        }
                    },
                    'required': True
                },
                'responses': {
                    '200': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/Features"},  # noqa
                    '400': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/InvalidParameter"},  # noqa
                    '500': {'$ref': f"{OPENAPI_YAML['oapif-1']}#/components/responses/ServerError"}  # noqa
                }
            }

            if p.editable:
                LOGGER.debug('Provider is editable; adding post')

                paths[items_path]['post']['operationId'] = f'getCQL2OrAdd{k.capitalize()}Features'  # noqa

                val = paths[items_path]['post']['summary']
                paths[items_path]['post']['summary'] = f'{val} or add item (see media type)'  # noqa

                val = paths[items_path]['post']['requestBody']['description']
                paths[items_path]['post']['requestBody']['description'] = f'{val} or add item to collection'  # noqa

                paths[items_path]['post']['requestBody']['content']['application/geo+json'] = {  # noqa
                    'schema': {}
                }

                paths[items_path]['post']['responses']['201'] = {
                    'description': 'Successful creation'
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
                            coll_properties,
                            {'$ref': '#/components/parameters/f'},
                            profile,
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


def _derive_limit(limit_object, server_limits, collection_limits) -> dict:
    """
    Helper function to derive a limit object for a given collection

    :param limit_object: OpenAPI limit parameter
    :param server_limits: server level limits configuration
    :param collection_limits: collection level limits configuration

    :returns: updated limit object
    """

    effective_limits = ChainMap(collection_limits, server_limits)

    default_limit = effective_limits.get('default_items', 10)
    max_limit = effective_limits.get('max_items', 10)

    limit_object['schema']['default'] = default_limit
    limit_object['schema']['maximum'] = max_limit

    text = f' (maximum={max_limit}, default={default_limit}).'
    limit_object['description'] += text

    return limit_object
