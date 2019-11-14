# =================================================================
#
# Authors: Jorge Samuel Mendes de Jesus <jorge.dejesus@protonmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#          Mary Bucknell <mbucknell@usgs.gov>
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

# Testing local docker:
# docker run --name "postgis" \
# -v postgres_data:/var/lib/postgresql -p 5432:5432 \
# -e ALLOW_IP_RANGE=0.0.0.0/0 \
# -e POSTGRES_USER=postgres \
# -e POSTGRES_PASS=postgres \
# -e POSTGRES_DBNAME=test \
# -d -t kartoza/postgis

# Import dump:
# gunzip < tests/data/hotosm_bdi_waterways.sql.gz |
#  psql -U postgres -h 127.0.0.1 -p 5432 test

import logging
import json
import psycopg2
from psycopg2.sql import SQL, Identifier, Literal
from pygeoapi.provider.base import BaseProvider, \
    ProviderConnectionError, ProviderQueryError

from psycopg2.extras import RealDictCursor

LOGGER = logging.getLogger(__name__)


class DatabaseConnection(object):
    """Database connection class to be used as 'with' statement.
     The class returns a connection object.
    """

    def __init__(self, conn_dic, columns):
        """
        PostgreSQLProvider Class constructor returning
        :param conn_dic: dictionary with connection parameters
                    to be used by psycopg2
            dbname – the database name (database is a deprecated alias)
            user – user name used to authenticate
            password – password used to authenticate
            host – database host address
             (defaults to UNIX socket if not provided)
            port – connection port number
             (defaults to 5432 if not provided)
            search_path – search path to be used (by order) , normally
             data is in the public schema, [public],
             or in a specific schema ["osm", "public"].
             Note: First we should have the schema
             being used and then public
        :returns: psycopg2.extensions.connection
        """

        self.conn_dic = conn_dic
        self.conn = None

    def __enter__(self):
        try:
            search_path = self.conn_dic.pop('search_path', ['public'])
            if search_path != ['public']:
                self.conn_dic["options"] = f'-c \
                search_path={",".join(search_path)}'
                LOGGER.debug(f'Using search path: {search_path} ')
            self.conn = psycopg2.connect(**self.conn_dic)

        except psycopg2.OperationalError:
            LOGGER.error(f'Couldn\'t connect to Postgis using: {self.conn_dic!s}')
            raise ProviderConnectionError()

        self.cur = self.conn.cursor()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # some logic to commit/rollback
        self.conn.close()


