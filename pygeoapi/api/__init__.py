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

"""
Root level code of pygeoapi, parsing content provided by web framework.
Returns content from plugins and sets responses.
"""

import asyncio
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from functools import partial
from gzip import compress
from http import HTTPStatus
import logging
import re
import sys
from typing import Any, Tuple, Union, Optional

from dateutil.parser import parse as dateparse
import pytz

from pygeoapi import __version__, l10n
from pygeoapi.linked_data import jsonldify, jsonldify_collection
from pygeoapi.log import setup_logger
from pygeoapi.plugin import load_plugin
from pygeoapi.process.manager.base import get_manager
from pygeoapi.provider.base import (
    ProviderConnectionError, ProviderGenericError, ProviderTypeError)

from pygeoapi.util import (
    CrsTransformSpec, TEMPLATES, UrlPrefetcher, dategetter,
    filter_dict_by_key_value, get_api_rules, get_base_url,
    get_provider_by_type, get_provider_default, get_typed_value,
    get_crs_from_uri, get_supported_crs_list, render_j2_template, to_json
)

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
F_JPEG = 'jpeg'
F_MVT = 'mvt'
F_NETCDF = 'NetCDF'

#: Formats allowed for ?f= requests (order matters for complex MIME types)
FORMAT_TYPES = OrderedDict((
    (F_HTML, 'text/html'),
    (F_JSONLD, 'application/ld+json'),
    (F_JSON, 'application/json'),
    (F_PNG, 'image/png'),
    (F_JPEG, 'image/jpeg'),
    (F_MVT, 'application/vnd.mapbox-vector-tile'),
    (F_NETCDF, 'application/x-netcdf'),
))

#: Locale used for system responses (e.g. exceptions)
SYSTEM_LOCALE = l10n.Locale('en', 'US')

CONFORMANCE_CLASSES = [
    'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections',
    'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page',
    'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json',
    'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/oas30'
]

OGC_RELTYPES_BASE = 'http://www.opengis.net/def/rel/ogc/1.0'

DEFAULT_CRS_LIST = [
    'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
    'http://www.opengis.net/def/crs/OGC/1.3/CRS84h',
]

DEFAULT_CRS = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
DEFAULT_STORAGE_CRS = DEFAULT_CRS


def all_apis() -> dict:
    """
    Return all supported API modules

    NOTE: this is a function and not a constant to avoid import loops

    :returns: `dict` of API provider type, API module
    """

    from . import (coverages, environmental_data_retrieval, itemtypes, maps,
                   processes, tiles, stac)

    return {
        'coverage': coverages,
        'edr': environmental_data_retrieval,
        'itemtypes': itemtypes,
        'map': maps,
        'process': processes,
        'tile': tiles,
        'stac': stac
    }


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


# TODO: remove this when all functions have been refactored
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


