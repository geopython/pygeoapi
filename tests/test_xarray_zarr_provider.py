# =================================================================
#
# Authors: Gregory Petrochenkov <gpetrochenkov@usgs.gov>
#
# Copyright (c) 2020 Gregory Petrochenkov
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

import os
import pytest

from pygeoapi.provider.xarray_ import XarrayProvider


def get_test_file_path(filename):
    """helper function to open test file safely"""

    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


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


def test_domainset(config):
    p = XarrayProvider(config)
    domainset = p.get_coverage_domainset()

    assert isinstance(domainset, dict)
    assert domainset['generalGrid']['axisLabels'] == ['lon', 'lat', 'time']
    assert domainset['generalGrid']['gridLimits']['axisLabels'] == ['i', 'j']
    assert domainset['generalGrid']['gridLimits']['axis'][0]['upperBound'] == 101  # noqa
    assert domainset['generalGrid']['gridLimits']['axis'][1]['upperBound'] == 101  # noqa


def test_rangetype(config):
    p = XarrayProvider(config)
    rangetype = p.get_coverage_rangetype()

    assert isinstance(rangetype, dict)
    assert len(rangetype['field']) == 4
    assert rangetype['field'][0]['name'] == 'analysed sea surface temperature'


def test_query(config):
    p = XarrayProvider(config)

    data = p.query()
    assert isinstance(data, dict)

    data = p.query(format_='zarr')
    assert isinstance(data, bytes)
