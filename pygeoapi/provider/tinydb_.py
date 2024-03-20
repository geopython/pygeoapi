# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2023 Tom Kralidis
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
import uuid

from shapely.geometry import shape
from tinydb import TinyDB, Query, where

from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
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

        LOGGER.debug(f'Connecting to TinyDB db at {self.data}')

        if not os.path.exists(self.data):
            msg = ('TinyDB file does not exist, please check '
                   'the path specified, or include the full '
                   'path to the file')
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
            if p not in self.excludes:
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
        LOGGER.debug(f'Query initiated: {Q}')

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
            QUERY.append(f"Q.geometry.test(bbox_intersects, '{bbox_as_string}')")  # noqa

        if datetime_ is not None:
            LOGGER.debug('processing datetime parameter')
            if self.time_field is None:
                LOGGER.error('time_field not enabled for collection')
                LOGGER.error('Using default time property')
                time_field2 = 'time'
            else:
                LOGGER.error(f'Using properties.{self.time_field}')
                time_field2 = f"properties['{self.time_field}']"

            if '/' in datetime_:  # envelope
                LOGGER.debug('detected time range')
                time_begin, time_end = datetime_.split('/')

                if time_begin != '..':
                    QUERY.append(f"(Q.{time_field2}>='{time_begin}')")  # noqa
                if time_end != '..':
                    QUERY.append(f"(Q.{time_field2}<='{time_end}')")  # noqa

            else:  # time instant
                LOGGER.debug('detected time instant')
                QUERY.append(f"(Q.{time_field2}=='{datetime_}')")  # noqa

        if properties:
            LOGGER.debug('processing properties')
            for prop in properties:
                QUERY.append(f"(Q.properties['{prop[0]}']=='{prop[1]}')")

        if q is not None:
            for t in q.split():
                QUERY.append(f"(Q.properties['_metadata-anytext'].search('{t}', flags=re.IGNORECASE))")  # noqa

        QUERY_STRING = '&'.join(QUERY)
        LOGGER.debug(f'QUERY_STRING: {QUERY_STRING}')
        SEARCH_STRING = f'self.db.search({QUERY_STRING})'
        LOGGER.debug(f'SEARCH_STRING: {SEARCH_STRING}')

        LOGGER.debug('querying database')
        if len(QUERY) > 0:
            LOGGER.debug(f'running eval on {SEARCH_STRING}')
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
                    LOGGER.debug(f'Missing excluded property {e}')

        len_results = len(results)

        LOGGER.debug(f'Results found: {len_results}')

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

        LOGGER.debug(f'Fetching identifier {identifier}')

        record = self.db.get(Query().id == identifier)

        if record is None:
            raise ProviderItemNotFoundError('record does not exist')

        for e in self.excludes:
            try:
                del record['properties'][e]
            except KeyError:
                LOGGER.debug(f'Missing excluded property {e}')

        return record

    def create(self, item):
        """
        Adds an item to the TinyDB repository

        :param item: item data

        :returns: identifier of newly created item
        """

        identifier, json_data = self._load_and_prepare_item(
            item, accept_missing_identifier=True)
        if identifier is None:
            # If there is no incoming identifier, allocate a random one
            identifier = str(uuid.uuid4())
            json_data["id"] = identifier

        try:
            json_data['properties']['_metadata-anytext'] = ''.join([
                json_data['properties']['title'],
                json_data['properties']['description']
            ])
        except KeyError:
            LOGGER.debug('Missing title and description')
            json_data['properties']['_metadata_anytext'] = ''

        LOGGER.debug(f'Inserting data with identifier {identifier}')
        result = self.db.insert(json_data)

        LOGGER.debug(f'Item added with internal id {result}')

        return identifier

    def update(self, identifier, item):
        """
        Updates an existing item

        :param identifier: feature id
        :param item: `dict` of partial or full item

        :returns: `bool` of update result
        """

        LOGGER.debug(f'Updating item {identifier}')
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

        LOGGER.debug(f'Deleting item {identifier}')
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
        return f'<TinyDBCatalogueProvider> {self.data}'


def bbox_intersects(record_geometry, input_bbox):
    """
    Manual bbox intersection calculation

    :param record_geometry: `dict` of polygon geometry
    :param input_bbox: `str` of 'minx,miny,maxx,maxy'

    :returns: `bool` of whether the record_bbox intersects input_bbox
    """

    bbox1 = list(shape(record_geometry).bounds)

    bbox2 = [float(c) for c in input_bbox.split(',')]

    LOGGER.debug(f'Record bbox: {bbox1}')
    LOGGER.debug(f'Input bbox: {bbox2}')

    bbox1_minx, bbox1_miny, bbox1_maxx, bbox1_maxy = bbox1
    bbox2_minx, bbox2_miny, bbox2_maxx, bbox2_maxy = bbox2

    return bbox1_minx <= bbox2_maxx and \
        bbox1_miny <= bbox2_maxy and \
        bbox2_minx <= bbox1_maxx and \
        bbox2_miny <= bbox1_maxy
