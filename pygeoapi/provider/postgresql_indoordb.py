import json
import random
import datetime
import psycopg2
import logging
from functools import partial
from dateutil.parser import parse as dateparse
import pytz
from pygeoapi.util import format_datetime

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
        Query indoor features collection list with metadata.
        Returns:
            list[dict]: A list of dicts, e.g. 
            [{'id': 'campus_1', 'title': 'Main Campus', 'itemType': 'feature'}, ...]
        """
        self.connect()

        with self.connection.cursor() as cur:
            # Fetch both the ID and the properties JSON
            select_query = "SELECT collection_id, collection_property FROM collection"
            cur.execute(select_query)
            result = cur.fetchall()
        
        clean_list = []
        for row in result:
            c_id = row[0]
            # Handle cases where collection_property might be None
            props = row[1] if row[1] else {}
            
            clean_list.append({
                'id': c_id,
                # Replicate your original logic: default title to ID if missing
                'title': props.get('title', c_id), 
                'itemType': props.get('itemType', 'feature')
            })
        
        return clean_list

    def get_collections_list(self):
        """
        Query indoor features collection list with metadata.
        Returns: [{'id': 'campus_1', 'title': 'My Campus', 'itemType': 'indoorfeature'}, ...]
        """
        self.connect()

        with self.connection.cursor() as cur:
            # Select the String ID and the JSON properties
            select_query = "SELECT id_str, collection_property FROM collection"

            cur.execute(select_query)
            result = cur.fetchall()
        
        clean_list = []
        for row in result:
            c_id = row[0]       # id_str column
            props = row[1]      # collection_property column (JSONB)
            
            # Safety check: if props is None, use empty dict
            if props is None:
                props = {}
            
            clean_list.append({
                'id': c_id,
                # Default to the ID if title is missing
                'title': props.get('title', c_id),
                'itemType': props.get('itemType', 'indoorfeature')
            })
            
        return clean_list
    
    def get_collection(self, collection_id):
        """
        Query specific indoor features collection metadata.
        Args:
            collection_id (str): The string ID (e.g. 'campus_1')
        Returns:
            dict: Metadata dict or None if not found.
        """
        self.connect()
        
        with self.connection.cursor() as cur:
            # Query for the ID and Properties using the String ID
            query = "SELECT id_str, collection_property FROM collection WHERE id_str = %s"
            cur.execute(query, (collection_id,))
            row = cur.fetchone()
        
        if not row:
            return None
            
        c_id = row[0]
        props = row[1] if row[1] else {}
        
        return {
            'id': c_id,
            'title': props.get('title', c_id),
            'description': props.get('description', ''),
            'itemType': props.get('itemType', 'indoorfeature')
        }
    

    def create_collection(self, id_str, title, description, item_type='indoorfeature'):
        """
        Creates a new collection in the IndoorGML database.
        """
        self.connect()
        
        # 1. Generate a random BigInt ID (since your schema uses BigInt PKs, not Serial)
        # Matches your previous logic: random.randint(1, 9223372036854775800)
        new_pk_id = random.randint(1, 9223372036854775800)

        # 2. Prepare the JSON property blob
        properties = {
            'title': title,
            'description': description,
            'itemType': item_type
        }
        
        with self.connection.cursor() as cur:
            # 3. Check if exists first (safety check)
            cur.execute("SELECT 1 FROM collection WHERE id_str = %s", (id_str,))
            if cur.fetchone():
                return False  # Already exists

            # 4. Insert
            insert_query = """
                INSERT INTO collection (id, id_str, collection_property)
                VALUES (%s, %s, %s)
            """
            cur.execute(insert_query, (new_pk_id, id_str, json.dumps(properties)))
            
            # Commit is handled by the connection context or autocommit settings, 
            # but usually explicit commit is safer in transactional wrapper.
            self.connection.commit()
            
        return True

    def delete_collection(self, id_str):
        """
        Deletes a collection and CASCADES valid deletions down to all child tables.
        Matches the "Deep Clean" logic of your SQLAlchemy code.
        """
        self.connect()

        with self.connection.cursor() as cur:
            # 1. Get the Numeric Primary Key (id) from the String ID (id_str)
            cur.execute("SELECT id FROM collection WHERE id_str = %s", (id_str,))
            row = cur.fetchone()
            
            if not row:
                return False # Collection not found
            
            coll_pk = row[0]

            # 2. CASCADE DELETE (Bottom-Up Order)
            
            # A. Delete Connections (Edges between nodes)
            # Logic: Delete from 'connects' where source or target is in the set of nodes belonging to this collection
            delete_connects = """
                DELETE FROM connects 
                WHERE node_source_id IN (SELECT id FROM node_n_edge WHERE collection_id = %s)
                   OR node_target_id IN (SELECT id FROM node_n_edge WHERE collection_id = %s)
                   OR edge_id IN (SELECT id FROM node_n_edge WHERE collection_id = %s)
            """
            cur.execute(delete_connects, (coll_pk, coll_pk, coll_pk))

            # B. Delete Inter-Layer Connections
            cur.execute("DELETE FROM interlayerconnection WHERE collection_id = %s", (coll_pk,))

            # C. Delete Spatial Elements (Nodes & Cells)
            cur.execute("DELETE FROM node_n_edge WHERE collection_id = %s", (coll_pk,))
            cur.execute("DELETE FROM cell_space_n_boundary WHERE collection_id = %s", (coll_pk,))

            # D. Delete Thematic Layers
            cur.execute("DELETE FROM thematiclayer WHERE collection_id = %s", (coll_pk,))

            # E. Delete IndoorFeatures
            cur.execute("DELETE FROM indoorfeature WHERE collection_id = %s", (coll_pk,))

            # F. FINALLY: Delete the Collection itself
            cur.execute("DELETE FROM collection WHERE id = %s", (coll_pk,))
            
            self.connection.commit()
        
        return True

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

    def get_interlayer_connections(self, feature_str_id):
        """
        Fetches connections for a specific IndoorFeature.
        Matches table: interlayerconnection
        """
        self.connect()
        with self.connection.cursor() as cur:
            # 1. Get Feature PK
            cur.execute("SELECT id FROM indoorfeature WHERE id_str = %s", (feature_str_id,))
            res = cur.fetchone()
            if not res: return []
            feature_pk = res[0]

            # 2. Get Connections
            # Note: We join with 'layer' table (l1, l2) to get the String IDs back for the JSON response
            query = """
                SELECT 
                    c.id_str, 
                    c.topo_type, 
                    c.comment, 
                    l1.id_str as layer_a_str, 
                    l2.id_str as layer_b_str,
                    c.id as conn_pk
                FROM interlayerconnection c
                LEFT JOIN layer l1 ON c.connected_layer_a = l1.id
                LEFT JOIN layer l2 ON c.connected_layer_b = l2.id
                WHERE c.indoorfeature_id = %s
            """
            cur.execute(query, (feature_pk,))
            rows = cur.fetchall()
            
            results = []
            for row in rows:
                conn_pk = row[5]
                
                # TODO: If you have an 'interlayeredge' table, fetch edges here using conn_pk
                # For now, we return the connection shell
                
                results.append({
                    "id": row[0],
                    "typeOfTopoExpression": row[1],
                    "comment": row[2],
                    "interConnects": [row[3], row[4]], # Layer String IDs
                    "interLayerConnectionMember": [] # Populate this if you have an edge table
                })
                
        return results


    def create_interlayer_connection(self, collection_str_id, feature_str_id, data):
        """
        Creates a connection in the 'interlayerconnection' table.
        Resolves String IDs to BigInt IDs for Foreign Keys.
        """
        self.connect()
        
        new_id = data.get('id')
        topo = data.get('typeOfTopoExpression', 'EQUALS')
        comment = data.get('comment', '')
        
        # Extract Layer String IDs from JSON
        layers = data.get('interConnects', [])
        layer_a_str = layers[0] if len(layers) > 0 else None
        layer_b_str = layers[1] if len(layers) > 1 else None

        try:
            with self.connection.cursor() as cur:
                # 1. Resolve IDs (This is robust SQL to get BigInts from Strings)
                
                # Resolve Collection PK
                cur.execute("SELECT id FROM collection WHERE id_str = %s", (collection_str_id,))
                res = cur.fetchone()
                if not res: raise Exception("Collection not found")
                coll_pk = res[0]

                # Resolve Feature PK
                cur.execute("SELECT id FROM indoorfeature WHERE id_str = %s AND collection_id = %s", (feature_str_id, coll_pk))
                res = cur.fetchone()
                if not res: raise Exception("Feature not found")
                feat_pk = res[0]

                # Resolve Layer A PK
                cur.execute("SELECT id FROM layer WHERE id_str = %s", (layer_a_str,))
                res = cur.fetchone()
                if not res: raise Exception(f"Layer {layer_a_str} not found")
                layer_a_pk = res[0]

                # Resolve Layer B PK
                cur.execute("SELECT id FROM layer WHERE id_str = %s", (layer_b_str,))
                res = cur.fetchone()
                if not res: raise Exception(f"Layer {layer_b_str} not found")
                layer_b_pk = res[0]

                # 2. Insert Record
                insert_query = """
                    INSERT INTO interlayerconnection 
                    (id_str, collection_id, indoorfeature_id, connected_layer_a, connected_layer_b, topo_type, comment)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                
                cur.execute(insert_query, (
                    new_id, 
                    coll_pk, 
                    feat_pk, 
                    layer_a_pk, 
                    layer_b_pk, 
                    topo, 
                    comment
                ))
                
                self.connection.commit()
                return new_id

        except Exception as e:
            self.connection.rollback()
            LOGGER.error(f"DB Error: {e}")
            return None