class PostgreSQLQueryProvider(BaseProvider):
    """Generic provider for Postgresql based on psycopg2
    using sync approach and server side
    cursor (using support class DatabaseCursor)
    """

    ## TODO: think about SQL injection and how to sanitize the query config parameter

    def __init__(self, provider_def):
        """
        PostgreSQLProvider Class constructor
        :param provider_def: provider definitions from yml pygeoapi-config.
                             data, name, id_field and query set in parent class
                             data contains the connection information
                             for class DatabaseCursor
        :returns: pygeoapi.providers.base.PostgreSQLProvider
        """

        BaseProvider.__init__(self, provider_def)

        self.name = provider_def['name']
        self.query_table = provider_def['query_table']
        self.id_field = provider_def['id_field']
        self.conn_dic = provider_def['data']
        self.geom = provider_def.get('geom_field', 'geom')
        self.columns_to_properties = provider_def.get('column_property_mapping');
        self.columns = SQL(', ').join(
            [SQL('{} {}').format(Identifier(col), Identifier(prop))
             for (col, prop) in self.columns_to_properties.items()])
        self.properties_to_cols = dict(zip(self.columns_to_properties.values(), self.columns_to_properties.keys()))

        LOGGER.debug('Setting Postgresql properties:')
        LOGGER.debug('Connection String:{}'.format(
            ",".join(("{}={}".format(*i) for i in self.conn_dic.items()))))
        LOGGER.debug('Name:{}'.format(self.name))
        LOGGER.debug('ID_field:{}'.format(self.id_field))
        LOGGER.debug('Query:{}'.format(self.query_table))

        LOGGER.debug('Get available fields/properties')
        self.get_fields()

    def get_fields(self):
        if not self.fields:
            self.fields = dict((v, '') for v in self.properties_to_cols.keys())
        return self.fields

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime=None, properties=[], sortby=[]):
        """
        Query Postgis for all the content.
        e,g: http://localhost:5000/collections/hotosm_bdi_waterways/items?
        limit=1&resulttype=results
        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :returns: GeoJSON FeaturesCollection
        """
        LOGGER.debug('Querying PostGIS')
        if resulttype == 'hits':
            select_clause = SQL('SELECT count(*) as hits')
        else:
            select_clause = SQL('SELECT {}, ST_AsGeoJSON({})').format(
                self.columns, Identifier(self.geom))

        where_conditions = []
        if properties:
            property_clauses = \
                [SQL('{} = {}').format(
                    Identifier(k), Literal(v)) for k, v in properties]
            where_conditions += property_clauses
        if bbox:
            bbox_clause = SQL('{} && ST_MakeEnvelope({})').format(
                Identifier(self.geom),
                SQL(', ').join(
                    [Literal(bbox_coord) for bbox_coord in bbox]
                )
            )
            where_conditions.append(bbox_clause)

        if where_conditions:
            where_clause = SQL(' WHERE {}').format(
                SQL(' AND ').join(where_conditions)
            )
        else:
            where_clause = SQL('')

        if resulttype == 'hits':
            with DatabaseConnection(self.conn_dic,
                                    self.columns, context="hits") as db:
                cursor = db.conn.cursor(cursor_factory=RealDictCursor)
                sql_query = SQL("{} FROM {}{}").format(select_clause,
                                                       SQL(self.query_table),
                                                       where_clause)
                try:
                    cursor.execute(sql_query)
                except Exception as err:
                    LOGGER.error('Error executing sql_query: {}: {}'.format(
                        sql_query.as_string(cursor)), err)
                    raise ProviderQueryError()

                hits = cursor.fetchone()["hits"]

            return self.__response_feature_hits(hits)
        else:
            end_index = startindex + limit

            with DatabaseConnection(self.conn_dic, self.columns) as db:
                cursor = db.conn.cursor(cursor_factory=RealDictCursor)
                sql_query = SQL(
                "DECLARE \"geo_cursor\" CURSOR FOR {} FROM {} {}"
                ).format(select_clause, SQL(self.query_table), where_clause)

                LOGGER.debug('SQL Query: {}'.format(sql_query.as_string(cursor)))
                LOGGER.debug('Start Index: {}'.format(startindex))
                LOGGER.debug('End Index: {}'.format(end_index))
                try:
                    cursor.execute(sql_query)
                    for index in [startindex, limit]:
                        cursor.execute("fetch forward {} from geo_cursor"
                                       .format(index))
                except Exception as err:
                    LOGGER.error('Error executing sql_query: {}'.format(
                        sql_query.as_string(cursor)))
                    LOGGER.error(err)
                    raise ProviderQueryError()

                row_data = cursor.fetchall()

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
        feature id e.g: /collections/hotosm_bdi_waterways/items/13990765
        :param identifier: feature id
        :returns: GeoJSON FeaturesCollection
        """

        LOGGER.debug('Get item from Postgis')
        with DatabaseConnection(self.conn_dic, self.columns) as db:
            cursor = db.conn.cursor(cursor_factory=RealDictCursor)

            sql_query = SQL("SELECT {}, ST_AsGeoJSON({})  FROM {} WHERE {}=%s").format(
                self.columns, Identifier(self.geom), SQL(self.query_table), Identifier(self.id_field))

            #sql_query = SQL("select {0},ST_AsGeoJSON({1}) \
            #from {2} WHERE {3}=%s").format(db.columns,
            #                               Identifier(self.geom),
            #                               Identifier(self.table),
            #                               Identifier(self.id_field))

            LOGGER.debug('SQL Query: {}'.format(sql_query.as_string(db.conn)))
            LOGGER.debug('Identifier: {}'.format(identifier))
            try:
                cursor.execute(sql_query, (identifier, ))
            except Exception as err:
                LOGGER.error('Error executing sql_query: {}'.format(
                    sql_query.as_string(cursor)))
                LOGGER.error(err)
                raise ProviderQueryError()

            row_data = cursor.fetchall()[0]
        feature = self.__response_feature(row_data)

        return feature

    def __response_feature(self, row_data):
        """
        Assembles GeoJSON output from DB query
        :param row_data: DB row result
        :returns: `dict` of GeoJSON Feature
        """

        rd = dict(row_data)
        feature = {
            'type': 'Feature'
        }
        feature["geometry"] = json.loads(
            rd.pop('st_asgeojson'))

        feature['properties'] = rd
        feature['id'] = rd.pop(self.columns_to_properties.get(self.id_field))

        return feature

    def __response_feature_hits(self, hits):
        """Assembles GeoJSON/Feature number
        e.g: http://localhost:5000/collections/
        hotosm_bdi_waterways/items?resulttype=hits
        :returns: GeoJSON FeaturesCollection
        """

        feature_collection = {"features": [],
                              "type": "FeatureCollection"}
        feature_collection['numberMatched'] = hits

        return feature_collection