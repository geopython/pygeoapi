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
