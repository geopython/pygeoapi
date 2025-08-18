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

import csv
import io
import pytest

from pygeoapi.formatter.csv_ import CSVFormatter


@pytest.fixture()
def fixture():
    data = {
      'features': [{
          'geometry': {
            'type': 'Point',
            'coordinates': [
              -130.44472222222223,
              54.28611111111111
            ]
          },
          'type': 'Feature',
          'properties': {
            'id': 1972,
            'foo': 'bar',
            'title': None,
          },
          'id': 48693
        }]
    }

    return data


def test_csv__formatter(fixture):
    f = CSVFormatter({'geom': True})
    f_csv = f.write(data=fixture)

    buffer = io.StringIO(f_csv.decode('utf-8'))
    reader = csv.DictReader(buffer)

    header = list(reader.fieldnames)

    assert f.mimetype == 'text/csv; charset=utf-8'

    assert len(header) == 5

    assert 'x' in header
    assert 'y' in header

    data = next(reader)
    assert data['x'] == '-130.44472222222223'
    assert data['y'] == '54.28611111111111'
    assert data['id'] == '1972'
    assert data['foo'] == 'bar'
    assert data['title'] == ''
