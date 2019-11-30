# =================================================================
#
# Authors: Jorge Samuel Mendes de Jesus <jorge.dejesus@protonmail.net>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2018 Jorge Samuel Mendes de Jesus
# Copyright (c) 2019 Tom Kralidis
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

import sqlite3
import logging
import os
import json
from pygeoapi.plugin import InvalidPluginError
from pygeoapi.provider.base import BaseProvider, ProviderConnectionError

LOGGER = logging.getLogger(__name__)


class SQLiteProvider(BaseProvider):
    """Generic provider for SQLITE using sqlite3 module.
    This module requires install of libsqlite3-mod-spatialite
    TODO: DELETE, UPDATE, CREATE
    """

    def __init__(self, provider_def):
        """
        SQLiteProvider Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class

        :returns: pygeoapi.providers.base.SQLiteProvider
        """
        BaseProvider.__init__(self, provider_def)

        self.table = provider_def['table']

        LOGGER.debug('Setting SQLite properties:')
        LOGGER.debug(f'Data source: {self.data}')
        LOGGER.debug(f'Name: {self.name}')
        LOGGER.debug(f'ID_field: {self.id_field}')
        LOGGER.debug(f'Table: {self.table}')
        
        LOGGER.debug('Get available fields/properties')
        self.get_fields()

    def get_fields(self):
        """
         Get fields from sqlite table (columns are field) 
        
        :returns: dict of fields
        """
        # get_fields as a method decorator? 
        if not self.fields:
            cursor = self.__load()
            results = cursor.execute(f'PRAGMA table_info({self.table})').fetchall()
            [self.fields.update({ item["name"]:item["type"].lower()}) for item in results]
        return self.fields



    def __response_feature(self, row_data):
        """
        Assembles GeoJSON output from DB query

        :param row_data: DB row result

        :returns: `dict` of GeoJSON Feature
        """

        rd = dict(row_data)  # sqlite3.Row is doesnt support pop
        feature = {
            'type': 'Feature'
        }
        feature["geometry"] = json.loads(
            rd.pop('AsGeoJSON(geometry)')
            )
        feature['properties'] = rd
        feature['id'] = feature['properties'].pop(self.id_field)

        return feature

    def __response_feature_hits(self, hits):
        """Assembles GeoJSON/Feature number

        :returns: GeoJSON FeaturesCollection
        """

        feature_collection = {"features": [],
                              "type": "FeatureCollection"}
        feature_collection['numberMatched'] = hits

        return feature_collection

    def __load(self):
        """
        Private method for loading spatiallite,
        get the table structure and dump geometry

        :returns: sqlite3.Cursor
        """

        if (os.path.exists(self.data)):
            conn = sqlite3.connect(self.data)
        else:
            LOGGER.error('Path to sqlite does not exist')
            raise InvalidPluginError()

        try:
            conn.enable_load_extension(True)
        except AttributeError as err:
            LOGGER.error(f'Extension loading not enabled: {err}')
            raise ProviderConnectionError()

        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT load_extension('mod_spatialite.so')")
            cursor.execute(f'PRAGMA table_info({self.table})')
        except sqlite3.OperationalError as err:
            LOGGER.error(f'Extension loading error: {err}')
            raise ProviderConnectionError()
        result = cursor.fetchall()
        try:
            assert len(result), 'Table not found'
            assert len([item for item in result
                        if item['pk'] == 1]), 'Primary key not found'
            assert len([item for item in result
                        if self.id_field in item]), 'id_field not present'
            assert len([item for item in result
                        if 'GEOMETRY' in item]), 'GEOMETRY column not found'

        except AssertionError:
            raise InvalidPluginError

        self.columns = [item[1] for item in result if item[1] != 'GEOMETRY']
        self.columns = ','.join(self.columns)+',AsGeoJSON(geometry)'

        return cursor

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime=None, properties=[], sortby=[]):
        """
        Query SQLite for all the content.
        e,g: http://localhost:5000/collections/countries/items?
        limit=5&startindex=2&resulttype=results&continent=Europe&admin=Albania

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)

        :returns: GeoJSON FeaturesCollection
        """
        LOGGER.debug('Querying SQLite')

        cursor = self.__load()

        LOGGER.debug('Got cursor from DB')

        if resulttype == 'hits':
            res = cursor.execute(f"select count(*) as hits from {self.table};")

            hits = res.fetchone()["hits"]
            return self.__response_feature_hits(hits)


        where_syntax = ""
        where_values = tuple()
        if properties:
            where_syntax = " where "
            where_syntax += " and ".join([f"{k}=?" for k,v in properties])
        
            where_values += where_values + tuple((v for k,v in properties)) 
        
        sql_query = f"select {self.columns} from {self.table} {where_syntax} limit ? offset ?"
        end_index = startindex + limit
        
        LOGGER.debug(f'SQL Query: {sql_query}')
        LOGGER.debug(f'Start Index: {startindex}')
        LOGGER.debug(f'End Index: {end_index}')
        
        row_data = cursor.execute(sql_query, where_values + (limit, startindex))
        
        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        for rd in row_data:
            feature_collection['features'].append(
                self.__response_feature(rd))

        return feature_collection

    def get(self, identifier):
        """
        Query the provider for a specific
        feature id e.g: /collections/countries/items/1

        :param identifier: feature id

        :returns: GeoJSON FeaturesCollection
        """

        LOGGER.debug('Get item from SQLite')

        cursor = self.__load()

        LOGGER.debug('Got cursor from DB')

        sql_query = f'select {self.columns} from {self.table} where {self.id_field}==?;'

        LOGGER.debug(f'SQL Query: {sql_query}')
        LOGGER.debug(f'Identifier: {identifier}')

        row_data = cursor.execute(sql_query, (identifier, )).fetchone()

        feature = self.__response_feature(row_data)
        return feature

    def __repr__(self):
        return f'<SQLiteProvider> {self.data}, {self.table}'
