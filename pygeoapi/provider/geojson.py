# =================================================================
#
# Authors: Matthew Perry <perrygeo@gmail.com>
#
# Copyright (c) 2018 Matthew Perry
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

import os
import json

from pygeoapi.provider.base import BaseProvider


class GeoJSONProvider(BaseProvider):
    """Provider class backed by local GeoJSON files

    This is meant to be simple
    (no external services, no schema)

    at the expense of performance
    (no indexing, full serialization roundtrip on each request)
    """

    def __init__(self, definition):
        """initializer"""

        BaseProvider.__init__(self, definition)

        # url is a file path, TODO use urlparse or support local paths
        self._validate_or_create(self.url)

    @classmethod
    def _validate_or_create(self, path):
        """Validate that the path exists and that
        it is a geojson feature collection
        """
        if os.path.exists(path):
            with open(path) as src:
                data = json.loads(src.read())
                assert data['type'] == 'FeatureCollection'
        else:
            with open(path, 'w') as dst:
                empty = {
                    'type': 'FeatureCollection',
                    'features': []}
                dst.write(json.dumps(empty))

    def _load(self, startindex=0, count=10, resulttype='results'):
        with open(self.url) as src:
            data = json.loads(src.read())

        if resulttype == 'hits':
            data['numberMatched'] = len(data['features'])
            data['features'] = []
        else:
            data['features'] = data['features'][startindex:startindex + count]
        return data

    def query(self, startindex=0, count=10, resulttype='results'):
        """
        query the provider

        :returns: FeatureCollection dict of 0..n GeoJSON features

        TODO yield GeoJSON features?
        """
        return self._load(startindex, count, resulttype)

    def get(self, identifier):
        """
        query the provider by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """
        collection = {
            'type': 'FeatureCollection',
            'features': []}

        all_data = self._load()

        if self.id_field:
            # Use id field
            for feature in all_data['features']:
                if feature[self.id_field] == identifier:
                    collection['features'].append(feature)
        else:
            # Use enumeration, zero-indexed
            for i, feature in enumerate(all_data['features']):
                # TODO assumes identifier is always a string
                if str(i) == identifier:
                    collection['features'].append(feature)

        # assert that one and only one feature returned
        n_features = len(collection['features'])
        if n_features != 1:
            raise RuntimeError('Expected 1 feature, got {}'.format(n_features))

        return collection

    def __repr__(self):
        return '<GeoJSONProvider> {}'.format(self.url)
