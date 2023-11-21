# =================================================================
#
# Authors: Martin Pontius <m.pontius@52north.org>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 52°North Spatial Information Research GmbH
# Copyright (c) 2022 Tom Kralidis
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

from multiprocessing import Process, Manager
import pytest
from tinydb import TinyDB, Query
from werkzeug.wrappers import Request
from werkzeug.test import create_environ

from pygeoapi.api import API, APIRequest
from pygeoapi.util import yaml_load
from .util import get_test_file_path


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def openapi():
    with open(get_test_file_path('pygeoapi-test-openapi.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def api_(config, openapi):
    return API(config, openapi)


def _execute_process(api, request, process_id, index, processes_out):
    headers, http_status, response = api.execute_process(request, process_id)
    processes_out[index] = {"headers": headers, "http_status": http_status,
                            "response": response}


def _create_request(name, message, locales):
    data = {
        "mode": "async",
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
    return APIRequest.with_data(req, locales)


def test_async_hello_world_process_parallel(api_, config):
    index_name = Path(config['server']['manager']['connection'])

    if index_name.exists():
        index_name.unlink()

    NUM_PROCS = 4
    process_id = "hello-world"
    req = _create_request("World", "Hello", api_.locales)

    manager = Manager()
    processes_out = manager.dict()
    procs = []
    for i in range(0, NUM_PROCS):
        procs.append(Process(target=_execute_process,
                             args=(api_, req, process_id, i, processes_out)))

    # Run processes in parallel
    procs_started = []
    for p in procs:
        p.start()
        procs_started.append(p)

    for p in procs_started:
        # let main process wait until sub-processes completed
        p.join()

    # Test if jobs are registered and run correctly
    db = TinyDB(index_name)
    query = Query()
    for process_out in processes_out.values():
        try:
            assert process_out['http_status'] == 200
            job_id = process_out['headers']['Location'].split('/')[-1]
            job_dict = db.search(query.identifier == job_id)[0]
            assert job_dict["identifier"] == job_id
            assert job_dict["process_id"] == process_id
            assert job_dict["mimetype"] == process_out['headers'][
                'Content-Type']
            try:
                with open(f'{index_name.parent}/hello-world-{job_id}') as fh:
                    out_json = json.load(fh)
                    assert out_json["id"] == "echo"
                    assert out_json["value"] == "Hello World! Hello"
            except FileNotFoundError as e:
                assert False, e
        except json.decoder.JSONDecodeError as e:
            assert False, e
        except Exception as e:
            assert False, e
