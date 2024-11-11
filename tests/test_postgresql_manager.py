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

# See pygeoapi/process/manager/postgresql.py
# for instructions on setting up database structure.

import json

import pytest
from werkzeug.wrappers import Request
from werkzeug.test import create_environ

from .util import get_test_file_path
from pygeoapi.api import API, APIRequest
import pygeoapi.api.processes as processes_api
from pygeoapi.util import yaml_load


@pytest.fixture()
def config():
    with open(get_test_file_path(
              'pygeoapi-test-config-postgresql-manager.yml')
              ) as fh:
        return yaml_load(fh)


@pytest.fixture()
def openapi():
    with open(get_test_file_path('pygeoapi-test-openapi.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def api_(config, openapi):
    return API(config, openapi)


def _create_execute_request(name, message, locales):
    data = {
        "response": "raw",
        "inputs": {
            "name": name,
            "message": message
        }
    }
    environ = create_environ(
        base_url='http://localhost:5000/processes/hello-world/execution',
        method="POST", json=data)
    req = Request(environ)
    return APIRequest.from_flask(req, locales)


def _create_job_request(job_id, locales):
    environ = create_environ(
        base_url=f'http://localhost:5000/jobs/{job_id}',
        query_string="f=json",
        method="GET")
    req = Request(environ)
    return APIRequest.from_flask(req, locales)


def _create_results_request(job_id, locales):
    environ = create_environ(
        base_url=f'http://localhost:5000/jobs/{job_id}/results',
        query_string="f=json",
        method="GET")
    req = Request(environ)
    return APIRequest.from_flask(req, locales)


def _create_delete_request(job_id, locales):
    environ = create_environ(
        base_url=f'http://localhost:5000/jobs/{job_id}',
        query_string="f=json",
        method="DELETE")
    req = Request(environ)
    return APIRequest.from_flask(req, locales)


def test_api_connection_rfc3986(config, openapi):
    connection = config['server']['manager']['connection']
    connection_string = (
        f"postgresql://{connection['user']}:{connection['password']}"
        f"@{connection['host']}:{connection['port']}/{connection['database']}")
    config['server']['manager']['connection'] = connection_string
    API(config, openapi)


def test_job_sync_hello_world(api_, config):
    """
    Create a new job for hello-world,
    which mplicitly tests add_job() and update_job();
    then:
    -) get the job info, whch tests get_job(),
    -) get the job results, whch tests get_job_result(),
    -) get all present jobs, whch tests get_jobs(),
    -) delete the newly inserted job, whch tests delete_job().
    """
    process_id = "hello-world"

    # Create new job
    req = _create_execute_request("World", "Hello", api_.locales)
    headers, http_status, response = processes_api.execute_process(
        api_, req, process_id)
    assert http_status == 200
    out_json = json.loads(response)
    assert out_json["id"] == "echo"
    assert out_json["value"] == "Hello World! Hello"

    # Save job_id for later use
    job_id = headers['Location'].split('/')[-1]
    mimetype = headers['Content-Type']

    # Get job info
    req = _create_job_request(job_id, api_.locales)
    headers, http_status, response = processes_api.get_jobs(
        api_, req, job_id)
    assert http_status == 200
    out_json = json.loads(response)
    assert out_json["type"] == "process"
    assert out_json["processID"] == process_id
    assert out_json["jobID"] == job_id

    # Get job results
    req = _create_results_request(job_id, api_.locales)
    headers, http_status, response = processes_api.get_job_result(
        api_, req, job_id)
    assert http_status == 200
    assert mimetype == headers['Content-Type']
    out_json = json.loads(response)
    assert out_json["id"] == "echo"
    assert out_json["value"] == "Hello World! Hello"

    # Get all present jobs
    req = _create_job_request(None, api_.locales)
    headers, http_status, response = processes_api.get_jobs(
        api_, req, None)
    assert http_status == 200
    # check the inserted job is in the list
    out_json = json.loads(response)
    jobs = out_json["jobs"]
    assert any(job["jobID"] == job_id for job in jobs)

    # Delete the inserted job
    req = _create_delete_request(job_id, api_.locales)
    headers, http_status, response = processes_api.delete_job(
        api_, req, job_id)
    assert http_status == 200
    out_json = json.loads(response)
    assert out_json["jobID"] == job_id
    assert out_json["status"] == "dismissed"

    # Try again to delete the inserted job
    req = _create_delete_request(job_id, api_.locales)
    headers, http_status, response = processes_api.get_jobs(
        api_, req, job_id)
    assert http_status == 404
    out_json = json.loads(response)
    assert out_json["code"] == "InvalidParameterValue"
    assert out_json["description"] == job_id
