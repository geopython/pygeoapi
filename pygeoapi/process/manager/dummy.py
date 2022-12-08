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
from typing import Any, Tuple

from pygeoapi.process.base import BaseProcessor
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import JobStatus

LOGGER = logging.getLogger(__name__)


class DummyManager(BaseManager):
    """generic Manager ABC"""

    def __init__(self, manager_def: dict):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.base.BaseManager`
        """

        super().__init__(manager_def)

    def get_jobs(self, status: JobStatus = None) -> list:
        """
        Get process jobs, optionally filtered by status

        :param status: job status (accepted, running, successful,
                       failed, results) (default is all)

        :returns: `list` of jobs (identifier, status, process identifier)
        """

        return []

    def execute_process(self, p: BaseProcessor, job_id: str, data_dict: dict,
                        is_async: bool = False) -> Tuple[str, Any, int]:
        """
        Default process execution handler

        :param p: `pygeoapi.process` object
        :param job_id: job identifier
        :param data_dict: `dict` of data parameters
        :param is_async: `bool` specifying sync or async processing.

        :returns: tuple of MIME type, response payload and status
        """

        jfmt = 'application/json'

        if is_async:
            LOGGER.debug('Dummy manager does not support asynchronous')
            LOGGER.debug('Forcing synchronous execution')

        try:
            jfmt, outputs = p.execute(data_dict)
            current_status = JobStatus.successful
        except Exception as err:
            outputs = {
                'code': 'InvalidParameterValue',
                'description': 'Error updating job'
            }
            current_status = JobStatus.failed
            LOGGER.error(err)

        return jfmt, outputs, current_status

    def __repr__(self):
        return f'<DummyManager> {self.name}'
