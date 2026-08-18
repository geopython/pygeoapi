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

from http import HTTPStatus
import logging

from pygeoapi.error import GenericError

LOGGER = logging.getLogger(__name__)


class BaseValidator:
    """generic Validator ABC"""

    def __init__(self, validator_def):
        """
        Initialize object

        :param validator_def: validator definition

        :returns: pygeoapi.validator.base.BaseValidator
        """

    def validate(self, data: bytes, partial: bool = False) -> None:
        """
        Validate a data structure

        :param data: `bytes` of data
        :param partial: `bool` of whether data to be validated is a
                        partial resource (default `False`)

        :returns: None
        """

        raise NotImplementedError()

    def __repr__(self):
        return '<BaseValidator>'


class ValidatorGenericError(GenericError):
    """validator generic error"""

    default_msg = 'generic validation error (check logs)'


class ValidatorValidationError(ValidatorGenericError):
    """validator generic error"""

    default_msg = 'Data validation error'
    http_status_code = HTTPStatus.BAD_REQUEST
    ogc_exception_code = 'InvalidParameterValue'
