# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2019 Tom Kralidis
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
import os

import tinydb

from pygeoapi.process.manager.base import BaseManager

LOGGER = logging.getLogger(__name__)


class TinyDBManager(BaseManager):
    """TinyDB Manager"""

    def __init__(self, manager_def):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.base.BaseManager`
        """

        BaseManager.__init__(self, manager_def)

        self.connection = manager_def['connection']

    def connect(self):

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

    def get_jobs(self, processid=None, status=None):
        """
        Get jobs

        :param processid: process identifier
        :param status: job status (accepted, running, successful,
                       failed, results) (default is all)

        :returns: 'list` of jobs (identifier, status, process identifier)
        """

        self.connect()
        if processid is None:
            return [doc.doc_id for doc in self.db.all()]
        else:
            query = tinydb.Query()
            return self.db.search(query.processid == processid)

        self.db.close()

    def add_job(self, job_metadata):
        """
        Add a job

        :param job_metadata: `dict` of job metadata

        :returns: `bool` of add job result
        """

        self.connect()
        doc_id = self.db.insert(job_metadata)
        self.db.close()
        return doc_id

    def update_job(self, processid, job_id, update_dict):
        """
        Updates a job

        :param processid: process identifier
        :param job_id: job identifier
        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """

        self.connect()
        self.db.update(update_dict, tinydb.where('identifier') == job_id)
        self.db.close()
        return True

    def delete_job(self, processid, job_id):
        """
        Deletes a job

        :param processid: process identifier
        :param job_id: job identifier

        :return `bool` of status result
        """
        self.connect()

        # delete result file if present
        job_result = self.get_job_result(processid, job_id)
        if job_result:
            location = job_result.get('location', None)
            if location:
                os.remove(location)

        removed_ids = self.db.remove(tinydb.where('identifier') == job_id)

        return bool(removed_ids)

    def delete_jobs(self, max_jobs, older_than):
        """
        TODO
        """
        raise NotImplementedError()

    def get_job_result(self, processid, job_id):
        """
        Get a single job

        :param processid: process identifier
        :param jobid: job identifier

        :returns: `dict`  # `pygeoapi.process.manager.Job`
        """

        self.connect()
        query = tinydb.Query()
        r = self.db.search((query.processid == processid) & (query.identifier == job_id))

        return r[0] if r else None

    def get_job_output(self, processid, job_id):
        """
        Get a job's status, and actual output of executing the process

        :param processid: process identifier
        :param jobid: job identifier

        :returns: tuple of JobStatus and the process output as a `dict`
        """
        job_result = self.get_job_result(processid, job_id)
        if not job_result:
            # processs/job does not exist
            return None, None
        location = job_result.get('location', None)
        job_status = JobStatus[job_result['status']]
        if not job_status == JobStatus.successful:
            # Job is incomplete
            return job_status, None
        if not location:
            # Job data was not written for some reason
            # TODO log/raise exception?
            return job_status, {}
        with io.open(location, 'r') as fh:
            result = json.load(fh)
        return job_status, result

    def __repr__(self):
        return '<TinyDBManager> {}'.format(self.name)
