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

LOGGER = logging.getLogger(__name__)

TEMPLATES = '{}{}templates'.format(os.path.dirname(
    os.path.realpath(__file__)), os.sep)

HEADERS = {
    'Content-Type': 'application/json',
    'X-Powered-By': 'pygeoapi {}'.format(__version__)
}


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

    def root(self, headers, args):
        """
        Provide API

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        formats = ['json', 'html']

        format_ = args.get('f')
        if format_ is not None and format_ not in formats:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        fcm = {
            'links': [],
        }

        LOGGER.debug('Creating links')
        fcm['links'] = [{
              'rel': 'self',
              'type': 'application/json',
              'title': 'this document',
              'href': self.config['server']['url']
            }, {
              'rel': 'self',
              'type': 'text/html',
              'title': 'this document as HTML',
              'href': '{}/?f=html'.format(self.config['server']['url']),
              'hreflang': self.config['server']['language']
            }, {
              'rel': 'self',
              'type': 'application/openapi+json;version=3.0',
              'title': 'the OpenAPI definition as JSON',
              'href': '{}/api'.format(self.config['server']['url'])
            }, {
              'rel': 'self',
              'type': 'text/html',
              'title': 'the OpenAPI definition as HTML',
              'href': '{}/api?f=html'.format(self.config['server']['url']),
              'hreflang': self.config['server']['language']
            }
        ]

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
            content = _render_j2_template(self.config, 'root.html', fcm)
            return headers_, 200, content

        return headers_, 200, json.dumps(fcm)

    def api(self, headers, args, openapi):
        """
        Provide OpenAPI document

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param openapi: dict of OpenAPI definition

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()
        headers_['Content-Type'] = 'application/openapi+json;version=3.0'

        return headers_, 200, json.dumps(openapi)

    def api_conformance(self, headers, args):
        """
        Provide conformance definition

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        formats = ['json', 'html']

        format_ = args.get('f')
        if format_ is not None and format_ not in formats:
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

    def describe_processes(self, headers, args, process=None):
        """
        Provide processes metadata

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param process: name of process

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        processes_config = self.config['processes']
        processes = {}

        if process is not None:
            if process not in processes_config.keys():
                exception = {
                    'code': 'NotFound',
                    'description': 'identifier not found'
                }
                LOGGER.error(exception)
                return headers_, 404, json.dumps(exception)

            p = load_plugin('process', processes_config[process]['processor'])
            processes[process] = p.metadata
        else:
            for k, v in processes_config.items():
                p = load_plugin('process', processes_config[k]['processor'])
                processes[k] = p.metadata

        response = {
            'processes': processes
        }

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

        response = p.execute(data)

        return headers_, 201, json.dumps(response)

    def describe_collections(self, headers, args, dataset=None):
        """
        Provide feature collection metadata

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param dataset: name of collection

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        formats = ['json', 'html']

        format_ = args.get('f')
        if format_ is not None and format_ not in formats:
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid format'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        fcm = {
            'collections': []
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

            if dataset is not None and k == dataset:
                fcm = collection
                break

            fcm['collections'].append(collection)

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
            if dataset is not None:
                content = _render_j2_template(self.config, 'collection.html',
                                              fcm)
            else:
                content = _render_j2_template(self.config, 'collections.html',
                                              fcm)

            return headers_, 200, content

        return headers_, 200, json.dumps(fcm)

    def get_features(self, headers, args, dataset):
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
        formats = ['json', 'html']
        formats.extend(f.lower() for f in PLUGINS['formatter'].keys())

        if dataset not in self.config['datasets'].keys():
            exception = {
                'code': 'InvalidParameterValue',
                'description': 'Invalid feature collection'
            }
            LOGGER.error(exception)
            return headers_, 400, json.dumps(exception)

        format_ = args.get('f')
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
            'type': 'application/json',
            'rel': 'self',
            'title': 'Collection items',
            'href': '{}collections/{}/items'.format(
                self.config['server']['url'], dataset)
            }, {
            'type': 'application/json',
            'rel': 'prev',
            'title': 'items (prev)',
            'href': '{}/collections/{}/items/?startindex={}'.format(
                self.config['server']['url'], dataset, prev)
            }, {
            'type': 'application/json',
            'rel': 'next',
            'title': 'items (next)',
            'href': '{}/collections/{}/items/?startindex={}'.format(
                self.config['server']['url'], dataset, next_)
            }, {
            'type': 'application/json',
            'title': 'Collection',
            'rel': 'collection',
            'href': '{}/collections/{}'.format(
                self.config['server']['url'], dataset)
            }
        ]

        content['timeStamp'] = datetime.utcnow().isoformat()

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
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

    def get_feature(self, headers, args, dataset, identifier):
        """
        Get a single feature

        :param headers: dict of HTTP headers
        :param args: dict of HTTP request parameters
        :param dataset: dataset name
        :param identifier: feature identifier

        :returns: tuple of headers, status code, content
        """

        headers_ = HEADERS.copy()

        formats = ['json', 'html']

        format_ = args.get('f')
        if format_ is not None and format_ not in formats:
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
            'type': 'application/json',
            'href': '{}/collections/{}/items/{}'.format(
                self.config['server']['url'], dataset, identifier)
            }, {
            'rel': 'collection',
            'type': 'application/json',
            'href': '{}/collections/{}'.format(
                self.config['server']['url'], dataset)
            }
        ]

        if format_ == 'html':  # render
            headers_['Content-Type'] = 'text/html'
            content = _render_j2_template(self.config, 'item.html',
                                          content)
            return headers_, 200, content

        return headers_, 200, json.dumps(content)


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
