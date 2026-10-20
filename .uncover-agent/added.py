        'Elasticsearch': 'pygeoapi.process.manager.elasticsearch_.ElasticsearchManager',  # noqa
# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
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

import json
import logging
from pathlib import Path
from typing import Any, Tuple

from elasticsearch import Elasticsearch, exceptions

from pygeoapi.formats import FORMAT_TYPES, F_JSON, F_JSONLD
from pygeoapi.process.base import (
    JobNotFoundError,
    JobResultNotFoundError,
    ProcessorGenericError
)
from pygeoapi.process.manager.base import BaseManager
from pygeoapi.util import JobStatus

LOGGER = logging.getLogger(__name__)


class ElasticsearchManager(BaseManager):
    """Elasticsearch Manager"""

    def __init__(self, manager_def: dict):
        """
        Initialize object

        :param manager_def: manager definition

        :returns: `pygeoapi.process.manager.elasticsearch_.ElasticsearchManager`  # noqa
        """

        super().__init__(manager_def)

        self.is_async = True
        self.supports_subscribing = True

        self.es_host, self.index_name = self.connection.rsplit('/', 1)

        LOGGER.debug('Setting Elasticsearch properties')

        LOGGER.debug(f'host: {self.es_host}')
        LOGGER.debug(f'index: {self.index_name}')

        LOGGER.debug('Connecting to Elasticsearch')
        self.es = Elasticsearch(self.es_host)
        if not self.es.ping():
            msg = f'Cannot connect to Elasticsearch: {self.es_host}'
            LOGGER.error(msg)
            raise ProcessorGenericError(msg)

    def destroy(self) -> bool:
        """
        Destroy manager

        :returns: `bool` status of result
        """

        LOGGER.debug(f'Destroying ES index {self.index_name}')
        response = self.es.options(ignore_status=[400, 404]).indices.delete(
            index=self.index_name)
        LOGGER.debug(f'Result: {response}')

        return True

    def get_jobs(self, status: JobStatus = None, limit=None, offset=None
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

        jobs_list = []
        query = {}

        if status is not None:
            LOGGER.debug('Applying status query')
            query = {
                'match': {
                    'status': {
                        'query': status
                    }
                }
            }

        es_results = self.es.search(index=self.index_name,
                                    from_=offset, size=limit, **query)
        matched = es_results['hits']['total']['value']
        returned = len(es_results['hits']['hits'])

        for hit in es_results['hits']['hits']:
            job = hit['_source']
            jobs_list.append(job)

        return {
            'jobs': jobs_list,
            'numberMatched': matched,
            'numberReturned': returned
        }

    def add_job(self, job_metadata: dict) -> str:
        """
        Add a job

        :param job_metadata: `dict` of job metadata

        :returns: identifier of added job
        """

        job_id = job_metadata['identifier']

        LOGGER.debug(f"Inserting job with identifier {job_id}")
        _ = self.es.index(index=self.index_name, id=job_id,
                          body=job_metadata)
        LOGGER.debug('Job added')

        return job_id

    def update_job(self, job_id: str, update_dict: dict) -> bool:
        """
        Updates a job

        :param job_id: job identifier
        :param update_dict: `dict` of property updates

        :returns: `bool` of status result
        """

        LOGGER.debug(f'Updating job {job_id}')
        _ = self.es.update(index=self.index_name, id=job_id, doc=update_dict)

        return True

    def delete_job(self, job_id: str) -> bool:
        """
        Deletes a job

        :param job_id: job identifier

        :raises JobNotFoundError: if the job_id does not correspond to a
                                  known job
        :return `bool` of status result
        """

        LOGGER.debug(f'Deleting job {job_id}')
        _ = self.es.delete(index=self.index_name, id=job_id)

        return True

    def get_job(self, job_id: str) -> dict:
        """
        Get a single job

        :param job_id: job identifier

        :raises JobNotFoundError: if the job_id does not correspond to a
                                  known job
        :returns: `dict`  # `pygeoapi.process.manager.Job`
        """

        LOGGER.debug(f'Fetching job {job_id}')
        try:
            result = self.es.get(index=self.index_name, id=job_id)
            result = result['_source']
            return result
        except exceptions.NotFoundError:
            raise JobNotFoundError()

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

        if not job_status == JobStatus.successful:
            # Job is incomplete
            return (None,)
        if location is None:
            LOGGER.warning(f'job {job_id!r} -  unknown result location')
            raise JobResultNotFoundError()
        else:
            try:
                if Path(location).exists():
                    location = Path(location)
                    if mimetype in (None, FORMAT_TYPES[F_JSON],
                                    FORMAT_TYPES[F_JSONLD]):
                        with location.open('r', encoding='utf-8') as fh:
                            result = json.load(fh)
                    else:
                        with location.open('rb') as filehandler:
                            result = filehandler.read()
                else:
                    if mimetype in (None, FORMAT_TYPES[F_JSON],
                                    FORMAT_TYPES[F_JSONLD]):
                        print("QQQQ", location)
                        print("QQQQ", type(location))
                        result = json.loads(location)
            except (TypeError, FileNotFoundError, json.JSONDecodeError):
                raise JobResultNotFoundError()

            return mimetype, result

    def __repr__(self):
        return f'<ElasticsearchManager> {self.name}'
    JobResultNotFoundError
        :returns: `pygeoapi.process.manager.tinydb_.TinyDBManager`
# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
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

import json
from pathlib import Path
import sys

from elasticsearch import Elasticsearch, helpers
es = Elasticsearch('http://localhost:9200')

if len(sys.argv) < 2:
    print(f'Usage: {sys.argv[0]} <path/to/jobs.json>')
    sys.exit(1)

index_name = Path(sys.argv[1]).stem.lower()

if es.indices.exists(index=index_name):
    es.indices.delete(index=index_name)

# index settings
settings = {
    'number_of_shards': 1,
    'number_of_replicas': 0
}


def gendata(data):
    """
    Generator function to yield features
    """

    for j in data['jobs']:
        yield {
            "_index": index_name,
            "_id": j['identifier'],
            "_source": j
        }


# create index
es.options(request_timeout=90).indices.create(
    index=index_name, settings=settings)

with open(sys.argv[1], encoding='utf-8') as fh:
    d = json.load(fh)

    # call generator function to yield features into ES bulk API
    helpers.bulk(es, gendata(d))
# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
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

import pytest

from pygeoapi.process.base import JobNotFoundError, JobResultNotFoundError
from pygeoapi.process.manager.elasticsearch_ import ElasticsearchManager


@pytest.fixture()
def config():
    return {
        'name': 'Elasticsearch',
        'connection': 'http://localhost:9200/test-manager'
    }


@pytest.fixture()
def data():
    return {
        'type': 'process',
        'identifier': '123',
        'process_id': 'foo-process',
        'created': '2026-10-12T14:50:00.693224Z',
        'started': '2026-10-12T14:50:00.693242Z',
        'updated': '2026-10-12T14:50:00.725403Z',
        'finished': '2026-10-12T14:50:00.725386Z',
        'status': 'successful',
        'location': '{"foo": "bar"}',
        'mimetype': 'application/json',
        'message': 'Job in progress',
        'progress': 50
    }


def test_get_jobs(config):
    em = ElasticsearchManager(config)

    jobs = em.get_jobs()
    num_jobs = len(jobs['jobs'])

    assert num_jobs == jobs['numberMatched']
    assert num_jobs == jobs['numberReturned']


def test_get_job(config):
    em = ElasticsearchManager(config)

    id_ = '335fdbaf-c64c-11f1-ac1e-85ca8be9387b'
    job = em.get_job(id_)

    assert job['identifier'] == id_
    assert job['status'] == 'successful'
    assert job['progress'] == 100

    with pytest.raises(JobNotFoundError):
        em.get_job('404')


def test_get_job_result(config):
    em = ElasticsearchManager(config)

    result = em.get_job_result('cb23ae5b-c335-11f1-bb5c-d9d1498a46ce')
    assert result == (None,)

    with pytest.raises(JobResultNotFoundError):
        _ = em.get_job_result('55555')

    mimetype, data = em.get_job_result('335fdbaf-c64c-11f1-ac1e-85ca8be9387b')
    assert mimetype == 'application/json'

    assert data['foo'] == 'bar'


def test_add_job(config, data):
    em = ElasticsearchManager(config)

    with pytest.raises(JobNotFoundError):
        em.get_job(data['identifier'])

    id_ = em.add_job(data)
    assert id_ == data['identifier']

    job = em.get_job(id_)
    assert job['identifier'] == id_


def test_update_job(config, data):
    em = ElasticsearchManager(config)

    id_ = '123'
    job = em.get_job(id_)
    assert job['message'] == 'Job in progress'
    assert job['progress'] == 50

    data['message'] = 'Job complete'
    data['progress'] = 100

    _ = em.update_job(data['identifier'], data)

    job = em.get_job(id_)
    assert job['identifier'] == '123'
    assert job['progress'] == 100


def test_delete_job(config):
    em = ElasticsearchManager(config)

    id_ = '123'
    job = em.get_job(id_)
    assert job['identifier'] == id_

    _ = em.delete_job(id_)

    with pytest.raises(JobNotFoundError):
        em.get_job(id_)