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

from pygeoapi.provider.base import (BaseProvider, ProviderInvalidDataError,
                                    ProviderQueryError)

LOGGER = logging.getLogger(__name__)

EDR_QUERY_TYPES = ['position', 'radius', 'area', 'cube',
                   'trajectory', 'corridor', 'items',
                   'locations', 'instances']


class BaseEDRProvider(BaseProvider):
    """Base EDR Provider"""

    query_types = []

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.base_edr.BaseEDRProvider
        """

        BaseProvider.__init__(self, provider_def)

#        self.instances = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        cls.query_types = [
            name for name, function in cls.__dict__.items()
            if name in EDR_QUERY_TYPES and callable(function)
        ]

        if not cls.query_types:
            msg = f"{cls.__name__} does not implement any query types"
            LOGGER.error(msg)
            raise ProviderInvalidDataError(msg)

        LOGGER.debug(
            f'{cls.__name__} registered query types: {cls.query_types}'
        )

        if 'items' in cls.query_types:
            LOGGER.warning(
                f'items query is registered in {cls.__name__}, '
                'but requests will be routed to a feature provider'
            )

    def get_instance(self, instance):
        """
        Validate instance identifier

        :returns: `bool` of whether instance is valid
        """

        return NotImplementedError()

    def get_query_types(self):
        """
        Provide supported query types

        :returns: `list` of EDR query types
        """

        return self.query_types

    def query(self, **kwargs):
        """
        Extract data from collection collection

        :param query_type: query type
        :param wkt: `shapely.geometry` WKT geometry
        :param datetime_: temporal (datestamp or extent)
        :param select_properties: list of parameters
        :param z: vertical level(s)
        :param format_: data format of output
        :param bbox: bbox geometry (for cube queries)
        :param within: distance (for radius queries)
        :param within_units: distance units (for radius queries)
        :param instance: instance name (for instances queries)
        :param limit: number of records to return (for locations queries)
        :param location_id: location identifier (for locations queries)

        :returns: coverage data as `dict` of CoverageJSON or native format
        """
        query_type = kwargs.get('query_type')
        if query_type is None:
            raise ProviderQueryError('Query type is required')
        try:
            query_function = getattr(self, query_type)
        except AttributeError:
            raise ProviderQueryError('Query type not implemented')

        return query_function(**kwargs)
