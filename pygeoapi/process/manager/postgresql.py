# =================================================================
#
# Authors: Francesco Martinelli <francesco.martinelli@ingv.it>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2024 Francesco Martinelli
# Copyright (c) 2026 Tom Kralidis
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
# CREATE DATABASE test
#   WITH TEMPLATE = template0
#   ENCODING = 'UTF8'
#   LOCALE = 'en_US.UTF-8';
# ALTER DATABASE test OWNER TO postgres;
#
# Import dump:
# psql -U postgres -h 127.0.0.1 -p 5432 test <
#   tests/data/postgres_manager_full_structure.backup.sql

import json
import logging
from pathlib import Path
from typing import Any, Tuple

from sqlalchemy import (
    Column,
    DateTime,
    delete,
    insert,
    Integer,
    LargeBinary,
    String,
    Table,
    text,
    update
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, Session

from pygeoapi.formats import F_JSON, F_JSONLD, FORMAT_TYPES
from pygeoapi.process.base import (
    JobNotFoundError,
    JobResultNotFoundError,
    ProcessorGenericError
)
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.provider.sql import get_engine, store_db_parameters
from pygeoapi.util import JobStatus


LOGGER = logging.getLogger(__name__)


class PostgreSQLManager(BaseManager):
    """PostgreSQL Manager"""

    default_port = 5432
    _store_db_parameters = store_db_parameters

    def __init__(self, manager_def: dict):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.postgresql.PostgreSQLManager`
        """

        super().__init__(manager_def)
        self.is_async = True
        self.id_field = 'identifier'
        self.supports_subscribing = True
        self.connection = manager_def['connection']

        options = manager_def.get('options', {})
        self._store_db_parameters(manager_def['connection'], options)
        self._engine = get_engine(
            'postgresql+psycopg2',
            self.db_host,
            self.db_port,
            self.db_name,
            self.db_user,
            self._db_password,
            self.db_conn,
            **self.db_options
        )
        self.table_output = self.output_dir is None

        self.table_model = get_table_model(
            self.db_search_path, self._engine, self.table_output
        )
        self.c = self.table_model.c
        try:
            LOGGER.debug('Getting table model')

        except Exception as err:
            msg = 'Table model fetch failed'
            LOGGER.error(f'{msg}: {err}')
            raise ProcessorGenericError(msg)

    def get_jobs(
        self, status: JobStatus = None, limit=None, offset=None
    ) -> dict:
        """
        Get jobs

        :param status: job status (accepted, running, successful,
                        failed, results) (default is all)
        :param limit: number of jobs to return
        :param offset: pagination offset

        :returns: dict of list of jobs (identifier, status, process identifier)
                  and numberMatched
        """

        LOGGER.debug('Querying for jobs')
        with Session(self._engine) as session:
            results = session.query(self.table_model)

            if status is not None:
                results = results.filter(self.c.status == status.value)

            jobs = [r._asdict() for r in results.all()]
            return {'jobs': jobs, 'numberMatched': len(jobs)}

    def add_job(self, job_metadata: dict) -> str:
        """
        Add a job

        :param job_metadata: `dict` of job metadata

        :returns: identifier of added job
        """

        LOGGER.debug('Adding job')
        with Session(self._engine) as session:
            try:
                session.execute(
                    insert(self.table_model).values(**job_metadata)
                )
                session.commit()
            except Exception as err:
                session.rollback()
                msg = 'Insert failed'
                LOGGER.error(f'{msg}: {err}')
                raise ProcessorGenericError(msg)

        return job_metadata['identifier']

    def update_job(self, job_id: str, update_dict: dict) -> bool:
        """
        Updates a job

        :param job_id: job identifier
        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """

        rowcount = 0

        LOGGER.debug('Updating job')
        with Session(self._engine) as session:
            try:
                stmt = (
                    update(self.table_model)
                    .where(self.c.identifier == job_id)
                    .values(**update_dict)
                )
                result = session.execute(stmt)
                session.commit()
                rowcount = result.rowcount
            except Exception as err:
                session.rollback()
                msg = 'Update failed'
                LOGGER.error(f'{msg}: {err}')
                raise ProcessorGenericError(msg)

        return rowcount == 1

    def get_job(self, job_id: str) -> dict:
        """
        Get a single job

        :param job_id: job identifier

        :raises JobNotFoundError: if the job_id does not correspond to a
                                  known job
        :returns: `dict`  # `pygeoapi.process.manager.Job`
        """

        LOGGER.debug('Querying for job')
        with Session(self._engine) as session:
            results = session.query(self.table_model).filter(
                self.c.identifier == job_id
            )

            first = results.first()

            if first is not None:
                return first._asdict()
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

        rowcount = 0

        # get result file if present for deletion
        job_result = self.get_job(job_id)
        location = job_result.get('location')

        LOGGER.debug('Deleting job')
        with Session(self._engine) as session:
            try:
                stmt = delete(self.table_model).where(
                    self.c.identifier == job_id
                )
                result = session.execute(stmt)
                session.commit()
                rowcount = result.rowcount
            except Exception as err:
                session.rollback()
                msg = 'Delete failed'
                LOGGER.error(f'{msg}: {err}')
                raise ProcessorGenericError(msg)

        # delete result file if present
        if None not in [location, self.output_dir]:
            try:
                Path(location).unlink()
            except FileNotFoundError:
                pass

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
                if mimetype in (
                    None,
                    FORMAT_TYPES[F_JSON],
                    FORMAT_TYPES[F_JSONLD]
                ):
                    with location.open('r', encoding='utf-8') as fh:
                        result = json.load(fh)
                else:
                    with location.open('rb') as fh:
                        result = fh.read()
            except (TypeError, FileNotFoundError, json.JSONDecodeError):
                raise JobResultNotFoundError()
            else:
                return mimetype, result

    def __repr__(self):
        return f'<PostgreSQLManager> {self.name}'


def get_table_model(
    db_search_path: tuple[str], engine: Engine, table_output: bool
) -> Any:
    """Define SQLAlchemy job model"""

    Base = declarative_base()
    schema = db_search_path[0]

    Jobs = Table(
        'jobs',
        Base.metadata,
        Column('identifier', String, primary_key=True, nullable=False),
        Column(
            'type',
            String,
            nullable=False,
            server_default=text("'process'::character varying")
        ),
        Column('process_id', String, nullable=False),
        Column('created', DateTime),
        Column('started', DateTime),
        Column('finished', DateTime),
        Column('updated', DateTime),
        Column('status', String, nullable=False),
        Column('location', String),
        Column('mimetype', String),
        Column('message', String),
        Column('progress', Integer, nullable=False),
        schema=schema
    )

    if table_output:
        Jobs.append_column(Column('output', LargeBinary))

    Base.metadata.create_all(engine, tables=[Jobs], checkfirst=True)

    return Jobs
