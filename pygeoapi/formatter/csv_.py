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

import csv
import io
import logging

from shapely.geometry import shape as geojson_to_geom

from pygeoapi.formatter.base import BaseFormatter, FormatterSerializationError

LOGGER = logging.getLogger(__name__)


class CSVFormatter(BaseFormatter):
    """CSV formatter"""

    def __init__(self, formatter_def: dict):
        """
        Initialize object

        :param formatter_def: formatter definition

        :returns: `pygeoapi.formatter.csv_.CSVFormatter`
        """

        geom = formatter_def.get('geom', False)

        super().__init__({'name': 'csv', 'geom': geom})
        self.mimetype = 'text/csv; charset=utf-8'
        self.f = 'csv'
        self.extension = 'csv'

    def write(self, options: dict = {}, data: dict = None) -> str:
        """
        Generate data in CSV format

        :param options: CSV formatting options
        :param data: dict of data

        :returns: string representation of format
        """
        type = data.get('type') or ''
        LOGGER.debug(f'Formatting CSV from data type: {type}')

        if 'Feature' in type or 'features' in data:
            return self._write_from_geojson(options, data)

    def _write_from_geojson(
        self, options: dict = {}, data: dict = None, is_point=False
    ) -> str:
        """
        Generate GeoJSON data in CSV format

        :param options: CSV formatting options
        :param data: dict of GeoJSON data
        :param is_point: whether the features are point geometries

        :returns: string representation of format
        """
        try:
            fields = list(data['features'][0]['properties'].keys())
        except IndexError:
            LOGGER.error('no features')
            return str()

        if self.geom:
            LOGGER.debug('Including point geometry')
            if data['features'][0]['geometry']['type'] == 'Point':
                LOGGER.debug('point geometry detected, adding x,y columns')
                fields.extend(['x', 'y'])
                is_point = True
            else:
                LOGGER.debug('not a point geometry, adding wkt column')
                fields.append('wkt')

        LOGGER.debug(f'CSV fields: {fields}')
        output = io.StringIO()
        writer = csv.DictWriter(output, fields)
        writer.writeheader()

        for feature in data['features']:
            self._add_feature(writer, feature, is_point)

        return output.getvalue().encode('utf-8')

    def _add_feature(
        self, writer: csv.DictWriter, feature: dict, is_point: bool
    ) -> None:
        """
        Add feature data to CSV writer

        :param writer: CSV DictWriter
        :param feature: dict of GeoJSON feature
        :param is_point: whether the feature is a point geometry
        """
        fp = feature['properties']
        try:
            if self.geom:
                if is_point:
                    [fp['x'], fp['y']] = feature['geometry']['coordinates']
                else:
                    geom = geojson_to_geom(feature['geometry'])
                    fp['wkt'] = geom.wkt

            LOGGER.debug(f'Writing feature to row: {fp}')
            writer.writerow(fp)
        except ValueError as err:
            LOGGER.error(err)
            raise FormatterSerializationError('Error writing CSV output')

        return output.getvalue().encode('utf-8')

    def __repr__(self):
        return f'<CSVFormatter> {self.name}'
