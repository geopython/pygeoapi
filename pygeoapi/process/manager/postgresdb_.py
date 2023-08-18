# =================================================================
#
# Authors: Alexandre Roy <alexandre.roy@fujitsu.com>
#
# Copyright (c) 2023 Alexandre Roy
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
from pathlib import Path
from typing import (Any, Tuple)

import psycopg2
import psycopg2.extras
from psycopg2 import sql

from pygeoapi.process.base import (
    JobNotFoundError,
    JobResultNotFoundError,
)
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import JobStatus

LOGGER = logging.getLogger(__name__)


class PostgresDBManager(BaseManager):
    """PostgresDB Manager"""

    def __init__(self, manager_def: dict):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.base.BaseManager`
        """

        super().__init__(manager_def)
        self.is_async = True
        self.host = manager_def['connection']['host']
        self.port = manager_def['connection']['port']
        self.dbname = manager_def['connection']['dbname']
        self.user = manager_def['connection']['user']
        self.password = manager_def['connection']['password']

        # Table specs
        self.table_jobs = {
            'table_name': "jobs",
            'field_identifier': "identifier",
            'field_process_id': "process_id",
            'field_status': "status",
            'field_progress': "progress",
            'field_date_started': "job_start_datetime",
            'field_date_ended': "job_end_datetime",
            'field_location': "location",
            'field_mimetype': "mimetype",
            'field_message': "message",
            'field_result': "result"
        }

    def open_conn(self):
        """
        Returns a connection to the database
        """

        return psycopg2.connect(host=self.host, port=self.port,
                                dbname=self.dbname, user=self.user,
                                password=self.password, sslmode="allow")

    def destroy(self) -> bool:
        """
        Destroy manager

        :returns: `bool` status of result
        """

        with self.open_conn() as conn:
            # Open a cursor
            with conn.cursor() as cur:
                str_query = "DELETE FROM {table}"

                # Query in the database
                query = sql.SQL(str_query).format(
                    table=sql.Identifier(self.dbname,
                                         self.table_jobs['table_name'])
                )

                # Execute cursor
                cur.execute(query)
            conn.commit()
        return True

    def get_jobs(self, status: JobStatus = None) -> list:
        """
        Get jobs

        :param status: job status (accepted, running, successful,
                       failed, results) (default is all)

        :returns: 'list` of jobs (identifier, status, process identifier)
        """

        with self.open_conn() as conn:
            # Open a cursor
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:  # noqa
                if status:
                    str_query = """SELECT * FROM {table}
                                   WHERE {field_status} = %s
                                   ORDER BY {field_order} DESC"""

                    # Query in the database
                    query = sql.SQL(str_query).format(
                        table=sql.Identifier(self.dbname,
                                             self.table_jobs['table_name']),
                        field_order=sql.Identifier(self.table_jobs['field_date_started']))  # noqa

                    # Execute cursor and fetch
                    cur.execute(query, (status,))

                else:
                    str_query = """SELECT *
                                   FROM {table}
                                   ORDER BY {field_order} DESC"""

                    # Query in the database
                    query = sql.SQL(str_query).format(
                        table=sql.Identifier(self.dbname,
                                             self.table_jobs['table_name']),
                        field_order=sql.Identifier(self.table_jobs['field_date_started']))  # noqa

                    # Execute cursor and fetch
                    cur.execute(query)

                # Fetch all
                return cur.fetchall()

    def add_job(self, job_metadata: dict) -> str:
        """
        Add a job

        :param job_metadata: `dict` of job metadata

        :returns: identifier of added job
        """

        with self.open_conn() as conn:
            # Open a cursor
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:  # noqa
                str_query = """INSERT INTO {table} (
                                    {field_identifier},
                                    {field_process_id},
                                    {field_status},
                                    {field_progress},
                                    {field_job_start_datetime},
                                    {field_location},
                                    {field_mimetype},
                                    {field_message})
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                            """

                # Query in the database
                query = sql.SQL(str_query).format(
                    table=sql.Identifier(self.dbname, self.table_jobs['table_name']),  # noqa
                    field_identifier=sql.Identifier(self.table_jobs['field_identifier']),  # noqa
                    field_process_id=sql.Identifier(self.table_jobs['field_process_id']),  # noqa
                    field_status=sql.Identifier(self.table_jobs['field_status']),  # noqa
                    field_progress=sql.Identifier(self.table_jobs['field_progress']),  # noqa
                    field_job_start_datetime=sql.Identifier(self.table_jobs['field_date_started']),  # noqa
                    field_location=sql.Identifier(self.table_jobs['field_location']),  # noqa
                    field_mimetype=sql.Identifier(self.table_jobs['field_mimetype']),  # noqa
                    field_message=sql.Identifier(self.table_jobs['field_message']))  # noqa

                # Execute cursor and fetch
                cur.execute(query, (job_metadata[self.table_jobs['field_identifier']],  # noqa
                                    job_metadata[self.table_jobs['field_process_id']],  # noqa
                                    job_metadata[self.table_jobs['field_status']],  # noqa
                                    job_metadata[self.table_jobs['field_progress']],  # noqa
                                    job_metadata[self.table_jobs['field_date_started']],  # noqa
                                    job_metadata[self.table_jobs['field_location']],  # noqa
                                    job_metadata[self.table_jobs['field_mimetype']],  # noqa
                                    job_metadata[self.table_jobs['field_message']]))  # noqa
            conn.commit()
            return job_metadata['identifier']

    def update_job(self, job_id: str, update_dict: dict) -> bool:
        """
        Updates a job

        :param job_id: job identifier
        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """

        with self.open_conn() as conn:
            # Open a cursor
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:  # noqa
                str_query = "UPDATE {table} SET "
                i = 1
                values = []
                for k in update_dict:
                    str_query = str_query + f" {k} = %s,"
                    values.append(update_dict[k])
                    i = i+1
                str_query = str_query[:-1]
                str_query = str_query + " WHERE {field_identifier}=%s"
                values.append(job_id)

                # Query in the database
                query = sql.SQL(str_query).format(
                    table=sql.Identifier(self.dbname, self.table_jobs['table_name']),  # noqa
                    field_identifier=sql.Identifier(self.table_jobs['field_identifier']))  # noqa

                # Execute cursor and fetch
                cur.execute(query, values)
            conn.commit()
            return True

    def delete_job(self, job_id: str) -> bool:
        """
        Deletes a job

        :param job_id: job identifier

        :raises: JobNotFoundError: if the job_id does not correspond to a
            known job
        :return `bool` of status result
        """
        # delete result file if present
        job_result = self.get_job(job_id)

        if job_result:
            with self.open_conn() as conn:
                # Open a cursor
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:  # noqa
                    str_query = """DELETE FROM {table}
                                   WHERE {field_identifier}=%s"""

                    # Query in the database
                    query = sql.SQL(str_query).format(
                        table=sql.Identifier(self.dbname, self.table_jobs['table_name']),  # noqa
                        field_identifier=sql.Identifier(self.table_jobs['field_identifier']))  # noqa

                    # Execute cursor and fetch
                    cur.execute(query, (job_id,))
                conn.commit()
                return True
        else:
            raise JobNotFoundError()

    def get_job(self, job_id: str) -> dict:
        """
        Get a single job

        :param job_id: job identifier

        :raises: JobNotFoundError: if the job_id does not correspond to a
            known job
        :returns: `dict`  # `pygeoapi.process.manager.Job`
        """

        with self.open_conn() as conn:
            # Open a cursor
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:  # noqa
                str_query = """SELECT * FROM {table}
                               WHERE {field_identifier}=%s"""

                # Query in the database
                query = sql.SQL(str_query).format(
                    table=sql.Identifier(self.dbname, self.table_jobs['table_name']),  # noqa
                    field_identifier=sql.Identifier(self.table_jobs['field_identifier']))  # noqa

                # Execute cursor and fetch
                cur.execute(query, (job_id,))

                # Fetch one
                res = cur.fetchone()
                if res:
                    return res
                raise JobNotFoundError()

    def get_job_result(self, job_id: str) -> Tuple[str, Any]:
        """
        Get a job's status, and actual output of executing the process

        :param job_id: job identifier

        :raises: JobNotFoundError: if the job_id does not correspond to a
            known job
        :raises: JobResultNotFoundError: if the job-related result cannot
            be returned
        :returns: `tuple` of mimetype and raw output
        """

        job_result = self.get_job(job_id)

        # If job was found
        if job_result:
            # Read the status
            job_status = JobStatus[job_result[self.table_jobs['field_status']]]  # noqa

            # If job is complete
            if job_status == JobStatus.successful:
                # Read the mimetype
                mimetype = job_result[self.table_jobs['field_mimetype']]

                # Read the location
                location = job_result[self.table_jobs['field_location']]

                # If the job is in the database
                if self.result_in_db:
                    # Read the result
                    result = json.loads(job_result[self.table_jobs['field_result']])  # noqa
                    return mimetype, result

                elif location:
                    # The result is in a file (default)
                    location = Path(location)
                    with location.open('r', encoding='utf-8') as filehandler:
                        result = json.load(filehandler)
                    return mimetype, result

                else:
                    LOGGER.warning(f'job {job_id!r} -  unknown result location')  # noqa
                    raise JobResultNotFoundError()

            # Job is incomplete
            return (None,)

        else:
            raise JobNotFoundError()

    def __repr__(self):
        return f'<PostgresDBManager> {self.name}'
