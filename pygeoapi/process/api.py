# =================================================================
#
# Authors: Ricardo Garcia Silva <ricardo.garcia.silva@gmail.com>
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
"""Utilities for dealing with the implementation of OGC API - Processes
specification.
"""
from base64 import urlsafe_b64encode
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
from http import HTTPStatus
import json
import logging
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
    Union
)
import urllib.parse

from babel import Locale
import pydantic
from werkzeug.datastructures import ImmutableMultiDict

from .. import l10n
from ..models.processes import (
    Execution,
    ExecutionDocumentResult,
    ExecutionDocumentSingleOutput,
    ExecutionResultInternal,
    JobList,
    JobStatus,
    JobStatusInfoInternal,
    JobStatusInfoRead,
    Link,
    ProcessDescription,
    ProcessExecutionMode,
    ProcessList,
    ProcessOutputTransmissionMode,
    ProcessResponseType,
    RequestedProcessExecutionMode,
)
from ..process.base import ProcessorGenericError
from ..process.manager import get_manager
from ..process.manager.base import BaseManager
from .. import util

LOGGER = logging.getLogger(__name__)


class ProcessApi:
    manager: BaseManager
    base_url: str
    default_locale: Locale

    def __init__(
            self, manager: BaseManager, base_url: str, default_locale: Locale):
        self.manager = manager
        self.base_url = base_url
        self.default_locale = default_locale

    @classmethod
    def from_main_api(cls, api):
        return cls(api.manager, api.base_url, api.default_locale)

    @classmethod
    def from_config(cls, config: Dict):
        locales = l10n.get_locales(config)
        return cls(
            manager=get_manager(config),
            base_url=util.get_base_url(config),
            default_locale=locales[0]
        )

    def describe_processes(
            self,
            request,
            process=None
    ) -> ProcessList:
        """
        Provide processes metadata

        :param request: A request object
        :param process: process identifier, defaults to None to obtain
                        information about all processes

        :returns: processes description
        """

        pagination_links = []
        if len(self.manager.processes) > 0:
            if process is None:
                relevant, pagination_links = self._filter_processes(
                    raw_limit=request.params.get('limit'),
                    raw_offset=request.params.get('offset')
                )
            else:
                try:
                    processor = self.manager.get_processor(process)
                except ProcessorGenericError:
                    # error, could not find process with that id
                    # TODO: raise an error to the client
                    relevant = []
                else:
                    relevant = [processor.process_metadata]
        else:
            relevant = []
        process_descriptions = []
        for description in relevant:
            translated_description = l10n.translate_model(
                description, request.locale)
            translated_description.links.extend(
                _generate_process_description_links(
                    request.get_linkrel,
                    description.id,
                    self.base_url,
                    self.default_locale)
            )
            process_descriptions.append(translated_description)
        process_url = f"{self.base_url}/processes"
        return ProcessList(
            processes=process_descriptions,
            links=[
                Link(
                    type=util.FORMAT_TYPES[util.F_JSON],
                    rel=request.get_linkrel(util.F_JSON),
                    title="This document as JSON",
                    href=f"{process_url}?f={util.F_JSON}"
                ),
                Link(
                    type=util.FORMAT_TYPES[util.F_JSONLD],
                    rel=request.get_linkrel(util.F_JSONLD),
                    title="This document as RDF (JSON-LD)",
                    href=f"{process_url}?f={util.F_JSONLD}"
                ),
                Link(
                    type=util.FORMAT_TYPES[util.F_HTML],
                    rel=request.get_linkrel(util.F_HTML),
                    title="This document as HTML",
                    href=f"{process_url}?f={util.F_HTML}"
                ),
                *pagination_links
            ]
        )

    def execute_process(
            self,
            process_id: str,
            request_headers: Mapping,
            request_payload: Optional[str],
            response_headers: MutableMapping,
    ) -> Tuple[int, bytes, Dict[str, str]]:
        """
        Execute process

        :param request_headers: The request's headers
        :param request_payload: Raw request payload
        :param response_headers: Already initialized response headers
        :param process_id: id of process to be executed

        :returns: tuple of status code, response payload, HTTP headers
        """

        try:
            payload = json.loads(request_payload)
            execution_request = Execution(**payload)
        except (
                json.JSONDecodeError,
                TypeError,
                pydantic.ValidationError
        ) as err:
            LOGGER.error(err)
            raise RuntimeError("InvalidParameterValue")
        else:
            try:
                execution_mode = RequestedProcessExecutionMode(
                    request_headers.get('Prefer'))
            except ValueError:
                execution_mode = None
            (
                job_id,
                execution_result,
                chosen_execution_mode,
                additional_headers
            ) = self.manager.execute_process(
                process_id, execution_request, execution_mode)
            if chosen_execution_mode == ProcessExecutionMode.sync_execute:
                location_link = Link(href=f'{self.base_url}/jobs/{job_id}')
                pass  # FIXME
                # as per OAproc, if the execution mode is sync and the server
                # creates a job, then the response shall include
                # Link header with rel=monitor, pointing to the
                # created job

            payload, media_type, additional_headers = get_execution_response(
                execution_request, execution_result)

            response_headers['Content-Type'] = media_type
            if execution_result.status in (
                    JobStatus.accepted,
                    JobStatus.running
            ):
                http_status = HTTPStatus.CREATED
            elif execution_result.status == JobStatus.successful:
                http_status = HTTPStatus.OK
            else:
                # we don't expect to ever reach this section, since processing
                # errors must raise an exception to be handled at the outer
                # layer
                raise RuntimeError(
                    f"Unexpected job status: {execution_result.status!r}")
            return http_status, payload, response_headers

    def get_jobs(
            self,
            request: Union[APIRequest, Any],
            job_id=None
    ) -> JobList:
        """
        Get process jobs

        :param request: A request object
        :param job_id: id of job

        :returns: tuple of headers, status code, content
        """
        response_links = []
        for media_type, name in ((util.F_HTML, "HTML"), (util.F_JSON, "JSON")):
            response_links.append(
                Link(
                    href=f"{self.base_url}/jobs/?f={media_type}",
                    type=util.FORMAT_TYPES[media_type],
                    rel=request.get_linkrel(media_type),
                    title=f'Job list as {name}'
                )
            )
        if job_id is not None:
            jobs = [self.manager.get_job(job_id)]
        else:
            jobs, pagination_links = self._filter_jobs(request.params)
            response_links.extend(pagination_links)

        job_reads = []
        for job in jobs:
            job_reads.append(_prepare_job_for_response(job, self.base_url))
        return JobList(jobs=job_reads, links=response_links)

    def _filter_processes(
            self,
            raw_limit: Optional[str],
            raw_offset: Optional[str],
    ) -> Tuple[List[ProcessDescription], List[Link]]:
        limit = util.parse_positive_int_parameter(raw_limit)
        offset = util.parse_positive_int_parameter(raw_offset, default_value=0)
        total_filtered, processes = self.manager.get_process_descriptions(
            limit, offset)
        pagination_links = _get_pagination_links(
            len(processes), limit, offset, total_filtered,
            base_url=f"{self.base_url}/processes",
            title_fragment="process list"
        )
        return processes, pagination_links

    def _filter_jobs(
            self, request_params: ImmutableMultiDict
    ) -> Tuple[List[JobStatusInfoInternal], List[Link]]:
        requested_filters = {
            'type': request_params.getlist('type'),
            'processID': request_params.getlist('processID'),
            'status': request_params.getlist('status'),
            'datetime': request_params.get('datetime'),
            'minDuration': request_params.get('minDuration'),
            'maxDuration': request_params.get('maxDuration'),
        }
        requested_filters = {
            k: v for k, v in requested_filters.items() if v is not None}
        try:
            status_filter = (
                    [JobStatus(s) for s in requested_filters['status']]
                    or None
            )
        except ValueError:
            LOGGER.warning(
                f"Received invalid status: {requested_filters['status']!r}"
            )
            status_filter = None
        limit = util.parse_positive_int_parameter(
            request_params.get('limit'), default_value=10)
        offset = util.parse_positive_int_parameter(
            request_params.get('offset'), default_value=0)
        total_filtered_jobs, jobs = self.manager.get_jobs(
            type_=requested_filters.get('type') or None,
            process_id=requested_filters.get('processID') or None,
            status=status_filter,
            date_time=requested_filters.get('datetime'),
            min_duration_seconds=util.parse_positive_int_parameter(
                requested_filters.get('minDuration')),
            max_duration_seconds=util.parse_positive_int_parameter(
                requested_filters.get('maxDuration')),
            limit=limit,
            offset=offset,
        )
        pagination_links = _get_pagination_links(
            len(jobs), limit, offset, total_filtered_jobs,
            base_url=f'{self.base_url}/jobs',
            title_fragment='job list',
            querystring_params=requested_filters
        )
        return jobs, pagination_links


