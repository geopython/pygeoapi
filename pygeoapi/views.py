# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Norman Barker <norman.barker@gmail.com>
#
# Copyright (c) 2018 Tom Kralidis
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

from pygeoapi.config import settings
from pygeoapi.provider import load_provider

LOGGER = logging.getLogger(__name__)

TEMPLATES = '{}{}templates'.format(os.path.dirname(
    os.path.realpath(__file__)), os.sep)


def root(headers, args, baseurl):
    """
    Provide API

    :param headers: dict of HTTP headers
    :param args: dict of HTTP request parameters
    :param baseurl: baseurl of the server

    :returns: tuple of headers, status code, content
    """

    headers_ = {
        'Content-type': 'application/json'
    }

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
          'href': baseurl
        }, {
          'rel': 'self',
          'type': 'text/html',
          'title': 'this document as HTML',
          'href': '{}?f=html'.format(baseurl)
        }, {
          'rel': 'self',
          'type': 'application/openapi+json;version=3.0',
          'title': 'the OpenAPI definition as JSON',
          'href': '{}api'.format(baseurl)
        }, {
          'rel': 'self',
          'type': 'text/html',
          'title': 'the OpenAPI definition as HTML',
          'href': '{}?f=html'.format(baseurl)
        }
    ]

    if format_ == 'html':  # render
        headers_['Content-type'] = 'text/html'
        content = _render_j2_template(settings, 'service.html', fcm)

        return headers_, 200, content

    return headers_, 200, json.dumps(fcm)


def api(headers, args, openapi):
    """
    Provide OpenAPI document

    :param headers: dict of HTTP headers
    :param args: dict of HTTP request parameters
    :param openapi: dict of OpenAPI definition

    :returns: tuple of headers, status code, content
    """

    headers_ = {
        'Content-type': 'application/json'
    }

    return headers_, 200, json.dumps(openapi)


def api_conformance(headers, args):
    """
    Provide conformance definition

    :param headers: dict of HTTP headers
    :param args: dict of HTTP request parameters

    :returns: tuple of headers, status code, content
    """

    headers_ = {
        'Content-type': 'application/json'
    }

    conformance = {
        'conformsTo': [
            'http://www.opengis.net/spec/wfs-1/3.0/req/core',
            'http://www.opengis.net/spec/wfs-1/3.0/req/oas30',
            'http://www.opengis.net/spec/wfs-1/3.0/req/html',
            'http://www.opengis.net/spec/wfs-1/3.0/req/geojson'
        ]
    }

    return headers_, 200, json.dumps(conformance)


def describe_collections(headers, args, dataset=None):
    """
    Provide feature collection metadata

    :param headers: dict of HTTP headers
    :param args: dict of HTTP request parameters

    :returns: tuple of headers, status code, content
    """

    headers_ = {
        'Content-type': 'application/json'
    }

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

    if dataset is not None and dataset not in settings['datasets'].keys():
        exception = {
            'code': 'InvalidParameterValue',
            'description': 'Invalid feature collection'
        }
        LOGGER.error(exception)
        return headers_, 400, json.dumps(exception)

    LOGGER.debug('Creating collections')
    for k, v in settings['datasets'].items():
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
                'rel': 'alternate',
                'type': link['type'],
                'href': link['url']
            }
            collection['links'].append(lnk)

        if dataset is not None and k == dataset:
            return headers_, 200, json.dumps(collection)

        fcm['collections'].append(collection)

    if format_ == 'html':  # render
        headers_['Content-type'] = 'text/html'
        content = _render_j2_template(settings, 'service.html', fcm)

        return headers_, 200, content

    return headers_, 200, json.dumps(fcm)


def get_features(headers, args, dataset):
    """
    Queries feature collection

    :param headers: dict of HTTP headers
    :param args: dict of HTTP request parameters
    :param dataset: dataset name

    :returns: tuple of headers, status code, content
    """

    headers_ = {
        'Content-type': 'application/json'
    }

    startindex = args.get('startindex') or 0
    limit = args.get('limit') or settings['server']['limit']
    resulttype = args.get('resulttype') or 'results'

    if dataset not in settings['datasets'].keys():
        exception = {
            'code': 'InvalidParameterValue',
            'description': 'Invalid feature collection'
        }
        LOGGER.error(exception)
        return headers_, 400, json.dumps(exception)

    LOGGER.debug('Loading provider')
    p = load_provider(settings['datasets'][dataset]['provider'])
    LOGGER.debug('Querying provider')
    LOGGER.debug('startindex: {}'.format(startindex))
    LOGGER.debug('limit: {}'.format(limit))
    LOGGER.debug('resulttype: {}'.format(resulttype))
    content = p.query(startindex=int(startindex), limit=int(limit),
                      resulttype=resulttype)

    next_ = startindex + settings['server']['limit']

    content['links'] = [{
        'rel': 'self',
        'type': 'application/json',
        'href': '/collections/{}/items'.format(dataset)
        }, {
        'rel': 'next',
        'type': 'application/json',
        'href': '/collections/{}/items/?startindex={}'.format(dataset, next_)
        }, {
        'rel': 'collection',
        'type': 'application/json',
        'href': '/collections/{}'.format(dataset)
        }
    ]

    content['timeStamp'] = datetime.utcnow().isoformat()

    return headers_, 200, json.dumps(content)


def get_feature(headers, args, dataset, identifier):
    """
    Get a single feature

    :param headers: dict of HTTP headers
    :param args: dict of HTTP request parameters
    :param dataset: dataset name
    :param identifier: feature identifier

    :returns: tuple of headers, status code, content
    """

    headers_ = {
        'Content-type': 'application/json'
    }

    if dataset not in settings['datasets'].keys():
        exception = {
            'code': 'InvalidParameterValue',
            'description': 'Invalid feature collection'
        }
        LOGGER.error(exception)
        return headers_, 400, json.dumps(exception)

    LOGGER.debug('Loading provider')
    p = load_provider(settings['datasets'][dataset]['provider'])

    LOGGER.debug('Fetching id {}'.format(identifier))
    content = p.get(identifier)

    content['links'] = [{
        'rel': 'self',
        'type': 'application/json',
        'href': '/collections/{}/items/{}'.format(dataset, identifier)
        }, {
        'rel': 'collection',
        'type': 'application/json',
        'href': '/collections/{}'.format(dataset)
        }
    ]

    if content is None:
        exception = {
            'code': 'NotFound',
            'description': 'identifier not found'
        }
        LOGGER.error(exception)
        return headers_, 404, json.dumps(exception)

    return headers_, 200, json.dumps(content)


def _render_j2_template(config, template, data):
    """
    render Jinja2 template

    :param config: dict of configuration
    :param template: template (relative path)
    :param data: dict of data

    :returns: string of rendered template
    """

    env = Environment(loader=FileSystemLoader(TEMPLATES))
    template = env.get_template(template)
    return template.render(config=config, data=data)
