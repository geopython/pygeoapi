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

import abc
from base64 import urlsafe_b64encode
import collections
import datetime as dt
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
import json
import logging
from multiprocessing import dummy
from pathlib import Path
from typing import Dict, List, Optional, OrderedDict, Tuple
import uuid

from pygeoapi.models.base import Link
from pygeoapi.models.processes import (
    ExecutionOutput,
    ExecuteRequest,
    ExecutionDocumentResult,
    ExecutionDocumentSingleOutput,
    ExecutionFormat,
    ExecutionQualifiedInputValue,
    JobStatus,
    JobStatusInfoInternal,
    OutputExecutionResultInternal,
    ProcessDescription,
    ProcessOutputTransmissionMode,
    ProcessExecutionMode,
    ProcessResponseType,
    RequestedProcessExecutionMode
)
from pygeoapi.plugin import load_plugin
from pygeoapi.process.base import (
    BaseProcessor,
)
from pygeoapi.process import exceptions

LOGGER = logging.getLogger(__name__)


class BaseManager(abc.ABC):
    """generic Manager ABC"""

    is_async: bool = False
    connection: str
    name: str
    output_dir: Optional[Path]
    processes: OrderedDict[str, Dict]

    def __init__(self, manager_def: Dict):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.base.BaseManager`
        """

        self.name = manager_def['name']
        self.connection = manager_def.get('connection')
        out_dir = manager_def.get('output_dir')
        self.output_dir = Path(out_dir) if out_dir is not None else None
        self.processes = collections.OrderedDict()
        for id_, process_conf in manager_def.get('processes', {}).items():
            self.processes[id_] = dict(process_conf)

    @abc.abstractmethod
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

        :raise: JobError: if the job list cannot be retrieved
        :returns: a two-element tuple with the total number of jobs that
                  match the filtering parameters and a list of job statuses
        """
        ...

    @abc.abstractmethod
    def get_job(self, job_id: str) -> JobStatusInfoInternal:
        """
        Get a job (!)

        :param job_id: job identifier

        :raise JobNotFoundError: If job_id does not correspond to a known job
        :raise JobError: If the job cannot be retrieved
        :returns: job status info
        """
        ...

    @abc.abstractmethod
    def delete_job(self, job_id: str) -> JobStatusInfoInternal:
        """
        Deletes a job and associated results, if any.

        :param job_id: job identifier

        :raise JobNotFoundError: If job_id does not correspond to a known job
        :raise JobError: If the job cannot be deleted
        :returns: job status info of the dismissed job
        """
        ...

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
            if i >= offset and i < right_bound
        )
        descriptions = []
        for _, conf in relevant_:
            processor = load_plugin('process', conf.get('processor'))
            descriptions.append(processor.process_description)
        return len(self.processes), descriptions

    def get_processor(self, process_id: str) -> Optional[BaseProcessor]:
        """Instantiate a process.

        :param process_id: Identifier of the process

        :raise UnknownProcessError: if the process cannot be created
        :returns: instance of the process
        """

        try:
            process_conf = self.processes[process_id]
        except KeyError as err:
            raise exceptions.UnknownProcessError(
                'Invalid process identifier') from err
        else:
            return load_plugin('process', process_conf['processor'])

    def update_job(self, job_status: JobStatusInfoInternal) -> bool:
        """
        Updates a job

        :param job_status: property updates for the job status info

        :raise JobError: if the job cannot be updated
        :returns: `bool` of status result
        """

        raise NotImplementedError()

    def get_execution_response(
            self,
            requested_response_type: ProcessResponseType,
            requested_outputs: Optional[Dict[str, ExecutionOutput]],
            generated_outputs: Dict[str, OutputExecutionResultInternal],
    ) -> Tuple[bytes, Optional[str], List[Link]]:
        """Get the details for an execution response."""
        LOGGER.debug(f'locals: {locals()}')
        media_type = None
        payload = None
        additional_headers = []
        if len(generated_outputs) == 0:
            LOGGER.info('there are no outputs to include in the response')
        elif requested_response_type == ProcessResponseType.raw:
            if len(generated_outputs) == 1:
                if requested_outputs is not None:
                    requested = list(requested_outputs.values())[0]
                else:
                    requested = None
                payload, media_type, additional_headers = (
                    _get_execution_response_single_output(
                        requested,
                        tuple(generated_outputs.values())[0],
                    )
                )
            else:
                any_by_value = ProcessOutputTransmissionMode.VALUE in [
                    out.transmission_mode for out in
                    requested_outputs.values()
                ]
                media_type = 'multipart/related' if any_by_value else None
                payload = _get_execution_response_multiple_outputs(
                    requested_outputs, generated_outputs)
        else:
            media_type = 'application/json'
            payload = _get_execution_response_document(
                requested_outputs, generated_outputs)
        return payload, media_type, additional_headers

    def add_job(self, job_status: JobStatusInfoInternal) -> str:
        """
        Persist job details.

        :param job_status: job status info

        Derived classes only need to supply an implementation of this method
        if they are relying on the base class' `execute_process()` method.

        :raise: JobError: if job cannot be persisted
        :returns: `str` added job identifier
        """

        raise NotImplementedError()

    def execute_process(
            self,
            process_id: str,
            execution_request: ExecuteRequest,
            requested_execution_mode: Optional[
                RequestedProcessExecutionMode] = None
    ) -> Tuple[
        JobStatusInfoInternal,
        Optional[Dict[str, str]]
    ]:
        """
        Default process execution handler.

        :param process_id: identifier of the process to be executed
        :param execution_request: execution request
        :param requested_execution_mode: optionally specifying sync or
                                         async processing.

        :raise: UnknownProcessError: if the process_id is not known
        :raise: JobFailedError: if there is an error processing the job
        :raise: JobError: if there is an error persisting job details
        :returns: tuple of job status info, and optionally additional HTTP
                  headers to include in the final response.
        """

        processor = self.get_processor(process_id)
        chosen_mode, additional_headers = self._select_execution_mode(
            requested_execution_mode, processor)

        now = dt.datetime.now(dt.timezone.utc)
        job_id = str(uuid.uuid1())
        status_info = JobStatusInfoInternal(
            jobID=job_id,
            processID=processor.process_description.id,
            status=JobStatus.accepted,
            message='Job accepted and ready for execution',
            created=now,
            started=now,
            progress=5,
            negotiated_execution_mode=ProcessExecutionMode.sync_execute,
            requested_response_type=execution_request.response,
            requested_outputs=execution_request.outputs,
        )
        self.add_job(status_info)
        if chosen_mode == ProcessExecutionMode.async_execute:
            LOGGER.debug('Asynchronous execution')
            self._execute_handler_async(processor, job_id, execution_request)
        else:
            LOGGER.debug('Synchronous execution')
            self._execute_handler_sync(processor, job_id, execution_request)
        result_info = self.get_job(job_id)
        return result_info, additional_headers

    def _execute_handler_async(
            self,
            processor: BaseProcessor,
            job_id: str,
            execution_request: ExecuteRequest
    ) -> None:
        """
        This private execution handler executes a process in a background
        thread using `multiprocessing.dummy`

        https://docs.python.org/3/library/multiprocessing.html#module-multiprocessing.dummy  # noqa

        :param p: `pygeoapi.process` object
        :param job_id: job identifier
        :param data_dict: `dict` of data parameters
        """
        process_ = dummy.Process(
            target=self._execute_handler_sync,
            args=(processor, job_id, execution_request)
        )
        process_.start()

    def _execute_handler_sync(
            self,
            processor: BaseProcessor,
            job_id: str,
            execution_request: ExecuteRequest
    ) -> None:
        """
        Synchronous execution handler

        If the manager has defined `output_dir`, then the result
        will be written to disk
        output store. There is no clean-up of old process outputs.

        :param processor: `pygeoapi.process` object
        :param job_id: job identifier
        :param execution_request: execution parameters

        :raise: JobFailedError: if there is a processing error
        """

        try:
            execution_result = processor.execute(
                job_id, execution_request,
                results_storage_root=self.output_dir,
                progress_reporter=self.update_job
            )
        except (exceptions.JobFailedError, Exception) as err:
            now = dt.datetime.now(dt.timezone.utc)
            status_info = JobStatusInfoInternal(
                jobID=job_id,
                finished=now,
                updated=now,
                status=JobStatus.failed,
                message=f'Job failed - {str(err)}',
            )
            self.update_job(status_info)
            raise
        else:
            now = dt.datetime.now(dt.timezone.utc)
            status_info = JobStatusInfoInternal(
                jobID=job_id,
                finished=now,
                updated=now,
                status=execution_result.status,
                message="Process completed successfully",
                generated_outputs=execution_result.generated_outputs,
            )
            self.update_job(status_info)

    def _select_execution_mode(
            self,
            requested: Optional[RequestedProcessExecutionMode],
            processor: BaseProcessor
    ) -> Tuple[ProcessExecutionMode, Dict[str, str]]:
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
                    [
                        op.value for op in
                        processor.process_description.job_control_options
                    ]
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
            additional_headers = {}
        return result, additional_headers

    def __repr__(self):
        return f'<BaseManager> {self.name}'


def _get_execution_response_single_output(
        requested_output: Optional[ExecutionOutput],
        generated_output: OutputExecutionResultInternal,
) -> Tuple[Optional[bytes], Optional[str], List]:
    """Get process execution response for when there is a single process output

    If there is a single execution output:
    - If transmission is by value, return the output directly
    - If transmission is by reference, include a link header
      for where the output can be downloaded

    :param requested_output: requested output parameters
    :param generated_output: Generated output parameters
    :returns: a three-element tuple with the already serialized response
              payload, the media type and a list with any additional headers
              to be added to the response
    """
    if requested_output is None:
        should_transmit_by_value = True
    else:
        should_transmit_by_value = (
                requested_output.transmission_mode ==
                ProcessOutputTransmissionMode.VALUE.value
        )
    additional_headers = []
    if should_transmit_by_value:
        media_type = generated_output.media_type
        payload = Path(generated_output.location).read_bytes()
    else:
        media_type = None
        payload = None
        additional_headers.append(
            Link(href=generated_output.location).as_link_header()
        )
    return payload, media_type, additional_headers


def _get_execution_response_multiple_outputs(
        requested_outputs: Dict[str, ExecutionOutput],
        generated_outputs: Dict[str, OutputExecutionResultInternal],
        multipart_boundary: Optional[str] = None,
) -> bytes:
    """Generate an appropriate body for process execution HTTP responses

    According to the OAProc spec (Requirement 31 -
    /req/core/process-execute-sync-raw-mixed-multi),
    if there are multiple outputs, then responses should have a media type
    of `multipart/related` and, depending on the transmission mode, either
    include the contents directly in the response, or include
    links to them.
    """
    payload = MIMEMultipart("related", boundary=multipart_boundary)
    for output_id, generated_output in generated_outputs.items():
        part = MIMENonMultipart(
            *generated_output.media_type.split('/'), )
        part.set_param('Type', generated_output.media_type)
        part.add_header('Content-ID', output_id)
        requested = requested_outputs.get(output_id)
        if requested is None:
            should_transmit_by_value = True
        else:
            should_transmit_by_value = (
                    requested.transmission_mode ==
                    ProcessOutputTransmissionMode.VALUE.value
            )
        if should_transmit_by_value:
            data_ = Path(generated_output.location).read_bytes()
            part.set_payload(data_)
            if payload.get_param("Type") is None:
                # set the `Type` of the payload as the same media
                # type of the first output
                payload.set_param(
                    "Type", generated_output.media_type)
        else:
            part.add_header('Content-Location', generated_output.location)
        payload.attach(part)
    return payload.as_bytes()


def _get_execution_response_document(
        requested_outputs: Dict[str, ExecutionOutput],
        generated_outputs: Dict[str, OutputExecutionResultInternal],
) -> str:
    """Prepare process execution response when the requested type is `document`

    :param execution_request: The parameters that originated the execution
    :param execution_result: Process execution results
    """
    output_results = {}
    for out_id, generated_output in generated_outputs.items():
        requested = requested_outputs.get(out_id)
        if requested is None:
            should_transmit_by_value = True
        else:
            should_transmit_by_value = (
                    requested.transmission_mode ==
                    ProcessOutputTransmissionMode.VALUE.value
            )
        if should_transmit_by_value:
            # if the output's media type is not text based we should
            # be able to base64 encode the file contents
            output_data = Path(generated_output.location).read_bytes()

            if 'json' in generated_output.media_type:
                # TODO: is it a BBOX?
                parsed_output_data = json.loads(output_data)
                out_result = ExecutionDocumentSingleOutput(
                    __root__=ExecutionQualifiedInputValue(
                        value=parsed_output_data)
                )
            elif 'xml' in generated_output.media_type:
                out_result = ExecutionDocumentSingleOutput(
                    __root__=ExecutionQualifiedInputValue(
                        value=output_data,
                        format_=ExecutionFormat(
                            mediaType=generated_output.media_type)
                    )
                )
            elif 'text' in generated_output.media_type:
                out_result = ExecutionDocumentSingleOutput(
                    __root__=output_data)
            else:
                serialized_output_data = urlsafe_b64encode(
                    output_data).decode('utf-8')
                out_result = ExecutionDocumentSingleOutput(
                    __root__=serialized_output_data)
        else:
            out_result = ExecutionDocumentSingleOutput(
                __root__=Link(
                    href=generated_output.location,
                    type=generated_output.media_type
                )
            )
        output_results[out_id] = out_result
    result = ExecutionDocumentResult(__root__=output_results)
    return result.json(by_alias=True, exclude_none=True)
