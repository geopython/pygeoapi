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

from shapely import wkt
from shapely.geometry import mapping

from pygeoapi.provider.base import BaseProvider


class CSVProvider(BaseProvider):
    """CSV provider"""

    def __init__(self, definition):
        """initializer"""

        BaseProvider.__init__(self, definition)

        with open(self.url) as ff:
            self.data = csv.DictReader(ff)

    def _load(self, startindex=0, count=10, resulttype='results',
              identifier=None):
        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }
        with open(self.url) as ff:
            data = csv.DictReader(ff)
            if resulttype == 'hits':
                feature_collection['numberMatched'] = len(list(data))
                return feature_collection
            for row in itertools.islice(data, startindex, startindex+count):
                feature = {'type': 'Feature'}
                feature['ID'] = row.pop('id')
                feature['geometry'] = mapping(wkt.loads(row.pop('geom')))
                feature['properties'] = row
                if identifier is not None and feature['ID'] == identifier:
                    return feature
                feature_collection['features'].append(feature)

        return feature_collection

    def query(self, startindex=0, count=10, resulttype='results'):
        """
        CSV query

        :returns: dict of 0..n GeoJSON features
        """

        return self._load(startindex, count, resulttype)

    def get(self, identifier):
        """
        query CSV id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """

        return self._load(identifier)

    def __repr__(self):
        return '<CSVProvider> {}'.format(self.url)
