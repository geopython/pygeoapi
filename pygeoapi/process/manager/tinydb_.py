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

        self.name = manager_def['name']
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

    def update_job(self, job_id, update_dict):
        """
        Updates a job

        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """

        self.connect()
        self.db.update(update_dict, tinydb.where('identifier') == job_id)
        self.db.close()
        return True

    def delete_jobs(self, max_jobs, older_than):
        """
        TODO
        """
        raise NotImplementedError()

    def get_job_result(self, processid, jobid):
        """
        Get a single job

        :param processid: process identifier
        :param jobid: job identifier

        :returns: `dict`  # `pygeoapi.process.manager.Job`
        """

        self.connect()
        query = tinydb.Query()
        r = self.db.search(query.processid == processid, query.jobid == jobid)

        return r

    def add_job_result(self, processid, jobid):
        """
        Add a job result

        :param processid: process identifier
        :param jobid: job identifier

        :returns: `bool` of add job result result
        """

    def __repr__(self):
        return '<TinyDBManager> {}'.format(self.name)


class ManagerExecuteError(Exception):
    """query / backend error"""
    pass
