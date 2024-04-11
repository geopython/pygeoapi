# =================================================================
#
# Authors: Timo Tuunanen <timo.tuunanen@rdvelho.com>
#
# Copyright (c) 2019 Timo Tuunanen
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

from datetime import datetime
import logging

from pymongo import MongoClient
from pymongo import GEOSPHERE
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import ObjectId
from pygeoapi.provider.base import BaseProvider, ProviderItemNotFoundError
from pygeoapi.util import crs_transform

LOGGER = logging.getLogger(__name__)


class MongoProvider(BaseProvider):
    """Generic provider for Mongodb.
    """

    def __init__(self, provider_def):
        """
        MongoProvider Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class

        :returns: pygeoapi.provider.mongo.MongoProvider
        """
        # this is dummy value never used in case of Mongo.
        # Mongo id field is _id
        provider_def.setdefault('id_field', '_id')

        super().__init__(provider_def)

        LOGGER.info(f'Mongo source config: {self.data}')

        dbclient = MongoClient(self.data)
        self.featuredb = dbclient.get_default_database()
        self.collection = provider_def['collection']
        self.featuredb[self.collection].create_index([("geometry", GEOSPHERE)])
        self.fields = self.get_fields()

    def get_fields(self):
        """
        Get provider field information (names, types)

        :returns: dict of fields
        """

        pipeline = [
            {"$project": {"properties": 1}},
            {"$unwind": "$properties"},
            {"$group": {"_id": "$properties", "count": {"$sum": 1}}},
            {"$project": {"_id": 1}}
        ]

        result = list(self.featuredb[self.collection].aggregate(pipeline))

        # prepare a dictionary with fields
        # set the field type to 'string'.
        # by operating without a schema, mongo can query any data type.
        fields = {}

        for i in result:
            for key in result[0]['_id'].keys():
                fields[key] = {'type': 'string'}

        return fields

    def _get_feature_list(self, filterObj, sortList=[], skip=0, maxitems=1,
                          skip_geometry=False):
        featurecursor = self.featuredb[self.collection].find(filterObj)

        if sortList:
            featurecursor = featurecursor.sort(sortList)

        matchCount = self.featuredb[self.collection].count_documents(filterObj)
        featurecursor.skip(skip)
        featurecursor.limit(maxitems)
        featurelist = list(featurecursor)
        for item in featurelist:
            item['id'] = str(item.pop('_id'))
            if skip_geometry:
                item['geometry'] = None

        return featurelist, matchCount

    @crs_transform
    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, **kwargs):
        """
        query the provider

        :returns: dict of 0..n GeoJSON features
        """
        and_filter = []

        if len(bbox) == 4:
            x, y, w, h = map(float, bbox)
            and_filter.append(
                {'geometry': {'$geoWithin': {'$box': [[x, y], [w, h]]}}})

        # This parameter is not working yet!
        # gte is not sufficient to check date range
        if datetime_ is not None:
            assert isinstance(datetime_, datetime)
            and_filter.append({'properties.datetime': {'$gte': datetime_}})

        for prop in properties:
            and_filter.append({"properties."+prop[0]: {'$eq': prop[1]}})

        filterobj = {'$and': and_filter} if and_filter else {}

        sort_list = [("properties." + sort['property'],
                      ASCENDING if (sort['order'] == '+') else DESCENDING)
                     for sort in sortby]

        featurelist, matchcount = self._get_feature_list(
            filterobj, sortList=sort_list, skip=offset, maxitems=limit,
            skip_geometry=skip_geometry)

        if resulttype == 'hits':
            featurelist = []

        feature_collection = {
            'type': 'FeatureCollection',
            'features': featurelist,
            'numberMatched': matchcount,
            'numberReturned': len(featurelist)
        }

        return feature_collection

    @crs_transform
    def get(self, identifier, **kwargs):
        """
        query the provider by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """
        featurelist, matchcount = self._get_feature_list(
                                    {'_id': ObjectId(identifier)})
        if featurelist:
            return featurelist[0]
        else:
            err = f'item {identifier} not found'
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

    def create(self, new_feature):
        """Create a new feature
        """
        self.featuredb[self.collection].insert_one(new_feature)

    def update(self, identifier, updated_feature):
        """Updates an existing feature id with new_feature

        :param identifier: feature id
        :param new_feature: new GeoJSON feature dictionary
        """
        data = {k: v for k, v in updated_feature.items() if k != 'id'}
        self.featuredb[self.collection].update_one(
            {'_id': ObjectId(identifier)}, {"$set": data})

    def delete(self, identifier):
        """Deletes an existing feature

        :param identifier: feature id
        """
        self.featuredb[self.collection].delete_one(
            {'_id': ObjectId(identifier)})
