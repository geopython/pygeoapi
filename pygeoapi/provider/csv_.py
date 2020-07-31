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
                    feature['properties'] = dict()
                    for prop in row:
                        if row[prop] != '':
                            feature['properties'][prop] = row[prop]

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

        feature_collection['numberReturned'] = len(
            feature_collection['features'])

        return feature_collection

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
            print(item)
            props = item.pop('properties')
            item['properties'] = dict()
            for prop in props:
                if props[prop] != '':
                    item['properties'][prop] = props[prop]
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
            curr = [{k: v for k, v in row.items()}
                    for row in csv.DictReader(csv_file, skipinitialspace=True)]

        curr_cols = set(curr[0].keys())
        new_cols = set(new_feature['properties'].keys()).union({id_field,
                                                               'lat', 'long'})

        # if given data has extra properties not in schema
        if bool(new_cols - curr_cols):
            err = 'properties {} not prescent in provider schema'\
                .format(new_cols - curr_cols)
            LOGGER.error(err)
            raise ProviderSchemaError(err)
        else:
            # copy properties of the given data
            feature = new_feature['properties']
            # copy latitude and longitude of given data
            lat = new_feature['geometry']['coordinates'][1]
            lon = new_feature['geometry']['coordinates'][0]
            feature['lat'] = lat
            feature['long'] = lon
            # set id of given data
            if id_field in new_feature:
                feature[id_field] = str(new_feature[id_field])
                # if id is already used in the provider
                for f in curr:
                    if str(f[id_field]) == feature[id_field]:
                        err = 'provider item {} already exists'\
                            .format(feature[id_field])
                        LOGGER.error(err)
                        raise ProviderItemAlreadyExistsError(err)
            else:
                # set a randomly generated id
                feature[id_field] = str(uuid.uuid4())
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
                print("I/O error")

            # return id of the new data item added
            return new_feature['properties'][id_field]

    def replace(self, identifier, new_feature):
        """
        replace an existing feature item with new_feature item

        :param identifier: feature id
        :param new_feature: new GeoJSON feature dictionary
        """
        id_field = self.id_field
        with open(self.data) as csv_file:
            curr = [{k: v for k, v in row.items()}
                    for row in csv.DictReader(csv_file, skipinitialspace=True)]

        curr_cols = set(curr[0].keys())
        new_cols = set(new_feature['properties'].keys()).union({id_field,
                                                               'lat', 'long'})
        index = -1
        for i, f in enumerate(curr):
            if str(f[id_field]) == str(identifier):
                index = i

        # if given identifier is not prescent in the data provider
        if index == -1:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

        else:
            # if given data item has extra properties not in schema
            if bool(new_cols - curr_cols):
                err = 'properties {} not prescent in provider schema'\
                    .format(new_cols - curr_cols)
                LOGGER.error(err)
                raise ProviderSchemaError(err)
            else:
                # copy properties of the given data
                feature = new_feature['properties']
                for k in feature:
                    feature[k] = feature[k]
                # copy latitude and longitude of given data
                lat = new_feature['geometry']['coordinates'][1]
                lon = new_feature['geometry']['coordinates'][0]
                feature['lat'] = lat
                feature['long'] = lon
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
                    print("I/O error")

    def update(self, identifier, updates):
        """
        update an existing feature item

        :param identifier: feature id
        :param updates: updates dictionary

        :returns: feature item
        """
        id_field = self.id_field

        with open(self.data) as csv_file:
            curr = [{k: v for k, v in row.items()}
                    for row in csv.DictReader(csv_file, skipinitialspace=True)]

        found_feature = False
        for index, feature in enumerate(curr):
            if str(feature[id_field]) == identifier:
                found_feature = True
                break

        if not found_feature:
            err = 'item {} not found'.format(identifier)
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)
        else:
            if 'add' in updates:
                add_set = set()
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
                print("I/O error")

            return self._load(identifier=identifier)

    def delete(self, identifier):
        """
        deletes an existing feature item

        :param identifier: feature id
        """
        id_field = self.id_field

        with open(self.data) as csv_file:
            curr = [{k: v for k, v in row.items()}
                    for row in csv.DictReader(csv_file, skipinitialspace=True)]

        found_feature = False
        for index, feature in enumerate(curr):
            if str(feature[id_field]) == identifier:
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
                print("I/O error")

    def __repr__(self):
        return '<CSVProvider> {}'.format(self.data)