def apply_gzip(headers: dict, content: Union[str, bytes]) -> Union[str, bytes]:
    """
    Compress content if requested in header.
    """
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
    return content


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

    # TODO: remove this after all views have been refactored (only used
    #       in pre_process)
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
                # Set data from Starlette request after async
                # coroutine completion
                # TODO:
                # this now blocks, but once Flask v2 with async support
                # has been implemented, with_data() can become async too
                loop = asyncio.get_event_loop()
                api_req._data = asyncio.run_coroutine_threadsafe(
                    request.body(), loop).result(1)
        return api_req

    @classmethod
    def from_flask(cls, request, supported_locales) -> 'APIRequest':
        """Factory class similar to with_data, but only for flask requests"""
        api_req = cls(request, supported_locales)
        api_req._data = request.data
        return api_req

    @classmethod
    async def from_starlette(cls, request, supported_locales) -> 'APIRequest':
        """Factory class similar to with_data, but only for starlette requests
        """
        api_req = cls(request, supported_locales)
        api_req._data = await request.body()
        return api_req

    @classmethod
    def from_django(cls, request, supported_locales) -> 'APIRequest':
        """Factory class similar to with_data, but only for django requests"""
        api_req = cls(request, supported_locales)
        api_req._data = request.body
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

    def __init__(self, config, openapi):
        """
        constructor

        :param config: configuration dict
        :param openapi: openapi dict

        :returns: `pygeoapi.API` instance
        """

        self.config = config
        self.openapi = openapi
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
            'title': l10n.translate('This document as JSON', request.locale),
            'href': f"{self.base_url}?f={F_JSON}"
        }, {
            'rel': request.get_linkrel(F_JSONLD),
            'type': FORMAT_TYPES[F_JSONLD],
            'title': l10n.translate('This document as RDF (JSON-LD)', request.locale),  # noqa
            'href': f"{self.base_url}?f={F_JSONLD}"
        }, {
            'rel': request.get_linkrel(F_HTML),
            'type': FORMAT_TYPES[F_HTML],
            'title': l10n.translate('This document as HTML', request.locale),
            'href': f"{self.base_url}?f={F_HTML}",
            'hreflang': self.default_locale
        }, {
            'rel': 'service-desc',
            'type': 'application/vnd.oai.openapi+json;version=3.0',
            'title': l10n.translate('The OpenAPI definition as JSON', request.locale),  # noqa
            'href': f"{self.base_url}/openapi"
        }, {
            'rel': 'service-doc',
            'type': FORMAT_TYPES[F_HTML],
            'title': l10n.translate('The OpenAPI definition as HTML', request.locale),  # noqa
            'href': f"{self.base_url}/openapi?f={F_HTML}",
            'hreflang': self.default_locale
        }, {
            'rel': 'conformance',
            'type': FORMAT_TYPES[F_JSON],
            'title': l10n.translate('Conformance', request.locale),
            'href': f"{self.base_url}/conformance"
        }, {
            'rel': 'data',
            'type': FORMAT_TYPES[F_JSON],
            'title': l10n.translate('Collections', request.locale),
            'href': self.get_collections_url()
        }, {
            'rel': 'http://www.opengis.net/def/rel/ogc/1.0/processes',
            'type': FORMAT_TYPES[F_JSON],
            'title': l10n.translate('Processes', request.locale),
            'href': f"{self.base_url}/processes"
        }, {
            'rel': 'http://www.opengis.net/def/rel/ogc/1.0/job-list',
            'type': FORMAT_TYPES[F_JSON],
            'title': l10n.translate('Jobs', request.locale),
            'href': f"{self.base_url}/jobs"
        }, {
            'rel': 'http://www.opengis.net/def/rel/ogc/1.0/tiling-schemes',
            'type': FORMAT_TYPES[F_JSON],
            'title': l10n.translate('The list of supported tiling schemes as JSON', request.locale),  # noqa
            'href': f"{self.base_url}/TileMatrixSets?f=json"
        }, {
            'rel': 'http://www.opengis.net/def/rel/ogc/1.0/tiling-schemes',
            'type': FORMAT_TYPES[F_HTML],
            'title': l10n.translate('The list of supported tiling schemes as HTML', request.locale),  # noqa
            'href': f"{self.base_url}/TileMatrixSets?f=html"
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
    def openapi_(self, request: Union[APIRequest, Any]) -> Tuple[
                 dict, int, str]:
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

        if isinstance(self.openapi, dict):
            return headers, HTTPStatus.OK, to_json(self.openapi,
                                                   self.pretty_print)
        else:
            return headers, HTTPStatus.OK, self.openapi

    @gzip
    @pre_process
    def conformance(self,
                    request: Union[APIRequest, Any]) -> Tuple[dict, int, str]:
        """
        Provide conformance definition

        :param request: A request object

        :returns: tuple of headers, status code, content
        """

        apis_dict = all_apis()

        if not request.is_valid():
            return self.get_format_exception(request)

        conformance_list = CONFORMANCE_CLASSES

        for key, value in self.config['resources'].items():
            if value['type'] == 'process':
                conformance_list.extend(
                    apis_dict['process'].CONFORMANCE_CLASSES)
            else:
                for provider in value['providers']:
                    if provider['type'] in apis_dict:
                        conformance_list.extend(
                            apis_dict[provider['type']].CONFORMANCE_CLASSES)
                    if provider['type'] == 'feature':
                        conformance_list.extend(
                            apis_dict['itemtypes'].CONFORMANCE_CLASSES_FEATURES)  # noqa
                    if provider['type'] == 'record':
                        conformance_list.extend(
                            apis_dict['itemtypes'].CONFORMANCE_CLASSES_RECORDS)

        conformance = {
            'conformsTo': sorted(list(set(conformance_list)))
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

            collection_data_format = None

            if 'format' in collection_data:
                collection_data_format = collection_data['format']

            is_vector_tile = (collection_data_type == 'tile' and
                              collection_data_format['name'] not
                              in [F_PNG, F_JPEG])

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
                'title': l10n.translate('The landing page of this server as JSON', request.locale),  # noqa
                'href': f"{self.base_url}?f={F_JSON}"
            })
            collection['links'].append({
                'type': FORMAT_TYPES[F_HTML],
                'rel': 'root',
                'title': l10n.translate('The landing page of this server as HTML', request.locale),  # noqa
                'href': f"{self.base_url}?f={F_HTML}"
            })
            collection['links'].append({
                'type': FORMAT_TYPES[F_JSON],
                'rel': request.get_linkrel(F_JSON),
                'title': l10n.translate('This document as JSON', request.locale),  # noqa
                'href': f'{self.get_collections_url()}/{k}?f={F_JSON}'
            })
            collection['links'].append({
                'type': FORMAT_TYPES[F_JSONLD],
                'rel': request.get_linkrel(F_JSONLD),
                'title': l10n.translate('This document as RDF (JSON-LD)', request.locale),  # noqa
                'href': f'{self.get_collections_url()}/{k}?f={F_JSONLD}'
            })
            collection['links'].append({
                'type': FORMAT_TYPES[F_HTML],
                'rel': request.get_linkrel(F_HTML),
                'title': l10n.translate('This document as HTML', request.locale),  # noqa
                'href': f'{self.get_collections_url()}/{k}?f={F_HTML}'
            })

            if collection_data_type in ['feature', 'coverage', 'record']:
                collection['links'].append({
                    'type': FORMAT_TYPES[F_JSON],
                    'rel': f'{OGC_RELTYPES_BASE}/schema',
                    'title': l10n.translate('Schema of collection in JSON', request.locale),  # noqa
                    'href': f'{self.get_collections_url()}/{k}/schema?f={F_JSON}'  # noqa
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': f'{OGC_RELTYPES_BASE}/schema',
                    'title': l10n.translate('Schema of collection in HTML', request.locale),  # noqa
                    'href': f'{self.get_collections_url()}/{k}/schema?f={F_HTML}'  # noqa
                })

            if is_vector_tile or collection_data_type in ['feature', 'record']:
                # TODO: translate
                collection['itemType'] = collection_data_type
                LOGGER.debug('Adding feature/record based links')
                collection['links'].append({
                    'type': 'application/schema+json',
                    'rel': 'http://www.opengis.net/def/rel/ogc/1.0/queryables',
                    'title': l10n.translate('Queryables for this collection as JSON', request.locale),  # noqa
                    'href': f'{self.get_collections_url()}/{k}/queryables?f={F_JSON}'  # noqa
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': 'http://www.opengis.net/def/rel/ogc/1.0/queryables',
                    'title': l10n.translate('Queryables for this collection as HTML', request.locale),  # noqa
                    'href': f'{self.get_collections_url()}/{k}/queryables?f={F_HTML}'  # noqa
                })
                collection['links'].append({
                    'type': 'application/geo+json',
                    'rel': 'items',
                    'title': l10n.translate('Items as GeoJSON', request.locale),  # noqa
                    'href': f'{self.get_collections_url()}/{k}/items?f={F_JSON}'  # noqa
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_JSONLD],
                    'rel': 'items',
                    'title': l10n.translate('Items as RDF (GeoJSON-LD)', request.locale),  # noqa
                    'href': f'{self.get_collections_url()}/{k}/items?f={F_JSONLD}'  # noqa
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': 'items',
                    'title': l10n.translate('Items as HTML', request.locale),  # noqa
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
                    'type': 'application/prs.coverage+json',
                    'rel': f'{OGC_RELTYPES_BASE}/coverage',
                    'title': l10n.translate('Coverage data', request.locale),
                    'href': f'{self.get_collections_url()}/{k}/coverage?f={F_JSON}'  # noqa
                })
                if collection_data_format is not None:
                    title_ = l10n.translate('Coverage data as', request.locale)  # noqa
                    title_ = f"{title_} {collection_data_format['name']}"
                    collection['links'].append({
                        'type': collection_data_format['mimetype'],
                        'rel': f'{OGC_RELTYPES_BASE}/coverage',
                        'title': title_,
                        'href': f"{self.get_collections_url()}/{k}/coverage?f={collection_data_format['name']}"  # noqa
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
                        collection['extent']['spatial']['grid'] = [{
                            'cellsCount': p._coverage_properties['width'],
                            'resolution': p._coverage_properties['resx']
                            }, {
                            'cellsCount': p._coverage_properties['height'],
                            'resolution': p._coverage_properties['resy']
                        }]

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
                    'title': l10n.translate('Tiles as JSON', request.locale),
                    'href': f'{self.get_collections_url()}/{k}/tiles?f={F_JSON}'  # noqa
                })
                collection['links'].append({
                    'type': FORMAT_TYPES[F_HTML],
                    'rel': f'http://www.opengis.net/def/rel/ogc/1.0/tilesets-{p.tile_type}',  # noqa
                    'title': l10n.translate('Tiles as HTML', request.locale),
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

                title_ = l10n.translate('Map as', request.locale)
                title_ = f"{title_} {map_format}"

                collection['links'].append({
                    'type': map_mimetype,
                    'rel': 'http://www.opengis.net/def/rel/ogc/1.0/map',
                    'title': title_,
                    'href': f"{self.get_collections_url()}/{k}/map?f={map_format}"  # noqa
                })

            try:
                edr = get_provider_by_type(v['providers'], 'edr')
                p = load_plugin('provider', edr)
            except ProviderConnectionError:
                msg = 'connection error (check logs)'
                return self.get_exception(
                    HTTPStatus.INTERNAL_SERVER_ERROR, headers,
                    request.format, 'NoApplicableCode', msg)
            except ProviderTypeError:
                edr = None

            if edr:
                # TODO: translate
                LOGGER.debug('Adding EDR links')
                parameters = p.get_fields()
                if parameters:
                    collection['parameter_names'] = {}
                    for key, value in parameters.items():
                        collection['parameter_names'][key] = {
                            'id': key,
                            'type': 'Parameter',
                            'name': value['title'],
                            'unit': {
                                'label': {
                                    'en': value['title']
                                },
                                'symbol': {
                                    'value': value['x-ogc-unit'],
                                    'type': 'http://www.opengis.net/def/uom/UCUM/'  # noqa
                                }
                            }
                        }

                for qt in p.get_query_types():
                    title1 = l10n.translate('query for this collection as JSON', request.locale)  # noqa
                    title1 = f'{qt} {title1}'
                    title2 = l10n.translate('query for this collection as HTML', request.locale)  # noqa
                    title2 = f'{qt} {title2}'

                    collection['links'].append({
                        'type': 'application/json',
                        'rel': 'data',
                        'title': title1,
                        'href': f'{self.get_collections_url()}/{k}/{qt}?f={F_JSON}'  # noqa
                    })
                    collection['links'].append({
                        'type': FORMAT_TYPES[F_HTML],
                        'rel': 'data',
                        'title': title2,
                        'href': f'{self.get_collections_url()}/{k}/{qt}?f={F_HTML}'  # noqa
                    })

            if dataset is not None and k == dataset:
                fcm = collection
                break

            fcm['collections'].append(collection)

        if dataset is None:
            # TODO: translate
            fcm['links'].append({
                'type': FORMAT_TYPES[F_JSON],
                'rel': request.get_linkrel(F_JSON),
                'title': l10n.translate('This document as JSON', request.locale),  # noqa
                'href': f'{self.get_collections_url()}?f={F_JSON}'
            })
            fcm['links'].append({
                'type': FORMAT_TYPES[F_JSONLD],
                'rel': request.get_linkrel(F_JSONLD),
                'title': l10n.translate('This document as RDF (JSON-LD)', request.locale),  # noqa
                'href': f'{self.get_collections_url()}?f={F_JSONLD}'
            })
            fcm['links'].append({
                'type': FORMAT_TYPES[F_HTML],
                'rel': request.get_linkrel(F_HTML),
                'title': l10n.translate('This document as HTML', request.locale),  # noqa
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
    def get_collection_schema(self, request: Union[APIRequest, Any],
                              dataset) -> Tuple[dict, int, str]:
        """
        Returns a collection schema

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        headers = request.get_response_headers(**self.api_headers)

        if any([dataset is None,
                dataset not in self.config['resources'].keys()]):

            msg = 'Collection not found'
            return self.get_exception(
                HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

        LOGGER.debug('Creating collection schema')
        try:
            LOGGER.debug('Loading feature provider')
            p = load_plugin('provider', get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'feature'))
        except ProviderTypeError:
            try:
                LOGGER.debug('Loading coverage provider')
                p = load_plugin('provider', get_provider_by_type(
                    self.config['resources'][dataset]['providers'], 'coverage'))  # noqa
            except ProviderTypeError:
                LOGGER.debug('Loading record provider')
                p = load_plugin('provider', get_provider_by_type(
                    self.config['resources'][dataset]['providers'], 'record'))
        except ProviderGenericError as err:
            LOGGER.error(err)
            return self.get_exception(
                err.http_status_code, headers, request.format,
                err.ogc_exception_code, err.message)

        schema = {
            'type': 'object',
            'title': l10n.translate(
                self.config['resources'][dataset]['title'], request.locale),
            'properties': {},
            '$schema': 'http://json-schema.org/draft/2019-09/schema',
            '$id': f'{self.get_collections_url()}/{dataset}/schema'
        }

        if p.type != 'coverage':
            schema['properties']['geometry'] = {
                '$ref': 'https://geojson.org/schema/Geometry.json',
                'x-ogc-role': 'primary-geometry'
            }

        for k, v in p.fields.items():
            schema['properties'][k] = v
            if v.get('format') is None:
                schema['properties'][k].pop('format', None)

            if k == p.id_field:
                schema['properties'][k]['x-ogc-role'] = 'id'
            if k == p.time_field:
                schema['properties'][k]['x-ogc-role'] = 'primary-instant'

        if request.format == F_HTML:  # render
            schema['title'] = l10n.translate(
                self.config['resources'][dataset]['title'], request.locale)

            schema['collections_path'] = self.get_collections_url()

            content = render_j2_template(self.tpl_config,
                                         'collections/schema.html',
                                         schema, request.locale)

            return headers, HTTPStatus.OK, content

        headers['Content-Type'] = 'application/schema+json'

        return headers, HTTPStatus.OK, to_json(schema, self.pretty_print)

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

        exception_info = sys.exc_info()
        LOGGER.error(
            description,
            exc_info=exception_info if exception_info[0] is not None else None
        )
        exception = {
            'code': code,
            'type': code,
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
