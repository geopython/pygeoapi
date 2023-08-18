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

import pyproj

from pygeoapi.provider.rasterio_ import RasterioProvider
from pygeoapi.util import get_transform_from_crs
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


def test_domainset(config):
    p = RasterioProvider(config)
    domainset = p.get_coverage_domainset()

    assert isinstance(domainset, dict)
    assert domainset['generalGrid']['axisLabels'] == ['Long', 'Lat']
    assert domainset['generalGrid']['gridLimits']['axisLabels'] == ['i', 'j']
    assert domainset['generalGrid']['gridLimits']['axis'][0]['upperBound'] == 2400  # noqa
    assert domainset['generalGrid']['gridLimits']['axis'][1]['upperBound'] == 1201  # noqa


def test_rangetype(config):
    p = RasterioProvider(config)
    rangetype = p.get_coverage_rangetype()

    assert isinstance(rangetype, dict)
    assert len(rangetype['field']) == 1
    assert rangetype['field'][0]['name'] == 'Temperature [C]'


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

    bbox_crs_epsg = 4326
    bbox = [-79, 45, -75, 49]
    xmin, ymin, xmax, ymax = bbox
    data = p.query(bbox=bbox, bbox_crs=bbox_crs_epsg)
    storage_crs = p._data.crs
    transform_func = get_transform_from_crs(
        pyproj.CRS.from_epsg(bbox_crs_epsg),
        storage_crs,
        geom_objects=False,
        always_xy=True,
    )
    x_start, y_stop = transform_func(xmin, ymin)
    x_stop, y_start = transform_func(xmax, ymax)

    assert isinstance(data, dict)

    assert data['domain']['axes']['x']['start'] == x_start
    assert data['domain']['axes']['x']['stop'] == x_stop
    assert data['domain']['axes']['y']['start'] == y_start
    assert data['domain']['axes']['y']['stop'] == y_stop
