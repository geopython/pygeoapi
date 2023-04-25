# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2022 Tom Kralidis
# Copyright (c) 2023 Ricardo Garcia Silva
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
import logging
import operator
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pydantic
import tinydb
from tinydb.storages import MemoryStorage

from pygeoapi.process import exceptions
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.models.processes import (
    JobStatus,
    JobStatusInfoInternal
)
from pygeoapi.util import DATETIME_FORMAT

LOGGER = logging.getLogger(__name__)


class TinyDBManager(BaseManager):
    """TinyDB Manager"""
    is_async = True

    _JOB_ID = "jobID"
    _JOB_SORT_KEY = "created"

    def _connect(self, mode: str = 'r') -> bool:
        """
        connect to manager

        :returns: `bool` of status of result
        """

        if self.connection is not None:
            db = tinydb.TinyDB(self.connection)
        else:
            db = tinydb.TinyDB(storage=MemoryStorage)
        self.db = db

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
        Get process jobs, optionally filtered by relevant parameters.

        The filtering parameters follow their respective definition in
        OAProc spec, as per:

        https://docs.ogc.org/is/18-062r2/18-062r2.html#toc49

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

        :raise: JobError: if the job list cannot be retrieved
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

    def _serialize_job_status_info(
            self, job_status: JobStatusInfoInternal) -> Dict:
        serialized_properties = {
            'created': job_status.created.strftime(
                DATETIME_FORMAT) if job_status.created is not None else None,
            'started': job_status.started.strftime(
                DATETIME_FORMAT) if job_status.started is not None else None,
            'finished': job_status.finished.strftime(
                DATETIME_FORMAT) if job_status.finished is not None else None,
            'updated': job_status.updated.strftime(
                DATETIME_FORMAT) if job_status.updated is not None else None,
            'status': job_status.status.value,
            'negotiated_execution_mode': (
                job_status.negotiated_execution_mode.value if
                job_status.negotiated_execution_mode is not None else None
            ),
            'requested_response_type': (
                job_status.requested_response_type.value if
                job_status.requested_response_type is not None else None
            ),
        }
        serialized_properties = {
            k: v for k, v in serialized_properties.items() if v is not None}
        return {
            **serialized_properties,
            **job_status.dict(
                by_alias=True,
                exclude={*serialized_properties.keys()},
                exclude_none=True
            )
        }

    def add_job(self, job_status: JobStatusInfoInternal) -> str:
        """
        Add a job

        :param job_status: job status

        :raise: JobError: if job cannot be persisted
        :returns: `str` added job identifier
        """

        self._connect(mode='w')
        db_job = self._serialize_job_status_info(job_status)
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

        :raise JobError: if the job cannot be updated
        :returns: `bool` of status result
        """

        self._connect(mode='w')
        db_job = self._serialize_job_status_info(job_status)
        self.db.update(
            db_job,
            tinydb.where(self._JOB_ID) == job_status.job_id
        )
        self.db.close()
        return True

    def delete_job(self, job_id: str) -> JobStatusInfoInternal:
        """
        Deletes a job and associated results, if any.

        :param job_id: job identifier

        :raise JobNotFoundError: If job_id does not correspond to a known job
        :raise JobError: If the job cannot be deleted
        :returns: job status info of the dismissed job
        """

        job_status = self.get_job(job_id)
        for generated_output_detail in job_status.generated_outputs.values():
            # TODO: guard for deletion errors
            Path(generated_output_detail.location).unlink(missing_ok=True)
        self._connect(mode='w')
        self.db.remove(tinydb.where(self._JOB_ID) == job_id)
        self.db.close()

        return JobStatusInfoInternal(
            **job_status.dict(by_alias=True, exclude_none=True),
            status=JobStatus.dismissed,
            message='Job dismissed successfully'
        )

    def get_job(self, job_id: str) -> JobStatusInfoInternal:
        """
        Get a single job

        :param job_id: job identifier

        :raise JobNotFoundError: If job_id does not correspond to a known job
        :raise JobError: If the job cannot be retrieved
        :returns: job status info
        """

        self._connect()
        query = tinydb.Query()
        result = self.db.search(query[self._JOB_ID] == job_id)
        self.db.close()
        if len(result) > 0:
            job = JobStatusInfoInternal(**result[0])
        else:
            raise exceptions.JobNotFoundError('Invalid job_id')
        return job

    def __repr__(self):
        return f'<TinyDBManager> {self.name}'
