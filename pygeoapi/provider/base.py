# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2018 Tom Kralidis
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


class BaseProvider(object):
    """generic Provider ABC"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.providers.base.BaseProvider
        """

        self.name = provider_def['name']
        self.data = provider_def['data']
        self.id_field = provider_def['id_field']
        self.time_field = provider_def.get('time_field')
        self.fields = {}

    def get_fields(self):
        """
        Get provider field information (names, types)

        :returns: dict of fields
        """

        raise NotImplementedError()

    def query(self):
        """
        query the provider

        :returns: dict of 0..n GeoJSON features
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

    def delete(self, identifier):
        """Updates an existing feature id with new_feature

        :param identifier: feature id
        """

        raise NotImplementedError()

    def __repr__(self):
        return '<BaseProvider> {}'.format(self.type)


class ProviderConnectionError(Exception):
    """query / backend error"""
    pass


class ProviderQueryError(Exception):
    """query / backend error"""
    pass


class ProviderVersionError(Exception):
    """Incorrect provider version"""
    pass