# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2022 Tom Kralidis
#           (c) 2023 Ricardo Garcia Silva
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

import collections
from datetime import datetime
import json
import logging
import multiprocessing
from multiprocessing import dummy
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, OrderedDict
import uuid

from pygeoapi.plugin import load_plugin
from pygeoapi.process.base import (
    BaseProcessor,
    JobNotFoundError,
    JobResultNotFoundError,
    UnknownProcessError,
)
from pygeoapi.util import (
    DATETIME_FORMAT,
    JobStatus,
    ProcessExecutionMode,
    RequestedProcessExecutionMode,
)
from pygeoapi.provider.base import (
    ProviderPreconditionFailed,
    ProviderRequestEntityTooLargeError
)
LOGGER = logging.getLogger(__name__)



class BaseManager:
    """generic Manager ABC"""
    processes: OrderedDict[str, Dict]

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
        self.max_concurrent = manager_def.get('max_concurrent', 0)
        self.max_queue = manager_def.get('max_queue', 0)
        self.result_in_db = manager_def.get('result_in_db', False)
        self.internal_error_in_db = manager_def.get('internal_error_in_db',
                                                    False)
        self.job_pending = 0

        if self.output_dir is not None:
            self.output_dir = Path(self.output_dir)

        # Note: There are two different things named OrderedDict here - one
        # is coming from typing.OrderedDict (type annotation), the other is
        # coming from collections.OrderedDict (actual type we want
        # to use here) - this will not be needed anymore when pygeoapi moves
        # to requiring Python 3.9 as the minimum supported Python version
        self.processes = collections.OrderedDict()
        for id_, process_conf in manager_def.get('processes', {}).items():
            self.processes[id_] = dict(process_conf)

        # If parallel processing is limited
        self.semaphore = None
        if self.max_concurrent > 0:
            # Create a semaphore to limit a maximum of parallel processes
            self.semaphore = multiprocessing.Semaphore(self.max_concurrent)

    def get_processor(self, process_id: str) -> Optional[BaseProcessor]:
        """Instantiate a processor.

        :param process_id: Identifier of the process

        :raise UnknownProcessError: if the processor cannot be created
        :returns: instance of the processor
        """

        try:
            process_conf = self.processes[process_id]
        except KeyError as err:
            raise UnknownProcessError('Invalid process identifier') from err
        else:
            return load_plugin('process', process_conf['processor'])

    def get_jobs(self, status: JobStatus = None) -> list:
        """
        Get process jobs, optionally filtered by status

        :param status: job status (accepted, running, successful,
                       failed, results) (default is all)

        :returns: `list` of jobs (identifier, status, process identifier)
        """

        raise NotImplementedError()

    def add_job(self, job_metadata: dict) -> str:
        """
        Add a job

        :param job_metadata: `dict` of job metadata

        :returns: `str` added job identifier
        """

        raise NotImplementedError()

    def update_job(self, job_id: str, update_dict: dict) -> bool:
        """
        Updates a job

        :param job_id: job identifier
        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """

        raise NotImplementedError()

    def get_job(self, job_id: str) -> dict:
        """
        Get a job (!)

        :param job_id: job identifier

        :raises: JobNotFoundError: if the job_id does not correspond to a
            known job
        :returns: `dict` of job result
        """

        raise JobNotFoundError()

    def get_job_result(self, job_id: str) -> Tuple[str, Any]:
        """
        Returns the actual output from a completed process

        :param job_id: job identifier

        :raises: JobNotFoundError: if the job_id does not correspond to a
            known job
        :raises: JobResultNotFoundError: if the job-related result cannot
            be returned
        :returns: `tuple` of mimetype and raw output
        """

        raise JobResultNotFoundError()

    def delete_job(self, job_id: str) -> bool:
        """
        Deletes a job and associated results/outputs

        :param job_id: job identifier

        :raises: JobNotFoundError: if the job_id does not correspond to a
            known job
        :returns: `bool` of status result
        """

        raise JobNotFoundError()

    def _execute_handler_async(self, p: BaseProcessor, job_id: str,
                               data_dict: dict) -> Tuple[str, None, JobStatus]:  # noqa
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

        # If limiting the queue
        if self.max_queue > 0:
            # Check if over
            if self.job_pending >= self.max_queue:
                # Refuse, queue is full
                return 'application/json', {'job_id': None}, JobStatus.dismissed  # noqa

        # Proceed
        _process = dummy.Process(
            target=self._execute_handler_sync,
            args=(p, job_id, data_dict)
        )
        _process.start()
        return 'application/json', {'job_id': job_id}, JobStatus.accepted

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
        message = 'Job accepted'

        # If using limitation
        if self.semaphore:
            current_status = JobStatus.in_queue
            message = 'Job accepted and put in queue'

        job_metadata = {
            'identifier': job_id,
            'process_id': process_id,
            'job_start_datetime': datetime.utcnow().strftime(
                DATETIME_FORMAT),
            'job_end_datetime': None,
            'status': current_status.value,
            'location': None,
            'mimetype': None,
            'message': message,
            'progress': 5
        }

        self.add_job(job_metadata)

        try:
            # Increment task count pending
            self.job_pending = self.job_pending + 1

            # If limiting parallel processing
            if self.semaphore:
                # Acquire the semaphore permission
                self.semaphore.acquire()

            try:
                current_status = JobStatus.accepted
                self.update_job(job_id, {
                    'status': current_status.value,
                    'message': 'Job ready for execution',
                    'progress': 10
                })

                if self.output_dir is not None:
                    filename = f"{p.metadata['id']}-{job_id}"
                    job_filename = self.output_dir / filename
                else:
                    job_filename = None

                current_status = JobStatus.running
                jfmt, outputs = p.execute(data_dict)

                self.update_job(job_id, {
                    'status': current_status.value,
                    'message': 'Writing job output',
                    'progress': 95
                })

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
                    with job_filename.open(mode=mode,
                                           encoding=encoding) as fh:
                        fh.write(data)

                current_status = JobStatus.successful

                job_update_metadata = {
                    'job_end_datetime': datetime.utcnow().strftime(
                        DATETIME_FORMAT),
                    'status': current_status.value,
                    'location': str(job_filename),
                    'mimetype': jfmt,
                    'message': 'Job complete',
                    'progress': 100
                }

                # If data is going in the database
                if self.result_in_db:
                    job_update_metadata['result'] = json.dumps(outputs,
                                                               sort_keys=True,
                                                               indent=4)

                # Update the job termination
                self.update_job(job_id, job_update_metadata)

            except Exception as err:
                # TODO assess correct exception type and description to help
                # users
                # NOTE, the /results endpoint should return the error HTTP
                # status for jobs that failed, ths specification says that
                # failing jobs must still be able to be retrieved with their
                # error message intact, and the correct HTTP error status at
                # the /results endpoint, even if the /result endpoint
                # correctly returns the failure information
                # (i.e. what one might assume is a 200 response).

                current_status = JobStatus.failed
                if isinstance(err, ProviderPreconditionFailed):
                    code = 'PreconditionFailed'
                    description = str(err)

                elif isinstance(err, ProviderRequestEntityTooLargeError):
                    code = 'RequestEntityTooLargeError'
                    description = str(err)

                else:
                    code = 'InvalidParameterValue'
                    description = 'Error processing job'

                outputs = {
                    'code': code,
                    'error': err,
                    'description': description
                }

                LOGGER.error(err)
                job_metadata = {
                    'job_end_datetime': datetime.utcnow().strftime(
                        DATETIME_FORMAT),
                    'status': current_status.value,
                    'location': None,
                    'mimetype': None,
                    'message': f'{code}: {outputs["description"]}'
                }

                jfmt = 'application/json'

                # If the internal error is going in the database
                if self.internal_error_in_db:
                    job_metadata['internal_error'] = str(err)

                # Update the job
                self.update_job(job_id, job_metadata)

            return jfmt, outputs, current_status

        finally:
            # Decrement job pending
            self.job_pending = self.job_pending - 1

            # If using limitation
            if self.semaphore:
                # Release the semaphore
                self.semaphore.release()

    def execute_process(
            self,
            process_id: str,
            data_dict: dict,
            execution_mode: Optional[RequestedProcessExecutionMode] = None
    ) -> Tuple[str, Any, JobStatus, Optional[Dict[str, str]]]:
        """
        Default process execution handler

        :param process_id: process identifier
        :param data_dict: `dict` of data parameters
        :param execution_mode: `str` optionally specifying sync or async
        processing.

        :raises: UnknownProcessError if the input process_id does not
                 correspond to a known process
        :returns: tuple of job_id, MIME type, response payload, status and
                  optionally additional HTTP headers to include in the final
                  response
        """

        job_id = str(uuid.uuid1())
        processor = self.get_processor(process_id)

        # Running inside a process manager, set it
        processor.set_process_manager(self, job_id)

        if execution_mode == RequestedProcessExecutionMode.respond_async:
            job_control_options = processor.metadata.get(
                'jobControlOptions', [])
            # client wants async - do we support it?
            process_supports_async = (
                ProcessExecutionMode.async_execute.value in job_control_options  # noqa
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
                'Preference-Applied': RequestedProcessExecutionMode.wait.value}  # noqa
        else:  # client has no preference
            # according to OAPI - Processes spec we ought to respond with sync
            LOGGER.debug('Synchronous execution')
            handler = self._execute_handler_sync
            response_headers = None
        # TODO: handler's response could also be allowed to include more HTTP
        # headers
        mime_type, outputs, status = handler(processor, job_id, data_dict)
        return job_id, mime_type, outputs, status, response_headers

    def __repr__(self):
        return f'<BaseManager> {self.name}'


def get_manager(config: Dict) -> BaseManager:
    """
    Instantiate process manager from the supplied configuration.

    :param config: pygeoapi configuration
    :returns: The pygeoapi process manager object
    """
    manager_conf = config.get('server', {}).get(
        'manager',
        {
            'name': 'Dummy',
            'connection': None,
            'output_dir': None
        }
    )
    processes_conf = {}
    for id_, resource_conf in config.get('resources', {}).items():
        if resource_conf.get('type') == 'process':
            processes_conf[id_] = resource_conf
    manager_conf['processes'] = processes_conf
    if manager_conf.get('name') == 'Dummy':
        LOGGER.info('Starting dummy manager')
    return load_plugin('process_manager', manager_conf)
