# =================================================================
#
# Authors: Richard Law <lawr@landcareresearch.co.nz>
#
# Copyright (c) 2020 Richard Law
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

import redis

from pygeoapi.process.manager.base import BaseManager, ManagerExecuteError

LOGGER = logging.getLogger(__name__)

def make_key(processid='*', job_id='*'):
    """
    Concatenates a process ID and a job ID into a static key for use in Redis

    :param processid: process identifier, or '*' as wildcard
    :param jobid: job identifier, or '*' as wildcard

    :returns: `str` concatenation like `'process:{processid}:job:{job_id}'`
    """
    return f'process:{processid or "*"}:job:{job_id or "*"}'

def dict_remove_none(_dict):
    """
    Removes key-value pairs from a dictionary where the value is `None`. Does
    not handle nested dictionaries.

    :param _dict: `dict`

    :returns: `dict`
    """
    return {k: v for k, v in _dict.items() if v is not None}


class RedisManager(BaseManager):
    """Redis Manager"""

    def __init__(self, manager_def):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.base.BaseManager`
        """

        BaseManager.__init__(self, manager_def)

        self.connection = manager_def['connection']
        self.connect()

    def connect(self, health_check_interval=30):

        """
        connect to manager

        :returns: `bool` of status of result
        """

        self.db = redis.ConnectionPool(
            host=self.connection,
            port=6379,
            db=0,
            decode_responses=True
        )
        return True

    def _connect(self):
        try:
            return redis.Redis(connection_pool=self.db)
        except redis.exceptions.ConnectionError as exc:
            # TODO - wait, retry, return 503 (Service Unavailable)?
            raise exc

    def destroy(self):
        """
        Destroy manager

        :returns: `bool` status of result
        """
        # This manager uses a Redis connection pool that does not need to be
        # explicitly closed
        return True

    def get_jobs(self, processid=None, status=None):
        """
        Get jobs

        :param processid: process identifier
        :param status: job status (accepted, running, successful,
                       failed, results) (default is all)

        :returns: list of jobs
        """
        db = self._connect()
        jobs = []
        match = make_key(processid or '*', '*')
        for key in db.scan_iter(match):
            data = db.hgetall(key)
            if status and data.get('status') != status:
                continue
            jobs.append(data)
        return jobs

    def add_job(self, job_metadata):
        """
        Add a job

        :param job_metadata: `dict` of job metadata

        :returns: `bool` of add job result
        """
        # TODO maybe don't use a hash, but rather single values, with prefixes
        db = self._connect()
        job_id = job_metadata.get('identifier')
        processid = job_metadata.get('processid')
        key = make_key(processid, job_id)
        hmset_status = db.hmset(key, dict_remove_none(job_metadata))
        return hmset_status

    def update_job(self, processid, job_id, update_dict):
        """
        Updates a job

        :param processid: process identifier
        :param job_id: job identifier
        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """
        db = self._connect()
        key = make_key(processid, job_id)
        update_dict = dict_remove_none(update_dict)
        # dicts are serialised before being added to redis, so the update_dict
        # cannot be used to partially update; first HGETALL the record and then
        # create a new, complete, update dict
        with db.pipeline() as pipe:
            # Context manager for pipe calls reset() automatically to return
            # the connection to the pool
            while True:
                try:
                    pipe.watch(key)
                    current_data = pipe.hgetall(key)
                    update_data = {**current_data, **update_dict}
                    pipe.multi()
                    pipe.hmset(key, update_data)
                    hmset_status = pipe.execute()
                    break
                except redis.exceptions.WatchError:
                    # The key was updated between being read and updated with
                    # the new information
                    # TODO could retry
                    # TODO better error message
                    raise ManagerExecuteError('Update atomicity error')
        return hmset_status

    def delete_job(self, processid, job_id):
        """
        Deletes a job

        :param processid: process identifier
        :param job_id: job identifier

        :return `bool` of status result
        """
        db = self._connect()
        key = make_key(processid, job_id)
        del_status = db.delete(key)
        return del_status

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
        db = self._connect()
        key = make_key(processid, job_id)
        return db.hgetall(key)

    def __repr__(self):
        return '<RedisManager> {}'.format(self.name)
