# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
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
""" Root level code of pygeoapi, parsing content provided by webframework.
Returns content from plugins and sets reponses
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

from dateutil.parser import parse as dateparse
import pytz

from pygeoapi import __version__
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
FORMATS = ['json', 'html', 'jsonld']

CONFORMANCE = [
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson',
    'http://www.opengis.net/spec/ogcapi_coverages-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/oas30',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/req/core',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/req/collections'
]

OGC_RELTYPES_BASE = 'http://www.opengis.net/def/rel/ogc/1.0'


def pre_process(func):
    """
        Decorator performing header copy and format
        checking before sending arguments to methods

        :param func: decorated function

        :returns: `func`
    """

    def inner(*args, **kwargs):
        cls = args[0]
        headers_ = HEADERS.copy()
        format_ = check_format(args[2], args[1])
        if len(args) > 3:
            args = args[3:]
            return func(cls, headers_, format_, *args, **kwargs)
        else:
            return func(cls, headers_, format_)

    return inner


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
    def landing_page(self, headers_, format_):
        """
        Provide API

        :param headers_: copy of HEADERS object
        :param format_: format of requests, pre checked by
                        pre_process decorator

        :returns: tuple of headers, status code, content
        """

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        fcm = {
            'links': [],
            'title': self.config['metadata']['identification']['title'],
            'description':
                self.config['metadata']['identification']['description']
        }

        LOGGER.debug('Creating links')
        fcm['links'] = [{
              'rel': 'self' if not format_ or
              format_ == 'json' else 'alternate',
              'type': 'application/json',
              'title': 'This document as JSON',
              'href': '{}?f=json'.format(self.config['server']['url'])
            }, {
              'rel': 'self' if format_ == 'jsonld' else 'alternate',
              'type': 'application/ld+json',
              'title': 'This document as RDF (JSON-LD)',
              'href': '{}?f=jsonld'.format(self.config['server']['url'])
            }, {
              'rel': 'self' if format_ == 'html' else 'alternate',
              'type': 'text/html',
              'title': 'This document as HTML',
              'href': '{}?f=html'.format(self.config['server']['url']),
              'hreflang': self.config['server']['language']
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
              'hreflang': self.config['server']['language']
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
            }
        ]

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'

            fcm['processes'] = False
            fcm['stac'] = False

            if filter_dict_by_key_value(self.config['resources'],
                                        'type', 'process'):
                fcm['processes'] = True

            if filter_dict_by_key_value(self.config['resources'],
                                        'type', 'stac-collection'):
                fcm['stac'] = True

            content = render_j2_template(self.config, 'landing_page.html', fcm)
            return headers_, 200, content

        if format_ == 'jsonld':
            headers_['Content-Type'] = 'application/ld+json'
            return headers_, 200, to_json(self.fcmld, self.pretty_print)

        return headers_, 200, to_json(fcm, self.pretty_print)

    @pre_process
    def openapi(self, headers_, format_, openapi):
        """
        Provide OpenAPI document


        :param headers_: copy of HEADERS object
        :param format_: format of requests, pre checked by
                        pre_process decorator
        :param openapi: dict of OpenAPI definition

        :returns: tuple of headers, status code, content
        """

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        path = '/'.join([self.config['server']['url'].rstrip('/'), 'openapi'])

        if format_ == 'html':
            data = {
                'openapi-document-path': path
            }
            headers_['Content-Type'] = 'text/html'
            content = render_j2_template(self.config, 'openapi.html', data)
            return headers_, 200, content

        headers_['Content-Type'] = \
            'application/vnd.oai.openapi+json;version=3.0'

        return headers_, 200, to_json(openapi, self.pretty_print)

    @pre_process
    def conformance(self, headers_, format_):
        """
        Provide conformance definition

        :param headers_: copy of HEADERS object
        :param format_: format of requests,
                        pre checked by pre_process decorator

        :returns: tuple of headers, status code, content
        """

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        conformance = {
            'conformsTo': CONFORMANCE
        }

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
            content = render_j2_template(self.config, 'conformance.html',
                                         conformance)
            return headers_, 200, content

        return headers_, 200, to_json(conformance, self.pretty_print)

    @pre_process
    @jsonldify
    def describe_collections(self, headers_, format_, dataset=None):
        """
        Provide collection metadata

        :param headers_: copy of HEADERS object
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param dataset: name of collection

        :returns: tuple of headers, status code, content
        """

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        fcm = {
            'collections': [],
            'links': []
        }

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if all([dataset is not None, dataset not in collections.keys()]):
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        LOGGER.debug('Creating collections')
        for k, v in collections.items():
            collection_data = get_provider_default(v['providers'])
            collection_data_type = collection_data['type']

            collection_data_format = None

            if 'format' in collection_data:
                collection_data_format = collection_data['format']

            collection = {'links': []}
            collection['id'] = k
            collection['title'] = v['title']
            collection['description'] = v['description']
            collection['keywords'] = v['keywords']

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

            for link in v['links']:
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
                'rel': 'self' if not format_
                or format_ == 'json' else 'alternate',
                'title': 'This document as JSON',
                'href': '{}/collections/{}?f=json'.format(
                    self.config['server']['url'], k)
            })
            collection['links'].append({
                'type': 'application/ld+json',
                'rel': 'self' if format_ == 'jsonld' else 'alternate',
                'title': 'This document as RDF (JSON-LD)',
                'href': '{}/collections/{}?f=jsonld'.format(
                    self.config['server']['url'], k)
            })
            collection['links'].append({
                'type': 'text/html',
                'rel': 'self' if format_ == 'html' else 'alternate',
                'title': 'This document as HTML',
                'href': '{}/collections/{}?f=html'.format(
                    self.config['server']['url'], k)
            })

            if collection_data_type == 'feature':
                collection['itemType'] = collection_data_type.capitalize()
                LOGGER.debug('Adding feature based links')
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
                            self.config['resources'][dataset]['providers'],
                            'coverage'))
                    except ProviderConnectionError:
                        exception = {
                           'code': 'NoApplicableCode',
                           'description': 'connection error (check logs)'
                        }
                        LOGGER.error(exception)
                        return headers_, 500, to_json(exception,
                                                      self.pretty_print)

                    collection['crs'] = [p.crs]
                    collection['domainset'] = p.get_coverage_domainset()
                    collection['rangetype'] = p.get_coverage_rangetype()

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

            if dataset is not None and k == dataset:
                fcm = collection
                break

            fcm['collections'].append(collection)

        if dataset is None:
            fcm['links'].append({
                'type': 'application/json',
                'rel': 'self' if not format
                or format_ == 'json' else 'alternate',
                'title': 'This document as JSON',
                'href': '{}/collections?f=json'.format(
                    self.config['server']['url'])
            })
            fcm['links'].append({
                'type': 'application/ld+json',
                'rel': 'self' if format_ == 'jsonld' else 'alternate',
                'title': 'This document as RDF (JSON-LD)',
                'href': '{}/collections?f=jsonld'.format(
                    self.config['server']['url'])
            })
            fcm['links'].append({
                'type': 'text/html',
                'rel': 'self' if format_ == 'html' else 'alternate',
                'title': 'This document as HTML',
                'href': '{}/collections?f=html'.format(
                    self.config['server']['url'])
            })

        if format_ == 'html':  # render

            headers_['Content-Type'] = 'text/html'
            if dataset is not None:
                content = render_j2_template(self.config,
                                             'collections/collection.html',
                                             fcm)
            else:
                content = render_j2_template(self.config,
                                             'collections/index.html', fcm)

            return headers_, 200, content

        if format_ == 'jsonld':
            jsonld = self.fcmld.copy()
            if dataset is not None:
                jsonld['dataset'] = jsonldify_collection(self, fcm)
            else:
                jsonld['dataset'] = list(
                    map(
                        lambda collection: jsonldify_collection(
                            self, collection
                        ), fcm.get('collections', [])
                    )
                )
            headers_['Content-Type'] = 'application/ld+json'
            return headers_, 200, to_json(jsonld, self.pretty_print)

        return headers_, 200, to_json(fcm, self.pretty_print)

    @pre_process
    @jsonldify
    def get_collection_queryables(self, headers_, format_, dataset=None):
        """
        Provide collection queryables

        :param headers_: copy of HEADERS object
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param dataset: name of collection

        :returns: tuple of headers, status code, content
        """

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        if any([dataset is None,
                dataset not in self.config['resources'].keys()]):

            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        LOGGER.debug('Creating collection queryables')
        LOGGER.debug('Loading provider')
        try:
            p = load_plugin('provider', get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'feature'))
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception, self.pretty_print)
        except ProviderQueryError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception, self.pretty_print)

        queryables = {
            'queryables': []
        }

        for k, v in p.fields.items():
            show_field = False
            if p.properties:
                if k in p.properties:
                    show_field = True
            else:
                show_field = True

            if show_field:
                queryables['queryables'].append({
                    'queryable': k,
                    'type': v
                })

        if format_ == 'html':  # render
            queryables['title'] = self.config['resources'][dataset]['title']
            headers_['Content-Type'] = 'text/html'
            content = render_j2_template(self.config,
                                         'collections/queryables.html',
                                         queryables)

            return headers_, 200, content

        return headers_, 200, to_json(queryables, self.pretty_print)

    def get_collection_items(self, headers, args, dataset, pathinfo=None):
        """
        Queries collection

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param dataset: dataset name
        :param pathinfo: path location

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        properties = []
        reserved_fieldnames = ['bbox', 'f', 'limit', 'startindex',
                               'resulttype', 'datetime', 'sortby',
                               'properties', 'skipGeometry']
        formats = FORMATS
        formats.extend(f.lower() for f in PLUGINS['formatter'].keys())

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        format_ = check_format(args, headers)

        if format_ is not None and format_ not in formats:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Processing startindex parameter')
        try:
            startindex = int(args.get('startindex'))
            if startindex < 0:
                exception = {
                    'code': 'InvalidParameterValue',
                    'description': 'startindex value should be positive ' +
                                   'or zero'
                }
                LOGGER.error(exception)
                return headers_, 400, to_json(exception, self.pretty_print)
        except (TypeError) as err:
            LOGGER.warning(err)
            startindex = 0
        except ValueError as err:
            LOGGER.warning(err)
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'startindex value should be an integer'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        LOGGER.debug('Processing limit parameter')
        try:
            limit = int(args.get('limit'))
            # TODO: We should do more validation, against the min and max
            # allowed by the server configuration
            if limit <= 0:
                exception = {
                    'code': 'InvalidParameterValue',
                    'description': 'limit value should be strictly positive'
                }
                LOGGER.error(exception)
                return headers_, 400, to_json(exception, self.pretty_print)
        except TypeError as err:
            LOGGER.warning(err)
            limit = int(self.config['server']['limit'])
        except ValueError as err:
            LOGGER.warning(err)
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'limit value should be an integer'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        resulttype = args.get('resulttype') or 'results'

        LOGGER.debug('Processing bbox parameter')

        bbox = args.get('bbox')

        if bbox is None:
            bbox = []
        else:
            try:
                bbox = validate_bbox(bbox)
            except ValueError as err:
                exception = {
                    'code': 'InvalidParameterValue',
                    'description': str(err)
                }
                LOGGER.error(exception)
                return headers_, 400, to_json(exception, self.pretty_print)

        LOGGER.debug('Processing datetime parameter')
        datetime_ = args.get('datetime')
        try:
            datetime_ = validate_datetime(collections[dataset]['extents'],
                                          datetime_)
        except ValueError as err:
            exception = {
                'code': 'InvalidParameterValue',
                'description': str(err)
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        LOGGER.debug('Loading provider')
        try:
            p = load_plugin('provider', get_provider_by_type(
                collections[dataset]['providers'], 'feature'))
        except ProviderTypeError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'invalid provider type'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception, self.pretty_print)
        except ProviderQueryError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception, self.pretty_print)

        LOGGER.debug('processing property parameters')
        for k, v in args.items():
            if k not in reserved_fieldnames and k not in p.fields.keys():
                exception = {
                    'code': 'InvalidParameterValue',
                    'description': 'unknown query parameter'
                }
                LOGGER.error(exception)
                return headers_, 400, to_json(exception, self.pretty_print)
            elif k not in reserved_fieldnames and k in p.fields.keys():
                LOGGER.debug('Add property filter {}={}'.format(k, v))
                properties.append((k, v))

        LOGGER.debug('processing sort parameter')
        val = args.get('sortby')

        if val is not None:
            sortby = []
            sorts = val.split(',')
            for s in sorts:
                if ':' in s:
                    prop, order = s.split(':')
                    if order not in ['A', 'D']:
                        exception = {
                            'code': 'InvalidParameterValue',
                            'description': 'sort order should be A or D'
                        }
                        LOGGER.error(exception)
                        return headers_, 400, to_json(exception,
                                                      self.pretty_print)
                    sortby.append({'property': prop, 'order': order})
                else:
                    sortby.append({'property': s, 'order': 'A'})
            for s in sortby:
                if s['property'] not in p.fields.keys():
                    exception = {
                        'code': 'InvalidParameterValue',
                        'description': 'bad sort property'
                    }
                    LOGGER.error(exception)
                    return headers_, 400, to_json(exception, self.pretty_print)
        else:
            sortby = []

        LOGGER.debug('processing properties parameter')
        val = args.get('properties')

        if val is not None:
            select_properties = val.split(',')
            properties_to_check = set(p.properties) | set(p.fields.keys())

            if (len(list(set(select_properties) -
                         set(properties_to_check))) > 0):
                exception = {
                    'code': 'InvalidParameterValue',
                    'description': 'unknown properties specified'
                }
                LOGGER.error(exception)
                return headers_, 400, to_json(exception, self.pretty_print)
        else:
            select_properties = []

        LOGGER.debug('processing skipGeometry parameter')
        val = args.get('skipGeometry')
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

        try:
            content = p.query(startindex=startindex, limit=limit,
                              resulttype=resulttype, bbox=bbox,
                              datetime_=datetime_, properties=properties,
                              sortby=sortby,
                              select_properties=select_properties,
                              skip_geometry=skip_geometry)
        except ProviderConnectionError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(err)
            return headers_, 500, to_json(exception, self.pretty_print)
        except ProviderQueryError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(err)
            return headers_, 500, to_json(exception, self.pretty_print)
        except ProviderGenericError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'generic error (check logs)'
            }
            LOGGER.error(err)
            return headers_, 500, to_json(exception, self.pretty_print)

        serialized_query_params = ''
        for k, v in args.items():
            if k not in ('f', 'startindex'):
                serialized_query_params += '&'
                serialized_query_params += urllib.parse.quote(k, safe='')
                serialized_query_params += '='
                serialized_query_params += urllib.parse.quote(str(v), safe=',')

        content['links'] = [{
            'type': 'application/geo+json',
            'rel': 'self' if not format_ or format_ == 'json' else 'alternate',
            'title': 'This document as GeoJSON',
            'href': '{}/collections/{}/items?f=json{}'.format(
                self.config['server']['url'], dataset, serialized_query_params)
            }, {
            'rel': 'self' if format_ == 'jsonld' else 'alternate',
            'type': 'application/ld+json',
            'title': 'This document as RDF (JSON-LD)',
            'href': '{}/collections/{}/items?f=jsonld{}'.format(
                self.config['server']['url'], dataset, serialized_query_params)
            }, {
            'type': 'text/html',
            'rel': 'self' if format_ == 'html' else 'alternate',
            'title': 'This document as HTML',
            'href': '{}/collections/{}/items?f=html{}'.format(
                self.config['server']['url'], dataset, serialized_query_params)
            }
        ]

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
                'title': collections[dataset]['title'],
                'rel': 'collection',
                'href': '{}/collections/{}'.format(
                    self.config['server']['url'], dataset)
            })

        content['timeStamp'] = datetime.utcnow().strftime(
            '%Y-%m-%dT%H:%M:%S.%fZ')

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'

            # For constructing proper URIs to items
            if pathinfo:
                path_info = '/'.join([
                    self.config['server']['url'].rstrip('/'),
                    pathinfo.strip('/')])
            else:
                path_info = '/'.join([
                    self.config['server']['url'].rstrip('/'),
                    headers.environ['PATH_INFO'].strip('/')])

            content['items_path'] = path_info
            content['dataset_path'] = '/'.join(path_info.split('/')[:-1])
            content['collections_path'] = '/'.join(path_info.split('/')[:-2])
            content['startindex'] = startindex

            content = render_j2_template(self.config,
                                         'collections/items/index.html',
                                         content)
            return headers_, 200, content
        elif format_ == 'csv':  # render
            formatter = load_plugin('formatter', {'name': 'CSV', 'geom': True})

            content = formatter.write(
                data=content,
                options={
                    'provider_def': get_provider_by_type(
                                        collections[dataset]['providers'],
                                        'feature')
                }
            )

            headers_['Content-Type'] = '{}; charset={}'.format(
                formatter.mimetype, self.config['server']['encoding'])

            cd = 'attachment; filename="{}.csv"'.format(dataset)
            headers_['Content-Disposition'] = cd

            return headers_, 200, content
        elif format_ == 'jsonld':
            headers_['Content-Type'] = 'application/ld+json'
            content = geojson2geojsonld(self.config, content, dataset)
            return headers_, 200, content

        return headers_, 200, to_json(content, self.pretty_print)

    @pre_process
    def get_collection_item(self, headers_, format_, dataset, identifier):
        """
        Get a single collection item

        :param headers_: copy of HEADERS object
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param dataset: dataset name
        :param identifier: item identifier

        :returns: tuple of headers, status code, content
        """

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        LOGGER.debug('Processing query parameters')

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        LOGGER.debug('Loading provider')
        try:
            p = load_plugin('provider', get_provider_by_type(
                collections[dataset]['providers'], 'feature'))
        except ProviderTypeError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'invalid provider type'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)
        try:
            LOGGER.debug('Fetching id {}'.format(identifier))
            content = p.get(identifier)
        except ProviderConnectionError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(err)
            return headers_, 500, to_json(exception, self.pretty_print)
        except ProviderItemNotFoundError:
            exception = {
                'code': 'NotFound',
                'description': 'identifier not found'
            }
            LOGGER.error(exception)
            return headers_, 404, to_json(exception, self.pretty_print)
        except ProviderQueryError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(err)
            return headers_, 500, to_json(exception, self.pretty_print)
        except ProviderGenericError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'generic error (check logs)'
            }
            LOGGER.error(err)
            return headers_, 500, to_json(exception, self.pretty_print)

        if content is None:
            exception = {
                'code': 'NotFound',
                'description': 'identifier not found'
            }
            LOGGER.error(exception)
            return headers_, 404, to_json(exception, self.pretty_print)

        content['links'] = [{
            'rel': 'self' if not format_ or format_ == 'json' else 'alternate',
            'type': 'application/geo+json',
            'title': 'This document as GeoJSON',
            'href': '{}/collections/{}/items/{}?f=json'.format(
                self.config['server']['url'], dataset, identifier)
            }, {
            'rel': 'self' if format_ == 'jsonld' else 'alternate',
            'type': 'application/ld+json',
            'title': 'This document as RDF (JSON-LD)',
            'href': '{}/collections/{}/items/{}?f=jsonld'.format(
                self.config['server']['url'], dataset, identifier)
            }, {
            'rel': 'self' if format_ == 'html' else 'alternate',
            'type': 'text/html',
            'title': 'This document as HTML',
            'href': '{}/collections/{}/items/{}?f=html'.format(
                self.config['server']['url'], dataset, identifier)
            }, {
            'rel': 'collection',
            'type': 'application/json',
            'title': collections[dataset]['title'],
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
            }
        ]

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'

            content['title'] = collections[dataset]['title']
            content = render_j2_template(self.config,
                                         'collections/items/item.html',
                                         content)
            return headers_, 200, content
        elif format_ == 'jsonld':
            headers_['Content-Type'] = 'application/ld+json'
            content = geojson2geojsonld(
                self.config, content, dataset, identifier=identifier
            )
            return headers_, 200, content

        return headers_, 200, to_json(content, self.pretty_print)

    @jsonldify
    def get_collection_coverage(self, headers, args, dataset):
        """
        Returns a subset of a collection coverage

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()
        query_args = {}
        format_ = 'json'

        LOGGER.debug('Processing query parameters')

        subsets = {}

        LOGGER.debug('Loading provider')
        try:
            collection_def = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'coverage')

            p = load_plugin('provider', collection_def)
        except KeyError:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'collection does not exist'
            }
            LOGGER.error(exception)
            return headers_, 404, to_json(exception, self.pretty_print)
        except ProviderTypeError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'invalid provider type'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception, self.pretty_print)

        LOGGER.debug('Processing bbox parameter')

        bbox = args.get('bbox')

        if bbox is None:
            bbox = []
        else:
            try:
                bbox = validate_bbox(bbox)
            except ValueError as err:
                exception = {
                    'code': 'InvalidParameterValue',
                    'description': str(err)
                }
                LOGGER.error(exception)
                return headers_, 400, to_json(exception, self.pretty_print)

        query_args['bbox'] = bbox

        LOGGER.debug('Processing datetime parameter')

        datetime_ = args.get('datetime', None)

        try:
            datetime_ = validate_datetime(
                self.config['resources'][dataset]['extents'], datetime_)
        except ValueError as err:
            exception = {
                'code': 'InvalidParameterValue',
                'description': str(err)
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        query_args['datetime_'] = datetime_

        if 'f' in args:
            query_args['format_'] = format_ = args['f']

        if 'rangeSubset' in args:
            LOGGER.debug('Processing rangeSubset parameter')

            query_args['range_subset'] = list(
                filter(None, args['rangeSubset'].split(',')))
            LOGGER.debug('Fields: {}'.format(query_args['range_subset']))

            for a in query_args['range_subset']:
                if a not in p.fields:
                    exception = {
                        'code': 'InvalidParameterValue',
                        'description': 'Invalid field specified'
                    }
                    LOGGER.error(exception)
                    return headers_, 400, to_json(exception, self.pretty_print)

        if 'subset' in args:
            LOGGER.debug('Processing subset parameter')
            for s in args['subset'].split(','):
                try:
                    if '"' not in s:
                        m = re.search(r'(.*)\((.*):(.*)\)', s)
                    else:
                        m = re.search(r'(.*)\(\"(\S+)\":\"(\S+.*)\"\)', s)

                    subset_name = m.group(1)

                    if subset_name not in p.axes:
                        exception = {
                            'code': 'InvalidParameterValue',
                            'description': 'Invalid axis name'
                        }
                        LOGGER.error(exception)
                        return (headers_, 400, to_json(exception,
                                self.pretty_print))

                    subsets[subset_name] = list(map(
                        get_typed_value, m.group(2, 3)))
                except AttributeError:
                    exception = {
                        'code': 'InvalidParameterValue',
                        'description': 'subset should be like "axis(min:max)"'
                    }
                    LOGGER.error(exception)
                    return headers_, 400, to_json(exception, self.pretty_print)

            query_args['subsets'] = subsets
            LOGGER.debug('Subsets: {}'.format(query_args['subsets']))

        LOGGER.debug('Querying coverage')
        try:
            data = p.query(**query_args)
        except ProviderInvalidQueryError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error: {}'.format(err),
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)
        except ProviderNoDataError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'No data found'
            }
            LOGGER.debug(exception)
            return headers_, 204, to_json(exception, self.pretty_print)
        except ProviderQueryError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception, self.pretty_print)

        mt = collection_def['format']['name']

        if format_ == mt:
            headers_['Content-Type'] = collection_def['format']['mimetype']
            return headers_, 200, data
        elif format_ == 'json':
            headers_['Content-Type'] = 'application/prs.coverage+json'
            return headers_, 200, to_json(data, self.pretty_print)
        else:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'invalid format parameter'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(data, self.pretty_print)

    @jsonldify
    def get_collection_coverage_domainset(self, headers, args, dataset):
        """
        Returns a collection coverage domainset

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        format_ = check_format(args, headers)
        if format_ is None:
            format_ = 'json'

        LOGGER.debug('Loading provider')
        try:
            collection_def = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'coverage')

            p = load_plugin('provider', collection_def)

            data = p.get_coverage_domainset()
        except KeyError:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'collection does not exist'
            }
            LOGGER.error(exception)
            return headers_, 404, to_json(exception, self.pretty_print)
        except ProviderTypeError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'invalid provider type'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception, self.pretty_print)

        if format_ == 'json':
            return headers_, 200, to_json(data, self.pretty_print)
        elif format_ == 'html':
            data['id'] = dataset
            data['title'] = self.config['resources'][dataset]['title']
            content = render_j2_template(self.config,
                                         'collections/coverage/domainset.html',
                                         data)
            headers_['Content-Type'] = 'text/html'
            return headers_, 200, content
        else:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'invalid format parameter'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

    @jsonldify
    def get_collection_coverage_rangetype(self, headers, args, dataset):
        """
        Returns a collection coverage rangetype

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()
        format_ = check_format(args, headers)
        if format_ is None:
            format_ = 'json'

        LOGGER.debug('Loading provider')
        try:
            collection_def = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'coverage')

            p = load_plugin('provider', collection_def)

            data = p.get_coverage_rangetype()
        except KeyError:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'collection does not exist'
            }
            LOGGER.error(exception)
            return headers_, 404, to_json(exception, self.pretty_print)
        except ProviderTypeError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'invalid provider type'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception, self.pretty_print)

        if format_ == 'json':
            return (headers_, 200, to_json(data, self.pretty_print))
        elif format_ == 'html':
            data['id'] = dataset
            data['title'] = self.config['resources'][dataset]['title']
            content = render_j2_template(self.config,
                                         'collections/coverage/rangetype.html',
                                         data)
            headers_['Content-Type'] = 'text/html'
            return headers_, 200, content
        else:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'invalid format parameter'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

    @pre_process
    @jsonldify
    def get_collection_tiles(self, headers_, format_, dataset=None):
        """
        Provide collection tiles

        :param headers_: copy of HEADERS object
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param dataset: name of collection

        :returns: tuple of headers, status code, content
        """

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        if any([dataset is None,
                dataset not in self.config['resources'].keys()]):

            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        LOGGER.debug('Creating collection tiles')
        LOGGER.debug('Loading provider')
        try:
            t = get_provider_by_type(
                    self.config['resources'][dataset]['providers'], 'tile')
            p = load_plugin('provider', t)
        except (KeyError, ProviderTypeError):
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection tiles'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception)
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception)
        except ProviderQueryError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception)

        tiles = {
            'title': dataset,
            'description': self.config['resources'][dataset]['description'],
            'links': [],
            'tileMatrixSetLinks': []
        }

        tiles['links'].append({
            'type': 'application/json',
            'rel': 'self' if format_ == 'json' else 'alternate',
            'title': 'This document as JSON',
            'href': '{}/collections/{}/tiles?f=json'.format(
                self.config['server']['url'], dataset)
        })
        tiles['links'].append({
            'type': 'application/ld+json',
            'rel': 'self' if format_ == 'jsonld' else 'alternate',
            'title': 'This document as RDF (JSON-LD)',
            'href': '{}/collections/{}/tiles?f=jsonld'.format(
                self.config['server']['url'], dataset)
        })
        tiles['links'].append({
            'type': 'text/html',
            'rel': 'self' if format_ == 'html' else 'alternate',
            'title': 'This document as HTML',
            'href': '{}/collections/{}/tiles?f=html'.format(
                self.config['server']['url'], dataset)
        })

        for service in p.get_tiles_service(
            baseurl=self.config['server']['url'],
            servicepath='/collections/{}/\
tiles/{{{}}}/{{{}}}/{{{}}}/{{{}}}?f=mvt'
            .format(dataset, 'tileMatrixSetId',
                    'tileMatrix', 'tileRow', 'tileCol'))['links']:
            tiles['links'].append(service)

        tiles['tileMatrixSetLinks'] = p.get_tiling_schemes()
        metadata_format = p.options['metadata_format']

        if format_ == 'html':  # render
            tiles['id'] = dataset
            tiles['title'] = self.config['resources'][dataset]['title']
            tiles['tilesets'] = [
                scheme['tileMatrixSet'] for scheme in p.get_tiling_schemes()]
            tiles['format'] = metadata_format
            tiles['bounds'] = \
                self.config['resources'][dataset]['extents']['spatial']['bbox']
            tiles['minzoom'] = p.options['zoom']['min']
            tiles['maxzoom'] = p.options['zoom']['max']

            headers_['Content-Type'] = 'text/html'
            content = render_j2_template(self.config,
                                         'collections/tiles/index.html', tiles)

            return headers_, 200, content

        return headers_, 200, to_json(tiles, self.pretty_print)

    @pre_process
    @jsonldify
    def get_collection_tiles_data(self, headers, format_, dataset=None,
                                  matrix_id=None, z_idx=None, y_idx=None,
                                  x_idx=None):
        """
        Get collection items tiles

        :param headers: copy of HEADERS object
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param dataset: dataset name
        :param matrix_id: matrix identifier
        :param z_idx: z index
        :param y_idx: y index
        :param x_idx: x index

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()
#        format_ = check_format({}, headers)

        if format_ is None and format_ not in ['mvt']:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception)

        LOGGER.debug('Processing tiles')

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception)

        LOGGER.debug('Loading tile provider')
        try:
            t = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'tile')
            p = load_plugin('provider', t)

            format_ = p.format_type
            headers_['Content-Type'] = format_

            LOGGER.debug('Fetching tileset id {} and tile {}/{}/{}'.format(
                matrix_id, z_idx, y_idx, x_idx))
            content = p.get_tiles(layer=p.get_layer(), tileset=matrix_id,
                                  z=z_idx, y=y_idx, x=x_idx, format_=format_)
            if content is None:
                exception = {
                    'code': 'NotFound',
                    'description': 'identifier not found'
                }
                LOGGER.error(exception)
                return headers_, 404, to_json(exception)
            else:
                return headers_, 202, content
        # @TODO: figure out if the spec requires to return json errors
        except KeyError:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection tiles'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception)
        except ProviderConnectionError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(err)
            return headers_, 500, to_json(exception)
        except ProviderTilesetIdNotFoundError:
            exception = {
                'code': 'NotFound',
                'description': 'Tileset id not found'
            }
            LOGGER.error(exception)
            return headers_, 404, to_json(exception)
        except ProviderTileQueryError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'Tile not found'
            }
            LOGGER.error(err)
            return headers_, 500, to_json(exception)
        except ProviderTileNotFoundError as err:
            exception = {
                'code': 'NoMatch',
                'description': 'tile not found (check logs)'
            }
            LOGGER.error(err)
            return headers_, 404, to_json(exception)
        except ProviderGenericError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'generic error (check logs)'
            }
            LOGGER.error(err)
            return headers_, 500, to_json(exception)

    @pre_process
    @jsonldify
    def get_collection_tiles_metadata(self, headers_, format_, dataset=None,
                                      matrix_id=None):
        """
        Get collection items tiles

        :param headers_: copy of HEADERS object
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param dataset: dataset name
        :param matrix_id: matrix identifier

        :returns: tuple of headers, status code, content
        """

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        if any([dataset is None,
                dataset not in self.config['resources'].keys()]):

            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        LOGGER.debug('Creating collection tiles')
        LOGGER.debug('Loading provider')
        try:
            t = get_provider_by_type(
                self.config['resources'][dataset]['providers'], 'tile')
            p = load_plugin('provider', t)
        except KeyError:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection tiles'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception, self.pretty_print)
        except ProviderQueryError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception, self.pretty_print)

        if matrix_id not in p.options['schemes']:
            exception = {
                'code': 'NotFound',
                'description': 'tileset not found'
            }
            LOGGER.error(exception)
            return headers_, 404, to_json(exception, self.pretty_print)

        metadata_format = p.options['metadata_format']
        tilejson = True if (metadata_format == 'tilejson') else False

        tiles_metadata = p.get_metadata(
            dataset=dataset, server_url=self.config['server']['url'],
            layer=p.get_layer(), tileset=matrix_id, tilejson=tilejson)

        if format_ == 'html':  # render
            metadata = dict(metadata=tiles_metadata)
            metadata['id'] = dataset
            metadata['title'] = self.config['resources'][dataset]['title']
            metadata['tileset'] = matrix_id
            metadata['format'] = metadata_format
            headers_['Content-Type'] = 'text/html'

            content = render_j2_template(self.config,
                                         'collections/tiles/metadata.html',
                                         metadata)

            return headers_, 200, content

        return headers_, 200, to_json(tiles_metadata, self.pretty_print)

    @pre_process
    @jsonldify
    def describe_processes(self, headers_, format_, process=None):
        """
        Provide processes metadata

        :param headers: dict of HTTP headers
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param process: process identifier, defaults to None to obtain
                        information about all processes

        :returns: tuple of headers, status code, content
        """

        processes = []

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        processes_config = filter_dict_by_key_value(self.config['resources'],
                                                    'type', 'process')

        if process is not None:
            if process not in processes_config.keys() or not processes_config:
                exception = {
                    'code': 'NoSuchProcess',
                    'description': 'identifier not found'
                }
                LOGGER.error(exception)
                return headers_, 404, to_json(exception, self.pretty_print)

        if processes_config:
            if process is not None:
                relevant_processes = [(process, processes_config[process])]
            else:
                relevant_processes = processes_config.items()

            for key, value in relevant_processes:
                p = load_plugin('process',
                                processes_config[key]['processor'])

                p2 = deepcopy(p.metadata)

                p2['jobControlOptions'] = ['sync-execute']
                if self.manager.is_async:
                    p2['jobControlOptions'].append('async-execute')

                p2['outputTransmission'] = ['value']
                p2['links'] = p2.get('links', [])

                jobs_url = '{}/processes/{}/jobs'.format(
                    self.config['server']['url'], key)

                link = {
                    'type': 'text/html',
                    'rel': 'collection',
                    'href': '{}?f=html'.format(jobs_url),
                    'title': 'jobs for this process as HTML',
                    'hreflang': self.config['server'].get('language', None)
                }
                p2['links'].append(link)

                link = {
                    'type': 'application/json',
                    'rel': 'collection',
                    'href': '{}?f=json'.format(jobs_url),
                    'title': 'jobs for this process as JSON',
                    'hreflang': self.config['server'].get('language', None)
                }
                p2['links'].append(link)

                processes.append(p2)

        if process is not None:
            response = processes[0]
        else:
            response = {
                'processes': processes
            }

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
            if process is not None:
                response = render_j2_template(self.config,
                                              'processes/process.html',
                                              response)
            else:
                response = render_j2_template(self.config,
                                              'processes/index.html', response)

            return headers_, 200, response

        return headers_, 200, to_json(response, self.pretty_print)

    def get_process_jobs(self, headers, args, process_id, job_id=None):
        """
        Get process jobs

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param process_id: id of process
        :param job_id: id of job

        :returns: tuple of headers, status code, content
        """

        format_ = check_format(args, headers)

        headers_ = HEADERS.copy()

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        response = {}

        processes = filter_dict_by_key_value(
            self.config['resources'], 'type', 'process')

        if process_id not in processes:
            exception = {
                'code': 'NoSuchProcess',
                'description': 'identifier not found'
            }
            LOGGER.error(exception)
            return headers_, 404, to_json(exception, self.pretty_print)

        p = load_plugin('process', processes[process_id]['processor'])

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

        if format_ == 'html':
            headers_['Content-Type'] = 'text/html'
            data = {
                'process': {
                    'id': process_id,
                    'title': p.metadata['title']
                },
                'jobs': serialized_jobs,
                'now': datetime.now(timezone.utc).strftime(DATETIME_FORMAT)
            }
            response = render_j2_template(self.config, j2_template, data)
            return headers_, 200, response

        return headers_, 200, to_json(serialized_jobs, self.pretty_print)

    def execute_process(self, headers, args, data, process_id):
        """
        Execute process

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param data: process data
        :param process_id: id of process

        :returns: tuple of headers, status code, content
        """

        format_ = check_format(args, headers)

        headers_ = HEADERS.copy()

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        response = {}

        processes_config = filter_dict_by_key_value(
            self.config['resources'], 'type', 'process'
        )
        if process_id not in processes_config:
            exception = {
                'code': 'NoSuchProcess',
                'description': 'identifier not found'
            }
            LOGGER.error(exception)
            return headers_, 404, to_json(exception, self.pretty_print)

        if not self.manager:
            LOGGER.debug('Process manager is undefined')
            exception = {
                'code': 'NoApplicableCode',
                'description': 'No processing service defined'
            }
            return headers_, 500, json.dumps(exception)

        process = load_plugin('process',
                              processes_config[process_id]['processor'])

        if not data:
            # TODO not all processes require input, e.g. time-depenendent or
            # random value generators
            exception = {
                'code': 'MissingParameterValue',
                'description': 'missing request data'
            }
            LOGGER.info(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        try:
            # Parse bytes data, if applicable
            data = data.decode()
        except (UnicodeDecodeError, AttributeError):
            pass

        try:
            data = json.loads(data)
        except (json.decoder.JSONDecodeError, TypeError) as err:
            # Input does not appear to be valid JSON
            LOGGER.error(err)
            LOGGER.debug(data)
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'invalid request data'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

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
        except KeyError as err:
            # Return 4XX client error for missing 'id' or 'value' in an input
            LOGGER.error(err)
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'invalid request data'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)
        else:
            LOGGER.debug(data_dict)

        job_id = str(uuid.uuid1())
        url = '{}/processes/{}/jobs/{}'.format(
            self.config['server']['url'], process_id, job_id)

        headers_['Location'] = url

        outputs = status = None
        is_async = data.get('mode', 'auto') == 'async'

        if is_async:
            LOGGER.debug('Asynchronous request mode detected')

        try:
            LOGGER.debug('Executing process')
            outputs, status = self.manager.execute_process(
                process, job_id, data_dict, is_async)
        except ProcessorExecuteError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'Processing error'
            }
            LOGGER.error(err)
            return headers_, 500, to_json(exception, self.pretty_print)

        if status == JobStatus.failed:
            response = outputs

        ct = process.metadata['outputs'][0]['output']['formats'][0]['mimeType']

        if data.get('response', 'document') == 'raw':
            headers_['Content-Type'] = ct
            if format_ == 'json':
                response = to_json(outputs)
            else:
                response = outputs

        elif status != JobStatus.failed and not is_async:
            response['outputs'] = outputs

        if is_async:
            http_status = 201
        else:
            http_status = 200

        return headers_, http_status, to_json(response, self.pretty_print)

    def get_process_job_result(self, headers, args, process_id, job_id):
        """
        Get result of job (instance of a process)

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param process_id: name of process
        :param job_id: ID of job

        :returns: tuple of headers, status code, content
        """
        headers_ = HEADERS.copy()
        processes_config = filter_dict_by_key_value(self.config['resources'],
                                                    'type', 'process')
        if process_id not in processes_config:
            exception = {
                'code': 'NoSuchProcess',
                'description': 'identifier not found'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)

        process = load_plugin('process',
                              processes_config[process_id]['processor'])

        if not process:
            exception = {
                'code': 'NoSuchProcess',
                'description': 'identifier not found'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)

        job = self.manager.get_job(process_id, job_id)

        if not job:
            exception = {
                'code': 'NoSuchJob',
                'description': 'job not found'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)

        status = JobStatus[job['status']]

        if status == JobStatus.running:
            exception = {
                'code': 'ResultNotReady',
                'description': 'job still running'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)

        elif status == JobStatus.accepted:
            # NOTE: this case is not mentioned in the specification
            exception = {
                'code': 'ResultNotReady',
                'description': 'job accepted but not yet running'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)

        elif status == JobStatus.failed:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'job failed'
            }
            LOGGER.info(exception)
            return headers_, 400, json.dumps(exception)

        mimetype, job_output = self.manager.get_job_result(process_id, job_id)

        format_ = check_format(args, headers)

        if mimetype not in [None, 'application/json']:
            headers_['Content-Type'] = mimetype
            content = job_output
        else:
            if format_ == 'json':
                content = json.dumps(job_output, sort_keys=True, indent=4,
                                     default=json_serial)
            else:
                headers_['Content-Type'] = 'text/html'
                data = {
                    'process': {
                        'id': process_id, 'title': process.metadata['title']
                    },
                    'job': {'id': job_id},
                    'result': job_output
                }
                content = render_j2_template(
                    self.config, 'processes/jobs/results/index.html', data)

        return headers_, 200, content

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

    @pre_process
    @jsonldify
    def get_stac_root(self, headers_, format_):

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        id_ = 'pygeoapi-stac'
        stac_version = '0.6.2'
        stac_url = os.path.join(self.config['server']['url'], 'stac')

        content = {
            'id': id_,
            'stac_version': stac_version,
            'title': self.config['metadata']['identification']['title'],
            'description': self.config['metadata']['identification']['description'],  # noqa
            'license': self.config['metadata']['license']['name'],
            'providers': [{
                'name': self.config['metadata']['provider']['name'],
                'url': self.config['metadata']['provider']['url'],
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

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
            content = render_j2_template(self.config, 'stac/collection.html',
                                         content)
            return headers_, 200, content

        return headers_, 200, to_json(content, self.pretty_print)

    @pre_process
    @jsonldify
    def get_stac_path(self, headers_, format_, path):

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, to_json(exception, self.pretty_print)

        LOGGER.debug('Path: {}'.format(path))
        dir_tokens = path.split('/')
        if dir_tokens:
            dataset = dir_tokens[0]

        stac_collections = filter_dict_by_key_value(self.config['resources'],
                                                    'type', 'stac-collection')

        if dataset not in stac_collections:
            exception = {
                'code': 'NotFound',
                'description': 'collection not found'
            }
            LOGGER.error(exception)
            return headers_, 404, to_json(exception, self.pretty_print)

        LOGGER.debug('Loading provider')
        try:
            p = load_plugin('provider', get_provider_by_type(
                stac_collections[dataset]['providers'], 'stac'))
        except ProviderConnectionError as err:
            LOGGER.error(err)
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, to_json(exception, self.pretty_print)

        id_ = '{}-stac'.format(dataset)
        stac_version = '0.6.2'
        description = stac_collections[dataset]['description']

        content = {
            'id': id_,
            'stac_version': stac_version,
            'description': description,
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
            exception = {
                'code': 'NotFound',
                'description': 'resource not found'
            }
            return headers_, 404, to_json(exception, self.pretty_print)
        except Exception as err:
            LOGGER.error(err)
            exception = {
                'code': 'NoApplicableCode',
                'description': 'data query error'
            }
            return headers_, 500, to_json(exception, self.pretty_print)

        if isinstance(stac_data, dict):
            content.update(stac_data)
            content['links'].extend(stac_collections[dataset]['links'])

            if format_ == 'html':  # render
                headers_['Content-Type'] = 'text/html'
                content['path'] = path
                if 'assets' in content:  # item view
                    content = render_j2_template(self.config,
                                                 'stac/item.html',
                                                 content)
                else:
                    content = render_j2_template(self.config,
                                                 'stac/catalog.html',
                                                 content)

                return headers_, 200, content

            return headers_, 200, to_json(content, self.pretty_print)

        else:  # send back file
            headers_.pop('Content-Type', None)
            return headers_, 200, stac_data


def check_format(args, headers):
    """
    check format requested from arguments or headers

    :param args: dict of request keyword value pairs
    :param headers: dict of request headers

    :returns: format value
    """

    # Optional f=html or f=json query param
    # overrides accept
    format_ = args.get('f')
    if format_:
        return format_

    # Format not specified: get from accept headers
    # format_ = 'text/html'
    headers_ = None
    if 'accept' in headers.keys():
        headers_ = headers['accept']
    elif 'Accept' in headers.keys():
        headers_ = headers['Accept']

    format_ = None
    if headers_:
        headers_ = headers_.split(',')

        if 'text/html' in headers_:
            format_ = 'html'
        elif 'application/ld+json' in headers_:
            format_ = 'jsonld'
        elif 'application/json' in headers_:
            format_ = 'json'

    return format_


def validate_bbox(value=None):
    """
    Helper function to validate bbox parameter

    :param bbox: `list` of minx, miny, maxx, maxy

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

        if te['begin'] is not None and te['begin'].tzinfo is None:
            te['begin'] = te['begin'].replace(tzinfo=pytz.UTC)
        if te['end'] is not None and te['end'].tzinfo is None:
            te['end'] = te['end'].replace(tzinfo=pytz.UTC)

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
