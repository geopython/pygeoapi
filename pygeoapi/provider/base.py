# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2021 Tom Kralidis
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

import logging

LOGGER = logging.getLogger(__name__)


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

        self.options = provider_def.get('options', None)
        self.id_field = provider_def.get('id_field', None)
        self.uri_field = provider_def.get('uri_field', None)
        self.x_field = provider_def.get('x_field', None)
        self.y_field = provider_def.get('y_field', None)
        self.time_field = provider_def.get('time_field')
        self.title_field = provider_def.get('title_field')
        self.properties = provider_def.get('properties', [])
        self.file_types = provider_def.get('file_types', [])
        self.fields = {}

        # for coverage providers
        self.axes = []
        self.crs = None
        self.num_bands = None

    def get_fields(self):
        """
        Get provider field information (names, types)

        :returns: dict of fields
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

    def get(self, identifier):
        """
        query the provider by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """

        raise NotImplementedError()

    def create(self, new_feature):
        """Create a new feature
        """

        raise NotImplementedError()

    def update(self, identifier, new_feature):
        """Updates an existing feature id with new_feature

        :param identifier: feature id
        :param new_feature: new GeoJSON feature dictionary
        """

        raise NotImplementedError()

    def get_coverage_domainset(self):
        """
        Provide coverage domainset

        :returns: CIS JSON object of domainset metadata
        """

        raise NotImplementedError()

    def get_coverage_rangetype(self):
        """
        Provide coverage rangetype

        :returns: CIS JSON object of rangetype metadata
        """

        raise NotImplementedError()

    def delete(self, identifier):
        """Deletes an existing feature

        :param identifier: feature id
        """

        raise NotImplementedError()

    def __repr__(self):
        return '<BaseProvider> {}'.format(self.type)


class ProviderGenericError(Exception):
    """provider generic error"""
    pass


class ProviderConnectionError(ProviderGenericError):
    """provider connection error"""
    pass


class ProviderTypeError(ProviderGenericError):
    """provider type error"""
    pass


class ProviderInvalidQueryError(ProviderGenericError):
    """provider invalid query error"""
    pass


class ProviderQueryError(ProviderGenericError):
    """provider query error"""
    pass


class ProviderItemNotFoundError(ProviderGenericError):
    """provider item not found query error"""
    pass


class ProviderNoDataError(ProviderGenericError):
    """provider no data error"""
    pass


class ProviderNotFoundError(ProviderGenericError):
    """provider not found error"""
    pass


class ProviderVersionError(ProviderGenericError):
    """provider incorrect version error"""
    pass
