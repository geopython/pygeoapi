# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Benjamin Webb <benjamin.miller.webb@gmail.com>
#
# Copyright (c) 2023 Tom Kralidis
# Copyright (c) 2023 Benjamin Webb
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
import os
import json
from jsonpatch import make_patch
from jsonschema.exceptions import ValidationError
import logging
from typing import Any, Tuple, Union

from pygeoapi.api import API, APIRequest, F_HTML, pre_process

from pygeoapi.config import get_config, validate_config
from pygeoapi.openapi import get_oas
# from pygeoapi.openapi import validate_openapi_document
from pygeoapi.util import to_json, render_j2_template, yaml_dump


LOGGER = logging.getLogger(__name__)


class Admin(API):
    """Admin object"""

    PYGEOAPI_CONFIG = os.environ.get('PYGEOAPI_CONFIG')
    PYGEOAPI_OPENAPI = os.environ.get('PYGEOAPI_OPENAPI')

    def __init__(self, config, openapi):
        """
        constructor

        :param config: configuration dict
        :param openapi: openapi dict

        :returns: `pygeoapi.Admin` instance
        """

        super().__init__(config, openapi)

    def merge(self, obj1, obj2):
        """
        Merge two dictionaries

        :param obj1: `dict` of first object
        :param obj2: `dict` of second object

        :returns: `dict` of merged objects
        """

        if isinstance(obj1, dict) and isinstance(obj2, dict):
            merged = obj1.copy()
            for key, value in obj2.items():
                if key in merged:
                    merged[key] = self.merge(merged[key], value)
                else:
                    merged[key] = value
            return merged
        elif isinstance(obj1, list) and isinstance(obj2, list):
            return [self.merge(i1, i2) for i1, i2 in zip(obj1, obj2)]
        else:
            return obj2

    def validate(self, config):
        """
        Validate pygeoapi configuration and OpenAPI to file

        :param config: configuration dict
        """

        # validate pygeoapi configuration
        LOGGER.debug('Validating configuration')
        validate_config(config)
        # validate OpenAPI document
        # LOGGER.debug('Validating openapi document')
        # oas = get_oas(config)
        # validate_openapi_document(oas)
        return True

    def write(self, config):
        """
        Write pygeoapi configuration and OpenAPI to file

        :param config: configuration dict
        """

        self.write_config(config)
        self.write_oas(config)

    def write_config(self, config):
        """
        Write pygeoapi configuration file

        :param config: configuration dict
        """

        # validate pygeoapi configuration
        config = deepcopy(config)
        validate_config(config)

        # Preserve env variables
        LOGGER.debug('Reading env variables in configuration')
        raw_conf = json.loads(to_json(get_config(raw=True)))
        conf = json.loads(to_json(get_config()))
        patch = make_patch(conf, raw_conf)

        LOGGER.debug('Merging env variables')
        config = patch.apply(config)

        # write pygeoapi configuration
        LOGGER.debug('Writing pygeoapi configuration')
        yaml_dump(config, self.PYGEOAPI_CONFIG)
        LOGGER.debug('Finished writing pygeoapi configuration')

    def write_oas(self, config):
        """
        Write pygeoapi OpenAPI document

        :param config: configuration dict
        """

        # validate OpenAPI document
        config = deepcopy(config)
        oas = get_oas(config)
        # validate_openapi_document(oas)

        # write OpenAPI document
        LOGGER.debug('Writing OpenAPI document')
        yaml_dump(oas, self.PYGEOAPI_OPENAPI)
        LOGGER.debug('Finished writing OpenAPI document')

    @pre_process
    def get_config(
        self,
        request: Union[APIRequest, Any]
    ) -> Tuple[dict, int, str]:
        """
        Provide admin configuration document

        :param request: request object

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        headers = request.get_response_headers()

        cfg = get_config(raw=True)

        if request.format == F_HTML:
            content = render_j2_template(
                self.config, 'admin/index.html', cfg, request.locale
            )
        else:
            content = to_json(cfg, self.pretty_print)

        return headers, 200, content

    @pre_process
    def put_config(
        self,
        request: Union[APIRequest, Any]
    ) -> Tuple[dict, int, str]:
        """
        Update complete pygeoapi configuration

        :param request: request object

        :returns: tuple of headers, status code, content
        """

        LOGGER.debug('Updating configuration')

        if not request.is_valid():
            return self.get_format_exception(request)

        headers = request.get_response_headers()

        data = request.data
        if not data:
            msg = 'missing request data'
            return self.get_exception(
                400, headers, request.format, 'MissingParameterValue', msg
            )

        try:
            # Parse data
            data = data.decode()
        except (UnicodeDecodeError, AttributeError):
            pass

        try:
            data = json.loads(data)
        except (json.decoder.JSONDecodeError, TypeError) as err:
            # Input is not valid JSON
            LOGGER.error(err)
            msg = 'invalid request data'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg
            )

        LOGGER.debug('Updating configuration')
        try:
            self.validate(data)
        except ValidationError as err:
            LOGGER.error(err)
            msg = 'Schema validation error'
            return self.get_exception(
                400, headers, request.format, 'ValidationError', msg
            )

        self.write(data)

        return headers, 204, {}

    @pre_process
    def patch_config(
        self, request: Union[APIRequest, Any]
    ) -> Tuple[dict, int, str]:
        """
        Update partial pygeoapi configuration

        :param request: request object
        :param resource_id: resource identifier

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        config = deepcopy(self.config)
        headers = request.get_response_headers()

        data = request.data
        if not data:
            msg = 'missing request data'
            return self.get_exception(
                400, headers, request.format, 'MissingParameterValue', msg
            )

        try:
            # Parse data
            data = data.decode()
        except (UnicodeDecodeError, AttributeError):
            pass

        try:
            data = json.loads(data)
        except (json.decoder.JSONDecodeError, TypeError) as err:
            # Input is not valid JSON
            LOGGER.error(err)
            msg = 'invalid request data'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg
            )

        LOGGER.debug('Merging configuration')
        config = self.merge(config, data)

        try:
            self.validate(config)
        except ValidationError as err:
            LOGGER.error(err)
            msg = 'Schema validation error'
            return self.get_exception(
                400, headers, request.format, 'ValidationError', msg
            )

        self.write(config)

        content = to_json(config, self.pretty_print)

        return headers, 204, content

    @pre_process
    def get_resources(
        self, request: Union[APIRequest, Any]
    ) -> Tuple[dict, int, str]:
        """
        Provide admin document

        :param request: request object

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        headers = request.get_response_headers()

        cfg = get_config(raw=True)

        if request.format == F_HTML:
            content = render_j2_template(
                self.config,
                'admin/index.html',
                cfg['resources'],
                request.locale,
            )
        else:
            content = to_json(cfg['resources'], self.pretty_print)

        return headers, 200, content

    @pre_process
    def post_resource(
        self, request: Union[APIRequest, Any]
    ) -> Tuple[dict, int, str]:
        """
        Add resource configuration

        :param request: request object

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        config = deepcopy(self.config)
        headers = request.get_response_headers()

        data = request.data
        if not data:
            msg = 'missing request data'
            return self.get_exception(
                400, headers, request.format, 'MissingParameterValue', msg
            )

        try:
            # Parse data
            data = data.decode()
        except (UnicodeDecodeError, AttributeError):
            pass

        try:
            data = json.loads(data)
        except (json.decoder.JSONDecodeError, TypeError) as err:
            # Input is not valid JSON
            LOGGER.error(err)
            msg = 'invalid request data'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg
            )

        resource_id = next(iter(data.keys()))

        if config['resources'].get(resource_id) is not None:
            # Resource already exists
            msg = f'Resource exists: {resource_id}'
            LOGGER.error(msg)
            return self.get_exception(
                400, headers, request.format, 'NoApplicableCode', msg
            )

        LOGGER.debug(f'Adding resource: {resource_id}')
        config['resources'].update(data)

        try:
            self.validate(config)
        except ValidationError as err:
            LOGGER.error(err)
            msg = 'Schema validation error'
            return self.get_exception(
                400, headers, request.format, 'ValidationError', msg
            )

        self.write(config)

        content = f'Location: /{request.path_info}/{resource_id}'
        LOGGER.debug(f'Success at {content}')

        return headers, 201, content

    @pre_process
    def get_resource(
        self, request: Union[APIRequest, Any], resource_id: str
    ) -> Tuple[dict, int, str]:
        """
        Get resource configuration

        :param request: request object
        :param resource_id:

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        headers = request.get_response_headers()

        cfg = get_config(raw=True)

        try:
            resource = cfg['resources'][resource_id]
        except KeyError:
            msg = f'Resource not found: {resource_id}'
            return self.get_exception(
                400, headers, request.format, 'ResourceNotFound', msg
            )

        if request.format == F_HTML:
            content = render_j2_template(
                self.config, 'admin/index.html', resource, request.locale
            )
        else:
            content = to_json(resource, self.pretty_print)

        return headers, 200, content

    @pre_process
    def delete_resource(
        self, request: Union[APIRequest, Any], resource_id: str
    ) -> Tuple[dict, int, str]:
        """
        Delete resource configuration

        :param request: request object
        :param resource_id: resource identifier

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        config = deepcopy(self.config)
        headers = request.get_response_headers()

        try:
            LOGGER.debug(f'Removing resource configuration for: {resource_id}')
            config['resources'].pop(resource_id)
        except KeyError:
            msg = f'Resource not found: {resource_id}'
            return self.get_exception(
                400, headers, request.format, 'ResourceNotFound', msg
            )

        LOGGER.debug('Resource removed, validating and saving configuration')
        try:
            self.validate(config)
        except ValidationError as err:
            LOGGER.error(err)
            msg = 'Schema validation error'
            return self.get_exception(
                400, headers, request.format, 'ValidationError', msg
            )

        self.write(config)

        return headers, 204, {}

    @pre_process
    def put_resource(
        self,
        request: Union[APIRequest, Any],
        resource_id: str,
    ) -> Tuple[dict, int, str]:
        """
        Update complete resource configuration

        :param request: request object
        :param resource_id: resource identifier

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        config = deepcopy(self.config)
        headers = request.get_response_headers()

        try:
            LOGGER.debug('Verifying resource exists')
            config['resources'][resource_id]
        except KeyError:
            msg = f'Resource not found: {resource_id}'
            return self.get_exception(
                400, headers, request.format, 'ResourceNotFound', msg
            )

        data = request.data
        if not data:
            msg = 'missing request data'
            return self.get_exception(
                400, headers, request.format, 'MissingParameterValue', msg
            )

        try:
            # Parse data
            data = data.decode()
        except (UnicodeDecodeError, AttributeError):
            pass

        try:
            data = json.loads(data)
        except (json.decoder.JSONDecodeError, TypeError) as err:
            # Input is not valid JSON
            LOGGER.error(err)
            msg = 'invalid request data'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg
            )

        LOGGER.debug(f'Updating resource: {resource_id}')
        config['resources'].update({resource_id: data})
        try:
            self.validate(config)
        except ValidationError as err:
            LOGGER.error(err)
            msg = 'Schema validation error'
            return self.get_exception(
                400, headers, request.format, 'ValidationError', msg
            )

        self.write(config)

        return headers, 204, {}

    @pre_process
    def patch_resource(
        self, request: Union[APIRequest, Any], resource_id: str
    ) -> Tuple[dict, int, str]:
        """
        Update partial resource configuration

        :param request: request object
        :param resource_id: resource identifier

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)

        config = deepcopy(self.config)
        headers = request.get_response_headers()

        try:
            LOGGER.debug('Verifying resource exists')
            resource = config['resources'][resource_id]
        except KeyError:
            msg = f'Resource not found: {resource_id}'
            return self.get_exception(
                400, headers, request.format, 'ResourceNotFound', msg
            )

        data = request.data
        if not data:
            msg = 'missing request data'
            return self.get_exception(
                400, headers, request.format, 'MissingParameterValue', msg
            )

        try:
            # Parse data
            data = data.decode()
        except (UnicodeDecodeError, AttributeError):
            pass

        try:
            data = json.loads(data)
        except (json.decoder.JSONDecodeError, TypeError) as err:
            # Input is not valid JSON
            LOGGER.error(err)
            msg = 'invalid request data'
            return self.get_exception(
                400, headers, request.format, 'InvalidParameterValue', msg
            )

        LOGGER.debug('Merging resource block')
        data = self.merge(resource, data)
        LOGGER.debug('Updating resource')
        config['resources'].update({resource_id: data})

        try:
            self.validate(config)
        except ValidationError as err:
            LOGGER.error(err)
            msg = 'Schema validation error'
            return self.get_exception(
                400, headers, request.format, 'ValidationError', msg
            )

        self.write(config)

        content = to_json(resource, self.pretty_print)

        return headers, 204, content
