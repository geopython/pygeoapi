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

import pytest

from pygeoapi.provider.base import ProviderQueryError
from pygeoapi.provider.xarray_ import XarrayProvider

from .util import get_test_file_path

path = get_test_file_path('tests/data/coads_sst.nc')


@pytest.fixture()
def config():
    return {
        'name': 'xarray',
        'type': 'coverage',
        'data': path,
        'format': {
            'name': 'netcdf',
            'mimetype': 'application/x-netcdf'
        }
    }


def test_provider(config):
    p = XarrayProvider(config)

    assert len(p.fields) == 4
    assert len(p.axes) == 3
    assert p.axes == ['COADSX', 'COADSY', 'TIME']


def test_rangetype(config):
    p = XarrayProvider(config)

    assert isinstance(p.fields, dict)
    assert len(p.fields) == 4
    assert p.fields['SST']['title'] == 'SEA SURFACE TEMPERATURE'


def test_query(config):
    p = XarrayProvider(config)

    data = p.query()
    assert isinstance(data, dict)

    data = p.query(format_='NetCDF')
    assert isinstance(data, bytes)

    data = p.query(datetime_='2000-01-16')
    assert isinstance(data, dict)

    data = p.query(datetime_='2000-01-16/2000-04-16')
    assert isinstance(data, dict)

    with pytest.raises(ProviderQueryError):
        data = p.query(datetime_='2010-01-16')
