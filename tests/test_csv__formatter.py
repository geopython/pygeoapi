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
from io import StringIO

import pytest

from build.lib.pygeoapi.formatter.base import FormatterSerializationError
from pygeoapi.formatter.csv_ import CSVFormatter


@pytest.fixture
def data():
    return {
        'features': [
            {
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-130.44472222222223, 54.28611111111111],
                },
                'type': 'Feature',
                'properties': {'id': 1, 'foo': 'bar', 'title': 'Point Feature'},
                'id': 1,
            },
            {
                'geometry': None,
                'type': 'Feature',
                'properties': {'id': 2, 'foo': 'baz', 'title': 'Non-geometry Feature'},
                'id': 2,
            },
            {
                'geometry': {
                    'type': 'MultiPoint',
                    'coordinates': [[100.0, 0.0], [101.0, 1.0]],
                },
                'type': 'Feature',
                'properties': {'id': 3, 'foo': 'bat', 'title': 'MultiPoint Feature'},
                'id': 3,
            },
            {
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [[102.0, 0.0], [103.0, 1.0], [104.0, 0.0]],
                },
                'type': 'Feature',
                'properties': {'id': 4, 'foo': 'baa', 'title': 'LineString Feature'},
                'id': 4,
            },
            {
                'geometry': {
                    'type': 'MultiLineString',
                    'coordinates': [
                        [[100.0, 0.0], [101.0, 1.0]],
                        [[102.0, 2.0], [103.0, 3.0]],
                    ],
                },
                'type': 'Feature',
                'properties': {
                    'id': 5,
                    'foo': 'bab',
                    'title': 'MultiLineString Feature',
                },
                'id': 5,
            },
            {
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [
                        # Exterior ring
                        [
                            [100.0, 0.0],
                            [101.0, 0.0],
                            [101.0, 1.0],
                            [100.0, 1.0],
                            [100.0, 0.0],
                        ],
                        # Interior ring (hole)
                        [
                            [100.2, 0.2],
                            [100.8, 0.2],
                            [100.8, 0.8],
                            [100.2, 0.8],
                            [100.2, 0.2],
                        ],
                    ],
                },
                'type': 'Feature',
                'properties': {'id': 6, 'foo': 'bac', 'title': 'Polygon Feature'},
                'id': 6,
            },
            {
                'geometry': {
                    'type': 'MultiPolygon',
                    'coordinates': [
                        [
                            [
                                [102.0, 2.0],
                                [103.0, 2.0],
                                [103.0, 3.0],
                                [102.0, 3.0],
                                [102.0, 2.0],
                            ]
                        ],
                        [
                            [
                                [100.0, 0.0],
                                [101.0, 0.0],
                                [101.0, 1.0],
                                [100.0, 1.0],
                                [100.0, 0.0],
                            ]
                        ],
                    ],
                },
                'type': 'Feature',
                'properties': {'id': 7, 'foo': 'bad', 'title': 'MultiPolygon Feature'},
                'id': 7,
            },
        ],
    }


@pytest.fixture(scope='function')
def csv_reader_geom_enabled(data):
    """csv_reader with geometry enabled"""
    formatter = CSVFormatter({'geom': True})
    output = formatter.write(data=data)
    return csv.DictReader(StringIO(output.decode('utf-8')))


@pytest.fixture
def invalid_geometry_data():
    return {
        'features': [
            {
                'geometry': {'type': 'Point', 'coordinates': [-130.44472222222223]},
                'type': 'Feature',
                'properties': {'id': 1, 'foo': 'bar', 'title': 'Invalid Point Feature'},
                'id': 1,
            }
        ]
    }


def test_write_with_geometry_enabled(csv_reader_geom_enabled):
    """Test CSV output with geometry enabled"""
    rows = list(csv_reader_geom_enabled)

    # Verify the header
    header = list(csv_reader_geom_enabled.fieldnames)
    assert len(header) == 4

    # Verify number of rows
    assert len(rows) == 7

    # Verify first row
    first_row = rows[0]
    assert first_row['geometry'] == 'POINT (-130.44472222222223 54.28611111111111)'
    assert first_row['id'] == '1'
    assert first_row['foo'] == 'bar'
    assert first_row['title'] == 'Point Feature'

    # Verify second row (null geometry)
    second_row = rows[1]
    assert second_row['geometry'] == ''
    assert second_row['id'] == '2'
    assert second_row['foo'] == 'baz'
    assert second_row['title'] == 'Non-geometry Feature'


def test_write_without_geometry(data):
    formatter = CSVFormatter({'geom': False})
    output = formatter.write(data=data)
    csv_reader = csv.DictReader(StringIO(output.decode('utf-8')))

    """Test CSV output with geometry disabled"""
    rows = list(csv_reader)

    # Verify headers don't include geometry
    headers = csv_reader.fieldnames
    assert 'geometry' not in headers

    # Verify data
    first_row = rows[0]
    assert first_row['id'] == '1'
    assert first_row['foo'] == 'bar'
    assert first_row['title'] == 'Point Feature'


def test_write_empty_features():
    """Test handling of empty feature collection"""
    formatter = CSVFormatter({'geom': True})
    data = {'features': []}
    output = formatter.write(data=data)
    assert output == ''


@pytest.mark.parametrize(
    'row_index,expected_wkt',
    [
        (2, 'MULTIPOINT (100 0, 101 1)'),
        (3, 'LINESTRING (102 0, 103 1, 104 0)'),
        (4, 'MULTILINESTRING ((100 0, 101 1), (102 2, 103 3))'),
        (
            5,
            'POLYGON ((100 0, 101 0, 101 1, 100 1, 100 0), (100.2 0.2, 100.8 0.2, 100.8 0.8, 100.2 0.8, 100.2 0.2))',
        ),
        (
            6,
            'MULTIPOLYGON (((102 2, 103 2, 103 3, 102 3, 102 2)), ((100 0, 101 0, 101 1, 100 1, 100 0)))',
        ),
    ],
)
def test_wkt(csv_reader_geom_enabled, row_index, expected_wkt):
    """Test CSV output of multi-point geometry"""
    rows = list(csv_reader_geom_enabled)

    # Verify data
    geometry_row = rows[row_index]
    assert geometry_row['geometry'] == expected_wkt

def test_invalid_geometry_data(invalid_geometry_data):
    formatter = CSVFormatter({'geom': True})
    output = formatter.write(data=invalid_geometry_data)
    csv_reader = csv.DictReader(StringIO(output.decode('utf-8')))

    rows = list(csv_reader)

    # Verify the empty geometry
    first_row = rows[0]
    assert first_row['geometry'] == ''
    assert first_row['id'] == '1'
    assert first_row['foo'] == 'bar'
    assert first_row['title'] == 'Invalid Point Feature'
