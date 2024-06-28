# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
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
import logging
from enum import Enum
from http import HTTPStatus

from pygeoapi.error import GenericError

LOGGER = logging.getLogger(__name__)


class SchemaType(Enum):
    item = 'item'
    create = 'create'
    update = 'update'
    replace = 'replace'


class BaseProvider:
    """generic Provider ABC"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.base.BaseProvider
        """

        try:
            self.name = provider_def['name']
            self.type = provider_def['type']
            self.data = provider_def['data']
        except KeyError:
            raise RuntimeError('name/type/data are required')

        self.editable = provider_def.get('editable', False)
        self.options = provider_def.get('options')
        self.id_field = provider_def.get('id_field')
        self.uri_field = provider_def.get('uri_field')
        self.x_field = provider_def.get('x_field')
        self.y_field = provider_def.get('y_field')
        self.time_field = provider_def.get('time_field')
        self.title_field = provider_def.get('title_field')
        self.properties = provider_def.get('properties', [])
        self.file_types = provider_def.get('file_types', [])
        self.fields = {}
        self.filename = None

        # for coverage providers
        self.axes = []
        self.crs = None
        self.num_bands = None

    def get_fields(self):
        """
        Get provider field information (names, types)

        Example response: {'field1': 'string', 'field2': 'number'}}

        :returns: dict of field names and their associated JSON Schema types
        """

        raise NotImplementedError()

    def get_schema(self, schema_type: SchemaType = SchemaType.item):
        """
        Get provider schema model

        :param schema_type: `SchemaType` of schema (default is 'item')

        :returns: tuple pair of `str` of media type and `dict` of schema
                  (i.e. JSON Schema)
        """

        raise NotImplementedError()

    def get_data_path(self, baseurl, urlpath, dirpath):
        """
        Gets directory listing or file description or raw file dump

        :param baseurl: base URL of endpoint
        :param urlpath: base path of URL
        :param dirpath: directory basepath (equivalent of URL)

        :returns: `dict` of file listing or `dict` of GeoJSON item or raw file
        """

        raise NotImplementedError()

    def get_metadata(self):
        """
        Provide data/file metadata

        :returns: `dict` of metadata construct (format
                  determined by provider/standard)
        """

        raise NotImplementedError()

    def query(self):
        """
        query the provider

        :returns: dict of 0..n GeoJSON features or coverage data
        """

        raise NotImplementedError()

    def get(self, identifier, **kwargs):
        """
        query the provider by id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """

        raise NotImplementedError()

    def create(self, item):
        """
        Create a new item

        :param item: `dict` of new item

        :returns: identifier of created item
        """

        raise NotImplementedError()

    def update(self, identifier, item):
        """
        Updates an existing item

        :param identifier: feature id
        :param item: `dict` of partial or full item

        :returns: `bool` of update result
        """

        raise NotImplementedError()

    def delete(self, identifier):
        """
        Deletes an existing item

        :param identifier: item id

        :returns: `bool` of deletion result
        """

        raise NotImplementedError()

    def _load_and_prepare_item(self, item, identifier=None,
                               accept_missing_identifier=False,
                               raise_if_exists=True):
        """
        Helper function to load a record, detect its idenfier and prepare
        a record item

        :param item: `str` of incoming item data
        :param identifier: `str` of item identifier (optional)
        :param accept_missing_identifier: `bool` of whether a missing
                                          identifier in item is valid
                                          (typically for a create() method)
        :param raise_if_exists: `bool` of whether to check if record
                                 already exists

        :returns: `tuple` of item identifier and item data/payload
        """

        identifier2 = None
        msg = None

        LOGGER.debug('Loading data')
        LOGGER.debug(f'Data: {item}')
        try:
            json_data = json.loads(item)
        except TypeError as err:
            LOGGER.error(err)
            msg = 'Invalid data'
        except json.decoder.JSONDecodeError as err:
            LOGGER.error(err)
            msg = 'Invalid JSON data'

        if msg is not None:
            raise ProviderInvalidDataError(msg)

        LOGGER.debug('Detecting identifier')
        if identifier is not None:
            identifier2 = identifier
        else:
            try:
                identifier2 = json_data['id']
            except KeyError:
                LOGGER.debug('Cannot find id; trying properties.identifier')
                try:
                    identifier2 = json_data['properties']['identifier']
                except KeyError:
                    LOGGER.debug('Cannot find properties.identifier')

        if identifier2 is None and not accept_missing_identifier:
            msg = 'Missing identifier (id or properties.identifier)'
            LOGGER.error(msg)
            raise ProviderInvalidDataError(msg)

        if 'geometry' not in json_data or 'properties' not in json_data:
            msg = 'Missing core GeoJSON geometry or properties'
            LOGGER.error(msg)
            raise ProviderInvalidDataError(msg)

        if identifier2 is not None and raise_if_exists:
            LOGGER.debug('Querying database whether item exists')
            try:
                _ = self.get(identifier2)

                msg = 'record already exists'
                LOGGER.error(msg)
                raise ProviderInvalidDataError(msg)
            except ProviderItemNotFoundError:
                LOGGER.debug('record does not exist')

        return identifier2, json_data

    def __repr__(self):
        return f'<BaseProvider> {self.type}'


class ProviderGenericError(GenericError):
    """provider generic error"""
    default_msg = 'generic error (check logs)'


class ProviderConnectionError(ProviderGenericError):
    """provider connection error"""
    default_msg = 'connection error (check logs)'


class ProviderTypeError(ProviderGenericError):
    """provider type error"""
    default_msg = 'invalid provider type'
    http_status_code = HTTPStatus.BAD_REQUEST


class ProviderInvalidQueryError(ProviderGenericError):
    """provider invalid query error"""
    ogc_exception_code = 'InvalidQuery'
    http_status_code = HTTPStatus.BAD_REQUEST
    default_msg = "query error"


class ProviderQueryError(ProviderGenericError):
    """provider query error"""
    default_msg = 'query error (check logs)'


class ProviderItemNotFoundError(ProviderGenericError):
    """provider item not found query error"""
    ogc_exception_code = 'NotFound'
    http_status_code = HTTPStatus.NOT_FOUND
    default_msg = 'identifier not found'


class ProviderNoDataError(ProviderGenericError):
    """provider no data error"""
    ogc_exception_code = 'InvalidParameterValue'
    http_status_code = HTTPStatus.NO_CONTENT
    default_msg = 'No data found'


class ProviderNotFoundError(ProviderGenericError):
    """provider not found error"""
    pass


class ProviderVersionError(ProviderGenericError):
    """provider incorrect version error"""
    pass


class ProviderInvalidDataError(ProviderGenericError):
    """provider invalid data error"""
    pass


class ProviderRequestEntityTooLargeError(ProviderGenericError):
    """provider request entity too large error"""
    http_status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    def __init__(self, msg=None, *args, user_msg=None) -> None:
        if msg and not user_msg:
            # This error type shows the error by default
            user_msg = msg
        super().__init__(msg, *args, user_msg=user_msg)
