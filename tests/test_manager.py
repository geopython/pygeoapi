import json
from email import message_from_bytes
from typing import Dict
from unittest import mock

from pygeoapi.process import exceptions
from pygeoapi.process.manager import get_manager
from pygeoapi.process.manager import base
from pygeoapi.models import processes
from shapely.geometry import Point

import pytest


@pytest.fixture()
def config() -> Dict:
    return {
        'server': {
            'manager': {
                'name': 'TinyDB',
                'output_dir': '/tmp',
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


def test_manager_must_implement_abstract_methods():

    class ManagerWithoutDeleteJobs(base.BaseManager):
        ...

    class ManagerWithoutGetJob(base.BaseManager):
        ...

    class ManagerWithoutGetJobs(base.BaseManager):
        ...

    with pytest.raises(expected_exception=TypeError):
        ManagerWithoutDeleteJobs(manager_def={})

    with pytest.raises(expected_exception=TypeError):
        ManagerWithoutGetJob(manager_def={})

    with pytest.raises(expected_exception=TypeError):
        ManagerWithoutGetJobs(manager_def={})


def test_get_manager(config):
    manager = get_manager(config)
    assert manager.name == config['server']['manager']['name']
    assert 'hello-world' in manager.processes


def test_get_process_descriptions(config):
    manager = get_manager(config)
    total, descriptions = manager.get_process_descriptions()
    assert total == 1
    assert len(descriptions) == 1
    assert descriptions[0].id == 'hello-world'

    total, descriptions = manager.get_process_descriptions(offset=10)
    assert total == 1
    assert len(descriptions) == 0


def test_get_processor(config):
    manager = get_manager(config)
    process_id = 'hello-world'
    processor = manager.get_processor(process_id)
    assert processor.process_description.id == process_id


def test_get_processor_raises_exception(config):
    manager = get_manager(config)
    with pytest.raises(expected_exception=exceptions.UnknownProcessError):
        manager.get_processor('foo')


@pytest.mark.parametrize(
    'manager_is_async, processor_is_async, requested_mode, '
    'expected_chosen, expected_headers',
    [
        pytest.param(
            True, True, None,
            processes.ProcessExecutionMode.sync_execute, {}
        ),
        pytest.param(
            True, True, processes.RequestedProcessExecutionMode.wait,
            processes.ProcessExecutionMode.sync_execute,
            {'Preference-Applied': 'wait'}
        ),
        pytest.param(
            True, True, processes.RequestedProcessExecutionMode.respond_async,
            processes.ProcessExecutionMode.async_execute,
            {'Preference-Applied': 'respond-async'}
        ),
        pytest.param(
            False, True, processes.RequestedProcessExecutionMode.respond_async,
            processes.ProcessExecutionMode.sync_execute,
            {'Preference-Applied': 'wait'}
        ),
        pytest.param(
            True, False, processes.RequestedProcessExecutionMode.respond_async,
            processes.ProcessExecutionMode.sync_execute,
            {'Preference-Applied': 'wait'}
        ),
        pytest.param(
            False, False,
            processes.RequestedProcessExecutionMode.respond_async,
            processes.ProcessExecutionMode.sync_execute,
            {'Preference-Applied': 'wait'}
        ),
    ]
)
def test_select_execution_mode(
        config, manager_is_async, processor_is_async,
        requested_mode, expected_chosen, expected_headers,
):
    manager = get_manager(config)
    manager.is_async = manager_is_async
    processor = manager.get_processor('hello-world')

    if processor_is_async:
        processor.process_description.job_control_options = [
            processes.ProcessJobControlOption.ASYNC_EXECUTE,
            processes.ProcessJobControlOption.SYNC_EXECUTE
        ]
    else:
        processor.process_description.job_control_options = [
            processes.ProcessJobControlOption.SYNC_EXECUTE]

    chosen_mode, additional_headers = manager._select_execution_mode(
        requested_mode, processor)
    assert chosen_mode == expected_chosen
    assert additional_headers == expected_headers


@pytest.mark.parametrize('requested_output, generated_output, expected', [
    pytest.param(
        processes.ExecutionOutput(),
        processes.OutputExecutionResultInternal(
            location='dummy-location', media_type='dummy-media-type'),
        ('dummy contents', 'dummy-media-type', [])
    ),
    pytest.param(
        processes.ExecutionOutput(
            transmissionMode=processes.ProcessOutputTransmissionMode.VALUE),
        processes.OutputExecutionResultInternal(
            location='dummy-location', media_type='dummy-media-type'),
        ('dummy contents', 'dummy-media-type', [])
    ),
    pytest.param(
        processes.ExecutionOutput(
            transmissionMode=processes.ProcessOutputTransmissionMode.REFERENCE),  # noqa: E501
        processes.OutputExecutionResultInternal(
            location='dummy-location', media_type='dummy-media-type'),
        (None, None, ['<dummy-location>'])
    ),
])
def test_get_execution_response_single_output(
        config, requested_output, generated_output, expected):
    manager = get_manager(config)
    with mock.patch(
            'pygeoapi.process.manager.base.Path', autospec=True) as mock_Path:
        mock_Path.return_value.read_bytes.return_value = 'dummy contents'
        payload, media_type, headers = manager._get_execution_response_single_output(  # noqa: E501
            requested_output, generated_output, 'hello-world'
        )
    assert payload == expected[0]
    assert media_type == expected[1]
    assert headers == expected[2]


@pytest.mark.parametrize(
    'requested_outputs, generated_outputs, expected_type', [
        pytest.param(
            {},
            {
                'first': processes.OutputExecutionResultInternal(
                    location='dummy1', media_type='text/plain'),
                'second': processes.OutputExecutionResultInternal(
                    location='dummy2', media_type='text/plain')
            },
            'text/plain'
        ),
        pytest.param(
            {
                'first': processes.ExecutionOutput(
                    transmissionMode=processes.ProcessOutputTransmissionMode.REFERENCE)  # noqa: E501
            },
            {
                'first': processes.OutputExecutionResultInternal(
                    location='dummy1', media_type='text/plain'),
                'second': processes.OutputExecutionResultInternal(
                    location='dummy2', media_type='text/plain')
            },
            'text/plain'
        ),
    ]
)
def test_get_execution_response_multiple_outputs(
        config, requested_outputs, generated_outputs, expected_type):
    manager = get_manager(config)
    with mock.patch(
            'pygeoapi.process.manager.base.Path', autospec=True) as mock_Path:
        mock_Path.return_value.read_bytes.side_effect = [
            'dummy1-content',
            'dummy2-content',
        ]
        result = manager._get_execution_response_multiple_outputs(
            requested_outputs, generated_outputs, 'hello-world',
            multipart_boundary='***123***'
        )
        message = message_from_bytes(result)
        print(message)
        assert message.is_multipart()
        assert message.get_default_type() == expected_type
        for part in message.get_payload():
            content_id = part['Content-ID']
            print(f'processing part with Content-ID: {content_id!r}...')
            assert content_id in generated_outputs.keys()
            requested_detail = requested_outputs.get(content_id)
            print(f'requested_detail: {requested_detail}')
            if requested_detail is not None:
                by_reference = (
                        requested_detail.transmission_mode ==
                        processes.ProcessOutputTransmissionMode.REFERENCE.value
                )
                print(f'by_reference: {by_reference}')
                if by_reference:
                    assert len(part.get_all('Content-Location', failobj=[])) > 0  # noqa: E501


@pytest.mark.parametrize(
    'requested_outputs, generated_outputs, output_contents, expected',
    [
        pytest.param(
            {
                'fourth': processes.ExecutionOutput(
                    transmissionMode=processes.ProcessOutputTransmissionMode.REFERENCE)  # noqa: E501
            },
            {
                'first': processes.OutputExecutionResultInternal(
                    location='dummy-first-location',
                    media_type='text/plain'
                ),
                'second': processes.OutputExecutionResultInternal(
                    location='dummy-second-location',
                    media_type='application/octet-stream'
                ),
                'third': processes.OutputExecutionResultInternal(
                    location='dummy-third-location',
                    media_type='application/json'
                ),
                'fourth': processes.OutputExecutionResultInternal(
                    location='dummy-fourth-location',
                    media_type='foo'
                )
            },
            [
                b'hi, this is a dummy text for output named first',
                Point(0, 0).wkb,
                bytes(json.dumps({'something': 'here'}), 'utf-8'),
                b'hey, this is some bogus content, which will not be shown'
            ],
            (
                    '{'
                    '"first": "hi, this is a dummy text for output named first", '  # noqa: E501
                    '"second": "AQEAAAAAAAAAAAAAAAAAAAAAAAAA", '
                    '"third": {"value": {"something": "here"}}, '
                    '"fourth": {"href": "dummy-fourth-location", "type": "foo"}'  # noqa: E501
                    '}'
            ),
        )
    ])
def test_get_execution_response_document(
        config, requested_outputs, generated_outputs,
        output_contents, expected
):
    manager = get_manager(config)
    with mock.patch(
            'pygeoapi.process.manager.base.Path', autospec=True) as mock_Path:
        mock_Path.return_value.read_bytes.side_effect = output_contents
        result = manager._get_execution_response_document(
            requested_outputs, generated_outputs, 'hello-world')
        assert result == expected