def _get_pagination_links(
        num_returned_records: int,
        limit: int,
        offset: int,
        total_records: int,
        base_url: str,
        title_fragment: str,
        querystring_params: Optional[Dict[str, str]] = None,
) -> List[Link]:
    result = []
    base_querystring = {
        'limit': limit,
        **(querystring_params if querystring_params is not None else {})
    }
    LOGGER.debug(f'locals: {locals()}')
    if offset + num_returned_records < total_records:
        querystring = {
            'offset': offset + limit,
            **base_querystring,
        }
        html_querystring = urllib.parse.urlencode(
            {'f': util.F_HTML, **querystring}, doseq=True)
        json_querystring = urllib.parse.urlencode(
            {'f': util.F_JSON, **querystring}, doseq=True)
        result.extend(
            [
                Link(
                    href=f'{base_url}?{html_querystring}',
                    type=util.FORMAT_TYPES[util.F_HTML],
                    rel='next',
                    title=f'Next page of {title_fragment}, as HTML'
                ),
                Link(
                    href=f'{base_url}?{json_querystring}',
                    type=util.FORMAT_TYPES[util.F_JSON],
                    rel='next',
                    title=f'Next page of {title_fragment}, as JSON'
                ),
            ]
        )
    if offset + num_returned_records > limit:
        querystring = {
            'offset': max(offset - limit, 0),
            **base_querystring,
        }
        html_querystring = urllib.parse.urlencode(
            {'f': util.F_HTML, **querystring}, doseq=True)
        json_querystring = urllib.parse.urlencode(
            {'f': util.F_JSON, **querystring}, doseq=True)
        result.extend(
            [
                Link(
                    href=f'{base_url}?{html_querystring}',
                    type=util.FORMAT_TYPES[util.F_HTML],
                    rel='prev',
                    title=f'Previous page of {title_fragment}, as HTML'
                ),
                Link(
                    href=f'{base_url}?{json_querystring}',
                    type=util.FORMAT_TYPES[util.F_JSON],
                    rel='prev',
                    title=f'Previous page of {title_fragment}, as JSON'
                )

            ]
        )
    return result


