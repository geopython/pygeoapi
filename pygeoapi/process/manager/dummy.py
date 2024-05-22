# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2024 Tom Kralidis
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
from typing import Any, Dict, Optional, Tuple
import uuid

from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import (
    RequestedProcessExecutionMode,
    JobStatus,
    Subscriber
)

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

    def execute_process(
            self,
            process_id: str,
            data_dict: dict,
            execution_mode: Optional[RequestedProcessExecutionMode] = None,
            requested_outputs: Optional[dict] = None,
            subscriber: Optional[Subscriber] = None
    ) -> Tuple[str, str, Any, JobStatus, Optional[Dict[str, str]]]:
        """
        Default process execution handler

        :param process_id: process identifier
        :param data_dict: `dict` of data parameters
        :param execution_mode: requested execution mode

        :returns: tuple of job_id, MIME type, response payload, status and
                  optionally additional HTTP headers to include in the
                  response
        """

        jfmt = 'application/json'

        response_headers = None
        if execution_mode is not None:
            response_headers = {
                'Preference-Applied': RequestedProcessExecutionMode.wait.value}
            if execution_mode == RequestedProcessExecutionMode.respond_async:
                LOGGER.debug('Dummy manager does not support asynchronous')
                LOGGER.debug('Forcing synchronous execution')

        self._send_in_progress_notification(subscriber)
        processor = self.get_processor(process_id)
        try:
            jfmt, outputs = processor.execute(data_dict)
            current_status = JobStatus.successful
            self._send_success_notification(subscriber, outputs)
        except Exception as err:
            outputs = {
                'code': 'InvalidParameterValue',
                'description': f'Error executing process: {err}'
            }
            current_status = JobStatus.failed
            LOGGER.exception(err)
            self._send_failed_notification(subscriber)
        job_id = str(uuid.uuid1())
        return job_id, jfmt, outputs, current_status, response_headers

    def __repr__(self):
        return f'<DummyManager> {self.name}'
