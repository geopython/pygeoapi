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
import json
import logging
import traceback

from pymongo import MongoClient

from pygeoapi.process.base import (
    JobNotFoundError,
    JobResultNotFoundError,
)
from pygeoapi.process.manager.base import BaseManager

LOGGER = logging.getLogger(__name__)


class MongoDBManager(BaseManager):
    def __init__(self, manager_def):
        super().__init__(manager_def)
        self.is_async = True
        self.supports_subscribing = True

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

    def get_jobs(self, status=None):
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            if status is not None:
                jobs = list(collection.find({}, {"status": status}))
            else:
                jobs = list(collection.find({}))
            LOGGER.info("JOBMANAGER - MongoDB jobs queried")
            return jobs
        except Exception:
            LOGGER.error("JOBMANAGER - get_jobs error",
                         exc_info=(traceback))
            return False

    def add_job(self, job_metadata):
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            doc_id = collection.insert_one(job_metadata)
            LOGGER.info("JOBMANAGER - MongoDB job added")
            return doc_id
        except Exception:
            LOGGER.error("JOBMANAGER - add_job error",
                         exc_info=(traceback))
            return False

    def update_job(self, job_id, update_dict):
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            entry = collection.find_one({"identifier": job_id})
            collection.update_one(entry, {"$set": update_dict})
            LOGGER.info("JOBMANAGER - MongoDB job updated")
            return True
        except Exception:
            LOGGER.error("JOBMANAGER - MongoDB update_job error",
                         exc_info=(traceback))
            return False

    def delete_job(self, job_id):
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            collection.delete_one({"identifier": job_id})
            LOGGER.info("JOBMANAGER - MongoDB job deleted")
            return True
        except Exception:
            LOGGER.error("JOBMANAGER - MongoDB delete_job error",
                         exc_info=(traceback))
            return False

    def get_job(self, job_id):
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            entry = collection.find_one({"identifier": job_id})
            LOGGER.info("JOBMANAGER - MongoDB job queried")
            return entry
        except Exception as err:
            LOGGER.error("JOBMANAGER - MongoDB get_job error",
                         exc_info=(traceback))
            raise JobNotFoundError() from err

    def get_job_result(self, job_id):
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            entry = collection.find_one({"identifier": job_id})
            if entry["status"] != "successful":
                LOGGER.info("JOBMANAGER - job not finished or failed")
                return (None,)
            with open(entry["location"], "r") as file:
                data = json.load(file)
            LOGGER.info("JOBMANAGER - MongoDB job result queried")
            return entry["mimetype"], data
        except Exception as err:
            LOGGER.error("JOBMANAGER - MongoDB get_job_result error",
                         exc_info=(traceback))
            raise JobResultNotFoundError() from err

    def __repr__(self):
        return f'<MongoDBManager> {self.name}'
