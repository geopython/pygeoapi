# =================================================================
#
# Authors: Jorge Samuel Mendes de Jesus <jorge.dejesus@protonmail.com>
#
# Copyright (c) 2018 Jorge Samuel Mendes de Jesus
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
# -v postgres_data:/var/lib/postgresql -p 25432:5432 \
# -e ALLOW_IP_RANGE=0.0.0.0/0 \
# -e POSTGRES_USER=postgres \
# -e POSTGRES_PASS=postgres \
# -e POSTGRES_DBNAME=test \
# -d -t kartoza/postgis

# Import dump:
# gunzip < tests/data/hotosm_bdi_waterways.sql.gz |
#  psql -U postgres -h 127.0.0.1 -p 25432 test

import logging
import json
import psycopg2
from psycopg2.sql import SQL, Identifier
from pygeoapi.provider.base import BaseProvider
from psycopg2.extras import RealDictCursor

LOGGER = logging.getLogger(__name__)


class DatabaseConnection(object):
    """Database connection class to be use as a with statement
    Returning a connection object is better than a cursor, since
     using with will be responsible for naming the cursor
    """

    def __init__(self, conn_dic, table, context="query"):
        """
        PostgreSQLProvider Class constructor returning

        :param conn: dictionary with connection parameters
                    to be used by psycopg2
            dbname – the database name (database is a deprecated alias)
            user – user name used to authenticate
            password – password used to authenticate
            host – database host address
             (defaults to UNIX socket if not provided)
            port – connection port number
             (defaults to 5432 if not provided)

        :param table: table name containind data. This variable is used to
                assemble column information
        :param context: query or hits, if query then it will determine
                table column otherwise will not do it
        :returns: psycopg2.extensions.connection
        """

        self.conn_dic = conn_dic
        self.table = table
        self.context = context
        self.columns = None
        self.conn = None

    def __enter__(self):
        self.conn = psycopg2.connect(**self.conn_dic)
        self.cur = self.conn.cursor()
        if self.context == 'query':
            # Getting columns
            query_cols = "SELECT column_name FROM information_schema.columns \
            WHERE table_name = '{}' and udt_name != 'geometry';".format(
                self.table)

            self.cur.execute(query_cols)
            result = self.cur.fetchall()
            self.columns = SQL(', ').join(
                [Identifier(item[0]) for item in result]
                )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # some logic to commit/rollback
        self.conn.close()


class PostgreSQLProvider(BaseProvider):
    """Generic provider for Postgresql based on psycopg2
    using sync approach and server side
    cursor (using support class DatabaseCursor)
    """

    def __init__(self, provider_def):
        """
        PostgreSQLProvider Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class
                             data contains the connection information
                             for class DatabaseCursor

        :returns: pygeoapi.providers.base.PostgreSQLProvider
        """

        BaseProvider.__init__(self, provider_def)

        self.table = provider_def['table']
        self.id_field = provider_def['id_field']
        self.conn_dic = provider_def['data']

        LOGGER.debug('Setting Postgresql properties:')
        LOGGER.debug('Connection String:{}'.format(
            ",".join(("{}={}".format(*i) for i in self.conn_dic.items()))))
        LOGGER.debug('Name:{}'.format(self.name))
        LOGGER.debug('ID_field:{}'.format(self.id_field))
        LOGGER.debug('Table:{}'.format(self.table))

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], time=None, properties=[]):
        """
        Query Postgis for all the content.
        e,g: http://localhost:5000/collections/hotosm_bdi_waterways/items?
        limit=1&resulttype=results

        :param startindex: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param time: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)

        :returns: GeoJSON FeaturesCollection
        """
        LOGGER.debug('Querying PostGIS')

        if resulttype == 'hits':

            with DatabaseConnection(self.conn_dic,
                                    self.table, context="hits") as db:
                cursor = db.conn.cursor(cursor_factory=RealDictCursor)
                sql_query = SQL("select count(*) as hits from {}").\
                    format(Identifier(self.table))
                cursor.execute(sql_query)
                hits = cursor.fetchone()["hits"]

            return self.__response_feature_hits(hits)

        end_index = startindex + limit

        with DatabaseConnection(self.conn_dic, self.table) as db:
            cursor = db.conn.cursor(cursor_factory=RealDictCursor)
            sql_query = SQL("DECLARE \"geo_cursor\" CURSOR FOR \
             SELECT {0},ST_AsGeoJSON({1}) FROM {2}").\
                format(db.columns,
                       Identifier('geom'),
                       Identifier(self.table))

            LOGGER.debug('SQL Query:{}'.format(sql_query))
            LOGGER.debug('Start Index:{}'.format(startindex))
            LOGGER.debug('End Index'.format(end_index))

            cursor.execute(sql_query)

            for index in [startindex, limit]:
                cursor.execute("fetch forward {} from geo_cursor"
                               .format(index))

            self.dataDB = cursor.fetchall()
            feature_collection = self.__response_feature_collection()
            return feature_collection

    def get(self, identifier):
        """
        Query the provider for a specific
        feature id e.g: /collections/hotosm_bdi_waterways/items/25469515

        :param identifier: feature id

        :returns: GeoJSON FeaturesCollection
        """

        LOGGER.debug('Get item from Postgis')
        with DatabaseConnection(self.conn_dic, self.table) as db:
            cursor = db.conn.cursor(cursor_factory=RealDictCursor)
            sql_query = SQL("select {0},ST_AsGeoJSON({1}) \
            from {2} WHERE {3}=%s").format(db.columns,
                                           Identifier('geom'),
                                           Identifier(self.table),
                                           Identifier(self.id_field))

            LOGGER.debug('SQL Query:{}'.format(sql_query.as_string(db.conn)))
            LOGGER.debug('Identifier:{}'.format(identifier))

            cursor.execute(sql_query, (identifier, ))
            self.dataDB = cursor.fetchall()
            feature_collection = self.__response_feature_collection()
            return feature_collection

    def __response_feature_collection(self):
        """Assembles GeoJSON output from DB query

        :returns: GeoJSON FeaturesCollection
        """

        feature_list = list()
        for row_data in self.dataDB:
            row_data = dict(row_data)
            feature = {
                'type': 'Feature'
            }
            feature["geometry"] = json.loads(
                row_data.pop('st_asgeojson')
                )
            feature['properties'] = row_data
            feature['id'] = feature['properties'].pop(self.id_field)
            feature_list.append(feature)

        feature_collection = {
            'type': 'FeatureCollection',
            'features': feature_list
        }

        return feature_collection

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
