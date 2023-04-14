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

import datetime as dt
import json
import logging
from multiprocessing import dummy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from pygeoapi.models.processes import (
    JobStatusInfoInternal,
    JobStatus,
)
from pygeoapi.plugin import load_plugin
from pygeoapi.process.base import (
    BaseProcessor,
    ProcessorGenericError,
)
from pygeoapi.util import DATETIME_FORMAT

LOGGER = logging.getLogger(__name__)


class BaseManager:
    """generic Manager ABC"""

    def __init__(self, manager_def: dict):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.base.BaseManager`
        """

        self.name = manager_def['name']
        self.is_async = False
        self.connection = manager_def.get('connection')
        self.output_dir = manager_def.get('output_dir')
        self.processes = {}
        for id_, process_conf in manager_def.get('processes', {}).items():
            self.processes[id_] = dict(process_conf)

        if self.output_dir is not None:
            self.output_dir = Path(self.output_dir)

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
    ) -> Tuple[int, List[JobStatusInfoInternal]]:
        """
        Get process jobs, optionally filtered by relevant parameters.

        The filtering parameters follow their respective definition in
        OAPI - Processes spec, as per:

        https://docs.ogc.org/is/18-062r2/18-062r2.html#toc49

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

        raise NotImplementedError()

    def add_job(self, job_status: JobStatusInfoInternal) -> str:
        """
        Add a job

        :param job_status: job status info

        :returns: `str` added job identifier
        """

        raise NotImplementedError()

    def get_processor(self, process_id: str) -> Optional[BaseProcessor]:
        """Instantiate a process.

        :param process_id: Identifier of the process

        :returns: instance of the process
        """

        try:
            process_conf = self.processes[process_id]
        except KeyError as err:
            msg = 'Invalid process identifier'
            LOGGER.warning(msg)
            raise ProcessorGenericError(msg) from err
        else:
            return load_plugin('process', process_conf['processor'])

    def update_job(self, job_status: JobStatusInfoInternal) -> bool:
        """
        Updates a job

        :param job_status: property updates for the job status info

        :returns: `bool` of status result
        """

        raise NotImplementedError()

    def get_job(self, job_id: str) -> Optional[JobStatusInfoInternal]:
        """
        Get a job (!)

        :param job_id: job identifier

        :returns: job status info
        """

        raise NotImplementedError()

    def get_job_result(self, job_id: str) -> Tuple[str, Any]:
        """
        Returns the actual output from a completed process

        :param job_id: job identifier

        :returns: `tuple` of mimetype and raw output
        """

        raise NotImplementedError()

    def delete_job(self, job_id: str) -> bool:
        """
        Deletes a job and associated results/outputs

        :param job_id: job identifier

        :returns: `bool` of status result
        """

        raise NotImplementedError()

    def _execute_handler_async(self, p: BaseProcessor, job_id: str,
                               data_dict: dict) -> Tuple[str, None, JobStatus]:
        """
        This private execution handler executes a process in a background
        thread using `multiprocessing.dummy`

        https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing.dummy  # noqa

        :param p: `pygeoapi.process` object
        :param job_id: job identifier
        :param data_dict: `dict` of data parameters

        :returns: tuple of None (i.e. initial response payload)
                  and JobStatus.accepted (i.e. initial job status)
        """
        _process = dummy.Process(
            target=self._execute_handler_sync,
            args=(p, job_id, data_dict)
        )
        _process.start()
        return 'application/json', None, JobStatus.accepted

    def _execute_handler_sync(self, p: BaseProcessor, job_id: str,
                              data_dict: dict) -> Tuple[str, Any, JobStatus]:
        """
        Synchronous execution handler

        If the manager has defined `output_dir`, then the result
        will be written to disk
        output store. There is no clean-up of old process outputs.

        :param p: `pygeoapi.process` object
        :param job_id: job identifier
        :param data_dict: `dict` of data parameters

        :returns: tuple of MIME type, response payload and status
        """

        process_id = p.metadata['id']
        current_status = JobStatus.accepted

        now = dt.datetime.now(dt.timezone.utc)

        self.add_job(JobStatusInfoInternal(
            jobID=job_id,
            status=current_status,
            processID=process_id,
            message="Job accepted and ready for execution",
            created=now,
            started=now,
            progress=5,
        ))

        try:
            if self.output_dir is not None:
                filename = f"{p.metadata['id']}-{job_id}"
                job_filename = self.output_dir / filename
            else:
                job_filename = None

            current_status = JobStatus.running
            jfmt, outputs = p.execute(data_dict)

            self.update_job(
                JobStatusInfoInternal(
                    jobID=job_id,
                    status=current_status,
                    message="Writing job output",
                    progress=95
                )
            )

            if self.output_dir is not None:
                LOGGER.debug(f'writing output to {job_filename}')
                if isinstance(outputs, dict):
                    mode = 'w'
                    data = json.dumps(outputs, sort_keys=True, indent=4)
                    encoding = 'utf-8'
                elif isinstance(outputs, bytes):
                    mode = 'wb'
                    data = outputs
                    encoding = None
                with job_filename.open(mode=mode, encoding=encoding) as fh:
                    fh.write(data)

            current_status = JobStatus.successful

            now = dt.datetime.now(dt.timezone.utc)
            self.update_job(JobStatusInfoInternal(
                jobID=job_id,
                status=JobStatus.successful,
                finished=now,
                updated=now,
                location=str(job_filename),
                message="Job complete",
                progress=100
            ))

        except Exception as err:
            # TODO assess correct exception type and description to help users
            # NOTE, the /results endpoint should return the error HTTP status
            # for jobs that failed, ths specification says that failing jobs
            # must still be able to be retrieved with their error message
            # intact, and the correct HTTP error status at the /results
            # endpoint, even if the /result endpoint correctly returns the
            # failure information (i.e. what one might assume is a 200
            # response).

            current_status = JobStatus.failed
            code = 'InvalidParameterValue'
            outputs = {
                'code': code,
                'description': 'Error updating job'
            }
            LOGGER.error(err)
            jfmt = 'application/json'
            now = dt.datetime.now(dt.timezone.utc)
            self.update_job(JobStatusInfoInternal(
                jobID=job_id,
                finished=now,
                updated=now,
                status=current_status,
                message=f"{code}: {outputs['description']}"
            ))

        return jfmt, outputs, current_status

    def execute_process(
            self,
            process_id: str,
            data_dict: Dict,
            execution_mode: Optional[RequestedProcessExecutionMode] = None
    ) -> Tuple[str, str, Any, JobStatus, Optional[Dict[str, str]]]:
        """
        Default process execution handler

        :param process_id: identifier of the process to be executed
        :param data_dict: `dict` of data parameters
        :param execution_mode: `str` optionally specifying sync or async
        processing.

        :returns: tuple of job_id, MIME type, response payload, status and
                  optionally additional HTTP headers to include in the final
                  response
        """

        p = self.get_processor(process_id)
        job_id = str(uuid.uuid1())
        if execution_mode == RequestedProcessExecutionMode.respond_async:
            # client wants async - do we support it?
            process_supports_async = (
                ProcessExecutionMode.async_execute.value in p.metadata.get(
                    'jobControlOptions', []
                )
            )
            if self.is_async and process_supports_async:
                LOGGER.debug('Asynchronous execution')
                handler = self._execute_handler_async
                response_headers = {
                    'Preference-Applied': (
                        RequestedProcessExecutionMode.respond_async.value)
                }
            else:
                LOGGER.debug('Synchronous execution')
                handler = self._execute_handler_sync
                response_headers = {
                    'Preference-Applied': (
                        RequestedProcessExecutionMode.wait.value)
                }
        elif execution_mode == RequestedProcessExecutionMode.wait:
            # client wants sync - pygeoapi implicitly supports sync mode
            LOGGER.debug('Synchronous execution')
            handler = self._execute_handler_sync
            response_headers = {
                'Preference-Applied': RequestedProcessExecutionMode.wait.value}
        else:  # client has no preference
            # according to OAPI - Processes spec we ought to respond with sync
            LOGGER.debug('Synchronous execution')
            handler = self._execute_handler_sync
            response_headers = None
        # TODO: handler's response could also be allowed to include more HTTP
        # headers
        mime_type, outputs, status = handler(p, job_id, data_dict)
        return job_id, mime_type, outputs, status, response_headers

    def __repr__(self):
        return f'<BaseManager> {self.name}'
