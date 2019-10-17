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

import logging

LOGGER = logging.getLogger(__name__)


class BaseProcessor(object):
    """generic Processor ABC. Processes are inherited from this class"""

    def __init__(self, processor_def, process_metadata):
        """
        Initialize object

        :param processor_def: processor definition
        :param process_metadata: process metadata `dict`

        :returns: pygeoapi.processor.base.BaseProvider
        """

        self.name = processor_def['name']
        self.metadata = process_metadata

    def execute(self):
        """
        execute the process
        :returns: dict of process response
        """

        raise NotImplementedError()

    def __repr__(self):
        return '<BaseProcessor> {}'.format(self.name)


class ProcessorExecuteError(Exception):
    """query / backend error"""
    pass