def get_execution_response(
        execution_request: Execution,
        execution_result: ExecutionResultInternal,
) -> Tuple[bytes, Optional[str], List[Link]]:
    media_type = None
    payload = None
    additional_headers = []
    if len(execution_result.outputs) == 0:
        LOGGER.info('there are no outputs to include in the response')
    elif execution_request.response == ProcessResponseType.raw:
        if len(execution_result.outputs) == 1:
            payload, media_type, additional_headers = (
                _get_execution_response_single_output(
                    execution_request, execution_result)
            )
        else:
            any_by_value = ProcessOutputTransmissionMode.VALUE in [
                out.transmission_mode for out in
                execution_request.outputs.values()
            ]
            media_type = 'multipart/related' if any_by_value else None
            payload = _get_execution_response_multiple_outputs(
                execution_request, execution_result)
    else:
        media_type = 'application/json'
        payload = _get_execution_response_document(
            execution_request, execution_result)
    return payload, media_type, additional_headers


def _get_execution_response_single_output(
        execution_request: Execution,
        execution_result: ExecutionResultInternal
) -> Tuple[Optional[bytes], str, List]:
    """Get process execution response for when there is a single process output

    If there is a single execition output:
    - If transmission is by value, return the output directly
    - If transmission is by reference, include a link header
      for where the output can be downloaded

    :param execution_request: The parameters that originated the execution
    :param execution_result: Execution results
    """
    out_id, requested_output = execution_request.outputs.items()[0]
    should_transmit_by_value = (
            requested_output.transmission_mode ==
            ProcessOutputTransmissionMode.VALUE
    )
    generated_output = execution_result.outputs.items()[0]
    additional_headers = []
    if should_transmit_by_value:
        media_type = generated_output.media_type
        payload = Path(generated_output.location).read_bytes()
    else:
        media_type = None
        payload = None
        additional_headers.append(
            Link(href=None, rel=None, title=None).as_link_header()
        )
    return payload, media_type, additional_headers


def _get_execution_response_multiple_outputs(
        execution_request: Execution,
        execution_result: ExecutionResultInternal,
) -> bytes:
    """Generate an appropriate body for process execution HTTP responses

    According to the OAProc spec (Requirement 31 -
    /req/core/process-execute-sync-raw-mixed-multi),
    if there are multiple outputs, then responses should have a media type
    of `multipart/related` and, depending on the transmission mode, either
    include the contents directly in the response, or include
    links to them.
    """
    payload = MIMEMultipart("related")
    for output_id, generated_output in execution_result.outputs.items():
        requested = execution_request.outputs.get(output_id)
        part = MIMENonMultipart(
            *generated_output.media_type.split('/'), )
        part.set_param('Type', generated_output.media_type)
        part.add_header('Content-ID', output_id)
        should_transmit_by_value = (
                requested.transmission_mode ==
                ProcessOutputTransmissionMode.VALUE
        )
        if should_transmit_by_value:
            data_ = Path(generated_output.location).read_bytes()
            part.set_payload(data_)
            if payload.get_param("Type") is None:
                # set the `Type` of the payload as the same media
                # type of the first output
                payload.set_param(
                    "Type", generated_output.media_type)
        else:
            part.add_header('Content-Location', None)
        payload.attach(part)
    return payload.as_bytes()


