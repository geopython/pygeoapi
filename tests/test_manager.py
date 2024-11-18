# =================================================================
#
# Authors: Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2023 Ricardo Garcia Silva
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
from typing import Dict

import pytest

from pygeoapi.process.base import UnknownProcessError, JobNotFoundError
from pygeoapi.process.manager.base import get_manager

from .util import get_test_file_path


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
        "job_start_datetime": "2024-08-22T12:00:00.000000Z",
        "job_end_datetime": "2024-08-22T12:00:01.000000Z",
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
