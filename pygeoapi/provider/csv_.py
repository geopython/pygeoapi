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

from collections import OrderedDict
import csv
import itertools
import logging

from pygeoapi.provider.base import (BaseProvider, ProviderQueryError,
                                    ProviderItemNotFoundError)
from pygeoapi.util import get_typed_value, crs_transform

LOGGER = logging.getLogger(__name__)


class CSVProvider(BaseProvider):
    """CSV provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.csv_.CSVProvider
        """

        super().__init__(provider_def)
        self.geometry_x = provider_def['geometry']['x_field']
        self.geometry_y = provider_def['geometry']['y_field']
        self.fields = self.get_fields()

    def get_fields(self):
        """
         Get provider field information (names, types)

        :returns: dict of fields
        """

        LOGGER.debug('Treating all columns as string types')
        with open(self.data) as ff:
            LOGGER.debug('Serializing DictReader')
            data_ = csv.DictReader(ff)
            fields = {}

            row = next(data_)

            for key, value in row.items():
                LOGGER.debug(f'key: {key}, value: {value}')
                value2 = get_typed_value(value)
                if key in [self.geometry_x, self.geometry_y]:
                    continue
                if key == self.id_field:
                    type_ = 'string'
                elif isinstance(value2, float):
                    type_ = 'number'
                elif isinstance(value2, int):
                    type_ = 'integer'
                else:
                    type_ = 'string'

                fields[key] = {'type': type_}

            return fields

    def _load(self, offset=0, limit=10, resulttype='results',
              identifier=None, bbox=[], datetime_=None, properties=[],
              select_properties=[], skip_geometry=False, q=None):
        """
        Load CSV data

        :param offset: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param datetime_: temporal (datestamp or extent)
        :param resulttype: return results or hit limit (default results)
        :param properties: list of tuples (name, value)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param q: full-text search term(s)

        :returns: dict of GeoJSON FeatureCollection
        """

        found = False
        result = None
        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }
        if identifier is not None:
            # Loop through all rows when searching for a single feature
            limit = self._load(resulttype='hits').get('numberMatched')

        with open(self.data) as ff:
            LOGGER.debug('Serializing DictReader')
            data_ = csv.DictReader(ff)
            if properties:
                data_ = filter(
                    lambda p: all(
                        [p[prop[0]] == prop[1] for prop in properties]), data_)

            if resulttype == 'hits':
                LOGGER.debug('Returning hits only')
                feature_collection['numberMatched'] = len(list(data_))
                return feature_collection
            LOGGER.debug('Slicing CSV rows')
            for row in itertools.islice(data_, 0, None):
                try:
                    coordinates = [
                        float(row.pop(self.geometry_x)),
                        float(row.pop(self.geometry_y)),
                    ]
                except ValueError:
                    msg = f'Skipping row with invalid geometry: {row.get(self.id_field)}'  # noqa
                    LOGGER.error(msg)
                    continue
                feature = {'type': 'Feature'}
                feature['id'] = row.pop(self.id_field)
                if not skip_geometry:
                    feature['geometry'] = {
                        'type': 'Point',
                        'coordinates': coordinates
                    }
                else:
                    feature['geometry'] = None

                feature['properties'] = OrderedDict()

                if self.properties or select_properties:
                    for p in set(self.properties) | set(select_properties):
                        try:
                            feature['properties'][p] = get_typed_value(row[p])
                        except KeyError as err:
                            LOGGER.error(err)
                            raise ProviderQueryError()
                else:
                    for key, value in row.items():
                        LOGGER.debug(f'key: {key}, value: {value}')
                        feature['properties'][key] = get_typed_value(value)

                if identifier is not None and feature['id'] == identifier:
                    found = True
                    result = feature

                feature_collection['features'].append(feature)

                feature_collection['numberMatched'] = \
                    len(feature_collection['features'])

        if identifier is not None and not found:
            return None
        elif identifier is not None and found:
            return result

        features_returned = feature_collection['features'][offset:offset+limit]
        feature_collection['features'] = features_returned

        feature_collection['numberReturned'] = len(
            feature_collection['features'])

        return feature_collection

    @crs_transform
    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, **kwargs):
        """
        CSV query

        :param offset: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param q: full-text search term(s)

        :returns: dict of GeoJSON FeatureCollection
        """

        return self._load(offset, limit, resulttype,
                          properties=properties,
                          select_properties=select_properties,
                          skip_geometry=skip_geometry)

    @crs_transform
    def get(self, identifier, **kwargs):
        """
        query CSV id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """
        item = self._load(identifier=identifier)
        if item:
            return item
        else:
            err = f'item {identifier} not found'
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

    def __repr__(self):
        return f'<CSVProvider> {self.data}'
