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

import os
import pytest

from pygeoapi.provider.filesystem import FileSystemProvider

THISDIR = os.path.dirname(os.path.realpath(__file__))


@pytest.fixture()
def config():
    return {
        'name': 'FileSystem',
        'type': 'stac',
        'data': os.path.join(THISDIR, 'data'),
        'file_types': ['.gpkg']
    }


def test_query(config):
    p = FileSystemProvider(config)

    baseurl = 'http://example.org/stac'
    urlpath = ''
    dirpath = ''

    r = p.get_data_path(baseurl, urlpath, dirpath)

    assert len(r['links']) == 12

    r = p.get_data_path(baseurl, urlpath, '/poi_portugal')

    assert r['geometry'] == {
        'coordinates': [[[-31.263032, 32.635814],
                         [-31.263032, 42.120163],
                         [-6.221649, 42.120163],
                         [-6.221649, 32.635814],
                         [-31.263032, 32.635814]]],
        'type': 'Polygon'
    }
    assert r['properties'] == {
        'fclass': 'str:255',
        'gid': 'int',
        'name': 'str:255',
        'osm_id': 'int'
    }
    assert r['assets']['default']['href'] == 'http://example.org/stac/poi_portugal.gpkg'  # noqa