def _get_execution_response_document(
        execution_request: Execution,
        execution_result: ExecutionResultInternal
) -> str:
    """Prepare process execution response when the requested type is `document`

    :param execution_request: The parameters that originated the execution
    :param execution_result: Process execution results
    """
    output_results = {}
    for out_id, requested_output in execution_request.outputs.items():
        should_transmit_by_value = (
                requested_output.transmission_mode ==
                ProcessOutputTransmissionMode.VALUE
        )
        generated_output = execution_result.outputs.get(out_id)
        if should_transmit_by_value:
            # if the output's media type is text based we should be
            # able to read the file as json.
            # if the output's media type is not text based we should
            # be able to base64 encode the file contents
            output_data = Path(generated_output.location).read_bytes()
            try:
                parsed_output_data = json.loads(output_data)
                out_result = (
                    ExecutionDocumentSingleOutput(
                        __root__=parsed_output_data)
                )
            except json.JSONDecodeError:
                serialized_output_data = str(
                    urlsafe_b64encode(output_data))
                out_result = (
                    ExecutionDocumentSingleOutput(
                        __root__=serialized_output_data)
                )
        else:
            out_result = ExecutionDocumentSingleOutput(
                __root__=Link(href=None)
            )
        output_results[out_id] = out_result
    result = ExecutionDocumentResult(__root__=output_results)
    return result.json(by_alias=True, exclude_none=True)


def _generate_process_description_links(
        link_rel_getter: Callable,
        process_description_id: str,
        base_url: str,
        locale
) -> List[Link]:
    """Generate links for a process description"""
    process_url = f"{base_url}/processes/{process_description_id}"
    jobs_url = f"{base_url}/jobs"
    return [
        Link(
            type=util.FORMAT_TYPES[util.F_JSON],
            rel=link_rel_getter(util.F_JSON),
            href=f'{process_url}?f={util.F_JSON}',
            title='Process description as JSON',
            hreflang=locale,
        ),
        Link(
            type=util.FORMAT_TYPES[util.F_HTML],
            rel=link_rel_getter(util.F_HTML),
            href=f'{process_url}?f={util.F_HTML}',
            title='Process description as HTML',
            hreflang=locale
        ),
        Link(
            type=util.FORMAT_TYPES[util.F_JSON],
            rel='http://www.opengis.net/def/rel/ogc/1.0/job-list',
            href=f'{jobs_url}?f={util.F_JSON}',
            title='jobs for this process as JSON',
            hreflang=locale
        ),
        Link(
            type=util.FORMAT_TYPES[util.F_HTML],
            rel='http://www.opengis.net/def/rel/ogc/1.0/job-list',
            href=f'{jobs_url}?f={util.F_HTML}',
            title='jobs for this process as HTML',
            hreflang=locale
        ),
        Link(
            type=util.FORMAT_TYPES[util.F_JSON],
            rel='http://www.opengis.net/def/rel/ogc/1.0/execute',
            href=f'{process_url}/execution?f={util.F_JSON}',
            title='Execution for this process as JSON',
            hreflang=locale
        )
    ]


def _prepare_job_for_response(
        job_status: JobStatusInfoInternal,
        base_url: str
) -> JobStatusInfoRead:
    result_related_statuses = (
        JobStatus.successful,
        JobStatus.running,
        JobStatus.accepted
    )
    links = []
    if job_status.status in result_related_statuses:
        result_url = f"{base_url}/jobs/{job_status.job_id}/results"  # noqa
        links.extend(
            [
                Link(
                    type=util.FORMAT_TYPES[util.F_HTML],
                    rel='about',
                    title=f'Job results as HTML',
                    href=f'{result_url}?f={util.F_HTML}',
                ),
                Link(
                    type=util.FORMAT_TYPES[util.F_JSON],
                    rel='about',
                    title=f'Job results as JSON',
                    href=f'{result_url}?f={util.F_JSON}',
                ),
            ]
        )
    return JobStatusInfoRead(
        **job_status.dict(by_alias=True),
        links=links
    )
