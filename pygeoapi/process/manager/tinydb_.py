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


from contextlib import contextmanager
import json
import logging
from pathlib import Path
from typing import Any, Tuple

import tinydb
from filelock import FileLock

from pygeoapi.process.base import (
    JobNotFoundError,
    JobResultNotFoundError,
)
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import JobStatus

LOGGER = logging.getLogger(__name__)


class TinyDBManager(BaseManager):
    """TinyDB Manager"""

    def __init__(self, manager_def: dict):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.base.BaseManager`
        """

        super().__init__(manager_def)
        self.is_async = True
        self.supports_subscribing = True

    @contextmanager
    def _db(self):
        self.lock = FileLock(f"{self.connection}.lock")
        with self.lock:
            with tinydb.TinyDB(self.connection) as db:
                yield db

    def destroy(self) -> bool:
        """
        Destroy manager

        :returns: `bool` status of result
        """

        with self._db as db:
            db.purge()

        return True

    def get_jobs(self, status: JobStatus = None) -> list:
        """
        Get jobs

        :param status: job status (accepted, running, successful,
                       failed, results) (default is all)

        :returns: 'list` of jobs (identifier, status, process identifier)
        """

        with self._db() as db:
            jobs_list = db.all()

        return jobs_list

    def add_job(self, job_metadata: dict) -> str:
        """
        Add a job

        :param job_metadata: `dict` of job metadata

        :returns: identifier of added job
        """

        with self._db() as db:
            doc_id = db.insert(job_metadata)

        return doc_id  # noqa

    def update_job(self, job_id: str, update_dict: dict) -> bool:
        """
        Updates a job

        :param job_id: job identifier
        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """

        with self._db() as db:
            db.update(update_dict, tinydb.where('identifier') == job_id)

        return True

    def delete_job(self, job_id: str) -> bool:
        """
        Deletes a job

        :param job_id: job identifier

        :raises JobNotFoundError: if the job_id does not correspond to a
                                  known job
        :return `bool` of status result
        """
        # delete result file if present
        job_result = self.get_job(job_id)
        location = job_result.get('location')
        if location and self.output_dir is not None:
            Path(location).unlink()

        with self._db() as db:
            removed = bool(db.remove(tinydb.where('identifier') == job_id))

        return removed

    def get_job(self, job_id: str) -> dict:
        """
        Get a single job

        :param job_id: job identifier

        :raises JobNotFoundError: if the job_id does not correspond to a
                                  known job
        :returns: `dict`  # `pygeoapi.process.manager.Job`
        """

        query = tinydb.Query()
        with self._db() as db:
            found = db.search(query.identifier == job_id)
        if found is not None:
            try:
                return found[0]
            except IndexError:
                raise JobNotFoundError()
        else:
            raise JobNotFoundError()

    def get_job_result(self, job_id: str) -> Tuple[str, Any]:
        """
        Get a job's status, and actual output of executing the process

        :param job_id: job identifier

        :raises JobNotFoundError: if the job_id does not correspond to a
                                  known job
        :raises JobResultNotFoundError: if the job-related result cannot
                                        be returned
        :returns: `tuple` of mimetype and raw output
        """

        job_result = self.get_job(job_id)
        location = job_result.get('location')
        mimetype = job_result.get('mimetype')
        job_status = JobStatus[job_result['status']]

        if not job_status == JobStatus.successful:
            # Job is incomplete
            return (None,)
        if not location:
            LOGGER.warning(f'job {job_id!r} -  unknown result location')
            raise JobResultNotFoundError()
        else:
            try:
                location = Path(location)
                with location.open('r', encoding='utf-8') as filehandler:
                    result = json.load(filehandler)
            except (TypeError, FileNotFoundError, json.JSONDecodeError):
                raise JobResultNotFoundError()
            else:
                return mimetype, result

    def __repr__(self):
        return f'<TinyDBManager> {self.name}'
