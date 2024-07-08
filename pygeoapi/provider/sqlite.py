# =================================================================
#
# Authors: Jorge Samuel Mendes de Jesus <jorge.dejesus@protonmail.net>
#          Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2018 Jorge Samuel Mendes de Jesus
# Copyright (c) 2023 Tom Kralidis
# Copyright (c) 2020 Francesco Bartoli
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
from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
                                    ProviderItemNotFoundError)
from pygeoapi.util import crs_transform

LOGGER = logging.getLogger(__name__)


SPATIALITE_EXTENSION = os.getenv('SPATIALITE_LIBRARY_PATH',
                                 'mod_spatialite.so')


class SQLiteGPKGProvider(BaseProvider):
    """Generic provider for SQLITE and GPKG using sqlite3 module.
    This module requires install of libsqlite3-mod-spatialite
    TODO: DELETE, UPDATE, CREATE
    """

    def __init__(self, provider_def):
        """
        SQLiteGPKGProvider Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class

        :returns: pygeoapi.provider.base.SQLiteProvider
        """
        super().__init__(provider_def)

        self.table = provider_def['table']
        self.application_id = None
        self.geom_col = None

        LOGGER.debug('Setting SQLite properties:')
        LOGGER.debug(f'Data source: {self.data}')
        LOGGER.debug(f'Name: {self.name}')
        LOGGER.debug(f'ID_field: {self.id_field}')
        LOGGER.debug(f'Table: {self.table}')

        self.cursor = self.__load()

        LOGGER.debug('Got cursor from DB')
        LOGGER.debug('Get available fields/properties')

        self.get_fields()

    def get_fields(self):
        """
         Get fields from sqlite table (columns are field)

        :returns: dict of fields
        """

        if not self.fields:
            results = self.cursor.execute(
                f'PRAGMA table_info({self.table})').fetchall()
            for item in results:
                json_type = None

                if item['type'] in ['INTEGER', 'REAL']:
                    json_type = 'number'
                elif item['type'].startswith('TEXT') or item['type'] == 'BLOB':
                    json_type = 'string'

                if json_type is not None:
                    self.fields[item['name']] = {'type': json_type}

        return self.fields

    def __get_where_clauses(self, properties=[], bbox=[]):
        """
        Generarates WHERE conditions to be implemented in query.
        Private method mainly associated with query method.

        Method returns part of the SQL query, plus tuple to be used
        in the sqlite query method

        :param properties: list of tuples (name, value)
        :param bbox: bounding box [minx,miny,maxx,maxy]

        :returns: str, tuple
        """

        where_values = tuple()
        where_clause = " WHERE " if (properties or bbox) else ""
        if not where_clause:
            return where_clause, where_values

        if properties:
            where_clause += " AND ".join(
                [f"{k}=?" for k, v in properties])
            where_values += where_values + tuple((v for k, v in properties))

        if bbox:
            if properties:
                where_clause += " AND "
            where_clause += f" Intersects({self.geom_col}, BuildMbr(?,?,?,?)) "
            where_values += tuple(bbox)
        # WHERE continent=? <class 'tuple'>: ('Europe',)
        return where_clause, where_values

    def __response_feature(self, row_data, skip_geometry=False):
        """
        Assembles GeoJSON output from DB query

        :param row_data: DB row result
        :param skip_geometry: whether to skip geometry (default False)

        :returns: `dict` of GeoJSON Feature
        """

        if row_data:
            rd = dict(row_data)  # sqlite3.Row is doesnt support pop
            feature = {
                'type': 'Feature',
                'geometry': None
            }

            try:
                if not skip_geometry:
                    feature['geometry'] = json.loads(
                        rd.pop(f'AsGeoJSON({self.geom_col})')
                    )
            except TypeError:
                LOGGER.warning('Missing geometry')

            feature['properties'] = rd
            feature['id'] = feature['properties'].pop(self.id_field)

            return feature
        else:
            return None

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
        # conn.set_trace_callback(LOGGER.debug)
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT load_extension('{SPATIALITE_EXTENSION}')")
        except sqlite3.OperationalError as err:
            LOGGER.error(f'Extension loading error: {err}')
            raise ProviderConnectionError()
        result = cursor.fetchall()

        # Checking for geopackage
        cursor.execute("PRAGMA application_id")
        result = cursor.fetchone()

        self.application_id = result["application_id"]
        if self.application_id == 1196444487:
            LOGGER.info("Detected GPKG 1.2 and greater")
        elif self.application_id == 1196437808:
            LOGGER.info("Detected GPKG 1.0 or 1.1")
        else:
            LOGGER.info("No GPKG detected assuming spatial sqlite3")
            self.application_id = 0

        if self.application_id:
            geometry_columns_table = 'gpkg_geometry_columns'
            geometry_columns_table_name = 'table_name'
            geometry_columns_column_name = 'column_name'
            cursor.execute("SELECT AutoGPKGStart()")
            result = cursor.fetchall()
            if result[0][0] >= 1:
                LOGGER.info("Loaded Geopackage support")
            else:
                LOGGER.info("SELECT AutoGPKGStart() returned 0." +
                            "Detected GPKG but couldn't load support")
                raise InvalidPluginError()
        else:
            geometry_columns_table = 'geometry_columns'
            geometry_columns_column_name = 'f_geometry_column'
            geometry_columns_table_name = 'f_table_name'

        try:
            cursor.execute(f'PRAGMA table_info({self.table})')
            result = cursor.fetchall()
        except sqlite3.OperationalError:
            LOGGER.error(f'Could not find table: {self.table}')
            raise ProviderConnectionError()

        LOGGER.debug('Determining name of geometry column')
        cursor.execute(f"SELECT {geometry_columns_column_name} FROM {geometry_columns_table} WHERE {geometry_columns_table_name} = '{self.table}'")  # noqa
        geometry_column = cursor.fetchall()

        if geometry_column:
            LOGGER.debug("Found geometry column")
            self.geom_col = geometry_column[0][0]
        else:
            msg = 'No geometry column found'
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

        try:
            assert len(result), 'Table not found'
            assert len([item for item in result
                        if self.id_field in item]), 'id_field not present'
        except AssertionError:
            raise InvalidPluginError()

        self.columns = [item[1] for item in result if item[1]
                        not in [self.geom_col, self.geom_col.upper()]]
        self.columns = ','.join(self.columns)+f',AsGeoJSON({self.geom_col})'

        if self.application_id:
            self.table = f"vgpkg_{self.table}"

        return cursor

    @crs_transform
    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, **kwargs):
        """
        Query SQLite/GPKG for all the content.
        e,g: http://localhost:5000/collections/countries/items?
        limit=5&offset=2&resulttype=results&continent=Europe&admin=Albania&bbox=29.3373,-3.4099,29.3761,-3.3924
        http://localhost:5000/collections/countries/items?continent=Africa&bbox=29.3373,-3.4099,29.3761,-3.3924

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

        :returns: GeoJSON FeaturesCollection
        """
        LOGGER.debug('Querying SQLite/GPKG')

        where_clause, where_values = self.__get_where_clauses(
            properties=properties, bbox=bbox)

        if resulttype == 'hits':

            sql_query = f"SELECT COUNT(*) as hits FROM {self.table} {where_clause} "  # noqa

            res = self.cursor.execute(sql_query, where_values)

            hits = res.fetchone()["hits"]
            return self.__response_feature_hits(hits)

        sql_query = f"SELECT DISTINCT {self.columns} from \
            {self.table} {where_clause} limit ? offset ?"

        end_index = offset + limit

        LOGGER.debug(f'SQL Query: {sql_query}')
        LOGGER.debug(f'Start Index: {offset}')
        LOGGER.debug(f'End Index: {end_index}')

        row_data = self.cursor.execute(
            sql_query, where_values + (limit, offset))

        feature_collection = {
            'type': 'FeatureCollection',
            'features': []
        }

        for rd in row_data:
            feature_collection['features'].append(
                self.__response_feature(rd, skip_geometry=skip_geometry))

        return feature_collection

    @crs_transform
    def get(self, identifier, **kwargs):
        """
        Query the provider for a specific
        feature id e.g: /collections/countries/items/1

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """

        LOGGER.debug('Get item from SQLite/GPKG')

        sql_query = f'SELECT {self.columns} FROM \
            {self.table} WHERE {self.id_field}==?;'

        LOGGER.debug(f'SQL Query: {sql_query}')
        LOGGER.debug(f'Identifier: {identifier}')

        row_data = self.cursor.execute(sql_query, (identifier, )).fetchone()

        feature = self.__response_feature(row_data)
        if feature:
            return feature
        else:
            err = f'item {identifier} not found'
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

    def __repr__(self):
        return f'<SQLiteGPKGProvider> {self.data}, {self.table}'
