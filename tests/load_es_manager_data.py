# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2026 Tom Kralidis
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
from pathlib import Path
import sys

from elasticsearch import Elasticsearch, helpers
es = Elasticsearch('http://localhost:9200')

if len(sys.argv) < 2:
    print(f'Usage: {sys.argv[0]} <path/to/jobs.json>')
    sys.exit(1)

index_name = Path(sys.argv[1]).stem.lower()

if es.indices.exists(index=index_name):
    es.indices.delete(index=index_name)

# index settings
settings = {
    'number_of_shards': 1,
    'number_of_replicas': 0
}


def gendata(data):
    """
    Generator function to yield features
    """

    for j in data['jobs']:
        yield {
            "_index": index_name,
            "_id": j['identifier'],
            "_source": j
        }


# create index
es.options(request_timeout=90).indices.create(
    index=index_name, settings=settings)

with open(sys.argv[1], encoding='utf-8') as fh:
    d = json.load(fh)

    # call generator function to yield features into ES bulk API
    helpers.bulk(es, gendata(d))
