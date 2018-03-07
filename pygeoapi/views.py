# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
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

from flask import url_for

from pygeoapi.provider import load_provider


def get_feature_collection_metadata(config):
    fcm = {
        'links': [],
        'collections': []
    }

    url = config['server']['url'].rstrip('/')

    fcm['links'] = [{
          'rel': 'self',
          'type': 'application/json',
          'title': 'this document',
          'href': '{}{}'.format(url, url_for('index_json')),
        }, {
          'rel': 'self',
          'type': 'text/html',
          'title': 'this document as HTML',
          'href': '{}{}'.format(url, url_for('index_html')),
        }, {
          'rel': 'self',
          'type': 'application/openapi+json;version=3.0',
          'title': 'the OpenAPI definition as JSON',
          'href': '{}{}'.format(url, url_for('api_json')),
        }, {
          'rel': 'self',
          'type': 'text/html',
          'title': 'the OpenAPI definition as HTML',
          'href': '{}{}'.format(url, url_for('api_html')),
        }
    ]

    for k, v in config['datasets'].items():
        collection = {'links': [], 'crs': []}
        collection['collectionId'] = k
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


def get_feature_collection(config, dataset, startindex=0, count=10,
                           resulttype='results'):
    if dataset not in config['datasets'].keys():
        return None

    p = load_provider(config['datasets'][dataset]['data'])

    results = p.query(startindex=startindex, count=count,
                      resulttype=resulttype)

    return results


def get_feature(config, dataset, identifier):
    if dataset not in config['datasets'].keys():
        return None

    p = load_provider(config['datasets'][dataset]['data'])

    results = p.get(identifier)

    return results


def get_api_conformance_json():
    return {
        'conformsTo': [
            'http://www.opengis.net/spec/wfs-1/3.0/req/core',
            'http://www.opengis.net/spec/wfs-1/3.0/req/oas30',
            'http://www.opengis.net/spec/wfs-1/3.0/req/html',
            'http://www.opengis.net/spec/wfs-1/3.0/req/geojson'
        ]
    }


def get_es_index(url):
    return split_es_url(url)[-2]


def get_es_type(url):
    return split_es_url(url)[-1]


def split_es_url(url):
    """splits ES URL into host index, type"""

    tokens = url.split('/')
    return tokens
