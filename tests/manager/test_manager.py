# =================================================================
#
# Authors: Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2023 Ricardo Garcia Silva
# Copyright (c) 2025 Tom Kralidis
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

from datetime import datetime
from typing import Dict

import pytest
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    create_engine
)

from pygeoapi.process.base import UnknownProcessError, JobNotFoundError
from pygeoapi.process.manager.base import get_manager
from pygeoapi.process.manager.mongodb_ import MongoDBManager
from pygeoapi.process.manager.postgresql import PostgreSQLManager
from pygeoapi.util import JobStatus

from ..util import get_test_file_path


@pytest.fixture()
def config() -> Dict:
    return {
        'server': {
            'manager': {
                'name': 'TinyDB',
                'output_dir': '/tmp',
                'connection': '/tmp/pygeoapi-process-manager-test.db'
            }
        },
        'resources': {
            'hello-world': {
                'type': 'process',
                'processor': {
                    'name': 'HelloWorld'
                }
            }
        }
    }


def test_get_manager(config):
    manager = get_manager(config)
    assert manager.name == config['server']['manager']['name']
    assert 'hello-world' in manager.processes


def test_get_processor(config):
    manager = get_manager(config)
    process_id = 'hello-world'
    processor = manager.get_processor(process_id)
    assert processor.metadata["id"] == process_id


def test_get_processor_raises_exception(config):
    manager = get_manager(config)
    with pytest.raises(expected_exception=UnknownProcessError):
        manager.get_processor('foo')


def test_get_job_result_binary(config):
    manager = get_manager(config)
    nc_file = get_test_file_path("tests/data/coads_sst.nc")
    job_id = "15eeae38-608c-11ef-81c8-0242ac130002"
    job_metadata = {
        "type": "process",
        "identifier": job_id,
        "process_id": "dummy",
        "created": "2024-08-22T12:00:00.000000Z",
        "started": "2024-08-22T12:00:00.000000Z",
        "finished": "2024-08-22T12:00:01.000000Z",
        "updated": "2024-08-22T12:00:01.000000Z",
        "status": "successful",
        "location": nc_file,
        "mimetype": "application/x-netcdf",
        "message": "Job complete",
        "progress": 100
    }
    try:
        manager.get_job(job_id)
    except JobNotFoundError:
        manager.add_job(job_metadata)
    mimetype, result = manager.get_job_result(job_id)
    assert mimetype == "application/x-netcdf"
    assert isinstance(result, bytes)


def _job_metadata(identifier, status='successful'):
    return {
        'identifier': identifier,
        'type': 'process',
        'process_id': 'hello-world',
        'created': datetime(2024, 8, 22, 12, 0, 0),
        'started': datetime(2024, 8, 22, 12, 0, 0),
        'finished': datetime(2024, 8, 22, 12, 0, 1),
        'updated': datetime(2024, 8, 22, 12, 0, 1),
        'status': status,
        'location': None,
        'mimetype': 'application/json',
        'message': 'Job complete',
        'progress': 100
    }


def test_get_jobs_pagination_postgresql():
    # exercise PostgreSQLManager.get_jobs against an in-memory
    # SQLite database with the same jobs table layout, so the
    # test does not need a live PostgreSQL server
    engine = create_engine('sqlite://')
    metadata = MetaData()
    jobs_table = Table(
        'jobs', metadata,
        Column('identifier', String, primary_key=True, nullable=False),
        Column('type', String, nullable=False),
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
        Column('output', LargeBinary)
    )
    metadata.create_all(engine)

    manager = object.__new__(PostgreSQLManager)
    manager._engine = engine
    manager.table_model = jobs_table
    manager.c = jobs_table.c

    manager.add_job(_job_metadata('job-1'))
    manager.add_job(_job_metadata('job-2'))
    manager.add_job(_job_metadata('job-3', status='failed'))

    results = manager.get_jobs()
    assert results['numberMatched'] == 3
    assert len(results['jobs']) == 3

    results = manager.get_jobs(limit=2)
    assert results['numberMatched'] == 3
    assert len(results['jobs']) == 2

    results = manager.get_jobs(limit=1, offset=1)
    assert results['numberMatched'] == 3
    assert len(results['jobs']) == 1

    results = manager.get_jobs(status=JobStatus.successful, limit=1)
    assert results['numberMatched'] == 2
    assert len(results['jobs']) == 1


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def skip(self, n):
        self._docs = self._docs[n:]
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def _matching(self, query):
        return [doc for doc in self._docs
                if all(doc.get(key) == value
                       for key, value in query.items())]

    def find(self, query=None):
        return _FakeCursor(self._matching(query or {}))

    def count_documents(self, query):
        return len(self._matching(query))


class _FakeDatabase:
    def __init__(self, jobs):
        self.jobs = jobs
        self.job_manager_pygeoapi = self


def test_get_jobs_pagination_mongodb():
    # exercise MongoDBManager.get_jobs against a fake in-memory
    # collection, so the test does not need a live MongoDB server
    docs = [
        {'identifier': 'job-1', 'status': 'successful'},
        {'identifier': 'job-2', 'status': 'successful'},
        {'identifier': 'job-3', 'status': 'failed'}
    ]
    database = _FakeDatabase(_FakeCollection(docs))

    manager = object.__new__(MongoDBManager)
    manager._connect = lambda: setattr(manager, 'db', database)

    results = manager.get_jobs()
    assert results['numberMatched'] == 3
    assert len(results['jobs']) == 3

    results = manager.get_jobs(limit=2)
    assert results['numberMatched'] == 3
    assert len(results['jobs']) == 2

    results = manager.get_jobs(limit=1, offset=1)
    assert results['numberMatched'] == 3
    assert len(results['jobs']) == 1

    results = manager.get_jobs(status=JobStatus.successful, limit=1)
    assert results['numberMatched'] == 2
    assert len(results['jobs']) == 1
