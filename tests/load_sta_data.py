# =================================================================
#
# Authors: Benjamin Webb <benjamin.miller.webb@gmail.com>
#
# Copyright (c) 2021 Benjamin Webb
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

import time
import requests
import sys
import json

url = 'http://localhost:8080/FROST-Server/v1.1/Datastreams'


def main(filename):
    with open(filename) as fh:
        data = json.load(fh)
        data = data.get('value')
        for v in data:
            clean(v)
            requests.post(url, json.dumps(v))
            time.sleep(0.02)


def clean(dirty_dict):
    if isinstance(dirty_dict, dict):
        keys = []
        for (k, v) in dirty_dict.items():
            if '@' in k:
                keys.append(k)
            elif isinstance(v, dict):
                clean(v)
            elif isinstance(v, list):
                for _v in v:
                    if isinstance(_v, dict):
                        clean(_v)

        for k in keys:
            dirty_dict.pop(k)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print('Usage: {} <path/to/data.geojson>'.format(sys.argv[0]))
        sys.exit(1)

    main(sys.argv[1])
