# =================================================================

# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Sander Schaminee <sander.schaminee@geocat.net>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#          Bernhard Mallinger <bernhard.mallinger@eox.at>
#          Francesco Martinelli <francesco.martinelli@ingv.it>
#
# Copyright (c) 2024 Tom Kralidis
# Copyright (c) 2022 Francesco Bartoli
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
# Copyright (c) 2023 Ricardo Garcia Silva
# Copyright (c) 2024 Bernhard Mallinger
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


from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
import json
import logging
from typing import Tuple

from pygeoapi import l10n
from pygeoapi.util import (
    json_serial, render_j2_template, JobStatus, RequestedProcessExecutionMode,
    to_json, DATETIME_FORMAT)
from pygeoapi.process.base import (
    JobNotFoundError, JobResultNotFoundError, ProcessorExecuteError
)
from pygeoapi.process.manager.base import get_manager, Subscriber

from . import (
    APIRequest, API, SYSTEM_LOCALE, F_JSON, FORMAT_TYPES, F_HTML, F_JSONLD,
)

LOGGER = logging.getLogger(__name__)

CONFORMANCE_CLASSES = [
    'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/ogc-process-description', # noqa
    'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/json',
    'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/oas30',
    'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/callback'
]


def describe_processes(api: API, request: APIRequest,
                       process=None) -> Tuple[dict, int, str]:
    """
    Provide processes metadata

    :param request: A request object
    :param process: process identifier, defaults to None to obtain
                    information about all processes

    :returns: tuple of headers, status code, content
    """

    processes = []

    headers = request.get_response_headers(**api.api_headers)

    if process is not None:
        if process not in api.manager.processes.keys():
            msg = 'Identifier not found'
            return api.get_exception(
                HTTPStatus.NOT_FOUND, headers,
                request.format, 'NoSuchProcess', msg)

    if len(api.manager.processes) > 0:
        if process is not None:
            relevant_processes = [process]
        else:
            LOGGER.debug('Processing limit parameter')
            try:
                limit = int(request.params.get('limit'))

                if limit <= 0:
                    msg = 'limit value should be strictly positive'
                    return api.get_exception(
                        HTTPStatus.BAD_REQUEST, headers, request.format,
                        'InvalidParameterValue', msg)

                relevant_processes = list(api.manager.processes)[:limit]
            except TypeError:
                LOGGER.debug('returning all processes')
                relevant_processes = api.manager.processes.keys()
            except ValueError:
                msg = 'limit value should be an integer'
                return api.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format,
                    'InvalidParameterValue', msg)

        for key in relevant_processes:
            p = api.manager.get_processor(key)
            p2 = l10n.translate_struct(deepcopy(p.metadata),
                                       request.locale)
            p2['id'] = key

            if process is None:
                p2.pop('inputs')
                p2.pop('outputs')
                p2.pop('example', None)

            p2['jobControlOptions'] = ['sync-execute']
            if api.manager.is_async:
                p2['jobControlOptions'].append('async-execute')

            p2['outputTransmission'] = ['value']
            p2['links'] = p2.get('links', [])

            jobs_url = f"{api.base_url}/jobs"
            process_url = f"{api.base_url}/processes/{key}"

            # TODO translation support
            link = {
                'type': FORMAT_TYPES[F_JSON],
                'rel': request.get_linkrel(F_JSON),
                'href': f'{process_url}?f={F_JSON}',
                'title': l10n.translate('Process description as JSON', request.locale),  # noqa
                'hreflang': api.default_locale
            }
            p2['links'].append(link)

            link = {
                'type': FORMAT_TYPES[F_HTML],
                'rel': request.get_linkrel(F_HTML),
                'href': f'{process_url}?f={F_HTML}',
                'title': l10n.translate('Process description as HTML', request.locale),  # noqa
                'hreflang': api.default_locale
            }
            p2['links'].append(link)

            link = {
                'type': FORMAT_TYPES[F_HTML],
                'rel': 'http://www.opengis.net/def/rel/ogc/1.0/job-list',
                'href': f'{jobs_url}?f={F_HTML}',
                'title': l10n.translate('Jobs for this process as HTML', request.locale),  # noqa
                'hreflang': api.default_locale
            }
            p2['links'].append(link)

            link = {
                'type': FORMAT_TYPES[F_JSON],
                'rel': 'http://www.opengis.net/def/rel/ogc/1.0/job-list',
                'href': f'{jobs_url}?f={F_JSON}',
                'title': l10n.translate('Jobs for this process as HTML', request.locale),  # noqa
                'hreflang': api.default_locale
            }
            p2['links'].append(link)

            link = {
                'type': FORMAT_TYPES[F_JSON],
                'rel': 'http://www.opengis.net/def/rel/ogc/1.0/execute',
                'href': f'{process_url}/execution?f={F_JSON}',
                'title': l10n.translate('Execution for this process as JSON', request.locale),  # noqa
                'hreflang': api.default_locale
            }
            p2['links'].append(link)

            processes.append(p2)

    if process is not None:
        response = processes[0]
    else:
        process_url = f"{api.base_url}/processes"
        response = {
            'processes': processes,
            'links': [{
                'type': FORMAT_TYPES[F_JSON],
                'rel': request.get_linkrel(F_JSON),
                'title': l10n.translate('This document as JSON', request.locale),  # noqa
                'href': f'{process_url}?f={F_JSON}'
            }, {
                'type': FORMAT_TYPES[F_JSONLD],
                'rel': request.get_linkrel(F_JSONLD),
                'title': l10n.translate('This document as RDF (JSON-LD)', request.locale),  # noqa
                'href': f'{process_url}?f={F_JSONLD}'
            }, {
                'type': FORMAT_TYPES[F_HTML],
                'rel': request.get_linkrel(F_HTML),
                'title': l10n.translate('This document as HTML', request.locale),  # noqa
                'href': f'{process_url}?f={F_HTML}'
            }]
        }

    if request.format == F_HTML:  # render
        if process is not None:
            response = render_j2_template(api.tpl_config,
                                          'processes/process.html',
                                          response, request.locale)
        else:
            response = render_j2_template(api.tpl_config,
                                          'processes/index.html', response,
                                          request.locale)

        return headers, HTTPStatus.OK, response

    return headers, HTTPStatus.OK, to_json(response, api.pretty_print)


