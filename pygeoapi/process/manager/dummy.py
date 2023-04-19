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
from typing import Any, Dict, List, Optional, Tuple

from pygeoapi.process.manager.base import BaseManager
from pygeoapi.models.processes import (
    Execution,
    JobStatus,
    RequestedProcessExecutionMode,
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

    def get_jobs(
            self,
            type_: Optional[List[str]] = None,
            process_id: Optional[List[str]] = None,
            status: Optional[List[JobStatus]] = None,
            date_time: Optional[str] = None,
            min_duration_seconds: Optional[int] = None,
            max_duration_seconds: Optional[int] = None,
            limit: Optional[int] = 10,
            offset: Optional[int] = 0,
    ) -> Tuple[int, List[Dict]]:
        """
        Get process jobs, optionally filtered by status

        :param type_: process types to be returned
        :param process_id: identifiers of the parent processes of jobs
        :param status: job statuses (accepted, running, successful,
                       failed, results)
        :param date_time: temporal interval that a job's `create` property
                          must intersect
        :param min_duration_seconds: minimum duration of jobs
        :param max_duration_seconds: maximum duration of jobs
        :param limit: number of jobs to return
        :param offset: Offset for selecting which jobs to return

        :returns: a two-element tuple with the total number of jobs that
                  match the filtering parameters and a list of job statuses
        """

        return 0, []

    def execute_process(
            self,
            process_id: str,
            execution_request: Execution,
            requested_execution_mode: Optional[
                RequestedProcessExecutionMode] = None
    ) -> Tuple[
            str,
            Optional[str],
            JobStatus,
            Any,
            Optional[Dict[str, str]]
    ]:
        """
        Default process execution handler.

        :param process_id: identifier of the process to be executed
        :param execution_request: execution request
        :param requested_execution_mode: optionally specifying sync or
                                         async processing.

        :returns: tuple of generated job_id, optional response media type,
                  response payload, current job status and
                  optionally additional HTTP headers to include in the final
                  response
        """

        if requested_execution_mode is not None:
            requested_async = (
                    requested_execution_mode ==
                    RequestedProcessExecutionMode.respond_async
            )
            if requested_async:
                LOGGER.debug('Dummy manager does not support asynchronous')
                LOGGER.debug('Forcing synchronous execution')
        return super().execute_process(
            process_id, execution_request, RequestedProcessExecutionMode.wait)

    def __repr__(self):
        return f'<DummyManager> {self.name}'
