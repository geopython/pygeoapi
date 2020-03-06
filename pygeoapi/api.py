# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2019 Tom Kralidis
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
import io
import logging
import multiprocessing
import os
import uuid
import urllib.parse
from copy import deepcopy

from dateutil.parser import parse as dateparse
import pytz

from pygeoapi import __version__
from pygeoapi.linked_data import (geojson2geojsonld, jsonldify,
                                  jsonldify_collection)
from pygeoapi.log import setup_logger
from pygeoapi.plugin import load_plugin, PLUGINS
from pygeoapi.provider.base import ProviderConnectionError, ProviderQueryError
from pygeoapi.util import (dategetter, json_serial, render_j2_template,
                           str2bool, JobStatus, TEMPLATES)

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
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson'
]

DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'

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

class API(object):
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

        # TODO: add as decorator
        if 'manager' in self.config['server']:
            self.manager = load_plugin('process_manager',
                                       self.config['server']['manager'])
            LOGGER.info('Process manager plugin loaded')
        else:
            LOGGER.info('No process manager defined')
            self.manager = None


    @pre_process
    @jsonldify
    def root(self, headers_, format_):
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
            return headers_, 400, json.dumps(exception)

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
            content = render_j2_template(self.config, 'root.html', fcm)
            return headers_, 200, content

        if format_ == 'jsonld':
            headers_['Content-Type'] = 'application/ld+json'
            return headers_, 200, json.dumps(self.fcmld)

        return headers_, 200, json.dumps(fcm)

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
            return headers_, 400, json.dumps(exception)

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

        return headers_, 200, json.dumps(openapi)

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
            return headers_, 400, json.dumps(exception)

        conformance = {
            'conformsTo': CONFORMANCE
        }

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
            content = render_j2_template(self.config, 'conformance.html',
                                         conformance)
            return headers_, 200, content

        return headers_, 200, json.dumps(conformance)

    @pre_process
    @jsonldify
    def describe_collections(self, headers_, format_, dataset=None):
        """
        Provide feature collection metadata

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

        fcm = {
            'collections': [],
            'links': []
        }

        if all([dataset is not None,
                dataset not in self.config['datasets'].keys()]):

            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid feature collection'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        LOGGER.debug('Creating collections')
        for k, v in self.config['datasets'].items():
            collection = {'links': []}
            collection['id'] = k
            collection['itemType'] = 'feature'
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
                'type': 'application/geo+json',
                'rel': 'items',
                'title': 'Features as GeoJSON',
                'href': '{}/collections/{}/items?f=json'.format(
                    self.config['server']['url'], k)
            })
            collection['links'].append({
                'type': 'application/ld+json',
                'rel': 'items',
                'title': 'Features as RDF (GeoJSON-LD)',
                'href': '{}/collections/{}/items?f=jsonld'.format(
                    self.config['server']['url'], k)
            })
            collection['links'].append({
                'type': 'text/html',
                'rel': 'items',
                'title': 'Features as HTML',
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

            headers_['Content-Type'] = 'text/html'
            if dataset is not None:
                content = render_j2_template(self.config, 'collection.html',
                                             fcm)
            else:
                content = render_j2_template(self.config, 'collections.html',
                                             fcm)

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
            return headers_, 200, json.dumps(jsonld)

        return headers_, 200, json.dumps(fcm, default=json_serial)

    def get_collection_items(self, headers, args, dataset, pathinfo=None):
        """
        Queries feature collection

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param dataset: dataset name
        :param pathinfo: path location

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        properties = []
        reserved_fieldnames = ['bbox', 'f', 'limit', 'startindex',
                               'resulttype', 'datetime', 'sortby']
        formats = FORMATS
        formats.extend(f.lower() for f in PLUGINS['formatter'].keys())

        if dataset not in self.config['datasets'].keys():
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid feature collection'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception, default=json_serial)

        format_ = check_format(args, headers)

        if format_ is not None and format_ not in formats:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

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
                return headers_, 400, json.dumps(exception)
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
            return headers_, 400, json.dumps(exception)

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
                return headers_, 400, json.dumps(exception)
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
            return headers_, 400, json.dumps(exception)

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
                return headers_, 400, json.dumps(exception)
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
            return headers_, 400, json.dumps(exception)

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
                'temporal' in self.config['datasets'][dataset]['extents']):
            te = self.config['datasets'][dataset]['extents']['temporal']

            if te['begin'].tzinfo is None:
                te['begin'] = te['begin'].replace(tzinfo=pytz.UTC)
            if te['end'].tzinfo is None:
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
            return headers_, 400, json.dumps(exception)

        LOGGER.debug('Loading provider')
        try:
            p = load_plugin('provider',
                            self.config['datasets'][dataset]['provider'])
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, json.dumps(exception)
        except ProviderQueryError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, json.dumps(exception)

        LOGGER.debug('processing property parameters')
        for k, v in args.items():
            if k not in reserved_fieldnames and k not in p.fields.keys():
                exception = {
                    'code': 'InvalidParameterValue',
                    'description': 'unknown query parameter'
                }
                LOGGER.error(exception)
                return headers_, 400, json.dumps(exception)
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
                        return headers_, 400, json.dumps(exception)
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
                    return headers_, 400, json.dumps(exception)
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
        except ProviderConnectionError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'connection error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, json.dumps(exception)
        except ProviderQueryError:
            exception = {
                'code': 'NoApplicableCode',
                'description': 'query error (check logs)'
            }
            LOGGER.error(exception)
            return headers_, 500, json.dumps(exception)

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
                'title': self.config['datasets'][dataset]['title'],
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

            content = render_j2_template(self.config, 'items.html',
                                         content)
            return headers_, 200, content
        elif format_ == 'csv':  # render
            formatter = load_plugin('formatter', {'name': 'CSV', 'geom': True})

            content = formatter.write(
                data=content,
                options={
                    'provider_def':
                        self.config['datasets'][dataset]['provider']
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

        return headers_, 200, json.dumps(content, default=json_serial)

    @pre_process
    def get_collection_item(self, headers_, format_, dataset, identifier):
        """
        Get a single feature

        :param headers_: copy of HEADERS object
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param dataset: dataset name
        :param identifier: feature identifier

        :returns: tuple of headers, status code, content
        """

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        LOGGER.debug('Processing query parameters')

        if dataset not in self.config['datasets'].keys():
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid feature collection'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        LOGGER.debug('Loading provider')
        p = load_plugin('provider',
                        self.config['datasets'][dataset]['provider'])

        LOGGER.debug('Fetching id {}'.format(identifier))
        content = p.get(identifier)

        if content is None:
            exception = {
                'code': 'NotFound',
                'description': 'identifier not found'
            }
            LOGGER.error(exception)
            return headers_, 404, json.dumps(exception)

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
            'title': self.config['datasets'][dataset]['title'],
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

            content['title'] = self.config['datasets'][dataset]['title']
            content = render_j2_template(self.config, 'item.html',
                                         content)
            return headers_, 200, content
        elif format_ == 'jsonld':
            headers_['Content-Type'] = 'application/ld+json'
            content = geojson2geojsonld(
                self.config, content, dataset, identifier=identifier
            )
            return headers_, 200, content

        return headers_, 200, json.dumps(content, default=json_serial)

    @pre_process
    @jsonldify
    def describe_processes(self, headers_, format_, process=None):
        """
        Provide processes metadata

        :param headers: dict of HTTP headers
        :param format_: format of requests,
                        pre checked by pre_process decorator
        :param process: name of process, defaults to None to obtain
            information about all processes

        :returns: tuple of headers, status code, content
        """

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        processes_config = self.config.get('processes', {})

        if process and not processes_config.get(process, None):
            exception = {
                'code': 'NoSuchProcess',
                'description': 'identifier not found'
            }
            return headers_, 404, json.dumps(exception)

        process_jobs_link = lambda process_id: dict({
            'type': 'text/html',
            'rel': 'collection',
            'href': '{}/processes/{}/jobs'.format(self.config['server']['url'], process_id),
            'title': 'Collection of jobs for the {} process'.format(process_id),
            'hreflang': self.config['server'].get('language', None)
        })


        if processes_config:
            process_ids = processes_config.keys() if not process else [p for p in processes_config.keys() if p == process]
            processes = list(map(lambda process_id: load_plugin('process', processes_config[process_id]['processor']), process_ids))
            output = []
            for _process in processes:
                process_id = _process.metadata['id']
                if process is not None and process != process_id:
                    continue
                metadata = deepcopy(_process.metadata)
                metadata['itemType'] = ['process']
                metadata['jobControlOptions'] = ['sync-execute']
                metadata['outputTransmission'] = ['value']
                metadata['links'] = metadata.get('links', list())
                metadata['links'].append(process_jobs_link(process_id))
                output.append(metadata)

            response = output[0] if process is not None else {
                'processes': output
            }
        else:
            response = {'processes': []}

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
            if process is not None:
                response = render_j2_template(self.config, 'process.html',
                                              response)
            else:
                response = render_j2_template(self.config, 'processes.html',
                                              response)

            return headers_, 200, response

        return headers_, 200, json.dumps(response)

    def execute_process(self, method, headers, args, data, process_id):
        """
        Execute process

        :param method: HTTP method (GET/POST)
        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param data: process data
        :param process_id: id of process

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        format_ = check_format(args, headers_)

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        response = {}

        processes_config = self.config.get('processes', {})
        if process_id not in processes_config:
            exception = {
                'code': 'NoSuchProcess',
                'description': 'identifier not found'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)

        process = load_plugin('process', processes_config.get(process_id, {}).get('processor'))

        if method == 'GET' and process_id:
            jobs = sorted(self.manager.get_jobs(process_id), key=lambda k: k['process_start_datetime'], reverse=True)
            if not format_ or format_ == 'html':
                headers_['Content-Type'] = 'text/html'
                response = render_j2_template(self.config, 'jobs.html', {'process': {'id': process_id, 'title': process.metadata['title']}, 'jobs': jobs})
                return headers_, 200, response
            response = [job['identifier'] for job in jobs]
            return headers_, 200, json.dumps(response)

        elif method == 'POST' and not data:
            # TODO not all processes require input, e.g. time-depenendent or
            # random value generators
            exception = {
                'code': 'MissingParameterValue',
                'description': 'missing request data'
            }
            LOGGER.info(exception)
            return headers_, 400, json.dumps(exception)

        if not self.manager:
            raise Exception('No manager, no execution!')

        try:
            data = json.loads(data)
        except (json.decoder.JSONDecodeError, TypeError) as e:
            # Input does not appear to be valid JSON
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'invalid request data'
            }
            LOGGER.info(exception)
            return headers_, 400, json.dumps(exception)

        try:
            data_dict = {_input['id']: _input['value'] for _input in data.get('inputs', [])}
        except KeyError:
            # Return 4XX client error for missing 'id' or 'value' in an input
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'invalid request data'
            }
            LOGGER.info(exception)
            return headers_, 400, json.dumps(exception)

        job_id = str(uuid.uuid1())
        url = '{}/processes/{}/jobs/{}'.format(
            self.config['server']['url'], process_id, job_id)
        headers_['Location'] = url

        if 'sync-execute' in args and args['sync-execute'] == 'false':
            LOGGER.debug('asynchronous execution specified')
            _process = multiprocessing.Process(
                target=self._execute_handler,
                args=(process, job_id, data_dict, True))
            _process.start()
            return headers_, 201, ''
        else:
            LOGGER.debug('synchronous execution')
            outputs, status = self._execute_handler(process, job_id, data_dict)

        if status == JobStatus.failed:
            response = outputs

        if 'raw' in args and str2bool(args['raw']):
            headers_['Content-Type'] = \
                process.metadata['outputs'][0]['output']['formats'][0]['mimeType']
            response = outputs
        elif status != JobStatus.failed:
            response['outputs'] = outputs

        return headers_, 201, json.dumps(response)

    def retrieve_job_status(self, headers, args, data, process_id, job_id):
        """
        Get status of job (instance of a process)

        :param method: HTTP method (GET)
        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param data: process data
        :param process_id: name of process
        :param job_id: ID of job

        :returns: tuple of headers, status code, content
        """
        headers_ = HEADERS.copy()
        process = self.config.get('processes', {}).get(process_id, None)

        if not process:
            exception = {
                'code': 'NoSuchProcess',
                'description': 'identifier not found'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)

        job_result = self.manager.get_job_result(process_id, job_id)
        if not job_result:
            exception = {
                'code': 'NoSuchJob',
                'description': 'job not found'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)
        status = JobStatus[job_result['status']]
        response = {
            'jobID': job_id,
            'status': status.value,
            'message': job_result.get('message', None),
            'progress': 100 if status == JobStatus.finished else 0, # TODO actual progress value
            'links': [{
                'href': '{}/processes/{}/jobs/{}'.format(
                    self.config['server']['url'], process_id, job_id
                ),
                'rel': 'self',
                'type': 'application/json',
                'title': 'Status of {} job {}'.format(process_id, job_id)
            }]
        }
        if status in (JobStatus.successful, JobStatus.running, JobStatus.accepted):
            # TODO link also if accepted/running?
            response['links'].append({
                'href': '{}/processes/{}/jobs/{}/results'.format(
                    self.config['server']['url'], process_id, job_id
                ),
                'rel': 'about',
                'type': 'application/json',
                'title': 'Results of {} job {}'.format(process_id, job_id)
            })
        elif status == JobStatus.failed:
            # TODO link to exception report?
            pass
        return headers_, 200, json.dumps(response)

    def retrieve_job_result(self, method, headers, args, data, process_id, job_id):
        """
        Get result of job (instance of a process)

        :param method: HTTP method (GET)
        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param data: process data
        :param process_id: name of process
        :param job_id: ID of job

        :returns: tuple of headers, status code, content
        """
        headers_ = HEADERS.copy()
        # process = self.config.get('processes', {}).get(process_id, None)
        processes_config = self.config.get('processes', {})
        if process_id not in processes_config:
            exception = {
                'code': 'NoSuchProcess',
                'description': 'identifier not found'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)

        process = load_plugin('process', processes_config.get(process_id, {}).get('processor'))

        if not process:
            exception = {
                'code': 'NoSuchProcess',
                'description': 'identifier not found'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)

        job_result = self.manager.get_job_result(process_id, job_id)
        if not job_result:
            exception = {
                'code': 'NoSuchJob',
                'description': 'job not found'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)
        status = JobStatus[job_result['status']]
        if status == JobStatus.running:
            exception = {
                'code': 'JobNotReady',
                'description': 'job still running'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)
        elif status == JobStatus.accepted:
            # NOTE: this case is not mentioned in the specification
            exception = {
                'code': 'JobNotReady',
                'description': 'job accepted but not yet running'
            }
            LOGGER.info(exception)
            return headers_, 404, json.dumps(exception)
        elif status == JobStatus.failed:
            code = 'InvalidParameterValue' # TODO this must correspond to actual failure reason
            http_status = 400 # TODO this must correspond to actual failure reason
            exception = {
                'code': code,
                'description': 'job failed'
            }
            LOGGER.info(exception)
            return headers_, http_status, json.dumps(exception)
        location = job_result['location']
        with io.open(location, 'r') as fh:
            result = json.load(fh)

        format_ = check_format(args, headers_)

        if not format_ or format_ == 'html':
            headers_['Content-Type'] = 'text/html'
            response = render_j2_template(self.config, 'jobresult.html', {
                'process': {'id': process_id, 'title': process.metadata['title']},
                'job': {'id': job_id},
                'result': result
            })
            return headers_, 200, response
        return headers_, 200, json.dumps(result)

    def _execute_handler(self, p, job_id, data_dict, async_=False):
        """
        Process execution handler

        :param p: `pygeoapi.process` object
        :param job_id: job identifier
        :param data_dict: `dict` of data parameters
        :param async_: `bool` whether to return or dispatch results

        :returns: tuple of response payload and status, or None if `async` is `True`
        """

        process_start_datetime = datetime.utcnow().strftime(DATETIME_FORMAT)

        filename = '{}-{}'.format(p.metadata['id'], job_id)
        job_filename = os.path.join(self.manager.output_dir, filename) # TODO FIXME

        current_status = JobStatus.accepted
        job_metadata = {
            'identifier': job_id,
            'processid': p.metadata['id'],
            'process_start_datetime': process_start_datetime,
            'process_end_datetime': None,
            'status': current_status.value,
            'location': None,
            'message': 'Process accepted'
        }
        self.manager.add_job(job_metadata)

        try:
            current_status = JobStatus.running
            outputs = p.execute(data_dict)
            self.manager.update_job(job_id, {
                'status': current_status.value,
                'message': 'Process running'
            })

            with io.open(job_filename, 'w') as fh:
                fh.write(json.dumps(outputs))

            current_status = JobStatus.finished
            job_update_metadata = {
                'process_end_datetime': datetime.utcnow().strftime(DATETIME_FORMAT),
                'status': current_status.value,
                'location': job_filename,
                'message': 'Process complete'
            }

            self.manager.update_job(job_id, job_update_metadata)

        except Exception as err:
            # TODO assess correct exception type and description to help users
            # NOTE, the /results endpoint should return the error HTTP status
            # for jobs that failed, ths specification says that failing jobs
            # must still be able to be retrieved with their error message
            # intact, and the correct HTTP error status at the /results
            # endpoint, even if the /result endpoint correctly returns the
            # failure information (i.e. what one might assume is a 200
            # response).
            current_status = JobStatus.failed
            code = 'InvalidParameterValue'
            status_code = 400
            outputs = {
                'code': code,
                'description': str(err) # NOTE this is optional and internal exceptions aren't useful for (or safe to show) end-users
            }
            LOGGER.error(outputs)
            job_metadata = {
                'process_end_datetime': datetime.utcnow().strftime(DATETIME_FORMAT),
                'status': current_status.value,
                'location': None,
                'message': code
            }

            self.manager.update_job(job_id, job_metadata)

        if not async_:
            return outputs, current_status
        return


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
