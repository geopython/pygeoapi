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

try:
    import fcntl
except ModuleNotFoundError:
    # When on Windows, fcntl does not exist and file locking is automatic
    fcntl = None

import functools
import json
import logging
import operator
from pathlib import Path
from typing import Any, List, Optional, Tuple

import pydantic
import tinydb

from pygeoapi.models.processes import JobStatusInfoInternal
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import DATETIME_FORMAT, JobStatus

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

    def _connect(self, mode: str = 'r') -> bool:
        """
        connect to manager

        :returns: `bool` of status of result
        """

        self.db = tinydb.TinyDB(self.connection)

        if mode == 'w' and fcntl is not None:
            fcntl.lockf(self.db.storage._handle, fcntl.LOCK_EX)

        return True

    def destroy(self) -> bool:
        """
        Destroy manager

        :returns: `bool` status of result
        """

        self.db.purge()
        self.db.close()
        return True

    def get_jobs(
            self,
            type_: Optional[str] = None,
            process_id: Optional[str] = None,
            status: Optional[JobStatus] = None,
            date_time: Optional[str] = None,
            min_duration_seconds: Optional[int] = None,
            max_duration_seconds: Optional[int] = None,
            limit: Optional[int] = 10,
            offset: Optional[int] = 0,
    ) -> Tuple[int, int, List[JobStatusInfoInternal]]:
        """
        Get jobs

        :param type_: process type
        :param process_id: identifier of the parent process of jobs
        :param status: job status (accepted, running, successful,
                       failed, results) (default is all)
        :param date_time: temporal interval that a job's `create` property
                          must intersect
        :param min_duration_seconds: minimum duration of jobs
        :param max_duration_seconds: maximum duration of jobs
        :param limit: number of jobs to return
        :param offset: Offset for selecting which jobs to return

        :returns: a three-element tuple with the total number of jobs, the
                  total number of jobs that match the filtering parameters
                  and a list of job statuses
        """

        self._connect()
        JobSummary = tinydb.Query()
        filters = []
        if process_id is not None:
            filters.append(JobSummary.process_id == process_id)
        if status is not None:
            filters.append(JobSummary.status == status.value)
        else:
            # According of OAPI - Processes spec, Requirement 75:
            #
            # > If the status parameter is not specified then only jobs that
            # > are running (status: running) or have completed execution
            # > (successful, failed or dismissed) SHALL be considered for
            # > inclusion in the response.
            filters.append(
                JobSummary.status.any(
                    [
                        JobStatus.dismissed.value,
                        JobStatus.failed.value,
                        JobStatus.running.value,
                        JobStatus.successful.value,
                    ]
                )
            )
        if date_time is not None:
            pass
        if min_duration_seconds is not None:
            pass
        if max_duration_seconds is not None:
            pass
        if len(filters) > 1:
            all_filtered_jobs = self.db.search(
                functools.reduce(operator.and_, filters))
        else:
            all_filtered_jobs = self.db.all()
        db_jobs = sorted(
            all_filtered_jobs,
            key=lambda obj: obj.get("created"),
            reverse=True
        )[offset:offset+limit]

        result = []
        for db_job in db_jobs:
            try:
                job = JobStatusInfoInternal(**db_job)
            except pydantic.ValidationError:
                LOGGER.warning(
                    f"Unable to parse db_job {db_job} - skipping...")
            else:
                result.append(job)
        all_jobs = len(self.db)
        self.db.close()
        return all_jobs, len(all_filtered_jobs), result

    def add_job(self, job_status: JobStatusInfoInternal) -> str:
        """
        Add a job

        :param job_status: job status

        :returns: identifier of added job
        """

        self._connect(mode='w')
        db_job = {
            "created": (
                job_status.created.strftime(DATETIME_FORMAT)
                if job_status.created is not None else None
            ),
            "started": (
                job_status.started.strftime(DATETIME_FORMAT)
                if job_status.started is not None else None
            ),
            "finished": (
                job_status.finished.strftime(DATETIME_FORMAT)
                if job_status.finished is not None else None
            ),
            "updated": (
                job_status.updated.strftime(DATETIME_FORMAT)
                if job_status.updated is not None else None
            ),
            **job_status.dict(
                by_alias=True,
                exclude={"created", "started", "finished", "updated"}
            )
        }
        doc_id = self.db.insert(db_job)
        self.db.close()

        return doc_id  # noqa

    def update_job(self, job_id: str, update_dict: dict) -> bool:
        """
        Updates a job

        :param job_id: job identifier
        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """

        self._connect(mode='w')
        self.db.update(update_dict, tinydb.where('identifier') == job_id)
        self.db.close()

        return True

    def delete_job(self, job_id: str) -> bool:
        """
        Deletes a job

        :param job_id: job identifier

        :return `bool` of status result
        """
        # delete result file if present
        job_result = self.get_job(job_id)
        if job_result:
            location = job_result.get('location')
            if location and self.output_dir is not None:
                Path(location).unlink()

        self._connect(mode='w')
        removed = bool(self.db.remove(tinydb.where('identifier') == job_id))
        self.db.close()

        return removed

    def get_job(self, job_id: str) -> Optional[JobStatusInfoInternal]:
        """
        Get a single job

        :param job_id: job identifier

        :returns: job status info
        """

        self._connect()
        query = tinydb.Query()
        result = self.db.search(query["jobID"] == job_id)
        if len(result) > 0:
            job = JobStatusInfoInternal(**result[0])
        else:
            job = None
        self.db.close()
        return job

    def get_job_result(self, job_id: str) -> Tuple[str, Any]:
        """
        Get a job's status, and actual output of executing the process

        :param job_id: job identifier

        :returns: `tuple` of mimetype and raw output
        """

        job_result = self.get_job(job_id)
        if not job_result:
            # job does not exist
            return None

        location = job_result.get('location')
        mimetype = job_result.get('mimetype')
        job_status = JobStatus[job_result['status']]

        if not job_status == JobStatus.successful:
            # Job is incomplete
            return (None,)
        if not location:
            # Job data was not written for some reason
            # TODO log/raise exception?
            return (None,)
        else:
            location = Path(location)

        with location.open('r', encoding='utf-8') as filehandler:
            result = json.load(filehandler)

        return mimetype, result

    def __repr__(self):
        return f'<TinyDBManager> {self.name}'
