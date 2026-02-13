import json
import random
import datetime
import psycopg2
import logging
from functools import partial
from dateutil.parser import parse as dateparse
import pytz
from pygeoapi.util import format_datetime
from psycopg2.extras import Json, RealDictCursor, NamedTupleCursor
import re

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
            
# region server
    def connect(self):
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
           
            self.connection.autocommit = False 
            
        except Exception as e:
            LOGGER.error(f"Error connecting to database: {e}")
            raise e
            
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
# endregion

# region IndoorFeatureCollections +

    def get_collections_list(self):
        """
        Query indoor features collection list with metadata.
        """
        with self.connection.cursor() as cur:
            try:
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
            except Exception as e:
                LOGGER.debug(e)
                raise e
            
        return clean_list
    
    def get_collection(self, collection_id: str):
        """
        Query specific indoor features collection metadata.
        Args:
            collection_id (str): The string ID (e.g. 'campus_1')
        Returns:
            dict: Metadata dict or None if not found.
        """
        with self.connection.cursor() as cur:
            try:
                query = "SELECT id_str, collection_property FROM collection WHERE id_str = %s"
                cur.execute(query, (collection_id,))
                row = cur.fetchone()
            
                if not row:
                    return None
                
                c_id = row[0]
                props = row[1] if row[1] else {}
                
                response = {
                    'id': c_id,
                    'title': props.get('title', c_id),
                    'description': props.get('description', ''),
                    'itemType': props.get('itemType', 'indoorfeature')
                }

                return response
            except Exception as e:
                LOGGER.debug(e)
                raise e
    
    def post_collection(self, collection):
        """
        Creates a new collection.
        Relies on DB to auto-generate the Integer ID.
        """
        c_id = collection.get('id')
        title = collection.get('title')
        description = collection.get('description', '')
        item_type = collection.get('itemType', 'indoorfeature')
        if not c_id or not title:
            raise ValueError("id and title is required.")
        if item_type != 'indoorfeature':
            raise TypeError("invalid collection type.")
        properties = {
            'title': title,
            'description': description,
            'itemType': item_type
        }
        with self.connection.cursor() as cur:
            try:
                # 2. Insert (Let Postgres handle the 'id' column automatically)
                insert_query = """
                    INSERT INTO collection (id_str, collection_property)
                    VALUES (%s, %s)
                    RETURNING id_str
                """
                cur.execute(insert_query, (c_id, json.dumps(properties)))
                new_id = cur.fetchone()[0]

                self.connection.commit()
                return new_id
            except Exception as e:
                self.connection.rollback()
                LOGGER.error(f"Error creating collection: {e}")
                return None

    def delete_collection(self, collection_id:str):
        """
        Deletes a collection and CASCADES valid deletions down to all child tables.
        Performs the "Deep Clean" logic 
        """
        with self.connection.cursor() as cur:
            try:
                # 1. Get the Numeric Primary Key (id) from the String ID (id_str)
                cur.execute("SELECT id FROM collection WHERE id_str = %s", (collection_id,))
                row = cur.fetchone()
                
                if not row:
                    return False # Collection not found
                
                coll_pk = row[0]

                # 2. CASCADE DELETE (Bottom-Up Order)
                
                # A. Delete Connections (Edges between nodes)
                # Logic: Delete from 'connects' where source or target is in the set of nodes belonging to this collection
                delete_connects = """
                    DELETE FROM connects WHERE node_source_id IN (SELECT id FROM node_n_edge WHERE collection_id = %s);
                    DELETE FROM connects WHERE node_target_id IN (SELECT id FROM node_n_edge WHERE collection_id = %s);
                    DELETE FROM connects WHERE edge_id IN (SELECT id FROM node_n_edge WHERE collection_id = %s);
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
            except Exception as e:
                self.connection.rollback()
                LOGGER.error(f"Error creating collection: {e}")
                raise e
# endregion

# region IndoorFeatures 
    def is_indoor_collection(self, collection_id:str):
        """
        Checks if the collection exists and has itemType='indoorfeature'.
        Returns True if it is an IndoorGML collection, False otherwise.
        """
        is_indoor = False
        with self.connection.cursor() as cur:
            try:
                # Adjust column names 'id_str' and 'itemType' to match your schema
                cur.execute("""
                    SELECT collection_property 
                    FROM collection 
                    WHERE id_str = %s
                """, (collection_id,))
                props = cur.fetchone()
                
                if props:
                    if props[0].get('itemType') == 'indoorfeature':
                        is_indoor = True    
            except Exception as e:
                LOGGER.error(f"Error checking collection type: {e}")

        return is_indoor

    def get_collection_items(
            self, collection_id: str, bbox:list = None, limit:int=10, offset:int=0):
        """
        Retrieve the indoor feature collection /collections/{collectionId}/items
        Optimized to fetch data and total count in a single query.
        /collections/{collectionId}/items
        """
        try:    
            # 1. Prepare Filter Strings
            where_clauses = ["c.id_str = %s"]
            params = [collection_id]

            # 2. Handle BBOX (Same logic as before)
            if bbox:
                if len(bbox) == 4: # OGC 2D
                    where_clauses.append("""
                        i.geojson_geometry && 
                        ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), ST_SRID(i.geojson_geometry))
                    """)
                    params.extend(bbox)
                elif len(bbox) == 6: # OGC 3D
                    where_clauses.append("""
                        i.geojson_geometry && 
                        ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), ST_SRID(i.geojson_geometry))
                    """)
                    params.extend([bbox[0], bbox[1], bbox[3], bbox[4]])

            where_str = " AND ".join(where_clauses)

            with self.connection.cursor() as cur:
                # 3. Combined Query: Get Data + Total Count
                sql = f"""
                    SELECT 
                        count(*) OVER() as full_count,
                        i.id_str, 
                        ST_AsGeoJSON(i.geojson_geometry,4326) as geom,
                        i.geojson_properties
                    FROM indoorfeature i
                    JOIN collection c ON i.collection_id = c.id
                    WHERE {where_str}
                    ORDER BY i.id ASC
                    LIMIT %s OFFSET %s
                """
                
                # Append limit and offset
                query_params = list(params) 
                query_params.extend([limit, offset])
                
                cur.execute(sql, tuple(query_params))
                rows = cur.fetchall()

                features = []
                number_matched = 0

                if rows:
                    # Get the total count from the first column of the first row
                    number_matched = rows[0][0]

                    # 4. Format Rows
                    for row in rows:
                        # Unpack 4 columns now (full_count is index 0)
                        _, feature_id, geom_text, props = row
                        
                        geometry = json.loads(geom_text) if geom_text else None
                        
                        feature = {
                            "type": "Feature",
                            "id": feature_id,
                            "geometry": geometry,
                            "properties": props or {} 
                        }
                        features.append(feature)
                
                return features, number_matched

        except Exception as e:
                LOGGER.debug(e)
                raise e
            
    def get_feature(self, collection_id: str, feature_id:str, level:str=None, bbox:list=None):
        """
        Retrieves the actual IndoorFeature when filtered.
        - If 'bbox' and 'level' are None: Returns only metadata (Lightweight).
        - Primal Space (Cells/Boundaries): Filtered by 'level' if provided.
        - Dual Space (Nodes/Edges): ALWAYS returns all members (unfiltered).
        """
        result_feature = None

        with self.connection.cursor() as cur:
            # ---------------------------------------------------------
            # 1. Fetch Root Metadata
            # ---------------------------------------------------------
            cur.execute("""
                SELECT i.id, i.id_str, ST_AsGeoJSON(i.geojson_geometry), i.geojson_properties
                FROM indoorfeature i
                JOIN collection c ON i.collection_id = c.id
                WHERE c.id_str = %s AND i.id_str = %s
            """, (collection_id, feature_id))
            
            row = cur.fetchone()
            if not row:
                return None
            
            feature_pk, feature_id_str, geom_str, props = row
            geometry = json.loads(geom_str) if geom_str else None
            properties = props or {}
            thematic_layers = []
            interlayer_connections = []
            # Initialize Skeleton
            result_feature = {
                "type": "Feature",
                "id": feature_id_str,
                "geometry": geometry,
                "properties": properties, # Standard metadata properties
                "links": []
            }
            # If no level and bbox provided, return Metadata only
            if not level and not bbox:
                LOGGER.debug("No query parameter")
                return result_feature
            
            # 2. Fetch Thematic Layers (Keep ID mapping for later)
            cur.execute("SELECT id FROM thematiclayer WHERE indoorfeature_id=%s", (feature_pk,))
            rows = cur.fetchall()
            for row in rows:
                thematic_layers.append(self._get_layer(row, level=level, bbox=bbox))

            # InterlayerConnection
            conn_sql = """
                SELECT 
                    i.id, i.id_str, i.topo_type, i.comment,
                    la.id_str AS layer_a_str, lb.id_str AS layer_b_str,
                    ca.id_str AS cell_a_str,  cb.id_str AS cell_b_str,
                    na.id_str AS node_a_str,  nb.id_str AS node_b_str
                FROM interlayerconnection i
                -- Join for Layer IDs
                LEFT JOIN thematiclayer la ON i.connected_layer_a = la.id
                LEFT JOIN thematiclayer lb ON i.connected_layer_b = lb.id
                -- Join for Cell IDs
                LEFT JOIN cell_space_n_boundary ca ON i.connected_cell_a = ca.id
                LEFT JOIN cell_space_n_boundary cb ON i.connected_cell_b = cb.id
                -- Join for Node IDs (Directly from node_n_edge, ignoring 'connects' table)
                LEFT JOIN node_n_edge na ON i.connected_node_a = na.id
                LEFT JOIN node_n_edge nb ON i.connected_node_b = nb.id
                WHERE i.indoorfeature_id = %s
            """
            
            cur.execute(conn_sql, (feature_pk,))
            connection_rows = cur.fetchall()

            for c_row in connection_rows:
                (
                    c_pk, c_id, topo, comment,
                    l_a_str, l_b_str,
                    c_a_str, c_b_str,
                    n_a_str, n_b_str
                ) = c_row

                # Build lists, filtering out None values 
                # (in case a connection is defined on Layers but not Nodes/Cells, etc.)
                layers = [x for x in [l_a_str, l_b_str] if x]
                nodes  = [x for x in [n_a_str, n_b_str] if x]
                cells  = [x for x in [c_a_str, c_b_str] if x]

                interlayer_connection = {
                    "id": c_id,
                    "featureType": "InterLayerConnection",
                    "typeOfTopoExpression": topo,
                    "comment": comment if comment else "",
                    "connectedLayers": layers,
                    "connectedNodes": nodes,
                    "connectedCells": cells
                }
                
                interlayer_connections.append(interlayer_connection)
            
            result_indoorfeature = {
                "featureType": "IndoorFeatures",
                "layers": thematic_layers,
                "layerConnections": interlayer_connections
            }
            result_feature["IndoorFeatures"] = result_indoorfeature
        
        return result_feature
    
    def post_indoorfeature(self, collection_id:str, indoorfeature):
        """
        Insert a indoor feature into a collection

        :param collection_id: local identifier of a collection

        :returns: IndoorFeature ID
        """        
        feature_str_id = indoorfeature.get('id')
        properties = indoorfeature.get('properties', {})
        geometries = indoorfeature.get('geometry', {})
        layers = indoorfeature.get('layers', None)
        interlayerconnections = indoorfeature.get('layerConnections', None)
        if not layers:
            raise Exception(f"An indoorFeature must have at least one thematic layer.")
        with self.connection.cursor() as cur:
            try:
                # Resolve Collection DB ID (Integer) from String ID
                cur.execute("SELECT id FROM collection WHERE id_str = %s", (collection_id,))
                res = cur.fetchone()
                if not res:
                    raise Exception(f"Collection {collection_id} not found.")
                collection_pk = res[0]
                LOGGER.debug("Insert indoorFeature")
                cur.execute(
                    """
                    INSERT INTO indoorfeature (id_str, collection_id, geojson_geometry ,geojson_properties)
                    VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),%s)
                    RETURNING id,id_str
                    """,
                    (feature_str_id, collection_pk, json.dumps(geometries), Json(properties))
                )
                ifeature_new = cur.fetchone()
                
                # Iterate and Insert Layers
                for layer in layers:
                    self._post_thematic_layer(collection_pk, ifeature_new[0], layer)
                if interlayerconnections:
                    for connection in interlayerconnections:
                        self.post_interlayer_connection(collection_id, feature_str_id, connection)

                # autocommit is False
                self.connection.commit()
            
                return ifeature_new[1]

            except Exception as e:
                self.connection.rollback()
                print(f"Error occurred: {e}. Rolling back changes.")
                raise None

    def delete_indoorfeature(self, collection_id:str, feature_id:str):
        """
        Deletes an IndoorFeature and all its associated layers, cells, nodes, and connections.
        
        :param collection_str_id: The String ID of the Collection (e.g., 'IndoorGML_DataSet_1')
        :param feature_id_str: The String ID of the Feature to delete (e.g., 'AIST_Waterfront')
        """
        LOGGER.debug(f"Deleting IndoorFeature: {feature_id} in {collection_id}")

        with self.connection.cursor() as cur:
            try:
                # 1. Resolve IDs (We need the Integer IDs to delete efficiently)
                cur.execute(
                    "SELECT c.id, i.id FROM collection c "
                    "JOIN indoorfeature i ON c.id = i.collection_id "
                    "WHERE c.id_str = %s AND i.id_str = %s",
                    (collection_id, feature_id)
                )
                res = cur.fetchone()
                
                if not res:
                    # Item not found, usually returns 404 in API, but here we can just return
                    LOGGER.warning(f"Feature {feature_id} not found.")
                    return

                coll_pk, feature_pk = res

                # 2. DELETE CHILDREN FIRST
                # A. Delete Connections (Edges between nodes)
                delete_connects = """
                    DELETE FROM connects WHERE node_source_id IN (SELECT id FROM node_n_edge WHERE indoorfeature_id = %s);
                    DELETE FROM connects WHERE node_target_id IN (SELECT id FROM node_n_edge WHERE indoorfeature_id = %s);
                    DELETE FROM connects WHERE edge_id IN (SELECT id FROM node_n_edge WHERE indoorfeature_id = %s);
                """
                cur.execute(delete_connects, (feature_pk,feature_pk,feature_pk))

                # B. Delete InterLayerConnections
                cur.execute("DELETE FROM interlayerconnection WHERE indoorfeature_id = %s", (feature_pk,))

                # C. Delete Nodes and Edges
                cur.execute("DELETE FROM node_n_edge WHERE indoorfeature_id = %s", (feature_pk,))

                # D. Delete Cells and Boundaries
                cur.execute("DELETE FROM cell_space_n_boundary WHERE indoorfeature_id = %s", (feature_pk,))

                # E. Delete Thematic Layers
                cur.execute("DELETE FROM thematiclayer WHERE indoorfeature_id = %s", (feature_pk,))

                # 3. DELETE PARENT (The IndoorFeature itself)
                cur.execute("DELETE FROM indoorfeature WHERE id = %s", (feature_pk,))

                # Commit is handled by the context manager
                self.connection.commit()
                return True
            except Exception as e:
                self.connection.rollback()
                LOGGER.error(f"Error deleting indoorfeature: {e}")
                raise e
# endregion 
    
# region ThematicLayers
    def get_layers(self, collection_id:str, feature_id:str, theme: str = None, level: str = None, limit:int=10, offset:int=0):
        """
        Retrieves a list of Thematic Layers.
        - Levels: Always returns ALL levels available in that layer (so client knows what else exists).
        - Filtering: Only returns layers that actually contain the requested level.
        """
        response = {
            "levels": [],
            "layers": [],
            "links": []
        }
        with self.connection.cursor() as cur:
            # 1. Get Available Levels (Global Context)
            sql_levels = """
                SELECT DISTINCT cs.level
                FROM cell_space_n_boundary cs
                JOIN thematiclayer tl ON cs.thematiclayer_id = tl.id
                JOIN indoorfeature i ON tl.indoorfeature_id = i.id
                JOIN collection c ON i.collection_id = c.id
                WHERE c.id_str = %s AND i.id_str = %s AND cs.level IS NOT NULL
            """
            params_levels = [collection_id, feature_id]

            if level:
                sql_levels += " AND cs.level = %s"
                params_levels.append(level)

            if theme:
                sql_levels += " AND tl.theme = %s"
                params_levels.append(theme)
            
            sql_levels += " ORDER BY cs.level"
            cur.execute(sql_levels, tuple(params_levels))
            response["levels"] = [row[0] for row in cur.fetchall()]

            # -----------------------------------------------------
            # 2. Get Layer Summaries
            # -----------------------------------------------------
            # Use separate lists to ensure order matches the final string
            select_params = []
            where_params = [collection_id, feature_id]
            having_params = []
            
            # A. Build SELECT Clause
            select_clause = """
                SELECT tl.id_str, tl.theme, tl.semantic_extension, i.id_str,
                       array_agg(DISTINCT cs.level) as layer_levels
            """

            # B. Build FROM/WHERE Clause
            from_clause = """
                FROM thematiclayer tl
                JOIN indoorfeature i ON tl.indoorfeature_id = i.id
                JOIN collection c ON i.collection_id = c.id
                LEFT JOIN cell_space_n_boundary cs ON cs.thematiclayer_id = tl.id
                WHERE c.id_str = %s AND i.id_str = %s
            """
            # where_params is already initialized with [collection_id, feature_id]

            if theme:
                from_clause += " AND tl.theme = %s"
                where_params.append(theme)
            
            # C. Build HAVING Clause (The actual filter)
            having_clause = ""
            if level:
                having_clause = "HAVING count(*) FILTER (WHERE cs.level = %s) > 0"
                having_params.append(level)

            # D. Combine Everything
            sql_layers = f"""
                {select_clause}
                {from_clause}
                GROUP BY tl.id, tl.id_str, tl.theme, tl.semantic_extension, i.id_str
                {having_clause}
                ORDER BY tl.id ASC LIMIT %s OFFSET %s
            """
            
            # CRITICAL: Concatenate lists in the exact order they appear in SQL
            final_params = select_params + where_params + having_params + [limit, offset]

            cur.execute(sql_layers, tuple(final_params))

            rows = cur.fetchall()
            # E. Process Results
            for row in rows:
                l_id, l_theme, semantic_extension, feature_id, layer_levels = row
                 
                found_levels = layer_levels if layer_levels is not None else []
                # Clean up None values and sort
                found_levels = [l for l in found_levels if l is not None]
                found_levels.sort()

                layer_summary = {
                    "id": l_id,
                    "featureType": "ThematicLayer",
                    "semanticExtension": semantic_extension,
                    "theme": l_theme if l_theme else "Unknown",
                    "levels": found_levels,
                    "links": []
                }
                response["layers"].append(layer_summary)

        return response
    
    def _get_layer(self, layer_pk:int, level:str=None, bbox:list=None):
        """
        Retrieves a single Thematic Layer.
        If not filtered, just the meta data is given.
        - PrimalSpace: Filtered by 'level' if provided.
        - DualSpace: Returns the ENTIRE network (unfiltered) for connectivity.
        """
        result_layer = None
        with self.connection.cursor() as cur:
            try:
                if level or bbox:
                # 1. Fetch layer filtered by level or bbox
                    query = """
                        SELECT tl.id, tl.id_str, tl.theme, tl.is_logical, tl.is_directed, tl.primalspace_id_str, tl.dualspace_id_str, tl.p_creation_datetime, tl.d_creation_datetime, tl.semantic_extension
                        FROM thematiclayer tl
                        WHERE tl.id = %s
                    """
                    cur.execute(query, (layer_pk,))

                    row = cur.fetchone()
                    
                    if not row:
                        return None
                    l_pk, l_id, l_theme, l_logical, l_directed, p_id, d_id, p_create, d_create, l_se = row
                    # 2. Fetch Primal and Dual Spaces
                    primal = self._get_primal_space(l_pk, p_id, p_create=p_create, level=level, bbox=bbox)
                    dual = self._get_dual_space(l_pk, d_id, d_create=d_create, is_logical=l_logical, is_directed=l_directed)
                    result_layer = {
                        "id": l_id,
                        "featureType": "ThematicLayer",
                        "theme": l_theme if l_theme else "Unknown",
                        "semanticExtension": l_se if l_se else False,
                        "primalSpace": primal,
                        "dualSpace": dual,
                        "links": []
                    }
                else:
                    raise KeyError("Missing required parameter: level or bbox")
            except Exception as e:
                raise e           

        return result_layer

    def get_layer(self, collection_id:str, feature_id:str, layer_id:str, level:str=None, bbox:list=None):
        """
        Retrieves a single Thematic Layer.
        If not filtered, just the meta data is given.
        - PrimalSpace: Filtered by 'level' if provided.
        - DualSpace: Returns the ENTIRE network (unfiltered) for connectivity.
        """
        result_layer = None
        with self.connection.cursor() as cur:
            if level or bbox:
               # 1. Fetch layer filtered by level or bbox
                query = """
                    SELECT tl.id, tl.id_str, tl.theme, tl.is_logical, tl.is_directed, tl.primalspace_id_str, tl.dualspace_id_str, tl.p_creation_datetime, tl.d_creation_datetime
                    FROM thematiclayer tl
                    JOIN indoorfeature i ON tl.indoorfeature_id = i.id
                    JOIN collection c ON i.collection_id = c.id
                    WHERE c.id_str = %s AND i.id_str = %s AND tl.id_str = %s
                """
                cur.execute(query, (collection_id, feature_id, layer_id))

                row = cur.fetchone()
                
                if not row:
                    return None
                l_pk, l_id, l_theme, l_logical, l_directed, p_id, d_id, p_create, d_create = row
                # 2. Fetch Primal and Dual Spaces
                primal = self._get_primal_space(l_pk, p_id, p_create, level=level, bbox=bbox)
                dual = self._get_dual_space(l_pk, d_id, d_create=d_create, is_logical=l_logical, is_directed=l_directed)
                result_layer = {
                    "id": l_id,
                    "featureType": "ThematicLayer",
                    "theme": l_theme if l_theme else "Unknown",
                    "semanticExtension": False,
                    "primalSpace": primal,
                    "dualSpace": dual,
                    "links": []
                }
            else:
                # 1. Fetch Layer Metadata
                sql_meta = """
                    SELECT tl.id, tl.id_str, tl.theme, tl.is_logical, tl.is_directed, tl.semantic_extension,
                       ST_XMin(ST_Extent(cs."2D_geometry")) as minx,
                       ST_YMin(ST_Extent(cs."2D_geometry")) as miny,
                       ST_XMax(ST_Extent(cs."2D_geometry")) as maxx,
                       ST_YMax(ST_Extent(cs."2D_geometry")) as maxy
                    FROM thematiclayer tl
                    JOIN indoorfeature i ON tl.indoorfeature_id = i.id
                    JOIN collection c ON i.collection_id = c.id
                    LEFT JOIN cell_space_n_boundary cs ON cs.thematiclayer_id = tl.id
                    WHERE c.id_str = %s AND i.id_str = %s AND tl.id_str = %s
                    GROUP BY tl.id, tl.id_str, tl.theme, i.id_str
                """
                cur.execute(sql_meta, (collection_id, feature_id, layer_id))

                row = cur.fetchone()
                if not row:
                    return None
                l_pk, id, theme, is_logical, is_directed, sematic_extension, minx, miny, maxx, maxy = row

                if minx is not None:
                    bbox = [float(minx), float(miny), float(maxx), float(maxy)]
                else:
                    bbox = []
                sql_levels = """
                    SELECT DISTINCT cs.level
                    FROM cell_space_n_boundary cs
                    WHERE cs.thematiclayer_id = %s AND cs.level IS NOT NULL
                    ORDER BY cs.level
                """
                cur.execute(sql_levels, (l_pk,))
                levels = [row[0] for row in cur.fetchall()]
                # select counts of members
                sql_counts = """
                    SELECT 
                        (SELECT COUNT(*) FROM cell_space_n_boundary 
                        WHERE thematiclayer_id = %s AND type = 'space') AS cell_count,
                        
                        (SELECT COUNT(*) FROM cell_space_n_boundary 
                        WHERE thematiclayer_id = %s AND type = 'boundary') AS boundary_count,
                        
                        (SELECT COUNT(*) FROM node_n_edge 
                        WHERE thematiclayer_id = %s AND type = 'node') AS node_count,
                        
                        (SELECT COUNT(*) FROM node_n_edge 
                        WHERE thematiclayer_id = %s AND type = 'edge') AS edge_count;
                """
                cur.execute(sql_counts, (l_pk, l_pk, l_pk, l_pk))
                result_cnt = cur.fetchone()
                
                result_layer = {
                    "id": id,
                    "featureType": "ThematicLayer",
                    "theme": theme if theme else "Unknown",
                    "semanticExtension": sematic_extension,
                    "summary": {
                        "primalSpace": {
                            "cellSpaceCount": result_cnt[0],
                            "cellBoundaryCount": result_cnt[1],
                            "level": levels
                        },
                        "dualSpace": {
                            "nodeCount": result_cnt[2],
                            "edgeCount": result_cnt[3],
                            "isDirected": is_directed,
                            "isLogical": is_logical
                        }
                    },
                    "bbox": bbox,
                    "links": []
                }
            
        return result_layer

    def _get_primal_space(self, layer_pk:int, primalspace_id:str, p_create:str = None, p_termination:str=None, level:str=None, bbox:list=None):
        """
        Helper to build PrimalSpaceLayer. 
        Supports optional filtering by 'level'.
        """
        primal_space = {
            "id": primalspace_id, 
            "featureType": "PrimalSpaceLayer",
            "creationDatetime": p_create,
            "terminationDatetime": p_termination,
            "cellSpaceMember": [],
            "cellBoundaryMember": []
        }
        with self.connection.cursor() as cur:
            sql_cells = """
                SELECT c.id, c.id_str, c.cell_name, c.level, c.external_reference, 
                    ST_AsText("2D_geometry"), c."3D_geometry", c.poi, n.id_str,
                    (
                        SELECT array_agg(child.id_str)s
                        FROM cell_space_n_boundary child
                        WHERE child.bounded_by_cell_id = c.id
                        ) as bounded_by_list
                FROM cell_space_n_boundary c
                LEFT JOIN node_n_edge n ON c.duality_id = n.id
                WHERE c.thematiclayer_id = %s AND c.type = 'space'
            """
            params_cells = [layer_pk]

            if level:
                sql_cells += " AND level = %s"
                params_cells.append(level)

            if bbox:
                minx, miny, maxx, maxy = map(float, bbox)
                sql_cells += """
                    AND c."2D_geometry"
                    && ST_MakeEnvelope(%s, %s, %s, %s, 0)
                """
                params_cells.extend([minx, miny, maxx, maxy])
                
            cur.execute(sql_cells, tuple(params_cells))
            all_referenced_boundaries = set()

            for row in cur.fetchall():
                pk, id, name, level, ext, geom_2d_wkt, geom_3d_json, poi, duality, boundedBylist = row
                geom_2d = self.wkt_to_json(geom_2d_wkt)
    
                if boundedBylist:
                    all_referenced_boundaries.update(boundedBylist)
              
                cell = {
                    "id": id,
                    "featureType": "CellSpace",
                    "duality": duality,
                    "cellSpaceName": name,
                    "level": level,
                    "poi": poi,
                    "cellSpaceGeom": {
                        "geometry2D": geom_2d,
                        "geometry3D": geom_3d_json
                    },
                    "boundedBy": boundedBylist
                }
                if ext: cell["externalReference"] = {"uri": ext}
                primal_space["cellSpaceMember"].append(cell)
                # only boundedBy boundary member could be retrieved
                
                # Convert set to list for the query
                boundary_id_list = list(all_referenced_boundaries)
            
                sql_bounds = """
                    SELECT c.id, c.id_str, c.external_reference, 
                    ST_AsText(c."2D_geometry"), c."3D_geometry", n.id_str, c.is_virtual
                    FROM cell_space_n_boundary c
                    LEFT JOIN node_n_edge n ON c.duality_id = n.id
                    WHERE c.id_str = ANY(%s) AND c.thematiclayer_id = %s
                """
                cur.execute(sql_bounds, (boundary_id_list, layer_pk))
                
                for b_row in cur.fetchall():
                    b_pk, b_id, ext, b_geom2d, b_geom3d, duality, is_virtual = b_row
                    boundary = {
                        "id": b_id,
                        "featureType": "CellBoundary",
                        "duality": duality,
                        "isVirtual": is_virtual,
                        "cellBoundaryGeom": {
                            "geometry2D": self.wkt_to_json(b_geom2d),
                            "geometry3D": b_geom3d
                        }
                    }
                    if ext: boundary["externalReference"] = {"uri": ext}
                    primal_space["cellBoundaryMember"].append(boundary)

            if not primal_space["cellSpaceMember"]:
                return None
            
        return primal_space
    
    def _get_dual_space(self, layer_pk:int, dualspace_id:str, d_create:str = None, d_terminate:str = None, is_logical: bool = False, is_directed: bool = False):
        """
        Helper: Fetches Nodes, Edges, and resolves 'connects' relationships.
        """
        dual_space = {
            "id": dualspace_id,
            "featureType": "DualSpaceLayer",
            "isLogical": is_logical,
            "isDirected": is_directed,
            "creationDatetime": d_create,
            "terminationDatetime": d_terminate,
            "nodeMember": [],
            "edgeMember": []
        }

        node_map = {}
        edge_map = {}
        with self.connection.cursor() as cur:
            # Fetch nodes
            sql_nodes = """
                SELECT n.id_str,
                    ST_AsText(n.geometry_val), c.id_str
                FROM node_n_edge n
                LEFT JOIN cell_space_n_boundary c ON n.duality_id = c.id
                WHERE n.thematiclayer_id = %s AND n.type = 'node'
            """
            cur.execute(sql_nodes, (layer_pk,))
            
            for row in cur.fetchall():
                nid, geom_str_node, duality = row
                geom_node = self.wkt_to_json(geom_str_node)
                
                node = {
                    "id": nid,
                    "featureType": "Node",
                    "geometry": geom_node,
                    "duality": duality,
                    "connects": [] # Populated later
                }
                dual_space["nodeMember"].append(node)
                node_map[nid] = node

            # Fetch Edges
            sql_edges = """
                SELECT n.id_str,
                    ST_AsText(n.geometry_val), n.weight, c.id_str
                FROM node_n_edge n
                LEFT JOIN cell_space_n_boundary c ON n.duality_id = c.id
                WHERE n.thematiclayer_id = %s AND n.type = 'edge'
            """
            cur.execute(sql_edges, (layer_pk,))
            
            for row in cur.fetchall():
                eid, geom_str_edge, weight, duality = row
                geom_edge = self.wkt_to_json(geom_str_edge)
                edge = {
                    "id": eid,
                    "featureType": "Edge",
                    "geometry": geom_edge,
                    "duality": duality,
                    "weight": weight if weight is not None else 0.0,
                    "connects": [] # Populated later
                }
                dual_space["edgeMember"].append(edge)
                edge_map[eid] = edge

            # Populate Connectivity
            #
            # We join node_n_edge 3 times: for the edge itself, the source node, and the target node
            sql_links = """
                SELECT 
                    e.id_str AS edge_id,
                    ns.id_str AS source_id,
                    nt.id_str AS target_id
                FROM connects c
                JOIN node_n_edge e  ON c.edge_id = e.id
                JOIN node_n_edge ns ON c.node_source_id = ns.id
                JOIN node_n_edge nt ON c.node_target_id = nt.id
                WHERE e.thematiclayer_id = %s
            """
            cur.execute(sql_links, (layer_pk,))
            
            for row in cur.fetchall():
                eid, source_id, target_id = row

                # Update Edge 'connects' (Edge connects Node A and Node B)
                if eid in edge_map:
                    edge_map[eid]["connects"] = [source_id, target_id]
                    
                # Update Node 'connects' (Node connects to Edge X)
                if source_id in node_map:
                    # Avoid duplicates
                    if eid not in node_map[source_id]["connects"]:
                        node_map[source_id]["connects"].append(eid)
                
                if target_id in node_map:
                    if eid not in node_map[target_id]["connects"]:
                        node_map[target_id]["connects"].append(eid)

        return dual_space
     
    def _post_thematic_layer(self, collection_pk:int, feature_pk:int, layer_data):
        """
        Helper to insert a ThematicLayer and trigger its content insertion.
        """
        primal = layer_data.get('primalSpace', {})
        dual = layer_data.get('dualSpace', {})
        LOGGER.debug("Insert thematicLayer")
        with self.connection.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO thematiclayer 
                    (id_str, collection_id, indoorfeature_id, theme, semantic_extension, 
                    is_logical, is_directed, 
                    primalspace_id_str, dualspace_id_str, 
                    p_creation_datetime, p_termination_datetime,
                    d_creation_datetime, d_termination_datetime)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, id_str
                    """,
                    (
                        layer_data.get('id'),
                        collection_pk,
                        feature_pk,
                        layer_data.get('theme', 'Unknown').lower(),
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
            
                layer_new = cur.fetchone()
            
                # Insert Primal Members (Cells/Boundaries) - returns duality dict 
                d_c, d_b = self._post_primal_members(collection_pk, feature_pk, layer_new[0], primal)
                
                # Insert Dual Members (Nodes/Edges)
                self._post_dual_members(collection_pk, feature_pk, layer_new[0], dual, d_c, d_b)   

                return layer_new[1]
            except Exception as e:
                LOGGER.debug(f"Insert Error: {e}")
                raise e   

    def _post_primal_members(self, collection_pk:int, feature_pk:int, layer_pk:int, primal_data):
        """
        Helper to insert CellSpace and CellSpaceBoundary
        """
        dual_cell = {}
        dual_boundary = {}
        boundedBy = {}
        with self.connection.cursor() as cur:
            # 1. Cells
            for cell in primal_data.get('cellSpaceMember', []):
                geom_raw = cell.get('cellSpaceGeom', {})
                geom_2d = geom_raw.get('geometry2D', None) 
                geom_3d = geom_raw.get('geometry3D', None)
                
                duplicate_sql = """
                        SELECT n.id_str
                        FROM node_n_edge n
                        WHERE n.indoorfeature_id = %s AND n.id_str = %s
                    """
                cur.execute(duplicate_sql, (feature_pk, cell.get('id')))
                row = cur.fetchone()
                if row:
                    msg = f"{cell.get('id')} is already exist."
                    LOGGER.debug(msg)
                    raise Exception(msg)

                # Insert Cell
                sql = """
                    INSERT INTO cell_space_n_boundary 
                    (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, 
                    cell_name, level, "2D_geometry","3D_geometry", poi)
                    VALUES (%s, 'space', %s, %s, %s, %s, %s, ST_GeomFromText(%s, 0), %s, %s)
                    RETURNING id
                """
                cur.execute(sql, (
                    cell.get('id'),
                    collection_pk,
                    feature_pk,
                    layer_pk,
                    cell.get('cellSpaceName'),
                    str(cell.get('level')),
                    self.json_to_wkt(geom_2d),
                    json.dumps(geom_3d),
                    cell.get('poi')
                ))
                # Store cell pk for duality
                cell_pk = cur.fetchone()
                duality_of_cell = cell.get('duality').split(":")[-1]
                dual_cell[duality_of_cell] = cell_pk[0]
                # Store cell pk for boundedBy
                bbs = cell.get('boundedBy')
                if bbs:
                    for b in bbs:
                        boundedBy[b.split(":")[-1]] = cell_pk[0]
        
            # 2. Boundaries
            for bound in primal_data.get('cellBoundaryMember', []):
                geom_raw = bound.get('cellBoundaryGeom', {})
                geom_2d = geom_raw.get('geometry2D', None) 
                geom_3d = geom_raw.get('geometry3D', None)

                duplicate_sql = """
                        SELECT n.id_str
                        FROM node_n_edge n
                        WHERE n.indoorfeature_id = %s AND n.id_str = %s
                    """
                cur.execute(duplicate_sql, (feature_pk, bound.get('id')))
                row = cur.fetchone()
                if row:
                    msg = f"{bound.get('id')} is already exist."
                    LOGGER.debug(msg)
                    raise Exception(msg)
                # get bounding cell primal key
                boundingCell = boundedBy.get(bound.get('id'))
                
                sql = """
                    INSERT INTO cell_space_n_boundary 
                    (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, 
                    is_virtual, "2D_geometry", "3D_geometry", bounded_by_cell_id)
                    VALUES (%s, 'boundary', %s, %s, %s, %s, ST_GeomFromText(%s, 0), %s, %s)
                    RETURNING id
                """
                cur.execute(sql, (
                    bound.get('id'),
                    collection_pk,
                    feature_pk,
                    layer_pk,
                    bound.get('isVirtual', False),
                    self.json_to_wkt(geom_2d),
                    json.dumps(geom_3d),
                    boundingCell
                ))

                # Store boundary pk for duality
                boundary_pk = cur.fetchone()
                if bound.get('duality'):
                    duality_of_boundary = bound.get('duality').split(":")[-1]
                    dual_boundary[duality_of_boundary] = boundary_pk[0]
            
            # If there is no 2D geometry but 3D, project 3D to 2D geometry
            LOGGER.debug("Project geometry 3D to 2D ")
            sql_projection = """
                UPDATE cell_space_n_boundary c
                SET "2D_geometry" = sub.footprint
                FROM (
                    SELECT 
                        id, 
                        ST_AsText(
                            ST_UnaryUnion(
                                ST_Collect(
                                    ST_Force2D(
                                        ST_GeomFromGeoJSON(
                                            jsonb_build_object(
                                                'type', 'Polygon',
                                                'coordinates', jsonb_build_array(face_element) 
                                            )
                                        )
                                    )
                                )
                            )
                        ) AS footprint
                    FROM cell_space_n_boundary,
                        jsonb_array_elements("3D_geometry"->'coordinates'->0) AS face_element
                    WHERE "3D_geometry" IS NOT NULL AND type='space' AND "2D_geometry" IS NULL AND thematiclayer_id = %s
                    GROUP BY id
                ) sub
                WHERE c.id = sub.id AND thematiclayer_id = %s;
            """
            cur.execute(sql_projection,(layer_pk,layer_pk))

        return dual_cell, dual_boundary
            
    def _post_dual_members(self, collection_pk:int, feature_pk:int, layer_pk:int, dual_data, cell_dict, boundary_dict):
        """
        Helper to insert Nodes and Edges
        """
        # 1. Nodes
        LOGGER.debug("Creating Dual members ")
        node_pk_dict = {}
        with self.connection.cursor() as cur:
            for node in dual_data.get('nodeMember', []):
                duplicate_sql = """
                        SELECT c.id
                        FROM cell_space_n_boundary c
                        WHERE c.indoorfeature_id = %s AND c.id_str = %s
                    """
                cur.execute(duplicate_sql, (feature_pk, node.get('id')))
                row = cur.fetchone()
                if row:
                    msg = f"{node.get('id')} is already exist."
                    LOGGER.debug(msg)
                    raise Exception(msg)
                
                geom_node = node.get('geometry')
                dual_cell_pk = cell_dict.get(node.get('id'))
            
                if not dual_cell_pk:
                    LOGGER.debug(node.get('id'))
                    raise Exception("Duality cell not found")

                sql = """
                    INSERT INTO node_n_edge 
                    (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, geometry_val, duality_id)
                    VALUES (%s, 'node', %s, %s, %s, ST_GeomFromText(%s, 0), %s)
                    RETURNING id
                """
                cur.execute(sql, (
                    node.get('id'),
                    collection_pk,
                    feature_pk,
                    layer_pk,
                    self.json_to_wkt(geom_node),
                    dual_cell_pk
                ))
                # update node's duality
                node_pk = cur.fetchone()
                cur.execute("""
                        UPDATE cell_space_n_boundary 
                        SET duality_id = %s 
                        WHERE id = %s
                    """, (node_pk[0], dual_cell_pk))
                node_pk_dict[node.get('id')] = node_pk[0]

            # 2. Edges
            for edge in dual_data.get('edgeMember', []):
                duplicate_sql = """
                        SELECT c.id
                        FROM cell_space_n_boundary c
                        WHERE c.indoorfeature_id = %s AND c.id_str = %s
                    """
                cur.execute(duplicate_sql, (feature_pk, edge.get('id')))
                row = cur.fetchone()
                if row:
                    msg = f"{edge.get('id')} is already exist."
                    LOGGER.debug(msg)
                    raise Exception(msg)
                
                geom_edge = edge.get('geometry')
                dual_boundary_pk = boundary_dict.get(edge.get('id'))
                sql = """
                    INSERT INTO node_n_edge 
                    (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, geometry_val, weight, duality_id)
                    VALUES (%s, 'edge', %s, %s, %s, ST_GeomFromText(%s, 0), %s, %s)
                    RETURNING id
                """
                cur.execute(sql, (
                    edge.get('id'),
                    collection_pk,
                    feature_pk,
                    layer_pk,
                    self.json_to_wkt(geom_edge),
                    edge.get('weight', 0.0),
                    dual_boundary_pk
                ))

                # update edge's duality
                edge_pk = cur.fetchone()
                cur.execute("""
                        UPDATE cell_space_n_boundary 
                        SET duality_id = %s 
                        WHERE id = %s
                    """, (edge_pk[0], dual_boundary_pk))
                
                # Insert connects into connects table
                sql = """
                    INSERT INTO connects 
                    (node_source_id, node_target_id, edge_id)
                    VALUES (%s, %s, %s)
                """
                
                connects = edge.get('connects')
                n_pk = []
                for i in range(2):
                    n_pk.append(node_pk_dict.get(connects[i].split(":")[-1])) 
                cur.execute(sql, (
                    n_pk[0],
                    n_pk[1],
                    edge_pk[0]
                ))    
              
    def post_thematic_layer(self, collection_id:str, feature_id:str, layer_data):
        """
        Public wrapper: Manages connection/cursor lifecycle and commits data.
        """
        primal = layer_data.get('primalSpace', {})
        dual = layer_data.get('dualSpace', {})
        LOGGER.debug("Insert thematicLayer")
        with self.connection.cursor() as cur:
            try:
                # Check validation and Insert ThematicLayer
                lookup_sql = """
                    SELECT i.id, i.collection_id
                    FROM indoorfeature i
                    JOIN collection c ON i.collection_id = c.id
                    WHERE c.id_str = %s AND i.id_str = %s
                """
                cur.execute(lookup_sql, (collection_id, feature_id))
                ifeature = cur.fetchone()
                if not ifeature:
                    msg = f"{feature_id} is not found"
                    LOGGER.debug(msg)
                    raise Exception(msg)

                cur.execute(
                    """
                    INSERT INTO thematiclayer 
                    (id_str, collection_id, indoorfeature_id, theme, semantic_extension, 
                    is_logical, is_directed, 
                    primalspace_id_str, dualspace_id_str, 
                    p_creation_datetime, p_termination_datetime,
                    d_creation_datetime, d_termination_datetime)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, id_str
                    """,
                    (
                        layer_data.get('id'),
                        ifeature[1],
                        ifeature[0],
                        layer_data.get('theme', 'Unknown').lower(),
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
            
                layer_new = cur.fetchone()
            
                # Insert Primal Members (Cells/Boundaries) - returns duality dict 
                d_c, d_b = self._post_primal_members(ifeature[1], ifeature[0], layer_new[0], primal)
                
                # Insert Dual Members (Nodes/Edges)
                self._post_dual_members(ifeature[1], ifeature[0], layer_new[0], dual, d_c, d_b)   
                
                self.connection.commit()
                
                return layer_new[1]
                
            except Exception as e:
                self.connection.rollback()
                LOGGER.debug(e)
                raise e

    def delete_thematic_layer(self, collection_id:str, feature_id:str, layer_id:str):
        """
        Deletes a ThematicLayer and all associated data (Cells, Nodes, Edges).
        
        Args:
            collection_id (str): The collection ID.
            feature_id (str): The indoor feature ID.
            layer_id (str): The layer ID to delete.
            
        Returns:
            bool: True if deleted, False if not found.
        """       
        with self.connection.cursor() as cur:
            try:
                # 1. Verify existence and get Internal Primary Key (PK)
                # We join tables to ensure strict hierarchy validation
                cur.execute("""
                    SELECT tl.id 
                    FROM thematiclayer tl
                    JOIN indoorfeature i ON tl.indoorfeature_id = i.id
                    JOIN collection c ON i.collection_id = c.id
                    WHERE c.id_str = %s AND i.id_str = %s AND tl.id_str = %s
                """, (collection_id, feature_id, layer_id))
                
                row = cur.fetchone()
                if not row:
                    return False # Layer not found
                
                layer_pk = row[0]
                delete_connects = """
                    DELETE FROM connects WHERE node_source_id IN (SELECT id FROM node_n_edge WHERE thematiclayer_id = %s);
                    DELETE FROM connects WHERE node_target_id IN (SELECT id FROM node_n_edge WHERE thematiclayer_id = %s);
                    DELETE FROM connects WHERE edge_id IN (SELECT id FROM node_n_edge WHERE thematiclayer_id = %s);
                """                
                cur.execute(delete_connects, (layer_pk,layer_pk,layer_pk))
                cur.execute("DELETE FROM interlayerconnection WHERE connected_layer_a = %s", (layer_pk,))
                cur.execute("DELETE FROM interlayerconnection WHERE connected_layer_b = %s", (layer_pk,))
                cur.execute("DELETE FROM node_n_edge WHERE thematiclayer_id = %s", (layer_pk,))
                cur.execute("DELETE FROM cell_space_n_boundary WHERE thematiclayer_id = %s", (layer_pk,))
                cur.execute("DELETE FROM thematiclayer WHERE id = %s", (layer_pk,))
            
                self.connection.commit()
                return True
            except Exception as e:
                self.connection.rollback()
                # Re-raise the exception to be handled by the API (returns 500 or 400)
                raise e
# endregion

# region InterlayerConnections

    def get_interlayer_connections(self, collection_id:str, feature_id:str, 
                                 connected_layer_id:str=None, topo_type:str=None, 
                                 limit:int=10, offset:int=0):
        """
        Fetches connections for a feature.
        - connected_layer_id: Matches if the ID is in EITHER connectedLayerA OR connectedLayerB.
        - topo_type: Filters by specific topological expression (e.g. EQUALS, WITHIN).
        - limit/offset: Pagination.
        """
        response = {
            "layerConnections": [],
        }

        with self.connection.cursor() as cur:
            try:
                # 1. Get Context (Collection & Feature PKs)
                cur.execute("""
                    SELECT i.id 
                    FROM indoorfeature i
                    JOIN collection c ON i.collection_id = c.id
                    WHERE c.id_str = %s AND i.id_str = %s
                """, (collection_id, feature_id))
                
                res = cur.fetchone()
                if not res:
                    return {} # Return empty if feature not found

                feature_pk = res[0]

                # 2. Build Query
                # We include COUNT(*) OVER() to get the full count ignoring LIMIT
                sql = """
                    SELECT 
                        c.id_str, 
                        c.topo_type, 
                        c.comment,
                        l1.id_str as l1_id, l2.id_str as l2_id,
                        n1.id_str as n1_id, n2.id_str as n2_id,
                        cs1.id_str as c1_id, cs2.id_str as c2_id,
                        COUNT(*) OVER() as full_count
                    FROM interlayerconnection c
                    LEFT JOIN thematiclayer l1 ON c.connected_layer_a = l1.id
                    LEFT JOIN thematiclayer l2 ON c.connected_layer_b = l2.id
                    LEFT JOIN node_n_edge n1 ON c.connected_node_a = n1.id
                    LEFT JOIN node_n_edge n2 ON c.connected_node_b = n2.id
                    LEFT JOIN cell_space_n_boundary cs1 ON c.connected_cell_a = cs1.id
                    LEFT JOIN cell_space_n_boundary cs2 ON c.connected_cell_b = cs2.id
                    WHERE c.indoorfeature_id = %s
                """
                params = [feature_pk]

                # --- FILTER: Connected Layer ---
                if connected_layer_id:
                    # Check if the requested layer is EITHER side of the connection
                    sql += " AND (l1.id_str = %s OR l2.id_str = %s)"
                    params.extend([connected_layer_id, connected_layer_id])

                # --- FILTER: Topology Type ---
                if topo_type:
                    # We assume the input string matches the ENUM values (case-sensitivity depends on DB collation)
                    sql += " AND c.topo_type = %s"
                    params.append(topo_type.lower())

                # --- PAGINATION ---
                sql += " ORDER BY c.id ASC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
                
                # Handle empty results
                if not rows:
                    return {}
                
                for row in rows:
                    # Build lists, filtering out None values (e.g. connections might only link Layers, not Nodes)
                    layers = [x for x in [row[3], row[4]] if x]
                    nodes = [x for x in [row[5], row[6]] if x]
                    cells = [x for x in [row[7], row[8]] if x]

                    conn_obj = {
                        "id": row[0],
                        "featureType": "InterLayerConnection",
                        "typeOfTopoExpression": row[1],
                        "comment": row[2] or "",
                        "connectedLayers": layers,
                        "connectedNodes": nodes,
                        "connectedCells": cells
                    }
                    response["layerConnections"].append(conn_obj)
            except Exception as e:
                LOGGER.debug(e)
                raise e
                
        return response

    def post_interlayer_connection(self, collection_id:str, feature_id:str, data):
        """
        Creates a connection.
        UPDATED: Implements Supervisor's "Direct SQL Check" to prevent duplicates 
        within the same Feature scope.
        """
        
        new_id_str = data.get('id')
        topo = data.get('typeOfTopoExpression', 'others').lower()
        comment = data.get('comment', '')
        
        layers = data.get('connectedLayers', [])
        nodes = data.get('connectedNodes', [])
        cells = data.get('connectedCells', [])

        l1_str, l2_str = (layers[0], layers[1]) if len(layers) >= 2 else (None, None)
        n1_str, n2_str = (nodes[0], nodes[1]) if len(nodes) >= 2 else (None, None)
        c1_str, c2_str = (cells[0], cells[1]) if len(cells) >= 2 else (None, None)

        
        with self.connection.cursor() as cur:
            try:
                # 1. Resolve Context (Collection & Feature)
                cur.execute("SELECT id FROM collection WHERE id_str = %s", (collection_id,))
                res = cur.fetchone()
                if not res: raise Exception("Collection not found")
                coll_pk = res[0]

                cur.execute("SELECT id FROM indoorfeature WHERE id_str = %s AND collection_id = %s", (feature_id, coll_pk))
                res = cur.fetchone()
                if not res: raise Exception("Feature not found")
                feat_pk = res[0]

                # ---------------------------------------------------------
                # 2. SUPERVISOR FIX: Manual Duplicate Check
                # Since 'id_str' is no longer UNIQUE in the DB schema,
                # we must check if this ID exists *inside this specific feature*.
                # ---------------------------------------------------------
                check_dup = """
                    SELECT 1 FROM interlayerconnection 
                    WHERE id_str = %s AND indoorfeature_id = %s
                """
                cur.execute(check_dup, (new_id_str, feat_pk))
                if cur.fetchone():
                    LOGGER.warning(f"Duplicate Connection ID {new_id_str} rejected.")
                    return None # Or raise Exception("ID already exists in this feature")
                
                

                # 3. Helper for Scoped Lookup (Same as before)
                def get_scoped_id(table, id_str, parent_col_name, parent_pk):
                    if not id_str: return None
                    query = f"SELECT id FROM {table} WHERE id_str = %s AND {parent_col_name} = %s"
                    cur.execute(query, (id_str, parent_pk))
                    res = cur.fetchone()
                    return res[0] if res else None

                # 4. Resolve Foreign Keys
                l1_pk = get_scoped_id('thematiclayer', l1_str, 'indoorfeature_id', feat_pk)
                l2_pk = get_scoped_id('thematiclayer', l2_str, 'indoorfeature_id', feat_pk)
                n1_pk = get_scoped_id('node_n_edge', n1_str, 'indoorfeature_id', feat_pk)
                n2_pk = get_scoped_id('node_n_edge', n2_str, 'indoorfeature_id', feat_pk)
                c1_pk = get_scoped_id('cell_space_n_boundary', c1_str, 'indoorfeature_id', feat_pk)
                c2_pk = get_scoped_id('cell_space_n_boundary', c2_str, 'indoorfeature_id', feat_pk)

                if (n1_pk and n2_pk) and (c1_pk and c2_pk):
                    check_duality_sql = """
                        SELECT (
                            EXISTS(SELECT 1 FROM cell_space_n_boundary WHERE id = %s AND duality = %s)
                            AND
                            EXISTS(SELECT 1 FROM cell_space_n_boundary WHERE id = %s AND duality = %s)
                        ) AS both_valid;
                    """
                    cur.execute(check_duality_sql, (c1_pk, n1_pk, c2_pk, n2_pk))
                    is_valid = cur.fetchone()[0]  # Returns True or False

                    if is_valid:
                        LOGGER.debug("Both pairs are valid dualities.")
                    else:
                        msg = "Duality of one or both pairs is invalid"
                        LOGGER.debug(msg)
                        raise ValueError(msg)
                # 5. Insert
                insert_query = """
                    INSERT INTO interlayerconnection 
                    (id_str, collection_id, indoorfeature_id, 
                     connected_layer_a, connected_layer_b, 
                     connected_node_a, connected_node_b,
                     connected_cell_a, connected_cell_b,
                     topo_type, comment)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id_str
                """
                
                cur.execute(insert_query, (
                    new_id_str, coll_pk, feat_pk, 
                    l1_pk, l2_pk, 
                    n1_pk, n2_pk, 
                    c1_pk, c2_pk, 
                    topo, comment
                ))
                new_conn = cur.fetchone()[0]
                
                self.connection.commit()
                return new_conn

            except Exception as e:
                self.connection.rollback()
                LOGGER.error(f"DB Error: {e}")
                return None
        
    def delete_interlayer_connection(self, collection_id:str, feature_id:str, connection_id:str):
        """
        Deletes an InterLayerConnection.
        """
        query = """
            DELETE FROM interlayerconnection
            WHERE id_str = %s
              AND indoorfeature_id = (
                  SELECT id FROM indoorfeature 
                  WHERE id_str = %s 
                  AND collection_id = (SELECT id FROM collection WHERE id_str = %s)
              )
        """
        
        try:
            with self.connection.cursor() as cur:
                # We pass the arguments: connection_id, item_str (IndoorFeature), collection_str
                cur.execute(query, (connection_id, feature_id, collection_id))
                
                if cur.rowcount == 0:
                    self.connection.rollback()
                    return False
                
                self.connection.commit()
                return True
                
        except Exception as e:
            if self.connection:
                self.connection.rollback()
            print(f"Delete Connection Error: {e}")
            return False
# endregion

# region PrimalSpaceLayer
            
    def get_primal_members(self, collection_id:str, feature_id:str, layer_id:str, 
                                         level:str=None, poi:str=None, is_virtual:str=None, cell_space_name:str=None):
        """
        1. Resolves layer metadata.
        2. Fetches Spaces (Filtered by level, poi, name).
        3. Fetches Boundaries (Filtered by is_virtual AND parent Spaces).
        Returns: layer_row, spaces_list, boundaries_list
        """
        with self.connection.cursor() as cur:
            # STEP 1: Fetch Layer Metadata
            layer_query = """
                SELECT 
                    t.id, 
                    t.primalspace_id_str, 
                    t.p_creation_datetime, 
                    t.p_termination_datetime
                FROM thematiclayer t
                JOIN collection c ON t.collection_id = c.id
                JOIN indoorfeature i ON t.indoorfeature_id = i.id
                WHERE t.id_str = %s AND c.id_str = %s AND i.id_str = %s
            """
            cur.execute(layer_query, (layer_id, collection_id, feature_id))
            layer_row = cur.fetchone()

            if not layer_row:
                return {}

            layer_pk = layer_row[0]

            primal_space = {
                "id": layer_row[1], 
                "featureType": "PrimalSpaceLayer",
                "creationDatetime": layer_row[2],
                "terminationDatetime": layer_row[3],
                "cellSpaceMember": [],
                "cellBoundaryMember": []
            }
            
            # STEP 2: Fetch Spaces (with Filters)
            spaces_query = """
                SELECT 
                    cs.id, cs.id_str, cs.cell_name, cs.level, cs.poi, 
                    cs.external_reference,
                    cs.bounded_by_cell_id,
                    ST_AsText(cs."2D_geometry") as geom_wkt, 
                    cs."3D_geometry" as geom_3d,
                    ne.id_str as duality,
                    (
                    SELECT array_agg(child.id_str)
                    FROM cell_space_n_boundary child
                    WHERE child.bounded_by_cell_id = cs.id
                    ) as bounded_by_list
                FROM cell_space_n_boundary cs
                LEFT JOIN node_n_edge ne ON cs.duality_id = ne.id
                WHERE cs.thematiclayer_id = %s AND cs.type = 'space'
            """
            spaces_params = [layer_pk]

            # --- Apply Space Filters ---
            if level:
                spaces_query += " AND cs.level = %s"
                spaces_params.append(level)
            
            if poi:
                spaces_query += " AND cs.poi = %s"
                spaces_params.append(poi.lower())

            if cell_space_name:
                spaces_query += " AND cs.cell_name ILIKE %s"                
                spaces_params.append(f"%{cell_space_name}%")
            
            cur.execute(spaces_query, tuple(spaces_params))
            space_rows = cur.fetchall()
            all_referenced_boundaries = set()

            for row in space_rows:
                if row['bounded_by_list']:
                    all_referenced_boundaries.update(row['bounded_by_list'])
                geom_2d = self.wkt_to_json(row['geom_wkt'])
                cell = {
                        "id": row['id_str'],
                        "featureType": "CellSpace",
                        "cellSpaceName": row['cell_name'],
                        "level": row['level'],
                        "poi": row['poi'] if row['poi'] else False,
                        "duality": row['duality'],
                        "cellSpaceGeom": {
                            "geometry2D": geom_2d,
                            "geometry3D": row['geom_3d']
                        },
                        "boundedBy": row['bounded_by_list']
                    }
                if row['external_reference']: cell["externalReference"] = row['external_reference']
                primal_space["cellSpaceMember"].append(cell)

            boundary_id_list = list(all_referenced_boundaries)

            # Fetch Boundaries (Dependent on Spaces)
            boundary_query = """
                SELECT c.id, c.id_str, c.external_reference, 
                ST_AsText(c."2D_geometry", 0) as geom_wkt, c."3D_geometry" as geom_3d, n.id_str as duality, c.is_virtual
                FROM cell_space_n_boundary c
                LEFT JOIN node_n_edge n ON c.duality_id = n.id
                WHERE c.thematiclayer_id = %s
            """
            boundary_params = [layer_pk]
            # if cell spaces are filtered, select only its bounded by boundaries.
            if level or poi or cell_space_name:
                boundary_query += " AND c.id_str = ANY(%s)"
                boundary_params.append(boundary_id_list)

            if is_virtual:
                boundary_query += " AND c.is_virtual = %s"
                boundary_params.append(is_virtual.lower())

            cur.execute(boundary_query, tuple(boundary_params))
            boundary_rows = cur.fetchall() 

            for row in boundary_rows:
                boundary = {
                    "id": row['id_str'],
                    "featureType": "CellBoundary",
                    "duality": row['duality'],
                    "isVirtual": row['is_virtual'],
                    "cellBoundaryGeom": {
                        "geometry2D": self.wkt_to_json(row['geom_wkt']),
                        "geometry3D": row['geom_3d']
                    }
                }
                if row['external_reference']: boundary["externalReference"] = {"uri": row['external_reference']}
                primal_space["cellBoundaryMember"].append(boundary)
        
            return primal_space
        
    # Creates a CellSpace or CellBoundary member in the specified layer.
    def post_primal_member(self, collection_id:str, feature_id:str, layer_id:str, data):
        with self.connection.cursor() as cur:
            try:  
                # --- A. Lookup Context ---
                lookup_sql = """
                    SELECT t.id, t.collection_id, t.indoorfeature_id 
                    FROM thematiclayer t
                    JOIN collection c ON t.collection_id = c.id
                    JOIN indoorfeature i ON t.indoorfeature_id = i.id
                    WHERE t.id_str = %s and c.id_str = %s and i.id_str = %s
                """
                cur.execute(lookup_sql, (layer_id, collection_id, feature_id))
                layer_row = cur.fetchone()
                
                if not layer_row:
                    LOGGER.debug(f"Layer context not found for {layer_id}")
                    return None

                duplicate_sql = """
                    SELECT id_str 
                    FROM node_n_edge
                    WHERE indoorfeature_id = %s and id_str = %s
                """
                cur.execute(duplicate_sql, (layer_row[2], data.get('id')))
                row = cur.fetchone()
                if row:
                    LOGGER.debug(f"Invalid data value: {data.get('id')} is already exist.")
                    return None

                # --- B. Parse Data ---
                f_type = data.get('featureType')
                id_str = data.get('id')
                external_ref = json.dumps(data.get('externalReference')) if data.get('externalReference') else None
                
                # Safe integer conversion for duality
                duality_raw = data.get('duality')

                db_type = None
                cell_name = None
                level = None
                poi = None
                is_virtual = None
                geom_2d_wkt = None
                geom_3d_json = None 
                update_bounded_by = []
                duality_edge_pk = None   # Cellspace can't create new duality to exsiting node, because existing node with no duality is invalid.

                if f_type == 'CellSpace':
                    db_type = 'space'
                    cell_name = data.get('cellSpaceName')
                    level = data.get('level')
                    poi = data.get('poi', False)
                    bounded_by_refs = []
                    raw_bounds = data.get('boundedBy', [])
                    for b_ref in raw_bounds:
                        bounded_by_refs.append(b_ref.split(':')[-1])  # if the form is 'a:b:c'

                    # --- C. Validation ---
                    if bounded_by_refs:
                        unique_refs = list(set(bounded_by_refs))
                        check_sql = """
                            SELECT id, id_str, bounded_by_cell_id
                            FROM cell_space_n_boundary 
                            WHERE id_str = ANY(%s) 
                              AND thematiclayer_id = %s
                              AND type = 'boundary'
                        """
                        cur.execute(check_sql, (unique_refs, layer_row[0]))
                        rows = cur.fetchall()
                        
                        if len(rows) != len(unique_refs):
                            LOGGER.debug(f"Validation Failed: Missing boundaries in layer {layer_id}")
                            return None 
                        else: # validation check: CellBoundary can bound only if it bounds nothing
                            for row in rows:
                                if row[2]:
                                    LOGGER.debug(f"Validation Failed: Bounding boundary {row['id_str']} already bounds another cellSpace.")
                                    return None
                                else:
                                    update_bounded_by.append(row[0])

                    geom_root = data.get('cellSpaceGeom', {})
                    geom_2d_wkt = self.json_to_wkt(geom_root['geometry2D'])
                    geom_3d_json = json.dumps(geom_root['geometry3D'])
                
                elif f_type == 'CellBoundary':
                    db_type = 'boundary'
                    is_virtual = data.get('isVirtual', False)
                    geom_root = data.get('cellBoundaryGeom', {})
                    geom_2d_wkt = self.json_to_wkt(geom_root.get('geometry2D'))
                    geom_3d_json = json.dumps(geom_root.get('geometry3D'))

                    if duality_raw:  # validation check: CellBoundary can have duality to edge which has no duality
                        duality_id = duality_raw.split(':')[-1]
                        sql_duality = """
                            SELECT id, duality_id 
                            FROM node_n_edge
                            WHERE thematiclayer_id=%s AND id_str=%s
                        """
                        cur.execute(sql_duality, (layer_row[0], duality_id))
                        row = cur.fetchone()

                        if not row:
                            LOGGER.debug(f"Validation Failed: Duality edge {duality_id} is not found")
                            return None
                        elif row[1]:
                            LOGGER.debug(f"Validation Failed: Duality edge {duality_id} already has a duality")
                            return None
                        duality_edge_pk = row[0]        
                else:
                    LOGGER.debug(f"Invalid member type: {f_type}")
                    return None 

                # --- D. Insert ---
                insert_query = """
                    INSERT INTO cell_space_n_boundary (
                        id_str, type, collection_id, indoorfeature_id, thematiclayer_id,
                        "2D_geometry", "3D_geometry", 
                        cell_name, level, poi, is_virtual, external_reference, duality_id
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        ST_GeomFromText(%s, 0), 
                        %s,
                        %s, %s, %s, %s, %s, %s
                    ) RETURNING id, id_str
                """
                
                cur.execute(insert_query, (
                    id_str, db_type, layer_row[1], layer_row[2], layer_row[0],
                    geom_2d_wkt, geom_3d_json,
                    cell_name, level, poi, is_virtual, external_ref, duality_edge_pk
                ))
                
                new_row = cur.fetchone()
                new_internal_id = new_row[0]
                new_str_id = new_row[1]

                # --- E. Link Boundaries ---
                if f_type == 'CellSpace' and update_bounded_by:
                    update_boundaries_sql = """
                        UPDATE cell_space_n_boundary
                        SET bounded_by_cell_id = %s
                        WHERE id = ANY(%s) 
                          AND thematiclayer_id = %s
                    """
                    cur.execute(update_boundaries_sql, (
                        new_internal_id, 
                        update_bounded_by,
                        layer_row[0]
                    ))
                if f_type == 'CellBoundary' and duality_edge_pk:
                    update_edgeDuality_sql = """
                        UPDATE node_n_edge
                        SET duality_id = %s
                        WHERE id = %s
                    """
                    cur.execute(update_edgeDuality_sql, (new_internal_id, duality_edge_pk))

                # project cellspace's 3D geometry to 2D if it has no 2D geometry.
                LOGGER.debug("Project geometry 3D to 2D ")
                sql_projection = """
                    UPDATE cell_space_n_boundary c
                    SET "2D_geometry" = sub.footprint
                    FROM (
                        SELECT 
                            id, 
                            ST_AsText(
                                ST_UnaryUnion(
                                    ST_Collect(
                                        ST_Force2D(
                                            ST_GeomFromGeoJSON(
                                                jsonb_build_object(
                                                    'type', 'Polygon',
                                                    'coordinates', jsonb_build_array(face_element) 
                                                )
                                            )
                                        )
                                    )
                                )
                            ) AS footprint
                        FROM cell_space_n_boundary,
                            jsonb_array_elements("3D_geometry"->'coordinates'->0) AS face_element
                        WHERE "3D_geometry" IS NOT NULL AND type='space' AND "2D_geometry" IS NULL AND id = %s
                        GROUP BY id
                    ) sub
                    WHERE c.id = sub.id;
                """
                cur.execute(sql_projection,(new_internal_id,))
                # 4. FIX: Commit only if we get here successfully
                self.connection.commit()
                return new_str_id

            except Exception as e:
                # 5. FIX: Rollback on any error (lookup, validation, or insert)
                self.connection.rollback()
                LOGGER.debug(f"Insert Error: {e}")
                raise e
            
    def delete_primal_member(self, collection_id:str, feature_id:str, layer_id:str, member_id:str):
        """
        Deletes a CellSpace.
        1. Finds the Dual Node.
        2. Breaks connections in 'connects' table (Topological Delete).
        3. KEEPS the Edge features (Geometric Preservation).
        4. Deletes the Node and CellSpace.
        """
        
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # --- STEP A: Verify member Existence ---
                check_sql = """
                    SELECT c.id, c.type
                    FROM cell_space_n_boundary c
                    JOIN collection col ON c.collection_id = col.id
                    JOIN indoorfeature i ON c.indoorfeature_id = i.id
                    JOIN thematiclayer t ON c.thematiclayer_id = t.id
                    WHERE c.id_str = %s AND t.id_str = %s AND col.id_str = %s AND i.id_str = %s
                    
                """
                cur.execute(check_sql, (member_id, layer_id, collection_id, feature_id))
                row = cur.fetchone()
                
                if not row:
                    LOGGER.debug(f"Not Found error: {member_id} is not found.")
                    return False
                
                if row['type'] == 'space': # if member type is space..
                
                    space_id = row['id']

                    # --- STEP B: Find the Dual Node ---  
                    # When cell space is deleted, its duality node is also deleted.
                    dual_sql = "SELECT id FROM node_n_edge WHERE duality_id = %s"
                    cur.execute(dual_sql, (space_id,))
                    node_row = cur.fetchone()
                    node_id = node_row['id'] if node_row else None
                    if node_id:
                        # 1. Delete Interlayer Connections
                        cur.execute("""
                            DELETE FROM interlayerconnection 
                            WHERE connected_node_a = %s OR connected_node_b = %s
                        """, (node_id, node_id))

                        # 2. Find Connected Edges
                        cur.execute("""
                            SELECT edge_id FROM connects 
                            WHERE node_source_id = %s OR node_target_id = %s
                        """, (node_id, node_id))
                        rows = cur.fetchall()
                        if rows:
                            LOGGER.debug(rows)
                            edge_ids = [r['edge_id'] for r in rows]

                        if edge_ids:
                            # 3. Delete connects, node and edges
                            # We delete the row from 'connects' because it references the node we are about to kill.
                            cur.execute("DELETE FROM connects WHERE edge_id = ANY(%s)", (edge_ids,))
                            # update boudaries duality before delete edges
                            cur.execute("""
                                UPDATE cell_space_n_boundary 
                                SET duality_id = NULL 
                                WHERE duality_id = ANY(%s)
                            """, (edge_ids,))
                            # Delete edges connected with target node
                            cur.execute("DELETE FROM node_n_edge WHERE id=ANY(%s)", (edge_ids,))

                        # update duality before delete node.
                        cur.execute("""
                                UPDATE cell_space_n_boundary 
                                SET duality_id = NULL 
                                WHERE id = %s
                            """, (space_id,))   
                        # 4. Delete the Node
                        cur.execute("DELETE FROM node_n_edge WHERE id = %s", (node_id,))

                    # --- STEP C: Unlink Boundaries ---
                    cur.execute("""
                        UPDATE cell_space_n_boundary 
                        SET bounded_by_cell_id = NULL 
                        WHERE bounded_by_cell_id = %s
                    """, (space_id,))

                    # Delete connected interlayerconnection
                    cur.execute("""
                        DELETE FROM interlayerconnection 
                        WHERE connected_cell_a = %s OR connected_cell_b = %s
                    """, (space_id, space_id))  

                    # --- STEP D: Delete the Space ---
                    cur.execute("DELETE FROM cell_space_n_boundary WHERE id = %s", (space_id,))
                else:  # if member type is boundary...
                    boundary_id = row['id']
                    
                    # update edge duality before delete boundary
                    cur.execute("""
                        UPDATE node_n_edge
                        SET duality_id = NULL
                        WHERE duality_id = %s
                        """, (boundary_id,))
                    # delete boundary
                    cur.execute("DELETE FROM cell_space_n_boundary WHERE id = %s", (boundary_id,))

                self.connection.commit()
                return True

            except Exception as e:
                self.connection.rollback()
                LOGGER.debug(f"Delete Primal Error: {e}")
                return False
        
    def get_primal_member(self, collection_id:str, feature_id:str, layer_id:str, member_id:str):
        """
        Fetches a single Primal Member.
        Ensures SQL alias 'duality' matches API handler expectations.
        """
        sql = """
            SELECT c.id, c.id_str, c.type, c.cell_name, c.level, c.poi, c.is_virtual, 
                c.external_reference,
                ST_AsText(c."2D_geometry") as geometry_2d, 
                c."3D_geometry" as geometry_3d,
                n.id_str as duality_id, 
                (
                    SELECT array_agg(child.id_str)
                    FROM cell_space_n_boundary child
                    WHERE child.bounded_by_cell_id = c.id
                ) as bounded_by_list
            FROM cell_space_n_boundary c
            LEFT JOIN node_n_edge n ON c.duality_id = n.id
            JOIN collection col ON c.collection_id = col.id
            JOIN indoorfeature i ON c.indoorfeature_id = i.id
            JOIN thematiclayer t ON c.thematiclayer_id = t.id
            WHERE c.id_str = %s AND t.id_str = %s AND col.id_str = %s AND i.id_str = %s
        """
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # Ensure params match SQL order: member, layer, item, collection
                cur.execute(sql, (member_id, layer_id, collection_id, feature_id))
                result = cur.fetchone()
                
                if not result:
                    LOGGER.debug(f"Not Found {member_id}")
                    return None
                if not result.get('bounded_by_list'):
                    result['bounded_by_list'] = []
            
                response = {}
                # if member type is cell space
                if result['type'] == 'space':
                    response = {
                        "id": result['id_str'],
                        "featureType": "CellSpace",
                        "cellSpaceName": result.get('cell_name'),
                        "level": result.get('level'),
                        "poi": result.get('poi', False),
                        "duality": result.get('duality_id'),
                        "cellSpaceGeom": {
                            "geometry2D": self.wkt_to_json(result['geometry_2d']),
                            "geometry3D": result.get('geometry_3d')
                        },
                        "externalReference": result.get('external_reference'),
                        # Convert the list of IDs ["B1", "B2"] to URI refs ["#B1", "#B2"]
                        "boundedBy": result.get('bounded_by_list', [])
                    }
                
                elif result['type'] == 'boundary':
                    response = {
                        "id": result['id_str'],
                        "featureType": "CellBoundary",
                        "isVirtual": result.get('is_virtual', False),
                        "duality": result.get('duality_id'),
                        "cellBoundaryGeom": {
                            "geometry2D": self.wkt_to_json(result.get('geometry_2d')),
                            "geometry3D": result.get('geometry_3d')
                        },
                        "externalReference": result.get('external_reference')
                    }
                return response 
                
            except Exception as e:
                LOGGER.debug(f"Get Member Error: {e}")
                return None

    def patch_cell_space(self, collection_id:str, feature_id:str, layer_id:str, cellspace_id:str, data):
        """
        Updates a CellSpace. 
        Strictly ignores Geometry, level and external_reference updates. duality
        Allows updating: cell_name, poi, and boundedBy.
        Modifying: patch 'level' is also disallowed.
        """
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # --- A. Resolve Parent Layer IDs ---
                lookup_sql = """
                    SELECT t.id 
                    FROM thematiclayer t
                    JOIN collection col ON t.collection_id = col.id
                    JOIN indoorfeature i ON t.indoorfeature_id = i.id
                    WHERE t.id_str = %s AND i.id_str = %s AND col.id_str = %s
                """
                cur.execute(lookup_sql, (layer_id, feature_id, collection_id))
                layer_row = cur.fetchone()
                
                if not layer_row:
                    LOGGER.debug(f"Not found {layer_id}")
                    return False 

                # --- B. Check Member Existence ---
                # We also verify it is a 'space' here
                check_sql = "SELECT id FROM cell_space_n_boundary WHERE id_str = %s AND thematiclayer_id = %s AND type = 'space'"
                cur.execute(check_sql, (cellspace_id, layer_row['id']))
                target_row = cur.fetchone()

                if not target_row:
                    LOGGER.debug(f"{cellspace_id} is not found or not cell space.")
                    return False 

                cellspace_pk = target_row['id']
                
                # --- C. Dynamic Field Construction ---
                fields = []
                values = []
                forbidden_keys = {'cellSpaceGeom', 'duality', 'external_reference', 'level'}
                
                if not forbidden_keys.isdisjoint(data):
                    LOGGER.debug("Invalid body value: Found forbidden keys.")
                    return False

                # Handle client typo/legacy support
                if 'cellSpaceName' in data: 
                    fields.append("cell_name = %s")
                    values.append(data['cellSpaceName'])
                    
                if 'poi' in data:
                    fields.append("poi = %s")
                    values.append(data['poi'].lower())

                # execute Update if we have fields
                if fields:
                    update_sql = f"UPDATE cell_space_n_boundary SET {', '.join(fields)} WHERE id = %s"
                    values.append(cellspace_pk)
                    cur.execute(update_sql, tuple(values))

                # --- D. Handle 'boundedBy' Relationship ---
                raw_bounds = []
                if 'boundedBy' in data:
                    for bounds in data['boundedBy']:
                        raw_bounds.append(bounds.split(':')[-1]) # e.g., ["a:b:c"]
                    # 1. Validation: Ensure all new boundaries exist
                    if raw_bounds:
                        check_refs = list(set(raw_bounds))
                        bounded_sql = """
                            SELECT  id, bounded_by_cell_id, id_str FROM cell_space_n_boundary 
                            WHERE id_str = ANY(%s) AND thematiclayer_id = %s AND type = 'boundary'
                        """
                        cur.execute(bounded_sql, (check_refs, layer_row['id']))
                        rows = cur.fetchall()
                        if len(rows) != len(check_refs):
                            # Rollback is handled by the except block below
                            print("Validation Failed: One or more boundaries do not exist.")
                            raise ValueError("Invalid Boundary References")
                        else:
                            for row in rows:  # if boundary already bounds another cell space, error is occured.
                                if row['bounded_by_cell_id'] and row['bounded_by_cell_id']!=cellspace_pk:
                                    LOGGER.debug(f"{row['id_str']} already bounds another cell space.")
                                    raise ValueError(f"Invalid boundedBy data: {row['id_str']}")
                        # update new bounded by cell id
                        link_new_sql = """
                            UPDATE cell_space_n_boundary
                            SET bounded_by_cell_id = %s
                            WHERE id_str = ANY(%s) AND thematiclayer_id = %s
                        """
                        cur.execute(link_new_sql, (cellspace_pk, raw_bounds, layer_row['id']))

                self.connection.commit()
                return True

            except Exception as e:
                self.connection.rollback()
                print(f"Update failed: {e}")
                return False

# endregion

# region DualSpaceLayer 

    def post_dual_member(self, collection_id:str, feature_id:str, layer_id:str, data): 
        """
        Create a single Node or Edge. 
        The created data id_str has to be unique in thematiclayer.
        """
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            try:    
                # --- Resolve Layer Context ---
                lookup_sql = """
                    SELECT t.id, t.collection_id, t.indoorfeature_id 
                    FROM thematiclayer t
                    JOIN collection c ON t.collection_id = c.id
                    JOIN indoorfeature i ON t.indoorfeature_id = i.id
                    WHERE t.id_str = %s and c.id_str = %s and i.id_str = %s
                """
                cur.execute(lookup_sql, (layer_id, collection_id, feature_id))
                layer_row = cur.fetchone()
                if not layer_row: 
                    LOGGER.debug("Layer not found.")
                    return None
                
                f_type = data.get('featureType')
                id_str = data.get('id')
                duplicate_sql = """
                    SELECT id_str
                    FROM cell_space_n_boundary 
                    WHERE indoorfeature_id = %s AND id_str = %s
                """
                cur.execute(duplicate_sql, (layer_row['indoorfeature_id'], id_str))
                row = cur.fetchone()
                if row:
                    LOGGER.debug(f"{id_str} is already exist.")
                    return None
                
                geom_wkt = self.json_to_wkt(data.get('geometry'))

                # ============================
                # CASE A: NODE
                # ============================
                if f_type == 'Node':
                    duality_ref = data.get('duality') 
                    
                    if not duality_ref:
                        raise ValueError("Node must have a 'duality' reference to a CellSpace.")

                    clean_duality = duality_ref.split(':')[-1]

                    # 1. Verify Duality Target (Must be a Space)
                    check_space_sql = """
                        SELECT id, duality_id FROM cell_space_n_boundary 
                        WHERE id_str = %s AND thematiclayer_id = %s AND type = 'space'
                    """
                    cur.execute(check_space_sql, (clean_duality, layer_row['id']))
                    space_row = cur.fetchone()
                    
                    if not space_row:
                        raise ValueError(f"Duality target '{clean_duality}' does not exist or is not a CellSpace.")
                    elif space_row['duality_id'] != None:
                        raise ValueError(f"Duality target '{clean_duality}' already has a duality.")
                    
                    space_id = space_row['id']

                    # 2. Insert Node
                    insert_node_sql = """
                        INSERT INTO node_n_edge (
                            id_str, type, collection_id, indoorfeature_id, thematiclayer_id,
                            geometry_val, duality_id
                        ) VALUES (
                            %s, 'node', %s, %s, %s,
                            ST_GeomFromText(%s, 0), %s
                        ) RETURNING id, id_str
                    """
                    cur.execute(insert_node_sql, (
                        id_str, layer_row['collection_id'], layer_row['indoorfeature_id'], layer_row['id'],
                        geom_wkt, space_id
                    ))
                    new_node = cur.fetchone()

                    # 3. Reverse Link: Update Space -> Point to Node
                    update_space_sql = "UPDATE cell_space_n_boundary SET duality_id = %s WHERE id = %s"
                    cur.execute(update_space_sql, (new_node['id'], space_id))
                    
                    self.connection.commit()
                    return new_node['id_str']

                # ============================
                # CASE B: EDGE
                # ============================
                elif f_type == 'Edge':
                    connects = data.get('connects')
                    if not connects or len(connects) != 2:
                        raise ValueError("Edge must connect exactly two Nodes.")

                    # 1. Duality is Optional for Edges
                    duality_ref = data.get('duality')
                    boundary_id = None
                    
                    if duality_ref:
                        clean_duality = duality_ref.split(':')[-1]
                        # Check if Boundary exists
                        check_bound_sql = """
                            SELECT id, duality_id FROM cell_space_n_boundary 
                            WHERE id_str = %s AND thematiclayer_id = %s AND type = 'boundary'
                        """
                        cur.execute(check_bound_sql, (clean_duality, layer_row['id']))
                        bound_row = cur.fetchone()
                        
                        if not bound_row:
                            raise ValueError(f"Duality target '{clean_duality}' does not exist or is not a CellBoundary.")
                        elif bound_row['duality_id'] != None:
                            raise ValueError(f"Duality target '{clean_duality}' already has a duality.")

                        boundary_id = bound_row['id']

                    # 2. Resolve Connected Nodes (Handling Directionality!)
                    ref_source = connects[0].split(':')[-1]
                    ref_target = connects[1].split(':')[-1]
                    
                    check_nodes_sql = "SELECT id, id_str FROM node_n_edge WHERE id_str = ANY(%s) AND thematiclayer_id = %s AND type = 'node'"
                    cur.execute(check_nodes_sql, ([ref_source, ref_target], layer_row['id']))
                    node_rows = cur.fetchall() # Returns list of dicts

                    if len(node_rows) != 2:
                        msg = "One or both connected nodes do not exist."
                        LOGGER.debug(msg)
                        raise ValueError(msg)

                    # FIX: Map ID_STR to Internal ID to preserve order (Source vs Target)
                    id_map = {row['id_str']: row['id'] for row in node_rows}
                    source_id = id_map[ref_source]
                    target_id = id_map[ref_target]

                    # 3. Insert Edge
                    insert_edge_sql = """
                        INSERT INTO node_n_edge (
                            id_str, type, collection_id, indoorfeature_id, thematiclayer_id,
                            geometry_val, weight, duality_id
                        ) VALUES (
                            %s, 'edge', %s, %s, %s,
                            ST_GeomFromText(%s, 0), %s, %s
                        ) RETURNING id, id_str
                    """
                    if not data.get('weight') or float(data.get('weight')) < 0: 
                        msg = "weight is required and cannot be negative."
                        LOGGER.debug(msg)
                        raise ValueError(msg)
                    cur.execute(insert_edge_sql, (
                        id_str, layer_row['collection_id'], layer_row['indoorfeature_id'], layer_row['id'],
                        geom_wkt, data.get('weight', 0.0), boundary_id
                    ))
                    new_edge = cur.fetchone()

                    # 4. Insert 'connects' Link
                    insert_link_sql = "INSERT INTO connects (node_source_id, node_target_id, edge_id) VALUES (%s, %s, %s)"
                    cur.execute(insert_link_sql, (source_id, target_id, new_edge['id']))
                    
                    # 5. Reverse Link (If duality existed)
                    if boundary_id:
                        update_bound_sql = "UPDATE cell_space_n_boundary SET duality_id = %s WHERE id = %s"
                        cur.execute(update_bound_sql, (new_edge['id'], boundary_id))

                    self.connection.commit()
                    return new_edge['id_str']
                
                return None

            except Exception as e:
                self.connection.rollback()
                print(f"Dual Member Creation Error: {e}")
                # Re-raise so the API knows to return 400/500
                raise ValueError(f"Failed to create member: {str(e)}")

    def get_dual_members(self, collection_id:str, feature_id:str, layer_id:str, min_weight:float=None, max_weight:float=None):
        """
        1. Fetches Layer Metadata.
        2. Fetches Members (Nodes & Edges).
           - EDGES are filtered by min_weight/max_weight.
           - Only Nodes connected to Edges when filtered.
                All Nodes when Edges are not filtered.
        3. Fetches Topology (Connections) and maps them.
        Returns: meta_row, nodes_list, edges_list
        """
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            try:    
                # STEP 1: Layer Metadata
                meta_query = """
                    SELECT 
                        t.id, t.id_str, t.dualspace_id_str,
                        t.d_creation_datetime, t.d_termination_datetime, t.is_logical, t.is_directed
                    FROM thematiclayer t
                    JOIN collection c ON t.collection_id = c.id
                    JOIN indoorfeature i ON t.indoorfeature_id = i.id
                    WHERE t.id_str = %s AND c.id_str = %s AND i.id_str = %s
                """
                cur.execute(meta_query, (layer_id, collection_id, feature_id))
                meta_row = cur.fetchone()

                if not meta_row:
                    LOGGER.debug("not found")
                    return {}
                
                response = {
                    "id": meta_row['dualspace_id_str'],
                    "featureType": "DualSpaceLayer",
                    "isLogical": meta_row['is_logical'], 
                    "isDirected": meta_row['is_directed'], 
                    "creationDatetime": meta_row['d_creation_datetime'],
                    "terminationDatetime": meta_row['d_termination_datetime']
                }

                layer_internal_id = meta_row['id']

                # STEP 2: Fetch Raw Members (Nodes & Edges)
                # We get the Duality String here via JOIN
                members_query = """
                    SELECT 
                        ne.id_str, 
                        ne.type, 
                        ne.weight, 
                        ST_AsText(ne.geometry_val) as geometry,
                        cs.id_str as duality
                    FROM node_n_edge ne
                    LEFT JOIN cell_space_n_boundary cs ON ne.duality_id = cs.id
                    WHERE ne.thematiclayer_id = %s
                """
                params = [layer_internal_id]

                # --- Apply Edge Filters ---
                # We use (type = 'node' OR ...) to ensure we don't hide the nodes 
                # even if they have no weight.
                
                if min_weight:
                    members_query += " AND (ne.type = 'node' OR ne.weight >= %s)"
                    params.append(min_weight)

                if max_weight:
                    members_query += " AND (ne.type = 'node' OR ne.weight <= %s)"
                    params.append(max_weight)
           
                cur.execute(members_query, tuple(params))
                member_rows = cur.fetchall()

                # STEP 3: Fetch Topology (The "Connects" Map)
                topo_query = """
                    SELECT 
                        edge.id_str as edge_ref,
                        src.id_str as source_ref,
                        tgt.id_str as target_ref
                    FROM connects c
                    JOIN node_n_edge edge ON c.edge_id = edge.id
                    JOIN node_n_edge src ON c.node_source_id = src.id
                    JOIN node_n_edge tgt ON c.node_target_id = tgt.id
                    WHERE edge.thematiclayer_id = %s
                """
                cur.execute(topo_query, (layer_internal_id,))
                topo_rows = cur.fetchall()

                # --- STEP 4: Build Aggregation Maps ---
                node_connections = {} 
                edge_connections = {}

                for row in topo_rows:
                    e_ref = row['edge_ref']
                    s_ref = row['source_ref']
                    t_ref = row['target_ref']

                    edge_connections[e_ref] = [s_ref, t_ref]

                    if s_ref not in node_connections: node_connections[s_ref] = []
                    node_connections[s_ref].append(e_ref)
                    
                    if t_ref not in node_connections: node_connections[t_ref] = []
                    node_connections[t_ref].append(e_ref)

                # --- STEP 5: Sort Members ---
                nodes = []
                edges = []

                valid_edge_ids = set()
                touched_node_ids = set()

                for row in member_rows:
                    if row['type'] == 'edge':
                        e_id = row['id_str']
                        valid_edge_ids.add(e_id)
                        # Add the nodes connected to this specific edge to the 'touched' set
                        if e_id in edge_connections:
                            touched_node_ids.update(edge_connections[e_id])

                # B. Determine if we are in "Filtering Mode"
                filtering_active = (min_weight) or (max_weight)

                # C. Build Final Lists
                for row in member_rows:
                    mid = row['id_str']
                    geom = self.wkt_to_json(row['geometry'])
                    
                    # --- PROCESSING EDGE ---
                    if row['type'] == 'edge':
                        # Edges in member_rows are already filtered by SQL. Just add them.
                        obj = {
                            "id": mid,
                            "featureType": "Edge",
                            "duality": row['duality'],
                            "geometry": geom,
                            "weight": row['weight'] if row['weight'] else 0.0,
                            "connects": edge_connections.get(mid, [])
                        }
                        edges.append(obj)
                    
                    # --- PROCESSING NODE ---
                    elif row['type'] == 'node':
                        # 1. Filter Logic:
                        # If filtering is ON, we skip nodes that aren't in 'touched_node_ids'
                        if filtering_active and mid not in touched_node_ids:
                            continue 
                        
                        # 2. Cleanup Logic:
                        # Ensure the 'connects' list only contains edges that actually exist in our response
                        full_connects = node_connections.get(mid, [])
                        valid_connects = [e for e in full_connects if e in valid_edge_ids]

                        obj = {
                            "id": mid,
                            "featureType": "Node",
                            "duality": row['duality'],
                            "geometry": geom,
                            "connects": valid_connects
                        }
                        nodes.append(obj)

                response["nodeMember"] = nodes
                response["edgeMember"] = edges
               
                return response

            except Exception as e:
                print(f"Dual Layer Error: {e}")
                return None
            
    def get_dual_member(self, collection_id:str, feature_id:str, layer_id:str, member_id:str):
        """
        Fetches a SINGLE Node or Edge.
        1. Resolves Duality String.
        2. IF EDGE: Fetches Source/Target via JOIN.
        3. IF NODE: Fetches Connected Edges via SUBQUERY.
        """
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            try:    
                query = """
                    SELECT 
                        ne.id_str, 
                        ne.type, 
                        ne.weight, 
                        ST_AsText(ne.geometry_val) as geometry,
                        cs.id_str as duality,
                        n_source.id_str as source_ref,
                        n_target.id_str as target_ref,
                        -- aggregate all edges where this node is Source OR Target
                        (
                            SELECT array_agg(e.id_str)
                            FROM connects c
                            JOIN node_n_edge e ON c.edge_id = e.id
                            WHERE c.node_source_id = ne.id OR c.node_target_id = ne.id
                        ) as node_connects_list
                    FROM node_n_edge ne
                    LEFT JOIN cell_space_n_boundary cs ON ne.duality_id = cs.id
                    LEFT JOIN connects c ON ne.id = c.edge_id
                    LEFT JOIN node_n_edge n_source ON c.node_source_id = n_source.id
                    LEFT JOIN node_n_edge n_target ON c.node_target_id = n_target.id
                    WHERE ne.id_str = %s
                    AND ne.thematiclayer_id = (
                        SELECT t.id FROM thematiclayer t
                        JOIN collection col ON t.collection_id = col.id
                        JOIN indoorfeature i ON t.indoorfeature_id = i.id
                        WHERE t.id_str = %s AND col.id_str = %s AND i.id_str = %s
                    )
                """
                cur.execute(query, (member_id, layer_id, collection_id, feature_id))
                result = cur.fetchone()
                if not result: 
                    msg = "requested parameters are not found."
                    LOGGER.debug(msg)
                    return None

                # 1. Base Response
                response = {
                    "id": result['id_str'],
                    "featureType": "Node" if result['type'] == 'node' else "Edge",
                    "geometry": self.wkt_to_json(result.get('geometry')),
                    "duality": result['duality']
                }

                connects = []
                # 2. Add Edge-Specific Fields
                if result['type'] == 'edge':
                    response["weight"] = result['weight']
                    
                    if result['source_ref']: connects.append(f"{result['source_ref']}")
                    if result['target_ref']: connects.append(f"{result['target_ref']}")
                    
                    response["connects"] = connects
                else:
                    if result["node_connects_list"]: connects.append(result["node_connects_list"])
                    response["connects"] = connects
                
                return response

            except Exception as e:
                LOGGER.debug(f"Get Dual Member Error: {e}")
                raise e

    def patch_edge(self, collection_id:str, feature_id:str, layer_id:str, edge_id:str, data):
        """
        Updates an Edge's weight.
        Strictly prevents updates to Nodes.
        """
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # One SQL command to rule them all:
                # 1. Joins the hierarchy to validate the URL path
                # 2. Filters by type='edge' to protect Nodes
                # 3. Updates the weight
                # 4. Returns the ID to confirm success
                if not data.get('weight'):
                    LOGGER.debug("Invalid input data.")
                    return False
                lookup_sql = """
                    SELECT n.id, n.id_str
                    FROM node_n_edge n
                    JOIN collection c ON n.collection_id = c.id
                    JOIN indoorfeature i ON n.indoorfeature_id = i.id
                    JOIN thematiclayer t ON n.thematiclayer_id = t.id
                    WHERE n.id_str = %s AND t.id_str = %s AND c.id_str = %s AND i.id_str = %s AND type='edge'
                """
                cur.execute(lookup_sql, (edge_id, layer_id, collection_id, feature_id))
                target_edge = cur.fetchone()
                if not target_edge:
                    msg = "requested parameters are not found."
                    LOGGER.debug(msg)
                    return False
                
                update_sql = """
                    UPDATE node_n_edge 
                    SET weight = %s 
                    WHERE id = %s 
                    AND type = 'edge'
                """
                
                cur.execute(update_sql, (
                    float(data.get('weight')), 
                    target_edge['id'], 
                ))
                
                self.connection.commit()
                return True

            except Exception as e:
                self.connection.rollback()
                print(f"Update Error: {e}")
                return False

    def delete_dual_member(self, collection_id:str, feature_id:str, layer_id:str, member_id:str):
        """
        Deletes a Node or Edge from a Thematic Layer.
        If you delete node, the connected edges are also deleted.
        Cascading Rules:
        1. If Node (State):
           - Remove InterlayerConnections (Links to other Thematic Layers).
           - Remove 'connects' table entries.
           - Remove connected Edges (Intra-layer transitions).
           - Clear Primal Duality (Room references).
        2. If Edge (Transition):
           - Remove 'connects' table entries.
           - Clear Primal Duality (Boundary references).
        """
        LOGGER.debug("Delete dual member")
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # --- Resolve Layer Context ---
                lookup_sql = """
                    SELECT t.id FROM thematiclayer t
                    JOIN collection c ON t.collection_id = c.id
                    JOIN indoorfeature i ON t.indoorfeature_id = i.id
                    WHERE t.id_str = %s AND c.id_str = %s AND i.id_str = %s
                """
                cur.execute(lookup_sql, (layer_id, collection_id, feature_id))
                layer_row = cur.fetchone()
                if not layer_row: 
                    msg = "requested parameters are not found."
                    LOGGER.debug(msg)
                    raise ValueError(msg)
                
                # --- Identify the Member ---
                check_sql = "SELECT id, type FROM node_n_edge WHERE id_str = %s AND thematiclayer_id = %s"
                cur.execute(check_sql, (member_id, layer_row['id']))
                target = cur.fetchone()
                
                if not target: 
                    msg = f"{member_id} is not found."
                    LOGGER.debug(msg)
                    raise ValueError(msg)

                if target['type'] == 'node':
                    LOGGER.debug(target)
                    # --- A. Clean up InterlayerConnections (Cross-Layer Links) ---
                    # If this node links to a node in a DIFFERENT Thematic Layer, delete that link.
                    delete_interlayer_sql = """
                        DELETE FROM interlayerconnection 
                        WHERE connected_node_a = %s OR connected_node_b = %s
                    """
                    cur.execute(delete_interlayer_sql, (target['id'], target['id']))

                    # --- B. Clean up Intra-Layer Edges (Standard Transitions) ---
                    # Find edges within THIS layer connected to this node
                    find_edges_sql = """
                        SELECT edge_id FROM connects 
                        WHERE node_source_id = %s OR node_target_id = %s
                    """
                    cur.execute(find_edges_sql, (target['id'], target['id']))
                    edges_to_remove = [row['edge_id'] for row in cur.fetchall()]
                    
                    if edges_to_remove:
                        # 1. Remove from 'connects' table (Topology)
                        cur.execute("DELETE FROM connects WHERE edge_id = ANY(%s)", (edges_to_remove,))
                        
                        # 2. Clear Primal Duality for these Edges (Boundaries)
                        cur.execute("""
                            UPDATE cell_space_n_boundary 
                            SET duality_id = NULL 
                            WHERE duality_id = ANY(%s)
                        """, (edges_to_remove,))

                        # 3. Delete the Edge Features themselves
                        # (An Edge cannot exist meaningfully if one of its Nodes is gone)
                        cur.execute("DELETE FROM node_n_edge WHERE id = ANY(%s)", (edges_to_remove,))

                elif target['type'] == 'edge':
                    # Simple: Remove the topological link for this edge
                    cur.execute("DELETE FROM connects WHERE edge_id = %s", (target['id'],))

                # --- STEP C: Clean up Reverse Duality (Primal Space) ---
                # Ensure no Cell Space or Boundary points to this deleted member
                cur.execute("""
                    UPDATE cell_space_n_boundary 
                    SET duality_id = NULL 
                    WHERE duality_id = %s
                """, (target['id'],))

                # --- STEP D: Final Delete of the Member ---
                cur.execute("DELETE FROM node_n_edge WHERE id = %s", (target['id'],))
                self.connection.commit()
                return True

            except Exception as e:
                self.connection.rollback()
                print(f"Delete Dual Member Error: {e}")
                return False
# endregion      

# region Services
    def geometric_query(self, collection_id:str, feature_id:str, layer_id:str, op:str=None, geometry:str=None, level:str=None):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            if not op or not geometry:
                LOGGER.debug("The 'op' and 'geometry' parameter are required.")
                return False
            lookup_sql = """
                SELECT t.*
                FROM thematiclayer t
                JOIN collection c ON t.collection_id=c.id
                JOIN indoorfeature i ON t.indoorfeature_id=i.id
                WHERE c.id_str = %s AND i.id_str = %s AND t.id_str = %s
            """
            cur.execute(lookup_sql, (collection_id, feature_id, layer_id))
            row = cur.fetchone()
            if not row:
                return {}
            
            primal = self._get_primal_geometric_query(row['id'], row['primalspace_id_str'], op=op, geometry=geometry, level=level,
                                                      p_create=row['p_creation_datetime'], p_terminate=row['p_termination_datetime'])
            dual = self._get_dual_space(row['id'], row['dualspace_id_str'], d_create=row['d_creation_datetime'], 
                                        d_terminate=row['d_termination_datetime'], is_logical=row['is_logical'], is_directed=row['is_directed'])
            result_layer = {
                "id": row['id_str'],
                "featureType": "ThematicLayer",
                "theme": row['theme'] if row['theme'] else "Unknown",
                "semanticExtension": row['semantic_extension'],
                "primalSpace": primal,
                "dualSpace": dual,
                "links": []
            }

            return result_layer

    def _get_primal_geometric_query(self, layer_id:str, pSpace_id:str, op: str, geometry: str, level: str = None, p_create=None, p_terminate=None):
        primal_space = {
            "id": pSpace_id, 
            "featureType": "PrimalSpaceLayer",
            "creationDatetime": p_create,
            "terminationDatetime": p_terminate,
            "cellSpaceMember": [],
            "cellBoundaryMember": []
        }
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            geometric_query = """
                SELECT c.id, c.id_str, ST_AsText(c."2D_geometry") as geom_wkt, c."3D_geometry", c.cell_name, c.level, c.poi, c.external_reference, n.id_str as duality, 
                (
                SELECT array_agg(child.id_str)s
                FROM cell_space_n_boundary child
                WHERE child.bounded_by_cell_id = c.id
                ) as bounded_by_list
                FROM cell_space_n_boundary c
                LEFT JOIN node_n_edge n ON c.duality_id = n.id
                WHERE c.thematiclayer_id = %s AND c.type = 'space'
            """
            params_cells = [layer_id]

            if level:
                geometric_query += " AND c.level = %s "
                params_cells.append(level)
            
            if op == 'contains':
                geometric_query += """ AND ST_Contains(c."2D_geometry", ST_GeomFromText(%s, 0)) """
                LOGGER.debug(geometry)
                params_cells.append(geometry)
            elif op == 'within':
                geometric_query += """ AND ST_Within(c."2D_geometry", ST_GeomFromText(%s, 0)) """
                params_cells.append(geometry)
            elif op == 'intersects':
                geometric_query += """ AND ST_Intersects(c."2D_geometry", ST_GeomFromText(%s, 0)) """
                params_cells.append(geometry)
            else:
                raise ValueError("Unaccepted op value.")
            
            cur.execute(geometric_query, tuple(params_cells))
            space_rows = cur.fetchall()
            all_referenced_boundaries = set()

            for row in space_rows:
                if row['bounded_by_list']:
                    all_referenced_boundaries.update(row['bounded_by_list'])
                geom_2d = self.wkt_to_json(row['geom_wkt'])
                cell = {
                        "id": row['id_str'],
                        "featureType": "CellSpace",
                        "duality": row['duality'],
                        "cellSpaceName": row['cell_name'],
                        "level": row['level'],
                        "poi": row['poi'] if row['poi'] else False,
                        "cellSpaceGeom": {
                            "geometry2D": geom_2d,
                            "geometry3D": row['3D_geometry']
                        },
                        "boundedBy": row['bounded_by_list']
                    }
                if row['external_reference']: cell["externalReference"] = row['external_reference']
                primal_space["cellSpaceMember"].append(cell)

            boundary_id_list = list(all_referenced_boundaries)
            
            sql_bounds = """
                SELECT c.id, c.id_str, c.external_reference, 
                ST_AsText(c."2D_geometry", 0) as geom_2d, c."3D_geometry" as geom_3d, n.id_str as duality, c.is_virtual
                FROM cell_space_n_boundary c
                LEFT JOIN node_n_edge n ON c.duality_id = n.id
                WHERE c.id_str = ANY(%s) AND c.thematiclayer_id = %s
            """
            cur.execute(sql_bounds, (boundary_id_list, layer_id))
            boundary_rows = cur.fetchall()  
            for row in boundary_rows:
                boundary = {
                    "id": row['id_str'],
                    "featureType": "CellBoundary",
                    "duality": row['duality'],
                    "isVirtual": row['is_virtual'],
                    "cellBoundaryGeom": {
                        "geometry2D": self.wkt_to_json(row['geom_2d']),
                        "geometry3D": row['geom_3d']
                    }
                }
                if row['external_reference']: boundary["externalReference"] = {"uri": row['external_reference']}
                primal_space["cellBoundaryMember"].append(boundary)

        return primal_space

    def routing_query(self, collection_id:str, feature_id:str, layer_id:str, sn:str, dn:str):
        # This query gets the full sequence from pgRouting and joins it with your tables
        lookup_sql = """
            SELECT n.id, t.is_directed 
            FROM node_n_edge n
            JOIN collection c ON n.collection_id = c.id
            JOIN indoorfeature i ON n.indoorfeature_id = i.id
            JOIN thematiclayer t ON n.thematiclayer_id = t.id
            WHERE n.id_str = %s AND c.id_str = %s AND i.id_str = %s AND t.id_str = %s
        """
        
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(lookup_sql, (sn, collection_id, feature_id, layer_id))
            start_node = cur.fetchone()
            if not start_node:
                msg = "requested parameters are not found."
                raise ValueError(msg)
            cur.execute(lookup_sql, (dn, collection_id, feature_id, layer_id))
            destination_node = cur.fetchone()
            if not destination_node:
                msg = "requested parameters are not found."
                raise ValueError(msg)
            network_sql = """
            SELECT 
                c.edge_id as id, 
                c.node_source_id as source, 
                c.node_target_id as target, 
                COALESCE(n.weight, ST_Length(n.geometry_val)) as cost,  -- fix if weight is exist.
                CASE 
                    WHEN t.is_directed = true THEN -1   -- If one-way, block reverse
                    ELSE COALESCE(n.weight, ST_Length(n.geometry_val))   -- If two-way, reuse the forward cost
                END as reverse_cost
            FROM connects c
            JOIN node_n_edge n ON c.edge_id = n.id
            JOIN thematiclayer t ON n.thematiclayer_id = t.id
            """
            routing_sql = f"""
            WITH route AS (
                SELECT * FROM pgr_dijkstra(
                    '{network_sql}',
                    %(start)s, 
                    %(dest)s, 
                    %(directed)s -- Set true if one-way streets exist
                )
            )
            SELECT 
                r.seq,
                r.node as node_id,
                r.edge as edge_id,
                r.cost,
                r.agg_cost,
                n.id_str,
                n.type,
                ST_AsText(n.geometry_val) as geometry
            FROM route r
            LEFT JOIN node_n_edge n 
                ON (r.edge = n.id)  -- Join Edge info
                OR (r.edge = -1 AND r.node = n.id) -- Join Last Node info
            ORDER BY r.seq;
            """
            sn_id= start_node['id']
            dn_id = destination_node['id']
            is_directed = start_node['is_directed']
            cur.execute(routing_sql, {'start': sn_id, 'dest': dn_id, 'directed': is_directed})
            path_rows = cur.fetchall()
            if not path_rows:
                return {"total_weight": 0, "path": []}
            total_weight = path_rows[-1]['agg_cost']

            response = {
                "type": "RouteResult",
                "start_node": sn,
                "destination_node": dn,
                "cost": total_weight,
                "path_segments": [
                    {
                        "seq": row['seq'],
                        "type": "edge" if row['edge_id'] != -1 else "destination_node",
                        "id_str": row['id_str'],
                        "cost": row['cost'],
                        "geometry": self.wkt_to_json(row['geometry'])
                    }
                    for row in path_rows
                ],
                "links": []
            }
                
            return response

    def bounding_cell_space(self, collection_id:str, feature_id:str, layer_id:str, boundary_id:str):
        lookup_sql = """
            SELECT b.id, b.bounded_by_cell_id
            FROM cell_space_n_boundary b
            JOIN collection c ON b.collection_id = c.id
            JOIN indoorfeature i ON b.indoorfeature_id = i.id
            JOIN thematiclayer t ON b.thematiclayer_id = t.id
            WHERE b.id_str = %s AND c.id_str = %s AND i.id_str = %s AND t.id_str = %s AND type = 'boundary'
        """
        response = {}
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(lookup_sql, (boundary_id, collection_id, feature_id, layer_id))
            row = cur.fetchone()

            if not row:
                msg = "requested parameters are not found."
                raise ValueError(msg)
            
            if not row['bounded_by_cell_id']:
                    return response
            
            cell_sql = """
                SELECT c.id_str, c.cell_name, c.level, c.poi, ST_AsText(c."2D_geometry") as geometry_2d, 
                c."3D_geometry" as geometry_3d, c.external_reference, n.id_str as duality, (
                    SELECT array_agg(child.id_str)
                    FROM cell_space_n_boundary child
                    WHERE child.bounded_by_cell_id = c.id
                ) as bounded_by_list
                FROM cell_space_n_boundary c
                LEFT JOIN node_n_edge n ON c.duality_id = n.id
                WHERE c.id = %s
            """
            cur.execute(cell_sql, (row['bounded_by_cell_id'],))
            cell = cur.fetchone()
            response = {
                        "id": cell['id_str'],
                        "featureType": "CellSpace",
                        "cellSpaceName": cell['cell_name'],
                        "level": cell['level'],
                        "poi": cell['poi'],
                        "duality": cell['duality'],
                        "cellSpaceGeom": {
                            "geometry2D": self.wkt_to_json(cell['geometry_2d']),
                            "geometry3D": cell['geometry_3d']
                        },
                        "externalReference": cell['external_reference'],
                        "boundedBy": cell['bounded_by_list']
                    }
            
            return response

    def connected_nodes(self, collection_id:str, feature_id:str, layer_id:str, node_id:str, hop:int = 1):
        lookup_sql = """
            SELECT n.id 
            FROM node_n_edge n
            JOIN collection c ON n.collection_id = c.id
            JOIN indoorfeature i ON n.indoorfeature_id = i.id
            JOIN thematiclayer t ON n.thematiclayer_id = t.id
            WHERE n.id_str = %s AND c.id_str = %s AND i.id_str = %s AND t.id_str = %s
        """
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(lookup_sql, (node_id, collection_id, feature_id, layer_id))
            row = cur.fetchone()
            if not row:
                msg = "requested parameters are not found."
                raise ValueError(msg)
            starting_node = row['id']
            nodes_sql = """
            WITH RECURSIVE neighbors AS (
            SELECT 
                node_source_id AS next_node, 
                node_target_id AS target_node, 
                1 AS current_hop
            FROM connects
            WHERE node_source_id = %s OR node_target_id = %s
            UNION
            -- Recursive step: Find nodes connected to the ones found in the previous step
            SELECT 
                CASE 
                    WHEN c.node_source_id = n.target_node THEN c.node_target_id 
                    ELSE c.node_source_id 
                END,
                CASE 
                    WHEN c.node_source_id = n.target_node THEN c.node_target_id 
                    ELSE c.node_source_id 
                END,
                n.current_hop + 1
            FROM connects c
            JOIN neighbors n ON (c.node_source_id = n.target_node OR c.node_target_id = n.target_node)
            WHERE n.current_hop < %s
            )
            SELECT DISTINCT 
                ne.id_str, 
                ST_AsText(ne.geometry_val) as geom_wkt, 
                ne.type,
                nb.current_hop,
                c.id_str as duality,
                (
                SELECT array_agg(e.id_str)
                FROM connects c
                JOIN node_n_edge e ON c.edge_id = e.id
                WHERE c.node_source_id = ne.id OR c.node_target_id = ne.id
                ) as node_connects_list
            FROM node_n_edge ne
            JOIN neighbors nb ON ne.id = nb.target_node
            LEFT JOIN cell_space_n_boundary c ON ne.duality_id = c.id
            WHERE ne.id != %s -- Exclude the starting node itself
            ORDER BY nb.current_hop ASC
            """
            cur.execute(nodes_sql, (starting_node, starting_node, hop, starting_node))
            nodes = cur.fetchall()
            response = {
                "type": "ConnectedNodesResult",
                "start_node": node_id,
                "connected_nodes": [
                    {
                        "hop": node['current_hop'],
                        "id": node['id_str'],
                        "featureType": "node",
                        "geometry": self.wkt_to_json(node['geom_wkt']),
                        "duality": node['duality'],
                        "connects": node['node_connects_list']
                    }
                    for node in nodes
                ],
                "links": []
            }

            return response


    def json_to_wkt(self, geom_json):
        """
        Converts GeoJSON-like dict to WKT string.
        Automatically detects 2D vs 3D based on coordinate length.
        """
        if not geom_json:
            return None

        g_type = geom_json.get('type')
        coords = geom_json.get('coordinates')

        if not coords:
            return None

        # --- HELPER: Detect Dimension ---
        # We check the length of the first point we can find to decide if it's "POLYGON" or "POLYGON Z"
        def get_prefix(geom_type, sample_point):
            if len(sample_point) == 3:
                return f"{geom_type.upper()} Z"
            return geom_type.upper()

        # --- HELPER: String formatters ---
        def make_coord_str(p):
            # Converts [x, y] -> "x y" OR [x, y, z] -> "x y z"
            return " ".join(map(str, p))

        def make_ring_str(ring):
            return ", ".join(make_coord_str(p) for p in ring)

        # ==============================
        # 1. POINT
        # ==============================
        if g_type == 'Point':
            prefix = get_prefix('POINT', coords)
            return f"{prefix} ({make_coord_str(coords)})"

        # ==============================
        # 2. LINESTRING
        # ==============================
        elif g_type == 'LineString':
            prefix = get_prefix('LINESTRING', coords[0])
            return f"{prefix} ({make_ring_str(coords)})"

        # ==============================
        # 3. POLYGON
        # ==============================
        elif g_type == 'Polygon':
            # Check nesting: Is it [[x,y], [x,y]] (Single Ring) or [[[x,y]], [[x,y]]] (Multi Ring)?
            if isinstance(coords[0][0], (float, int)):
                # Depth 2: Simple list of points (Non-standard but possible)
                prefix = get_prefix('POLYGON', coords[0])
                return f"{prefix} (({make_ring_str(coords)}))"
            else:
                # Depth 3: Standard GeoJSON (List of Rings)
                prefix = get_prefix('POLYGON', coords[0][0])
                rings_str = ", ".join(f"({make_ring_str(ring)})" for ring in coords)
                return f"{prefix} ({rings_str})"

        # ==============================
        # 4. POLYHEDRON (Custom 3D)
        # ==============================
        elif g_type == 'Polyhedron':
            # Polyhedrons are inherently 3D, but let's be safe
            # Structure: [ Face1[ Ring[...] ], ... ]
            prefix = "POLYHEDRALSURFACE Z" # Default to Z for Polyhedron
            
            faces_str = []
            for face in coords:
                rings = ", ".join(f"({make_ring_str(ring)})" for ring in face)
                faces_str.append(f"({rings})")
            return f"{prefix} ({', '.join(faces_str)})"

        # ==============================
        # 5. MULTIPOLYGON
        # ==============================
        elif g_type == 'MultiPolygon':
            # coords[0] is a Polygon -> coords[0][0] is a Ring -> coords[0][0][0] is a Point
            prefix = get_prefix('MULTIPOLYGON', coords[0][0][0])
            
            polys_str = []
            for poly in coords:
                rings_str = ", ".join(f"({make_ring_str(ring)})" for ring in poly)
                polys_str.append(f"({rings_str})")
            return f"{prefix} ({', '.join(polys_str)})"

        return None
    
    def wkt_to_json(self, wkt_text):
        """
        Parses WKT string into Dictionary (GeoJSON-like).
        Supports: POINT, LINESTRING, POLYGON, MULTIPOLYGON, POLYHEDRALSURFACE.
        """
        if not wkt_text:
            return None

        wkt = wkt_text.strip().upper()

        # Helper: "1 2 3, 4 5 6" -> [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        def parse_coord_list(coord_str):
            points = []
            for pt in coord_str.strip().split(','):
                nums = [float(n) for n in pt.strip().split(' ') if n]
                points.append(nums)
            return points

        # Helper: "1 2 3" -> [1.0, 2.0, 3.0]
        def parse_single_pt(pt_str):
            return [float(n) for n in pt_str.strip().split(' ') if n]

        # --- POINT ---
        if wkt.startswith('POINT'):
            # Remove POINT Z (...) -> ...
            body = re.sub(r'POINT\s*Z?\s*\(', '', wkt)[:-1]
            return {"type": "Point", "coordinates": parse_single_pt(body)}

        # --- LINESTRING ---
        elif wkt.startswith('LINESTRING'):
            body = re.sub(r'LINESTRING\s*Z?\s*\(', '', wkt)[:-1]
            return {"type": "LineString", "coordinates": parse_coord_list(body)}

        # --- POLYGON ---
        elif wkt.startswith('POLYGON'):
            body = re.sub(r'POLYGON\s*Z?\s*\(', '', wkt)[:-1]
            # Split rings: (...), (...)
            raw_rings = re.findall(r'\((.*?)\)', body)
            return {"type": "Polygon", "coordinates": [parse_coord_list(r) for r in raw_rings]}

        # --- POLYHEDRALSURFACE (Matches 'Polyhedron') ---
        elif wkt.startswith('POLYHEDRALSURFACE'):
            body = re.sub(r'POLYHEDRALSURFACE\s*Z?\s*\(', '', wkt)[:-1]
            # Split faces: ((...)), ((...))
            raw_faces = re.findall(r'\(\((.*?)\)\)', body)
            # Each face is a list of rings (usually 1 ring per face)
            coords = [[parse_coord_list(face)] for face in raw_faces]
            return {"type": "Polyhedron", "coordinates": coords}

        # --- MULTIPOLYGON ---
        elif wkt.startswith('MULTIPOLYGON'):
            body = re.sub(r'MULTIPOLYGON\s*Z?\s*\(', '', wkt)[:-1]
            raw_polys = re.findall(r'\(\((.*?)\)\)', body)
            
            coords = []
            for poly_str in raw_polys:
                # Simple split for rings inside polygon
                rings = poly_str.split('),(') 
                poly_coords = [parse_coord_list(r.replace(')','').replace('(','')) for r in rings]
                coords.append(poly_coords)
                
            return {"type": "MultiPolygon", "coordinates": coords}

        return None
# endregion