# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
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

from datetime import datetime
import json
import logging
import os
import urllib.parse

from dateutil.parser import parse as dateparse
import pytz

from pygeoapi import __version__
from pygeoapi.linked_data import (geojson2geojsonld, jsonldify)
from pygeoapi.log import setup_logger
from pygeoapi.plugin import load_plugin, PLUGINS
from pygeoapi.provider.base import (
    ProviderGenericError, ProviderConnectionError, ProviderNotFoundError,
    ProviderQueryError, ProviderItemNotFoundError)
from pygeoapi.util import (dategetter, filter_dict_by_key_value, json_serial,
                           render_j2_template, str2bool, TEMPLATES)

LOGGER = logging.getLogger(__name__)

#: Return headers for response (e.g:X-Powered-By)
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
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson'
]


def pre_process(func):
    """
    Decorator performing header copy and format
    checking before sending arguments to methods

    :param func: decorated function

    :returns: `func`
    """

    def inner(*args, **kwargs):
        cls = args[0]
        requestHeaders = args[1]
        requestArgs = args[2]
        format_ = check_format(requestArgs, requestHeaders)
        return func(cls, requestHeaders, format_, *args[2:], **kwargs)
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

        setup_logger(self.config['logging'])

    @pre_process
    @jsonldify
    def root(self, requestHeaders, format_, *args, **kwargs):
        """
        Provide API

        :param requestHeaders: request headers (immutable)
        :param format_: format of requests, pre checked by
                        pre_process decorator

        :returns: tuple of headers, status code, content
        """
        responseHeaders = HEADERS.copy()
        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

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
            responseHeaders['Content-Type'] = 'text/html'
            content = render_j2_template(self.config, 'root.html', fcm)
            return responseHeaders, 200, content

        if format_ == 'jsonld':
            responseHeaders['Content-Type'] = 'application/ld+json'
            return responseHeaders, 200, json.dumps(self.fcmld)

        return responseHeaders, 200, json.dumps(fcm)

    @pre_process
    def openapi(self, requestHeaders, format_, openapi):
        """
        Provide OpenAPI document

        :param requestHeaders: request headers (immutable)
        :param format_: format of requests, pre checked by
                        pre_process decorator
        :param openapi: dict of OpenAPI definition

        :returns: tuple of headers, status code, content
        """
        responseHeaders = HEADERS.copy()
        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

        path = '/'.join([self.config['server']['url'].rstrip('/'), 'openapi'])

        if format_ == 'html':
            data = {
                'openapi-document-path': path
            }
            responseHeaders['Content-Type'] = 'text/html'
            content = render_j2_template(self.config, 'openapi.html', data)
            return responseHeaders, 200, content

        responseHeaders['Content-Type'] = \
            'application/vnd.oai.openapi+json;version=3.0'

        return responseHeaders, 200, json.dumps(openapi)

    @pre_process
    def conformance(self, requestHeaders, format_):
        """
        Provide conformance definition

        :param requestHeaders: request headers (immutable)
        :param format_: format of requests,
                        pre checked by pre_process decorator

        :returns: tuple of headers, status code, content
        """
        responseHeaders = HEADERS.copy()
        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

        conformance = {
            'conformsTo': CONFORMANCE
        }

        if format_ == 'html':  # render
            responseHeaders['Content-Type'] = 'text/html'
            content = render_j2_template(self.config, 'conformance.html',
                                         conformance)
            return responseHeaders, 200, content

        return responseHeaders, 200, json.dumps(conformance)

    @pre_process
    @jsonldify
    def describe_collections(self, requestHeaders, format_, args, dataset=None):
        """
        Provide collection metadata

        :param requestHeaders: request headers (immutable)
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param dataset: name of collection

        :returns: tuple of headers, status code, content
        """
        repsonseHeaders = HEADERS.copy()
        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return repsonseHeaders, 400, json.dumps(exception)

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
            return repsonseHeaders, 400, json.dumps(exception)

        LOGGER.debug('Creating collections')
        for k, v in collections.items():
            collection = {'links': []}
            collection['id'] = k
            collection['itemType'] = 'Feature'
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
                'title': 'Items as GeoJSON',
                'href': '{}/collections/{}/items?f=json'.format(
                    self.config['server']['url'], k)
            })
            collection['links'].append({
                'type': 'application/ld+json',
                'rel': 'items',
                'title': 'Items as RDF (GeoJSON-LD)',
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

            repsonseHeaders['Content-Type'] = 'text/html'
            if dataset is not None:
                content = render_j2_template(self.config, 'collection.html',
                                             fcm)
            else:
                content = render_j2_template(self.config, 'collections.html',
                                             fcm)

            return repsonseHeaders, 200, content

        if format_ == 'jsonld':
            return repsonseHeaders, 200, json.dumps(self.fcmld)

        return repsonseHeaders, 200, json.dumps(fcm, default=json_serial)

    @pre_process
    @jsonldify
    def get_collection_queryables(self, requestHeaders, format_, args, dataset=None):
        """
        Provide collection queryables

        :param requestHeaders: request headers (immutable)
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param args: dict of HTTP request parameters
        :param dataset: name of collection

        :returns: tuple of headers, status code, content
        """
        responseHeaders = HEADERS.copy()
        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

        if any([dataset is None,
                dataset not in self.config['resources'].keys()]):

            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

        LOGGER.debug('Creating collection queryables')
        LOGGER.debug('Loading provider')
        try:
            p = load_plugin('provider',
                            self.config['resources'][dataset]['provider'])
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return responseHeaders, 500, json.dumps(exception)
        except ProviderQueryError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(exception)
            return responseHeaders, 500, json.dumps(exception)

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
            responseHeaders['Content-Type'] = 'text/html'
            content = render_j2_template(self.config, 'queryables.html',
                                         queryables)

            return responseHeaders, 200, content

        if format_ == 'jsonld':
            responseHeaders['Content-Type'] = 'application/ld+json'
            return responseHeaders, 200, queryables

        return responseHeaders, 200, json.dumps(queryables, default=json_serial)

    @pre_process
    @jsonldify
    def get_collection_items(self, requestHeaders, format_, args, dataset, pathinfo=None):
        """
        Queries collection

        :param requestHeaders: request headers (immutable)
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param args: dict of HTTP request parameters
        :param dataset: dataset name
        :param pathinfo: path location

        :returns: tuple of headers, status code, content
        """

        responseHeaders = HEADERS.copy()

        properties = []
        reserved_fieldnames = ['bbox', 'f', 'limit', 'startindex',
                               'resulttype', 'datetime', 'sortby']
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
            return responseHeaders, 400, json.dumps(exception, default=json_serial)

        if format_ is not None and format_ not in formats:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

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
                return responseHeaders, 400, json.dumps(exception)
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
            return responseHeaders, 400, json.dumps(exception)

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
                return responseHeaders, 400, json.dumps(exception)
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
            return responseHeaders, 400, json.dumps(exception)

        resulttype = args.get('resulttype') or 'results'

        LOGGER.debug('Processing bbox parameter')
        try:
            bbox = args.get('bbox').split(',')
            if len(bbox) != 4:
                exception = {
                    'code': 'InvalidParameterValue',
                    'description': 'bbox values should be minx,miny,maxx,maxy'
                }
                LOGGER.error(exception)
                return responseHeaders, 400, json.dumps(exception)
        except AttributeError:
            bbox = []
        try:
            bbox = [float(c) for c in bbox]
        except ValueError:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'bbox values must be numbers'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

        LOGGER.debug('Processing datetime parameter')
        # TODO: pass datetime to query as a `datetime` object
        # we would need to ensure partial dates work accordingly
        # as well as setting '..' values to `None` so that underlying
        # providers can just assume a `datetime.datetime` object
        #
        # NOTE: needs testing when passing partials from API to backend
        datetime_ = args.get('datetime')
        datetime_invalid = False

        if (datetime_ is not None and
                'temporal' in collections[dataset]['extents']):
            te = collections[dataset]['extents']['temporal']

            if te['begin'] is not None and te['begin'].tzinfo is None:
                te['begin'] = te['begin'].replace(tzinfo=pytz.UTC)
            if te['end'] is not None and te['end'].tzinfo is None:
                te['end'] = te['end'].replace(tzinfo=pytz.UTC)

            if '/' in datetime_:  # envelope
                LOGGER.debug('detected time range')
                LOGGER.debug('Validating time windows')
                datetime_begin, datetime_end = datetime_.split('/')
                if datetime_begin != '..':
                    datetime_begin = dateparse(datetime_begin)
                    if datetime_begin.tzinfo is None:
                        datetime_begin = datetime_begin.replace(
                            tzinfo=pytz.UTC)

                if datetime_end != '..':
                    datetime_end = dateparse(datetime_end)
                    if datetime_end.tzinfo is None:
                        datetime_end = datetime_end.replace(tzinfo=pytz.UTC)

                if te['begin'] is not None and datetime_begin != '..':
                    if datetime_begin < te['begin']:
                        datetime_invalid = True

                if te['end'] is not None and datetime_end != '..':
                    if datetime_end > te['end']:
                        datetime_invalid = True

            else:  # time instant
                datetime__ = dateparse(datetime_)
                if datetime__ != '..':
                    if datetime__.tzinfo is None:
                        datetime__ = datetime__.replace(tzinfo=pytz.UTC)
                LOGGER.debug('detected time instant')
                if te['begin'] is not None and datetime__ != '..':
                    if datetime__ < te['begin']:
                        datetime_invalid = True
                if te['end'] is not None and datetime__ != '..':
                    if datetime__ > te['end']:
                        datetime_invalid = True

        if datetime_invalid:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'datetime parameter out of range'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

        LOGGER.debug('Loading provider')
        try:
            p = load_plugin('provider',
                            collections[dataset]['provider'])
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return responseHeaders, 500, json.dumps(exception)
        except ProviderQueryError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(exception)
            return responseHeaders, 500, json.dumps(exception)

        LOGGER.debug('processing property parameters')
        for k, v in args.items():
            if k not in reserved_fieldnames and k not in p.fields.keys():
                exception = {
                    'code': 'InvalidParameterValue',
                    'description': 'unknown query parameter'
                }
                LOGGER.error(exception)
                return responseHeaders, 400, json.dumps(exception)
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
                        return responseHeaders, 400, json.dumps(exception)
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
                    return responseHeaders, 400, json.dumps(exception)
        else:
            sortby = []

        LOGGER.debug('Querying provider')
        LOGGER.debug('startindex: {}'.format(startindex))
        LOGGER.debug('limit: {}'.format(limit))
        LOGGER.debug('resulttype: {}'.format(resulttype))
        LOGGER.debug('sortby: {}'.format(sortby))

        try:
            content = p.query(startindex=startindex, limit=limit,
                              resulttype=resulttype, bbox=bbox,
                              datetime=datetime_, properties=properties,
                              sortby=sortby)
        except ProviderConnectionError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(err)
            return responseHeaders, 500, json.dumps(exception)
        except ProviderQueryError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(err)
            return responseHeaders, 500, json.dumps(exception)
        except ProviderGenericError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'generic error (check logs)'
            }
            LOGGER.error(err)
            return responseHeaders, 500, json.dumps(exception)

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
            responseHeaders['Content-Type'] = 'text/html'

            # For constructing proper URIs to items
            if pathinfo:
                path_info = '/'.join([
                    self.config['server']['url'].rstrip('/'),
                    pathinfo.strip('/')])
            else:
                LOGGER.debug(requestHeaders)
                LOGGER.debug(requestHeaders.get('PATH_INFO'))
                path_info = '/'.join([
                    self.config['server']['url'].rstrip('/'),
                    requestHeaders.environ['PATH_INFO'].strip('/')])

            content['items_path'] = path_info
            content['dataset_path'] = '/'.join(path_info.split('/')[:-1])
            content['collections_path'] = '/'.join(path_info.split('/')[:-2])
            content['startindex'] = startindex

            content = render_j2_template(self.config, 'items.html',
                                         content)
            return responseHeaders, 200, content
        elif format_ == 'csv':  # render
            formatter = load_plugin('formatter', {'name': 'CSV', 'geom': True})

            content = formatter.write(
                data=content,
                options={
                    'provider_def':
                        collections[dataset]['provider']
                }
            )

            responseHeaders['Content-Type'] = '{}; charset={}'.format(
                formatter.mimetype, self.config['server']['encoding'])

            cd = 'attachment; filename="{}.csv"'.format(dataset)
            responseHeaders['Content-Disposition'] = cd

            return responseHeaders, 200, content

        elif format_ == 'jsonld':
            # @jsonldify is responsible for transforming GeoJSON output
            responseHeaders['Content-Type'] = 'application/ld+json'
            return responseHeaders, 200, content

        return responseHeaders, 200, json.dumps(content, default=json_serial)

    @pre_process
    @jsonldify
    def get_collection_item(self, requestHeaders, format_, args, dataset, identifier):
        """
        Get a single collection item

        :param requestHeaders: request headers (immutable)
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param args: dict of HTTP request parameters
        :param dataset: dataset name
        :param identifier: item identifier

        :returns: tuple of headers, status code, content
        """
        responseHeaders = HEADERS.copy()
        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

        LOGGER.debug('Processing query parameters')

        collections = filter_dict_by_key_value(self.config['resources'],
                                               'type', 'collection')

        if dataset not in collections.keys():
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid collection'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

        LOGGER.debug('Loading provider')
        p = load_plugin('provider', collections[dataset]['provider'])

        try:
            LOGGER.debug('Fetching id {}'.format(identifier))
            content = p.get(identifier)
        except ProviderConnectionError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(err)
            return responseHeaders, 500, json.dumps(exception)
        except ProviderItemNotFoundError:
            exception = {
                'code': 'NotFound',
                'description': 'identifier not found'
            }
            LOGGER.error(exception)
            return responseHeaders, 404, json.dumps(exception)
        except ProviderQueryError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(err)
            return responseHeaders, 500, json.dumps(exception)
        except ProviderGenericError as err:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'generic error (check logs)'
            }
            LOGGER.error(err)
            return responseHeaders, 500, json.dumps(exception)

        if content is None:
            exception = {
                'code': 'NotFound',
                'description': 'identifier not found'
            }
            LOGGER.error(exception)
            return responseHeaders, 404, json.dumps(exception)

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
            responseHeaders['Content-Type'] = 'text/html'

            content['title'] = collections[dataset]['title']
            content = render_j2_template(self.config, 'item.html',
                                         content)
            return responseHeaders, 200, content

        elif format_ == 'jsonld':
            responseHeaders['Content-Type'] = 'application/ld+json'
            return responseHeaders, 200, content

        return responseHeaders, 200, json.dumps(content, default=json_serial)

    @pre_process
    @jsonldify
    def get_stac_root(self, requestHeaders, format_, args):
        responseHeaders = HEADERS.copy()
        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

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
            responseHeaders['Content-Type'] = 'text/html'
            content = render_j2_template(self.config, 'stac/root.html',
                                         content)
            return responseHeaders, 200, content

        return responseHeaders, 200, json.dumps(content, default=json_serial)

    @pre_process
    def get_stac_path(self, requestHeaders, format_, args, path):
        responseHeaders = HEADERS.copy()
        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

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
            return responseHeaders, 404, json.dumps(exception)

        LOGGER.debug('Loading provider')
        try:
            p = load_plugin('provider', stac_collections[dataset]['provider'])
        except ProviderConnectionError as err:
            LOGGER.error(err)
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return responseHeaders, 500, json.dumps(exception)

        id_ = '{}-stac'.format(dataset)
        stac_version = '0.6.2'
        description = stac_collections[dataset]['description']

        content = {
            'id': id_,
            'stac_version': stac_version,
            'description': description,
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
            return responseHeaders, 404, json.dumps(exception)
        except Exception as err:
            LOGGER.error(err)
            exception = {
                'code': 'NoApplicableCode',
                'description': 'data query error'
            }
            return responseHeaders, 500, json.dumps(exception)

        if isinstance(stac_data, dict):
            content.update(stac_data)
            content['links'].extend(stac_collections[dataset]['links'])

            if format_ == 'html':  # render
                responseHeaders['Content-Type'] = 'text/html'
                content['path'] = path
                if 'assets' in content:  # item view
                    content = render_j2_template(self.config,
                                                 'stac/item.html',
                                                 content)
                else:
                    content = render_j2_template(self.config,
                                                 'stac/catalog.html',
                                                 content)

                return responseHeaders, 200, content

            return responseHeaders, 200, json.dumps(content, default=json_serial)

        else:  # send back file
            responseHeaders.pop('Content-Type', None)
            return responseHeaders, 200, stac_data

    @pre_process
    def describe_processes(self, requestHeaders, format_, args, process=None):
        """
        Provide processes metadata

        :param requestHeaders: request headers (immutable)
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param args: dict of HTTP request parameters
        :param process: name of process

        :returns: tuple of headers, status code, content
        """
        responseHeaders = HEADERS.copy()
        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

        processes_config = filter_dict_by_key_value(self.config['resources'],
                                                    'type', 'process')

        if processes_config:
            if process is not None:
                if process not in processes_config.keys():
                    exception = {
                        'code': 'NotFound',
                        'description': 'identifier not found'
                    }
                    LOGGER.error(exception)
                    return responseHeaders, 404, json.dumps(exception)

                p = load_plugin('process',
                                processes_config[process]['processor'])
                p.metadata['jobControlOptions'] = ['sync-execute']
                p.metadata['outputTransmission'] = ['value']
                json_response = p.metadata
            else:
                processes = []
                for k, v in processes_config.items():
                    p = load_plugin('process',
                                    processes_config[k]['processor'])
                    p.metadata['itemType'] = 'process'
                    p.metadata['jobControlOptions'] = ['sync-execute']
                    p.metadata['outputTransmission'] = ['value']
                    processes.append(p.metadata)
                json_response = {
                    'processes': processes
                }
        else:
            processes = []
            json_response = {'processes': processes}

        if format_ == 'html':  # render
            responseHeaders['Content-Type'] = 'text/html'
            if process is not None:
                response = render_j2_template(self.config, 'process.html',
                                              p.metadata)
            else:
                response = render_j2_template(self.config, 'processes.html',
                                              {'processes': processes})

            return responseHeaders, 200, response

        # if format_ == 'jsonld':
        #     responseHeaders['Content-Type'] = 'application/ld+json'
        #     return responseHeaders, 200, json_response

        return responseHeaders, 200, json.dumps(json_response)

    def execute_process(self, requestHeaders, args, data, process):
        """
        Execute process

        :param requestHeaders: request headers (immutable)
        :param args: dict of HTTP request parameters
        :param data: process data
        :param process: name of process

        :returns: tuple of headers, status code, content
        """

        responseHeaders = HEADERS.copy()

        data_dict = {}
        response = {}

        if not data:
            exception = {
                'code': 'MissingParameterValue',
                'description': 'missing request data'
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)

        processes = filter_dict_by_key_value(self.config['resources'],
                                             'type', 'process')

        if process not in processes:
            exception = {
                'code': 'NotFound',
                'description': 'identifier not found'
            }
            LOGGER.error(exception)
            return responseHeaders, 404, json.dumps(exception)

        p = load_plugin('process',
                        processes[process]['processor'])

        data_ = json.loads(data)
        for input_ in data_['inputs']:
            data_dict[input_['id']] = input_['value']

        try:
            outputs = p.execute(data_dict)
            m = p.metadata
            if 'raw' in args and str2bool(args['raw']):
                responseHeaders['Content-Type'] = \
                    m['outputs'][0]['output']['formats'][0]['mimeType']
                response = outputs
            else:
                response['outputs'] = outputs
            return responseHeaders, 201, json.dumps(response)
        except Exception as err:
            exception = {
                'code': 'InvalidParameterValue',
                'description': str(err)
            }
            LOGGER.error(exception)
            return responseHeaders, 400, json.dumps(exception)


def check_format(args, requestHeaders):
    """
    check format requested from arguments or request headers

    FIXME: this does not handle quality values
    https://developer.mozilla.org/en-US/docs/Glossary/quality_values
    i.e. it ignores client's specifity and priority.

    :param args: dict of request keyword value pairs
    :param requestHeaders: request headers (immutable)

    :returns: format value
    """

    # Optional f=html or f=json query param
    # overrides accept
    format_ = args.get('f')
    if format_:
        return format_

    # Format not specified: get from accept headers
    acceptHeaders = requestHeaders.get('accept') or requestHeaders.get('Accept')

    if not acceptHeaders:
        return None

    format_ = None
    acceptHeaders = acceptHeaders.split(',')
    if 'text/html' in acceptHeaders:
        format_ = 'html'
    elif 'application/ld+json' in acceptHeaders:
        format_ = 'jsonld'
    elif 'application/json' in acceptHeaders:
        format_ = 'json'

    return format_
