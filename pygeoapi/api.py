# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Sander Schaminee <sander.schaminee@geocat.net>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2023 Tom Kralidis
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
""" Root level code of pygeoapi, parsing content provided by web framework.
Returns content from plugins and sets responses.
"""

import asyncio
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from functools import partial
from gzip import compress
from http import HTTPStatus
import json
import logging
import re
from typing import Any, Tuple, Union, Optional
import urllib.parse

from dateutil.parser import parse as dateparse
from pygeofilter.parsers.ecql import parse as parse_ecql_text
from pygeofilter.parsers.cql_json import parse as parse_cql_json
from pyproj.exceptions import CRSError
import pytz
from shapely.errors import WKTReadingError
from shapely.wkt import loads as shapely_loads

from pygeoapi import __version__, l10n
from pygeoapi.formatter.base import FormatterSerializationError
from pygeoapi.linked_data import (geojson2jsonld, jsonldify,
                                  jsonldify_collection)
from pygeoapi.log import setup_logger
from pygeoapi.process.base import (
    JobNotFoundError,
    JobResultNotFoundError,
    ProcessorExecuteError,
)
from pygeoapi.process.manager.base import get_manager
from pygeoapi.plugin import load_plugin, PLUGINS
from pygeoapi.provider.base import (
    ProviderGenericError, ProviderConnectionError, ProviderNotFoundError,
    ProviderInvalidDataError, ProviderInvalidQueryError, ProviderNoDataError,
    ProviderQueryError, ProviderItemNotFoundError, ProviderTypeError,
    ProviderRequestEntityTooLargeError)

from pygeoapi.provider.tile import (ProviderTileNotFoundError,
                                    ProviderTileQueryError,
                                    ProviderTilesetIdNotFoundError)
from pygeoapi.models.cql import CQLModel
from pygeoapi.util import (dategetter, RequestedProcessExecutionMode,
                           DATETIME_FORMAT, UrlPrefetcher,
                           filter_dict_by_key_value, get_provider_by_type,
                           get_provider_default, get_typed_value, JobStatus,
                           json_serial, render_j2_template, str2bool,
                           TEMPLATES, to_json, get_api_rules, get_base_url,
                           get_crs_from_uri, get_supported_crs_list,
                           CrsTransformSpec, transform_bbox)

from pygeoapi.models.provider.base import TilesMetadataFormat

LOGGER = logging.getLogger(__name__)

#: Return headers for requests (e.g:X-Powered-By)
HEADERS = {
    'Content-Type': 'application/json',
    'X-Powered-By': f'pygeoapi {__version__}'
}

CHARSET = ['utf-8']
F_JSON = 'json'
F_HTML = 'html'
F_JSONLD = 'jsonld'
F_GZIP = 'gzip'
F_PNG = 'png'
F_MVT = 'mvt'

#: Formats allowed for ?f= requests (order matters for complex MIME types)
FORMAT_TYPES = OrderedDict((
    (F_HTML, 'text/html'),
    (F_JSONLD, 'application/ld+json'),
    (F_JSON, 'application/json'),
    (F_PNG, 'image/png'),
    (F_MVT, 'application/vnd.mapbox-vector-tile')
))

#: Locale used for system responses (e.g. exceptions)
SYSTEM_LOCALE = l10n.Locale('en', 'US')

CONFORMANCE = {
    'common': [
        'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core',
        'http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections',
        'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page',
        'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json',
        'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/html',
        'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/oas30'
    ],
    'feature': [
        'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core',
        'http://www.opengis.net/spec/ogcapi-features-1/1.0/req/oas30',
        'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html',
        'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson',
        'http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs',
        'http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/queryables',
        'http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/queryables-query-parameters',  # noqa
        'http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/create-replace-delete'  # noqa
    ],
    'coverage': [
        'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/core',
        'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/oas30',
        'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/html',
        'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/geodata-coverage',  # noqa
        'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-subset',  # noqa
        'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-rangesubset',  # noqa
        'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-bbox',  # noqa
        'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-datetime'  # noqa
    ],
    'map': [
        'http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/core'
    ],
    'tile': [
        'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/core',
        'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/mvt'
    ],
    'record': [
        'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/core',
        'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/sorting',
        'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/opensearch',
        'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/json',
        'http://www.opengis.net/spec/ogcapi-records-1/1.0/conf/html'
    ],
    'process': [
        'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/ogc-process-description', # noqa
        'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/core',
        'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/json',
        'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/oas30'
    ],
    'edr': [
        'http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/core'
    ]
}

OGC_RELTYPES_BASE = 'http://www.opengis.net/def/rel/ogc/1.0'

DEFAULT_CRS_LIST = [
    'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
    'http://www.opengis.net/def/crs/OGC/1.3/CRS84h',
]

DEFAULT_CRS = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
DEFAULT_STORAGE_CRS = DEFAULT_CRS


def pre_process(func):
    """
    Decorator that transforms an incoming Request instance specific to the
    web framework (i.e. Flask, Starlette or Django) into a generic
    :class:`APIRequest` instance.

    :param func: decorated function

    :returns: `func`
    """

    def inner(*args):
        cls, req_in = args[:2]
        req_out = APIRequest.with_data(req_in, getattr(cls, 'locales', set()))
        if len(args) > 2:
            return func(cls, req_out, *args[2:])
        else:
            return func(cls, req_out)

    return inner


def gzip(func):
    """
    Decorator that compresses the content of an outgoing API result
    instance if the Content-Encoding response header was set to gzip.

    :param func: decorated function

    :returns: `func`
    """

    def inner(*args, **kwargs):
        headers, status, content = func(*args, **kwargs)
        charset = CHARSET[0]
        if F_GZIP in headers.get('Content-Encoding', []):
            try:
                if isinstance(content, bytes):
                    # bytes means Content-Type needs to be set upstream
                    content = compress(content)
                else:
                    headers['Content-Type'] = \
                        f"{headers['Content-Type']}; charset={charset}"
                    content = compress(content.encode(charset))
            except TypeError as err:
                headers.pop('Content-Encoding')
                LOGGER.error(f'Error in compression: {err}')

        return headers, status, content

    return inner


