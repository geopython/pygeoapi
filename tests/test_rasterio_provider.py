# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2021 Tom Kralidis
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

from pygeoapi.provider.rasterio_ import RasterioProvider

from .util import get_test_file_path

path = get_test_file_path(
    'tests/data/CMC_glb_TMP_TGL_2_latlon.15x.15_2020081000_P000.grib2')


@pytest.fixture()
def config():
    return {
        'name': 'rasterio',
        'type': 'coverage',
        'data': path,
        'options': {
            'DATA_ENCODING': 'COMPLEX_PACKING'
        },
        'format': {
            'name': 'GRIB',
            'mimetype': 'application/x-grib2'
        }
    }


def test_provider(config):
    p = RasterioProvider(config)

    assert p.num_bands == 1
    assert len(p.axes) == 2
    assert p.axes == ['Long', 'Lat']


def test_schema(config):
    p = RasterioProvider(config)

    assert isinstance(p.fields, dict)
    assert len(p.fields) == 1
    assert p.fields['1']['title'] == 'Temperature [C]'


def test_query(config):
    p = RasterioProvider(config)

    data = p.query()
    assert isinstance(data, dict)

    data = p.query(format_='GRIB')
    assert isinstance(data, bytes)


def test_query_bbox_reprojection(config):
    config['options']['DATA_ENCODING'] = 'SIMPLE_PACKING'
    config['data'] = get_test_file_path(
        'tests/data/CMC_hrdps_continental_TMP_TGL_80_ps2.5km_2020102700_P005-00.grib2'  # noqa
    )
    p = RasterioProvider(config)

    data = p.query(bbox=[-79, 45, -75, 49])

    assert isinstance(data, dict)
    assert data['domain']['axes']['x']['start'] == -79.0
    assert data['domain']['axes']['x']['stop'] == -75.0
    assert data['domain']['axes']['y']['start'] == 49.0
    assert data['domain']['axes']['y']['stop'] == 45.0
