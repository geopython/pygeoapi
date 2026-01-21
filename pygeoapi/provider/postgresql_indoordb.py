import json
import random
import datetime
import psycopg2
import logging
from functools import partial
from dateutil.parser import parse as dateparse
import pytz
from pygeoapi.util import format_datetime
from psycopg2.extras import Json

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
                INSERT INTO collection (id_str, collection_property)
                VALUES (%s, %s)
            """
            cur.execute(insert_query, (id_str, json.dumps(properties)))
            
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
    
    def post_indoorfeature(self, collection_str_id, indoorfeature):
        """
        Insert a indoor feature into a collection

        :param collection_id: local identifier of a collection
        :param movingfeature: IndoorFeature object or
                           

        :returns: IndoorFeature ID
        """        
        feature_id_str = indoorfeature.get('id')
        properties = indoorfeature.get('properties', {})
        indoor_content = indoorfeature.get('IndoorFeatures', {})
        layers = indoor_content.get('layers', [])

        with self.connection.cursor() as cur:
            try:
                # 2. Resolve Collection DB ID (Integer) from String ID
                cur.execute("SELECT id_str FROM collection WHERE id_str = %s", (collection_str_id,))
                res = cur.fetchone()
                if not res:
                    raise Exception(f"Collection {collection_str_id} not found.")
                collection_pk = res[0]

                # 3. Insert Main IndoorFeature
                # We store the raw GeoJSON properties in a JSONB column
                cur.execute(
                    """
                    INSERT INTO indoorfeature (id_str, collection_id, geojson_properties)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (feature_id_str, collection_pk, Json(properties))
                )
                indoorfeature_pk = cur.fetchone()[0]

                # 4. Iterate and Insert Layers
                for layer in layers:
                    self._post_thematic_layer(cur, collection_pk, indoorfeature_pk, layer)

                # Commit is handled automatically by the context manager if no error is raised
                self.connection.commit()
                return feature_id_str

            except Exception as e:
                self.connection.rollback()
                raise e
    def _post_thematic_layer(self, cur, coll_pk, feature_pk, layer_data):
        """
        Helper to insert a ThematicLayer and trigger its content insertion.
        """
        # Extract Primal/Dual logical blocks
        primal = layer_data.get('primalSpace', {})
        dual = layer_data.get('dualSpace', {})

        # Insert ThematicLayer
        cur.execute(
            """
            INSERT INTO thematiclayer 
            (id_str, collection_id, indoorfeature_id, theme, semantic_extension, 
             is_logical, is_directed, 
             primalspace_id_str, dualspace_id_str, 
             p_creation_datetime, p_termination_datetime,
             d_creation_datetime, d_termination_datetime)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                layer_data.get('id'),
                coll_pk,
                feature_pk,
                layer_data.get('theme', 'Unknown'),
                layer_data.get('semanticExtension', False),
                dual.get('isLogical', False),
                dual.get('isDirected', False),
                primal.get('id'),
                dual.get('id'),
                primal.get('creationDatetime'),
                primal.get('terminationDatetime'),
                dual.get('creationDatetime'),
                dual.get('terminationDatetime')
            )
        )
        layer_pk = cur.fetchone()[0]

        # Insert Primal Members (Cells/Boundaries)
        self._post_primal_members(cur, coll_pk, feature_pk, layer_pk, primal)
        
        # Insert Dual Members (Nodes/Edges)
        self._post_dual_members(cur, coll_pk, feature_pk, layer_pk, dual)

    def _post_primal_members(self, cur, coll_pk, feat_pk, layer_pk, primal_data):
        """
        Helper to insert CellSpace and CellSpaceBoundary
        """
        # 1. Cells
        for cell in primal_data.get('cellSpaceMember', []):
            geom_raw = cell.get('cellSpaceGeom', {})
            geom_json = geom_raw.get('geometry2D') or geom_raw.get('geometry3D') or geom_raw.get('geometry')

            # Insert Cell
            # Note: We use ST_SetSRID(ST_GeomFromGeoJSON(...), 4326) to handle the geometry conversion safely
            sql = """
                INSERT INTO cell_space_n_boundary 
                (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, 
                 cell_name, level, "2D_geometry", poi)
                VALUES (%s, 'space', %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s)
            """
            cur.execute(sql, (
                cell.get('id'),
                coll_pk,
                feat_pk,
                layer_pk,
                cell.get('cellSpaceName'),
                str(cell.get('level')),
                json.dumps(geom_json) if geom_json else None,
                cell.get('poi')
            ))

        # 2. Boundaries
        for bound in primal_data.get('cellBoundaryMember', []):
            geom_raw = bound.get('cellBoundaryGeom', {})
            geom_json = geom_raw.get('geometry2D') or geom_raw.get('geometry3D') or geom_raw.get('geometry')

            sql = """
                INSERT INTO cell_space_n_boundary 
                (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, 
                 is_virtual, "2D_geometry")
                VALUES (%s, 'boundary', %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
            """
            cur.execute(sql, (
                bound.get('id'),
                coll_pk,
                feat_pk,
                layer_pk,
                bound.get('isVirtual', False),
                json.dumps(geom_json) if geom_json else None
            ))

    def _post_dual_members(self, cur, coll_pk, feat_pk, layer_pk, dual_data):
        """
        Helper to insert Nodes and Edges
        """
        # 1. Nodes
        for node in dual_data.get('nodeMember', []):
            geom_json = node.get('geometry')
            
            sql = """
                INSERT INTO node_edge 
                (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, geometry_val)
                VALUES (%s, 'node', %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
            """
            cur.execute(sql, (
                node.get('id'),
                coll_pk,
                feat_pk,
                layer_pk,
                json.dumps(geom_json) if geom_json else None
            ))

        # 2. Edges
        for edge in dual_data.get('edgeMember', []):
            geom_json = edge.get('geometry')

            sql = """
                INSERT INTO node_edge 
                (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, geometry_val, weight)
                VALUES (%s, 'edge', %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s)
            """
            cur.execute(sql, (
                edge.get('id'),
                coll_pk,
                feat_pk,
                layer_pk,
                json.dumps(geom_json) if geom_json else None,
                edge.get('weight', 1.0)
            ))
        