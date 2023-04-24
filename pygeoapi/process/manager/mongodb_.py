# =================================================================
#
# Authors: Alexander Pilz <a.pilz@52north.org>
#
# Copyright (c) 2023 Alexander Pilz
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
import traceback
from typing import List, Optional, Tuple

import pydantic
from pymongo import MongoClient

from pygeoapi.process import exceptions
from pygeoapi.models.processes import JobStatusInfoInternal
from pygeoapi.models.processes import (
    JobStatus,
)
from pygeoapi.process.manager.base import BaseManager

LOGGER = logging.getLogger(__name__)


class MongoDBManager(BaseManager):
    is_async = True

    def _connect(self):
        try:
            client = MongoClient(self.connection)
            self.db = client
            LOGGER.info("JOBMANAGER - MongoDB connected")
            return True
        except Exception:
            self.destroy()
            LOGGER.error("JOBMANAGER - connect error",
                         exc_info=(traceback))
            return False

    def destroy(self):
        try:
            self.db.close()
            LOGGER.info("JOBMANAGER - MongoDB disconnected")
            return True
        except Exception:
            self.destroy()
            LOGGER.error("JOBMANAGER - destroy error",
                         exc_info=(traceback))
            return False

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
        # TODO: Implement filtering
        # TODO: Implement limit
        # TODO: Implement offset
        # TODO: Implement sorting
        # TODO: Implement returning total number of records and
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            if status is not None:
                db_jobs = list(collection.find({}, {"status": status[0]}))
            else:
                # FIXME: According of OAPI - Processes spec, Requirement 75:
                #
                # > If the status parameter is not specified then only jobs
                # > that are running (status: running) or have completed
                # > execution (successful, failed or dismissed) SHALL be
                # > considered for inclusion in the response.
                db_jobs = list(collection.find({}))

            result = []
            for db_job in db_jobs:
                try:
                    job = JobStatusInfoInternal(**db_job)
                except pydantic.ValidationError:
                    LOGGER.warning(
                        f"Unable to parse db_job {db_job} - skipping...")
                else:
                    result.append(job)

            LOGGER.info("JOBMANAGER - MongoDB jobs queried")
            return 0, result
        except Exception as err:
            LOGGER.error("JOBMANAGER - get_jobs error",
                         exc_info=(traceback))
            raise exceptions.JobError('Could not retrieve jobs') from err

    def add_job(self, job_status: JobStatusInfoInternal):
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            doc_id = collection.insert_one(
                job_status.dict(by_alias=True, exclude_none=True))
            LOGGER.info("JOBMANAGER - MongoDB job added")
            return doc_id
        except Exception as err:
            LOGGER.error("JOBMANAGER - add_job error",
                         exc_info=(traceback))
            raise exceptions.JobError('Could not persist job details') from err

    def update_job(self, job_status: JobStatusInfoInternal):
        job_status_info = self.get_job(job_status.job_id)
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            entry = collection.find_one({"identifier": job_status_info.job_id})
            collection.update_one(
                entry,
                {"$set": job_status.dict(by_alias=True, exclude_none=True)}
            )
            LOGGER.info("JOBMANAGER - MongoDB job updated")
            return True
        except Exception as err:
            LOGGER.error("JOBMANAGER - MongoDB update_job error",
                         exc_info=(traceback))
            raise exceptions.JobError('Could not update job') from err

    def delete_job(self, job_id):
        job_status_info = self.get_job(job_id)
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            collection.delete_one({"identifier": job_id})
            LOGGER.info("JOBMANAGER - MongoDB job deleted")
            return JobStatusInfoInternal(
                **job_status_info.dict(by_alias=True, exclude_none=True),
                status=JobStatus.dismissed,
                message='Job dismissed successfully'
            )
        except Exception as err:
            LOGGER.error("JOBMANAGER - MongoDB delete_job error",
                         exc_info=(traceback))
            raise exceptions.JobError('Could not delete job') from err

    def get_job(self, job_id):
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            entry = collection.find_one({"identifier": job_id})
            LOGGER.info("JOBMANAGER - MongoDB job queried")
            return JobStatusInfoInternal(**entry)
        except Exception as err:
            LOGGER.error("JOBMANAGER - MongoDB get_job error",
                         exc_info=(traceback))
            raise exceptions.JobError(
                f'Could not retrieve job {job_id} - {str(err)}') from err

    def __repr__(self):
        return f'<MongoDBManager> {self.name}'
