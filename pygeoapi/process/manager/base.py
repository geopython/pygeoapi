# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
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

from datetime import datetime
import io
import json
import logging
from multiprocessing import dummy
import os

from pygeoapi.util import DATETIME_FORMAT, JobStatus

LOGGER = logging.getLogger(__name__)


class BaseManager:
    """generic Manager ABC"""

    def __init__(self, manager_def):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.base.BaseManager`
        """

        self.name = manager_def['name']
        self.is_async = False
        self.output_dir = manager_def.get('output_dir', None)

    def get_jobs(self, process_id=None, status=None):
        """
        Get process jobs, optionally filtered by status

        :param process_id: process identifier
        :param status: job status (accepted, running, successful,
                       failed, results) (default is all)

        :returns: `list` of jobs (identifier, status, process identifier)
        """

        raise NotImplementedError()

    def add_job(self, job_metadata):
        """
        Add a job

        :param job_metadata: `dict` of job metadata

        :returns: `str` added job identifier
        """

        raise NotImplementedError()

    def update_job(self, process_id, job_id, update_dict):
        """
        Updates a job

        :param process_id: process identifier
        :param job_id: job identifier
        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """

        raise NotImplementedError()

    def get_job(self, process_id, job_id):
        """
        Get a job (!)

        :param process_id: process identifier
        :param job_id: job identifier

        :returns: `dict` of job result
        """

        raise NotImplementedError()

    def get_job_result(self, process_id, job_id):
        """
        Returns the actual output from a completed process

        :param process_id: process identifier
        :param job_id: job identifier

        :returns: `str` of raw output or None
        """

        raise NotImplementedError()

    def delete_job(self, process_id, job_id):
        """
        Deletes a job and associated results/outputs

        :param process_id: process identifier
        :param job_id: job identifier

        :returns: `bool` of status result
        """

        raise NotImplementedError()

    def _execute_handler_async(self, p, job_id, data_dict):
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
        return None, JobStatus.accepted

    def _execute_handler_sync(self, p, job_id, data_dict):
        """
        Synchronous execution handler

        If the manager has defined `output_dir`, then the result
        will be written to disk
        output store. There is no clean-up of old process outputs.

        :param p: `pygeoapi.process` object
        :param job_id: job identifier
        :param data_dict: `dict` of data parameters

        :returns: tuple of response payload and status
        """

        if self.output_dir is not None:
            filename = '{}-{}'.format(p.metadata['id'], job_id)
            job_filename = os.path.join(self.output_dir, filename)
        else:
            job_filename = 'stdout'

        process_id = p.metadata['id']
        current_status = JobStatus.accepted

        job_metadata = {
            'identifier': job_id,
            'process_id': process_id,
            'process_start_datetime': datetime.utcnow().strftime(
                DATETIME_FORMAT),
            'process_end_datetime': None,
            'status': current_status.value,
            'location': None,
            'message': 'Job accepted and ready for execution',
            'progress': 5
        }

        self.add_job(job_metadata)

        try:
            current_status = JobStatus.running
            outputs = p.execute(data_dict)
            self.update_job(process_id, job_id, {
                'status': current_status.value,
                'message': 'Writing job output',
                'progress': 95
            })

            if self.output_dir is not None:
                LOGGER.debug('writing output to {}'.format(job_filename))
                with io.open(job_filename, 'w', encoding='utf-8') as fh:
                    fh.write(json.dumps(outputs, sort_keys=True, indent=4))

            current_status = JobStatus.successful
            job_update_metadata = {
                'process_end_datetime': datetime.utcnow().strftime(
                    DATETIME_FORMAT),
                'status': current_status.value,
                'location': job_filename,
                'message': 'Job complete',
                'progress': 100
            }

            self.update_job(process_id, job_id, job_update_metadata)

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
                'process_end_datetime': datetime.utcnow().strftime(
                    DATETIME_FORMAT),
                'status': current_status.value,
                'location': None,
                'message': f'{code}: {outputs["description"]}'
            }

            self.update_job(process_id, job_id, job_metadata)

        return outputs, current_status

    def execute_process(self, p, job_id, data_dict, is_async=False):
        """
        Default process execution handler

        :param p: `pygeoapi.process` object
        :param job_id: job identifier
        :param data_dict: `dict` of data parameters
        :param is_async: `bool` specifying sync or async processing.

        :returns: tuple of response payload and status
        """

        if not is_async:
            LOGGER.debug('Synchronous execution')
            return self._execute_handler_sync(p, job_id, data_dict)
        else:
            LOGGER.debug('Asynchronous execution')
            return self._execute_handler_async(p, job_id, data_dict)

    def __repr__(self):
        return '<BaseManager> {}'.format(self.name)
