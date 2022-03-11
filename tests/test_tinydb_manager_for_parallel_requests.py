import os

from werkzeug.wrappers import Request
from werkzeug.test import create_environ
from multiprocessing import Process, Manager
import json

from tinydb import TinyDB, Query

import pytest
from pygeoapi.api import (
    API, APIRequest
)
from pygeoapi.util import yaml_load

from .util import get_test_file_path


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def api_(config):
    return API(config)


def _execute_process(api, request, process_id, index, processes_out):
    headers, http_status, response = api.execute_process(request, process_id)
    processes_out[index] = {"headers": headers, "http_status": http_status, "response": response}


def _create_request(name, message, locales):
    data = {
        "mode": "async",
        "response": "raw",
        "inputs": {
            "name": name,
            "message": message
        }
    }
    environ = create_environ(base_url='http://localhost:5000/processes/hello-world/execution', method="POST", json=data)
    req = Request(environ)
    return APIRequest.with_data(req, locales)


def test_async_hello_world_process_parallel(api_, config):
    index_name = config['server']['manager']['connection']

    if os.path.exists(index_name):
        os.remove(index_name)

    NUM_PROCS = 4
    process_id = "hello-world"
    req = _create_request("World", "Hello", api_.locales)

    manager = Manager()
    processes_out = manager.dict()
    procs = []
    for i in range(0, NUM_PROCS):
        procs.append(Process(target=_execute_process, args=(api_, req, process_id, i, processes_out)))

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
            assert process_out['http_status'] == 201
            job_id = process_out['headers']['Location'].split('/')[-1]
            job_dict = db.search(query.identifier == job_id)[0]
            assert job_dict["identifier"] == job_id
            assert job_dict["process_id"] == process_id
            assert job_dict["mimetype"] == process_out['headers']['Content-Type']
            try:
                with open("{}/hello-world-{}".format(os.path.dirname(index_name), job_id)) as json_file:
                    out_json = json.load(json_file)
                    assert out_json["id"] == "echo"
                    assert out_json["value"] == "Hello World! Hello"
            except FileNotFoundError as e:
                assert False, e
        except json.decoder.JSONDecodeError as e:
            assert False, e
        except Exception as e:
            assert False, e
