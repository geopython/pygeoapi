# =================================================================
#
# Authors: Gregory Petrochenkov <gpetrochenkov@usgs.gov>
#
# Copyright (c) 2021 Gregory Petrochenkov
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

from numpy import float64, int64

import pytest

from pygeoapi.provider.xarray_ import XarrayProvider
from pygeoapi.util import json_serial

from .util import get_test_file_path

path = get_test_file_path(
    'data/analysed_sst.zarr')


@pytest.fixture()
def config():
    return {
        'name': 'zarr',
        'type': 'coverage',
        'data': path,
        'format': {
             'name': 'zarr',
             'mimetype': 'application/zip'
        }
    }


def test_provider(config):
    p = XarrayProvider(config)

    assert len(p.fields) == 4
    assert len(p.axes) == 3
    assert p.axes == ['lon', 'lat', 'time']


def test_schema(config):
    p = XarrayProvider(config)

    assert isinstance(p.fields, dict)
    assert len(p.fields) == 4
    assert p.fields['analysed_sst']['title'] == 'analysed sea surface temperature'  # noqa


def test_query(config):
    p = XarrayProvider(config)

    data = p.query()
    assert isinstance(data, dict)

    data = p.query(format_='zarr')
    assert isinstance(data, bytes)


def test_numpy_json_serial():
    d = int64(500_000_000_000)
    assert json_serial(d) == 500_000_000_000

    d = float64(500.00000005)
    assert json_serial(d) == 500.00000005
