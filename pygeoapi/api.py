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

from datetime import datetime
import json
import logging
import os

from jinja2 import Environment, FileSystemLoader

from pygeoapi import __version__
from pygeoapi.log import setup_logger
from pygeoapi.plugin import load_plugin, PLUGINS
from pygeoapi.provider.base import ProviderConnectionError, ProviderQueryError
from pygeoapi.util import str2bool

LOGGER = logging.getLogger(__name__)

TEMPLATES = '{}{}templates'.format(os.path.dirname(
    os.path.realpath(__file__)), os.sep)

HEADERS = {
    'Content-Type': 'application/json',
    'X-Powered-By': 'pygeoapi {}'.format(__version__)
}

FORMATS = ['json', 'html']


def pre_process(func):
    """
        Decorator performing header copy and format\
        checking before sending arguments to mehods

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

    @pre_process
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
              'rel': 'self',
              'type': 'application/json',
              'title': 'This document as JSON',
              'href': self.config['server']['url']
            }, {
              'rel': 'self',
              'type': 'text/html',
              'title': 'This document as HTML',
              'href': '{}/?f=html'.format(self.config['server']['url']),
              'hreflang': self.config['server']['language']
            }, {
              'rel': 'service',
              'type': 'application/openapi+json;version=3.0',
              'title': 'The OpenAPI definition as JSON',
              'href': '{}/api'.format(self.config['server']['url'])
            }, {
              'rel': 'self',
              'type': 'text/html',
              'title': 'The OpenAPI definition as HTML',
              'href': '{}/api?f=html'.format(self.config['server']['url']),
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
            for link in fcm['links']:
                if 'json' in link['type']:
                    link['href'] = ''.join((link['href'], '?f=json'))

            headers_['Content-Type'] = 'text/html'
            content = _render_j2_template(self.config, 'root.html', fcm)
            return headers_, 200, content

        return headers_, 200, json.dumps(fcm)

    @pre_process
    def api(self, headers_, format_, openapi):
        """
        Provide OpenAPI document


        :param headers_: copy of HEADERS object
        :param format_: format of requests, pre checked by
                        pre_process decorator
        :param openapi: dict of OpenAPI definition

        :returns: tuple of headers, status code, content
        """

        path = '/'.join([self.config['server']['url'].rstrip('/'), 'api'])

        if format_ == 'html':
            data = {
                'openapi-document-path': path
            }
            headers_['Content-Type'] = 'text/html'
            content = _render_j2_template(self.config, 'api.html', data)
            return headers_, 200, content

        headers_['Content-Type'] = 'application/openapi+json;version=3.0'

        return headers_, 200, json.dumps(openapi)

    @pre_process
    def api_conformance(self,  headers_, format_):
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
            'conformsTo': [
                'http://www.opengis.net/spec/wfs-1/3.0/req/core',
                'http://www.opengis.net/spec/wfs-1/3.0/req/oas30',
                'http://www.opengis.net/spec/wfs-1/3.0/req/html',
                'http://www.opengis.net/spec/wfs-1/3.0/req/geojson'
            ]
        }

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
            content = _render_j2_template(self.config, 'conformance.html',
                                          conformance)
            return headers_, 200, content

        return headers_, 200, json.dumps(conformance)

    @pre_process
    def describe_collections(self,  headers_, format_, dataset=None):
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
            collection = {'links': [], 'crs': []}
            collection['name'] = k
            collection['title'] = v['title']
            collection['description'] = v['description']
            collection['keywords'] = v['keywords'];
            for crs in v['crs']:
                collection['crs'].append(
                    'http://www.opengis.net/def/crs/OGC/1.3/{}'.format(crs))
            collection['extent'] = v['extents']['spatial']['bbox']

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
                'rel': 'item',
                'title': 'Features as GeoJSON',
                'href': '{}/collections/{}/items?f=json'.format(
                    self.config['server']['url'], k)
            })
            collection['links'].append({
                'type': 'text/html',
                'rel': 'item',
                'title': 'Features as HTML',
                'href': '{}/collections/{}/items?f=html'.format(
                    self.config['server']['url'], k)
            })
            collection['links'].append({
                'type': 'application/json',
                'rel': 'self',
                'title': 'This document as JSON',
                'href': '{}/collections/{}?f=json'.format(
                    self.config['server']['url'], k)
            })
            collection['links'].append({
                'type': 'text/html',
                'rel': 'alternate',
                'title': 'This document as HTML',
                'href': '{}/collections/{}?f=html'.format(
                    self.config['server']['url'], k)
            })

            if dataset is not None and k == dataset:
                fcm = collection
                break

            fcm['collections'].append(collection)

        fcm['links'].append({
            'type': 'application/json',
            'rel': 'self',
            'title': 'This document as JSON',
            'href': '{}/collections?f=json'.format(
                self.config['server']['url'])
        })
        fcm['links'].append({
            'type': 'text/html',
            'rel': 'alternate',
            'title': 'This document as HTML',
            'href': '{}/collections?f=html'.format(
                self.config['server']['url'])
        })

        if format_ == 'html':  # render
            fcm['links'][0]['rel'] = 'alternate'
            fcm['links'][1]['rel'] = 'self'

            headers_['Content-Type'] = 'text/html'
            if dataset is not None:
                content = _render_j2_template(self.config, 'collection.html',
                                              fcm)
            else:
                content = _render_j2_template(self.config, 'collections.html',
                                              fcm)

            return headers_, 200, content

        return headers_, 200, json.dumps(fcm)

    def get_features(self, headers,  args, dataset):
        """
        Queries feature collection

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        properties = []
        reserved_fieldnames = ['bbox', 'f', 'limit', 'startindex',
                               'resulttype', 'time']
        formats = FORMATS
        formats.extend(f.lower() for f in PLUGINS['formatter'].keys())

        if dataset not in self.config['datasets'].keys():
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid feature collection'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        format_ = check_format(args, headers)

        if format_ is not None and format_ not in formats:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        LOGGER.debug('Processing query parameters')
        try:
            startindex = int(args.get('startindex'))
        except TypeError:
            startindex = 0
        try:
            limit = int(args.get('limit'))
        except TypeError:
            limit = self.config['server']['limit']

        resulttype = args.get('resulttype') or 'results'

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

        time = args.get('time')

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
            if k not in reserved_fieldnames and k in p.fields.keys():
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
            content = p.query(startindex=int(startindex), limit=int(limit),
                              resulttype=resulttype, bbox=bbox, time=time,
                              properties=properties, sortby=sortby)
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

        prev = startindex - self.config['server']['limit']
        if prev < 0:
            prev = 0

        next_ = startindex + self.config['server']['limit']

        content['links'] = [{
            'type': 'application/geo+json',
            'rel': 'self',
            'title': 'This document as GeoJSON',
            'href': '{}/collections/{}/items?f=json'.format(
                self.config['server']['url'], dataset)
            }, {
            'type': 'text/html',
            'rel': 'alternate',
            'title': 'This document as HTML',
            'href': '{}/collections/{}/items?f=html'.format(
                self.config['server']['url'], dataset)
            }, {
            'type': 'application/geo+json',
            'rel': 'prev',
            'title': 'items (prev)',
            'href': '{}/collections/{}/items/?startindex={}'.format(
                self.config['server']['url'], dataset, prev)
            }, {
            'type': 'application/geo+json',
            'rel': 'next',
            'title': 'items (next)',
            'href': '{}/collections/{}/items/?startindex={}'.format(
                self.config['server']['url'], dataset, next_)
            }, {
            'type': 'application/json',
            'title': self.config['datasets'][dataset]['title'],
            'rel': 'collection',
            'href': '{}/collections/{}'.format(
                self.config['server']['url'], dataset)
            }
        ]

        content['timeStamp'] = datetime.utcnow().strftime(
            '%Y-%m-%dT%H:%M:%S.%fZ')

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'

            content['links'][0]['rel'] = 'alternate'
            content['links'][1]['rel'] = 'self'

            # For constructing proper URIs to items
            path_info = '/'.join([
                self.config['server']['url'].rstrip('/'),
                headers.environ['PATH_INFO'].strip('/')])

            content['items_path'] = path_info
            content['dataset_path'] = '/'.join(path_info.split('/')[:-1])
            content['collections_path'] = '/'.join(path_info.split('/')[:-2])
            content['startindex'] = startindex

            content = _render_j2_template(self.config, 'items.html',
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

        return headers_, 200, json.dumps(content)

    @pre_process
    def get_feature(self, headers_, format_, dataset, identifier):
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
            'rel': 'self',
            'type': 'application/geo+json',
            'title': 'This document as GeoJSON',
            'href': '{}/collections/{}/items/{}?f=json'.format(
                self.config['server']['url'], dataset, identifier)
            }, {
            'rel': 'alternate',
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

            content['links'][0]['rel'] = 'alternate'
            content['links'][1]['rel'] = 'self'

            content = _render_j2_template(self.config, 'item.html',
                                          content)
            return headers_, 200, content

        return headers_, 200, json.dumps(content)

    @pre_process
    def describe_processes(self, headers_, format_, process=None):
        """
        Provide processes metadata

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param process: name of process

        :returns: tuple of headers, status code, content
        """

        if format_ is not None and format_ not in FORMATS:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        processes_config = self.config['processes']

        if process is not None:
            if process not in processes_config.keys():
                exception = {
                    'code': 'NotFound',
                    'description': 'identifier not found'
                }
                LOGGER.error(exception)
                return headers_, 404, json.dumps(exception)

            p = load_plugin('process', processes_config[process]['processor'])
            p.metadata['jobControlOptions'] = ['sync-execute']
            p.metadata['outputTransmission'] = ['value']
            response = p.metadata
        else:
            processes = []
            for k, v in processes_config.items():
                p = load_plugin('process', processes_config[k]['processor'])
                p.metadata['jobControlOptions'] = ['sync-execute']
                p.metadata['outputTransmission'] = ['value']
                processes.append(p.metadata)
            response = {
                'processes': processes
            }

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
            if process is not None:
                response = _render_j2_template(self.config, 'process.html',
                                               p.metadata)
            else:
                response = _render_j2_template(self.config, 'processes.html',
                                               {'processes': processes})

            return headers_, 200, response

        return headers_, 200, json.dumps(response)

    def execute_process(self, headers, args, data, process):
        """
        Execute process

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param data: process data
        :param process: name of process

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        data_dict = {}
        response = {}

        if not data:
            exception = {
                'code': 'MissingParameterValue',
                'description': 'missing request data'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        if process not in self.config['processes'].keys():
            exception = {
                'code': 'NotFound',
                'description': 'identifier not found'
            }
            LOGGER.error(exception)
            return headers_, 404, json.dumps(exception)

        p = load_plugin('process',
                        self.config['processes'][process]['processor'])

        data_ = json.loads(data)
        for input_ in data_['inputs']:
            data_dict[input_['id']] = input_['value']

        try:
            outputs = p.execute(data_dict)
            m = p.metadata
            if 'raw' in args and str2bool(args['raw']):
                headers_['Content-Type'] = \
                    m['outputs'][0]['output']['formats'][0]['mimeType']
                response = outputs
            else:
                response['outputs'] = outputs
            return headers_, 201, json.dumps(response)
        except Exception as err:
            exception = {
                'code': 'InvalidParameterValue',
                'description': str(err)
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)


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
        elif 'application/json' in headers_:
            format_ = 'json'

    return format_


def to_json(dict_):
    """
    serialize dict to json

    :param dict_: dict_

    :returns: JSON string representation
    """

    return json.dumps(dict_)


def _render_j2_template(config, template, data):
    """
    render Jinja2 template

    :param config: dict of configuration
    :param template: template (relative path)
    :param data: dict of data

    :returns: string of rendered template
    """

    env = Environment(loader=FileSystemLoader(TEMPLATES))
    env.filters['to_json'] = to_json
    env.globals.update(to_json=to_json)

    template = env.get_template(template)
    return template.render(config=config, data=data, version=__version__)
