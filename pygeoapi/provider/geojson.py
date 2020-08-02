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

import json
import logging
import os
import uuid

from pygeoapi.provider.base import BaseProvider, ProviderItemNotFoundError
from pygeoapi.cql_evaluate import (CQLParser, CQLFilterEvaluator)
from pygeoapi.util import get_filter_fields


LOGGER = logging.getLogger(__name__)


class GeoJSONProvider(BaseProvider):
    """Provider class backed by local GeoJSON files

    This is meant to be simple
    (no external services, no dependencies, no schema)

    at the expense of performance
    (no indexing, full serialization roundtrip on each request)

    Not thread safe, a single server process is assumed

    This implementation uses the feature 'id' heavily
    and will override any 'id' provided in the original data.
    The feature 'properties' will be preserved.

    TODO:
    * query method should take bbox
    * instead of methods returning FeatureCollections,
    we should be yielding Features and aggregating in the view
    * there are strict id semantics; all features in the input GeoJSON file
    must be present and be unique strings. Otherwise it will break.
    * How to raise errors in the provider implementation such that
    * appropriate HTTP responses will be raised
    """

    def __init__(self, provider_def):
        """initializer"""
        BaseProvider.__init__(self, provider_def)
        self.fields = self.get_fields()

    def get_fields(self):
        """
         Get provider field information (names, types)

        :returns: dict of fields
        """

        LOGGER.debug('Treating all columns as string types')
        if os.path.exists(self.data):
            with open(self.data) as src:
                data = json.loads(src.read())
            fields = {}
            for f in data['features'][0]['properties'].keys():
                fields[f] = 'string'
            return fields

    def _load(self):
        """Load and validate the source GeoJSON file
        at self.data

        Yes loading from disk, deserializing and validation
        happens on every request. This is not efficient.
        """

        if os.path.exists(self.data):
            with open(self.data) as src:
                data = json.loads(src.read())
        else:
            data = {
                'type': 'FeatureCollection',
                'features': []}

        # Must be a FeatureCollection
        assert data['type'] == 'FeatureCollection'
        # All features must have ids, TODO must be unique strings

        return data

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime=None, properties=[], sortby=[],
              filter_expression=None):
        """
        query the provider

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param filter_expression: string of filter expression

        :returns: FeatureCollection dict of 0..n GeoJSON features
        """

        # TODO filter by bbox without resorting to third-party libs
        data = self._load()

        if filter_expression:
            cql_ast = CQLParser(filter_expression).create_ast()
            feature_set = data['features']
            fields_name = get_filter_fields(feature_set)
            feature_set = CQLFilterEvaluator(list(fields_name),
                                             feature_set).to_filter(cql_ast)
            data['features'] = feature_set

        data['numberMatched'] = len(data['features'])

        if resulttype == 'hits':
            data['features'] = []
        else:
            data['features'] = data['features'][startindex:startindex+limit]
            data['numberReturned'] = len(data['features'])

        return data

    def get(self, identifier):
        """
        query the provider by id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """

        all_data = self._load()
        for feature in all_data['features']:
            if str(feature[self.id_field]) == identifier:
                return feature

        # default, no match
        err = 'item {} not found'.format(identifier)
        LOGGER.error(err)
        raise ProviderItemNotFoundError(err)

    def create(self, new_feature):
        """Create a new feature

        :param new_feature: new GeoJSON feature dictionary
        """
        all_data = self._load()

        # Hijack the feature id and make sure it's unique
        new_feature[self.id_field] = str(uuid.uuid4())

        all_data['features'].append(new_feature)

        with open(self.data, 'w') as dst:
            dst.write(json.dumps(all_data))

    def update(self, identifier, new_feature):
        """Updates an existing feature id with new_feature

        :param identifier: feature id
        :param new_feature: new GeoJSON feature dictionary
        """

        all_data = self._load()
        for i, feature in enumerate(all_data['features']):
            if feature[self.id_field] == identifier:
                # ensure new_feature retains id
                new_feature[self.id_field] = identifier
                all_data['features'][i] = new_feature
                break

        with open(self.data, 'w') as dst:
            dst.write(json.dumps(all_data))

    def delete(self, identifier):
        """Updates an existing feature id with new_feature

        :param identifier: feature id
        """

        all_data = self._load()
        for i, feature in enumerate(all_data['features']):
            if feature[self.id_field] == identifier:
                all_data['features'].pop(i)
                break

        with open(self.data, 'w') as dst:
            dst.write(json.dumps(all_data))

    def __repr__(self):
        return '<GeoJSONProvider> {}'.format(self.data)
