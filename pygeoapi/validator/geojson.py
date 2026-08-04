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

import logging
import json
import os

from jsonschema import Draft202012Validator

from pygeoapi.validator.base import BaseValidator, ValidatorValidationError

LOGGER = logging.getLogger(__name__)

THISDIR = os.path.dirname(os.path.realpath(__file__))

SCHEMA_FILE = os.path.join(
    THISDIR, '..', 'resources', 'schemas', 'geojson', 'Feature.json')

with open(SCHEMA_FILE) as fh:
    SCHEMA_DICT = json.load(fh)


class GeoJSONValidator(BaseValidator):
    """GeoJSON validator"""

    def __init__(self, validator_def):
        """
        Initialize object

        :returns: pygeoapi.validator.geojson.GeoJSONValidator
        """

        super().__init__(validator_def)

    def validate(self, data: bytes, partial: bool = False) -> None:
        """
        Validate a GeoJSON payload

        :param data: `Any` data type
        :param partial: `bool` of whether data to be validated is a
                        partial resource (default `False`)

        :returns: `None` or `ValidatorValidationError`
        """

        if partial:
            msg = 'Partial validation not supported'
            raise ValidatorValidationError(msg)

        LOGGER.debug(f'Validating against {SCHEMA_FILE}')
        try:
            data_payload = json.loads(data)
        except json.decoder.JSONDecodeError as err:
            msg = 'Error decoding GeoJSON'
            LOGGER.error(f'{msg}: {err}')
            raise ValidatorValidationError(msg)

        validator = Draft202012Validator(SCHEMA_DICT)

        errors = [
            f'{list(err.path)}: {err.message}'
            for err in validator.iter_errors(data_payload)
        ]

        if errors:
            msg = 'Invalid GeoJSON payload'
            LOGGER.error(f'{msg}: {errors}')
            raise ValidatorValidationError(msg, user_msg=errors)

    def __repr__(self):
        return '<GeoJSONValidator>'