# TODO: get_jobs doesn't have tests
def get_jobs(api: API, request: APIRequest,
             job_id=None) -> Tuple[dict, int, str]:
    """
    Get process jobs

    :param request: A request object
    :param job_id: id of job

    :returns: tuple of headers, status code, content
    """

    headers = request.get_response_headers(SYSTEM_LOCALE,
                                           **api.api_headers)
    if job_id is None:
        jobs = sorted(api.manager.get_jobs(),
                      key=lambda k: k['job_start_datetime'],
                      reverse=True)
    else:
        try:
            jobs = [api.manager.get_job(job_id)]
        except JobNotFoundError:
            return api.get_exception(
                HTTPStatus.NOT_FOUND, headers, request.format,
                'InvalidParameterValue', job_id)

    serialized_jobs = {
        'jobs': [],
        'links': [{
            'href': f"{api.base_url}/jobs?f={F_HTML}",
            'rel': request.get_linkrel(F_HTML),
            'type': FORMAT_TYPES[F_HTML],
            'title': l10n.translate('Jobs list as HTML', request.locale)
        }, {
            'href': f"{api.base_url}/jobs?f={F_JSON}",
            'rel': request.get_linkrel(F_JSON),
            'type': FORMAT_TYPES[F_JSON],
            'title': l10n.translate('Jobs list as JSON', request.locale)
        }]
    }
    for job_ in jobs:
        job2 = {
            'type': 'process',
            'processID': job_['process_id'],
            'jobID': job_['identifier'],
            'status': job_['status'],
            'message': job_['message'],
            'progress': job_['progress'],
            'parameters': job_.get('parameters'),
            'job_start_datetime': job_['job_start_datetime'],
            'job_end_datetime': job_['job_end_datetime']
        }

        # TODO: translate
        if JobStatus[job_['status']] in (
           JobStatus.successful, JobStatus.running, JobStatus.accepted):

            job_result_url = f"{api.base_url}/jobs/{job_['identifier']}/results"  # noqa

            job2['links'] = [{
                'href': f'{job_result_url}?f={F_HTML}',
                'rel': 'http://www.opengis.net/def/rel/ogc/1.0/results',
                'type': FORMAT_TYPES[F_HTML],
                'title': l10n.translate(f'Results of job as HTML', request.locale),  # noqa
            }, {
                'href': f'{job_result_url}?f={F_JSON}',
                'rel': 'http://www.opengis.net/def/rel/ogc/1.0/results',
                'type': FORMAT_TYPES[F_JSON],
                'title': l10n.translate(f'Results of job as JSON', request.locale),  # noqa
            }]

            if job_['mimetype'] not in (FORMAT_TYPES[F_JSON],
                                        FORMAT_TYPES[F_HTML]):

                job2['links'].append({
                    'href': job_result_url,
                    'rel': 'http://www.opengis.net/def/rel/ogc/1.0/results',  # noqa
                    'type': job_['mimetype'],
                    'title': f"Results of job {job_id} as {job_['mimetype']}"  # noqa
                })

        serialized_jobs['jobs'].append(job2)

    if job_id is None:
        j2_template = 'jobs/index.html'
    else:
        serialized_jobs = serialized_jobs['jobs'][0]
        j2_template = 'jobs/job.html'

    if request.format == F_HTML:
        data = {
            'jobs': serialized_jobs,
            'now': datetime.now(timezone.utc).strftime(DATETIME_FORMAT)
        }
        response = render_j2_template(api.tpl_config, j2_template, data,
                                      request.locale)
        return headers, HTTPStatus.OK, response

    return headers, HTTPStatus.OK, to_json(serialized_jobs,
                                           api.pretty_print)


