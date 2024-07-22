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

from pygeoapi.provider.base import BaseProvider

LOGGER = logging.getLogger(__name__)

WKT = 'GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\",SPHEROID[\"WGS 84\",6378137,298.257223563,AUTHORITY[\"EPSG\",\"7030\"]],AUTHORITY[\"EPSG\",\"6326\"]],PRIMEM[\"Greenwich\",0,AUTHORITY[\"EPSG\",\"8901\"]],UNIT[\"degree\",0.01745329251994328,AUTHORITY[\"EPSG\",\"9122\"]],AUTHORITY[\"EPSG\",\"4326\"]]' # noqa


class BaseEDRProvider(BaseProvider):
    """Base EDR Provider"""

    query_types = {}

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.base_edr.BaseEDRProvider
        """

        super().__init__(provider_def)

        self.instances = []

    @classmethod
    def register(cls, output_formats=['CoverageJSON'],
                 crs='EPSG:4326', wkt=WKT):
        """
        Class method to register a query type with the provider class.

        :param output_formats: List of supported output formats
        :param crs: Coordinate Reference System, default is 'EPSG:4326'
        :param wkt: Well-Known Text representation of the CRS

        :returns: function
        """
        def inner(fn):
            variables = {
                'title': f'{fn.__name__} query',
                'query_type': fn.__name__,
                'output_formats': output_formats,
                'default_output_format': output_formats[0],
                'crs_details': [{
                    'crs': crs,
                    'wkt': wkt
                }]
            }
            cls.query_types[fn.__name__] = variables
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

        :returns: `dict` of EDR query types
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
        :param within: distance (for radius querires)
        :param within_units: distance units (for radius querires)

        :returns: coverage data as `dict` of CoverageJSON or native format
        """

        try:
            return getattr(self, kwargs.get('query_type'))(**kwargs)
        except AttributeError:
            raise NotImplementedError('Query not implemented!')
