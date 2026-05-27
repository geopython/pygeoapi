# =================================================================
#
# Authors: Gregory Petrochenkov <gpetrochenkov@usgs.gov>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2021 Gregory Petrochenkov
# Copyright (c) 2025 Tom Kralidis
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

from ..util import get_test_file_path

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


def test_query_serializes_nan_values(config):
    p = XarrayProvider(config)

    # Query the first available timestep
    query_time = str(p._data[p.time_field].values[0]).split('T')[0]

    baseline = p.query(properties=['SST'], datetime_=query_time)
    baseline_values = baseline['ranges']['SST']['values']
    baseline_none_count = sum(value is None for value in baseline_values)

    # Get the index of the first non-null/non-nan value in the baseline 
    target_index = next(
        idx for idx, value in enumerate(baseline_values)
        if value is not None and value == value
    )
    # Calculate the corresponding y/x indices in the original data array.
    _, x_size = baseline['ranges']['SST']['shape'][-2:]
    y_index = target_index // x_size
    x_index = target_index % x_size

    # Work on an in-memory copy so we can inject a NaN without touching fixture data.
    p._data = p._data.copy(deep=True)
    p._data['SST'][{
        p.time_field: 0,
        p.y_field: y_index,
        p.x_field: x_index
    }] = float('nan')

    coverage = p.query(properties=['SST'], datetime_=query_time)
    values = coverage['ranges']['SST']['values']

    # Baseline value at target index is numeric before the injected NaN.
    assert baseline_values[target_index] is not None
    # The injected NaN is converted to null during serialization.
    assert values[target_index] is None
    # Injecting one NaN should produce exactly one additional serialized null.
    assert sum(value is None for value in values) == baseline_none_count + 1