def execute_process(api: API, request: APIRequest,
                    process_id) -> Tuple[dict, int, str]:
    """
    Execute process

    :param request: A request object
    :param process_id: id of process

    :returns: tuple of headers, status code, content
    """

    # Responses are always in US English only
    headers = request.get_response_headers(SYSTEM_LOCALE,
                                           **api.api_headers)
    if process_id not in api.manager.processes:
        msg = 'identifier not found'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers,
            request.format, 'NoSuchProcess', msg)

    data = request.data
    if not data:
        # TODO not all processes require input, e.g. time-dependent or
        #      random value generators
        msg = 'missing request data'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'MissingParameterValue', msg)

    try:
        # Parse bytes data, if applicable
        data = data.decode()
        LOGGER.debug(data)
    except (UnicodeDecodeError, AttributeError):
        pass

    try:
        data = json.loads(data)
    except (json.decoder.JSONDecodeError, TypeError):
        # Input does not appear to be valid JSON
        msg = 'invalid request data'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    data_dict = data.get('inputs', {})
    LOGGER.debug(data_dict)

    requested_outputs = data.get('outputs')
    LOGGER.debug(f'outputs: {requested_outputs}')

    subscriber = None
    subscriber_dict = data.get('subscriber')
    if subscriber_dict:
        try:
            success_uri = subscriber_dict['successUri']
        except KeyError:
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'MissingParameterValue', 'Missing successUri')
        else:
            subscriber = Subscriber(
                # NOTE: successUri is mandatory according to the standard
                success_uri=success_uri,
                in_progress_uri=subscriber_dict.get('inProgressUri'),
                failed_uri=subscriber_dict.get('failedUri'),
            )

    try:
        execution_mode = RequestedProcessExecutionMode(
            request.headers.get('Prefer', request.headers.get('prefer'))
        )
    except ValueError:
        execution_mode = None
    try:
        LOGGER.debug('Executing process')
        result = api.manager.execute_process(
            process_id, data_dict, execution_mode=execution_mode,
            requested_outputs=requested_outputs,
            subscriber=subscriber)
        job_id, mime_type, outputs, status, additional_headers = result
        headers.update(additional_headers or {})
        headers['Location'] = f'{api.base_url}/jobs/{job_id}'
    except ProcessorExecuteError as err:
        return api.get_exception(
            err.http_status_code, headers,
            request.format, err.ogc_exception_code, err.message)

    response = {}
    if status == JobStatus.failed:
        response = outputs

    if data.get('response', 'raw') == 'raw':
        headers['Content-Type'] = mime_type
        response = outputs
    elif status not in (JobStatus.failed, JobStatus.accepted):
        response['outputs'] = [outputs]

    if status == JobStatus.accepted:
        http_status = HTTPStatus.CREATED
    elif status == JobStatus.failed:
        http_status = HTTPStatus.BAD_REQUEST
    else:
        http_status = HTTPStatus.OK

    if mime_type == 'application/json':
        response2 = to_json(response, api.pretty_print)
    else:
        response2 = response

    return headers, http_status, response2


