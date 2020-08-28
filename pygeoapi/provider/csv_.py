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
import uuid
import copy

from pygeoapi.provider.base import (BaseProvider, ProviderQueryError,
                                    ProviderItemNotFoundError,
                                    ProviderSchemaError,
                                    ProviderItemAlreadyExistsError)

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

    def stc(self, s):
        if s == 'string':
            return str
        if s == 'integer':
            return int
        if s == 'number':
            return float

    def assign_type(self, k, v):
        if v != '':
            v = self.stc(self.fields[k])(v)
        return v

    def count(self):
        with open(self.data) as ff:
            totalrows = 0
            data_ = csv.DictReader(ff)
            for row in data_:
                totalrows += 1
            return totalrows

    def get_fields(self):
        """
        Get provider field information (names, types)

        :returns: dict of fields
        """

        with open(self.data) as ff:
            LOGGER.debug('Serializing DictReader')
            data_ = csv.DictReader(ff)
            fields = {}
            samp_data = {}
            for row in data_:
                for key in row:
                    if key not in samp_data and row[key] != '':
                        samp_data[key] = row[key]
            for key in samp_data:
                try:
                    value = samp_data[key]
                    samp_data[key] = float(value)
                    if samp_data[key]-int(samp_data[key]) == 0:
                        samp_data[key] = int(value)
                except ValueError:
                    samp_data[key] = str(value)
                fields[key] = type(samp_data[key]).__name__
            fields[self.geometry_x] = float.__name__
            fields[self.geometry_y] = float.__name__
            # convert python types to openapidoc types
            for field in fields:
                if fields[field] == 'int':
                    fields[field] = 'integer'
                elif fields[field] == 'float':
                    fields[field] = 'number'
                elif fields[field] == 'str':
                    fields[field] = 'string'
            return fields

    def _load(self, startindex=0, limit=10, resulttype='results',
              identifier=None, bbox=[], datetime=None, properties=[]):
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
                LOGGER.debug('Returning hits only')
                feature_collection['numberMatched'] = len(list(data_))
                return feature_collection
            LOGGER.debug('Slicing CSV rows')
            for row in itertools.islice(data_, startindex, startindex+limit):
                for key in row:
                    if row[key] != '':
                        row[key] = self.assign_type(key, row[key])
                feature = {'type': 'Feature'}
                feature[self.id_field] = row.pop(self.id_field)
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
                    feature['properties'] = dict()
                    for prop in row:
                        feature['properties'][prop] = row[prop]

                if identifier is not None and \
                   feature[self.id_field] == \
                   self.assign_type(self.id_field, identifier):
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

    def get_unused_int_id(self):
        feats = self._load(limit=self.count())['features']
        ids = set(map(int, set([feat[self.id_field] for feat in feats])))
        id = 0
        while True:
            if id not in ids:
                return id
            id = id + 1

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime=None, properties=[], sortby=[]):
        """
        CSV query

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)

        :returns: dict of GeoJSON FeatureCollection
        """

        return self._load(startindex, limit, resulttype)

    def get(self, identifier):
        """
        query CSV id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """
        item = self._load(identifier=identifier)
        if item:
            for prop in item['properties']:
                if item['properties'][prop] == '':
                    item['properties'][prop] = None
            return item
        else:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

    def create(self, new_feature):
        """
        create a new feature item

        :param new_feature: new GeoJSON feature dictionary

        :returns: feature id
        """
        id_field = self.id_field
        with open(self.data) as csv_file:
            curr = [{k: self.assign_type(k, v) for k, v in row.items()}
                    for row in csv.DictReader(csv_file, skipinitialspace=True)]

        curr_cols = set(curr[0].keys()) - {id_field}
        new_cols = set(new_feature['properties'].keys()).\
            union({'lat', 'long'}) - {id_field}

        # copy properties of the given data
        feature = copy.deepcopy(new_feature['properties'])
        # copy latitude and longitude of given data
        feature['lat'] = new_feature['geometry']['coordinates'][1]
        feature['long'] = new_feature['geometry']['coordinates'][0]
        # initialize id field
        feature[id_field] = None

        # set id if present in request
        if id_field in new_feature:
            feature[id_field] = new_feature[id_field]
        elif id_field in new_feature['properties']:
            feature[id_field] = new_feature['properties'][id_field]

        #  check if id already exist
        if feature[id_field] is not None:
            for f in curr:
                if f[id_field] == self.\
                   assign_type(id_field, feature[id_field]):
                    err = 'provider item {} already exists'\
                        .format(feature[id_field])
                    LOGGER.error(err)
                    raise ProviderItemAlreadyExistsError(err)
        else:
            # set a randomly generated id
            samp_feat = self.query()['features'][0]
            try:
                int(samp_feat[id_field])
                feature[id_field] = self.get_unused_int_id()
            except ValueError:
                feature[id_field] = str(uuid.uuid4())

        # if given data has extra properties not in schema
        if bool(new_cols - curr_cols):
            err = 'properties {} not prescent in provider schema'\
                .format(new_cols - curr_cols)
            LOGGER.error(err)
            raise ProviderSchemaError(err)

        # append given data to provider data items
        curr.append(feature)

        # writing new set of data items to csv file
        try:
            with open(self.data, 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=curr[0].keys())
                writer.writeheader()
                for data in curr:
                    writer.writerow(data)
        except IOError:
            LOGGER.error("I/O error")

        # return id of the new data item added
        return feature[id_field]

    def replace(self, identifier, new_feature):
        """
        replace an existing feature item with new_feature item

        :param identifier: feature id
        :param new_feature: new GeoJSON feature dictionary
        """
        id_field = self.id_field
        with open(self.data) as csv_file:
            curr = [{k: self.assign_type(k, v) for k, v in row.items()}
                    for row in csv.DictReader(csv_file, skipinitialspace=True)]

        curr_cols = set(curr[0].keys()) - {id_field}
        new_cols = set(new_feature['properties'].keys())\
            .union({'lat', 'long'}) - {id_field}
        index = -1
        for i, f in enumerate(curr):
            if f[id_field] == self.assign_type(id_field, identifier):
                index = i

        # if given identifier is not prescent in the data provider
        if index == -1:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

        # if given data item has extra properties not in schema
        if bool(new_cols - curr_cols):
            err = 'properties {} not prescent in provider schema'\
                .format(new_cols - curr_cols)
            LOGGER.error(err)
            raise ProviderSchemaError(err)

        # copy properties of the given data
        feature = new_feature['properties']
        for k in feature:
            feature[k] = feature[k]
        # copy latitude and longitude of given data
        feature['lat'] = new_feature['geometry']['coordinates'][1]
        feature['long'] = new_feature['geometry']['coordinates'][0]
        # set id of given data
        feature[id_field] = identifier
        # set empty for remaining attributes
        for attrib in curr_cols - new_cols:
            feature[attrib] = ''
        # replace the data items
        curr[index] = feature

        # clean up empty attributes
        remove_set = set()
        for attrib in curr[0].keys():
            empt = True
            for feature in curr:
                if feature[attrib] != '':
                    empt = False
                    break
            if empt:
                remove_set.add(attrib)
        for attrib in remove_set:
            for feature in curr:
                feature.pop(attrib)

        new_fields = set(curr[0].keys())-remove_set

        # writing new set of data items to csv file
        try:
            with open(self.data, 'w') as csvfile:
                writer = csv.DictWriter(csvfile,
                                        fieldnames=new_fields)
                writer.writeheader()
                for data in curr:
                    writer.writerow(data)
        except IOError:
            LOGGER.error("I/O error")
        self.fields = self.get_fields()

    def update(self, identifier, updates):
        """
        update an existing feature item

        :param identifier: feature id
        :param updates: updates dictionary

        :returns: feature item
        """
        id_field = self.id_field

        with open(self.data) as csv_file:
            curr = [{k: self.assign_type(k, v) for k, v in row.items()}
                    for row in csv.DictReader(csv_file, skipinitialspace=True)]

        found_feature = False
        for index, feature in enumerate(curr):
            if feature[id_field] == self.assign_type(id_field, identifier):
                found_feature = True
                break

        if not found_feature:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)
        else:
            add_set = set()
            if 'add' in updates:
                # add the attribute if its not in the feature
                for name_val_pair in updates['add']:
                    name = name_val_pair['name']
                    value = name_val_pair['value']
                    add_set.add(name)
                    if name not in feature:
                        feature[name] = value
                    else:
                        err = 'property {} already exists'.format(name)
                        LOGGER.error(err)
                        raise ProviderSchemaError(err)
            if 'modify' in updates:
                # modify an attribute only if its already prescent
                for name_val_pair in updates['modify']:
                    name = name_val_pair['name']
                    value = name_val_pair['value']
                    if name in feature and name not in {id_field,
                                                        'lat', 'long'}:
                        feature[name] = value
                    else:
                        err = 'property {} already exists'.format(name)
                        LOGGER.error(err)
                        raise ProviderSchemaError(err)
            if 'remove' in updates:
                # delete an attribute only if its prescent
                for name in updates['remove']:
                    if name in feature:
                        feature[name] = ''
                    else:
                        err = 'property {} already exists for given provider \
                            item'.format(name)
                        LOGGER.error(err)
                        raise ProviderSchemaError(err)

            curr[index] = feature

            # clean up empty attributes
            remove_set = set()
            for attrib in curr[0].keys():
                empt = True
                for feature in curr:
                    if feature[attrib] != '':
                        empt = False
                        break
                if empt:
                    remove_set.add(attrib)
            for attrib in remove_set:
                for feature in curr:
                    feature.pop(attrib)

            # writing new set of data items to csv file
            new_fields = set(curr[0].keys()).union(add_set)-remove_set
            try:
                with open(self.data, 'w') as csvfile:
                    writer = csv.DictWriter(csvfile,
                                            fieldnames=new_fields)
                    writer.writeheader()
                    for data in curr:
                        writer.writerow(data)
            except IOError:
                LOGGER.error("I/O error")
            self.fields = self.get_fields()

            return self.get(identifier)

    def delete(self, identifier):
        """
        deletes an existing feature item

        :param identifier: feature id
        """
        id_field = self.id_field

        with open(self.data) as csv_file:
            curr = [{k: self.assign_type(k, v) for k, v in row.items()}
                    for row in csv.DictReader(csv_file, skipinitialspace=True)]

        found_feature = False
        for index, feature in enumerate(curr):

            if feature[id_field] == self.assign_type(id_field, identifier):
                found_feature = True
                break

        if not found_feature:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)
        else:
            curr.pop(index)

            # clean up empty attributes
            remove_set = set()
            for attrib in curr[0].keys():
                empt = True
                for feature in curr:
                    if feature[attrib] != '':
                        empt = False
                        break
                if empt:
                    remove_set.add(attrib)
            for attrib in remove_set:
                for feature in curr:
                    feature.pop(attrib)

            new_fields = set(curr[0].keys())-remove_set
            try:
                with open(self.data, 'w') as csvfile:
                    writer = csv.DictWriter(csvfile,
                                            fieldnames=new_fields)
                    writer.writeheader()
                    for data in curr:
                        writer.writerow(data)
            except IOError:
                LOGGER.error("I/O error")
            self.fields = self.get_fields()

    def __repr__(self):
        return '<CSVProvider> {}'.format(self.data)
