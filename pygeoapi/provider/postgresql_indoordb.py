import json
import datetime
import psycopg2
from functools import partial
from dateutil.parser import parse as dateparse
import pytz
from IndoorGML_API.pygeoapi.process.manager import postgresql
from pymeos import (Temporal, TFloatSeq, TFloatSeqSet, pymeos_initialize)
from pygeoapi.util import format_datetime
from pymeos_cffi import (tfloat_from_mfjson, ttext_from_mfjson,
                         tgeompoint_from_mfjson)

class PostgresIndoorDB:
    host= 'localhost'
    port= 5432
    dbname = 'indoordb'
    user= 'user'
    password= 'password'
    connection = None

    def __init__(self, datasource=None):
        """
        PostgresIndoorDB Class Constructor

        Initializes the connection settings.
        Allows overriding defaults via a dictionary if needed.

         :param datasource: datasource definition (default None)
            host - database host address
            port - connection port number
            db - table name
            user - user name used to authenticate
            password - password used to authenticate
        """
        if datasource is not None:
            self.host = datasource.get('host', self.host)
            self.port = datasource.get('port', self.port)
            self.dbname = datasource.get('dbname', self.dbname)
            self.user = datasource.get('user', self.user)
            self.password = datasource.get('password', self.password)
    
    def connect(self):
        """
        Establish a connection to the PostgreSQL database.
        """
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password
            )
        except Exception as e:
            print(f"Error connecting to database: {e}")
    
    def disconnect(self):
        """
        Close the connection to the PostgreSQL database.
        """
        if self.connection is not None:
            self.connection.close()

    def get_collections_list(self):
        """
        Query indoor features collection list
        GET /collections

        :returns: JSON FeatureCollection
        """
        with self.connection.cursor() as cur:
            select_query = "SELECT collection_id FROM collection"
            cur.execute(select_query)
            result = cur.fetchall()
        return result

    def get_collections(self):
        """
        Query indoor features collections

        :returns: JSON FeatureCollections
        """
        with self.connection.cursor() as cur:
            select_query = """TODO """

            cur.execute(select_query)
            result = cur.fetchall()
        return result

    def get_collection(self, collection_id):
        """
        Query specific indoor features collection
        GET /collections/{collectionId}

        :param collection_id: local identifier of a collection

        :returns: JSON FeatureCollection
        """
        with self.connection.cursor() as cur:
            select_query = ("""TODO""")

            cur.execute(select_query)
            result = cur.fetchall()
        return result

    def get_features_list(self):
        """
        Query all indoor features

        :returns: JSON IndoorFeatures
        """

        with self.connection.cursor() as cur:
            select_query = "TODO"
            cur.execute(select_query)
            result = cur.fetchall()
        return result

    def get_features(
            self, collection_id, bbox='', datetime='', limit=10, offset=0,
            sub_trajectory=False):
        """
        Retrieve the indoor feature collection to access
        the static information of the indoor feature
        /collections/{collectionId}/items

        :param collection_id: local identifier of a collection
        :param bbox: bounding box [lowleft1,lowleft2,min(optional),
                                   upright1,upright2,max(optional)]
        :param datetime: either a date-time or an interval(datestamp or extent)
        :param limit: number of items (default 10) [optional]
        :param offset: starting record to return (default 0)

        :returns: JSON IndoorFeatures
        """

        with self.connection.cursor() as cur:
            bbox_restriction = ""
            if bbox != '' and bbox is not None:
                s_bbox = ','.join(str(x) for x in bbox)
                if len(bbox) == 4:
                    bbox_restriction = " and box2d(stboxx(" + \
                        s_bbox + ")) &&& box2d(extentTGeometry) "
                elif len(bbox) == 6:
                    bbox_restriction = " and box3d(stboxz(" + \
                        s_bbox + ")) &&& box3d(extentTGeometry) "

            datetime_restriction = ""
            if datetime != '' and datetime is not None:
                if sub_trajectory is False or sub_trajectory == "false":
                    datetime_restriction = (
                        """ and((lifespan && tstzspan('[{0}]'))
                        or (extentTPropertiesValueFloat::tstzspan &&
                        tstzspan('[{0}]')) or
                        (extentTPropertiesValueText::tstzspan &&
                        tstzspan('[{0}]')) or
                        (extentTGeometry::tstzspan && tstzspan('[{0}]')))"""
                        .format(datetime))
            limit_restriction = " LIMIT " + \
                str(limit) + " OFFSET " + str(offset)

            # sub_trajectory is false
            select_query = (
                """TODO""" )

            cur.execute(select_query)
            result = cur.fetchall()
            number_matched = len(result)

            select_query += limit_restriction
            cur.execute(select_query)
            result = cur.fetchall()
            number_returned = len(result)

        return result, number_matched, number_returned

    def get_feature(self, collection_id, mfeature_id):
        """
        Access the static data of the indoor feature

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a indoor feature

        :returns: JSON IndoorFeature
        """
        with self.connection.cursor() as cur:
            # cur = self.connection.cursor()
            select_query = (
                """TODO""")
            cur.execute(select_query)
            result = cur.fetchall()
        return result