class APIRequest:
    """
    Transforms an incoming server-specific Request into an object
    with some generic helper methods and properties.

    .. note::   Typically, this instance is created automatically by the
                :func:`pre_process` decorator. **Every** API method that has
                been routed to a REST endpoint should be decorated by the
                :func:`pre_process` function.
                Therefore, **all** routed API methods should at least have 1
                argument that holds the (transformed) request.

    The following example API method will:

    - transform the incoming Flask/Starlette/Django `Request` into an
      `APIRequest`using the :func:`pre_process` decorator;
    - call :meth:`is_valid` to check if the incoming request was valid, i.e.
      that the user requested a valid output format or no format at all
      (which means the default format);
    - call :meth:`API.get_format_exception` if the requested format was
      invalid;
    - create a `dict` with the appropriate `Content-Type` header for the
      requested format and a `Content-Language` header if any specific language
      was requested.

    .. code-block:: python

       @pre_process
       def example_method(self, request: Union[APIRequest, Any], custom_arg):
          if not request.is_valid():
             return self.get_format_exception(request)

          headers = request.get_response_headers()

          # generate response_body here

          return headers, HTTPStatus.OK, response_body


    The following example API method is similar as the one above, but will also
    allow the user to request a non-standard format (e.g. ``f=xml``).
    If `xml` was requested, we set the `Content-Type` ourselves. For the
    standard formats, the `APIRequest` object sets the `Content-Type`.

    .. code-block:: python

       @pre_process
       def example_method(self, request: Union[APIRequest, Any], custom_arg):
          if not request.is_valid(['xml']):
             return self.get_format_exception(request)

          content_type = 'application/xml' if request.format == 'xml' else None
          headers = request.get_response_headers(content_type)

          # generate response_body here

          return headers, HTTPStatus.OK, response_body

    Note that you don't *have* to call :meth:`is_valid`, but that you can also
    perform a custom check on the requested output format by looking at the
    :attr:`format` property.
    Other query parameters are available through the :attr:`params` property as
    a `dict`. The request body is available through the :attr:`data` property.

    .. note::   If the request data (body) is important, **always** create a
                new `APIRequest` instance using the :meth:`with_data` factory
                method.
                The :func:`pre_process` decorator will use this automatically.

    :param request:             The web platform specific Request instance.
    :param supported_locales:   List or set of supported Locale instances.
    """
    def __init__(self, request, supported_locales):
        # Set default request data
        self._data = b''

        # Copy request query parameters
        self._args = self._get_params(request)

        # Get path info
        if hasattr(request, 'scope'):
            self._path_info = request.scope['path'].strip('/')
        elif hasattr(request.headers, 'environ'):
            self._path_info = request.headers.environ['PATH_INFO'].strip('/')
        elif hasattr(request, 'path_info'):
            self._path_info = request.path_info

        # Extract locale from params or headers
        self._raw_locale, self._locale = self._get_locale(request.headers,
                                                          supported_locales)

        # Determine format
        self._format = self._get_format(request.headers)

        # Get received headers
        self._headers = self.get_request_headers(request.headers)

    @classmethod
    def with_data(cls, request, supported_locales) -> 'APIRequest':
        """
        Factory class method to create an `APIRequest` instance with data.

        If the request body is required, an `APIRequest` should always be
        instantiated using this class method. The reason for this is, that the
        Starlette request body needs to be awaited (async), which cannot be
        achieved in the :meth:`__init__` method of the `APIRequest`.
        However, `APIRequest` can still be initialized using :meth:`__init__`,
        but then the :attr:`data` property value will always be empty.

        :param request:             The web platform specific Request instance.
        :param supported_locales:   List or set of supported Locale instances.
        :returns:                   An `APIRequest` instance with data.
        """

        api_req = cls(request, supported_locales)
        if hasattr(request, 'data'):
            # Set data from Flask request
            api_req._data = request.data
        elif hasattr(request, 'body'):
            if 'django' in str(request.__class__):
                # Set data from Django request
                api_req._data = request.body
            else:
                try:
                    import nest_asyncio
                    nest_asyncio.apply()
                    # Set data from Starlette request after async
                    # coroutine completion
                    # TODO:
                    # this now blocks, but once Flask v2 with async support
                    # has been implemented, with_data() can become async too
                    loop = asyncio.get_event_loop()
                    api_req._data = loop.run_until_complete(request.body())
                except ModuleNotFoundError:
                    LOGGER.error('Module nest-asyncio not found')
        return api_req

    @staticmethod
    def _get_params(request):
        """
        Extracts the query parameters from the `Request` object.

        :param request: A Flask or Starlette Request instance
        :returns: `ImmutableMultiDict` or empty `dict`
        """

        if hasattr(request, 'args'):
            # Return ImmutableMultiDict from Flask request
            return request.args
        elif hasattr(request, 'query_params'):
            # Return ImmutableMultiDict from Starlette request
            return request.query_params
        elif hasattr(request, 'GET'):
            # Return QueryDict from Django GET request
            return request.GET
        elif hasattr(request, 'POST'):
            # Return QueryDict from Django GET request
            return request.POST
        LOGGER.debug('No query parameters found')
        return {}

    def _get_locale(self, headers, supported_locales):
        """
        Detects locale from "lang=<language>" param or `Accept-Language`
        header. Returns a tuple of (raw, locale) if found in params or headers.
        Returns a tuple of (raw default, default locale) if not found.

        :param headers: A dict with Request headers
        :param supported_locales: List or set of supported Locale instances
        :returns: A tuple of (str, Locale)
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
                # Check if locale string is a good match for the UI
                loc = l10n.best_match(loc_str, supported_locales)
                is_override = func is l10n.locale_from_params
                if loc != default_locale or is_override:
                    return raw, loc

        return raw, default_locale

    def _get_format(self, headers) -> Union[str, None]:
        """
        Get `Request` format type from query parameters or headers.

        :param headers: Dict of Request headers
        :returns: format value or None if not found/specified
        """

        # Optional f=html or f=json query param
        # Overrides Accept header and might differ from FORMAT_TYPES
        format_ = (self._args.get('f') or '').strip()
        if format_:
            return format_

        # Format not specified: get from Accept headers (MIME types)
        # e.g. format_ = 'text/html'
        h = headers.get('accept', headers.get('Accept', '')).strip() # noqa
        (fmts, mimes) = zip(*FORMAT_TYPES.items())
        # basic support for complex types (i.e. with "q=0.x")
        for type_ in (t.split(';')[0].strip() for t in h.split(',') if t):
            if type_ in mimes:
                idx_ = mimes.index(type_)
                format_ = fmts[idx_]
                break

        return format_ or None

    @property
    def data(self) -> bytes:
        """Returns the additional data send with the Request (bytes)"""
        return self._data

    @property
    def params(self) -> dict:
        """Returns the Request query parameters dict"""
        return self._args

    @property
    def path_info(self) -> str:
        """Returns the web server request path info part"""
        return self._path_info

    @property
    def locale(self) -> l10n.Locale:
        """
        Returns the user-defined locale from the request object.
        If no locale has been defined or if it is invalid,
        the default server locale is returned.

        .. note::   The locale here determines the language in which pygeoapi
                    should return its responses. This may not be the language
                    that the user requested. It may also not be the language
                    that is supported by a collection provider, for example.
                    For this reason, you should pass the `raw_locale` property
                    to the :func:`l10n.get_plugin_locale` function, so that
                    the best match for the provider can be determined.

        :returns: babel.core.Locale
        """

        return self._locale

    @property
    def raw_locale(self) -> Union[str, None]:
        """
        Returns the raw locale string from the `Request` object.
        If no "lang" query parameter or `Accept-Language` header was found,
        `None` is returned.
        Pass this value to the :func:`l10n.get_plugin_locale` function to let
        the provider determine a best match for the locale, which may be
        different from the locale used by pygeoapi's UI.

        :returns: a locale string or None
        """

        return self._raw_locale

    @property
    def format(self) -> Union[str, None]:
        """
        Returns the content type format from the
        request query parameters or headers.

        :returns: Format name or None
        """

        return self._format

    @property
    def headers(self) -> dict:
        """
        Returns the dictionary of the headers from
        the request.

        :returns: Request headers dictionary
        """

        return self._headers

    def get_linkrel(self, format_: str) -> str:
        """
        Returns the hyperlink relationship (rel) attribute value for
        the given API format string.

        The string is compared against the request format and if it matches,
        the value 'self' is returned. Otherwise, 'alternate' is returned.
        However, if `format_` is 'json' and *no* request format was found,
        the relationship 'self' is returned as well (JSON is the default).

        :param format_: The format to compare the request format against.
        :returns: A string 'self' or 'alternate'.
        """

        fmt = format_.lower()
        if fmt == self._format or (fmt == F_JSON and not self._format):
            return 'self'
        return 'alternate'

    def is_valid(self, additional_formats=None) -> bool:
        """
        Returns True if:
            - the format is not set (None)
            - the requested format is supported
            - the requested format exists in a list if additional formats

        .. note::   Format names are matched in a case-insensitive manner.

        :param additional_formats: Optional additional supported formats list

        :returns: bool
        """

        if not self._format:
            return True
        if self._format in FORMAT_TYPES.keys():
            return True
        if self._format in (f.lower() for f in (additional_formats or ())):
            return True
        return False

    def get_response_headers(self, force_lang: l10n.Locale = None,
                             force_type: str = None,
                             force_encoding: str = None,
                             **custom_headers) -> dict:
        """
        Prepares and returns a dictionary with Response object headers.

        This method always adds a 'Content-Language' header, where the value
        is determined by the 'lang' query parameter or 'Accept-Language'
        header from the request.
        If no language was requested, the default pygeoapi language is used,
        unless a `force_lang` override was specified (see notes below).

        A 'Content-Type' header is also always added to the response.
        If the user does not specify `force_type`, the header is based on
        the `format` APIRequest property. If that is invalid, the default MIME
        type `application/json` is used.

        ..note::    If a `force_lang` override is applied, that language
                    is always set as the 'Content-Language', regardless of
                    a 'lang' query parameter or 'Accept-Language' header.
                    If an API response always needs to be in the same
                    language, 'force_lang' should be set to that language.

        :param force_lang: An optional Content-Language header override.
        :param force_type: An optional Content-Type header override.
        :param force_encoding: An optional Content-Encoding header override.
        :returns: A header dict
        """

        headers = HEADERS.copy()
        headers.update(**custom_headers)
        l10n.set_response_language(headers, force_lang or self._locale)
        if force_type:
            # Set custom MIME type if specified
            headers['Content-Type'] = force_type
        elif self.is_valid() and self._format:
            # Set MIME type for valid formats
            headers['Content-Type'] = FORMAT_TYPES[self._format]

        if F_GZIP in FORMAT_TYPES:
            if force_encoding:
                headers['Content-Encoding'] = force_encoding
            elif F_GZIP in self._headers.get('Accept-Encoding', ''):
                headers['Content-Encoding'] = F_GZIP

        return headers

    def get_request_headers(self, headers) -> dict:
        """
        Obtains and returns a dictionary with Request object headers.

        This method adds the headers of the original request and
        makes them available to the API object.

        :returns: A header dict
        """

        headers_ = {item[0]: item[1] for item in headers.items()}
        return headers_


class API:
    """API object"""

    def __init__(self, config):
        """
        constructor

        :param config: configuration dict

        :returns: `pygeoapi.API` instance
        """

        self.config = config
        self.api_headers = get_api_rules(self.config).response_headers
        self.base_url = get_base_url(self.config)
        self.prefetcher = UrlPrefetcher()

        CHARSET[0] = config['server'].get('encoding', 'utf-8')
        if config['server'].get('gzip'):
            FORMAT_TYPES[F_GZIP] = 'application/gzip'
            FORMAT_TYPES.move_to_end(F_JSON)

        # Process language settings (first locale is default!)
        self.locales = l10n.get_locales(config)
        self.default_locale = self.locales[0]

        if 'templates' not in self.config['server']:
            self.config['server']['templates'] = {'path': TEMPLATES}

        if 'pretty_print' not in self.config['server']:
            self.config['server']['pretty_print'] = False

        self.pretty_print = self.config['server']['pretty_print']

        setup_logger(self.config['logging'])

        # Create config clone for HTML templating with modified base URL
        self.tpl_config = deepcopy(self.config)
        self.tpl_config['server']['url'] = self.base_url

        self.manager = get_manager(self.config)
        LOGGER.info('Process manager plugin loaded')

    @gzip
    @pre_process
    @jsonldify
    def landing_page(self,
                     request: Union[APIRequest, Any]) -> Tuple[dict, int, str]:
        """
        Provide API landing page

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
            'rel': request.get_linkrel(F_JSON),
            'type': FORMAT_TYPES[F_JSON],
            'title': 'This document as JSON',
            'href': f"{self.base_url}?f={F_JSON}"
        }, {
            'rel': request.get_linkrel(F_JSONLD),
            'type': FORMAT_TYPES[F_JSONLD],
            'title': 'This document as RDF (JSON-LD)',
            'href': f"{self.base_url}?f={F_JSONLD}"
        }, {
            'rel': request.get_linkrel(F_HTML),
            'type': FORMAT_TYPES[F_HTML],
            'title': 'This document as HTML',
            'href': f"{self.base_url}?f={F_HTML}",
            'hreflang': self.default_locale
        }, {
            'rel': 'service-desc',
            'type': 'application/vnd.oai.openapi+json;version=3.0',
            'title': 'The OpenAPI definition as JSON',
            'href': f"{self.base_url}/openapi"
        }, {
            'rel': 'service-doc',
            'type': FORMAT_TYPES[F_HTML],
            'title': 'The OpenAPI definition as HTML',
            'href': f"{self.base_url}/openapi?f={F_HTML}",
            'hreflang': self.default_locale
        }, {
            'rel': 'conformance',
            'type': FORMAT_TYPES[F_JSON],
            'title': 'Conformance',
            'href': f"{self.base_url}/conformance"
        }, {
            'rel': 'data',
            'type': FORMAT_TYPES[F_JSON],
            'title': 'Collections',
            'href': self.get_collections_url()
        }, {
            'rel': 'http://www.opengis.net/def/rel/ogc/1.0/processes',
            'type': FORMAT_TYPES[F_JSON],
            'title': 'Processes',
            'href': f"{self.base_url}/processes"
        }, {
            'rel': 'http://www.opengis.net/def/rel/ogc/1.0/job-list',
            'type': FORMAT_TYPES[F_JSON],
            'title': 'Jobs',
            'href': f"{self.base_url}/jobs"
        }]

        headers = request.get_response_headers(**self.api_headers)
        if request.format == F_HTML:  # render

            fcm['processes'] = False
            fcm['stac'] = False
            fcm['collection'] = False

            if filter_dict_by_key_value(self.config['resources'],
                                        'type', 'process'):
                fcm['processes'] = True

            if filter_dict_by_key_value(self.config['resources'],
                                        'type', 'stac-collection'):
                fcm['stac'] = True

            if filter_dict_by_key_value(self.config['resources'],
                                        'type', 'collection'):
                fcm['collection'] = True

            content = render_j2_template(self.tpl_config, 'landing_page.html',
                                         fcm, request.locale)
            return headers, HTTPStatus.OK, content

        if request.format == F_JSONLD:
            return headers, HTTPStatus.OK, to_json(
                self.fcmld, self.pretty_print)

        return headers, HTTPStatus.OK, to_json(fcm, self.pretty_print)

    @gzip
    @pre_process
    def openapi(self, request: Union[APIRequest, Any],
                openapi) -> Tuple[dict, int, str]:
        """
        Provide OpenAPI document

        :param request: A request object
        :param openapi: dict of OpenAPI definition

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        headers = request.get_response_headers(**self.api_headers)

        if request.format == F_HTML:
            template = 'openapi/swagger.html'
            if request._args.get('ui') == 'redoc':
                template = 'openapi/redoc.html'

            path = f'{self.base_url}/openapi'
            data = {
                'openapi-document-path': path
            }
            content = render_j2_template(self.tpl_config, template, data,
                                         request.locale)
            return headers, HTTPStatus.OK, content

        headers['Content-Type'] = 'application/vnd.oai.openapi+json;version=3.0'  # noqa

        if isinstance(openapi, dict):
            return headers, HTTPStatus.OK, to_json(openapi, self.pretty_print)
        else:
            return headers, HTTPStatus.OK, openapi

    @gzip
    @pre_process
    def conformance(self,
                    request: Union[APIRequest, Any]) -> Tuple[dict, int, str]:
        """
        Provide conformance definition

        :param request: A request object

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        conformance_list = CONFORMANCE['common']

        for key, value in self.config['resources'].items():
            if value['type'] == 'process':
                conformance_list.extend(CONFORMANCE[value['type']])
            else:
                for provider in value['providers']:
                    if provider['type'] in CONFORMANCE:
                        conformance_list.extend(CONFORMANCE[provider['type']])

        conformance = {
            'conformsTo': list(set(conformance_list))
        }

        headers = request.get_response_headers(**self.api_headers)
        if request.format == F_HTML:  # render
            content = render_j2_template(self.tpl_config, 'conformance.html',
                                         conformance, request.locale)
            return headers, HTTPStatus.OK, content

        return headers, HTTPStatus.OK, to_json(conformance, self.pretty_print)

    @gzip
    @pre_process
    @jsonldify
    def describe_collections(self, request: Union[APIRequest, Any],
                             dataset=None) -> Tuple[dict, int, str]:
        """
        Provide collection metadata

        :param request: A request object
        :param dataset: name of collection

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers(**self.api_headers)

        fcm = {
            'collections': [],
            'links': []
        }

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if all([dataset is not None, dataset not in collections.keys()]):
            msg = 'Collection not found'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

        if dataset is not None:
            collections_dict = {
                k: v for k, v in collections.items() if k == dataset
            }
        else:
            collections_dict = collections

        LOGGER.debug('Creating collections')
        for k, v in collections_dict.items():
            if v.get('visibility', 'default') == 'hidden':
                LOGGER.debug(f'Skipping hidden layer: {k}')
                continue
            collection_data = get_provider_default(v['providers'])
            collection_data_type = collection_data['type']

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

            LOGGER.debug('Processing configured collection links')
            for link in l10n.translate(v.get('links', []), request.locale):
                lnk = {
                    'type': link['type'],
                    'rel': link['rel'],
                    'title': l10n.translate(link['title'], request.locale),
                    'href': l10n.translate(link['href'], request.locale),
                }
                if 'hreflang' in link:
                    lnk['hreflang'] = l10n.translate(
                        link['hreflang'], request.locale)
                content_length = link.get('length', 0)

                if lnk['rel'] == 'enclosure' and content_length == 0:
                    # Issue HEAD request for enclosure links without length
                    lnk_headers = self.prefetcher.get_headers(lnk['href'])
                    content_length = int(lnk_headers.get('content-length', 0))
                    content_type = lnk_headers.get('content-type', lnk['type'])
                    if content_length == 0:
                        # Skip this (broken) link
                        LOGGER.debug(f"Enclosure {lnk['href']} is invalid")
                        continue
                    if content_type != lnk['type']:
                        # Update content type if different from specified
                        lnk['type'] = content_type
                        LOGGER.debug(
                            f"Fixed media type for enclosure {lnk['href']}")

                if content_length > 0:
                    lnk['length'] = content_length

                collection['links'].append(lnk)

            # TODO: provide translations
            LOGGER.debug('Adding JSON and HTML link relations')
            collection['links'].append({
                'type': FORMAT_TYPES[F_JSON],
                'rel': 'root',
                'title': 'The landing page of this server as JSON',
                'href': f"{self.base_url}?f={F_JSON}"
            })
            collection['links'].append({
                'type': FORMAT_TYPES[F_HTML],
                'rel': 'root',
                'title': 'The landing page of this server as HTML',
                'href': f"{self.base_url}?f={F_HTML}"
            })
            collection['links'].append({
                'type': FORMAT_TYPES[F_JSON],
                'rel': request.get_linkrel(F_JSON),
                'title': 'This document as JSON',
                'href': f'{self.get_collections_url()}/{k}?f={F_JSON}'
            })
            collection['links'].append({
                'type': FORMAT_TYPES[F_JSONLD],
                'rel': request.get_linkrel(F_JSONLD),
                'title': 'This document as RDF (JSON-LD)',
                'href': f'{self.get_collections_url()}/{k}?f={F_JSONLD}'
            })
            collection['links'].append({
                'type': FORMAT_TYPES[F_HTML],
                'rel': request.get_linkrel(F_HTML),
                'title': 'This document as HTML',
                'href': f'{self.get_collections_url()}/{k}?f={F_HTML}'
            })

            if collection_data_type in ['feature', 'record', 'tile']:
                # TODO: translate
                collection['itemType'] = collection_data_type
                LOGGER.debug('Adding feature/record based links')
                collection['links'].append({
                    'type': 'application/schema+json',
                    'rel': 'http://www.opengis.net/def/rel/ogc/1.0/queryables',
                    'title': 'Queryables for this collection as JSON',
                    'href': f'{self.get_collections_url()}/{k}/queryables?f={F_JSON}'  # noqa
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': 'http://www.opengis.net/def/rel/ogc/1.0/queryables',
                    'title': 'Queryables for this collection as HTML',
                    'href': f'{self.get_collections_url()}/{k}/queryables?f={F_HTML}'  # noqa
                })
                collection['links'].append({
                    'type': 'application/geo+json',
                    'rel': 'items',
                    'title': 'items as GeoJSON',
                    'href': f'{self.get_collections_url()}/{k}/items?f={F_JSON}'  # noqa
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_JSONLD],
                    'rel': 'items',
                    'title': 'items as RDF (GeoJSON-LD)',
                    'href': f'{self.get_collections_url()}/{k}/items?f={F_JSONLD}'  # noqa
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': 'items',
                    'title': 'Items as HTML',
                    'href': f'{self.get_collections_url()}/{k}/items?f={F_HTML}'  # noqa
                })

                # OAPIF Part 2 - list supported CRSs and StorageCRS
                if collection_data_type == 'feature':
                    collection['crs'] = get_supported_crs_list(collection_data, DEFAULT_CRS_LIST) # noqa
                    collection['storageCRS'] = collection_data.get('storage_crs', DEFAULT_STORAGE_CRS) # noqa
                    if 'storage_crs_coordinate_epoch' in collection_data:
                        collection['storageCrsCoordinateEpoch'] = collection_data.get('storage_crs_coordinate_epoch') # noqa

            elif collection_data_type == 'coverage':
                # TODO: translate
                LOGGER.debug('Adding coverage based links')
                collection['links'].append({
                    'type': FORMAT_TYPES[F_JSON],
                    'rel': 'collection',
                    'title': 'Detailed Coverage metadata in JSON',
                    'href': f'{self.get_collections_url()}/{k}?f={F_JSON}'
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': 'collection',
                    'title': 'Detailed Coverage metadata in HTML',
                    'href': f'{self.get_collections_url()}/{k}?f={F_HTML}'
                })
                coverage_url = f'{self.get_collections_url()}/{k}/coverage'

                collection['links'].append({
                    'type': FORMAT_TYPES[F_JSON],
                    'rel': f'{OGC_RELTYPES_BASE}/coverage-domainset',
                    'title': 'Coverage domain set of collection in JSON',
                    'href': f'{coverage_url}/domainset?f={F_JSON}'
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': f'{OGC_RELTYPES_BASE}/coverage-domainset',
                    'title': 'Coverage domain set of collection in HTML',
                    'href': f'{coverage_url}/domainset?f={F_HTML}'
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_JSON],
                    'rel': f'{OGC_RELTYPES_BASE}/coverage-rangetype',
                    'title': 'Coverage range type of collection in JSON',
                    'href': f'{coverage_url}/rangetype?f={F_JSON}'
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': f'{OGC_RELTYPES_BASE}/coverage-rangetype',
                    'title': 'Coverage range type of collection in HTML',
                    'href': f'{coverage_url}/rangetype?f={F_HTML}'
                })
                collection['links'].append({
                    'type': 'application/prs.coverage+json',
                    'rel': f'{OGC_RELTYPES_BASE}/coverage',
                    'title': 'Coverage data as CoverageJSON',
                    'href': f'{self.get_collections_url()}/{k}/coverage?f={F_JSON}'  # noqa
                })
                if dataset is not None:
                    LOGGER.debug('Creating extended coverage metadata')
                    try:
                        provider_def = get_provider_by_type(
                            self.config['resources'][k]['providers'],
                            'coverage')
                        p = load_plugin('provider', provider_def)
                    except ProviderConnectionError:
                        msg = 'connection error (check logs)'
                        return self.get_exception(
                            HTTPStatus.INTERNAL_SERVER_ERROR,
                            headers, request.format,
                            'NoApplicableCode', msg)
                    except ProviderTypeError:
                        pass
                    else:
                        for f in p.supported_output_formats:
                            collection['links'].append(
                                {
                                 'type': p.get_format_mimetype(f),
                                 'rel': f'{OGC_RELTYPES_BASE}/coverage',
                                 'title': f'Coverage data as {f}',
                                 'href': f'{self.get_collections_url()}/{k}/coverage?f={f}'  # noqa
                                 }
                            )
                        collection['crs'] = [p.crs]
                        collection['domainset'] = p.get_coverage_domainset()
                        collection['rangetype'] = p.get_coverage_rangetype()

            try:
                tile = get_provider_by_type(v['providers'], 'tile')
                p = load_plugin('provider', tile)
            except ProviderConnectionError:
                msg = 'connection error (check logs)'
                return self.get_exception(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    headers, request.format,
                    'NoApplicableCode', msg)
            except ProviderTypeError:
                tile = None

            if tile:
                # TODO: translate

                LOGGER.debug('Adding tile links')
                collection['links'].append({
                    'type': FORMAT_TYPES[F_JSON],
                    'rel': f'http://www.opengis.net/def/rel/ogc/1.0/tilesets-{p.tile_type}',  # noqa
                    'title': 'Tiles as JSON',
                    'href': f'{self.get_collections_url()}/{k}/tiles?f={F_JSON}'  # noqa
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': f'http://www.opengis.net/def/rel/ogc/1.0/tilesets-{p.tile_type}',  # noqa
                    'title': 'Tiles as HTML',
                    'href': f'{self.get_collections_url()}/{k}/tiles?f={F_HTML}'  # noqa
                })

            try:
                map_ = get_provider_by_type(v['providers'], 'map')
            except ProviderTypeError:
                map_ = None

            if map_:
                LOGGER.debug('Adding map links')

                map_mimetype = map_['format']['mimetype']
                map_format = map_['format']['name']

                collection['links'].append({
                    'type': map_mimetype,
                    'rel': 'http://www.opengis.net/def/rel/ogc/1.0/map',
                    'title': f'Map as {map_format}',
                    'href': f"{self.get_collections_url()}/{k}/map?f={map_format}"  # noqa
                })

            try:
                edr = get_provider_by_type(v['providers'], 'edr')
            except ProviderTypeError:
                edr = None

            if edr and dataset is not None:
                # TODO: translate
                LOGGER.debug('Adding EDR links')
                try:
                    p = load_plugin('provider', get_provider_by_type(
                        self.config['resources'][dataset]['providers'], 'edr'))
                    parameters = p.get_fields()
                    if parameters:
                        collection['parameter-names'] = {}
                        for f in parameters['field']:
                            collection['parameter-names'][f['id']] = f

                    for qt in p.get_query_types():
                        collection['links'].append({
                            'type': 'application/json',
                            'rel': 'data',
                            'title': f'{qt} query for this collection as JSON',
                            'href': f'{self.get_collections_url()}/{k}/{qt}?f={F_JSON}'  # noqa
                        })
                        collection['links'].append({
                            'type': FORMAT_TYPES[F_HTML],
                            'rel': 'data',
                            'title': f'{qt} query for this collection as HTML',
                            'href': f'{self.get_collections_url()}/{k}/{qt}?f={F_HTML}'  # noqa
                        })
                except ProviderConnectionError:
                    msg = 'connection error (check logs)'
                    return self.get_exception(
                        HTTPStatus.INTERNAL_SERVER_ERROR, headers,
                        request.format, 'NoApplicableCode', msg)
                except ProviderTypeError:
                    pass

            if dataset is not None and k == dataset:
                fcm = collection
                break

            fcm['collections'].append(collection)

        if dataset is None:
            # TODO: translate
            fcm['links'].append({
                'type': FORMAT_TYPES[F_JSON],
                'rel': request.get_linkrel(F_JSON),
                'title': 'This document as JSON',
                'href': f'{self.get_collections_url()}?f={F_JSON}'
            })
            fcm['links'].append({
                'type': FORMAT_TYPES[F_JSONLD],
                'rel': request.get_linkrel(F_JSONLD),
                'title': 'This document as RDF (JSON-LD)',
                'href': f'{self.get_collections_url()}?f={F_JSONLD}'
            })
            fcm['links'].append({
                'type': FORMAT_TYPES[F_HTML],
                'rel': request.get_linkrel(F_HTML),
                'title': 'This document as HTML',
                'href': f'{self.get_collections_url()}?f={F_HTML}'
            })

        if request.format == F_HTML:  # render
            fcm['collections_path'] = self.get_collections_url()
            if dataset is not None:
                content = render_j2_template(self.tpl_config,
                                             'collections/collection.html',
                                             fcm, request.locale)
            else:
                content = render_j2_template(self.tpl_config,
                                             'collections/index.html', fcm,
                                             request.locale)

            return headers, HTTPStatus.OK, content

        if request.format == F_JSONLD:
            jsonld = self.fcmld.copy()
            if dataset is not None:
                jsonld['dataset'] = jsonldify_collection(self, fcm,
                                                         request.locale)
            else:
                jsonld['dataset'] = [
                    jsonldify_collection(self, c, request.locale)
                    for c in fcm.get('collections', [])
                ]
            return headers, HTTPStatus.OK, to_json(jsonld, self.pretty_print)

        return headers, HTTPStatus.OK, to_json(fcm, self.pretty_print)

    @gzip
    @pre_process
    @jsonldify
    def get_collection_queryables(self, request: Union[APIRequest, Any],
                                  dataset=None) -> Tuple[dict, int, str]:
        """
        Provide collection queryables

        :param request: A request object
        :param dataset: name of collection

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers(**self.api_headers)

        if any([dataset is None,
                dataset not in self.config['resources'].keys()]):

            msg = 'Collection not found'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

        LOGGER.debug('Creating collection queryables')
        try:
            LOGGER.debug('Loading feature provider')
            p = load_plugin('provider', get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'feature'))
        except ProviderTypeError:
            LOGGER.debug('Loading record provider')
            p = load_plugin('provider', get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'record'))
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)

        queryables = {
            'type': 'object',
            'title': l10n.translate(
                self.config['resources'][dataset]['title'], request.locale),
            'properties': {},
            '$schema': 'http://json-schema.org/draft/2019-09/schema',
            '$id': f'{self.get_collections_url()}/{dataset}/queryables'
        }

        if p.fields:
            queryables['properties']['geometry'] = {
                '$ref': 'https://geojson.org/schema/Geometry.json'
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

        if request.format == F_HTML:  # render
            queryables['title'] = l10n.translate(
                self.config['resources'][dataset]['title'], request.locale)

            queryables['collections_path'] = self.get_collections_url()

            content = render_j2_template(self.tpl_config,
                                         'collections/queryables.html',
                                         queryables, request.locale)

            return headers, HTTPStatus.OK, content

        headers['Content-Type'] = 'application/schema+json'

        return headers, HTTPStatus.OK, to_json(queryables, self.pretty_print)

    @gzip
    @pre_process
    def get_collection_items(
            self, request: Union[APIRequest, Any],
            dataset) -> Tuple[dict, int, str]:
        """
        Queries collection

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid(PLUGINS['formatter'].keys()):
            return self.get_format_exception(request)

        # Set Content-Language to system locale until provider locale
        # has been determined
        headers = request.get_response_headers(SYSTEM_LOCALE,
                                               **self.api_headers)

        properties = []
        reserved_fieldnames = ['bbox', 'bbox-crs', 'crs', 'f', 'lang', 'limit',
                               'offset', 'resulttype', 'datetime', 'sortby',
                               'properties', 'skipGeometry', 'q',
                               'filter', 'filter-lang']

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            msg = 'Collection not found'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Processing offset parameter')
        try:
            offset = int(request.params.get('offset'))
            if offset < 0:
                msg = 'offset value should be positive or zero'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            offset = 0
        except ValueError:
            msg = 'offset value should be an integer'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        LOGGER.debug('Processing limit parameter')
        try:
            limit = int(request.params.get('limit'))
            # TODO: We should do more validation, against the min and max
            #       allowed by the server configuration
            if limit <= 0:
                msg = 'limit value should be strictly positive'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            limit = int(self.config['server']['limit'])
        except ValueError:
            msg = 'limit value should be an integer'
            return self.get_exception(
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
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)

        LOGGER.debug('Processing datetime parameter')
        datetime_ = request.params.get('datetime')
        try:
            datetime_ = validate_datetime(collections[dataset]['extents'],
                                          datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
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
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'NoApplicableCode', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)

        crs_transform_spec = None
        if provider_type == 'feature':
            # crs query parameter is only available for OGC API - Features
            # right now, not for OGC API - Records.
            LOGGER.debug('Processing crs parameter')
            query_crs_uri = request.params.get('crs')
            try:
                crs_transform_spec = self._create_crs_transform_spec(
                    provider_def, query_crs_uri,
                )
            except (ValueError, CRSError) as err:
                msg = str(err)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)
            self._set_content_crs_header(headers, provider_def, query_crs_uri)

        LOGGER.debug('Processing bbox-crs parameter')
        bbox_crs = request.params.get('bbox-crs')
        if bbox_crs is not None:
            # Validate bbox-crs parameter
            if len(bbox) == 0:
                msg = 'bbox-crs specified without bbox parameter'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'NoApplicableCode', msg)

            if len(bbox_crs) == 0:
                msg = 'bbox-crs specified but is empty'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'NoApplicableCode', msg)

            supported_crs_list = get_supported_crs_list(provider_def, DEFAULT_CRS_LIST) # noqa
            if bbox_crs not in supported_crs_list:
                msg = f'bbox-crs {bbox_crs} not supported for this collection'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'NoApplicableCode', msg)
        elif len(bbox) > 0:
            # bbox but no bbox-crs parm: assume bbox is in default CRS
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
                return self.get_exception(
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
                    return self.get_exception(
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
                return self.get_exception(
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

        LOGGER.debug('processing filter parameter')
        cql_text = request.params.get('filter')
        if cql_text is not None:
            try:
                filter_ = parse_ecql_text(cql_text)
            except Exception as err:
                LOGGER.error(err)
                msg = f'Bad CQL string : {cql_text}'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)
        else:
            filter_ = None

        LOGGER.debug('Processing filter-lang parameter')
        filter_lang = request.params.get('filter-lang')
        # Currently only cql-text is handled, but it is optional
        if filter_lang not in [None, 'cql-text']:
            msg = 'Invalid filter language'
            return self.get_exception(
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
        LOGGER.debug(f'filter-lang: {filter_lang}')

        try:
            content = p.query(offset=offset, limit=limit,
                              resulttype=resulttype, bbox=bbox,
                              datetime_=datetime_, properties=properties,
                              sortby=sortby, skip_geometry=skip_geometry,
                              select_properties=select_properties,
                              crs_transform_spec=crs_transform_spec,
                              q=q, language=prv_locale, filterq=filter_)
        except ProviderConnectionError as err:
            LOGGER.error(err)
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderQueryError as err:
            LOGGER.error(err)
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderGenericError as err:
            LOGGER.error(err)
            msg = 'generic error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)

        serialized_query_params = ''
        for k, v in request.params.items():
            if k not in ('f', 'offset'):
                serialized_query_params += '&'
                serialized_query_params += urllib.parse.quote(k, safe='')
                serialized_query_params += '='
                serialized_query_params += urllib.parse.quote(str(v), safe=',')

        # TODO: translate titles
        uri = f'{self.get_collections_url()}/{dataset}/items'
        content['links'] = [{
            'type': 'application/geo+json',
            'rel': request.get_linkrel(F_JSON),
            'title': 'This document as GeoJSON',
            'href': f'{uri}?f={F_JSON}{serialized_query_params}'
        }, {
            'rel': request.get_linkrel(F_JSONLD),
            'type': FORMAT_TYPES[F_JSONLD],
            'title': 'This document as RDF (JSON-LD)',
            'href': f'{uri}?f={F_JSONLD}{serialized_query_params}'
        }, {
            'type': FORMAT_TYPES[F_HTML],
            'rel': request.get_linkrel(F_HTML),
            'title': 'This document as HTML',
            'href': f'{uri}?f={F_HTML}{serialized_query_params}'
        }]

        if offset > 0:
            prev = max(0, offset - limit)
            content['links'].append(
                {
                    'type': 'application/geo+json',
                    'rel': 'prev',
                    'title': 'items (prev)',
                    'href': f'{uri}?offset={prev}{serialized_query_params}'
                })

        if len(content['features']) == limit:
            next_ = offset + limit
            content['links'].append(
                {
                    'type': 'application/geo+json',
                    'rel': 'next',
                    'title': 'items (next)',
                    'href': f'{uri}?offset={next_}{serialized_query_params}'
                })

        content['links'].append(
            {
                'type': FORMAT_TYPES[F_JSON],
                'title': l10n.translate(
                    collections[dataset]['title'], request.locale),
                'rel': 'collection',
                'href': uri
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
            content['collections_path'] = self.get_collections_url()

            content['offset'] = offset

            content['id_field'] = p.id_field
            if p.uri_field is not None:
                content['uri_field'] = p.uri_field
            if p.title_field is not None:
                content['title_field'] = l10n.translate(p.title_field,
                                                        request.locale)
                # If title exists, use it as id in html templates
                content['id_field'] = content['title_field']
            content = render_j2_template(self.tpl_config,
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
            except FormatterSerializationError as err:
                LOGGER.error(err)
                msg = 'Error serializing output'
                return self.get_exception(
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
                self, content, dataset, id_field=(p.uri_field or 'id')
            )

        return headers, HTTPStatus.OK, to_json(content, self.pretty_print)

    @gzip
    @pre_process
    def post_collection_items(
            self, request: Union[APIRequest, Any],
            dataset) -> Tuple[dict, int, str]:
        """
        Queries collection or filter an item

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        request_headers = request.headers

        if not request.is_valid(PLUGINS['formatter'].keys()):
            return self.get_format_exception(request)

        # Set Content-Language to system locale until provider locale
        # has been determined
        headers = request.get_response_headers(SYSTEM_LOCALE,
                                               **self.api_headers)

        properties = []
        reserved_fieldnames = ['bbox', 'f', 'limit', 'offset',
                               'resulttype', 'datetime', 'sortby',
                               'properties', 'skipGeometry', 'q',
                               'filter-lang']

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            msg = 'Invalid collection'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Processing offset parameter')
        try:
            offset = int(request.params.get('offset'))
            if offset < 0:
                msg = 'offset value should be positive or zero'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            offset = 0
        except ValueError:
            msg = 'offset value should be an integer'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        LOGGER.debug('Processing limit parameter')
        try:
            limit = int(request.params.get('limit'))
            # TODO: We should do more validation, against the min and max
            # allowed by the server configuration
            if limit <= 0:
                msg = 'limit value should be strictly positive'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            limit = int(self.config['server']['limit'])
        except ValueError:
            msg = 'limit value should be an integer'
            return self.get_exception(
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
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)

        LOGGER.debug('Processing datetime parameter')
        datetime_ = request.params.get('datetime')
        try:
            datetime_ = validate_datetime(collections[dataset]['extents'],
                                          datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        LOGGER.debug('processing q parameter')
        val = request.params.get('q')

        q = None
        if val is not None:
            q = val

        LOGGER.debug('Loading provider')

        try:
            p = load_plugin('provider', get_provider_by_type(
                collections[dataset]['providers'], 'feature'))
        except ProviderTypeError:
            try:
                p = load_plugin('provider', get_provider_by_type(
                    collections[dataset]['providers'], 'record'))
            except ProviderTypeError:
                msg = 'Invalid provider type'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'NoApplicableCode', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)

        LOGGER.debug('processing property parameters')
        for k, v in request.params.items():
            if k not in reserved_fieldnames and k not in p.fields.keys():
                msg = f'unknown query parameter: {k}'
                return self.get_exception(
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
                    return self.get_exception(
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
                return self.get_exception(
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

        LOGGER.debug('Processing filter-lang parameter')
        filter_lang = request.params.get('filter-lang')
        if filter_lang != 'cql-json':  # @TODO add check from the configuration
            msg = 'Invalid filter language'
            return self.get_exception(
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

        LOGGER.debug('Processing headers')

        LOGGER.debug('Processing request content-type header')
        if (request_headers.get(
            'Content-Type') or request_headers.get(
                'content-type')) != 'application/query-cql-json':
            msg = ('Invalid body content-type')
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidHeaderValue', msg)

        LOGGER.debug('Processing body')

        if not request.data:
            msg = 'missing request data'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'MissingParameterValue', msg)

        filter_ = None
        try:
            # Parse bytes data, if applicable
            data = request.data.decode()
            LOGGER.debug(data)
        except UnicodeDecodeError as err:
            LOGGER.error(err)
            msg = 'Unicode error in data'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        # FIXME: remove testing backend in use once CQL support is normalized
        if p.name == 'PostgreSQL':
            LOGGER.debug('processing PostgreSQL CQL_JSON data')
            try:
                filter_ = parse_cql_json(data)
            except Exception as err:
                LOGGER.error(err)
                msg = f'Bad CQL string : {data}'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)
        else:
            LOGGER.debug('processing Elasticsearch CQL_JSON data')
            try:
                filter_ = CQLModel.parse_raw(data)
            except Exception as err:
                LOGGER.error(err)
                msg = f'Bad CQL string : {data}'
                return self.get_exception(
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
        except ProviderConnectionError as err:
            LOGGER.error(err)
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderQueryError as err:
            LOGGER.error(err)
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderGenericError as err:
            LOGGER.error(err)
            msg = 'generic error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)

        return headers, HTTPStatus.OK, to_json(content, self.pretty_print)

    @gzip
    @pre_process
    def manage_collection_item(
            self, request: Union[APIRequest, Any],
            action, dataset, identifier=None) -> Tuple[dict, int, str]:
        """
        Adds an item to a collection

        :param request: A request object
        :param action: an action among 'create', 'update', 'delete', 'options'
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid(PLUGINS['formatter'].keys()):
            return self.get_format_exception(request)

        # Set Content-Language to system locale until provider locale
        # has been determined
        headers = request.get_response_headers(SYSTEM_LOCALE,
                                               **self.api_headers)

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            msg = 'Collection not found'
            LOGGER.error(msg)
            return self.get_exception(
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
                LOGGER.error(msg)
                return self.get_exception(
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
            LOGGER.error(msg)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        if action in ['create', 'update'] and not request.data:
            msg = 'No data found'
            LOGGER.error(msg)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        if action == 'create':
            LOGGER.debug('Creating item')
            try:
                identifier = p.create(request.data)
            except (ProviderInvalidDataError, TypeError) as err:
                msg = str(err)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)

            headers['Location'] = f'{self.get_collections_url()}/{dataset}/items/{identifier}'  # noqa

            return headers, HTTPStatus.CREATED, ''

        if action == 'update':
            LOGGER.debug('Updating item')
            try:
                _ = p.update(identifier, request.data)
            except (ProviderInvalidDataError, TypeError) as err:
                msg = str(err)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)

            return headers, HTTPStatus.NO_CONTENT, ''

        if action == 'delete':
            LOGGER.debug('Deleting item')
            try:
                _ = p.delete(identifier)
            except ProviderGenericError as err:
                msg = str(err)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)

            return headers, HTTPStatus.OK, ''

    @gzip
    @pre_process
    def get_collection_item(self, request: Union[APIRequest, Any],
                            dataset, identifier) -> Tuple[dict, int, str]:
        """
        Get a single collection item

        :param request: A request object
        :param dataset: dataset name
        :param identifier: item identifier

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        # Set Content-Language to system locale until provider locale
        # has been determined
        headers = request.get_response_headers(SYSTEM_LOCALE,
                                               **self.api_headers)

        LOGGER.debug('Processing query parameters')

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            msg = 'Collection not found'
            return self.get_exception(
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
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)

        crs_transform_spec = None
        if provider_type == 'feature':
            # crs query parameter is only available for OGC API - Features
            # right now, not for OGC API - Records.
            LOGGER.debug('Processing crs parameter')
            query_crs_uri = request.params.get('crs')
            try:
                crs_transform_spec = self._create_crs_transform_spec(
                    provider_def, query_crs_uri,
                )
            except (ValueError, CRSError) as err:
                msg = str(err)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)
            self._set_content_crs_header(headers, provider_def, query_crs_uri)

        # Get provider language (if any)
        prv_locale = l10n.get_plugin_locale(provider_def, request.raw_locale)

        try:
            LOGGER.debug(f'Fetching id {identifier}')
            content = p.get(
                identifier,
                language=prv_locale,
                crs_transform_spec=crs_transform_spec,
            )
        except ProviderConnectionError as err:
            LOGGER.error(err)
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderItemNotFoundError:
            msg = 'identifier not found'
            return self.get_exception(HTTPStatus.NOT_FOUND, headers,
                                      request.format, 'NotFound', msg)
        except ProviderQueryError as err:
            LOGGER.error(err)
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderGenericError as err:
            LOGGER.error(err)
            msg = 'generic error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)

        if content is None:
            msg = 'identifier not found'
            return self.get_exception(HTTPStatus.BAD_REQUEST, headers,
                                      request.format, 'NotFound', msg)

        uri = content['properties'].get(p.uri_field) if p.uri_field else \
            f'{self.get_collections_url()}/{dataset}/items/{identifier}'

        if 'links' not in content:
            content['links'] = []

        content['links'].extend([{
            'type': FORMAT_TYPES[F_JSON],
            'rel': 'root',
            'title': 'The landing page of this server as JSON',
            'href': f"{self.base_url}?f={F_JSON}"
            }, {
            'type': FORMAT_TYPES[F_HTML],
            'rel': 'root',
            'title': 'The landing page of this server as HTML',
            'href': f"{self.base_url}?f={F_HTML}"
            }, {
            'rel': request.get_linkrel(F_JSON),
            'type': 'application/geo+json',
            'title': 'This document as GeoJSON',
            'href': f'{uri}?f={F_JSON}'
            }, {
            'rel': request.get_linkrel(F_JSONLD),
            'type': FORMAT_TYPES[F_JSONLD],
            'title': 'This document as RDF (JSON-LD)',
            'href': f'{uri}?f={F_JSONLD}'
            }, {
            'rel': request.get_linkrel(F_HTML),
            'type': FORMAT_TYPES[F_HTML],
            'title': 'This document as HTML',
            'href': f'{uri}?f={F_HTML}'
            }, {
            'rel': 'collection',
            'type': FORMAT_TYPES[F_JSON],
            'title': l10n.translate(collections[dataset]['title'],
                                    request.locale),
            'href': f'{self.get_collections_url()}/{dataset}'
        }])

        link_request_format = (
            request.format if request.format is not None else F_JSON
        )
        if 'prev' in content:
            content['links'].append({
                'rel': 'prev',
                'type': FORMAT_TYPES[link_request_format],
                'href': f"{self.get_collections_url()}/{dataset}/items/{content['prev']}?f={link_request_format}"  # noqa
            })
        if 'next' in content:
            content['links'].append({
                'rel': 'next',
                'type': FORMAT_TYPES[link_request_format],
                'href': f"{self.get_collections_url()}/{dataset}/items/{content['next']}?f={link_request_format}"  # noqa
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
            content['collections_path'] = self.get_collections_url()

            content = render_j2_template(self.tpl_config,
                                         'collections/items/item.html',
                                         content, request.locale)
            return headers, HTTPStatus.OK, content

        elif request.format == F_JSONLD:
            content = geojson2jsonld(
                self, content, dataset, uri, (p.uri_field or 'id')
            )

        return headers, HTTPStatus.OK, to_json(content, self.pretty_print)

    @pre_process
    @jsonldify
    def get_collection_coverage(self, request: Union[APIRequest, Any],
                                dataset) -> Tuple[dict, int, str]:
        """
        Returns a subset of a collection coverage

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        query_args = {}
        format_ = F_JSON
        # Force response content type and language (en-US only) headers
        headers = request.get_response_headers(SYSTEM_LOCALE,
                                               FORMAT_TYPES[F_JSON],
                                               **self.api_headers)

        LOGGER.debug('Loading provider')
        try:
            collection_def = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'coverage')

            p = load_plugin('provider', collection_def)
        except KeyError:
            msg = 'collection does not exist'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers, format_,
                'InvalidParameterValue', msg)
        except ProviderTypeError:
            msg = 'invalid provider type'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, format_,
                'NoApplicableCode', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, format_,
                'NoApplicableCode', msg)

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
                    HTTPStatus.INTERNAL_SERVER_ERROR, headers, format_,
                    'InvalidParameterValue', msg)

        query_args['bbox'] = bbox

        LOGGER.debug('Processing bbox-crs parameter')

        bbox_crs = request.params.get('bbox-crs')
        if bbox_crs is not None:
            query_args['bbox_crs'] = bbox_crs

        LOGGER.debug('Processing datetime parameter')

        datetime_ = request.params.get('datetime')

        try:
            datetime_ = validate_datetime(
                self.config['resources'][dataset]['extents'], datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, format_,
                'InvalidParameterValue', msg)

        query_args['datetime_'] = datetime_

        if 'f' in request.params:
            # Format explicitly set using a query parameter
            query_args['format_'] = format_ = request.format

        properties = request.params.get('properties')
        if properties:
            LOGGER.debug('Processing properties parameter')
            query_args['properties'] = [rs for
                                        rs in properties.split(',') if rs]
            LOGGER.debug(f"Fields: {query_args['properties']}")

            for a in query_args['properties']:
                if a not in p.fields:
                    msg = 'Invalid field specified'
                    return self.get_exception(
                        HTTPStatus.BAD_REQUEST, headers, format_,
                        'InvalidParameterValue', msg)

        if 'subset' in request.params:
            LOGGER.debug('Processing subset parameter')
            try:
                subsets = validate_subset(request.params['subset'] or '')
            except (AttributeError, ValueError) as err:
                msg = f'Invalid subset: {err}'
                LOGGER.error(msg)
                return self.get_exception(
                        HTTPStatus.BAD_REQUEST, headers, format_,
                        'InvalidParameterValue', msg)

            if not set(subsets.keys()).issubset(p.axes):
                msg = 'Invalid axis name'
                LOGGER.error(msg)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, format_,
                    'InvalidParameterValue', msg)

            query_args['subsets'] = subsets
            LOGGER.debug(f"Subsets: {query_args['subsets']}")

        LOGGER.debug('Querying coverage')
        try:
            data = p.query(**query_args)
        except ProviderInvalidQueryError as err:
            msg = f'query error: {err}'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, format_,
                'InvalidParameterValue', msg)
        except ProviderNoDataError:
            msg = 'No data found'
            return self.get_exception(
                HTTPStatus.NO_CONTENT, headers, format_,
                'InvalidParameterValue', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, format_,
                'NoApplicableCode', msg)

        if format_ == F_JSON:
            headers['Content-Type'] = 'application/prs.coverage+json'
            return headers, HTTPStatus.OK, to_json(data, self.pretty_print)

        if p.filename is not None:
            cd = f'attachment; filename="{p.filename}"'
            headers['Content-Disposition'] = cd

        headers['Content-Type'] = p.get_format_mimetype(format_)
        return headers, HTTPStatus.OK, data

    @gzip
    @pre_process
    @jsonldify
    def get_collection_coverage_domainset(
            self, request: Union[APIRequest, Any],
            dataset) -> Tuple[dict, int, str]:
        """
        Returns a collection coverage domainset

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        format_ = request.format or F_JSON
        headers = request.get_response_headers(**self.api_headers)

        LOGGER.debug('Loading provider')
        try:
            collection_def = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'coverage')

            p = load_plugin('provider', collection_def)

            data = p.get_coverage_domainset()
        except KeyError:
            msg = 'collection does not exist'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers, format_,
                'InvalidParameterValue', msg)
        except ProviderTypeError:
            msg = 'invalid provider type'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, format_,
                'NoApplicableCode', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, format_,
                'NoApplicableCode', msg)

        if format_ == F_JSON:
            return headers, HTTPStatus.OK, to_json(data, self.pretty_print)

        elif format_ == F_HTML:
            data['id'] = dataset
            data['title'] = l10n.translate(
                self.config['resources'][dataset]['title'],
                self.default_locale)
            data['collections_path'] = self.get_collections_url()
            content = render_j2_template(self.tpl_config,
                                         'collections/coverage/domainset.html',
                                         data, self.default_locale)
            return headers, HTTPStatus.OK, content
        else:
            return self.get_format_exception(request)

    @gzip
    @pre_process
    @jsonldify
    def get_collection_coverage_rangetype(
            self, request: Union[APIRequest, Any],
            dataset) -> Tuple[dict, int, str]:
        """
        Returns a collection coverage rangetype

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """
        format_ = request.format or F_JSON
        headers = request.get_response_headers(self.default_locale,
                                               **self.api_headers)
        LOGGER.debug('Loading provider')
        try:
            collection_def = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'coverage')

            p = load_plugin('provider', collection_def)

            data = p.get_coverage_rangetype()
        except KeyError:
            msg = 'collection does not exist'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers, format_,
                'InvalidParameterValue', msg)
        except ProviderTypeError:
            msg = 'invalid provider type'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, format_,
                'NoApplicableCode', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, format_,
                'NoApplicableCode', msg)

        if format_ == F_JSON:
            return headers, HTTPStatus.OK, to_json(data, self.pretty_print)

        elif format_ == F_HTML:
            data['id'] = dataset
            data['title'] = l10n.translate(
                self.config['resources'][dataset]['title'],
                self.default_locale)
            data['collections_path'] = self.get_collections_url()
            content = render_j2_template(self.tpl_config,
                                         'collections/coverage/rangetype.html',
                                         data, self.default_locale)
            return headers, HTTPStatus.OK, content
        else:
            return self.get_format_exception(request)

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
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)

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
            servicepath=f'{self.get_collections_url()}/{dataset}/tiles/{{tileMatrixSetId}}/{{tileMatrix}}/{{tileRow}}/{{tileCol}}?f=mvt'  # noqa
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
            tile_matrix['links'].append(matrix.tileMatrixSetDefinition)
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

        metadata_format = p.options['metadata_format']

        if request.format == F_HTML:  # render
            tiles['id'] = dataset
            tiles['title'] = l10n.translate(
                self.config['resources'][dataset]['title'], SYSTEM_LOCALE)
            tiles['tilesets'] = [
                scheme.tileMatrixSet for scheme in p.get_tiling_schemes()]
            tiles['format'] = metadata_format
            tiles['bounds'] = \
                self.config['resources'][dataset]['extents']['spatial']['bbox']
            tiles['minzoom'] = p.options['zoom']['min']
            tiles['maxzoom'] = p.options['zoom']['max']
            tiles['collections_path'] = self.get_collections_url()

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
                return headers, HTTPStatus.ACCEPTED, content

        # @TODO: figure out if the spec requires to return json errors
        except KeyError:
            msg = 'Invalid collection tiles'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, format_,
                'InvalidParameterValue', msg)
        except ProviderConnectionError as err:
            LOGGER.error(err)
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, format_,
                'NoApplicableCode', msg)
        except ProviderTilesetIdNotFoundError:
            msg = 'Tileset id not found'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers, format_, 'NotFound', msg)
        except ProviderTileQueryError as err:
            LOGGER.error(err)
            msg = 'Tile not found'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, format_,
                'NoApplicableCode', msg)
        except ProviderTileNotFoundError as err:
            LOGGER.error(err)
            msg = 'Tile not found (check logs)'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers, format_, 'NoMatch', msg)
        except ProviderGenericError as err:
            LOGGER.error(err)
            msg = 'Generic error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, format_,
                'NoApplicableCode', msg)

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

        if not request.is_valid():
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
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'InvalidParameterValue', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'InvalidParameterValue', msg)

        # Get provider language (if any)
        prv_locale = l10n.get_plugin_locale(t, request.raw_locale)

        if matrix_id not in p.options['schemes']:
            msg = 'tileset not found'
            return self.get_exception(HTTPStatus.NOT_FOUND, headers,
                                      request.format, 'NotFound', msg)

        metadata_format = TilesMetadataFormat[
            str(p.options['metadata_format']).upper()]

        # Set response language to requested provider locale
        # (if it supports language) and/or otherwise the requested pygeoapi
        # locale (or fallback default locale)
        l10n.set_response_language(headers, prv_locale, request.locale)

        if request.format == F_HTML:  # render
            tiles_metadata = p.get_metadata(
                dataset=dataset, server_url=self.base_url,
                layer=p.get_layer(), tileset=matrix_id,
                metadata_format=TilesMetadataFormat.TILEJSON,
                language=prv_locale)
            metadata = dict()
            metadata['metadata'] = tiles_metadata
            metadata['id'] = dataset
            metadata['title'] = l10n.translate(
                self.config['resources'][dataset]['title'], request.locale)
            metadata['tileset'] = matrix_id
            metadata['format'] = metadata_format.value
            metadata['collections_path'] = self.get_collections_url()

            content = render_j2_template(self.tpl_config,
                                         'collections/tiles/metadata.html',
                                         metadata, request.locale)

            return headers, HTTPStatus.OK, content
        else:
            tiles_metadata = p.get_metadata(
                dataset=dataset, server_url=self.base_url,
                layer=p.get_layer(), tileset=matrix_id,
                metadata_format=metadata_format, title=l10n.translate(
                    self.config['resources'][dataset]['title'],
                    request.locale),
                description=l10n.translate(
                    self.config['resources'][dataset]['description'],
                    request.locale),
                language=prv_locale)

        return headers, HTTPStatus.OK, tiles_metadata

    @gzip
    @pre_process
    def get_collection_map(self, request: Union[APIRequest, Any],
                           dataset, style=None) -> Tuple[dict, int, str]:
        """
        Returns a subset of a collection map

        :param request: A request object
        :param dataset: dataset name
        :param style: style name

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        query_args = {
            'crs': 'CRS84'
        }

        format_ = request.format or 'png'
        headers = request.get_response_headers(**self.api_headers)
        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Loading provider')
        try:
            collection_def = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'map')

            p = load_plugin('provider', collection_def)
        except KeyError:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'collection does not exist'
            }
            headers['Content-type'] = 'application/json'
            LOGGER.error(exception)
            return headers, HTTPStatus.NOT_FOUND, to_json(
                exception, self.pretty_print)
        except ProviderTypeError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'invalid provider type'
            }
            headers['Content-type'] = 'application/json'
            LOGGER.error(exception)
            return headers, HTTPStatus.BAD_REQUEST, to_json(
                exception, self.pretty_print)
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            headers['Content-type'] = 'application/json'
            LOGGER.error(exception)
            return headers, HTTPStatus.INTERNAL_SERVER_ERROR, to_json(
                exception, self.pretty_print)

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
                exception, self.pretty_print)

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
                    exception, self.pretty_print)
        except AttributeError:
            bbox = self.config['resources'][dataset]['extents']['spatial']['bbox']  # noqa
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
                exception, self.pretty_print)

        LOGGER.debug('Processing datetime parameter')
        datetime_ = request.params.get('datetime')
        try:
            query_args['datetime_'] = validate_datetime(
                self.config['resources'][dataset]['extents'], datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        LOGGER.debug('Generating map')
        try:
            data = p.query(**query_args)
        except ProviderInvalidQueryError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': f'query error: {err}'
            }
            LOGGER.error(exception)
            headers['Content-type'] = 'application/json'
            return headers, HTTPStatus.BAD_REQUEST, to_json(
                exception, self.pretty_print)
        except ProviderNoDataError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'No data found'
            }
            LOGGER.debug(exception)
            headers['Content-type'] = 'application/json'
            return headers, HTTPStatus.NO_CONTENT, to_json(
                exception, self.pretty_print)
        except ProviderQueryError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(exception)
            headers['Content-type'] = 'application/json'
            return headers, HTTPStatus.INTERNAL_SERVER_ERROR, to_json(
                exception, self.pretty_print)

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
                data, self.pretty_print)

    @gzip
    def get_collection_map_legend(
            self, request: Union[APIRequest, Any],
            dataset, style=None) -> Tuple[dict, int, str]:
        """
        Returns a subset of a collection map legend

        :param request: A request object
        :param dataset: dataset name
        :param style: style name

        :returns: tuple of headers, status code, content
        """

        format_ = 'png'
        headers = request.get_response_headers(**self.api_headers)
        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Loading provider')
        try:
            collection_def = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'map')

            p = load_plugin('provider', collection_def)
        except KeyError:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'collection does not exist'
            }
            LOGGER.error(exception)
            return headers, HTTPStatus.NOT_FOUND, to_json(
                exception, self.pretty_print)
        except ProviderTypeError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'invalid provider type'
            }
            LOGGER.error(exception)
            return headers, HTTPStatus.BAD_REQUEST, to_json(
                exception, self.pretty_print)
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return headers, HTTPStatus.INTERNAL_SERVER_ERROR, to_json(
                exception, self.pretty_print)

        LOGGER.debug('Generating legend')
        try:
            data = p.get_legend(style, request.params.get('f', 'png'))
        except ProviderInvalidQueryError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': f'query error: {err}'
            }
            LOGGER.error(exception)
            return headers, HTTPStatus.BAD_REQUEST, to_json(
                exception, self.pretty_print)
        except ProviderNoDataError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'No data found'
            }
            LOGGER.debug(exception)
            return headers, HTTPStatus.NO_CONTENT, to_json(
                exception, self.pretty_print)
        except ProviderQueryError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(exception)
            return headers, HTTPStatus.INTERNAL_SERVER_ERROR, to_json(
                exception, self.pretty_print)

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
                data, self.pretty_print)

    @gzip
    @pre_process
    @jsonldify
    def describe_processes(self, request: Union[APIRequest, Any],
                           process=None) -> Tuple[dict, int, str]:
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
        headers = request.get_response_headers(**self.api_headers)

        if process is not None:
            if process not in self.manager.processes.keys():
                msg = 'Identifier not found'
                return self.get_exception(
                    HTTPStatus.NOT_FOUND, headers,
                    request.format, 'NoSuchProcess', msg)

        if len(self.manager.processes) > 0:
            if process is not None:
                relevant_processes = [process]
            else:
                LOGGER.debug('Processing limit parameter')
                try:
                    limit = int(request.params.get('limit'))

                    if limit <= 0:
                        msg = 'limit value should be strictly positive'
                        return self.get_exception(
                            HTTPStatus.BAD_REQUEST, headers, request.format,
                            'InvalidParameterValue', msg)

                    relevant_processes = list(self.manager.processes)[:limit]
                except TypeError:
                    LOGGER.debug('returning all processes')
                    relevant_processes = self.manager.processes.keys()
                except ValueError:
                    msg = 'limit value should be an integer'
                    return self.get_exception(
                        HTTPStatus.BAD_REQUEST, headers, request.format,
                        'InvalidParameterValue', msg)

            for key in relevant_processes:
                p = self.manager.get_processor(key)
                p2 = l10n.translate_struct(deepcopy(p.metadata),
                                           request.locale)

                if process is None:
                    p2.pop('inputs')
                    p2.pop('outputs')
                    p2.pop('example')

                p2['jobControlOptions'] = ['sync-execute']
                if self.manager.is_async:
                    p2['jobControlOptions'].append('async-execute')

                p2['outputTransmission'] = ['value']
                p2['links'] = p2.get('links', [])

                jobs_url = f"{self.base_url}/jobs"
                process_url = f"{self.base_url}/processes/{key}"

                # TODO translation support
                link = {
                    'type': FORMAT_TYPES[F_JSON],
                    'rel': request.get_linkrel(F_JSON),
                    'href': f'{process_url}?f={F_JSON}',
                    'title': 'Process description as JSON',
                    'hreflang': self.default_locale
                }
                p2['links'].append(link)

                link = {
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': request.get_linkrel(F_HTML),
                    'href': f'{process_url}?f={F_HTML}',
                    'title': 'Process description as HTML',
                    'hreflang': self.default_locale
                }
                p2['links'].append(link)

                link = {
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': 'http://www.opengis.net/def/rel/ogc/1.0/job-list',
                    'href': f'{jobs_url}?f={F_HTML}',
                    'title': 'jobs for this process as HTML',
                    'hreflang': self.default_locale
                }
                p2['links'].append(link)

                link = {
                    'type': FORMAT_TYPES[F_JSON],
                    'rel': 'http://www.opengis.net/def/rel/ogc/1.0/job-list',
                    'href': f'{jobs_url}?f={F_JSON}',
                    'title': 'jobs for this process as JSON',
                    'hreflang': self.default_locale
                }
                p2['links'].append(link)

                link = {
                    'type': FORMAT_TYPES[F_JSON],
                    'rel': 'http://www.opengis.net/def/rel/ogc/1.0/execute',
                    'href': f'{process_url}/execution?f={F_JSON}',
                    'title': 'Execution for this process as JSON',
                    'hreflang': self.default_locale
                }
                p2['links'].append(link)

                processes.append(p2)

        if process is not None:
            response = processes[0]
        else:
            process_url = f"{self.base_url}/processes"
            response = {
                'processes': processes,
                'links': [{
                    'type': FORMAT_TYPES[F_JSON],
                    'rel': request.get_linkrel(F_JSON),
                    'title': 'This document as JSON',
                    'href': f'{process_url}?f={F_JSON}'
                }, {
                    'type': FORMAT_TYPES[F_JSONLD],
                    'rel': request.get_linkrel(F_JSONLD),
                    'title': 'This document as RDF (JSON-LD)',
                    'href': f'{process_url}?f={F_JSONLD}'
                }, {
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': request.get_linkrel(F_HTML),
                    'title': 'This document as HTML',
                    'href': f'{process_url}?f={F_HTML}'
                }]
            }

        if request.format == F_HTML:  # render
            if process is not None:
                response = render_j2_template(self.tpl_config,
                                              'processes/process.html',
                                              response, request.locale)
            else:
                response = render_j2_template(self.tpl_config,
                                              'processes/index.html', response,
                                              request.locale)

            return headers, HTTPStatus.OK, response

        return headers, HTTPStatus.OK, to_json(response, self.pretty_print)

    @gzip
    @pre_process
    def get_jobs(self, request: Union[APIRequest, Any],
                 job_id=None) -> Tuple[dict, int, str]:
        """
        Get process jobs

        :param request: A request object
        :param job_id: id of job

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers(SYSTEM_LOCALE,
                                               **self.api_headers)
        if job_id is None:
            jobs = sorted(self.manager.get_jobs(),
                          key=lambda k: k['job_start_datetime'],
                          reverse=True)
        else:
            try:
                jobs = [self.manager.get_job(job_id)]
            except JobNotFoundError:
                return self.get_exception(
                    HTTPStatus.NOT_FOUND, headers, request.format,
                    'InvalidParameterValue', job_id)

        serialized_jobs = {
            'jobs': [],
            'links': [{
                'href': f"{self.base_url}/jobs?f={F_HTML}",
                'rel': request.get_linkrel(F_HTML),
                'type': FORMAT_TYPES[F_HTML],
                'title': 'Jobs list as HTML'
            }, {
                'href': f"{self.base_url}/jobs?f={F_JSON}",
                'rel': request.get_linkrel(F_JSON),
                'type': FORMAT_TYPES[F_JSON],
                'title': 'Jobs list as JSON'
            }]
        }
        for job_ in jobs:
            job2 = {
                'processID': job_['process_id'],
                'jobID': job_['identifier'],
                'status': job_['status'],
                'message': job_['message'],
                'progress': job_['progress'],
                'parameters': job_.get('parameters'),
                'job_start_datetime': job_['job_start_datetime'],
                'job_end_datetime': job_['job_end_datetime']
            }

            # TODO: translate
            if JobStatus[job_['status']] in (
               JobStatus.successful, JobStatus.running, JobStatus.accepted):

                job_result_url = f"{self.base_url}/jobs/{job_['identifier']}/results"  # noqa

                job2['links'] = [{
                    'href': f'{job_result_url}?f={F_HTML}',
                    'rel': 'about',
                    'type': FORMAT_TYPES[F_HTML],
                    'title': f'results of job {job_id} as HTML'
                }, {
                    'href': f'{job_result_url}?f={F_JSON}',
                    'rel': 'about',
                    'type': FORMAT_TYPES[F_JSON],
                    'title': f'results of job {job_id} as JSON'
                }]

                if job_['mimetype'] not in (FORMAT_TYPES[F_JSON],
                                            FORMAT_TYPES[F_HTML]):
                    job2['links'].append({
                        'href': job_result_url,
                        'rel': 'about',
                        'type': job_['mimetype'],
                        'title': f"results of job {job_id} as {job_['mimetype']}"  # noqa
                    })

            serialized_jobs['jobs'].append(job2)

        if job_id is None:
            j2_template = 'jobs/index.html'
        else:
            serialized_jobs = serialized_jobs['jobs'][0]
            j2_template = 'jobs/job.html'

        if request.format == F_HTML:
            data = {
                'jobs': serialized_jobs,
                'now': datetime.now(timezone.utc).strftime(DATETIME_FORMAT)
            }
            response = render_j2_template(self.tpl_config, j2_template, data,
                                          request.locale)
            return headers, HTTPStatus.OK, response

        return headers, HTTPStatus.OK, to_json(serialized_jobs,
                                               self.pretty_print)

    @gzip
    @pre_process
    def execute_process(self, request: Union[APIRequest, Any],
                        process_id) -> Tuple[dict, int, str]:
        """
        Execute process

        :param request: A request object
        :param process_id: id of process

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        # Responses are always in US English only
        headers = request.get_response_headers(SYSTEM_LOCALE,
                                               **self.api_headers)
        if process_id not in self.manager.processes:
            msg = 'identifier not found'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers,
                request.format, 'NoSuchProcess', msg)

        data = request.data
        if not data:
            # TODO not all processes require input, e.g. time-dependent or
            #      random value generators
            msg = 'missing request data'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'MissingParameterValue', msg)

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
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        data_dict = data.get('inputs', {})
        LOGGER.debug(data_dict)

        try:
            execution_mode = RequestedProcessExecutionMode(
                request.headers.get('Prefer', request.headers.get('prefer'))
            )
        except ValueError:
            execution_mode = None
        try:
            LOGGER.debug('Executing process')
            result = self.manager.execute_process(
                process_id, data_dict, execution_mode=execution_mode)
            job_id, mime_type, outputs, status, additional_headers = result
            headers.update(additional_headers or {})
            headers['Location'] = f'{self.base_url}/jobs/{job_id}'
        except ProcessorExecuteError as err:
            LOGGER.error(err)
            msg = 'Processing error'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers,
                request.format, 'NoApplicableCode', msg)

        response = {}
        if status == JobStatus.failed:
            response = outputs

        if data.get('response', 'raw') == 'raw':
            headers['Content-Type'] = mime_type
            response = outputs
        elif status not in (JobStatus.failed, JobStatus.accepted):
            response['outputs'] = [outputs]

        if status == JobStatus.accepted:
            http_status = HTTPStatus.CREATED
        else:
            http_status = HTTPStatus.OK

        if mime_type == 'application/json':
            response2 = to_json(response, self.pretty_print)
        else:
            response2 = response

        return headers, http_status, response2

    @gzip
    @pre_process
    def get_job_result(self, request: Union[APIRequest, Any],
                       job_id) -> Tuple[dict, int, str]:
        """
        Get result of job (instance of a process)

        :param request: A request object
        :param job_id: ID of job

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers(SYSTEM_LOCALE,
                                               **self.api_headers)
        try:
            job = self.manager.get_job(job_id)
        except JobNotFoundError:
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers,
                request.format, 'NoSuchJob', job_id
            )

        status = JobStatus[job['status']]

        if status == JobStatus.running:
            msg = 'job still running'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers,
                request.format, 'ResultNotReady', msg)

        elif status == JobStatus.accepted:
            # NOTE: this case is not mentioned in the specification
            msg = 'job accepted but not yet running'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers,
                request.format, 'ResultNotReady', msg)

        elif status == JobStatus.failed:
            msg = 'job failed'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        try:
            mimetype, job_output = self.manager.get_job_result(job_id)
        except JobResultNotFoundError:
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers,
                request.format, 'JobResultNotFound', job_id
            )

        if mimetype not in (None, FORMAT_TYPES[F_JSON]):
            headers['Content-Type'] = mimetype
            content = job_output
        else:
            if request.format == F_JSON:
                content = json.dumps(job_output, sort_keys=True, indent=4,
                                     default=json_serial)
            else:
                # HTML
                data = {
                    'job': {'id': job_id},
                    'result': job_output
                }
                content = render_j2_template(
                    self.config, 'jobs/results/index.html',
                    data, request.locale)

        return headers, HTTPStatus.OK, content

    @pre_process
    def delete_job(
            self, request: Union[APIRequest, Any], job_id
    ) -> Tuple[dict, int, str]:
        """
        Delete a process job

        :param job_id: job identifier

        :returns: tuple of headers, status code, content
        """
        response_headers = request.get_response_headers(
            SYSTEM_LOCALE, **self.api_headers)
        try:
            success = self.manager.delete_job(job_id)
        except JobNotFoundError:
            return self.get_exception(
                HTTPStatus.NOT_FOUND, response_headers, request.format,
                'NoSuchJob', job_id
            )
        else:
            if success:
                http_status = HTTPStatus.OK
                jobs_url = f"{self.base_url}/jobs"

                response = {
                    'jobID': job_id,
                    'status': JobStatus.dismissed.value,
                    'message': 'Job dismissed',
                    'progress': 100,
                    'links': [{
                        'href': jobs_url,
                        'rel': 'up',
                        'type': FORMAT_TYPES[F_JSON],
                        'title': 'The job list for the current process'
                    }]
                }
            else:
                return self.get_exception(
                    HTTPStatus.INTERNAL_SERVER_ERROR, response_headers,
                    request.format, 'InternalError', job_id
                )
        LOGGER.info(response)
        # TODO: this response does not have any headers
        return {}, http_status, response

    @gzip
    @pre_process
    def get_collection_edr_query(
            self, request: Union[APIRequest, Any],
            dataset, instance, query_type) -> Tuple[dict, int, str]:
        """
        Queries collection EDR

        :param request: APIRequest instance with query params
        :param dataset: dataset name
        :param instance: instance name
        :param query_type: EDR query type

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid(PLUGINS['formatter'].keys()):
            return self.get_format_exception(request)
        headers = request.get_response_headers(self.default_locale,
                                               **self.api_headers)
        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            msg = 'Collection not found'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Processing datetime parameter')
        datetime_ = request.params.get('datetime')
        try:
            datetime_ = validate_datetime(collections[dataset]['extents'],
                                          datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        LOGGER.debug('Processing parameter-name parameter')
        parameternames = request.params.get('parameter-name') or []
        if isinstance(parameternames, str):
            parameternames = parameternames.split(',')

        bbox = None
        if query_type == 'cube':
            LOGGER.debug('Processing cube bbox')
            try:
                bbox = validate_bbox(request.params.get('bbox'))
                if not bbox:
                    raise ValueError('bbox parameter required by cube queries')
            except ValueError as err:
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', str(err))

        LOGGER.debug('Processing coords parameter')
        wkt = request.params.get('coords')

        if wkt:
            try:
                wkt = shapely_loads(wkt)
            except WKTReadingError:
                msg = 'invalid coords parameter'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)
        elif query_type != 'cube':
            msg = 'missing coords parameter'
            return self.get_exception(
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
        except ProviderTypeError:
            msg = 'invalid provider type'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers,
                request.format, 'NoApplicableCode', msg)
        except ProviderConnectionError:
            msg = 'connection error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers,
                request.format, 'NoApplicableCode', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers,
                request.format, 'NoApplicableCode', msg)

        if instance is not None and not p.get_instance(instance):
            msg = 'Invalid instance identifier'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers,
                request.format, 'InvalidParameterValue', msg)

        if query_type not in p.get_query_types():
            msg = 'Unsupported query type'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)

        if parameternames and not any((fld['id'] in parameternames)
                                      for fld in p.get_fields()['field']):
            msg = 'Invalid parameter-name'
            return self.get_exception(
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
            limit=int(self.config['server']['limit'])
        )

        try:
            data = p.query(**query_args)
        except ProviderNoDataError:
            msg = 'No data found'
            return self.get_exception(
                HTTPStatus.NO_CONTENT, headers, request.format, 'NoMatch', msg)
        except ProviderQueryError:
            msg = 'query error (check logs)'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format,
                'NoApplicableCode', msg)
        except ProviderRequestEntityTooLargeError as err:
            return self.get_exception(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE, headers, request.format,
                'NoApplicableCode', str(err))

        if request.format == F_HTML:  # render
            content = render_j2_template(self.tpl_config,
                                         'collections/edr/query.html', data,
                                         self.default_locale)
        else:
            content = to_json(data, self.pretty_print)

        return headers, HTTPStatus.OK, content

    @gzip
    @pre_process
    @jsonldify
    def get_stac_root(
            self, request: Union[APIRequest, Any]) -> Tuple[dict, int, str]:
        """
        Provide STAC root page

        :param request: APIRequest instance with query params

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers(**self.api_headers)

        id_ = 'pygeoapi-stac'
        stac_version = '1.0.0-rc.2'
        stac_url = f'{self.base_url}/stac'

        content = {
            'id': id_,
            'type': 'Catalog',
            'stac_version': stac_version,
            'title': l10n.translate(
                self.config['metadata']['identification']['title'],
                request.locale),
            'description': l10n.translate(
                self.config['metadata']['identification']['description'],
                request.locale),
            'links': []
        }

        stac_collections = filter_dict_by_key_value(self.config['resources'],
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
            content = render_j2_template(self.tpl_config,
                                         'stac/collection.html',
                                         content, request.locale)
            return headers, HTTPStatus.OK, content

        return headers, HTTPStatus.OK, to_json(content, self.pretty_print)

    @gzip
    @pre_process
    @jsonldify
    def get_stac_path(self, request: Union[APIRequest, Any],
                      path) -> Tuple[dict, int, str]:
        """
        Provide STAC resource path

        :param request: APIRequest instance with query params

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers(**self.api_headers)

        dataset = None
        LOGGER.debug(f'Path: {path}')
        dir_tokens = path.split('/')
        if dir_tokens:
            dataset = dir_tokens[0]

        stac_collections = filter_dict_by_key_value(self.config['resources'],
                                                    'type', 'stac-collection')

        if dataset not in stac_collections:
            msg = 'Collection not found'
            return self.get_exception(HTTPStatus.NOT_FOUND, headers,
                                      request.format, 'NotFound', msg)

        LOGGER.debug('Loading provider')
        try:
            p = load_plugin('provider', get_provider_by_type(
                stac_collections[dataset]['providers'], 'stac'))
        except ProviderConnectionError as err:
            LOGGER.error(err)
            msg = 'connection error (check logs)'
            return self.get_exception(
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
                f'{self.base_url}/stac',
                path,
                path.replace(dataset, '', 1)
            )
        except ProviderNotFoundError as err:
            LOGGER.error(err)
            msg = 'resource not found'
            return self.get_exception(HTTPStatus.NOT_FOUND, headers,
                                      request.format, 'NotFound', msg)
        except Exception as err:
            LOGGER.error(err)
            msg = 'data query error'
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, headers,
                request.format, 'NoApplicableCode', msg)

        if isinstance(stac_data, dict):
            content.update(stac_data)
            content['links'].extend(stac_collections[dataset]['links'])

            if request.format == F_HTML:  # render
                content['path'] = path
                if 'assets' in content:  # item view
                    content = render_j2_template(self.tpl_config,
                                                 'stac/item.html',
                                                 content, request.locale)
                else:
                    content = render_j2_template(self.tpl_config,
                                                 'stac/catalog.html',
                                                 content, request.locale)

                return headers, HTTPStatus.OK, content

            return headers, HTTPStatus.OK, to_json(content, self.pretty_print)

        else:  # send back file
            headers.pop('Content-Type', None)
            return headers, HTTPStatus.OK, stac_data

    def get_exception(self, status, headers, format_, code,
                      description) -> Tuple[dict, int, str]:
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

        if format_ == F_HTML:
            headers['Content-Type'] = FORMAT_TYPES[F_HTML]
            content = render_j2_template(
                self.config, 'exception.html', exception, SYSTEM_LOCALE)
        else:
            content = to_json(exception, self.pretty_print)

        return headers, status, content

    def get_format_exception(self, request) -> Tuple[dict, int, str]:
        """
        Returns a format exception.

        :param request: An APIRequest instance.

        :returns: tuple of (headers, status, message)
        """

        # Content-Language is in the system locale (ignore language settings)
        headers = request.get_response_headers(SYSTEM_LOCALE,
                                               **self.api_headers)
        msg = f'Invalid format: {request.format}'
        return self.get_exception(
            HTTPStatus.BAD_REQUEST, headers,
            request.format, 'InvalidParameterValue', msg)

    def get_collections_url(self):
        return f"{self.base_url}/collections"

    @staticmethod
    def _create_crs_transform_spec(
        config: dict,
        query_crs_uri: Optional[str] = None,
    ) -> Union[None, CrsTransformSpec]:
        """Create a `CrsTransformSpec` instance based on provider config and
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

    @staticmethod
    def _set_content_crs_header(
        headers: dict,
        config: dict,
        query_crs_uri: Optional[str] = None,
    ):
        """Set the *Content-Crs* header in responses from providers of Feature
        type.

        :param headers: Response headers dictionary.
        :type headers: dict
        :param config: Provider config dictionary.
        :type config: dict
        :param query_crs_uri: Uniform resource identifier of the coordinate
            reference system specified in query parameter (if specified).
        :type query_crs_uri: str, optional
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


def validate_bbox(value=None) -> list:
    """
    Helper function to validate bbox parameter

    :param value: `list` of minx, miny, maxx, maxy

    :returns: bbox as `list` of `float` values
    """

    if value is None:
        LOGGER.debug('bbox is empty')
        return []

    bbox = value.split(',')

    if len(bbox) not in [4, 6]:
        msg = 'bbox should be either 4 values (minx,miny,maxx,maxy) ' \
              'or 6 values (minx,miny,minz,maxx,maxy,maxz)'
        LOGGER.debug(msg)
        raise ValueError(msg)

    try:
        bbox = [float(c) for c in bbox]
    except ValueError as err:
        msg = 'bbox values must be numbers'
        err.args = (msg,)
        LOGGER.debug(msg)
        raise

    if (len(bbox) == 4 and bbox[1] > bbox[3]) \
            or (len(bbox) == 6 and bbox[1] > bbox[4]):
        msg = 'miny should be less than maxy'
        LOGGER.debug(msg)
        raise ValueError(msg)

    if (len(bbox) == 4 and bbox[0] > bbox[2]) \
            or (len(bbox) == 6 and bbox[0] > bbox[3]):
        msg = 'minx is greater than maxx (possibly antimeridian bbox)'
        LOGGER.debug(msg)

    if len(bbox) == 6 and bbox[2] > bbox[5]:
        msg = 'minz should be less than maxz'
        LOGGER.debug(msg)
        raise ValueError(msg)

    return bbox


def validate_datetime(resource_def, datetime_=None) -> str:
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

    if datetime_ is not None and 'temporal' in resource_def:

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
                (te['end'] is not None and datetime_begin != '..' and
                    datetime_begin > te['end']),
                (te['begin'] is not None and datetime_end != '..' and
                    datetime_end < te['begin'])
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


def validate_subset(value: str) -> dict:
    """
    Helper function to validate subset parameter

    :param value: `subset` parameter

    :returns: dict of axis/values
    """

    subsets = {}

    for s in value.split(','):
        LOGGER.debug(f'Processing subset {s}')
        m = re.search(r'(.*)\((.*)\)', s)
        subset_name, values = m.group(1, 2)

        if '"' in values:
            LOGGER.debug('Values are strings')
            if values.count('"') % 2 != 0:
                msg = 'Invalid format: subset should be like axis("min"[:"max"])'  # noqa
                LOGGER.error(msg)
                raise ValueError(msg)
            try:
                LOGGER.debug('Value is an interval')
                m = re.search(r'"(\S+)":"(\S+)"', values)
                values = list(m.group(1, 2))
            except AttributeError:
                LOGGER.debug('Value is point')
                m = re.search(r'"(.*)"', values)
                values = [m.group(1)]
        else:
            LOGGER.debug('Values are numbers')
            try:
                LOGGER.debug('Value is an interval')
                m = re.search(r'(\S+):(\S+)', values)
                values = list(m.group(1, 2))
            except AttributeError:
                LOGGER.debug('Value is point')
                values = [values]

        subsets[subset_name] = list(map(get_typed_value, values))

    return subsets
