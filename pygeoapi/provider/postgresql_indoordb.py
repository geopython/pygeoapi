import json
import datetime
import psycopg2
import logging
from functools import partial
from dateutil.parser import parse as dateparse
import pytz
from IndoorGML_API.pygeoapi.process.manager import postgresql
from pymeos import (Temporal, TFloatSeq, TFloatSeqSet, pymeos_initialize)
from pygeoapi.util import format_datetime
from pymeos_cffi import (tfloat_from_mfjson, ttext_from_mfjson,
                         tgeompoint_from_mfjson)

LOGGER = logging.getLogger(__name__)

class PostgresIndoorDB:
    def __init__(self, datasource=None):
        """
        PostgresIndoorDB Class Constructor
        """
        # define defaults inside init to avoid class-level state issues
        self.host = 'localhost'
        self.port = 5432
        self.dbname = 'indoordb'
        self.user = 'user'
        self.password = 'password'
        self.connection = None

        if datasource is not None:
            self.host = datasource.get('host', self.host)
            self.port = datasource.get('port', self.port)
            # Fixed: Ensure code matches docstring (using 'dbname' consistently)
            self.dbname = datasource.get('dbname', self.dbname) 
            self.user = datasource.get('user', self.user)
            self.password = datasource.get('password', self.password)
    
    def connect(self):
        """
        Establish a connection to the PostgreSQL database.
        """
        # Idempotency check: Don't reconnect if already connected
        if self.connection is not None and self.connection.closed == 0:
            return

        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password
            )
            # Optional: Set autocommit if you aren't doing transaction management
            # self.connection.autocommit = True 
            
        except Exception as e:
            LOGGER.error(f"Error connecting to database: {e}")
            # CRITICAL: Re-raise the exception so the caller knows it failed!
            raise e
    
    def disconnect(self):
        """
        Close the connection to the PostgreSQL database.
        """
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def get_collections_list(self):
        """
        Query indoor features collection list
        Returns a simple list of collection IDs, e.g., ['campus_1', 'campus_2']
        """
        # 1. Ensure connection is alive before asking for cursor
        self.connect()

        with self.connection.cursor() as cur:
            select_query = "SELECT collection_id FROM collection"
            cur.execute(select_query)
            result = cur.fetchall()
        
        # 2. Flatten the list of tuples [('id1',), ('id2',)] -> ['id1', 'id2']
        clean_list = [row[0] for row in result]
        
        return clean_list

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
