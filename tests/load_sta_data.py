# =================================================================
#
# Authors: Benjamin Webb <benjamin.miller.webb@gmail.com>
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2021 Benjamin Webb
# Copyright (c) 2022 Tom Kralidis
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

from pathlib import Path
import requests
import sys
import json

url = 'http://localhost:8080/FROST-Server/v1.1/Datastreams'
data_url = 'https://raw.githubusercontent.com/webb-ben/data/main/'


def main(path_: Path):
    filename = path_.name
    r = requests.get(f'{data_url}{filename}')
    data = r.json().get('value')
    for v in data:
        clean(v)
        requests.post(url, json.dumps(v))
    print(f"Added {len(requests.get(url).json()['value'])} entities")


def clean(dirty_dict):
    if isinstance(dirty_dict, dict):
        keys = []
        for (k, v) in dirty_dict.items():
            if '@' in k and k != '@iot.id':
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
        print(f'Usage: {sys.argv[0]} <path/to/data.geojson>')
        sys.exit(1)

    main(Path(sys.argv[1]))