def get_job_result(api: API, request: APIRequest,
                   job_id) -> Tuple[dict, int, str]:
    """
    Get result of job (instance of a process)

    :param request: A request object
    :param job_id: ID of job

    :returns: tuple of headers, status code, content
    """

    headers = request.get_response_headers(SYSTEM_LOCALE,
                                           **api.api_headers)
    try:
        job = api.manager.get_job(job_id)
    except JobNotFoundError:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers,
            request.format, 'NoSuchJob', job_id
        )

    status = JobStatus[job['status']]

    if status == JobStatus.running:
        msg = 'job still running'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers,
            request.format, 'ResultNotReady', msg)

    elif status == JobStatus.accepted:
        # NOTE: this case is not mentioned in the specification
        msg = 'job accepted but not yet running'
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers,
            request.format, 'ResultNotReady', msg)

    elif status == JobStatus.failed:
        msg = 'job failed'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    try:
        mimetype, job_output = api.manager.get_job_result(job_id)
    except JobResultNotFoundError:
        return api.get_exception(
            HTTPStatus.INTERNAL_SERVER_ERROR, headers,
            request.format, 'JobResultNotFound', job_id
        )

    if mimetype not in (None, FORMAT_TYPES[F_JSON]):
        headers['Content-Type'] = mimetype
        content = job_output
    else:
        if request.format == F_JSON:
            content = json.dumps(job_output, sort_keys=True, indent=4,
                                 default=json_serial)
        else:
            # HTML
            headers['Content-Type'] = "text/html"
            data = {
                'job': {'id': job_id},
                'result': job_output
            }
            content = render_j2_template(
                api.config, 'jobs/results/index.html',
                data, request.locale)

    return headers, HTTPStatus.OK, content


def delete_job(
    api: API, request: APIRequest, job_id
) -> Tuple[dict, int, str]:
    """
    Delete a process job

    :param job_id: job identifier

    :returns: tuple of headers, status code, content
    """
    response_headers = request.get_response_headers(
        SYSTEM_LOCALE, **api.api_headers)
    try:
        success = api.manager.delete_job(job_id)
    except JobNotFoundError:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, response_headers, request.format,
            'NoSuchJob', job_id
        )
    else:
        if success:
            http_status = HTTPStatus.OK
            jobs_url = f"{api.base_url}/jobs"

            response = {
                'jobID': job_id,
                'status': JobStatus.dismissed.value,
                'message': 'Job dismissed',
                'progress': 100,
                'links': [{
                    'href': jobs_url,
                    'rel': 'up',
                    'type': FORMAT_TYPES[F_JSON],
                    'title': l10n.translate('The job list for the current process', request.locale)  # noqa
                }]
            }
        else:
            return api.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR, response_headers,
                request.format, 'InternalError', job_id
            )
    LOGGER.info(response)
    # TODO: this response does not have any headers
    return {}, http_status, response


