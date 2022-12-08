# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Tom Kralidis
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

LOGGER = logging.getLogger(__name__)


class BaseFormatter:
    """generic Formatter ABC"""

    def __init__(self, formatter_def: dict):
        """
        Initialize object

        :param formatter_def: formatter definition

        :returns: pygeoapi.formatter.base.BaseFormatter
        """

        self.mimetype = None
        self.geom = False

        self.name = formatter_def['name']
        if 'geom' in formatter_def:
            self.geom = formatter_def['geom']

    def write(self, options: dict = {}, data: dict = None) -> str:
        """
        Generate data in specified format

        :param options: CSV formatting options
        :param data: dict representation of GeoJSON object

        :returns: string representation of format
        """

        raise NotImplementedError()

    def __repr__(self):
        return f'<BaseFormatter> {self.name}'


class FormatterGenericError(Exception):
    """formatter generic error"""
    pass


class FormatterSerializationError(FormatterGenericError):
    """formatter serialization error"""
    pass
