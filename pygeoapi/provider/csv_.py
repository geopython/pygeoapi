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

import csv
import itertools
import logging

from pygeoapi.provider.base import BaseProvider

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

    def _load(self, startindex=0, limit=10, resulttype='results',
              identifier=None, bbox=[], time=None, properties=[]):
        """
        Load CSV data

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param properties: list of tuples (name, value)

        :returns: dict of GeoJSON FeatureCollection
        """

        found = False
        result = None
        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        with open(self.data) as ff:
            LOGGER.debug('Serializing DictReader')
            data_ = csv.DictReader(ff)
            if resulttype == 'hits':
                LOGGER('Returning hits only')
                feature_collection['numberMatched'] = len(list(data_))
                return feature_collection
            LOGGER.debug('Slicing CSV rows')
            for row in itertools.islice(data_, startindex, startindex+limit):
                feature = {'type': 'Feature'}
                feature['ID'] = row.pop('id')
                feature['geometry'] = {
                    'type': 'Point',
                    'coordinates': [
                        float(row.pop(self.geometry_x)),
                        float(row.pop(self.geometry_y))
                    ]
                }
                feature['properties'] = row
                if identifier is not None and feature['ID'] == identifier:
                    found = True
                    result = feature
                feature_collection['features'].append(feature)
                feature_collection['numberMatched'] = \
                    len(feature_collection['features'])

        if identifier is not None and not found:
            return None
        elif identifier is not None and found:
            return result

        feature_collection['numberReturned'] = len(
            feature_collection['features'])

        return feature_collection

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], time=None, properties=[]):
        """
        CSV query

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param time: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)

        :returns: dict of GeoJSON FeatureCollection
        """

        return self._load(startindex, limit, resulttype)

    def get(self, identifier):
        """
        query CSV id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """

        return self._load(identifier=identifier)

    def __repr__(self):
        return '<CSVProvider> {}'.format(self.data)
