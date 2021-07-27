# =================================================================
#
# Authors: Jorge Samuel Mendes de Jesus <jorge.dejesus@protonmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#          Mary Bucknell <mbucknell@usgs.gov>
#
# Copyright (c) 2018 Jorge Samuel Mendes de Jesus
# Copyright (c) 2021 Tom Kralidis
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
    ProviderConnectionError, ProviderQueryError, ProviderItemNotFoundError

from psycopg2.extras import RealDictCursor

LOGGER = logging.getLogger(__name__)


class DatabaseConnection:
    """Database connection class to be used as 'with' statement.
     The class returns a connection object.
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
            search_path – search path to be used (by order) , normally
             data is in the public schema, [public],
             or in a specific schema ["osm", "public"].
             Note: First we should have the schema
             being used and then public

        :param table: table name containing the data. This variable is used to
                assemble column information
        :param context: query or hits, if query then it will determine
                table column otherwise will not do it
        :returns: psycopg2.extensions.connection
        """

        self.conn_dic = conn_dic
        self.table = table
        self.context = context
        self.columns = None
        self.fields = {}  # Dict of columns. Key is col name, value is type
        self.conn = None

    def __enter__(self):
        try:
            search_path = self.conn_dic.pop('search_path', ['public'])
            if search_path != ['public']:
                self.conn_dic["options"] = '-c \
                search_path={}'.format(",".join(search_path))
                LOGGER.debug('Using search path: {} '.format(search_path))
            self.conn = psycopg2.connect(**self.conn_dic)
            self.conn.set_client_encoding('utf8')

        except psycopg2.OperationalError:
            LOGGER.error("Couldn't connect to Postgis using:{}".format(
                str(self.conn_dic)))
            raise ProviderConnectionError()

        self.cur = self.conn.cursor()
        if self.context == 'query':
            # Getting columns
            query_cols = "SELECT column_name, udt_name FROM information_schema.columns \
            WHERE table_name = '{}' and udt_name != 'geometry';".format(
                self.table)

            self.cur.execute(query_cols)
            result = self.cur.fetchall()
            self.columns = SQL(', ').join(
                [Identifier(item[0]) for item in result]
                )

            for k, v in dict(result).items():
                self.fields[k] = {'type': v}

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

        :returns: pygeoapi.provider.base.PostgreSQLProvider
        """

        super().__init__(provider_def)

        self.table = provider_def['table']
        self.id_field = provider_def['id_field']
        self.conn_dic = provider_def['data']
        self.geom = provider_def.get('geom_field', 'geom')

        LOGGER.debug('Setting Postgresql properties:')
        LOGGER.debug('Connection String:{}'.format(
            ",".join(("{}={}".format(*i) for i in self.conn_dic.items()))))
        LOGGER.debug('Name:{}'.format(self.name))
        LOGGER.debug('ID_field:{}'.format(self.id_field))
        LOGGER.debug('Table:{}'.format(self.table))

        if "fields" in provider_def:
            LOGGER.debug('Using user-defined fields/properties')
            self.fields = {k: {'type': v} for k, v in provider_def['fields'].items()}
        else:
            LOGGER.debug('Get available fields/properties')
            self.get_fields()

    @property
    def columns(self):
        return SQL(', ').join(Identifier(k) for k in self.fields)

    def get_fields(self):
        """
        Get fields from PostgreSQL table (columns are field)

        :returns: dict of fields
        """
        if not self.fields:
            with DatabaseConnection(self.conn_dic, self.table) as db:
                self.fields = db.fields
        return self.fields

    def __get_where_clauses(self, properties=[], bbox=[]):
        """
        Generarates WHERE conditions to be implemented in query.
        Private method mainly associated with query method
        :param properties: list of tuples (name, value)
        :param bbox: bounding box [minx,miny,maxx,maxy]

        :returns: psycopg2.sql.Composed or psycopg2.sql.SQL
        """

        where_conditions = []
        if properties:
            property_clauses = [SQL('{} = {}').format(
                Identifier(k), Literal(v)) for k, v in properties]
            where_conditions += property_clauses
        if bbox:
            bbox_clause = SQL('{} && ST_MakeEnvelope({})').format(
                Identifier(self.geom), SQL(', ').join(
                    [Literal(bbox_coord) for bbox_coord in bbox]))
            where_conditions.append(bbox_clause)

        if where_conditions:
            where_clause = SQL(' WHERE {}').format(
                SQL(' AND ').join(where_conditions))
        else:
            where_clause = SQL('')

        return where_clause

    def query(self, startindex=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, **kwargs):
        """
        Query Postgis for all the content.
        e,g: http://localhost:5000/collections/hotosm_bdi_waterways/items?
        limit=1&resulttype=results

        :param startindex: starting record to return (default 0)
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
        LOGGER.debug('Querying PostGIS')

        if resulttype == 'hits':

            with DatabaseConnection(self.conn_dic,
                                    self.table, context="hits") as db:
                cursor = db.conn.cursor(cursor_factory=RealDictCursor)

                where_clause = self.__get_where_clauses(
                    properties=properties, bbox=bbox)
                sql_query = SQL("SELECT COUNT(*) as hits from {} {}").\
                    format(Identifier(self.table), where_clause)
                try:
                    cursor.execute(sql_query)
                except Exception as err:
                    LOGGER.error('Error executing sql_query: {}: {}'.format(
                        sql_query.as_string(cursor), err))
                    raise ProviderQueryError()

                hits = cursor.fetchone()["hits"]

            return self.__response_feature_hits(hits)

        end_index = startindex + limit

        with DatabaseConnection(self.conn_dic, self.table) as db:
            cursor = db.conn.cursor(cursor_factory=RealDictCursor)

            where_clause = self.__get_where_clauses(
                properties=properties, bbox=bbox)

            sql_query = SQL("DECLARE \"geo_cursor\" CURSOR FOR \
             SELECT DISTINCT {},ST_AsGeoJSON({}) FROM {}{}").\
                format(self.columns,
                       Identifier(self.geom),
                       Identifier(self.table),
                       where_clause)

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

    def get_previous(self, cursor, identifier):
        """
        Query previous ID given current ID

        :param identifier: feature id

        :returns: feature id
        """
        sql = 'SELECT {} AS id FROM {} WHERE {}<%s ORDER BY {} DESC LIMIT 1'
        cursor.execute(SQL(sql).format(
            Identifier(self.id_field),
            Identifier(self.table),
            Identifier(self.id_field),
            Identifier(self.id_field),
        ), (identifier,))
        item = cursor.fetchall()
        id_ = item[0]['id'] if item else identifier
        return id_

    def get_next(self, cursor, identifier):
        """
        Query next ID given current ID

        :param identifier: feature id

        :returns: feature id
        """
        sql = 'SELECT {} AS id FROM {} WHERE {}>%s ORDER BY {} LIMIT 1'
        cursor.execute(SQL(sql).format(
            Identifier(self.id_field),
            Identifier(self.table),
            Identifier(self.id_field),
            Identifier(self.id_field),
        ), (identifier,))
        item = cursor.fetchall()
        id_ = item[0]['id'] if item else identifier
        return id_

    def get(self, identifier, **kwargs):
        """
        Query the provider for a specific
        feature id e.g: /collections/hotosm_bdi_waterways/items/13990765

        :param identifier: feature id

        :returns: GeoJSON FeaturesCollection
        """

        LOGGER.debug('Get item from Postgis')
        with DatabaseConnection(self.conn_dic, self.table) as db:
            cursor = db.conn.cursor(cursor_factory=RealDictCursor)

            sql_query = SQL("SELECT {},ST_AsGeoJSON({}) \
            from {} WHERE {}=%s").format(self.columns,
                                         Identifier(self.geom),
                                         Identifier(self.table),
                                         Identifier(self.id_field))

            LOGGER.debug('SQL Query: {}'.format(sql_query.as_string(db.conn)))
            LOGGER.debug('Identifier: {}'.format(identifier))
            try:
                cursor.execute(sql_query, (identifier, ))
            except Exception as err:
                LOGGER.error('Error executing sql_query: {}'.format(
                    sql_query.as_string(cursor)))
                LOGGER.error(err)
                raise ProviderQueryError()

            results = cursor.fetchall()
            row_data = None
            if results:
                row_data = results[0]
            feature = self.__response_feature(row_data)

            if feature:
                feature['prev'] = self.get_previous(cursor, identifier)
                feature['next'] = self.get_next(cursor, identifier)
                return feature
            else:
                err = 'item {} not found'.format(identifier)
                LOGGER.error(err)
                raise ProviderItemNotFoundError(err)

    def __response_feature(self, row_data):
        """
        Assembles GeoJSON output from DB query

        :param row_data: DB row result

        :returns: `dict` of GeoJSON Feature
        """

        if row_data:
            rd = dict(row_data)
            feature = {
                'type': 'Feature'
            }

            geom = rd.pop('st_asgeojson')

            feature['geometry'] = json.loads(geom) if geom is not None else None  # noqa

            feature['properties'] = rd
            feature['id'] = feature['properties'].get(self.id_field)

            return feature
        else:
            return None

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
