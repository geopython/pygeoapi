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
import copy

from pygeoapi.provider.base import (BaseProvider, ProviderItemNotFoundError,
                                    ProviderSchemaError,
                                    ProviderItemAlreadyExistsError)

LOGGER = logging.getLogger(__name__)


class GeoJSONProvider(BaseProvider):
    """
    Provider class backed by local GeoJSON files

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

    def get_all_fields(self, dict):
        fields = set()
        for f in dict:
            fields = fields.union(set(f['properties'].keys()))
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
            return data

        else:
            data = {
                'type': 'FeatureCollection',
                'features': []}
        '''
        # Must be a FeatureCollection
        assert data['type'] == 'FeatureCollection'
        # All features must have ids, TODO must be unique strings
        for i in data['features']:
            i['id'] = i[self.id_field]
        '''

        return data

    def _load_without_null(self):
        """Load and validate the source GeoJSON file
        at self.data

        Yes loading from disk, deserializing and validation
        happens on every request. This is not efficient.
        """

        if os.path.exists(self.data):
            with open(self.data) as src:
                data = json.loads(src.read())
            mod_data = copy.deepcopy(data)
            for index, feature in enumerate(data['features']):
                for prop in feature['properties']:
                    if feature['properties'][prop] is None:
                        mod_data['features'][index]['properties'].pop(prop)
            return mod_data

        else:
            data = {
                'type': 'FeatureCollection',
                'features': []}
        '''
        # Must be a FeatureCollection
        assert data['type'] == 'FeatureCollection'
        # All features must have ids, TODO must be unique strings
        for i in data['features']:
            i['id'] = i[self.id_field]
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
        data = self._load_without_null()

        data['numberMatched'] = len(data['features'])

        if resulttype == 'hits':
            data['features'] = []
        else:
            data['features'] = data['features'][startindex:startindex+limit]
            data['numberReturned'] = len(data['features'])

        return data

    def get_unused_root_int_id(self):
        feats = self._load()['features']
        ids = set([feat[self.id_field] for feat in feats])
        id = 0
        while True:
            if id not in ids:
                return id
            id = id + 1

    def get_unused_prop_int_id(self):
        feats = self._load()['features']
        ids = set([feat['properties'][self.id_field] for feat in feats])
        id = 0
        while True:
            if id not in ids:
                return id
            id = id + 1

    def get(self, identifier):
        """
        query the provider by id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """

        all_data = self._load()
        samp_feat = all_data['features'][0]
        if self.id_field in samp_feat:
            id_type = type(samp_feat[self.id_field])
        else:
            id_type = type(samp_feat['properties'][self.id_field])
        for feature in all_data['features']:
            if self.id_field in feature:
                if feature[self.id_field] == id_type(identifier):
                    return feature
            elif self.id_field in feature['properties']:
                if feature['properties'][self.id_field] == id_type(identifier):
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
        id_field = self.id_field

        curr_cols = self.get_all_fields(all_data['features']) - {id_field}
        new_cols = set(new_feature['properties'].keys()) - {id_field}

        if id_field in new_feature:
            nfeat_id = new_feature[id_field]
        elif id_field in new_feature['properties']:
            nfeat_id = new_feature['properties'][id_field]
        else:
            nfeat_id = None

        if nfeat_id is not None:
            for feature in all_data['features']:
                if id_field in feature:
                    feat_id = feature[id_field]
                elif id_field in feature['properties']:
                    feat_id = feature['properties'][id_field]
                if nfeat_id == feat_id:
                    err = 'provider item {} already exists'\
                                .format(nfeat_id)
                    LOGGER.error(err)
                    raise ProviderItemAlreadyExistsError(err)
            samp_feat = self.query()['features'][0]
            if id_field in samp_feat:
                if id_field in new_feature['properties']:
                    new_feature['properties'].pop(id_field)
                id_type = type(samp_feat[id_field])
                new_feature[id_field] = id_type(nfeat_id)
            else:
                if id_field in new_feature:
                    new_feature.pop(id_field)
                id_type = type(samp_feat['properties'][id_field])
                new_feature['properties'][id_field] = id_type(nfeat_id)

        # if given data has extra properties not in schema
        if bool(new_cols - curr_cols):
            err = 'properties {} not prescent in provider schema'\
                .format(new_cols - curr_cols)
            LOGGER.error(err)
            raise ProviderSchemaError(err)

        if nfeat_id is None:
            # generate random id
            samp_feat = self.query()['features'][0]
            if id_field in samp_feat:
                if isinstance(samp_feat[id_field], str):
                    new_feature[id_field] = str(uuid.uuid4())
                elif isinstance(samp_feat[id_field], int):
                    new_feature[id_field] = self.get_unused_root_int_id()
            elif id_field in samp_feat['properties']:
                if isinstance(samp_feat['properties'][id_field], str):
                    new_feature['properties'][id_field] = str(uuid.uuid4())
                elif isinstance(samp_feat['properties'][id_field], int):
                    new_feature['properties'][id_field] = \
                        self.get_unused_prop_int_id()

        # set missing properties to empty
        for prop in curr_cols - new_cols:
            new_feature['properties'][prop] = None

        all_data['features'].append(new_feature)
        with open(self.data, 'w') as dst:
            dst.write(json.dumps(all_data, indent=2, sort_keys=True))

        if id_field in new_feature:
            return new_feature[id_field]
        else:
            return new_feature['properties'][id_field]

    def replace(self, identifier, new_feature):
        """
        replace an existing feature item with new_feature item

        :param identifier: feature id
        :param new_feature: new GeoJSON feature dictionary
        """
        all_data = self._load()
        id_field = self.id_field

        curr_cols = self.get_all_fields(self._load()['features']) - {id_field}
        new_cols = set(new_feature['properties'].keys()) - {id_field}

        # set id with type
        samp_feat = self.query()['features'][0]
        if id_field in samp_feat:
            if id_field in new_feature['properties']:
                new_feature['properties'].pop(id_field)
            id_type = type(samp_feat[id_field])
            new_feature[id_field] = id_type(identifier)
        else:
            if id_field in new_feature:
                new_feature.pop(id_field)
            id_type = type(samp_feat['properties'][id_field])
            new_feature['properties'][id_field] = id_type(identifier)

        # flag if id is already prescent in collection
        found_feature = False
        for index, feature in enumerate(all_data['features']):
            if id_field in feature and \
               feature[id_field] == id_type(identifier) or \
               id_field in feature['properties'] and \
               feature['properties'][id_field] == id_type(identifier):
                found_feature = True
                break

        # id is abscent in collection
        if not found_feature:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

        # if given data has extra properties not in schema
        if bool(new_cols - curr_cols):
            err = 'properties {} not prescent in provider schema'\
                .format(new_cols - curr_cols)
            LOGGER.error(err)
            raise ProviderSchemaError(err)

        # id is prescent in collection
        if found_feature:
            # set missing properties to empty
            for prop in curr_cols - new_cols:
                new_feature['properties'][prop] = None
            all_data['features'][index] = new_feature
            # clean up empty attributes
            remove_set = set()
            for attrib in curr_cols:
                empt = True
                for feature in all_data['features']:
                    if feature['properties'][attrib] is not None:
                        empt = False
                        break
                if empt:
                    remove_set.add(attrib)
            for attrib in remove_set:
                for feature in all_data['features']:
                    print(attrib)
                    print(feature)
                    feature['properties'].pop(attrib)

        with open(self.data, 'w') as dst:
            dst.write(json.dumps(all_data, indent=2, sort_keys=True))

    def update(self, identifier, updates):
        """
        update an existing feature item

        :param identifier: feature id
        :param updates: updates dictionary

        :returns: feature item
        """

        id_field = self.id_field

        all_data = self._load()
        samp_feat = all_data['features'][0]
        if self.id_field in samp_feat:
            id_type = type(samp_feat[self.id_field])
        else:
            id_type = type(samp_feat['properties'][self.id_field])

        curr_cols = self.get_all_fields(all_data['features']) - {id_field}

        found_feature = False
        for index, feature in enumerate(all_data['features']):
            if id_field in feature and \
               feature[id_field] == id_type(identifier) or \
               id_field in feature['properties'] and \
               feature['properties'][id_field] == id_type(identifier):
                found_feature = True
                break

        if not found_feature:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)
        else:

            # add an attribute if its not already prescent in the feature
            if 'add' in updates:
                for name_val_pair in updates['add']:
                    name = name_val_pair['name']
                    value = name_val_pair['value']
                    if name not in curr_cols:
                        for f in all_data['features']:
                            f['properties'][name] = None
                        feature['properties'][name] = value
                    else:
                        err = 'property {} exists in given provider item'\
                            .format(name)
                        LOGGER.error(err)
                        raise ProviderSchemaError(err)

            # modify an attribute if its  already prescent in the feature
            if 'modify' in updates:
                for name_val_pair in updates['modify']:
                    name = name_val_pair['name']
                    value = name_val_pair['value']
                    if name in self.get_all_fields(all_data['features']):
                        feature['properties'][name] = value
                    else:
                        err = 'property {} dont exist in given provider item'\
                            .format(name)
                        raise ProviderSchemaError(err)

            # delete an attribute if its prescent in the feature
            if 'remove' in updates:
                for name in updates['remove']:
                    if name in curr_cols and \
                       feature['properties'][name] is not None:
                        feature['properties'][name] = None
                        empt = True
                        for f in all_data['features']:
                            if f['properties'][name] is not None:
                                empt = False
                                break
                        if empt:
                            for f in all_data['features']:
                                f['properties'].pop(name)
                    else:
                        err = 'property {} doesnt exists for given \
                               provider item'.format(name)
                        raise ProviderSchemaError(err)

            all_data['features'][index] = feature

            curr_cols = self.get_all_fields(all_data['features']) - {id_field}
            # clean up empty attributes
            remove_set = set()
            for attrib in curr_cols:
                empt = True
                for feature in all_data['features']:
                    if feature['properties'][attrib] is not None:
                        empt = False
                        break
                if empt:
                    remove_set.add(attrib)
            for attrib in remove_set:
                for feature in all_data['features']:
                    feature['properties'].pop(attrib)

            with open(self.data, 'w') as dst:
                dst.write(json.dumps(all_data, indent=2, sort_keys=True))

            feature = all_data['features'][index]
            return feature

    def delete(self, identifier):
        """
        deletes an existing feature item

        :param identifier: feature id
        """

        id_field = self.id_field

        all_data = self._load()
        samp_feat = all_data['features'][0]
        if self.id_field in samp_feat:
            id_type = type(samp_feat[self.id_field])
        else:
            id_type = type(samp_feat['properties'][self.id_field])

        found_feature = False
        for index, feature in enumerate(all_data['features']):
            if id_field in feature and \
               feature[id_field] == id_type(identifier) or \
               id_field in feature['properties'] and \
               feature['properties'][id_field] == id_type(identifier):
                found_feature = True
                break

        if not found_feature:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)
        else:
            all_data['features'].pop(index)

            curr_cols = self.get_all_fields(all_data['features']) - {id_field}
            # clean up empty attributes
            remove_set = set()
            for attrib in curr_cols:
                empt = True
                for feature in all_data['features']:
                    if feature['properties'][attrib] is not None:
                        empt = False
                        break
                if empt:
                    remove_set.add(attrib)
            for attrib in remove_set:
                for feature in all_data['features']:
                    feature['properties'].pop(attrib)

            with open(self.data, 'w') as dst:
                dst.write(json.dumps(all_data, indent=2, sort_keys=True))

    def __repr__(self):
        return '<GeoJSONProvider> {}'.format(self.data)
