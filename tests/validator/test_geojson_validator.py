# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2026 Tom Kralidis
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

import json

import pytest

from pygeoapi.validator.base import ValidatorValidationError
from pygeoapi.validator.geojson import GeoJSONValidator


@pytest.fixture()
def validator_def():
    return {}


@pytest.fixture()
def valid_geojson_data():
    data = {
      'geometry': {
        'type': 'Point',
        'coordinates': [
          -130.44472222222223,
          54.28611111111111
        ]
      },
      'type': 'Feature',
      'properties': {
        'id': 1972,
        'foo': 'bar',
        'title': None
      },
      'id': 48693
    }

    return json.dumps(data)


@pytest.fixture()
def invalid_geojson_data():
    data = {
      'geometree': {
        'type': 'Point',
        'coordinates': [
          -130.44472222222223,
          54.28611111111111
        ]
      },
      'type': 'Feature',
      'properties': {
        'id': 1972,
        'foo': 'bar',
        'title': None
      },
      'id': 48693
    }

    return json.dumps(data)


def test_valid_geojson_data(validator_def, valid_geojson_data):
    v = GeoJSONValidator(validator_def)
    assert v.validate(valid_geojson_data) is None


def test_invalid_geojson_data(validator_def, invalid_geojson_data):
    v = GeoJSONValidator(validator_def)
    with pytest.raises(ValidatorValidationError):
        v.validate(invalid_geojson_data)
