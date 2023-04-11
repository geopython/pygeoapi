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

import json
import logging
import uuid
from datetime import datetime
from multiprocessing import dummy
from pathlib import Path
from typing import Any, Tuple

from pygeoapi.util import DATETIME_FORMAT, JobStatus
from pygeoapi.process.base import BaseProcessor

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

        if self.output_dir is not None:
            self.output_dir = Path(self.output_dir)

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

        :returns: `dict` of job result
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

        job_metadata = {
            'identifier': job_id,
            'process_id': process_id,
            'job_start_datetime': datetime.utcnow().strftime(
                DATETIME_FORMAT),
            'job_end_datetime': None,
            'status': current_status.value,
            'location': None,
            'mimetype': None,
            'message': 'Job accepted and ready for execution',
            'progress': 5
        }

        self.add_job(job_metadata)

        try:
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
                with job_filename.open(mode=mode, encoding=encoding) as fh:
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

            self.update_job(job_id, job_update_metadata)

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
            job_metadata = {
                'job_end_datetime': datetime.utcnow().strftime(
                    DATETIME_FORMAT),
                'status': current_status.value,
                'location': None,
                'mimetype': None,
                'message': f'{code}: {outputs["description"]}'
            }

            jfmt = 'application/json'

            self.update_job(job_id, job_metadata)

        return jfmt, outputs, current_status

    def execute_process(
            self,
            p,
            data_dict,
            is_async=False
    ) -> Tuple[str, str, Any, JobStatus]:
        """
        Default process execution handler

        :param p: `pygeoapi.process` object
        :param data_dict: `dict` of data parameters
        :param is_async: `bool` specifying sync or async processing.

        :returns: tuple of job_id, MIME type, response payload and status
        """

        job_id = str(uuid.uuid1())
        if not is_async:
            LOGGER.debug('Synchronous execution')
            result = self._execute_handler_sync(p, job_id, data_dict)
        else:
            LOGGER.debug('Asynchronous execution')
            result = self._execute_handler_async(p, job_id, data_dict)
        return (job_id, *result)

    def __repr__(self):
        return f'<BaseManager> {self.name}'
