# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Sander Schaminee <sander.schaminee@geocat.net>
#
# Copyright (c) 2021 Tom Kralidis
# Copyright (c) 2020 Francesco Bartoli
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
""" Root level code of pygeoapi, parsing content provided by web framework.
Returns content from plugins and sets responses.
"""

from datetime import datetime, timezone
from functools import partial
import json
import logging
import os
import uuid
import re
import urllib.parse
from copy import deepcopy
from typing import Union, Any
from collections import OrderedDict

from dateutil.parser import parse as dateparse
from shapely.wkt import loads as shapely_loads
from shapely.errors import WKTReadingError
import pytz

from pygeoapi import __version__
from pygeoapi import l10n
from pygeoapi.linked_data import (geojson2geojsonld, jsonldify,
                                  jsonldify_collection)
from pygeoapi.log import setup_logger
from pygeoapi.process.base import (
    ProcessorExecuteError
)
from pygeoapi.plugin import load_plugin, PLUGINS
from pygeoapi.provider.base import (
    ProviderGenericError, ProviderConnectionError, ProviderNotFoundError,
    ProviderInvalidQueryError, ProviderNoDataError, ProviderQueryError,
    ProviderItemNotFoundError, ProviderTypeError)

from pygeoapi.provider.tile import (ProviderTileNotFoundError,
                                    ProviderTileQueryError,
                                    ProviderTilesetIdNotFoundError)
from pygeoapi.util import (dategetter, DATETIME_FORMAT,
                           filter_dict_by_key_value, get_provider_by_type,
                           get_provider_default, get_typed_value, JobStatus,
                           json_serial, render_j2_template, str2bool,
                           TEMPLATES, to_json)

LOGGER = logging.getLogger(__name__)

#: Return headers for requests (e.g:X-Powered-By)
HEADERS = {
    'Content-Type': 'application/json',
    'X-Powered-By': 'pygeoapi {}'.format(__version__)
}

#: Formats allowed for ?f= requests
FORMATS = OrderedDict((
    ('html', 'text/html'),
    ('jsonld', 'application/ld+json'),
    ('json', 'application/json'),
))

CONFORMANCE = [
    'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson',
    'http://www.opengis.net/spec/ogcapi_coverages-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/oas30',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/req/core',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/req/collections',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/sorting',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/opensearch',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/json',
    'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/core'
]

OGC_RELTYPES_BASE = 'http://www.opengis.net/def/rel/ogc/1.0'


def pre_process(func):
    """ Decorator that transforms the incoming Request instance specific to the
    web framework (Flask, Starlette) into an APIRequest instance.

    :param func: decorated function

    :returns: `func`
    """

    def inner(*args):
        cls = args[0]
        req = APIRequest(args[1], getattr(cls, 'locales', set()))
        if len(args) > 2:
            args = args[2:]
            return func(cls, req, *args)
        else:
            return func(cls, req)

    return inner


class APIRequest:
    """ Transforms an incoming server-specific Request into an object
    with some generic helper methods and properties.

    :param request:             The web platform specific Request instance.
    :param supported_locales:   List or set of supported Locale instances.
    """
    def __init__(self, request, supported_locales):
        # Get request data (if any)
        self._data = getattr(request, 'data', None) or None

        # Copy request query parameters
        self._args = self._get_params(request)

        # Get path info
        self._path_info = request.headers.environ['PATH_INFO'].strip('/')

        # Extract locale from params or headers
        # _l_param stores a boolean -> True if language was found in query str
        self._raw_locale, self._locale, self._l_param = \
            self._get_locale(request.headers, supported_locales)

        # Determine format
        self._format = self._get_format(request.headers)

    @staticmethod
    def _get_params(request):
        """ Extracts the query parameters from the Request object.

        :param request: A Flask or Starlette Request instance
        :returns:       ImmutableMultiDict or empty dict
        """
        if hasattr(request, 'args'):
            # Return ImmutableMultiDict from Flask request
            return request.args
        elif hasattr(request, 'query_params'):
            # Return ImmutableMultiDict from Starlette request
            return request.query_params
        LOGGER.debug('No query parameters found')
        return {}

    def _get_locale(self, headers, supported_locales):
        """ Detects locale from "l=<language>" or Accept-Language header.
        Returns a tuple of (raw, locale, True) if found in the query params.
        Returns a tuple of (raw, locale, False) if found in headers.
        Returns a tuple of (raw, default locale, False) if not found.

        :param headers:             A dict with Request headers
        :param supported_locales:   List or set of supported Locale instances
        :returns:                   A tuple of (Locale, bool)
        """
        raw = None
        try:
            default_locale = l10n.str2locale(supported_locales[0])
        except (TypeError, IndexError, l10n.LocaleError) as err:
            # This should normally not happen, since the API class already
            # loads the supported languages from the config, which raises
            # a LocaleError if any of these languages are invalid.
            LOGGER.error(err)
            raise ValueError(f"{self.__class__.__name__} must be initialized"
                             f"with a list of valid supported locales")

        for func, mapping in ((l10n.locale_from_params, self._args),
                              (l10n.locale_from_headers, headers)):
            loc_str = func(mapping)
            if loc_str:
                if not raw:
                    # This is the first-found locale string: set as raw
                    raw = loc_str
                # Check of locale string is a good match for the UI
                loc = l10n.best_match(loc_str, supported_locales)
                precedence = func is l10n.locale_from_params
                if loc != default_locale or precedence:
                    return raw, loc, precedence

        return raw or supported_locales[0], default_locale, False

    def _get_format(self, headers) -> Union[str, None]:
        """
        Get Request format type from query parameters or headers.

        :param headers: Dict of Request headers
        :returns:       format value or None if not found/specified
        """

        # Optional f=html or f=json query param
        # Overrides Accept header and might differ from FORMATS
        format_ = (self._args.get('f') or '').strip()
        if format_:
            return format_

        # Format not specified: get from Accept headers (MIME types)
        # e.g. format_ = 'text/html'
        for h in (v.strip() for k, v in headers.items() if k.lower() == 'accept'):  # noqa
            for fmt, mime in FORMATS.items():
                # basic support for complex types (i.e. with "q=0.x")
                types_ = (t.split(';')[0].strip() for t in h.split(',') if t)
                if mime.strip() in types_:
                    format_ = fmt
                    break

        return format_ or None

    @property
    def data(self):
        """ Returns the additional data send with the Request. """
        return self._data

    @property
    def params(self):
        """ Returns the Request query parameters dict. """
        return self._args

    @property
    def path_info(self):
        """ Returns the web server request path info part. """
        return self._path_info

    @property
    def locale(self) -> l10n.Locale:
        """ Returns the user-defined locale from the request object.
        If no locale has been defined or if it is invalid,
        the default server locale is returned.

        .. note::   The locale here determines the language in which pygeoapi
                    should return its responses. This may not be the language
                    that the user requested. It may also not be the language
                    that is supported by a collection provider, for example.
                    For this reason, you should pass the `raw_locale` property
                    to all plugins, so (e.g.) providers can determine the best
                    matching locale themselves.

        :returns:   babel.core.Locale
        """
        return self._locale

    @property
    def raw_locale(self) -> str:
        """ Returns the raw locale string from the Request object.
        If no "l" query parameter or Accept-Language header was found,
        the first (= default) language tag from the server configuration is
        returned.
        Pass this value to the :func:`load_plugin` function to let the plugin
        determine a best match for the locale, which may be different from the
        locale used by pygeoapi's UI.

        :returns:   a locale string
        """
        return self._raw_locale

    @property
    def format(self) -> Union[str, None]:
        """ Returns the content type format from the
        request query parameters or headers.

        :returns:   Format name or None
        """
        return self._format

    def is_valid(self, additional_formats=None) -> bool:
        """ Returns True if:
        - the format is not set (None)
        - the requested format is supported
        - the requested format exists in a list if additional formats

        :param additional_formats:  Optional additional supported formats list
        :returns:   A boolean
        """
        if not self._format:
            return True
        if self._format in FORMATS.keys():
            return True
        if self._format in (f.lower() for f in (additional_formats or ())):
            return True
        return False

    def get_response_headers(self, content_type: str = None,
                             locale: l10n.Locale = None) -> dict:
        """ Prepares and returns a dictionary with Response object headers.
        Adds a 'Content-Language' header if the Request had a valid
        language query parameter or if a `locale` override is provided.
        If the user does not specify `content_type`, the 'Content-Type` header
        is based on the `format` property. If that is invalid, the default
        'application/json' is used.

        :param content_type:    An optional Content-Type header override.
        :param locale:          An optional Locale for the Content-Language.
        :returns:               A header dict
        """
        headers = HEADERS.copy()
        if self._raw_locale or locale:
            # Add a Content-Language response header if the user requested
            # a specific language or if the locale override is applied
            response_loc = l10n.locale2str(locale if locale else self._locale)
            headers['Content-Language'] = response_loc
        if content_type:
            # Set custom MIME type if specified
            headers['Content-Type'] = content_type
        elif self.is_valid() and self.format:
            # Set MIME type for valid formats
            headers['Content-Type'] = FORMATS[self.format]
        return headers


