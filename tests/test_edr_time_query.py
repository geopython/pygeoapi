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
import sys
from pathlib import Path
path_root = Path(__file__).parents[1]
sys.path.append(str(path_root))

import pytest
from shapely.geometry import Point

from pygeoapi.provider.xarray_edr import XarrayEDRProvider
from pygeoapi.util import json_serial

from tests.util import get_test_file_path

path = get_test_file_path(
    'data/analysed_sst.zarr')

# time testing scenarios
single = '2005-12-09T09:00:00Z'
bounded = '2005-12-09T09:00:00Z/2005-12-12T09:00:00.000000000'
unbounded_start = '../2005-12-12T09:00:00.000000000'
unbounded_end = '2005-12-09T09:00:00Z/..'
no_time = None

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

@pytest.fixture()
def query_parameters():
    return {
        'query_type': 'position',
        'instance': None,
        'format_': 'json',
        'select_properties': ['analysed_sst'],
        'wkt': Point(-27, 40),
        'z': None,
        'bbox': None,
        'within': None,
        'within_units': None,
        'limit': 10
        }

def test_single_time_query(config, query_parameters):
    p = XarrayEDRProvider(config)
    query_parameters['datetime_'] = single
    data = p.position(**query_parameters)

    assert isinstance(data, dict)
    assert len(data['ranges']['analysed_sst']['values']) == 1


def test_bounded_time_query(config, query_parameters):
    p = XarrayEDRProvider(config)
    query_parameters['datetime_'] = bounded
    data = p.position(**query_parameters)

    assert isinstance(data, dict)
    assert len(data['ranges']['analysed_sst']['values']) == 4


def test_unbounded_start_time_query(config, query_parameters):
    p = XarrayEDRProvider(config)
    query_parameters['datetime_'] = unbounded_start
    data = p.position(**query_parameters)

    assert isinstance(data, dict)
    assert len(data['ranges']['analysed_sst']['values']) == 12


def test_unbounded_end_time_query(config, query_parameters):
    p = XarrayEDRProvider(config)
    query_parameters['datetime_'] = unbounded_end
    data = p.position(**query_parameters)

    assert isinstance(data, dict)
    assert len(data['ranges']['analysed_sst']['values']) == 24

def test_no_time_query(config, query_parameters):
    p = XarrayEDRProvider(config)
    query_parameters['datetime_'] = no_time
    data = p.position(**query_parameters)

    assert isinstance(data, dict)
    assert len(data['ranges']['analysed_sst']['values']) == 32
    assert data['domain']['axes']['time']['start'] == "2005-12-01T09:00:00.000000000"
    assert data['domain']['axes']['time']['stop'] == "2006-01-01T09:00:00.000000000"