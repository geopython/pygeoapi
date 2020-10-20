# =================================================================
#
# Authors: Timo Tuunanen <timo.tuunanen@rdvelho.com>
#
# Copyright (c) 2019 Timo Tuunanen
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

import logging

from bson import Code
from pymongo import MongoClient
from pymongo import GEOSPHERE
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import ObjectId
from pygeoapi.provider.base import BaseProvider, ProviderItemNotFoundError

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

        BaseProvider.__init__(self, provider_def)

        LOGGER.info('Mongo source config: {}'.format(self.data))

        dbclient = MongoClient(self.data)
        self.featuredb = dbclient.get_default_database()
        self.collection = provider_def['collection']
        self.featuredb[self.collection].create_index([("geometry", GEOSPHERE)])

    def get_fields(self):
        """
        Get provider field information (names, types)

        :returns: dict of fields
        """
        map = Code(
            "function() { for (var key in this.properties) "
            "{ emit(key, null); } }")
        reduce = Code("function(key, stuff) { return null; }")
        result = self.featuredb[self.collection].map_reduce(
            map, reduce, "myresults")
        return result.distinct('_id')

    def _get_feature_list(self, filterObj, sortList=[], skip=0, maxitems=1):
        featurecursor = self.featuredb[self.collection].find(filterObj)

        if sortList:
            featurecursor = featurecursor.sort(sortList)

        matchCount = self.featuredb[self.collection].count_documents(filterObj)
        featurecursor.skip(skip)
        featurecursor.limit(maxitems)
        featurelist = list(featurecursor)
        for item in featurelist:
            item['id'] = str(item.pop('_id'))

        return featurelist, matchCount

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime=None, properties=[], sortby=[]):
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
        if datetime is not None:
            assert isinstance(datetime.datetime, datetime)
            and_filter.append({'properties.datetime': {'$gte': datetime}})

        for prop in properties:
            and_filter.append({"properties."+prop[0]: {'$eq': prop[1]}})

        filterobj = {'$and': and_filter} if and_filter else {}

        sort_list = [("properties." + sort['property'],
                      ASCENDING if (sort['order'] == 'A') else DESCENDING)
                     for sort in sortby]

        featurelist, matchcount = self._get_feature_list(filterobj,
                                                         sortList=sort_list,
                                                         skip=startindex,
                                                         maxitems=limit)

        if resulttype == 'hits':
            featurelist = []

        feature_collection = {
            'type': 'FeatureCollection',
            'features': featurelist,
            'numberMatched': matchcount,
            'numberReturned': len(featurelist)
        }

        return feature_collection

    def get(self, identifier):
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
            err = 'item {} not found'.format(identifier)
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
