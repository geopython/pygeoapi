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
        '''
        # Must be a FeatureCollection
        assert data['type'] == 'FeatureCollection'
        # All features must have ids, TODO must be unique strings
        for i in data['features']:
            i['id'] = i['properties'][self.id_field]
        '''

        return data

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime=None, properties=[], sortby=[]):
        """
        query the provider

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)

        :returns: FeatureCollection dict of 0..n GeoJSON features
        """

        # TODO filter by bbox without resorting to third-party libs
        data = self._load()

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
            if str(feature['properties'][self.id_field]) == identifier:
                return feature

        # default, no match
        err = 'item {} not found'.format(identifier)
        LOGGER.error(err)
        raise ProviderItemNotFoundError(err)

    def create(self, new_feature):
        """
        create a new feature item

        :param new_feature: new GeoJSON feature dictionary

        :returns: feature id
        """
        all_data = self._load()

        if 'id' in new_feature['properties']:
            try:
                self.get(str(new_feature['properties']['id']))
                new_feature['properties']['id'] = str(uuid.uuid4())
            except ProviderItemNotFoundError:
                pass
        else:
            new_feature['properties']['id'] = str(uuid.uuid4())

        all_data['features'].append(new_feature)

        with open(self.data, 'w') as dst:
            dst.write(json.dumps(all_data, indent=2, sort_keys=True))

        return new_feature['properties']['id']

    def replace(self, identifier, new_feature):
        """
        replace an existing feature item with new_feature item

        :param identifier: feature id
        :param new_feature: new GeoJSON feature dictionary

        :returns: feature item
        """

        all_data = self._load()

        found_feature = False
        for index, feature in enumerate(all_data['features']):
            if str(feature['properties']['id']) == identifier:
                found_feature = True
                break

        if not found_feature:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)
        else:
            new_feature['properties']['id'] = identifier
            all_data['features'][index] = new_feature
            with open(self.data, 'w') as dst:
                dst.write(json.dumps(all_data, indent=2, sort_keys=True))

    def update(self, identifier, updates):
        """
        update an existing feature item

        :param identifier: feature id
        :param new_feature: new GeoJSON feature dictionary

        :returns: feature item
        """

        all_data = self._load()

        found_feature = False
        for feature in all_data['features']:
            if str(feature['properties']['id']) == identifier:
                found_feature = True
                break

        if not found_feature:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)
        else:
            # not allowed to modify/remove id field
            for index, name_val_pair in enumerate(updates['modify']):
                if name_val_pair['name'] == 'id':
                    updates['modify'].pop(index)
            for index, attrib in enumerate(updates['remove']):
                if attrib == 'id':
                    updates['remove'].pop(index)
            # add an attribute if its not already prescent in the feature
            for name_val_pair in updates['add']:
                name = name_val_pair['name']
                value = name_val_pair['value']
                if name not in feature['properties']:
                    feature['properties'][name] = value
                else:
                    pass
            # modify an attribute if its  already prescent in the feature
            for name_val_pair in updates['modify']:
                name = name_val_pair['name']
                value = name_val_pair['value']
                if name in feature['properties']:
                    feature['properties'][name] = value
                else:
                    pass
            # delete an attribute if its prescent in the feature
            for name in updates['remove']:
                if name in feature['properties']:
                    feature['properties'].pop(name)
                else:
                    pass

            all_data['features'][index] = feature

            with open(self.data, 'w') as dst:
                dst.write(json.dumps(all_data, indent=2, sort_keys=True))
            return feature

    def delete(self, identifier):
        """
        deletes an existing feature item

        :param identifier: feature id
        """

        all_data = self._load()

        found_feature = False
        for index, feature in enumerate(all_data['features']):
            if str(feature['properties']['id']) == identifier:
                found_feature = True
                break

        if not found_feature:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)
        else:
            all_data['features'].pop(index)
            with open(self.data, 'w') as dst:
                dst.write(json.dumps(all_data, indent=2, sort_keys=True))

    def __repr__(self):
        return '<GeoJSONProvider> {}'.format(self.data)
