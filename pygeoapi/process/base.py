# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Martinelli <francesco.martinelli@ingv.it>
#
# Copyright (c) 2022 Tom Kralidis
# Copyright (c) 2024 Francesco Martinelli
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
from typing import Any, Tuple, Optional

from pygeoapi.error import GenericError

LOGGER = logging.getLogger(__name__)


class BaseProcessor:
    """generic Processor ABC. Processes are inherited from this class"""

    def __init__(self, processor_def: dict, process_metadata: dict):
        """
        Initialize object

        :param processor_def: processor definition
        :param process_metadata: process metadata `dict`

        :returns: pygeoapi.processor.base.BaseProvider
        """

        self.name = processor_def['name']
        self.metadata = process_metadata
        self.supports_outputs = False

    def set_job_id(self, job_id: str) -> None:
        """
        Set the job_id within the processor
        To be implemented by derived classes where required.

        :param job_id: the job_id assigned to the request by the Manager.
                       The function should be called by the Manager upon
                       assigning the job_id. The job_id is intended to be used
                       by derived classes, e.g. to write temporary files where
                       filenames contains the string job_id.

        :returns: `None`
        """

        pass

    def execute(self, data: dict, outputs: Optional[dict] = None
                ) -> Tuple[str, Any]:
        """
        execute the process

        :param data: Dict with the input data that the process needs in order
                     to execute
        :param outputs: `dict` or `list` to optionally specify the subset of
                        required outputs - defaults to all outputs.
                        The value of any key may be an object and include the
                        property `transmissionMode` - defaults to `value`.
        :returns: tuple of MIME type and process response
                  (string or bytes, or dict)
        """

        raise NotImplementedError()

    def __repr__(self):
        return f'<BaseProcessor> {self.name}'


class ProcessorGenericError(GenericError):
    """processor generic error"""
    pass


class ProcessorExecuteError(ProcessorGenericError):
    """query / backend error"""
    default_msg = "generic error (check logs)"


class JobError(Exception):
    pass


class JobNotFoundError(JobError):
    pass


class JobResultNotFoundError(JobError):
    pass


class ProcessError(Exception):
    pass


class UnknownProcessError(ProcessError):
    pass
