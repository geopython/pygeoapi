# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2025 Francesco Bartoli
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

import pytest

from pygeoapi.formatter.jsonfg import JSONFGFormatter


@pytest.fixture()
def fixture():
    data = {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'id': '123-456',
            'geometry': {
                'type': 'Point',
                'coordinates': [125.6, 10.1]},
            'properties': {
                'name': 'Dinagat Islands',
                'foo': 'bar'
            }}
        ],
        'links': [{
            'rel': 'self',
            'type': 'application/geo+json',
            'title': 'GeoJSON',
            'href': 'http://example.com'
        }]
    }

    return data


def test_jsonfg__formatter(fixture):
    f = JSONFGFormatter({'geom': True})
    f_jsonfg = f.write(data=fixture, dataset='test', id_field='id', options={})

    assert f.mimetype == "application/geo+json"

    assert f_jsonfg['type'] == 'FeatureCollection'
    assert f_jsonfg['features'][0]['type'] == 'Feature'
    assert f_jsonfg['features'][0]['geometry']['type'] == 'Point'
    assert f_jsonfg['features'][0]['geometry']['coordinates'] == [125.6, 10.1]
    assert f_jsonfg['features'][0]['properties']['id'] == '123-456'
    assert f_jsonfg['features'][0]['properties']['name'] == 'Dinagat Islands'
    assert f_jsonfg['features'][0]['properties']['foo'] == 'bar'

    assert f_jsonfg['featureType'] == 'OGRGeoJSON'
    assert f_jsonfg['conformsTo']
    assert f_jsonfg['coordRefSys'] == '[EPSG:4326]'
    assert f_jsonfg['features'][0]['place'] is None
    assert f_jsonfg['features'][0]['time'] is None

    assert len(f_jsonfg['links']) == 1
