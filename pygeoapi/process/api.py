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
"""Utilities for dealing with the implementation of OGC API - Processes
specification.
"""
from itertools import product
from http import HTTPStatus
import json
import logging
from typing import (
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
)

from babel import Locale
import pydantic
from werkzeug.datastructures import ImmutableMultiDict

from pygeoapi import l10n
from pygeoapi.models.processes import (
    ExecuteRequest,
    JobList,
    JobStatus,
    JobStatusInfoInternal,
    JobStatusInfoRead,
    ProcessDescription,
    ProcessExecutionMode,
    ProcessList,
    ProcessSummary,
    RequestedProcessExecutionMode,
)
from pygeoapi.models.base import Link
from pygeoapi.process import exceptions
from pygeoapi.process.manager import get_manager
from pygeoapi.process.manager.base import BaseManager
from pygeoapi import util

LOGGER = logging.getLogger(__name__)


class ProcessApi:
    """OGC API - Processes handler.

    This handler sits behind the main pygeoapi API handler and provides
    all job and process related features.

    Note that methods on this class do not catch exceptions, as
    it is expected that the main pygeoapi API handler will catch them and
    generate appropriate responses from them.
    """
    manager: BaseManager
    base_url: str
    default_locale: Locale
    pagination_default_limit: int = 10

    def __init__(
            self, manager: BaseManager, base_url: str, default_locale: Locale):
        self.manager = manager
        self.base_url = base_url
        self.default_locale = default_locale

    @classmethod
    def from_config(cls, config: Dict):
        """
        Return an instance of this class from the main pygeoapi configuration.

        :param config: pygeoapi configuration

        :return: An instance of this class
        """
        locales = l10n.get_locales(config)
        return cls(
            manager=get_manager(config),
            base_url=util.get_base_url(config),
            default_locale=locales[0]
        )

    def get_process(
            self,
            process_id: str,
            locale: Locale,
            link_rel_getter: Callable,
    ):
        processor = self.manager.get_processor(process_id)
        translated_description = l10n.translate_model(
            processor.process_description, locale)
        translated_description.links.extend(
            _generate_process_description_links(
                link_rel_getter,
                translated_description.id,
                self.base_url,
                self.default_locale)
        )
        return translated_description

    def list_processes(
            self,
            request_params: ImmutableMultiDict,
            locale: Locale,
            link_rel_getter: Callable,
    ) -> ProcessList:
        pagination_links = []
        if len(self.manager.processes) > 0:
            relevant, pagination_links = self._filter_processes(
                raw_limit=request_params.get(
                    'limit', self.pagination_default_limit),
                raw_offset=request_params.get('offset')
            )
        else:
            relevant = []
        process_descriptions = []
        for description in relevant:
            translated_description = l10n.translate_model(
                description, locale)
            existing_links = translated_description.links or []
            existing_links.extend(
                _generate_process_description_links(
                    link_rel_getter,
                    description.id,
                    self.base_url,
                    self.default_locale)
            )
            translated_description.links = existing_links
            summary = ProcessSummary(
                **translated_description.dict(
                    by_alias=True, exclude_none=True)
            )
            process_descriptions.append(summary)
        process_url = f"{self.base_url}/processes"
        return ProcessList(
            processes=process_descriptions,
            links=[
                Link(
                    type=util.FORMAT_TYPES[util.F_JSON],
                    rel=link_rel_getter(util.F_JSON),
                    title="This document as JSON",
                    href=f"{process_url}?f={util.F_JSON}"
                ),
                Link(
                    type=util.FORMAT_TYPES[util.F_JSONLD],
                    rel=link_rel_getter(util.F_JSONLD),
                    title="This document as RDF (JSON-LD)",
                    href=f"{process_url}?f={util.F_JSONLD}"
                ),
                Link(
                    type=util.FORMAT_TYPES[util.F_HTML],
                    rel=link_rel_getter(util.F_HTML),
                    title="This document as HTML",
                    href=f"{process_url}?f={util.F_HTML}"
                ),
                *pagination_links
            ]
        )

    def describe_processes(
            self,
            request,
            process=None
    ) -> ProcessList:
        """
        Provide processes metadata.

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
                processor = self.manager.get_processor(process)
                relevant = [processor.process_description]
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
            request_payload: bytes,
            response_headers: Dict[str, Union[str, List[str]]],
    ) -> Tuple[Dict[str, str], HTTPStatus, bytes]:
        """
        Execute process

        :param request_headers: The request's headers
        :param request_payload: Raw request payload
        :param response_headers: Already initialized response headers
        :param process_id: id of process to be executed

        :raise: UnknownProcessError: if the process id is invalid
        :raise MissingJobParameterError: If the input parameters for the job
                                         are missing
        :raise InvalidJobParameterError: If the input parameters for the job
                                          are not as expected
        :raise: JobFailedError: if there is an error processing the job
        :returns: tuple of status code, response payload, HTTP headers
        """

        try:
            payload = json.loads(request_payload)
            execution_request = ExecuteRequest(**payload)
        except json.JSONDecodeError as err:
            raise exceptions.MissingJobParameterError(
                'MissingParameterValue') from err
        except pydantic.ValidationError as err:
            raise exceptions.InvalidJobParameterError(
                "InvalidParameterValue") from err
        else:
            try:
                execution_mode = RequestedProcessExecutionMode(
                    request_headers.get('Prefer'))
            except ValueError:
                execution_mode = None
            job_status_info, additional_headers = self.manager.execute_process(
                process_id, execution_request, execution_mode)
            is_sync = (
                    job_status_info.negotiated_execution_mode ==
                    ProcessExecutionMode.sync_execute
            )
            if is_sync:
                # as per OAproc, requirement 33, if the execution mode is
                # sync and the server creates a job, then the response shall
                # include a `Link` header with rel=monitor, pointing to the
                # created job
                if self.manager.supports_job_creation:
                    response_headers['Link'] = Link(
                        href=f'{self.base_url}/jobs/{job_status_info.job_id}',
                        rel='monitor'
                    ).as_link_header()
            else:
                # as per OAProc, requirement 34, when the execution mode is
                # async, the response shall include a `Location` header, with
                # a link to the newly created job
                response_headers['Location'] = (
                    f'{self.base_url}/jobs/{job_status_info.job_id}')

            (
                payload,
                media_type,
                additional_headers
            ) = self.manager.get_execution_response(job_status_info)
            response_headers = _combine_response_headers(
                response_headers, additional_headers)
            response_headers['Content-Type'] = media_type
            if job_status_info.status in (
                    JobStatus.accepted,
                    JobStatus.running
            ):
                http_status = HTTPStatus.CREATED
            elif job_status_info.status == JobStatus.successful:
                http_status = HTTPStatus.OK
            else:
                # We'll never get here, as processing errors are expected to
                # raise an exception
                raise RuntimeError(
                    f"Unexpected job status: {job_status_info.status!r}")
            return response_headers, http_status, payload

    def list_jobs(
            self,
            request_params: ImmutableMultiDict,
            link_rel_getter: Callable,
    ) -> JobList:
        """
        Get process jobs

        :param request_params: Input parameters
        :param link_rel_getter: A callable that provides appropriate `rel`
                                values for generating response links

        :returns: tuple of headers, status code, content
        """
        response_links = []
        for media_type, name in ((util.F_HTML, "HTML"), (util.F_JSON, "JSON")):
            response_links.append(
                Link(
                    href=f"{self.base_url}/jobs/?f={media_type}",
                    type=util.FORMAT_TYPES[media_type],
                    rel=link_rel_getter(media_type),
                    title=f'Job list as {name}'
                )
            )
        jobs, pagination_links = self._filter_jobs(request_params)
        response_links.extend(pagination_links)
        job_reads = []
        for job in jobs:
            job_reads.append(_prepare_job_for_response(job, self.base_url))
        return JobList(jobs=job_reads, links=response_links)

    def get_job(
            self,
            job_id: str,
            link_rel_getter: Callable,
    ) -> JobStatusInfoRead:
        """
        Get job detail.

        :param request_params: Input parameters
        :param link_rel_getter: A callable that provides appropriate `rel`
                                values for generating response links
        :param job_id: id of job

        :returns: tuple of headers, status code, content
        """
        job_status_info = self.manager.get_job(job_id)
        return _prepare_job_for_response(job_status_info, self.base_url)

    def get_job_result(
            self, job_id: str) -> Tuple[bytes, Optional[str], List[Link]]:
        """
        Get result of job (instance of a process)

        :param request: A request object
        :param job_id: ID of job

        :raise JobNotFoundError: If job_id does not correspond to a known job
        :raise JobNotReadyError: If job is not finished running yet
        :raise JobFailedError: If job has failed
        :returns: A three element tuple with payload, media type and any
                  additional headers to include in the final response
        """

        job = self.manager.get_job(job_id)

        if job.status == JobStatus.successful:
            # result = self.manager.get_execution_response(
            #     job.requested_response_type,
            #     job.requested_outputs,
            #     job.generated_outputs,
            # )
            result = self.manager.get_execution_response(job)
        else:
            if job.status in (JobStatus.running, JobStatus.accepted):
                raise exceptions.JobNotReadyError
            elif job.status == JobStatus.failed:
                raise exceptions.JobFailedError
            else:
                # we should never reach this, as the only other job status
                # is `dismissed`, which has the effect of deleting the job
                raise RuntimeError
        return result

    def delete_job(self, job_id) -> JobStatusInfoRead:
        """Delete a job.

        :param job_id: job identifier

        :raise JobNotFoundError: If job_id does not correspond to a known job
        :returns: status info of the deleted job
        """

        status_info = self.manager.delete_job(job_id)
        response = JobStatusInfoRead(
            **status_info.dict(by_alias=True, exclude_none=True),
            links=[
                Link(
                    href=(
                        f'{self.base_url}/jobs?'
                        f'processID={status_info.process_id}'
                    ),
                    rel='up',
                    type=util.FORMAT_TYPES[util.F_JSON],
                    title='Job list for the current process'
                )
            ]
        )
        return response

    def _filter_processes(
            self,
            raw_limit: Optional[str],
            raw_offset: Optional[str],
    ) -> Tuple[List[ProcessDescription], List[Link]]:
        limit = util.parse_positive_int_parameter(raw_limit)
        offset = util.parse_positive_int_parameter(raw_offset, default_value=0)
        total_filtered, processes = self.manager.get_process_descriptions(
            limit, offset)
        pagination_links = util.get_pagination_links(
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
        pagination_links = util.get_pagination_links(
            len(jobs), limit, offset, total_filtered_jobs,
            base_url=f'{self.base_url}/jobs',
            title_fragment='job list',
            querystring_params=requested_filters
        )
        return jobs, pagination_links


def _generate_process_description_links(
        link_rel_getter: Callable,
        process_description_id: str,
        base_url: str,
        locale: Locale
) -> List[Link]:
    """Generate links for a process description"""
    process_url = f"{base_url}/processes/{process_description_id}"
    jobs_url = f"{base_url}/jobs"
    media_types = (
        (util.F_JSON, 'JSON'),
        (util.F_HTML, 'HTML')
    )
    link_base_hrefs = (
        (
            (process_url, 'Process description as'),
            (jobs_url, 'Jobs for this process as')
        )
    )
    result = [
        Link(
            type=util.FORMAT_TYPES[util.F_JSON],
            rel='http://www.opengis.net/def/rel/ogc/1.0/execute',
            href=f'{process_url}/execution?f={util.F_JSON}',
            title='Execution for this process as JSON',
            hreflang=locale.language
        )
    ]
    for media_type, link_base in product(media_types, link_base_hrefs):
        type_, title_suffix = media_type
        base_url, title_prefix = link_base
        result.append(
            Link(
                type=util.FORMAT_TYPES[type_],
                rel=link_rel_getter(type_),
                href=f'{base_url}?f={type_}',
                title=f'{title_prefix} {title_suffix}',
                hreflang=locale.language
            )
        )
    return result


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
                    title='Job results as HTML',
                    href=f'{result_url}?f={util.F_HTML}',
                ),
                Link(
                    type=util.FORMAT_TYPES[util.F_JSON],
                    rel='about',
                    title='Job results as JSON',
                    href=f'{result_url}?f={util.F_JSON}',
                ),
            ]
        )
    return JobStatusInfoRead(
        **job_status.dict(by_alias=True),
        links=links
    )


def _combine_response_headers(
        response_headers: Dict[str, Union[str, List[str]]],
        additional: List[Tuple[str, str]]
) -> Dict[str, Union[str, List[str]]]:
    for additional_header_name, content in additional:
        existing_header = response_headers.get(additional_header_name)
        if existing_header is None:
            response_headers[additional_header_name] = content
        elif isinstance(existing_header, str):
            response_headers[additional_header_name] = [
                existing_header, content]
        else:  # it is a list already
            response_headers[additional_header_name].append(content)
    return response_headers
