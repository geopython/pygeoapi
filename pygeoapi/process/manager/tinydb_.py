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

    _JOB_ID = "jobID"
    _JOB_SORT_KEY = "created"

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
        Get jobs

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

        :returns: a two-element tuple with the total number of jobs that
                  match the filtering parameters and a list of job statuses
        """

        self._connect()
        JobSummary = tinydb.Query()
        filters = []
        if process_id is not None:
            filters.append(JobSummary.process_id.one_of(process_id))
        if status is not None:
            filters.append(JobSummary.status.one_of(status.value))
        else:
            # According to OAPI - Processes spec, Requirement 75:
            #
            # > If the status parameter is not specified then only jobs that
            # > are running (status: running) or have completed execution
            # > (successful, failed or dismissed) SHALL be considered for
            # > inclusion in the response.
            filters.append(
                JobSummary.status.one_of(
                    [
                        JobStatus.dismissed.value,
                        JobStatus.failed.value,
                        JobStatus.running.value,
                        JobStatus.successful.value,
                    ]
                )
            )
        if date_time is not None:  # TODO: Implement this filter
            pass
        if min_duration_seconds is not None:  # TODO: Implement this filter
            pass
        if max_duration_seconds is not None:  # TODO: Implement this filter
            pass
        if len(filters) > 0:
            all_filtered_jobs = self.db.search(
                functools.reduce(operator.and_, filters))
        else:
            all_filtered_jobs = self.db.all()
        db_jobs = sorted(
            all_filtered_jobs,
            key=lambda obj: obj.get(self._JOB_SORT_KEY) or "",
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
        self.db.close()
        return len(all_filtered_jobs), result

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

    def update_job(
            self,
            job_status: JobStatusInfoInternal
    ) -> bool:
        """
        Updates a job

        :param job_status: property updates for the job status info

        :returns: `bool` of status result
        """

        self._connect(mode='w')
        temporal_properties = {
            "created": job_status.created.strftime(
                DATETIME_FORMAT) if job_status.created is not None else None,
            "started": job_status.started.strftime(
                DATETIME_FORMAT) if job_status.started is not None else None,
            "finished": job_status.finished.strftime(
                DATETIME_FORMAT) if job_status.finished is not None else None,
            "updated": job_status.updated.strftime(
                DATETIME_FORMAT) if job_status.updated is not None else None,
        }
        temporal_properties = {
            k: v for k, v in temporal_properties.items() if v is not None}
        db_job = {
            **temporal_properties,
            **job_status.dict(
                by_alias=True,
                exclude={*temporal_properties.keys()},
                exclude_none=True
            )
        }
        self.db.update(
            db_job,
            tinydb.where(self._JOB_ID) == job_status.job_id
        )
        self.db.close()
        return True

    def delete_job(self, job_id: str) -> bool:
        """
        Deletes a job

        :param job_id: job identifier

        :return `bool` of status result
        """
        # delete result file if present
        job_status = self.get_job(job_id)
        if job_status:
            if job_status.location and self.output_dir is not None:
                Path(job_status.location).unlink()

        self._connect(mode='w')
        removed = bool(self.db.remove(tinydb.where(self._JOB_ID) == job_id))
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
        result = self.db.search(query[self._JOB_ID] == job_id)
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

        job_status = self.get_job(job_id)
        if job_status is None:  # job does not exist
            result = None
        elif job_status.status != JobStatus.successful:  # Job is incomplete
            result = None
        elif job_status.location is None:
            # Job data was not written for some reason
            # TODO log/raise exception?
            result = None
        else:
            result = json.loads(Path(job_status.location).read_text())
        return "application/json", result

    def __repr__(self):
        return f'<TinyDBManager> {self.name}'
