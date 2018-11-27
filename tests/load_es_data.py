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

import json
import os
import sys

from elasticsearch import Elasticsearch
es = Elasticsearch()

type_name = 'FeatureCollection'

if len(sys.argv) == 1:
    print('Usage: {} <path/to/data.geojson>'.format(sys.argv[0]))
    sys.exit(1)

index_name = os.path.splitext(os.path.basename(sys.argv[1]))[0]

if es.indices.exists(index_name):
    es.indices.delete(index_name)

# index settings
settings = {
    'mappings': {
        'FeatureCollection': {
            'properties': {
                'geometry': {
                    'type': 'geo_shape'
                },
                'properties': {
                    'properties': {
                        'nameascii': {
                            'type': 'text',
                            'fields': {
                                'raw': {
                                    'type': 'keyword'
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

# create index
es.indices.create(index=index_name, body=settings, request_timeout=90)

with open(sys.argv[1]) as fh:
    d = json.load(fh)

for f in d['features']:
    f['properties']['geonameid'] = int(f['properties']['geonameid'])
    res = es.index(index=index_name, doc_type=type_name,
                   id=f['properties']['geonameid'], body=f)
