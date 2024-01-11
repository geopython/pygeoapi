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
from typing import List, Dict

from pygeoapi.provider.base import BaseProvider

LOGGER = logging.getLogger(__name__)


class BaseEDRProvider(BaseProvider):
    """Base EDR Provider"""

    query_types = []
    radius_within_units: List[str]
    cube_height_units: List[str]
    corridor_height_units: List[str]
    corridor_width_units: List[str]

    output_formats: Dict[str, List[str]] = {}
    crs_details: Dict[str, Dict] = {}

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.base_edr.BaseEDRProvider
        """

        super().__init__(provider_def)

        for query_type in self.get_query_types():
            self.output_formats[query_type] = \
                provider_def.get('data_queries', {}).get(query_type, {}) \
                                                    .get('output_formats')
            self.crs_details[query_type] = \
                provider_def.get('data_queries', {}).get(query_type, {}) \
                                                    .get('crs_details')

        self.cube_height_units = \
            provider_def.get('data_queries', {}).get('cube', {}) \
                        .get('height_units', [""])
        self.radius_within_units = \
            provider_def.get('data_queries', {}).get('radius', {}) \
                        .get('within_units', [""])
        self.corridor_height_units = \
            provider_def.get('data_queries', {}).get('corridor', {}) \
                        .get('height_units', [""])
        self.corridor_width_units = \
            provider_def.get('data_queries', {}).get('corridor', {}) \
                        .get('width_units', [""])

        self.instances = []

    @classmethod
    def register(cls):
        def inner(fn):
            cls.query_types.append(fn.__name__)
            return fn
        return inner

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

    def get_output_formats(self, query_type: str):
        return self.output_formats.get(query_type)

    def get_crs_details(self, query_type: str):
        return self.crs_details.get(query_type)

    def get_cube_height_units(self):
        return self.cube_height_units

    def get_radius_within_units(self):
        return self.radius_within_units

    def get_corridor_width_units(self):
        return self.corridor_width_units

    def get_corridor_height_units(self):
        return self.corridor_height_units

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
        :param within: distance (for radius querires)
        :param within_units: distance units (for radius querires)

        :returns: coverage data as `dict` of CoverageJSON or native format
        """

        try:
            return getattr(self, kwargs.get('query_type'))(**kwargs)
        except AttributeError:
            raise NotImplementedError('Query not implemented!')
