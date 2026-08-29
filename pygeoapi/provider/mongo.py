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

from pygeoapi.crs import crs_transform
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

        super().__init__(provider_def)

        LOGGER.info(f'Mongo source config: {self.data}')

        dbclient = MongoClient(self.data)
        self.featuredb = dbclient.get_default_database()
        self.collection = provider_def['collection']
        self.featuredb[self.collection].create_index([("feature.geometry", GEOSPHERE)])
        self.get_fields()

    def get_fields(self):
        """
        Get provider field information (names, types)

        :returns: dict of fields
        """

        if not self._fields:
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
            for i in result:
                for key in result[0]['_id'].keys():
                    self._fields[key] = {'type': 'string'}

        return self._fields

    def _get_feature_list(self, filterObj, sortList=[], skip=0, maxitems=1,
                          skip_geometry=False):
        featurecursor = self.featuredb[self.collection].find(filterObj)
        if sortList:
            featurecursor = featurecursor.sort(sortList)

        featurecursor.skip(skip)
        if maxitems > -1:
            featurecursor.limit(maxitems)
        featurelist = list(featurecursor)

        features = []

        for item in featurelist:
            feature_id = str(item.pop('_id'))
            geometry = item['feature']['geometry']
            props = item['feature']['properties']
            
            if skip_geometry:
                geometry = None

            feature = {
                'type': 'Feature',
                'id': feature_id,
                'geometry': geometry,
                'properties': props
            }

            features.append(feature)

        return features

    @crs_transform
    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, filterq=None, **kwargs):
        """
        query the provider

        :returns: dict of 0..n GeoJSON features
        """

        def cql2_to_mongo(node):
            if node is None:
                return
            
            # GeoJson operator
            if node.__class__.__name__ == "GeometryWithin":
                field = node.lhs.name
                geom = node.rhs.geometry

                query_body = {
                    field: {
                        '$geoWithin': {
                            '$geometry': geom
                        }
                    }
                }
                return query_body
            
            if node.__class__.__name__ == "GeometryIntersects":
                field = node.lhs.name
                geom = node.rhs.geometry

                return {
                    field: {
                        '$geoIntersects': {
                            '$geometry': geom
                        }
                    }
                }

            if node.__class__.__name__ == "DistanceWithin":
                field = node.lhs.name
                geom = node.rhs.geometry
                distance = node.distance
                units = node.units # mongo's default units are meters
                # but with CQL we can pass different units
                # and here we can recalculate them
                return {
                    field: {
                        '$near': {
                            '$geometry': geom,
                            '$maxDistance': distance,
                            '$minDistance': 0
                        }
                    }
                }

            # Logical operators
            if node.__class__.__name__ == "And":
                return {
                    "$and": [
                        cql2_to_mongo(node.lhs),
                        cql2_to_mongo(node.rhs)
                    ]
                }

            if node.__class__.__name__ == "Or":
                return {
                    "$or": [
                        cql2_to_mongo(node.lhs),
                        cql2_to_mongo(node.rhs)
                    ]
                }

            # Comparison operators
            if node.__class__.__name__ == "Equal":
                field = node.lhs.name
                value = node.rhs
                return {f"{field}": value}

            if node.__class__.__name__ == "GreaterEqual":
                field = node.lhs.name
                value = node.rhs
                return {f"{field}": {"$gte": value}}

            if node.__class__.__name__ == "LessEqual":
                field = node.lhs.name
                value = node.rhs
                return {f"{field}": {"$lte": value}}

            return

        and_filter = []
        cql_filters_parsed = cql2_to_mongo(filterq)
        if cql_filters_parsed is not None:
            and_filter.append(cql_filters_parsed)
            limit = -1 # if there is CQL query return all elements
        
        if len(bbox) == 4:
            x, y, w, h = map(float, bbox)
            and_filter.append(
                {'geometry': {'$geoWithin': {'$box': [[x, y], [w, h]]}}})

        
        for prop in properties:
            and_filter.append({"properties."+prop[0]: {'$eq': prop[1]}})
        
        filterobj = {'$and': and_filter} if and_filter else {}

        sort_list = [("properties." + sort['property'],
                      ASCENDING if (sort['order'] == '+') else DESCENDING)
                     for sort in sortby]

        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        if resulttype == 'hits':
            return feature_collection

        featurelist = self._get_feature_list(
            filterobj, sortList=sort_list, skip=offset, maxitems=limit,
            skip_geometry=skip_geometry
        )

        feature_collection['features'] = featurelist
        feature_collection['numberReturned'] = len(featurelist)

        return feature_collection

    @crs_transform
    def get(self, identifier, **kwargs):
        """
        query the provider by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """
        featurelist = self._get_feature_list({'_id': ObjectId(identifier)})
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
