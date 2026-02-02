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

from csv import DictReader
from io import StringIO
import json

import pytest

from pygeoapi.formatter.base import FormatterSerializationError
from pygeoapi.formatter.csv_ import CSVFormatter

from ..util import get_test_file_path


@pytest.fixture
def data():
    data_path = get_test_file_path('data/items.geojson')
    with open(data_path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


@pytest.fixture(scope='function')
def csv_reader_geom_enabled(data):
    """csv_reader with geometry enabled"""
    formatter = CSVFormatter({'geom': True})
    output = formatter.write(data=data)
    return DictReader(StringIO(output.decode('utf-8')))


@pytest.fixture
def invalid_geometry_data():
    return {
        'features': [
            {
                'id': 1,
                'type': 'Feature',
                'properties': {
                    'id': 1,
                    'title': 'Invalid Point Feature'
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [-130.44472222222223]
                }
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
    assert len(rows) == 9


def test_write_without_geometry(data):
    formatter = CSVFormatter({'geom': False})
    output = formatter.write(data=data)
    csv_reader = DictReader(StringIO(output.decode('utf-8')))

    """Test CSV output with geometry disabled"""
    rows = list(csv_reader)

    # Verify headers don't include geometry
    headers = csv_reader.fieldnames
    assert 'geometry' not in headers

    # Verify data
    first_row = rows[0]
    assert first_row['uri'] == \
        'http://localhost:5000/collections/objects/items/1'
    assert first_row['name'] == 'LineString'


def test_write_empty_features():
    """Test handling of empty feature collection"""
    formatter = CSVFormatter({'geom': True})
    data = {
        'features': []
    }
    output = formatter.write(data=data)
    assert output == ''


@pytest.mark.parametrize(
    'row_index,expected_wkt',
    [
        (2, 'POINT (-85 33)'),
        (3, 'MULTILINESTRING ((10 10, 20 20, 10 40), (40 40, 30 30, 40 20, 30 10))'),  # noqa
        (4, 'POLYGON ((30 10, 40 40, 20 40, 10 20, 30 10))'),
        (5, 'POLYGON ((35 10, 45 45, 15 40, 10 20, 35 10), (20 30, 35 35, 30 20, 20 30))'),  # noqa
        (6, 'MULTIPOLYGON (((30 20, 45 40, 10 40, 30 20)), ((15 5, 40 10, 10 20, 5 10, 15 5)))')  # noqa
    ]
)
def test_wkt(csv_reader_geom_enabled, row_index, expected_wkt):
    """Test CSV output of multi-point geometry"""
    rows = list(csv_reader_geom_enabled)

    # Verify data
    geometry_row = rows[row_index]
    assert geometry_row['wkt'] == expected_wkt


def test_invalid_geometry_data(invalid_geometry_data):
    formatter = CSVFormatter({'geom': True})
    with pytest.raises(FormatterSerializationError):
        formatter.write(data=invalid_geometry_data)
