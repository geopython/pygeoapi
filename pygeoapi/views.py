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


from pygeoapi.config import settings
from pygeoapi.provider import load_provider

def describe_collections(f='json'):
    # TODO allow other file return formats
    if f.upper() == 'JSON':
        fcm = {
            'collections': []
        }

        for k, v in settings['datasets'].items():
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

        return {'collections' : collection}
    else:
        return f'"{f}" not supported as a query parameter.', 400

def get_specification(f='json'):
    if f.upper() == 'JSON':
        return settings['api']
    else:
        return  f'"{f}" not supported as a query parameter.', 400

def getFeatures(ds, start_index, count, result_type, bbox=None, f='json'):
    if ds not in settings['datasets'].keys():
        return f'dataset {ds} not found.', 400
    else:
        p = load_provider(settings['datasets'][ds]['data'])
        return p.query()

def getFeature(ds, id, f='json'):
    if ds not in settings['datasets'].keys():
        return f'dataset {ds} not found.', 400
    else:
        p = load_provider(settings['datasets'][ds]['data'])
        feat = p.get(id)
        if feat is None:
            return f'feature "{id}" not found', 404
        else:
            return feat
