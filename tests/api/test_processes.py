# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Bernhard Mallinger <bernhard.mallinger@eox.at>
#
# Copyright (c) 2024 Tom Kralidis
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
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
from http import HTTPStatus
import time
from unittest import mock

from pygeoapi.api import FORMAT_TYPES, F_HTML, F_JSON
from pygeoapi.api.processes import (
    describe_processes, execute_process, delete_job, get_job_result, get_jobs
)

from tests.util import mock_api_request


def test_describe_processes(config, api_):
    req = mock_api_request({'limit': 1})
    # Test for description of single processes
    rsp_headers, code, response = describe_processes(api_, req)
    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert len(data['processes']) == 1
    assert len(data['links']) == 3

    req = mock_api_request()

    # Test for undefined process
    rsp_headers, code, response = describe_processes(api_, req, 'foo')
    data = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND
    assert data['code'] == 'NoSuchProcess'

    # Test for description of all processes
    rsp_headers, code, response = describe_processes(api_, req)
    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert len(data['processes']) == 2
    assert len(data['links']) == 3

    # Test for particular, defined process
    rsp_headers, code, response = describe_processes(api_, req, 'hello-world')
    process = json.loads(response)
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert process['id'] == 'hello-world'
    assert process['version'] == '0.2.0'
    assert process['title'] == 'Hello World'
    assert len(process['keywords']) == 3
    assert len(process['links']) == 6
    assert len(process['inputs']) == 2
    assert len(process['outputs']) == 1
    assert len(process['outputTransmission']) == 1
    assert len(process['jobControlOptions']) == 2
    assert 'sync-execute' in process['jobControlOptions']
    assert 'async-execute' in process['jobControlOptions']

    # Check HTML response when requested in headers
    req = mock_api_request(HTTP_ACCEPT='text/html')
    rsp_headers, code, response = describe_processes(api_, req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    # No language requested: return default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check JSON response when requested in headers
    req = mock_api_request(HTTP_ACCEPT='application/json')
    rsp_headers, code, response = describe_processes(api_, req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check HTML response when requested with query parameter
    req = mock_api_request({'f': 'html'})
    rsp_headers, code, response = describe_processes(api_, req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    # No language requested: return default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check JSON response when requested with query parameter
    req = mock_api_request({'f': 'json'})
    rsp_headers, code, response = describe_processes(api_, req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check JSON response when requested with French language parameter
    req = mock_api_request({'lang': 'fr'})
    rsp_headers, code, response = describe_processes(api_, req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'fr-CA'
    process = json.loads(response)
    assert process['title'] == 'Bonjour le Monde'

    # Check JSON response when language requested in headers
    req = mock_api_request(HTTP_ACCEPT_LANGUAGE='fr')
    rsp_headers, code, response = describe_processes(api_, req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'fr-CA'

    # Test for undefined process
    req = mock_api_request()
    rsp_headers, code, response = describe_processes(api_, req,
                                                     'goodbye-world')
    data = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND
    assert data['code'] == 'NoSuchProcess'
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]

    # Test describe doesn't crash if example is missing
    req = mock_api_request()
    processor = api_.manager.get_processor("hello-world")
    example = processor.metadata.pop("example")
    rsp_headers, code, response = describe_processes(api_, req)
    processor.metadata['example'] = example
    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert len(data['processes']) == 2


def test_execute_process(config, api_):
    req_body_0 = {
        'inputs': {
            'name': 'Test'
        }
    }
    req_body_1 = {
        'inputs': {
            'name': 'Test'
        },
        'response': 'document'
    }
    req_body_2 = {
        'inputs': {
            'name': 'Tést'
        }
    }
    req_body_3 = {
        'inputs': {
            'name': 'Tést',
            'message': 'This is a test.'
        }
    }
    req_body_4 = {
        'inputs': {
            'foo': 'Tést'
        }
    }
    req_body_5 = {
        'inputs': {}
    }
    req_body_6 = {
        'inputs': {
            'name': None
        }
    }
    req_body_7 = {
        'inputs': {
            'name': 'Test'
        },
        'subscriber': {
            'successUri': 'https://example.com/success',
            'inProgressUri': 'https://example.com/inProgress',
            'failedUri': 'https://example.com/failed',
        }
    }
    req_body_8 = {
        'inputs': {
            'name': 'Test document'
        },
        'response': 'document'
    }

    cleanup_jobs = set()

    # Test posting empty payload to existing process
    req = mock_api_request(data='')
    rsp_headers, code, response = execute_process(api_, req, 'hello-world')
    assert rsp_headers['Content-Language'] == 'en-US'

    data = json.loads(response)
    assert code == HTTPStatus.BAD_REQUEST
    assert 'Location' not in rsp_headers
    assert data['code'] == 'MissingParameterValue'

    req = mock_api_request(data=req_body_0)
    rsp_headers, code, response = execute_process(api_, req, 'foo')

    data = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND
    assert 'Location' not in rsp_headers
    assert data['code'] == 'NoSuchProcess'

    rsp_headers, code, response = execute_process(api_, req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers

    assert len(data.keys()) == 2
    assert data['id'] == 'echo'
    assert data['value'] == 'Hello Test!'

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_api_request(data=req_body_1)
    rsp_headers, code, response = execute_process(api_, req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers

    assert len(data.keys()) == 1
    assert data['outputs'][0]['id'] == 'echo'
    assert data['outputs'][0]['value'] == 'Hello Test!'

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_api_request(data=req_body_2)
    rsp_headers, code, response = execute_process(api_, req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers
    assert data['value'] == 'Hello Tést!'

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_api_request(data=req_body_3)
    rsp_headers, code, response = execute_process(api_, req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers
    assert data['value'] == 'Hello Tést! This is a test.'

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_api_request(data=req_body_4)
    rsp_headers, code, response = execute_process(api_, req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.BAD_REQUEST
    assert 'Location' in rsp_headers
    assert data['code'] == 'InvalidParameterValue'
    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_api_request(data=req_body_5)
    rsp_headers, code, response = execute_process(api_, req, 'hello-world')
    data = json.loads(response)
    assert code == HTTPStatus.BAD_REQUEST
    assert 'Location' in rsp_headers
    assert data['code'] == 'InvalidParameterValue'
    assert data['description'].startswith('Error executing process: ')

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_api_request(data=req_body_6)
    rsp_headers, code, response = execute_process(api_, req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.BAD_REQUEST
    assert 'Location' in rsp_headers
    assert data['code'] == 'InvalidParameterValue'
    assert data['description'].startswith('Error executing process: ')

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_api_request(data=req_body_0)
    rsp_headers, code, response = execute_process(api_, req, 'goodbye-world')

    response = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND
    assert 'Location' not in rsp_headers
    assert response['code'] == 'NoSuchProcess'

    rsp_headers, code, response = execute_process(api_, req, 'hello-world')

    response = json.loads(response)
    assert code == HTTPStatus.OK

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_api_request(data=req_body_1, HTTP_Prefer='respond-async')
    rsp_headers, code, response = execute_process(api_, req, 'hello-world')

    assert 'Location' in rsp_headers
    response = json.loads(response)
    assert isinstance(response, dict)
    assert code == HTTPStatus.CREATED

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_api_request(data=req_body_7)
    with mock.patch(
        'pygeoapi.process.manager.base.requests.post'
    ) as post_mocker:
        rsp_headers, code, response = execute_process(api_, req, 'hello-world')
    assert code == HTTPStatus.OK
    post_mocker.assert_any_call(
        req_body_7['subscriber']['inProgressUri'], json={}
    )
    post_mocker.assert_any_call(
        req_body_7['subscriber']['successUri'],
        json={'id': 'echo', 'value': 'Hello Test!'}
    )
    assert post_mocker.call_count == 2

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_api_request(data=req_body_8)
    rsp_headers, code, response = execute_process(api_, req, 'hello-world')

    response = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'outputs' in response
    assert isinstance(response['outputs'], list)

    # Cleanup
    time.sleep(2)  # Allow time for any outstanding async jobs
    for _, job_id in cleanup_jobs:
        rsp_headers, code, response = delete_job(api_, mock_api_request(),
                                                 job_id)
        assert code == HTTPStatus.OK


def _execute_a_job(api_):
    req_body_sync = {
        'inputs': {
            'name': 'Sync Test'
        }
    }

    req = mock_api_request(data=req_body_sync)
    rsp_headers, code, response = execute_process(api_, req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers
    assert data['value'] == 'Hello Sync Test!'

    job_id = rsp_headers['Location'].split('/')[-1]
    return job_id


def test_delete_job(api_):
    rsp_headers, code, response = delete_job(api_, mock_api_request(),
                                             'does-not-exist')

    assert code == HTTPStatus.NOT_FOUND
    req_body_async = {
        'inputs': {
            'name': 'Async Test Deletion'
        }
    }
    job_id = _execute_a_job(api_)
    rsp_headers, code, response = delete_job(api_, mock_api_request(), job_id)

    data = json.loads(response)

    assert code == HTTPStatus.OK
    assert data['message'] == 'Job dismissed'

    rsp_headers, code, response = delete_job(api_, mock_api_request(), job_id)
    assert code == HTTPStatus.NOT_FOUND

    req = mock_api_request(data=req_body_async, HTTP_Prefer='respond-async')
    rsp_headers, code, response = execute_process(api_, req, 'hello-world')

    assert code == HTTPStatus.CREATED
    assert 'Location' in rsp_headers

    time.sleep(2)  # Allow time for async execution to complete
    job_id = rsp_headers['Location'].split('/')[-1]
    rsp_headers, code, response = delete_job(api_, mock_api_request(), job_id)
    assert code == HTTPStatus.OK

    rsp_headers, code, response = delete_job(api_, mock_api_request(), job_id)
    assert code == HTTPStatus.NOT_FOUND


def test_get_job_result(api_):
    rsp_headers, code, response = get_job_result(
        api_, mock_api_request(), 'not-exist',
    )
    assert code == HTTPStatus.NOT_FOUND

    job_id = _execute_a_job(api_)
    rsp_headers, code, response = get_job_result(api_, mock_api_request(),
                                                 job_id)
    # default response is html
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == 'text/html'
    result = 'JSON.stringify({"id":"echo","value":"Hello Sync Test!"}'
    assert result in response

    rsp_headers, code, response = get_job_result(
        api_, mock_api_request({'f': 'json'}), job_id,
    )
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == 'application/json'
    assert json.loads(response)['value'] == 'Hello Sync Test!'


def test_get_jobs_single(api_):
    job_id = _execute_a_job(api_)
    headers, code, response = get_jobs(api_, mock_api_request(), job_id=job_id)
    assert code == HTTPStatus.OK

    job = json.loads(response)
    assert job['jobID'] == job_id
    assert job['status'] == 'successful'


def test_get_jobs_pagination(api_):
    # generate test jobs for querying
    for _ in range(11):
        _execute_a_job(api_)

    # test default pagination limit
    headers, code, response = get_jobs(api_, mock_api_request(), job_id=None)
    job_response = json.loads(response)
    assert len(job_response['jobs']) == 10
    assert next(
        link for link in job_response['links'] if link['rel'] == 'next'
    )['href'].endswith('/jobs?offset=10')

    headers, code, response = get_jobs(
        api_,
        mock_api_request({'limit': 10, 'offset': 9}),
        job_id=None)
    job_response_offset = json.loads(response)
    # check to get 1 same job id with an offset of 9 and limit of 10
    same_job_ids = {job['jobID'] for job in job_response['jobs']}.intersection(
        {job['jobID'] for job in job_response_offset['jobs']}
    )
    assert len(same_job_ids) == 1
    assert next(
        link for link in job_response_offset['links'] if link['rel'] == 'prev'
    )['href'].endswith('/jobs?offset=0&limit=10')

    # test custom limit
    headers, code, response = get_jobs(
        api_,
        mock_api_request({'limit': 20}),
        job_id=None)
    job_response = json.loads(response)
    # might be more than 11 due to test interaction
    assert len(job_response['jobs']) > 10
