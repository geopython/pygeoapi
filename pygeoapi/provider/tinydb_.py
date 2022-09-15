# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
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

import logging
import re  # noqa
import os

from tinydb import TinyDB, Query, where

from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
                                    ProviderQueryError,
                                    ProviderItemNotFoundError)

LOGGER = logging.getLogger(__name__)


class TinyDBCatalogueProvider(BaseProvider):
    """TinyDB Catalogue Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.tinydb_.TinyDBCatalogueProvider
        """

        self.excludes = [
            '_metadata-anytext',
        ]

        super().__init__(provider_def)

        LOGGER.debug('Connecting to TinyDB db at {}'.format(self.data))

        if not os.path.exists(self.data):
            msg = 'TinyDB does not exist'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

        LOGGER.debug('Checking TinyDB DB permissions')
        if not os.access(self.data, os.W_OK):
            self.db = TinyDB(self.data, access_mode='r')
        else:
            self.db = TinyDB(self.data)

        self.fields = self.get_fields()

    def get_fields(self):
        """
         Get provider field information (names, types)

        :returns: dict of fields
        """

        fields = {}

        try:
            r = self.db.all()[0]
        except IndexError as err:
            LOGGER.debug(err)
            return fields

        for p in r['properties'].keys():
            if p not in self.excludes + ['extent']:
                fields[p] = {'type': 'string'}

        fields['q'] = {'type': 'string'}

        return fields

    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, **kwargs):
        """
        query TinyDB document store

        :param offset: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param q: full-text search term(s)

        :returns: dict of 0..n GeoJSON feature collection
        """

        Q = Query()
        LOGGER.debug('Query initiated: {}'.format(Q))

        QUERY = []

        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        if resulttype == 'hits':
            LOGGER.debug('hits only specified')
            limit = 0

        if bbox:
            LOGGER.debug('processing bbox parameter')
            bbox_as_string = ','.join(str(s) for s in bbox)
            QUERY.append("Q.properties.extent.spatial.bbox.test(bbox_intersects, '{}')".format(bbox_as_string))  # noqa

        if datetime_ is not None:
            LOGGER.debug('processing datetime parameter')
            if self.time_field is None:
                LOGGER.error('time_field not enabled for collection')
                raise ProviderQueryError()

            if '/' in datetime_:  # envelope
                LOGGER.debug('detected time range')
                time_begin, time_end = datetime_.split('/')

                if time_begin != '..':
                    QUERY.append("(Q.properties[self.time_field]>='{}')".format(time_begin))  # noqa
                if time_end != '..':
                    QUERY.append("(Q.properties[self.time_field]<='{}')".format(time_end))  # noqa

            else:  # time instant
                LOGGER.debug('detected time instant')
                QUERY.append("(Q.properties[self.time_field]=='{}')".format(datetime_))  # noqa

        if properties:
            LOGGER.debug('processing properties')
            for prop in properties:
                QUERY.append("(Q.properties['{}']=='{}')".format(*prop))

        if q is not None:
            for t in q.split():
                QUERY.append("(Q.properties['_metadata-anytext'].search('{}', flags=re.IGNORECASE))".format(t))  # noqa

        QUERY_STRING = '&'.join(QUERY)
        LOGGER.debug('QUERY_STRING: {}'.format(QUERY_STRING))
        SEARCH_STRING = 'self.db.search({})'.format(QUERY_STRING)
        LOGGER.debug('SEARCH_STRING: {}'.format(SEARCH_STRING))

        LOGGER.debug('querying database')
        if len(QUERY) > 0:
            LOGGER.debug('running eval on {}'.format(SEARCH_STRING))
            results = eval(SEARCH_STRING)
        else:
            results = self.db.all()

        feature_collection['numberMatched'] = len(results)

        if resulttype == 'hits':
            return feature_collection

        for r in results:
            for e in self.excludes:
                try:
                    del r['properties'][e]
                except KeyError:
                    LOGGER.debug('Missing excluded property {}'.format(e))

        len_results = len(results)

        LOGGER.debug('Results found: {}'.format(len_results))

        if len_results > limit:
            returned = limit
        else:
            returned = len_results

        feature_collection['numberReturned'] = returned

        if sortby:
            LOGGER.debug('Sorting results')
            if sortby[0]['order'] == '-':
                sort_reverse = True
            else:
                sort_reverse = False

            results.sort(key=lambda k: k['properties'][sortby[0]['property']],
                         reverse=sort_reverse)

        feature_collection['features'] = results[offset:offset + limit]

        return feature_collection

    def get(self, identifier, **kwargs):
        """
        Get TinyDB document by id

        :param identifier: record id

        :returns: `dict` of single record
        """

        LOGGER.debug('Fetching identifier {}'.format(identifier))

        record = self.db.get(Query().id == identifier)

        if record is None:
            raise ProviderItemNotFoundError('record does not exist')

        for e in self.excludes:
            try:
                del record['properties'][e]
            except KeyError:
                LOGGER.debug('Missing excluded property {}'.format(e))

        return record

    def create(self, item):
        """
        Adds an item to the TinyDB repository

        :param item: item data

        :returns: identifier of newly created item
        """

        identifier, json_data = self._load_and_prepare_item(item)

        try:
            json_data['properties']['_metadata-anytext'] = ''.join([
                json_data['properties']['title'],
                json_data['properties']['description']
            ])
        except KeyError:
            LOGGER.debug('Missing title and description')
            json_data['properties']['_metadata_anytext'] = ''

        LOGGER.debug('Inserting data with identifier {}'.format(identifier))
        result = self.db.insert(json_data)

        LOGGER.debug('Item added with internal id {}'.format(result))

        return identifier

    def update(self, identifier, item):
        """
        Updates an existing item

        :param identifier: feature id
        :param item: `dict` of partial or full item

        :returns: `bool` of update result
        """

        LOGGER.debug('Updating item {}'.format(identifier))
        identifier, json_data = self._load_and_prepare_item(
            item, identifier, raise_if_exists=False)
        self.db.update(json_data, where('id') == identifier)

        return True

    def delete(self, identifier):
        """
        Deletes an existing item

        :param identifier: item id

        :returns: `bool` of deletion result
        """

        LOGGER.debug('Deleting item {}'.format(identifier))
        self.db.remove(where('id') == identifier)

        return True

    def _bbox(input_bbox, record_bbox):
        """
        Test whether one bbox intersects another

        :param input_bbox: `list` of minx,miny,maxx,maxy
        :param record_bbox: `list` of minx,miny,maxx,maxy

        :returns: `bool` of result
        """

        return True

    def __repr__(self):
        return '<TinyDBCatalogueProvider> {}'.format(self.data)


def bbox_intersects(record_bbox, input_bbox):
    """
    Manual bbox intersection calculation

    :param record_bbox: `dict` of polygon geometry
    :param input_bbox: `str` of 'minx,miny,maxx,maxy'

    :returns: `bool` of whether the record_bbox intersects input_bbox
    """

    bbox1 = record_bbox[0]
    bbox2 = [float(c) for c in input_bbox.split(',')]

    LOGGER.debug('Record bbox: {}'.format(bbox1))
    LOGGER.debug('Input bbox: {}'.format(bbox2))

    # any point in bbox1 should be in bbox2
    bbox_tests = [
        bbox2[0] <= bbox1[0] <= bbox2[2],
        bbox2[1] <= bbox1[1] <= bbox2[3],
        bbox2[0] <= bbox1[2] <= bbox2[2],
        bbox2[1] <= bbox1[3] <= bbox2[3]
    ]

    if any(bbox_tests):
        return True

    return False