class API:
    """API object"""

    def __init__(self, config):
        """
        constructor

        :param config: configuration dict

        :returns: `pygeoapi.API` instance
        """

        self.config = config
        self.config['server']['url'] = self.config['server']['url'].rstrip('/')

        # Process language settings
        self.locales = l10n.get_locales(config)
        self.default_locale = self.locales[0]

        if 'templates' not in self.config['server']:
            self.config['server']['templates'] = TEMPLATES

        if 'pretty_print' not in self.config['server']:
            self.config['server']['pretty_print'] = False

        self.pretty_print = self.config['server']['pretty_print']

        setup_logger(self.config['logging'])

        # TODO: add as decorator
        if 'manager' in self.config['server']:
            manager_def = self.config['server']['manager']
        else:
            LOGGER.info('No process manager defined; starting dummy manager')
            manager_def = {
                'name': 'Dummy',
                'connection': None,
                'output_dir': None
            }

        LOGGER.debug('Loading process manager {}'.format(manager_def['name']))
        self.manager = load_plugin('process_manager', manager_def)
        LOGGER.info('Process manager plugin loaded')

    @pre_process
    @jsonldify
    def landing_page(self, request: Union[APIRequest, Any]):
        """
        Provide API

        :param request: A request object

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        fcm = {
            'links': [],
            'title': l10n.translate(
                self.config['metadata']['identification']['title'],
                request.locale),
            'description':
                l10n.translate(
                    self.config['metadata']['identification']['description'],
                    request.locale)
        }

        LOGGER.debug('Creating links')
        # TODO: put title text in config or translatable files?
        fcm['links'] = [{
            'rel': 'self' if request.format in (None, 'json') else 'alternate',
            'type': FORMATS['json'],
            'title': 'This document as JSON',
            'href': '{}?f=json'.format(self.config['server']['url'])
        }, {
            'rel': 'self' if request.format == 'jsonld' else 'alternate',
            'type': FORMATS['jsonld'],
            'title': 'This document as RDF (JSON-LD)',
            'href': '{}?f=jsonld'.format(self.config['server']['url'])
        }, {
            'rel': 'self' if request.format == 'html' else 'alternate',
            'type': FORMATS['html'],
            'title': 'This document as HTML',
            'href': '{}?f=html'.format(self.config['server']['url']),
            'hreflang': self.default_locale
        }, {
            'rel': 'service-desc',
            'type': 'application/vnd.oai.openapi+json;version=3.0',
            'title': 'The OpenAPI definition as JSON',
            'href': '{}/openapi'.format(self.config['server']['url'])
        }, {
            'rel': 'service-doc',
            'type': 'text/html',
            'title': 'The OpenAPI definition as HTML',
            'href': '{}/openapi?f=html'.format(self.config['server']['url']),
            'hreflang': self.default_locale
        }, {
            'rel': 'conformance',
            'type': 'application/json',
            'title': 'Conformance',
            'href': '{}/conformance'.format(self.config['server']['url'])
        }, {
            'rel': 'data',
            'type': 'application/json',
            'title': 'Collections',
            'href': '{}/collections'.format(self.config['server']['url'])
        }]

        headers = request.get_response_headers()
        if request.format == 'html':  # render

            fcm['processes'] = False
            fcm['stac'] = False

            if filter_dict_by_key_value(self.config['resources'],
                                        'type', 'process'):
                fcm['processes'] = True

            if filter_dict_by_key_value(self.config['resources'],
                                        'type', 'stac-collection'):
                fcm['stac'] = True

            fcm['keywords'] = l10n.translate(
                self.config['metadata']['identification']['keywords'],
                request.locale)

            content = render_j2_template(self.config, 'landing_page.html', fcm)
            return headers, 200, content

        if request.format == 'jsonld':
            return headers, 200, to_json(self.fcmld, self.pretty_print)  # noqa

        return headers, 200, to_json(fcm, self.pretty_print)

    @pre_process
    def openapi(self, request: Union[APIRequest, Any], openapi):
        """
        Provide OpenAPI document

        :param request: A request object
        :param openapi: dict of OpenAPI definition

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        headers = request.get_response_headers()
        if request.format == 'html':
            path = '/'.join([self.config['server']['url'].rstrip('/'),
                            'openapi'])
            data = {
                'openapi-document-path': path
            }
            content = render_j2_template(self.config, 'openapi.html', data)
            return headers, 200, content

        headers['Content-Type'] = 'application/vnd.oai.openapi+json;version=3.0'  # noqa

        if isinstance(openapi, dict):
            return headers, 200, to_json(openapi, self.pretty_print)
        else:
            return headers, 200, openapi.read()

    @pre_process
    def conformance(self, request: Union[APIRequest, Any]):
        """
        Provide conformance definition

        :param request: A request object

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        conformance = {
            'conformsTo': CONFORMANCE
        }

        headers = request.get_response_headers()
        if request.format == 'html':  # render
            content = render_j2_template(self.config, 'conformance.html',
                                         conformance)
            return headers, 200, content

        return headers, 200, to_json(conformance, self.pretty_print)

    @pre_process
    @jsonldify
    def describe_collections(self, request: Union[APIRequest, Any], dataset=None):  # noqa
        """
        Provide collection metadata

        :param request: A request object
        :param dataset: name of collection

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        fcm = {
            'collections': [],
            'links': []
        }

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if all([dataset is not None, dataset not in collections.keys()]):
            msg = 'Invalid collection'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Creating collections')
        for k, v in collections.items():
            collection_data = get_provider_default(v['providers'])
            collection_data_type = collection_data['type']

            collection_data_format = None

            if 'format' in collection_data:
                collection_data_format = collection_data['format']

            collection = {
                'id': k,
                'title': l10n.translate(v['title'], request.locale),
                'description': l10n.translate(v['description'], request.locale),  # noqa
                'keywords': l10n.translate(v['keywords'], request.locale),
                'links': []
            }

            bbox = v['extents']['spatial']['bbox']
            # The output should be an array of bbox, so if the user only
            # provided a single bbox, wrap it in a array.
            if not isinstance(bbox[0], list):
                bbox = [bbox]
            collection['extent'] = {
                'spatial': {
                    'bbox': bbox
                }
            }
            if 'crs' in v['extents']['spatial']:
                collection['extent']['spatial']['crs'] = \
                    v['extents']['spatial']['crs']

            t_ext = v.get('extents', {}).get('temporal', {})
            if t_ext:
                begins = dategetter('begin', t_ext)
                ends = dategetter('end', t_ext)
                collection['extent']['temporal'] = {
                    'interval': [[begins, ends]]
                }
                if 'trs' in t_ext:
                    collection['extent']['temporal']['trs'] = t_ext['trs']

            for link in l10n.translate(v['links'], request.locale):
                lnk = {
                    'type': link['type'],
                    'rel': link['rel'],
                    'title': link['title'],
                    'href': link['href']
                }
                if 'hreflang' in link:
                    lnk['hreflang'] = link['hreflang']

                collection['links'].append(lnk)

            LOGGER.debug('Adding JSON and HTML link relations')
            collection['links'].append({
                'type': 'application/json',
                'rel': 'self' if not request.format
                or request.format == 'json' else 'alternate',
                'title': 'This document as JSON',
                'href': '{}/collections/{}?f=json'.format(
                    self.config['server']['url'], k)
            })
            collection['links'].append({
                'type': 'application/ld+json',
                'rel': 'self' if request.format == 'jsonld' else 'alternate',
                'title': 'This document as RDF (JSON-LD)',
                'href': '{}/collections/{}?f=jsonld'.format(
                    self.config['server']['url'], k)
            })
            collection['links'].append({
                'type': 'text/html',
                'rel': 'self' if request.format == 'html' else 'alternate',
                'title': 'This document as HTML',
                'href': '{}/collections/{}?f=html'.format(
                    self.config['server']['url'], k)
            })

            if collection_data_type in ['feature', 'record']:
                collection['itemType'] = collection_data_type
                LOGGER.debug('Adding feature/record based links')
                collection['links'].append({
                    'type': 'application/json',
                    'rel': 'queryables',
                    'title': 'Queryables for this collection as JSON',
                    'href': '{}/collections/{}/queryables?f=json'.format(
                        self.config['server']['url'], k)
                })
                collection['links'].append({
                    'type': 'text/html',
                    'rel': 'queryables',
                    'title': 'Queryables for this collection as HTML',
                    'href': '{}/collections/{}/queryables?f=html'.format(
                        self.config['server']['url'], k)
                })
                collection['links'].append({
                    'type': 'application/geo+json',
                    'rel': 'items',
                    'title': 'items as GeoJSON',
                    'href': '{}/collections/{}/items?f=json'.format(
                        self.config['server']['url'], k)
                })
                collection['links'].append({
                    'type': 'application/ld+json',
                    'rel': 'items',
                    'title': 'items as RDF (GeoJSON-LD)',
                    'href': '{}/collections/{}/items?f=jsonld'.format(
                        self.config['server']['url'], k)
                })
                collection['links'].append({
                    'type': 'text/html',
                    'rel': 'items',
                    'title': 'Items as HTML',
                    'href': '{}/collections/{}/items?f=html'.format(
                        self.config['server']['url'], k)
                })

            elif collection_data_type == 'coverage':
                LOGGER.debug('Adding coverage based links')
                collection['links'].append({
                    'type': 'application/json',
                    'rel': 'collection',
                    'title': 'Detailed Coverage metadata in JSON',
                    'href': '{}/collections/{}?f=json'.format(
                        self.config['server']['url'], k)
                })
                collection['links'].append({
                    'type': 'text/html',
                    'rel': 'collection',
                    'title': 'Detailed Coverage metadata in HTML',
                    'href': '{}/collections/{}?f=html'.format(
                        self.config['server']['url'], k)
                })
                coverage_url = '{}/collections/{}/coverage'.format(
                        self.config['server']['url'], k)

                collection['links'].append({
                    'type': 'application/json',
                    'rel': '{}/coverage-domainset'.format(OGC_RELTYPES_BASE),
                    'title': 'Coverage domain set of collection in JSON',
                    'href': '{}/domainset?f=json'.format(coverage_url)
                })
                collection['links'].append({
                    'type': 'text/html',
                    'rel': '{}/coverage-domainset'.format(OGC_RELTYPES_BASE),
                    'title': 'Coverage domain set of collection in HTML',
                    'href': '{}/domainset?f=html'.format(coverage_url)
                })
                collection['links'].append({
                    'type': 'application/json',
                    'rel': '{}/coverage-rangetype'.format(OGC_RELTYPES_BASE),
                    'title': 'Coverage range type of collection in JSON',
                    'href': '{}/rangetype?f=json'.format(coverage_url)
                })
                collection['links'].append({
                    'type': 'text/html',
                    'rel': '{}/coverage-rangetype'.format(OGC_RELTYPES_BASE),
                    'title': 'Coverage range type of collection in HTML',
                    'href': '{}/rangetype?f=html'.format(coverage_url)
                })
                collection['links'].append({
                    'type': 'application/prs.coverage+json',
                    'rel': '{}/coverage'.format(OGC_RELTYPES_BASE),
                    'title': 'Coverage data',
                    'href': '{}/collections/{}/coverage?f=json'.format(
                        self.config['server']['url'], k)
                })
                if collection_data_format is not None:
                    collection['links'].append({
                        'type': collection_data_format['mimetype'],
                        'rel': '{}/coverage'.format(OGC_RELTYPES_BASE),
                        'title': 'Coverage data as {}'.format(
                            collection_data_format['name']),
                        'href': '{}/collections/{}/coverage?f={}'.format(
                            self.config['server']['url'], k,
                            collection_data_format['name'])
                    })
                if dataset is not None:
                    LOGGER.debug('Creating extended coverage metadata')
                    try:
                        p = load_plugin('provider', get_provider_by_type(
                            self.config['resources'][k]['providers'],
                            'coverage'), request.locale)
                        collection['crs'] = [p.crs]
                        collection['domainset'] = p.get_coverage_domainset()
                        collection['rangetype'] = p.get_coverage_rangetype()
                    except ProviderConnectionError:
                        msg = 'connection error (check logs)'
                        return self.get_exception(500, headers, request.format,
                                                  'NoApplicableCode', msg)
                    except ProviderTypeError:
                        pass

            try:
                tile = get_provider_by_type(v['providers'], 'tile')
            except ProviderTypeError:
                tile = None

            if tile:
                LOGGER.debug('Adding tile links')
                collection['links'].append({
                    'type': 'application/json',
                    'rel': 'tiles',
                    'title': 'Tiles as JSON',
                    'href': '{}/collections/{}/tiles?f=json'.format(
                        self.config['server']['url'], k)
                })
                collection['links'].append({
                    'type': 'text/html',
                    'rel': 'tiles',
                    'title': 'Tiles as HTML',
                    'href': '{}/collections/{}/tiles?f=html'.format(
                        self.config['server']['url'], k)
                })

            try:
                edr = get_provider_by_type(v['providers'], 'edr')
            except ProviderTypeError:
                edr = None

            if edr and dataset is not None:
                LOGGER.debug('Adding EDR links')
                try:
                    p = load_plugin('provider', get_provider_by_type(
                        self.config['resources'][dataset]['providers'],
                        'edr'))
                    parameters = p.get_fields()
                    if parameters:
                        collection['parameters'] = {}
                        for f in parameters['field']:
                            collection['parameters'][f['id']] = f

                    for qt in p.get_query_types():
                        collection['links'].append({
                            'type': 'text/json',
                            'rel': 'data',
                            'title': '{} query for this collection as JSON'.format(qt),  # noqa
                            'href': '{}/collections/{}/{}?f=json'.format(
                                self.config['server']['url'], k, qt)
                        })
                        collection['links'].append({
                            'type': 'text/html',
                            'rel': 'data',
                            'title': '{} query for this collection as HTML'.format(qt),  # noqa
                            'href': '{}/collections/{}/{}?f=html'.format(
                                self.config['server']['url'], k, qt)
                        })
                except ProviderConnectionError:
                    msg = 'connection error (check logs)'
                    return self.get_exception(
                        500, headers, request.format, 'NoApplicableCode', msg)
                except ProviderTypeError:
                    pass

            if dataset is not None and k == dataset:
                fcm = collection
                break

            fcm['collections'].append(collection)

        if dataset is None:
            fcm['links'].append({
                'type': 'application/json',
                'rel': 'self' if not format
                or request.format == 'json' else 'alternate',
                'title': 'This document as JSON',
                'href': '{}/collections?f=json'.format(
                    self.config['server']['url'])
            })
            fcm['links'].append({
                'type': 'application/ld+json',
                'rel': 'self' if request.format == 'jsonld' else 'alternate',
                'title': 'This document as RDF (JSON-LD)',
                'href': '{}/collections?f=jsonld'.format(
                    self.config['server']['url'])
            })
            fcm['links'].append({
                'type': 'text/html',
                'rel': 'self' if request.format == 'html' else 'alternate',
                'title': 'This document as HTML',
                'href': '{}/collections?f=html'.format(
                    self.config['server']['url'])
            })

        if request.format == 'html':  # render

            if dataset is not None:
                content = render_j2_template(self.config,
                                             'collections/collection.html',
                                             fcm)
            else:
                content = render_j2_template(self.config,
                                             'collections/index.html', fcm)

            return headers, 200, content

        if request.format == 'jsonld':
            jsonld = self.fcmld.copy()  # noqa
            if dataset is not None:
                jsonld['dataset'] = jsonldify_collection(self, fcm,
                                                         request.locale)
            else:
                jsonld['dataset'] = [
                    jsonldify_collection(self, c, request.locale)
                    for c in fcm.get('collections', [])
                ]
            return headers, 200, to_json(jsonld, self.pretty_print)

        return headers, 200, to_json(fcm, self.pretty_print)

    @pre_process
    @jsonldify
    def get_collection_queryables(self, request: Union[APIRequest, Any], dataset=None):  # noqa
        """
        Provide collection queryables

        :param request: A request object
        :param dataset: name of collection

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        if any([dataset is None,
                dataset not in self.config['resources'].keys()]):

            msg = 'Invalid collection'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Creating collection queryables')
        try:
            LOGGER.debug('Loading feature provider')
            p = load_plugin('provider', get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'feature'),
                request.raw_locale)
        except ProviderTypeError:
            LOGGER.debug('Loading record provider')
            p = load_plugin('provider', get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'record'),
                request.raw_locale)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)

        queryables = {
            'type': 'object',
            'title': self.config['resources'][dataset]['title'],
            'properties': {},
            '$schema': 'http://json-schema.org/draft/2019-09/schema',
            '$id': '{}/collections/{}/queryables'.format(
                self.config['server']['url'], dataset)
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
                if 'values' in v:
                    queryables['properties'][k]['enum'] = v['values']

        if request.format == 'html':  # render
            queryables['title'] = l10n.translate(
                self.config['resources'][dataset]['title'], request.locale)
            content = render_j2_template(self.config,
                                         'collections/queryables.html',
                                         queryables)

            return headers, 200, content

        return headers, 200, to_json(queryables, self.pretty_print)

    @pre_process
    def get_collection_items(self, request: Union[APIRequest, Any], dataset, pathinfo=None):  # noqa
        """
        Queries collection

        :param request: A request object
        :param dataset: dataset name
        :param pathinfo: path location

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid(PLUGINS['formatter'].keys()):
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        properties = []
        reserved_fieldnames = ['bbox', 'f', 'l', 'limit', 'startindex',
                               'resulttype', 'datetime', 'sortby',
                               'properties', 'skipGeometry', 'q']

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            msg = 'Invalid collection'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Processing startindex parameter')
        try:
            startindex = int(request.params.get('startindex'))
            if startindex < 0:
                msg = 'startindex value should be positive or zero'
                return self.get_exception(
                    400, headers, request.format, 'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            startindex = 0
        except ValueError:
            msg = 'startindex value should be an integer'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing limit parameter')
        try:
            limit = int(request.params.get('limit'))
            # TODO: We should do more validation, against the min and max
            # allowed by the server configuration
            if limit <= 0:
                msg = 'limit value should be strictly positive'
                return self.get_exception(
                    400, headers, request.format, 'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            limit = int(self.config['server']['limit'])
        except ValueError:
            msg = 'limit value should be an integer'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

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
                return self.get_exception(
                    400, headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing datetime parameter')
        datetime_ = request.params.get('datetime')
        try:
            datetime_ = validate_datetime(collections[dataset]['extents'],
                                          datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('processing q parameter')
        q = request.params.get('q') or None

        LOGGER.debug('Loading provider')

        try:
            p = load_plugin('provider', get_provider_by_type(
                collections[dataset]['providers'], 'feature'),
                request.raw_locale)
        except ProviderTypeError:
            try:
                p = load_plugin('provider', get_provider_by_type(
                    collections[dataset]['providers'], 'record'),
                    request.raw_locale)
            except ProviderTypeError:
                msg = 'Invalid provider type'
                return self.get_exception(
                    400, headers, request.format, 'NoApplicableCode', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)

        LOGGER.debug('processing property parameters')
        for k, v in request.params.items():
            if k not in reserved_fieldnames and k not in p.fields.keys():
                msg = 'unknown query parameter: {}'.format(k)
                return self.get_exception(
                    400, headers, request.format, 'InvalidParameterValue', msg)
            elif k not in reserved_fieldnames and k in p.fields.keys():
                LOGGER.debug('Add property filter {}={}'.format(k, v))
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
                    return self.get_exception(
                        400, headers, request.format,
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
                return self.get_exception(
                    400, headers, request.format, 'InvalidParameterValue', msg)
        else:
            select_properties = []

        LOGGER.debug('processing skipGeometry parameter')
        val = request.params.get('skipGeometry')
        if val is not None:
            skip_geometry = str2bool(val)
        else:
            skip_geometry = False

        LOGGER.debug('Querying provider')
        LOGGER.debug('startindex: {}'.format(startindex))
        LOGGER.debug('limit: {}'.format(limit))
        LOGGER.debug('resulttype: {}'.format(resulttype))
        LOGGER.debug('sortby: {}'.format(sortby))
        LOGGER.debug('bbox: {}'.format(bbox))
        LOGGER.debug('datetime: {}'.format(datetime_))
        LOGGER.debug('properties: {}'.format(select_properties))
        LOGGER.debug('skipGeometry: {}'.format(skip_geometry))
        LOGGER.debug('q: {}'.format(q))

        try:
            content = p.query(startindex=startindex, limit=limit,
                              resulttype=resulttype, bbox=bbox,
                              datetime_=datetime_, properties=properties,
                              sortby=sortby,
                              select_properties=select_properties,
                              skip_geometry=skip_geometry,
                              q=q)
        except ProviderConnectionError as err:
            LOGGER.error(err)
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)
        except ProviderQueryError as err:
            LOGGER.error(err)
            msg = 'query error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)
        except ProviderGenericError as err:
            LOGGER.error(err)
            msg = 'generic error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)

        serialized_query_params = ''
        for k, v in request.params.items():
            if k not in ('f', 'startindex'):
                serialized_query_params += '&'
                serialized_query_params += urllib.parse.quote(k, safe='')
                serialized_query_params += '='
                serialized_query_params += urllib.parse.quote(str(v), safe=',')

        content['links'] = [{
            'type': 'application/geo+json',
            'rel': 'self' if request.format in (None, 'json') else 'alternate',
            'title': 'This document as GeoJSON',
            'href': '{}/collections/{}/items?f=json{}'.format(
                self.config['server']['url'], dataset, serialized_query_params)
        }, {
            'rel': 'self' if request.format == 'jsonld' else 'alternate',
            'type': 'application/ld+json',
            'title': 'This document as RDF (JSON-LD)',
            'href': '{}/collections/{}/items?f=jsonld{}'.format(
                self.config['server']['url'], dataset, serialized_query_params)
        }, {
            'type': 'text/html',
            'rel': 'self' if request.format == 'html' else 'alternate',
            'title': 'This document as HTML',
            'href': '{}/collections/{}/items?f=html{}'.format(
                self.config['server']['url'], dataset, serialized_query_params)
        }]

        if startindex > 0:
            prev = max(0, startindex - limit)
            content['links'].append(
                {
                    'type': 'application/geo+json',
                    'rel': 'prev',
                    'title': 'items (prev)',
                    'href': '{}/collections/{}/items?startindex={}{}'
                    .format(self.config['server']['url'], dataset, prev,
                            serialized_query_params)
                })

        if len(content['features']) == limit:
            next_ = startindex + limit
            content['links'].append(
                {
                    'type': 'application/geo+json',
                    'rel': 'next',
                    'title': 'items (next)',
                    'href': '{}/collections/{}/items?startindex={}{}'
                    .format(
                        self.config['server']['url'], dataset, next_,
                        serialized_query_params)
                })

        content['links'].append(
            {
                'type': 'application/json',
                'title': l10n.translate(
                    collections[dataset]['title'], request.locale),
                'rel': 'collection',
                'href': '{}/collections/{}'.format(
                    self.config['server']['url'], dataset)
            })

        content['timeStamp'] = datetime.utcnow().strftime(
            '%Y-%m-%dT%H:%M:%S.%fZ')

        if p.locale:
            # If provider supports locales, override/set response locale
            headers['Content-Language'] = p.locale

        if request.format == 'html':  # render

            # For constructing proper URIs to items
            if pathinfo:
                path_info = '/'.join([
                    self.config['server']['url'].rstrip('/'),
                    pathinfo.strip('/')])
            else:
                path_info = '/'.join([
                    self.config['server']['url'].rstrip('/'),
                    request.path_info])

            content['items_path'] = path_info
            content['dataset_path'] = '/'.join(path_info.split('/')[:-1])
            content['collections_path'] = '/'.join(path_info.split('/')[:-2])
            content['startindex'] = startindex

            if p.title_field is not None:
                content['title_field'] = p.title_field
            content['id_field'] = p.title_field

            content = render_j2_template(self.config,
                                         'collections/items/index.html',
                                         content)
            return headers, 200, content
        elif request.format == 'csv':  # render
            formatter = load_plugin('formatter',
                                    {'name': 'CSV', 'geom': True},
                                    request.raw_locale)

            content = formatter.write(
                data=content,
                options={
                    'provider_def': get_provider_by_type(
                                        collections[dataset]['providers'],
                                        'feature')
                }
            )

            headers['Content-Type'] = '{}; charset={}'.format(
                formatter.mimetype, self.config['server']['encoding'])

            cd = 'attachment; filename="{}.csv"'.format(dataset)
            headers['Content-Disposition'] = cd

            return headers, 200, content

        elif request.format == 'jsonld':
            content = geojson2geojsonld(self.config, content, dataset)
            return headers, 200, content

        return headers, 200, to_json(content, self.pretty_print)

    @pre_process
    def get_collection_item(self, request: Union[APIRequest, Any], dataset, identifier):  # noqa
        """
        Get a single collection item

        :param request: A request object
        :param dataset: dataset name
        :param identifier: item identifier

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        LOGGER.debug('Processing query parameters')

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            msg = 'Invalid collection'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Loading provider')

        try:
            p = load_plugin('provider', get_provider_by_type(
                collections[dataset]['providers'], 'feature'),
                            request.raw_locale)
        except ProviderTypeError:
            try:
                p = load_plugin('provider', get_provider_by_type(
                    collections[dataset]['providers'], 'record'),
                                request.raw_locale)
            except ProviderTypeError:
                msg = 'Invalid provider type'
                return self.get_exception(
                    400, headers, request.format, 'InvalidParameterValue', msg)
        try:
            LOGGER.debug('Fetching id {}'.format(identifier))
            content = p.get(identifier)
        except ProviderConnectionError as err:
            LOGGER.error(err)
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)
        except ProviderItemNotFoundError:
            msg = 'identifier not found'
            return self.get_exception(404, headers, request.format,
                                      'NotFound', msg)
        except ProviderQueryError as err:
            LOGGER.error(err)
            msg = 'query error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)
        except ProviderGenericError as err:
            LOGGER.error(err)
            msg = 'generic error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)

        if content is None:
            msg = 'identifier not found'
            return self.get_exception(400, headers, request.format,
                                      'NotFound', msg)

        content['links'] = [{
            'rel': 'self' if request.format in (None, 'json') else 'alternate',
            'type': 'application/geo+json',
            'title': 'This document as GeoJSON',
            'href': '{}/collections/{}/items/{}?f=json'.format(
                self.config['server']['url'], dataset, identifier)
        }, {
            'rel': 'self' if request.format == 'jsonld' else 'alternate',
            'type': 'application/ld+json',
            'title': 'This document as RDF (JSON-LD)',
            'href': '{}/collections/{}/items/{}?f=jsonld'.format(
                self.config['server']['url'], dataset, identifier)
        }, {
            'rel': 'self' if request.format == 'html' else 'alternate',
            'type': 'text/html',
            'title': 'This document as HTML',
            'href': '{}/collections/{}/items/{}?f=html'.format(
                self.config['server']['url'], dataset, identifier)
        }, {
            'rel': 'collection',
            'type': 'application/json',
            'title': l10n.translate(collections[dataset]['title'],
                                    request.locale),
            'href': '{}/collections/{}'.format(
                self.config['server']['url'], dataset)
        }, {
            'rel': 'prev',
            'type': 'application/geo+json',
            'href': '{}/collections/{}/items/{}'.format(
                self.config['server']['url'], dataset, identifier)
        }, {
            'rel': 'next',
            'type': 'application/geo+json',
            'href': '{}/collections/{}/items/{}'.format(
                self.config['server']['url'], dataset, identifier)
        }]

        if p.locale:
            # If provider supports locales, override/set response locale
            headers['Content-Language'] = p.locale

        if request.format == 'html':  # render
            content['title'] = l10n.translate(collections[dataset]['title'],
                                              request.locale)
            content['id_field'] = p.id_field
            if p.title_field is not None:
                content['title_field'] = p.title_field

            content = render_j2_template(self.config,
                                         'collections/items/item.html',
                                         content)
            return headers, 200, content

        elif request.format == 'jsonld':
            content = geojson2geojsonld(
                self.config, content, dataset, identifier=identifier
            )
            return headers, 200, content

        return headers, 200, to_json(content, self.pretty_print)

    @pre_process
    @jsonldify
    def get_collection_coverage(self, request: Union[APIRequest, Any], dataset):  # noqa
        """
        Returns a subset of a collection coverage

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        query_args = {}
        format_ = 'json'
        headers = request.get_response_headers(FORMATS['json'])

        LOGGER.debug('Loading provider')
        try:
            collection_def = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'coverage')

            p = load_plugin('provider', collection_def,
                            request.raw_locale)
        except KeyError:
            msg = 'collection does not exist'
            return self.get_exception(
                404, headers, format_, 'InvalidParameterValue', msg)
        except ProviderTypeError:
            msg = 'invalid provider type'
            return self.get_exception(
                400, headers, format_, 'NoApplicableCode', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers, format_, 'NoApplicableCode', msg)

        LOGGER.debug('Processing bbox parameter')

        bbox = request.params.get('bbox')

        if bbox is None:
            bbox = []
        else:
            try:
                bbox = validate_bbox(bbox)
            except ValueError as err:
                msg = str(err)
                return self.get_exception(
                    500, headers, format_, 'InvalidParameterValue', msg)

        query_args['bbox'] = bbox

        LOGGER.debug('Processing datetime parameter')

        datetime_ = request.params.get('datetime', None)

        try:
            datetime_ = validate_datetime(
                self.config['resources'][dataset]['extents'], datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                400, headers, format_, 'InvalidParameterValue', msg)

        query_args['datetime_'] = datetime_

        if request.format:
            query_args['format_'] = format_ = request.format

        range_subset = request.params.get('rangeSubset')
        if range_subset:
            LOGGER.debug('Processing rangeSubset parameter')
            query_args['range_subset'] = [rs for
                                          rs in range_subset.split(',') if rs]
            LOGGER.debug('Fields: {}'.format(query_args['range_subset']))

            for a in query_args['range_subset']:
                if a not in p.fields:
                    msg = 'Invalid field specified'
                    return self.get_exception(
                        400, headers, format_, 'InvalidParameterValue', msg)

        if 'subset' in request.params:
            subsets = {}
            LOGGER.debug('Processing subset parameter')
            for s in (request.params['subset'] or '').split(','):
                try:
                    if '"' not in s:
                        m = re.search(r'(.*)\((.*):(.*)\)', s)
                    else:
                        m = re.search(r'(.*)\(\"(\S+)\":\"(\S+.*)\"\)', s)

                    subset_name = m.group(1)

                    if subset_name not in p.axes:
                        msg = 'Invalid axis name'
                        return self.get_exception(
                            400, headers, format_,
                            'InvalidParameterValue', msg)

                    subsets[subset_name] = list(map(
                        get_typed_value, m.group(2, 3)))
                except AttributeError:
                    msg = 'subset should be like "axis(min:max)"'
                    return self.get_exception(
                        400, headers, format_, 'InvalidParameterValue', msg)

            query_args['subsets'] = subsets
            LOGGER.debug('Subsets: {}'.format(query_args['subsets']))

        LOGGER.debug('Querying coverage')
        try:
            data = p.query(**query_args)
        except ProviderInvalidQueryError as err:
            msg = 'query error: {}'.format(err)
            return self.get_exception(
                400, headers, format_, 'InvalidParameterValue', msg)
        except ProviderNoDataError:
            msg = 'No data found'
            return self.get_exception(
                204, headers, format_, 'InvalidParameterValue', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                500, headers, format_, 'NoApplicableCode', msg)

        mt = collection_def['format']['name']

        if format_ == mt:
            headers['Content-Type'] = collection_def['format']['mimetype']
            return headers, 200, data
        elif format_ == 'json':
            headers['Content-Type'] = 'application/prs.coverage+json'
            return headers, 200, to_json(data, self.pretty_print)
        else:
            return self.get_format_exception(request)

    @pre_process
    @jsonldify
    def get_collection_coverage_domainset(self, request: Union[APIRequest, Any], dataset):  # noqa
        """
        Returns a collection coverage domainset

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        format_ = request.format or 'json'
        headers = request.get_response_headers()

        LOGGER.debug('Loading provider')
        try:
            collection_def = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'coverage')

            p = load_plugin('provider', collection_def,
                            request.raw_locale)

            data = p.get_coverage_domainset()
        except KeyError:
            msg = 'collection does not exist'
            return self.get_exception(
                404, headers, format_, 'InvalidParameterValue', msg)
        except ProviderTypeError:
            msg = 'invalid provider type'
            return self.get_exception(
                500, headers, format_, 'NoApplicableCode', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers, format_, 'NoApplicableCode', msg)

        if format_ == 'json':
            return headers, 200, to_json(data, self.pretty_print)
        elif format_ == 'html':
            data['id'] = dataset
            data['title'] = l10n.translate(
                self.config['resources'][dataset]['title'], request.locale)
            content = render_j2_template(self.config,
                                         'collections/coverage/domainset.html',
                                         data)
            return headers, 200, content
        else:
            return self.get_format_exception(request)

    @pre_process
    @jsonldify
    def get_collection_coverage_rangetype(self, request: Union[APIRequest, Any], dataset):  # noqa
        """
        Returns a collection coverage rangetype

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """
        format_ = request.format or 'json'
        headers = request.get_response_headers()

        LOGGER.debug('Loading provider')
        try:
            collection_def = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'coverage')

            p = load_plugin('provider', collection_def,
                            request.raw_locale)

            data = p.get_coverage_rangetype()
        except KeyError:
            msg = 'collection does not exist'
            return self.get_exception(
                404, headers, format_, 'InvalidParameterValue', msg)
        except ProviderTypeError:
            msg = 'invalid provider type'
            return self.get_exception(
                500, headers, format_, 'NoApplicableCode', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers, format_, 'NoApplicableCode', msg)

        if format_ == 'json':
            return headers, 200, to_json(data, self.pretty_print)
        elif format_ == 'html':
            data['id'] = dataset
            data['title'] = l10n.translate(
                self.config['resources'][dataset]['title'], request.locale)
            content = render_j2_template(self.config,
                                         'collections/coverage/rangetype.html',
                                         data)
            return headers, 200, content
        else:
            return self.get_format_exception(request)

    @pre_process
    @jsonldify
    def get_collection_tiles(self, request: Union[APIRequest, Any], dataset=None):  # noqa
        """
        Provide collection tiles

        :param request: A request object
        :param dataset: name of collection

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        if any([dataset is None,
                dataset not in self.config['resources'].keys()]):

            msg = 'Invalid collection'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Creating collection tiles')
        LOGGER.debug('Loading provider')
        try:
            t = get_provider_by_type(
                    self.config['resources'][dataset]['providers'], 'tile')
            p = load_plugin('provider', t, request.raw_locale)
        except (KeyError, ProviderTypeError):
            msg = 'Invalid collection tiles'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)

        tiles = {
            'title': dataset,
            'description': l10n.translate(
                self.config['resources'][dataset]['description'],
                request.locale),
            'links': [],
            'tileMatrixSetLinks': []
        }

        tiles['links'].append({
            'type': 'application/json',
            'rel': 'self' if request.format == 'json' else 'alternate',
            'title': 'This document as JSON',
            'href': '{}/collections/{}/tiles?f=json'.format(
                self.config['server']['url'], dataset)
        })
        tiles['links'].append({
            'type': 'application/ld+json',
            'rel': 'self' if request.format == 'jsonld' else 'alternate',
            'title': 'This document as RDF (JSON-LD)',
            'href': '{}/collections/{}/tiles?f=jsonld'.format(
                self.config['server']['url'], dataset)
        })
        tiles['links'].append({
            'type': 'text/html',
            'rel': 'self' if request.format == 'html' else 'alternate',
            'title': 'This document as HTML',
            'href': '{}/collections/{}/tiles?f=html'.format(
                self.config['server']['url'], dataset)
        })

        for service in p.get_tiles_service(
            baseurl=self.config['server']['url'],
            servicepath='/collections/{}/tiles/{{{}}}/{{{}}}/{{{}}}/{{{}}}?f=mvt'  # noqa
            .format(dataset, 'tileMatrixSetId',
                    'tileMatrix', 'tileRow', 'tileCol'))['links']:
            tiles['links'].append(service)

        tiles['tileMatrixSetLinks'] = p.get_tiling_schemes()
        metadata_format = p.options['metadata_format']

        if request.format == 'html':  # render
            tiles['id'] = dataset
            tiles['title'] = l10n.translate(
                self.config['resources'][dataset]['title'], request.locale)
            tiles['tilesets'] = [
                scheme['tileMatrixSet'] for scheme in p.get_tiling_schemes()]
            tiles['format'] = metadata_format
            tiles['bounds'] = \
                self.config['resources'][dataset]['extents']['spatial']['bbox']
            tiles['minzoom'] = p.options['zoom']['min']
            tiles['maxzoom'] = p.options['zoom']['max']

            content = render_j2_template(self.config,
                                         'collections/tiles/index.html', tiles)

            return headers, 200, content

        return headers, 200, to_json(tiles, self.pretty_print)

    @pre_process
    @jsonldify
    def get_collection_tiles_data(self, request: Union[APIRequest, Any],
                                  dataset=None, matrix_id=None,
                                  z_idx=None, y_idx=None, x_idx=None):
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
        headers = request.get_response_headers()

        LOGGER.debug('Processing tiles')

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            msg = 'Invalid collection'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Loading tile provider')
        try:
            t = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'tile')
            p = load_plugin('provider', t, request.raw_locale)

            format_ = p.format_type
            headers['Content-Type'] = format_

            LOGGER.debug('Fetching tileset id {} and tile {}/{}/{}'.format(
                matrix_id, z_idx, y_idx, x_idx))
            content = p.get_tiles(layer=p.get_layer(), tileset=matrix_id,
                                  z=z_idx, y=y_idx, x=x_idx, format_=format_)
            if content is None:
                msg = 'identifier not found'
                return self.get_exception(
                    404, headers, format_, 'NotFound', msg)
            else:
                return headers, 202, content

        # @TODO: figure out if the spec requires to return json errors
        except KeyError:
            msg = 'Invalid collection tiles'
            return self.get_exception(
                400, headers, format_, 'InvalidParameterValue', msg)
        except ProviderConnectionError as err:
            LOGGER.error(err)
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers, format_, 'NoApplicableCode', msg)
        except ProviderTilesetIdNotFoundError:
            msg = 'Tileset id not found'
            return self.get_exception(
                404, headers, format_, 'NotFound', msg)
        except ProviderTileQueryError as err:
            LOGGER.error(err)
            msg = 'Tile not found'
            return self.get_exception(
                500, headers, format_, 'NoApplicableCode', msg)
        except ProviderTileNotFoundError as err:
            LOGGER.error(err)
            msg = 'tile not found (check logs)'
            return self.get_exception(
                404, headers, format_, 'NoMatch', msg)
        except ProviderGenericError as err:
            LOGGER.error(err)
            msg = 'generic error (check logs)'
            return self.get_exception(
                500, headers, format_, 'NoApplicableCode', msg)

    @pre_process
    @jsonldify
    def get_collection_tiles_metadata(self, request: Union[APIRequest, Any],
                                      dataset=None, matrix_id=None):
        """
        Get collection items tiles

        :param request: A request object
        :param dataset: dataset name
        :param matrix_id: matrix identifier

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        if any([dataset is None,
                dataset not in self.config['resources'].keys()]):

            msg = 'Invalid collection'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Creating collection tiles')
        LOGGER.debug('Loading provider')
        try:
            t = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'tile')
            p = load_plugin('provider', t, request.raw_locale)
        except KeyError:
            msg = 'Invalid collection tiles'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'InvalidParameterValue', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'InvalidParameterValue', msg)

        if matrix_id not in p.options['schemes']:
            msg = 'tileset not found'
            return self.get_exception(404, headers, request.format,
                                      'NotFound', msg)

        metadata_format = p.options['metadata_format']
        tilejson = True if (metadata_format == 'tilejson') else False

        tiles_metadata = p.get_metadata(
            dataset=dataset, server_url=self.config['server']['url'],
            layer=p.get_layer(), tileset=matrix_id, tilejson=tilejson)

        if request.format == 'html':  # render
            metadata = dict(metadata=tiles_metadata)
            metadata['id'] = dataset
            metadata['title'] = l10n.translate(
                self.config['resources'][dataset]['title'], request.locale)
            metadata['tileset'] = matrix_id
            metadata['format'] = metadata_format

            content = render_j2_template(self.config,
                                         'collections/tiles/metadata.html',
                                         metadata)

            return headers, 200, content

        return headers, 200, to_json(tiles_metadata, self.pretty_print)

    @pre_process
    @jsonldify
    def describe_processes(self, request: Union[APIRequest, Any], process=None):  # noqa
        """
        Provide processes metadata

        :param request: A request object
        :param process: process identifier, defaults to None to obtain
                        information about all processes

        :returns: tuple of headers, status code, content
        """

        processes = []

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        processes_config = filter_dict_by_key_value(self.config['resources'],
                                                    'type', 'process')

        if process is not None:
            if process not in processes_config.keys() or not processes_config:
                msg = 'Identifier not found'
                return self.get_exception(
                    404, headers, request.format, 'NoSuchProcess', msg)

        if processes_config:
            if process is not None:
                relevant_processes = [(process, processes_config[process])]
            else:
                relevant_processes = processes_config.items()

            for key, value in relevant_processes:
                p = load_plugin('process',
                                processes_config[key]['processor'],
                                request.raw_locale)

                p2 = deepcopy(p.metadata)

                p2['jobControlOptions'] = ['sync-execute']
                if self.manager.is_async:
                    p2['jobControlOptions'].append('async-execute')

                p2['outputTransmission'] = ['value']
                p2['links'] = l10n.translate(p2.get('links', []),
                                             request.locale)

                jobs_url = '{}/processes/{}/jobs'.format(
                    self.config['server']['url'], key)

                # TODO translation support
                link = {
                    'type': 'text/html',
                    'rel': 'collection',
                    'href': '{}?f=html'.format(jobs_url),
                    'title': 'jobs for this process as HTML',
                    'hreflang': self.default_locale
                }
                p2['links'].append(link)

                link = {
                    'type': 'application/json',
                    'rel': 'collection',
                    'href': '{}?f=json'.format(jobs_url),
                    'title': 'jobs for this process as JSON',
                    'hreflang': self.default_locale
                }
                p2['links'].append(link)

                processes.append(p2)

        if process is not None:
            response = processes[0]
        else:
            response = {
                'processes': processes
            }

        if request.format == 'html':  # render
            if process is not None:
                response = render_j2_template(self.config,
                                              'processes/process.html',
                                              response)
            else:
                response = render_j2_template(self.config,
                                              'processes/index.html', response)

            return headers, 200, response

        return headers, 200, to_json(response, self.pretty_print)

    @pre_process
    def get_process_jobs(self, request: Union[APIRequest, Any], process_id, job_id=None):  # noqa
        """
        Get process jobs

        :param request: A request object
        :param process_id: id of process
        :param job_id: id of job

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        processes = filter_dict_by_key_value(
            self.config['resources'], 'type', 'process')

        if process_id not in processes:
            msg = 'identifier not found'
            return self.get_exception(
                404, headers, request.format, 'NoSuchProcess', msg)

        p = load_plugin('process', processes[process_id]['processor'],
                        request.raw_locale)

        if self.manager:
            if job_id is None:
                jobs = sorted(self.manager.get_jobs(process_id),
                              key=lambda k: k['job_start_datetime'],
                              reverse=True)
            else:
                jobs = [self.manager.get_job(process_id, job_id)]
        else:
            LOGGER.debug('Process management not configured')
            jobs = []

        serialized_jobs = []
        for job_ in jobs:
            job2 = {
                'jobID': job_['identifier'],
                'status': job_['status'],
                'message': job_['message'],
                'progress': job_['progress'],
                'parameters': job_.get('parameters'),
                'job_start_datetime': job_['job_start_datetime'],
                'job_end_datetime': job_['job_end_datetime']
            }

            if JobStatus[job_['status']] in [
               JobStatus.successful, JobStatus.running, JobStatus.accepted]:

                job_result_url = '{}/processes/{}/jobs/{}/results'.format(
                    self.config['server']['url'],
                    process_id, job_['identifier'])

                job2['links'] = [{
                    'href': '{}?f=html'.format(job_result_url),
                    'rel': 'about',
                    'type': 'text/html',
                    'title': 'results of job {} as HTML'.format(job_id)
                }, {
                    'href': '{}?f=json'.format(job_result_url),
                    'rel': 'about',
                    'type': 'application/json',
                    'title': 'results of job {} as JSON'.format(job_id)
                }]

                if job_['mimetype'] not in ['application/json', 'text/html']:
                    job2['links'].append({
                        'href': job_result_url,
                        'rel': 'about',
                        'type': job_['mimetype'],
                        'title': 'results of job {} as {}'.format(
                            job_id, job_['mimetype'])
                    })

            serialized_jobs.append(job2)

        if job_id is None:
            j2_template = 'processes/jobs/index.html'
        else:
            serialized_jobs = serialized_jobs[0]
            j2_template = 'processes/jobs/job.html'

        if request.format == 'html':
            data = {
                'process': {
                    'id': process_id,
                    'title': l10n.translate(p.metadata['title'],
                                            request.locale)
                },
                'jobs': serialized_jobs,
                'now': datetime.now(timezone.utc).strftime(DATETIME_FORMAT)
            }
            response = render_j2_template(self.config, j2_template, data)
            return headers, 200, response

        return headers, 200, to_json(serialized_jobs, self.pretty_print)

    @pre_process
    def execute_process(self, request: Union[APIRequest, Any], process_id):
        """
        Execute process

        :param request: A request object
        :param process_id: id of process

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        processes_config = filter_dict_by_key_value(
            self.config['resources'], 'type', 'process'
        )
        if process_id not in processes_config:
            msg = 'identifier not found'
            return self.get_exception(
                404, headers, request.format, 'NoSuchProcess', msg)

        if not self.manager:
            msg = 'Process manager is undefined'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)

        process = load_plugin('process',
                              processes_config[process_id]['processor'],
                              request.raw_locale)

        if not request.data:
            # TODO not all processes require input, e.g. time-dependent or
            #      random value generators
            msg = 'missing request data'
            return self.get_exception(
                400, headers, request.format, 'MissingParameterValue', msg)

        data = request.data
        try:
            # Parse bytes data, if applicable
            data = data.decode()
            LOGGER.debug(data)
        except (UnicodeDecodeError, AttributeError):
            pass

        try:
            data = json.loads(data)
        except (json.decoder.JSONDecodeError, TypeError) as err:
            # Input does not appear to be valid JSON
            LOGGER.error(err)
            msg = 'invalid request data'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

        try:
            data_dict = {}
            for input in data.get('inputs', []):
                id = input['id']
                value = input['value']
                if id not in data_dict:
                    data_dict[id] = value
                elif id in data_dict and isinstance(data_dict[id], list):
                    data_dict[id].append(value)
                else:
                    data_dict[id] = [data_dict[id], value]
        except KeyError:
            # Return 4XX client error for missing 'id' or 'value' in an input
            msg = 'invalid request data'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)
        else:
            LOGGER.debug(data_dict)

        job_id = str(uuid.uuid1())
        url = '{}/processes/{}/jobs/{}'.format(
            self.config['server']['url'], process_id, job_id)

        headers['Location'] = url

        outputs = status = None
        is_async = data.get('mode', 'auto') == 'async'

        if is_async:
            LOGGER.debug('Asynchronous request mode detected')

        try:
            LOGGER.debug('Executing process')
            mime_type, outputs, status = self.manager.execute_process(
                process, job_id, data_dict, is_async)
        except ProcessorExecuteError as err:
            LOGGER.error(err)
            msg = 'Processing error'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)

        response = {}
        if status == JobStatus.failed:
            response = outputs

        if data.get('response', 'document') == 'raw':
            headers['Content-Type'] = mime_type
            if 'json' in mime_type:
                response = to_json(outputs)
            else:
                response = outputs

        elif status != JobStatus.failed and not is_async:
            response['outputs'] = outputs

        if is_async:
            http_status = 201
        else:
            http_status = 200

        return headers, http_status, to_json(response, self.pretty_print)

    @pre_process
    def get_process_job_result(self, request: Union[APIRequest, Any], process_id, job_id):  # noqa
        """
        Get result of job (instance of a process)

        :param request: A request object
        :param process_id: name of process
        :param job_id: ID of job

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        processes_config = filter_dict_by_key_value(self.config['resources'],
                                                    'type', 'process')

        if process_id not in processes_config:
            msg = 'identifier not found'
            return self.get_exception(
                404, headers, request.format, 'NoSuchProcess', msg)

        process = load_plugin('process',
                              processes_config[process_id]['processor'],
                              request.raw_locale)

        if not process:
            msg = 'identifier not found'
            return self.get_exception(
                404, headers, request.format, 'NoSuchProcess', msg)

        job = self.manager.get_job(process_id, job_id)

        if not job:
            msg = 'job not found'
            return self.get_exception(404, headers, request.format,
                                      'NoSuchJob', msg)

        status = JobStatus[job['status']]

        if status == JobStatus.running:
            msg = 'job still running'
            return self.get_exception(
                404, headers, request.format, 'ResultNotReady', msg)

        elif status == JobStatus.accepted:
            # NOTE: this case is not mentioned in the specification
            msg = 'job accepted but not yet running'
            return self.get_exception(
                404, headers, request.format, 'ResultNotReady', msg)

        elif status == JobStatus.failed:
            msg = 'job failed'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg)

        mimetype, job_output = self.manager.get_job_result(process_id, job_id)

        if mimetype not in [None, 'application/json']:
            headers['Content-Type'] = mimetype
            content = job_output
        else:
            if request.format == 'json':
                content = json.dumps(job_output, sort_keys=True, indent=4,
                                     default=json_serial)
            else:
                data = {
                    'process': {
                        'id': process_id, 'title': process.metadata['title']
                    },
                    'job': {'id': job_id},
                    'result': job_output
                }
                content = render_j2_template(
                    self.config, 'processes/jobs/results/index.html', data)

        return headers, 200, content

    def delete_process_job(self, process_id, job_id):
        """
        :param process_id: process identifier
        :param job_id: job identifier

        :returns: tuple of headers, status code, content
        """

        success = self.manager.delete_job(process_id, job_id)

        if not success:
            http_status = 404
            response = {
                'code': 'NoSuchJob',
                'description': 'Job identifier not found'
            }
        else:
            http_status = 200
            jobs_url = '{}/processes/{}/jobs'.format(
                self.config['server']['url'], process_id)

            response = {
                'jobID': job_id,
                'status': JobStatus.dismissed.value,
                'message': 'Job dismissed',
                'progress': 100,
                'links': [{
                    'href': jobs_url,
                    'rel': 'up',
                    'type': 'application/json',
                    'title': 'The job list for the current process'
                }]
            }

        LOGGER.info(response)
        return {}, http_status, response

    def get_collection_edr_query(self, headers, args, dataset, instance,
                                 query_type):
        """
        Queries collection EDR
        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param dataset: dataset name
        :param dataset: instance name
        :param query_type: EDR query type
        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        query_args = {}
        formats = FORMATS
        formats.extend(f.lower() for f in PLUGINS['formatter'].keys())

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        format_ = check_format(args, headers)

        if dataset not in collections.keys():
            msg = 'Invalid collection'
            return self.get_exception(
                400, headers_, format_, 'InvalidParameterValue', msg)

        if format_ is not None and format_ not in formats:
            msg = 'Invalid format'
            return self.get_exception(
                400, headers_, format_, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Processing datetime parameter')
        datetime_ = args.get('datetime')
        try:
            datetime_ = validate_datetime(collections[dataset]['extents'],
                                          datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                400, headers_, format_, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing parameter-name parameter')
        parameternames = args.get('parameter-name', [])
        if parameternames:
            parameternames = parameternames.split(',')

        LOGGER.debug('Processing coords parameter')
        wkt = args.get('coords', None)

        if wkt is None:
            msg = 'missing coords parameter'
            return self.get_exception(
                400, headers_, format_, 'InvalidParameterValue', msg)

        try:
            wkt = shapely_loads(wkt)
        except WKTReadingError:
            msg = 'invalid coords parameter'
            return self.get_exception(
                400, headers_, format_, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing z parameter')
        z = args.get('z')

        LOGGER.debug('Loading provider')
        try:
            p = load_plugin('provider', get_provider_by_type(
                collections[dataset]['providers'], 'edr'))
        except ProviderTypeError:
            msg = 'invalid provider type'
            return self.get_exception(
                500, headers_, format_, 'NoApplicableCode', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers_, format_, 'NoApplicableCode', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                500, headers_, format_, 'NoApplicableCode', msg)

        if instance is not None and not p.get_instance(instance):
            msg = 'Invalid instance identifier'
            return self.get_exception(
                400, headers_, format_, 'InvalidParameterValue', msg)

        if query_type not in p.get_query_types():
            msg = 'Unsupported query type'
            return self.get_exception(
                400, headers_, format_, 'InvalidParameterValue', msg)

        parametername_matches = list(
            filter(
                lambda p: p['id'] in parameternames, p.get_fields()['field']
            )
        )

        if len(parametername_matches) < len(parameternames):
            msg = 'Invalid parameter-name'
            return self.get_exception(
                400, headers_, format_, 'InvalidParameterValue', msg)

        query_args = dict(
            query_type=query_type,
            instance=instance,
            format_=format_,
            datetime_=datetime_,
            select_properties=parameternames,
            wkt=wkt,
            z=z
        )

        try:
            data = p.query(**query_args)
        except ProviderNoDataError:
            msg = 'No data found'
            return self.get_exception(
                204, headers_, format_, 'NoMatch', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                500, headers_, format_, 'NoApplicableCode', msg)

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
            content = render_j2_template(
                self.config, 'collections/edr/query.html', data)
        else:
            content = to_json(data, self.pretty_print)

        return headers_, 200, content

    @pre_process
    @jsonldify
    def get_stac_root(self, request: Union[APIRequest, Any]):

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        id_ = 'pygeoapi-stac'
        stac_version = '0.6.2'
        stac_url = os.path.join(self.config['server']['url'], 'stac')

        content = {
            'id': id_,
            'stac_version': stac_version,
            'title': l10n.translate(
                self.config['metadata']['identification']['title'],
                request.locale),
            'description': l10n.translate(
                self.config['metadata']['identification']['description'],
                request.locale),
            'license': l10n.translate(
                self.config['metadata']['license']['name'], request.locale),
            'providers': [{
                'name': l10n.translate(
                    self.config['metadata']['provider']['name'],
                    request.locale),
                'url': l10n.translate(
                    self.config['metadata']['provider']['url'], request.locale)
            }],
            'links': []
        }

        stac_collections = filter_dict_by_key_value(self.config['resources'],
                                                    'type', 'stac-collection')

        for key, value in stac_collections.items():
            content['links'].append({
                'rel': 'collection',
                'href': '{}/{}?f=json'.format(stac_url, key),
                'type': 'application/json'
            })
            content['links'].append({
                'rel': 'collection',
                'href': '{}/{}'.format(stac_url, key),
                'type': 'text/html'
            })

        if request.format == 'html':  # render
            content = render_j2_template(self.config, 'stac/collection.html',
                                         content)
            return headers, 200, content

        return headers, 200, to_json(content, self.pretty_print)

    @pre_process
    @jsonldify
    def get_stac_path(self, request: Union[APIRequest, Any], path):

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        dataset = None
        LOGGER.debug('Path: {}'.format(path))
        dir_tokens = path.split('/')
        if dir_tokens:
            dataset = dir_tokens[0]

        stac_collections = filter_dict_by_key_value(self.config['resources'],
                                                    'type', 'stac-collection')

        if dataset not in stac_collections:
            msg = 'collection not found'
            return self.get_exception(404, headers, request.format,
                                      'NotFound', msg)

        LOGGER.debug('Loading provider')
        try:
            p = load_plugin('provider', get_provider_by_type(
                stac_collections[dataset]['providers'], 'stac'),
                            request.raw_locale)
        except ProviderConnectionError as err:
            LOGGER.error(err)
            msg = 'connection error (check logs)'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)

        id_ = '{}-stac'.format(dataset)
        stac_version = '0.6.2'
        description = stac_collections[dataset]['description']

        content = {
            'id': id_,
            'stac_version': stac_version,
            'description': l10n.translate(description, request.locale),
            'extent': stac_collections[dataset]['extents'],
            'links': []
        }
        try:
            stac_data = p.get_data_path(
                os.path.join(self.config['server']['url'], 'stac'),
                path,
                path.replace(dataset, '', 1)
            )
        except ProviderNotFoundError as err:
            LOGGER.error(err)
            msg = 'resource not found'
            return self.get_exception(404, headers, request.format,
                                      'NotFound', msg)
        except Exception as err:
            LOGGER.error(err)
            msg = 'data query error'
            return self.get_exception(
                500, headers, request.format, 'NoApplicableCode', msg)

        if isinstance(stac_data, dict):
            content.update(stac_data)
            content['links'].extend(
                l10n.translate(stac_collections[dataset]['links'],
                               request.locale))

            if request.format == 'html':  # render
                content['path'] = path
                if 'assets' in content:  # item view
                    content = render_j2_template(self.config,
                                                 'stac/item.html',
                                                 content)
                else:
                    content = render_j2_template(self.config,
                                                 'stac/catalog.html',
                                                 content)

                return headers, 200, content

            return headers, 200, to_json(content, self.pretty_print)

        else:  # send back file
            headers.pop('Content-Type', None)
            return headers, 200, stac_data

    def get_exception(self, status, headers, format_, code, description):
        """
        Exception handler

        :param status: HTTP status code
        :param headers: dict of HTTP response headers
        :param format_: format string
        :param code: OGC API exception code
        :param description: OGC API exception code

        :returns: tuple of headers, status, and message
        """

        LOGGER.error(description)
        exception = {
            'code': code,
            'description': description
        }

        if format_ == 'html':
            headers['Content-Type'] = 'text/html'
            content = render_j2_template(
                self.config, 'exception.html', exception)
        else:
            content = to_json(exception, self.pretty_print)

        return headers, status, content

    def get_format_exception(self, request):
        """ Returns a format exception.

        :param request: An APIRequest instance.

        :returns:       tuple of (headers, status, message)
        """
        headers = request.get_response_headers()
        msg = f'Invalid format: {request.format}'
        return self.get_exception(
            400, headers, 'json', 'InvalidParameterValue', msg)


def validate_bbox(value=None):
    """
    Helper function to validate bbox parameter

    :param value: `list` of minx, miny, maxx, maxy

    :returns: bbox as `list` of `float` values
    """

    if value is None:
        LOGGER.debug('bbox is empty')
        return []

    bbox = value.split(',')

    if len(bbox) != 4:
        msg = 'bbox should be 4 values (minx,miny,maxx,maxy)'
        LOGGER.debug(msg)
        raise ValueError(msg)

    try:
        bbox = [float(c) for c in bbox]
    except ValueError as err:
        msg = 'bbox values must be numbers'
        err.args = (msg,)
        LOGGER.debug(msg)
        raise

    if bbox[0] > bbox[2] or bbox[1] > bbox[3]:
        msg = 'min values should be less than max values'
        LOGGER.debug(msg)
        raise ValueError(msg)

    return bbox


def validate_datetime(resource_def, datetime_=None):
    """
    Helper function to validate temporal parameter

    :param resource_def: `dict` of configuration resource definition
    :param datetime_: `str` of datetime parameter

    :returns: `str` of datetime input, if valid
    """

    # TODO: pass datetime to query as a `datetime` object
    # we would need to ensure partial dates work accordingly
    # as well as setting '..' values to `None` so that underlying
    # providers can just assume a `datetime.datetime` object
    #
    # NOTE: needs testing when passing partials from API to backend

    datetime_invalid = False

    if (datetime_ is not None and 'temporal' in resource_def):

        dateparse_begin = partial(dateparse, default=datetime.min)
        dateparse_end = partial(dateparse, default=datetime.max)
        unix_epoch = datetime(1970, 1, 1, 0, 0, 0)
        dateparse_ = partial(dateparse, default=unix_epoch)

        te = resource_def['temporal']

        try:
            if te['begin'] is not None and te['begin'].tzinfo is None:
                te['begin'] = te['begin'].replace(tzinfo=pytz.UTC)
            if te['end'] is not None and te['end'].tzinfo is None:
                te['end'] = te['end'].replace(tzinfo=pytz.UTC)
        except AttributeError:
            msg = 'Configured times should be RFC3339'
            LOGGER.error(msg)
            raise ValueError(msg)

        if '/' in datetime_:  # envelope
            LOGGER.debug('detected time range')
            LOGGER.debug('Validating time windows')

            # normalize "" to ".." (actually changes datetime_)
            datetime_ = re.sub(r'^/', '../', datetime_)
            datetime_ = re.sub(r'/$', '/..', datetime_)

            datetime_begin, datetime_end = datetime_.split('/')
            if datetime_begin != '..':
                datetime_begin = dateparse_begin(datetime_begin)
                if datetime_begin.tzinfo is None:
                    datetime_begin = datetime_begin.replace(
                        tzinfo=pytz.UTC)

            if datetime_end != '..':
                datetime_end = dateparse_end(datetime_end)
                if datetime_end.tzinfo is None:
                    datetime_end = datetime_end.replace(tzinfo=pytz.UTC)

            datetime_invalid = any([
                (te['begin'] is not None and datetime_begin != '..' and
                    datetime_begin < te['begin']),
                (te['end'] is not None and datetime_end != '..' and
                    datetime_end > te['end'])
            ])

        else:  # time instant
            LOGGER.debug('detected time instant')
            datetime__ = dateparse_(datetime_)
            if datetime__ != '..':
                if datetime__.tzinfo is None:
                    datetime__ = datetime__.replace(tzinfo=pytz.UTC)
            datetime_invalid = any([
                (te['begin'] is not None and datetime__ != '..' and
                    datetime__ < te['begin']),
                (te['end'] is not None and datetime__ != '..' and
                    datetime__ > te['end'])
            ])

    if datetime_invalid:
        msg = 'datetime parameter out of range'
        LOGGER.debug(msg)
        raise ValueError(msg)

    return datetime_
