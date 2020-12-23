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

import io
import json
import logging
import os

import tinydb

from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import JobStatus

LOGGER = logging.getLogger(__name__)


class TinyDBManager(BaseManager):
    """TinyDB Manager"""

    def __init__(self, manager_def):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.base.BaseManager`
        """

        super().__init__(manager_def)
        self.is_async = True

    def _connect(self):

        """
        connect to manager

        :returns: `bool` of status of result
        """

        self.db = tinydb.TinyDB(self.connection)
        return True

    def destroy(self):
        """
        Destroy manager

        :returns: `bool` status of result
        """

        self.db.purge()
        self.db.close()
        return True

    def get_jobs(self, process_id=None, status=None):
        """
        Get jobs

        :param process_id: process identifier
        :param status: job status (accepted, running, successful,
                       failed, results) (default is all)

        :returns: 'list` of jobs (identifier, status, process identifier)
        """

        self._connect()
        if process_id is None:
            jobs_list = [doc.doc_id for doc in self.db.all()]
        else:
            query = tinydb.Query()
            jobs_list = self.db.search(query.process_id == process_id)

        self.db.close()

        return jobs_list

    def add_job(self, job_metadata):
        """
        Add a job

        :param job_metadata: `dict` of job metadata

        :returns: identifier of added job
        """

        self._connect()
        doc_id = self.db.insert(job_metadata)
        self.db.close()

        return doc_id

    def update_job(self, process_id, job_id, update_dict):
        """
        Updates a job

        :param process_id: process identifier
        :param job_id: job identifier
        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """

        self._connect()
        self.db.update(update_dict, tinydb.where('identifier') == job_id)
        self.db.close()

        return True

    def delete_job(self, process_id, job_id):
        """
        Deletes a job

        :param process_id: process identifier
        :param job_id: job identifier

        :return `bool` of status result
        """
        # delete result file if present
        job_result = self.get_job(process_id, job_id)
        if job_result:
            location = job_result.get('location', None)
            if location and self.output_dir is not None:
                os.remove(location)

        self._connect()
        removed = bool(self.db.remove(tinydb.where('identifier') == job_id))
        self.db.close()

        return removed

    def get_job(self, process_id, job_id):
        """
        Get a single job

        :param process_id: process identifier
        :param jobid: job identifier

        :returns: `dict`  # `pygeoapi.process.manager.Job`
        """

        self._connect()
        query = tinydb.Query()
        result = self.db.search((
            query.process_id == process_id) & (query.identifier == job_id))

        result = result[0] if result else None
        self.db.close()
        return result

    def get_job_result(self, process_id, job_id):
        """
        Get a job's status, and actual output of executing the process

        :param process_id: process identifier
        :param jobid: job identifier

        :returns: The process output as a `dict`
        """

        job_result = self.get_job(process_id, job_id)
        if not job_result:
            # processs/job does not exist
            return None
        location = job_result.get('location', None)
        job_status = JobStatus[job_result['status']]
        if not job_status == JobStatus.successful:
            # Job is incomplete
            return None
        if not location:
            # Job data was not written for some reason
            # TODO log/raise exception?
            return {}
        with io.open(location, 'r', encoding='utf-8') as filehandler:
            result = json.load(filehandler)

        return result

    def __repr__(self):
        return '<TinyDBManager> {}'.format(self.name)
