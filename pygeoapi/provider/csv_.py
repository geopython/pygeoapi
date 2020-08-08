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

from collections import OrderedDict
import csv
import itertools
import logging
import os

from pygeoapi.provider.base import (BaseProvider, ProviderQueryError,
                                    ProviderItemNotFoundError)

from pygeoapi.cql_evaluate import (CQLParser, CQLFilterEvaluator)
from pygeoapi.util import get_filter_fields

LOGGER = logging.getLogger(__name__)


class CSVProvider(BaseProvider):
    """CSV provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.providers.csv_.CSVProvider
        """

        BaseProvider.__init__(self, provider_def)
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
            for f in data_.fieldnames:
                fields[f] = 'string'
            return fields

    def _load(self, identifier=None):
        """
        Load CSV data

        :param identifier: feature id
        """

        if os.path.exists(self.data):
            with open(self.data) as ff:
                LOGGER.debug('Serializing DictReader')
                data_ = csv.DictReader(ff)
                dataset = list(data_)
        else:
            dataset = None

        return dataset

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime=None, properties=[], sortby=[],
              cql_expression=None, identifier=None,):
        """
        CSV query

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param cql_expression: string of cql filter expression
        :param identifier: feature id

        :returns: dict of GeoJSON FeatureCollection
        """

        dataset = self._load(identifier=identifier)

        found = False
        result = None
        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        count = len(dataset)

        if resulttype == 'hits' and not cql_expression:
            LOGGER.debug('Returning hits only')
            feature_collection['numberMatched'] = count
            return feature_collection

        LOGGER.debug('Slicing CSV rows')
        for row in itertools.islice(dataset, 0, count):
            feature = {'type': 'Feature'}
            feature['id'] = row.pop(self.id_field)
            feature['geometry'] = {
                'type': 'Point',
                'coordinates': [
                    float(row.pop(self.geometry_x)),
                    float(row.pop(self.geometry_y))
                ]
            }
            if self.properties:
                feature['properties'] = OrderedDict()
                for p in self.properties:
                    try:
                        feature['properties'][p] = row[p]
                    except KeyError as err:
                        LOGGER.error(err)
                        raise ProviderQueryError()
            else:
                feature['properties'] = row

            if identifier is not None and feature['id'] == identifier:
                found = True
                result = feature
            feature_collection['features'].append(feature)
            feature_collection['numberMatched'] = \
                len(feature_collection['features'])

        if cql_expression:
            cql_ast = CQLParser(cql_expression).create_ast()
            feature_set = feature_collection['features']
            fields_name = get_filter_fields(feature_set)
            feature_set = CQLFilterEvaluator(list(fields_name),
                                             feature_set).to_filter(cql_ast)

            feature_collection['features'] = feature_set

            feature_collection['numberMatched'] = len(feature_collection
                                                      ['features'])

            if resulttype == 'hits':
                feature_collection['features'] = []
                return feature_collection

        feature_collection['features'] = \
            feature_collection['features'][startindex:startindex + limit]

        if identifier is not None and not found:
            return None
        elif identifier is not None and found:
            return result

        feature_collection['numberReturned'] = len(
            feature_collection['features'])

        return feature_collection

    def get(self, identifier):
        """
        query CSV id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """

        item = self.query(identifier=identifier)
        if item:
            return item
        else:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

    def __repr__(self):
        return '<CSVProvider> {}'.format(self.data)
