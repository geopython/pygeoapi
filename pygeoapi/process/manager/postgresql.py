# =================================================================
#
# Authors: Francesco Martinelli <francesco.martinelli@ingv.it>
#
# Copyright (c) 2024 Francesco Martinelli
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

# Requires postgresql database structure.
# Create the database:
# e.g.
# CREATE DATABASE test WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE = 'en_US.UTF-8';
# ALTER DATABASE test OWNER TO postgres;
#
# Import dump:
# psql -U postgres -h 127.0.0.1 -p 5432 test <
#   tests/data/postgres_manager_full_structure.backup.sql

import json
import logging
from pathlib import Path
from typing import Any, Tuple

import psycopg2
import psycopg2.extras

from pygeoapi.process.manager.base import BaseManager
from pygeoapi.process.base import (
    JobNotFoundError,
    JobResultNotFoundError,
    ProcessorGenericError,
)
from pygeoapi.util import JobStatus


LOGGER = logging.getLogger(__name__)


class PostgreSQLManager(BaseManager):
    """PostgreSql Manager"""

    def __init__(self, manager_def: dict):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.postgresqs.PostgreSQLManager`
        """

        super().__init__(manager_def)
        self.is_async = True
        self.supports_subscribing = True

        self.__database_connection_parameters = manager_def['connection']
        try:
            # Test connection parameters:
            test_query = """SELECT version()"""
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(test_query)
                    cur.fetchone()
        except Exception as err:
            LOGGER.error(f'Test connecting to DB failed: {err}')
            raise ProcessorGenericError('Test connecting to DB failed.')

    def get_db_connection(self):
        """
        Get and return a new connection to the DB.
        """
        if isinstance(self.__database_connection_parameters, str):
            conn = psycopg2.connect(self.__database_connection_parameters)
        else:
            conn = psycopg2.connect(**self.__database_connection_parameters)

        return conn

    def get_jobs(self, status: JobStatus = None) -> list:
        """
        Get jobs

        :param status: job status (accepted, running, successful,
                        failed, results) (default is all)

        :returns: 'list` of jobs (type (default='process'), identifier,
            status, process_id, job_start_datetime, job_end_datetime, location,
            mimetype, message, progress)
        """

        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                query_select = """SELECT * FROM jobs """
                if status is not None:
                    query_select = query_select + "WHERE status = %s"
                    query_params = [status.value]
                else:
                    query_params = []
                cur.execute(query_select, query_params)
                return cur.fetchall()

    def add_job(self, job_metadata: dict) -> str:
        """
        Add a job

        :param job_metadata: `dict` of job metadata

        :returns: identifier of added job
        """

        query_insert = """INSERT INTO jobs(
            type, process_id, identifier, status, message,
            progress, job_start_datetime, job_end_datetime
            ) VALUES(%(type)s, %(process_id)s, %(identifier)s, %(status)s,
                     %(message)s, %(progress)s, %(job_start_datetime)s,
                     %(job_end_datetime)s);"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query_insert, job_metadata)
                conn.commit()
        return job_metadata['identifier']

    def update_job(self, job_id: str, update_dict: dict) -> bool:
        """
        Updates a job

        :param job_id: job identifier
        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """

        query_update = "UPDATE jobs SET ("
        keys_to_update = 0
        for key in update_dict.keys():
            if keys_to_update:
                query_update = query_update + (", ")
            query_update = query_update + key
            keys_to_update = keys_to_update + 1

        query_update = query_update + ") = ("
        keys_to_update = 0
        for key in update_dict.keys():
            if keys_to_update:
                query_update = query_update + (", ")
            query_update = query_update + "%(" + key + ")s"
            keys_to_update = keys_to_update + 1
        query_update = query_update + (") WHERE identifier = %(identifier)s")

        update_dict['identifier'] = job_id

        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query_update, update_dict)
                rowcount = cur.rowcount
                conn.commit()

        return rowcount == 1

    def get_job(self, job_id: str) -> dict:
        """
        Get a single job

        :param job_id: job identifier

        :raises JobNotFoundError: if the job_id does not correspond to a
                                  known job
        :returns: `dict`  # `pygeoapi.process.manager.Job`
        """

        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                query_select = \
                    """SELECT * FROM jobs WHERE identifier = %s"""
                query_params = [job_id]
                cur.execute(query_select, query_params)
                found = cur.fetchone()

        if found is not None:
            return found
        else:
            raise JobNotFoundError()

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
            try:
                Path(location).unlink()
            except FileNotFoundError:
                pass

        query_delete = "DELETE FROM jobs WHERE identifier = %s"
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query_delete, [job_id])
                rowcount = cur.rowcount
                conn.commit()

        return rowcount == 1

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

        if job_status != JobStatus.successful:
            # Job is incomplete
            return (None,)
        if not location:
            LOGGER.warning(f'job {job_id!r} -  unknown result location')
            raise JobResultNotFoundError()
        else:
            try:
                location = Path(location)
                with location.open(encoding='utf-8') as fh:
                    result = json.load(fh)
            except (TypeError, FileNotFoundError, json.JSONDecodeError):
                raise JobResultNotFoundError()
            else:
                return mimetype, result

    def __repr__(self):
        return f'<PostgreSQLManager> {self.name}'
