# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Ricardo Garcia Silva <ricardo.garcia.silva@gmail.com>
#
# Copyright (c) 2022 Tom Kralidis
# Copyright (c) 2023 Ricardo Garcia Silva
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

from collections import OrderedDict
import datetime as dt
import logging
from multiprocessing import dummy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from pygeoapi.models.processes import (
    Execution,
    ExecutionResultInternal,
    JobStatus,
    JobStatusInfoInternal,
    ProcessDescription,
    ProcessOutputTransmissionMode,
    ProcessExecutionMode,
    ProcessResponseType,
    RequestedProcessExecutionMode
)
from pygeoapi.plugin import load_plugin
from pygeoapi.process.base import (
    BaseProcessor,
    ProcessorGenericError,
)

LOGGER = logging.getLogger(__name__)


class BaseManager:
    """generic Manager ABC"""

    is_async: bool = False
    connection: str
    name: str
    output_dir: Optional[Path]
    processes: OrderedDict[str, Dict]

    def __init__(self, manager_def: dict):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.base.BaseManager`
        """

        self.name = manager_def['name']
        self.connection = manager_def.get('connection')
        out_dir = manager_def.get('output_dir')
        self.output_dir = Path(out_dir) if out_dir is not None else None
        self.processes = OrderedDict()
        for id_, process_conf in manager_def.get('processes', {}).items():
            self.processes[id_] = dict(process_conf)

    def get_process_descriptions(
            self,
            limit: Optional[int] = None,
            offset: Optional[int] = 0
    ) -> Tuple[int, List[ProcessDescription]]:
        """Get process descriptions

        :param limit: Maximum number of process descriptions to return
        :param offset: Optional offset for selecting relevant process
                       descriptions

        :return: A two-element tuple with the total number of processes known
                 to the manager and a list of process-related metadata.
        """

        right_bound = (
            limit + offset if limit is not None else len(self.processes))
        relevant_ = (
            (i, conf) for i, conf in enumerate(self.processes.values())
            if i <= offset and i < right_bound
        )
        descriptions = []
        for _, conf in relevant_:
            try:
                processor = load_plugin("process", conf.get("processor"))
            except ProcessorGenericError:
                LOGGER.warning(f'Unable to load process {conf}, skipping...')
            else:
                descriptions.append(processor.process_metadata)
        return len(self.processes), descriptions


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
        OAProc spec, as per:

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

    def _execute_handler_async(
            self,
            processor: BaseProcessor,
            job_id: str,
            execution_request: Execution
    ) -> JobStatus:
        """
        This private execution handler executes a process in a background
        thread using `multiprocessing.dummy`

        https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing.dummy  # noqa

        :param p: `pygeoapi.process` object
        :param job_id: job identifier
        :param data_dict: `dict` of data parameters

        :returns: JobStatus.accepted (i.e. initial job status)
        """
        _process = dummy.Process(
            target=self._execute_handler_sync,
            args=(processor, job_id, execution_request)
        )
        _process.start()
        return JobStatus.accepted

    def _execute_handler_sync(
            self,
            processor: BaseProcessor,
            job_id: str,
            execution_request: Execution
    ) -> ExecutionResultInternal:
        """
        Synchronous execution handler

        If the manager has defined `output_dir`, then the result
        will be written to disk
        output store. There is no clean-up of old process outputs.

        :param processor: `pygeoapi.process` object
        :param job_id: job identifier
        :param execution_request: execution parameters

        :returns: A tuple of process status and a dict with output ids as
                  keys and respective output results as values
        """

        current_status = JobStatus.accepted
        now = dt.datetime.now(dt.timezone.utc)
        self.add_job(JobStatusInfoInternal(
            jobID=job_id,
            processID=processor.process_metadata.id,
            status=current_status,
            message='Job accepted and ready for execution',
            created=now,
            started=now,
            progress=5,
        ))
        try:
            execution_result = processor.execute(
                job_id, execution_request,
                results_storage_root=self.output_dir
            )
        except Exception as err:
            # TODO assess correct exception type and description to help users
            # NOTE, the /results endpoint should return the error HTTP status
            # for jobs that failed, ths specification says that failing jobs
            # must still be able to be retrieved with their error message
            # intact, and the correct HTTP error status at the /results
            # endpoint, even if the /result endpoint correctly returns the
            # failure information (i.e. what one might assume is a 200
            # response).
            execution_result = ExecutionResultInternal(status=JobStatus.failed)
            code = 'InvalidParameterValue'
            outputs = {
                'code': code,
                'description': 'Error updating job'
            }
            LOGGER.error(err)
            now = dt.datetime.now(dt.timezone.utc)
            self.update_job(JobStatusInfoInternal(
                jobID=job_id,
                finished=now,
                updated=now,
                status=execution_result.status,
                message=f"{code}: {outputs['description']}"
            ))
        return execution_result

    def execute_process(
            self,
            process_id: str,
            execution_request: Execution,
            requested_execution_mode: Optional[
                RequestedProcessExecutionMode] = None
    ) -> Tuple[
        str,
        ExecutionResultInternal,
        ProcessExecutionMode,
        Optional[Dict[str, str]]
    ]:
        """
        Default process execution handler.

        :param process_id: identifier of the process to be executed
        :param execution_request: execution request
        :param requested_execution_mode: optionally specifying sync or
                                         async processing.

        :returns: tuple of generated job_id, execution results,
                  chosen execution mode and optionally additional HTTP headers
                  to include in the final response
        """

        job_id = str(uuid.uuid1())
        processor = self.get_processor(process_id)
        chosen_mode, additional_headers = self._select_execution_mode(
            requested_execution_mode, processor)
        if chosen_mode == ProcessExecutionMode.async_execute:
            LOGGER.debug('Asynchronous execution')
            current_status = self._execute_handler_async(
                processor, job_id, execution_request)
            execution_result = ExecutionResultInternal(status=current_status)
        else:
            LOGGER.debug('Synchronous execution')
            current_status, execution_result = self._execute_handler_sync(
                processor, job_id, execution_request)
        return job_id, execution_result, chosen_mode, additional_headers

    def _select_execution_mode(
            self,
            requested: RequestedProcessExecutionMode,
            processor: BaseProcessor
    ) -> Tuple[ProcessExecutionMode, Optional[Dict[str, str]]]:
        """Select the execution mode to be employed

        The execution mode to use depends on a number of factors:

        - what mode, if any, was requested by the client?
        - does the process support sync and async execution modes?
        - does the process manager support sync and async modes?
        """
        if requested == RequestedProcessExecutionMode.respond_async:
            # client wants async - do we support it?
            process_supports_async = (
                    ProcessExecutionMode.async_execute.value in 
                    processor.process_metadata.job_control_options
            )
            if self.is_async and process_supports_async:
                result = ProcessExecutionMode.async_execute
                additional_headers = {
                    'Preference-Applied': (
                        RequestedProcessExecutionMode.respond_async.value)
                }
            else:
                result = ProcessExecutionMode.sync_execute
                additional_headers = {
                    'Preference-Applied': (
                        RequestedProcessExecutionMode.wait.value)
                }
        elif requested == RequestedProcessExecutionMode.wait:
            # client wants sync - pygeoapi implicitly supports sync mode
            LOGGER.debug('Synchronous execution')
            result = ProcessExecutionMode.sync_execute
            additional_headers = {
                'Preference-Applied': RequestedProcessExecutionMode.wait.value}
        else:  # client has no preference
            # according to OAPI - Processes spec we ought to respond with sync
            LOGGER.debug('Synchronous execution')
            result = ProcessExecutionMode.sync_execute
            additional_headers = {
                'Preference-Applied': RequestedProcessExecutionMode.wait.value}
        return result, additional_headers

    def __repr__(self):
        return f'<BaseManager> {self.name}'