def get_oas_30(cfg: dict, locale: str) -> tuple[list[dict[str, str]], dict[str, dict]]:  # noqa
    """
    Get OpenAPI fragments

    :param cfg: `dict` of configuration
    :param locale: `str` of locale

    :returns: `tuple` of `list` of tag objects, and `dict` of path objects
    """

    from pygeoapi.openapi import OPENAPI_YAML

    LOGGER.debug('setting up processes endpoints')

    oas = {'tags': []}

    paths = {}

    process_manager = get_manager(cfg)

    if len(process_manager.processes) > 0:
        paths['/processes'] = {
            'get': {
                'summary': 'Processes',
                'description': 'Processes',
                'tags': ['server'],
                'operationId': 'getProcesses',
                'parameters': [
                    {'$ref': '#/components/parameters/f'}
                ],
                'responses': {
                    '200': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/ProcessList.yaml"},  # noqa
                    'default': {'$ref': '#/components/responses/default'}
                }
            }
        }

    LOGGER.debug('setting up processes')

    for k, v in process_manager.processes.items():
        if k.startswith('_'):
            LOGGER.debug(f'Skipping hidden layer: {k}')
            continue
        name = l10n.translate(k, locale)
        p = process_manager.get_processor(k)
        md_desc = l10n.translate(p.metadata['description'], locale)
        process_name_path = f'/processes/{name}'
        tag = {
            'name': name,
            'description': md_desc,
            'externalDocs': {}
        }
        for link in p.metadata.get('links', []):
            if link['type'] == 'information':
                translated_link = l10n.translate(link, locale)
                tag['externalDocs']['description'] = translated_link[
                    'type']
                tag['externalDocs']['url'] = translated_link['url']
                break
        if len(tag['externalDocs']) == 0:
            del tag['externalDocs']

        oas['tags'].append(tag)

        paths[process_name_path] = {
            'get': {
                'summary': 'Get process metadata',
                'description': md_desc,
                'tags': [name],
                'operationId': f'describe{name.capitalize()}Process',
                'parameters': [
                    {'$ref': '#/components/parameters/f'}
                ],
                'responses': {
                    '200': {'$ref': '#/components/responses/200'},
                    'default': {'$ref': '#/components/responses/default'}
                }
            }
        }

        paths[f'{process_name_path}/execution'] = {
            'post': {
                'summary': f"Process {l10n.translate(p.metadata['title'], locale)} execution",  # noqa
                'description': md_desc,
                'tags': [name],
                'operationId': f'execute{name.capitalize()}Job',
                'responses': {
                    '200': {'$ref': '#/components/responses/200'},
                    '201': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/ExecuteAsync.yaml"},  # noqa
                    '404': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/NotFound.yaml"},  # noqa
                    '500': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/ServerError.yaml"},  # noqa
                    'default': {'$ref': '#/components/responses/default'}
                },
                'requestBody': {
                    'description': 'Mandatory execute request JSON',
                    'required': True,
                    'content': {
                        'application/json': {
                            'schema': {
                                '$ref': f"{OPENAPI_YAML['oapip']}/schemas/execute.yaml"  # noqa
                            }
                        }
                    }
                }
            }
        }
        if 'example' in p.metadata:
            paths[f'{process_name_path}/execution']['post']['requestBody']['content']['application/json']['example'] = p.metadata['example']  # noqa

    name_in_path = {
        'name': 'jobId',
        'in': 'path',
        'description': 'job identifier',
        'required': True,
        'schema': {
            'type': 'string'
        }
    }

    paths['/jobs'] = {
        'get': {
            'summary': 'Retrieve jobs list',
            'description': 'Retrieve a list of jobs',
            'tags': ['jobs'],
            'operationId': 'getJobs',
            'responses': {
                '200': {'$ref': '#/components/responses/200'},
                '404': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/NotFound.yaml"},  # noqa
                'default': {'$ref': '#/components/responses/default'}
            }
        }
    }

    paths['/jobs/{jobId}'] = {
        'get': {
            'summary': 'Retrieve job details',
            'description': 'Retrieve job details',
            'tags': ['jobs'],
            'parameters': [
                name_in_path,
                {'$ref': '#/components/parameters/f'}
            ],
            'operationId': 'getJob',
            'responses': {
                '200': {'$ref': '#/components/responses/200'},
                '404': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/NotFound.yaml"},  # noqa
                'default': {'$ref': '#/components/responses/default'}
            }
        },
        'delete': {
            'summary': 'Cancel / delete job',
            'description': 'Cancel / delete job',
            'tags': ['jobs'],
            'parameters': [
                name_in_path
            ],
            'operationId': 'deleteJob',
            'responses': {
                '204': {'$ref': '#/components/responses/204'},
                '404': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/NotFound.yaml"},  # noqa
                'default': {'$ref': '#/components/responses/default'}
            }
        },
    }

    paths['/jobs/{jobId}/results'] = {
        'get': {
            'summary': 'Retrieve job results',
            'description': 'Retrieve job results',
            'tags': ['jobs'],
            'parameters': [
                name_in_path,
                {'$ref': '#/components/parameters/f'}
            ],
            'operationId': 'getJobResults',
            'responses': {
                '200': {'$ref': '#/components/responses/200'},
                '404': {'$ref': f"{OPENAPI_YAML['oapip']}/responses/NotFound.yaml"},  # noqa
                'default': {'$ref': '#/components/responses/default'}
            }
        }
    }

    return [{'name': 'processes'}, {'name': 'jobs'}], {'paths': paths}
