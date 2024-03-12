# =================================================================

# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Sander Schaminee <sander.schaminee@geocat.net>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#          Bernhard Mallinger <bernhard.mallinger@eox.at>
#
# Copyright (c) 2023 Tom Kralidis
# Copyright (c) 2022 Francesco Bartoli
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
# Copyright (c) 2023 Ricardo Garcia Silva
# Copyright (c) 2024 Bernhard Mallinger
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
import logging
from http import HTTPStatus
import json
from typing import Tuple

from pygeoapi import l10n
from pygeoapi.util import (
    json_serial, render_j2_template, JobStatus, RequestedProcessExecutionMode,
    to_json, DATETIME_FORMAT)

from . import (
    APIRequest, API, SYSTEM_LOCALE, F_JSON, FORMAT_TYPES, F_HTML, F_JSONLD,
)


LOGGER = logging.getLogger(__name__)


@gzip
@pre_process
def get_collection_edr_query(
        self, request: Union[APIRequest, Any],
        dataset, instance, query_type,
        location_id=None) -> Tuple[dict, int, str]:
    """
    Queries collection EDR

    :param request: APIRequest instance with query params
    :param dataset: dataset name
    :param instance: instance name
    :param query_type: EDR query type
    :param location_id: location id of a /location/<location_id> query

    :returns: tuple of headers, status code, content
    """

    if not request.is_valid(PLUGINS['formatter'].keys()):
        return self.get_format_exception(request)
    headers = request.get_response_headers(self.default_locale,
                                           **self.api_headers)
    collections = filter_dict_by_key_value(self.config['resources'],
                                           'type', 'collection')

    if dataset not in collections.keys():
        msg = 'Collection not found'
        return self.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', msg)

    LOGGER.debug('Processing query parameters')

    LOGGER.debug('Processing datetime parameter')
    datetime_ = request.params.get('datetime')
    try:
        datetime_ = validate_datetime(collections[dataset]['extents'],
                                      datetime_)
    except ValueError as err:
        msg = str(err)
        return self.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    LOGGER.debug('Processing parameter_names parameter')
    parameternames = request.params.get('parameter_names') or []
    if isinstance(parameternames, str):
        parameternames = parameternames.split(',')

    bbox = None
    if query_type in ['cube', 'locations']:
        LOGGER.debug('Processing cube bbox')
        try:
            bbox = validate_bbox(request.params.get('bbox'))
            if not bbox and query_type == 'cube':
                raise ValueError('bbox parameter required by cube queries')
        except ValueError as err:
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', str(err))

    LOGGER.debug('Processing coords parameter')
    wkt = request.params.get('coords')

    if wkt:
        try:
            wkt = shapely_loads(wkt)
        except WKTReadingError:
            msg = 'invalid coords parameter'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format,
                'InvalidParameterValue', msg)
    elif query_type not in ['cube', 'locations']:
        msg = 'missing coords parameter'
        return self.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    within = within_units = None
    if query_type == 'radius':
        LOGGER.debug('Processing within / within-units parameters')
        within = request.params.get('within')
        within_units = request.params.get('within-units')

    LOGGER.debug('Processing z parameter')
    z = request.params.get('z')

    LOGGER.debug('Loading provider')
    try:
        p = load_plugin('provider', get_provider_by_type(
            collections[dataset]['providers'], 'edr'))
    except ProviderGenericError as err:
        LOGGER.error(err)
        return self.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    if instance is not None and not p.get_instance(instance):
        msg = 'Invalid instance identifier'
        return self.get_exception(
            HTTPStatus.BAD_REQUEST, headers,
            request.format, 'InvalidParameterValue', msg)

    if query_type not in p.get_query_types():
        msg = 'Unsupported query type'
        return self.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    if parameternames and not any((fld in parameternames)
                                  for fld in p.get_fields().keys()):
        msg = 'Invalid parameter_names'
        return self.get_exception(
            HTTPStatus.BAD_REQUEST, headers, request.format,
            'InvalidParameterValue', msg)

    query_args = dict(
        query_type=query_type,
        instance=instance,
        format_=request.format,
        datetime_=datetime_,
        select_properties=parameternames,
        wkt=wkt,
        z=z,
        bbox=bbox,
        within=within,
        within_units=within_units,
        limit=int(self.config['server']['limit']),
        location_id=location_id,
    )

    try:
        data = p.query(**query_args)
    except ProviderGenericError as err:
        LOGGER.error(err)
        return self.get_exception(
            err.http_status_code, headers, request.format,
            err.ogc_exception_code, err.message)

    if request.format == F_HTML:  # render
        content = render_j2_template(self.tpl_config,
                                     'collections/edr/query.html', data,
                                     self.default_locale)
    else:
        content = to_json(data, self.pretty_print)

    return headers, HTTPStatus.OK, content

