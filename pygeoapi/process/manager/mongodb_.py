# -*- coding: utf-8 -*-
"""
Created on Fri Feb 24 14:31:04 2023

@author: Alexander Pilz for 52°North Spatial Information Research GmbH
@contact: info@52north.org or a.pilz@52north.org
"""
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import JobStatus
from pymongo import MongoClient
import traceback
import json
import logging

LOGGER = logging.getLogger(__name__)
class MongoDBManager(BaseManager):
    def __init__(self, manager_def):
        super().__init__(manager_def)
        self.is_async = True

    def _connect(self):
        try:
            client = MongoClient(self.connection)
            self.db = client
            LOGGER.info("JOBMANAGER - MongoDB connected")
            return True
        except:
            self.destroy()
            LOGGER.error("JOBMANAGER - connect error",
                 exc_info=(traceback))
            return False

    def destroy(self):
        try:
            self.db.close()
            LOGGER.info("JOBMANAGER - MongoDB disconnected")
            return True
        except:
            self.destroy()
            LOGGER.error("JOBMANAGER - destroy error",
                 exc_info=(traceback))
            return False

    def get_jobs(self, status=None):
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            if status != None:
                jobs = list(collection.find({}, {"status": status}))
            else:
                jobs = list(collection.find({}))
            LOGGER.info("JOBMANAGER - MongoDB jobs queried")
            #self.destroy()
            return jobs
        except:
            #self.destroy()
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
            #self.destroy()
            return doc_id
        except:
            #self.destroy()
            LOGGER.error("JOBMANAGER - add_job error",
                 exc_info=(traceback))
            return False

    def update_job(self, job_id, update_dict):
        try:            
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            entry = collection.find_one( {"identifier" : job_id})
            collection.update_one(entry, {"$set": update_dict})
            LOGGER.info("JOBMANAGER - MongoDB job updated")
            #self.destroy()
            return True
        except:
            #self.destroy()
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
            #self.destroy()
            return True
        except:
            #self.destroy()
            LOGGER.error("JOBMANAGER - MongoDB delete_job error",
                 exc_info=(traceback))
            return False

    def get_job(self, job_id):
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            entry = collection.find_one( {"identifier" : job_id})
            LOGGER.info("JOBMANAGER - MongoDB job queried")
            #self.destroy()
            return entry
        except:
            #self.destroy()
            LOGGER.error("JOBMANAGER - MongoDB get_job error",
                 exc_info=(traceback))
            return False

    def get_job_result(self, job_id):
        try:
            self._connect()
            database = self.db.job_manager_pygeoapi
            collection = database.jobs
            entry = collection.find_one( {"identifier" : job_id})
            if entry["status"] != "successful":
                LOGGER.info("JOBMANAGER - job not finished or failed")
                return (None,)
            with open(entry["location"], "r") as file:
                data = json.load(file)
            #self.destroy()
            LOGGER.info("JOBMANAGER - MongoDB job result queried")
            return entry["mimetype"], data
        except:
            #self.destroy()
            LOGGER.error("JOBMANAGER - MongoDB get_job_result error",
                 exc_info=(traceback))
            return False

    def __repr__(self):
        return '<MongoDBManager> {}'.format(self.name)
