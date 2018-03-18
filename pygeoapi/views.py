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

import logging

from flask import request
# from flask import request, url_for

from pygeoapi.config import settings
from pygeoapi.provider import load_provider

LOGGER = logging.getLogger(__name__)


def describe_collections(f='json'):
    """
    Provide feature collection metadata

    :param f: response format (default JSON)

    :returns: dict of feature collection metadata
    """

    # TODO allow other file return formats
    if f.upper() != 'JSON':
        msg = 'Unsupported format: {}'.format(f)
        LOGGER.error(msg)
        return msg, 400

    fcm = {
        'links': [],
        'collections': []
    }

    url = '{}://{}'.format(request.scheme, settings['server']['host'])
    if settings['server']['port'] not in [80, 443]:
        url = '{}:{}'.format(url, settings['server']['port'])

#    LOGGER.debug('Creating links')
#    fcm['links'] = [{
#          'rel': 'self',
#          'type': 'application/json',
#          'title': 'this document',
#          'href': '{}{}'.format(url, url_for('index_json')),
#        }, {
#          'rel': 'self',
#          'type': 'text/html',
#          'title': 'this document as HTML',
#          'href': '{}{}'.format(url, url_for('index_html')),
#        }, {
#          'rel': 'self',
#          'type': 'application/openapi+json;version=3.0',
#          'title': 'the OpenAPI definition as JSON',
#          'href': '{}{}'.format(url, url_for('api_json')),
#        }, {
#          'rel': 'self',
#          'type': 'text/html',
#          'title': 'the OpenAPI definition as HTML',
#          'href': '{}{}'.format(url, url_for('api_html')),
#        }
#    ]

    LOGGER.debug('Creating collections')
    for k, v in settings['datasets'].items():
        collection = {'links': [], 'crs': []}
        collection['name'] = k
        collection['title'] = v['title']
        collection['description'] = v['abstract']
        for crs in v['crs']:
            collection['crs'].append(
                'http://www.opengis.net/def/crs/OGC/1.3/{}'.format(crs))
        collection['extent'] = v['extents']['spatial']['bbox']

        for link in v['links']:
            lnk = {'rel': link['type'], 'href': link['url']}
            collection['links'].append(lnk)

        fcm['collections'].append(collection)

    return fcm


def get_specification(f='json'):
    if f.upper() == 'JSON':
        return settings['api']
    else:
        return '{} not supported as a query parameter'.format(f), 400


def get_features(dataset, startindex=0, count=10, resulttype='results',
                 bbox=None, f='json'):
    """
    Queries feature collection

    :param dataset: dataset to query
    :param startindex: starting record to return (default 0)
    :param count: number of records to return (default 10)
    :param resulttype: return results or hit count (default results)
    :param bbox: list of minx,miny,maxx,maxy
    :param f: responase format (default GeoJSON)

    :returns: dict of GeoJSON FeatureCollection

    """
    if dataset not in settings['datasets'].keys():
        msg = 'dataset {} not found'.format(dataset)
        LOGGER.error(msg)
        return msg, 400
    else:
        LOGGER.debug('Loading provider')
        p = load_provider(settings['datasets'][dataset]['provider'],
                          settings['datasets'][dataset]['data'],
                          settings['datasets'][dataset]['id_field'])
        LOGGER.debug('Querying provider')
        LOGGER.debug('startindex: {}'.format(startindex))
        LOGGER.debug('count: {}'.format(count))
        LOGGER.debug('resulttype: {}'.format(resulttype))
        results = p.query(startindex=int(startindex), count=int(count),
                          resulttype=resulttype)

        return results


def get_feature(dataset, id, f='json'):
    """
    Get a single feature

    :param dataset: dataset to query
    :param id: feature identifier
    :param f: responase format (default GeoJSON)

    :returns: dict of GeoJSON Feature

    """
    if dataset not in settings['datasets'].keys():
        msg = 'dataset {} not found'.format(dataset)
        LOGGER.error(msg)
        return msg, 400

    LOGGER.debug('Loading provider')
    p = load_provider(settings['datasets'][dataset]['provider'],
                      settings['datasets'][dataset]['data'],
                      settings['datasets'][dataset]['id_field'])
    LOGGER.debug('Fetching id {}'.format(id))
    feature = p.get(id)
    if feature is None:
        msg = 'feature {} not found'.format(id)
        LOGGER.warning(msg)
        return msg, 404

    return feature
