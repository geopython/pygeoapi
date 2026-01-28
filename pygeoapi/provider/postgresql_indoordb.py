import json
import random
import datetime
import psycopg2
import logging
from functools import partial
from dateutil.parser import parse as dateparse
import pytz
from pygeoapi.util import format_datetime
from psycopg2.extras import Json, RealDictCursor
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

# region IndoorFeatureCollections 

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
        Creates a new collection.
        Refactored for 2026 Schema: Relies on DB to auto-generate the Integer ID.
        """
        self.connect()
        
        properties = {
            'title': title,
            'description': description,
            'itemType': item_type
        }
        
        try:
            with self.connection.cursor() as cur:
                # 1. Check if exists
                cur.execute("SELECT 1 FROM collection WHERE id_str = %s", (id_str,))
                if cur.fetchone():
                    return False

                # 2. Insert (Let Postgres handle the 'id' column automatically)
                insert_query = """
                    INSERT INTO collection (id_str, collection_property)
                    VALUES (%s, %s)
                """
                cur.execute(insert_query, (id_str, json.dumps(properties)))
                
                self.connection.commit()
                return True
        except Exception as e:
            self.connection.rollback()
            LOGGER.error(f"Error creating collection: {e}")
            return False

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
    
# endregion

# region IndoorFeatures 
    def is_indoor_collection(self, collection_id_str):
        """
        Checks if the collection exists and has itemType='indoorfeature'.
        Returns True if it is an IndoorGML collection, False otherwise.
        """
        is_indoor = False
        try:
            # Re-use existing connection logic or ensure connected
            if not self.connection or self.connection.closed:
                self.connect()

            with self.connection.cursor() as cur:
                # Adjust column names 'id_str' and 'itemType' to match your schema
                cur.execute("""
                    SELECT collection_property 
                    FROM collection 
                    WHERE id_str = %s
                """, (collection_id_str,))
                props = cur.fetchone()
                
                if props:
                    if props[0].get('itemType') == 'indoorfeature':
                        is_indoor = True
                    
        except Exception as e:
            LOGGER.error(f"Error checking collection type: {e}")
        # Note: You might choose NOT to disconnect here if you plan 
        # to reuse the connection immediately after.
        # self.disconnect() 
        
        return is_indoor

    def get_collection_items(
            self, collection_id, bbox='', limit=10, offset=0):
        """
        Retrieve the indoor feature collection to access
        the static information of the indoor feature
        /collections/{collectionId}/items

        :param collection_id: local identifier of a collection
        :param bbox: bounding box [lowleft1,lowleft2,min(optional),
                                   upright1,upright2,max(optional)]
        :param limit: number of items (default 10) [optional]
        :param offset: starting record to return (default 0)

        :returns: JSON IndoorFeatures
        """
        self.connect()
        try:
            if bbox is None:
                bbox = []
                
            # 1. Prepare Filter Strings
            # We need to filter by collection_id_str (which is passed in)
            # We assume collection_id here is the STRING ID (e.g., 'AIST_Building'), 
            # so we join with the collection table.
            
            where_clauses = ["c.id_str = %s"]
            params = [collection_id]

            # 2. Handle BBOX (Bounding Box)
            # bbox format: [minx, miny, maxx, maxy]
            if bbox and len(bbox) == 4:
                # PostGIS && operator checks if bounding boxes overlap
                # ST_MakeEnvelope creates a rectangle from the 4 coordinates
                where_clauses.append("i.geojson_geometry && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
                params.extend(bbox)

            # Join all where clauses
            where_str = " AND ".join(where_clauses)

            with self.connection.cursor() as cur:
                # 3. Get Total Count (number_matched)
                # This counts ALL items that match the filter (ignoring limit/offset)
                count_sql = f"""
                    SELECT COUNT(*) 
                    FROM indoorfeature i
                    JOIN collection c ON i.collection_id = c.id
                    WHERE {where_str}
                """
                
                # We must pass parameters safely to avoid SQL injection
                # Note: params currently has [collection_id] + [bbox values]
                cur.execute(count_sql, tuple(params))
                number_matched = cur.fetchone()[0]

                # 4. Get Data (Features) with Limit/Offset
                # We select the necessary columns to build the GeoJSON
                data_sql = f"""
                    SELECT 
                        i.id_str, 
                        ST_AsGeoJSON(i.geojson_geometry) as geom,
                        i.geojson_properties
                    FROM indoorfeature i
                    JOIN collection c ON i.collection_id = c.id
                    WHERE {where_str}
                    ORDER BY i.id ASC
                    LIMIT %s OFFSET %s
                """
                
                # Append limit and offset to the parameters list
                query_params = list(params) 
                query_params.extend([limit, offset])
                
                cur.execute(data_sql, tuple(query_params))
                rows = cur.fetchall()

                # 5. Format Rows into GeoJSON Feature Objects
                features = []
                
                for row in rows:
                    feature_id, geom_text, props = row
                    
                    # Parse geometry string into JSON object (or None)
                    geometry = json.loads(geom_text) if geom_text else None
                    
                    # Construct the GeoJSON Feature dictionary
                    feature = {
                        "type": "Feature",
                        "id": feature_id,
                        "geometry": geometry,
                        "properties": props or {} 
                    }
                    features.append(feature)
                
                return features, number_matched
        finally:
            self.disconnect()
            

    def get_feature(self, collection_id, feature_id, level=None):
        """
        TODO: Retrieve just the metadata when not filtered

        Retrieves the actual IndoorFeature when filtered.
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

            # Initialize Skeleton
            result_feature = {
                "featureType": "Feature",
                "id": feature_id_str,
                "geometry": geometry,
                "properties": properties, # Standard metadata properties
                
                # The core IndoorGML data structure
                "IndoorFeatures": {
                    "featureType": "IndoorFeatures",
                    "layers": [],
                    "layerConnections": []
                },
                "links": []
            }

            # ---------------------------------------------------------
            # 2. Fetch Thematic Layers (Keep ID mapping for later)
            # ---------------------------------------------------------

            cur.execute("""
                SELECT 
                    id, 
                    id_str, 
                    primalspace_id_str, 
                    dualspace_id_str, 
                    semantic_extension, 
                    theme,
                    p_creation_datetime, 
                    p_termination_datetime,
                    d_creation_datetime, 
                    d_termination_datetime,
                    is_logical, 
                    is_directed
                FROM thematiclayer
                WHERE indoorfeature_id = %s
            """, (feature_pk,))

            layer_rows = cur.fetchall()

            # Map database ID (pk) to the layer object so we can inject content later
            layers_by_pk = {}

            for l_row in layer_rows:
                (
                    l_pk, l_id, l_p_id, l_d_id, l_se, l_t, 
                    p_start, p_end, d_start, d_end, d_is_log, d_is_dir
                ) = l_row
                
                thematic_layer = {
                    "id": l_id,
                    "featureType": "ThematicLayer",
                    "theme": l_t if l_t else "Unknown",
                    "semanticExtension": l_se if l_se else False,
                    
                    # 1. Primal Space Object (ID + Members)
                    "primalSpace": {
                        "id": l_p_id,
                        "featureType": "PrimalSpaceLayer",
                        # Convert datetime to ISO string if exists, else None
                        "creationDatetime": p_start.isoformat() if p_start else None, 
                        "terminationDatetime": p_end.isoformat() if p_end else None,
                        "cellSpaceMember": [],
                        "cellBoundaryMember": []
                    },
                    
                    # 2. Dual Space Object (ID + Members)
                    "dualSpace": {
                        "id": l_d_id,
                        "featureType": "DualSpaceLayer",
                        # Use DB value; if None, fall back to True/False based on your preference
                        "isLogical": d_is_log if d_is_log is not None else True,   
                        "isDirected": d_is_dir if d_is_dir is not None else True,  
                        
                        "creationDatetime": d_start.isoformat() if d_start else None,
                        "terminationDatetime": d_end.isoformat() if d_end else None,
                        
                        "nodeMember": [],
                        "edgeMember": []
                    }
                }
                
                result_feature["IndoorFeatures"]["layers"].append(thematic_layer)
                layers_by_pk[l_pk] = thematic_layer
            
            # ---------------------------------------------------------
            # 3. Fetch CellSpaces (with Level Filter)
            # ---------------------------------------------------------
            # We LEFT JOIN node_n_edge to get the duality string ID immediately.
            
            space_sql = """
                SELECT 
                    s.id, s.id_str, s.thematiclayer_id, 
                    ST_AsText(s."2D_geometry"), s."3D_geometry",
                    s.cell_name, s.level, s.external_reference, 
                    s.poi, 
                    d.id_str as duality_str
                FROM cell_space_n_boundary s
                LEFT JOIN node_n_edge d ON s.duality_id = d.id
                WHERE s.indoorfeature_id = %s AND s.type = 'space'
            """
            space_params = [feature_pk]

            if level:
                space_sql += " AND s.level = %s"
                space_params.append(str(level))

            cur.execute(space_sql, tuple(space_params))
            space_rows = cur.fetchall()

            valid_space_ids = set() 
            spaces_by_pk = {} # Temporary map: { db_pk : space_object_reference }

            for s_row in space_rows:
                s_pk, s_id, layer_pk, s_geom_2d, s_geom_3d, s_name, s_lvl, s_ext, s_poi, s_duality_str = s_row
                
                valid_space_ids.add(s_pk)
                
                space_obj = {
                    "featureType": "CellSpace",
                    "id": s_id,
                    "cellSpacegeom": {
                        "geometry2D": self.wkt_to_json(s_geom_2d),
                        "geometry3D": s_geom_3d
                    }, 
                    "cellSpaceName": s_name,
                    "level": s_lvl,
                    "poi": s_poi if s_poi is not None else False,
                    "duality": s_duality_str, # Now a string
                    "boundedBy": [],          # Initialize empty, fill in Step 4
                    "externalReference": s_ext
                }

                # Save reference for reverse-lookup in step 4
                spaces_by_pk[s_pk] = space_obj

                # Inject into the correct layer
                if layer_pk in layers_by_pk:
                    layers_by_pk[layer_pk]["primalSpace"]["cellSpaceMember"].append(space_obj)

            # ---------------------------------------------------------
            # 4. Fetch CellSpaceBoundaries (Filtered by Space IDs)
            # ---------------------------------------------------------
            
            should_fetch_boundaries = True
            if level and not valid_space_ids:
                should_fetch_boundaries = False

            if should_fetch_boundaries:
                # We fetch bounded_by_cell_id to link back to the space.
                # We LEFT JOIN node_n_edge to get the duality string ID.
                bound_sql = """
                    SELECT 
                        b.id, b.id_str, b.thematiclayer_id, 
                        ST_AsText(b."2D_geometry"), b."3D_geometry",
                        b.external_reference, b.is_virtual,
                        b.bounded_by_cell_id,
                        d.id_str as duality_str
                    FROM cell_space_n_boundary b
                    LEFT JOIN node_n_edge d ON b.duality_id = d.id
                    WHERE b.indoorfeature_id = %s AND b.type = 'boundary'
                """
                bound_params = [feature_pk]

                if level:
                    bound_sql += " AND b.bounded_by_cell_id = ANY(%s)"
                    bound_params.append(list(valid_space_ids))

                cur.execute(bound_sql, tuple(bound_params))
                bound_rows = cur.fetchall()

                for b_row in bound_rows:
                    b_pk, b_id, layer_pk, b_geom_2d, b_geom_3d, b_ext, b_virt, parent_space_pk, b_duality_str = b_row
                    bound_obj = {
                        "featureType": "CellBoundary",
                        "id": b_id,
                        "CellBoundaryGeom": {
                            "geometry2D": self.wkt_to_json(b_geom_2d),
                            "geometry3D": b_geom_3d
                        },
                        "isVirtual": b_virt if b_virt is not None else False,
                        "duality": b_duality_str, # Now a string
                        "externalReference": b_ext 
                    }

                    # INVERSION LOGIC: Add this boundary ID to the parent Space's boundedBy list
                    if parent_space_pk in spaces_by_pk:
                        spaces_by_pk[parent_space_pk]["boundedBy"].append(b_id)

                    if layer_pk in layers_by_pk:
                        layers_by_pk[layer_pk]["primalSpace"]["cellBoundaryMember"].append(bound_obj)

            # ---------------------------------------------------------
            # 5 & 6. Fetch Dual Space (Nodes & Edges)
            # ---------------------------------------------------------
            
            dual_sql = """
                SELECT 
                    n.id, n.id_str, n.type, n.thematiclayer_id, 
                    ST_AsText(n.geometry_val), 
                    n.weight,
                    p.id_str as duality_str
                FROM node_n_edge n
                LEFT JOIN cell_space_n_boundary p ON n.duality_id = p.id
                WHERE n.indoorfeature_id = %s
            """
            cur.execute(dual_sql, (feature_pk,))
            dual_rows = cur.fetchall()

            # Temporary map to lookup objects by DB ID for the connection step
            # Key: database_id (int), Value: reference to the node/edge dict
            dual_items_by_pk = {}

            for d_row in dual_rows:
                d_pk, d_id, d_type, layer_pk, d_geom_str, d_weight, d_duality_str = d_row
                
                # --- NODE ---
                if d_type == 'node':
                    node_obj = {
                        "featureType": "Node",
                        "id": d_id,
                        "geometry": self.wkt_to_json(d_geom_str),
                        "duality": d_duality_str, 
                        "connects": [] # Will be populated in the next block
                    }
                    
                    dual_items_by_pk[d_pk] = node_obj
                    
                    if layer_pk in layers_by_pk:
                        layers_by_pk[layer_pk]["dualSpace"]["nodeMember"].append(node_obj)
                
                # --- EDGE ---
                elif d_type == 'edge':
                    edge_obj = {
                        "featureType": "Edge",
                        "id": d_id,
                        "geometry": self.wkt_to_json(d_geom_str),
                        "weight": d_weight if d_weight is not None else 0.0,
                        "duality": d_duality_str, 
                        "connects": [] # Will be populated in the next block
                    }

                    dual_items_by_pk[d_pk] = edge_obj

                    if layer_pk in layers_by_pk:
                        layers_by_pk[layer_pk]["dualSpace"]["edgeMember"].append(edge_obj)

            # ---------------------------------------------------------
            # 6.5. Populate 'connects' for Nodes and Edges
            # ---------------------------------------------------------
            # We query the 'connects' table and JOIN node_n_edge 3 times
            # to retrieve the String IDs for the Edge, Source Node, and Target Node.
            
            connects_sql = """
                SELECT 
                    c.edge_id,      e.id_str AS edge_str,
                    c.node_source_id, ns.id_str AS source_str,
                    c.node_target_id, nt.id_str AS target_str
                FROM connects c
                JOIN node_n_edge e  ON c.edge_id = e.id
                JOIN node_n_edge ns ON c.node_source_id = ns.id
                JOIN node_n_edge nt ON c.node_target_id = nt.id
                WHERE e.indoorfeature_id = %s
            """
            cur.execute(connects_sql, (feature_pk,))
            connects_rows = cur.fetchall()

            for conn_row in connects_rows:
                edge_pk, edge_str, src_pk, src_str, tgt_pk, tgt_str = conn_row
                
                # 1. Update the Edge object: connects [Source, Target]
                if edge_pk in dual_items_by_pk:
                    dual_items_by_pk[edge_pk]["connects"] = [src_str, tgt_str]

                # 2. Update the Source Node object: add Edge ID
                if src_pk in dual_items_by_pk:
                    dual_items_by_pk[src_pk]["connects"].append(edge_str)

                # 3. Update the Target Node object: add Edge ID
                if tgt_pk in dual_items_by_pk:
                    dual_items_by_pk[tgt_pk]["connects"].append(edge_str)
                
            # ---------------------------------------------------------
            # 7. Fetch InterLayerConnections 
            # ---------------------------------------------------------
            # Logic: We strictly query the 'interlayerconnection' table.
            # We LEFT JOIN 'thematiclayer', 'cell_space_n_boundary', and 'node_n_edge'
            # ONLY to resolve the integer Foreign Keys into String IDs (id_str).
            # This does NOT involve the 'connects' table.

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
                
                result_feature["IndoorFeatures"]["layerConnections"].append(interlayer_connection)
        
        return result_feature
    
    def delete_indoorfeature(self, collection_str_id, feature_id_str):
        """
        Deletes an IndoorFeature and all its associated layers, cells, nodes, and connections.
        
        :param collection_str_id: The String ID of the Collection (e.g., 'IndoorGML_DataSet_1')
        :param feature_id_str: The String ID of the Feature to delete (e.g., 'AIST_Waterfront')
        """
        LOGGER.debug(f"Deleting IndoorFeature: {feature_id_str} in {collection_str_id}")

        with self.connection.cursor() as cur:
            try:
                # 1. Resolve IDs (We need the Integer IDs to delete efficiently)
                cur.execute(
                    "SELECT c.id, i.id FROM collection c "
                    "JOIN indoorfeature i ON c.id = i.collection_id "
                    "WHERE c.id_str = %s AND i.id_str = %s",
                    (collection_str_id, feature_id_str)
                )
                res = cur.fetchone()
                
                if not res:
                    # Item not found, usually returns 404 in API, but here we can just return
                    LOGGER.warning(f"Feature {feature_id_str} not found.")
                    return

                coll_pk, feature_pk = res

                # 2. DELETE CHILDREN FIRST (Because we don't have CASCADE in SQL)
                
                # A. Delete Connections (Edges between nodes)
                # We must delete rows in 'connects' where the nodes belong to this feature
                cur.execute("""
                    DELETE FROM connects 
                    WHERE node_source_id IN (
                        SELECT id FROM node_n_edge WHERE indoorfeature_id = %s
                    )
                """, (feature_pk,))

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
                
            except Exception as e:
                self.connection.rollback()
                LOGGER.error(f"Error deleting indoorfeature: {e}")
                raise e
# endregion 
    
# region ThematicLayers
    def get_layers(self, collection_id, feature_id, theme = None, level = None, limit=10, offset=0):
        """
        Retrieves a list of Thematic Layers.
        - TODO:BBOX: If level is filtered, BBOX is calculated ONLY for that level.
        - Levels: Always returns ALL levels available in that layer (so client knows what else exists).
        - Filtering: Only returns layers that actually contain the requested level.
        """
        
        response = {
            "levels": [],
            "layers": [],
            "links": []
        }
        with self.connection.cursor() as cur:
            # -----------------------------------------------------
            # 1. Get Available Levels (Global Context)
            # -----------------------------------------------------

            sql_levels = """
                SELECT DISTINCT cs.level
                FROM cell_space_n_boundary cs
                JOIN thematiclayer tl ON cs.thematiclayer_id = tl.id
                JOIN indoorfeature i ON tl.indoorfeature_id = i.id
                JOIN collection c ON i.collection_id = c.id
                WHERE c.id_str = %s AND i.id_str = %s AND cs.level IS NOT NULL
            """
            params_levels = [collection_id, feature_id]

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
    
    def get_layer(self, collection_id, feature_id, layer_id, level=None, bbox=None):
        """
        Retrieves a single Thematic Layer.
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
                primal = self._get_primal_space(cur, l_pk, p_id, p_create, level=level, bbox=bbox)
                dual = self._get_dual_space(cur, l_pk, d_id, d_create, l_logical, l_directed)
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

    def _get_primal_space(self, cur, layer_pk, primalspace_id, p_create, level=None, bbox=None):
        """
        Helper to build PrimalSpaceLayer. 
        Supports optional filtering by 'level'.
        """
        primal_space = {
            "id": primalspace_id, 
            "featureType": "PrimalSpaceLayer",
            "creationDatetime": str(p_create) if p_create else None,
            "cellSpaceMember": [],
            "cellBoundaryMember": []
        }
        sql_cells = """
            SELECT c.id, c.id_str, c.type, c.cell_name, c.level, c.external_reference, 
                   ST_AsText("2D_geometry"), c."3D_geometry", c.poi, n.id_str, c.is_virtual,
                   (
                    SELECT array_agg(child.id_str)s
                    FROM cell_space_n_boundary child
                    WHERE child.bounded_by_cell_id = c.id
                    ) as bounded_by_list
            FROM cell_space_n_boundary c
            LEFT JOIN node_n_edge n ON c.duality_id = n.id
            WHERE c.thematiclayer_id = %s
        """
        params_cells = [layer_pk]

        if level is not None:
            sql_cells += " AND level = %s"
            params_cells.append(level)

        if bbox:
            parts = bbox.split(',')
            if len(parts) != 4:
                raise ValueError("Invalid bbox format. Expected: minx,miny,maxx,maxy")
            minx, miny, maxx, maxy = map(float, parts)
            sql_cells += """
                AND c."2D_geometry"
                && ST_MakeEnvelope(%s, %s, %s, %s, 0)
            """
            params_cells.extend([minx, miny, maxx, maxy])
            
        cur.execute(sql_cells, tuple(params_cells))
        all_referenced_boundaries = set()

        for row in cur.fetchall():
            pk, id, type, name, level, ext, geom_2d_wkt, geom_3d_json, poi, duality, is_virtual, boundedBylist = row
            geom_2d = self.wkt_to_json(geom_2d_wkt)
 
            if boundedBylist:
                all_referenced_boundaries.update(boundedBylist)
            if type == 'space':
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
            else: 
                continue   # always boundedBy boundary member could be retrieved
                # boundary = {
                #         "id": id,
                #         "featureType": "CellBoundary",
                #         "duality": duality,
                #         "isVirtual": is_virtual,
                #         "cellBoundaryGeom": {
                #             "geometry2D": geom_2d,
                #             "geometry3D": geom_3d_json
                #     }
                # }
                # if ext: boundary["externalReference"] = {"uri": ext}
                # primal_space["cellBoundaryMember"].append(boundary)
            
           
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
    
    def _get_dual_space(self, cur, layer_pk, dualspace_id, d_creat, is_logical, is_directed):
        """
        Helper: Fetches Nodes, Edges, and resolves 'connects' relationships.
        """
        dual_space = {
            "id": dualspace_id,
            "featureType": "DualSpaceLayer",
            "isLogical": is_logical if is_logical is not None else True,
            "isDirected": is_directed if is_directed is not None else True,
            "nodeMember": [],
            "edgeMember": [],
            "creationDatetime": str(d_creat) if d_creat else None
        }

        node_map = {}
        edge_map = {}

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

    def post_indoorfeature(self, collection_str_id, indoorfeature):
        """
        Insert a indoor feature into a collection

        :param collection_id: local identifier of a collection

        :returns: IndoorFeature ID
        """        
        feature_id_str = indoorfeature.get('id')
        properties = indoorfeature.get('properties', {})
        geometries = indoorfeature.get('geometry', {})
        layers = indoorfeature.get('layers', [])

        with self.connection.cursor() as cur:
            try:
                # Resolve Collection DB ID (Integer) from String ID
                cur.execute("SELECT id FROM collection WHERE id_str = %s", (collection_str_id,))
                res = cur.fetchone()
                if not res:
                    raise Exception(f"Collection {collection_str_id} not found.")
                collection_pk = res[0]
                # Avoid same str id
                cur.execute("SELECT id_str FROM indoorfeature WHERE collection_id = %s AND id_str = %s", (collection_pk, feature_id_str))
                res = cur.fetchone()
                if res:
                    raise Exception(f"IndoorFeature {feature_id_str} already exist.")
                # Insert IndoorFeature
                LOGGER.debug("Insert indoorfeature")
                cur.execute(
                    """
                    INSERT INTO indoorfeature (id_str, collection_id, geojson_geometry ,geojson_properties)
                    VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),%s)
                    RETURNING id
                    """,
                    (feature_id_str, collection_pk, json.dumps(geometries), Json(properties))
                )
                indoorfeature_pk = cur.fetchone()[0]
                
                # Iterate and Insert Layers
                for layer in layers:
                    self._post_thematic_layer(cur, collection_pk, indoorfeature_pk, layer)

                # autocommit is False
                self.connection.commit()
            
                return feature_id_str

            except Exception as e:
                self.connection.rollback()
                print(f"Error occurred: {e}. Rolling back changes.")
                raise e
            
    def _post_thematic_layer(self, cur, coll_pk, feature_pk, layer_data):
        """
        Helper to insert a ThematicLayer and trigger its content insertion.
        """
        primal = layer_data.get('primalSpace', {})
        dual = layer_data.get('dualSpace', {})
        LOGGER.debug("Insert thematicLayer")
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
       
        layer_pk = cur.fetchone()[0]
     
        # Insert Primal Members (Cells/Boundaries) - returns duality dict 
        d_c, d_b = self._post_primal_members(cur, coll_pk, feature_pk, layer_pk, primal)
        
        # Insert Dual Members (Nodes/Edges)
        self._post_dual_members(cur, coll_pk, feature_pk, layer_pk, dual, d_c, d_b)        

    def _post_primal_members(self, cur, coll_pk, feat_pk, layer_pk, primal_data):
        """
        Helper to insert CellSpace and CellSpaceBoundary
        """
        dual_cell = {}
        dual_boundary = {}
        boundedBy = {}
        # 1. Cells
        for cell in primal_data.get('cellSpaceMember', []):
            geom_raw = cell.get('cellSpaceGeom', {})
            geom_2d = geom_raw.get('geometry2D', None) 
            geom_3d = geom_raw.get('geometry3D', None)
            
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
                coll_pk,
                feat_pk,
                layer_pk,
                cell.get('cellSpaceName'),
                str(cell.get('level')),
                self.json_to_wkt(geom_2d),
                json.dumps(geom_3d),
                cell.get('poi')
            ))
            # Store cell pk for duality
            cell_pk = cur.fetchone()[0]
            duality_of_cell = cell.get('duality').split(":")[-1]
            dual_cell[duality_of_cell] = cell_pk
            # Store cell pk for boundedBy
            bbs = cell.get('boundedBy')
            if bbs:
                for b in bbs:
                    boundedBy[b.split(":")[-1]] = cell_pk
    
        # 2. Boundaries
        for bound in primal_data.get('cellBoundaryMember', []):
            geom_raw = bound.get('cellBoundaryGeom', {})
            geom_2d = geom_raw.get('geometry2D', None) 
            geom_3d = geom_raw.get('geometry3D', None)
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
                coll_pk,
                feat_pk,
                layer_pk,
                bound.get('isVirtual', False),
                self.json_to_wkt(geom_2d),
                json.dumps(geom_3d),
                boundingCell
            ))

            # Store boundary pk for duality
            boundary_pk = cur.fetchone()[0]
            if bound.get('duality'):
                duality_of_boundary = bound.get('duality').split(":")[-1]
                dual_boundary[duality_of_boundary] = boundary_pk
        
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
            
    def _post_dual_members(self, cur, coll_pk, feat_pk, layer_pk, dual_data, cell_dict, boundary_dict):
        """
        Helper to insert Nodes and Edges
        """
        # 1. Nodes
        node_pk_dict = {}
        for node in dual_data.get('nodeMember', []):
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
                coll_pk,
                feat_pk,
                layer_pk,
                self.json_to_wkt(geom_node),
                dual_cell_pk
            ))
            # update node's duality
            node_pk = cur.fetchone()[0]
            cur.execute("""
                    UPDATE cell_space_n_boundary 
                    SET duality_id = %s 
                    WHERE id = %s
                """, (node_pk, dual_cell_pk))
            node_pk_dict[node.get('id')] = node_pk

        # 2. Edges
        for edge in dual_data.get('edgeMember', []):
            geom_edge = edge.get('geometry')
            dual_boundary_pk = boundary_dict.get(edge.get('id'))
            LOGGER.debug(edge.get('id'))
            sql = """
                INSERT INTO node_n_edge 
                (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, geometry_val, weight, duality_id)
                VALUES (%s, 'edge', %s, %s, %s, ST_GeomFromText(%s, 0), %s, %s)
                RETURNING id
            """
            cur.execute(sql, (
                edge.get('id'),
                coll_pk,
                feat_pk,
                layer_pk,
                self.json_to_wkt(geom_edge),
                edge.get('weight', 1.0),
                dual_boundary_pk
            ))

            # update edge's duality
            edge_pk = cur.fetchone()[0]
            cur.execute("""
                    UPDATE cell_space_n_boundary 
                    SET duality_id = %s 
                    WHERE id = %s
                """, (edge_pk, dual_boundary_pk))
            

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
                edge_pk
            ))    
            

    def str_to_pk(self, collection_id_str, feature_id_str, layer_id_str=None):
        """
        Converts string IDs (slugs) to Database Integer Primary Keys.
        
        Args:
            collection_id_str (str): The unique string ID of the collection.
            feature_id_str (str): The unique string ID of the indoor feature.
            
        Returns:
            tuple: (collection_pk, feature_pk) or (None, None) if not found.
        """
        if not self.connection or self.connection.closed:
            self.connect()

        with self.connection.cursor() as cur:
            # We join the tables to ensure the feature actually belongs 
            # to the specified collection, providing a validity check.
            if not layer_id_str:
                query = """
                    SELECT c.id AS collection_pk, i.id AS feature_pk, t.id AS layer_pk
                    FROM thematiclayer t
                    JOIN indoorfeature i ON t.indoorfeature_id = i.id
                    JOIN collection c ON t.collection_id = c.id
                    WHERE c.id_str = %s AND i.id_str = %s AND t.id_str = %s
                """
                cur.execute(query, (collection_id_str, feature_id_str, layer_id_str))
                row = cur.fetchone()
                if row:
                    return row[0], row[1], row[2]
                else:
                    # Log warning or handle error depending on your preference
                    return None, None, None

            else:
                query = """
                    SELECT c.id AS collection_pk, i.id AS feature_pk
                    FROM indoorfeature i
                    JOIN collection c ON i.collection_id = c.id
                    WHERE c.id_str = %s AND i.id_str = %s
                """
                cur.execute(query, (collection_id_str, feature_id_str))
                row = cur.fetchone()
                
                if row:
                    return row[0], row[1]
                else:
                    # Log warning or handle error depending on your preference
                    return None, None
            
    def post_thematic_layer(self, collection_id, feature_id, layer_data):
        """
        Public wrapper: Manages connection/cursor lifecycle and commits data.
        """
        # Ensure we are connected
        if self.connection is None or self.connection.closed:
            self.connect()

        try:
            with self.connection.cursor() as cur:
                # Call the internal logic
                collection_pk, feature_pk = self.str_to_pk(collection_id, feature_id)
                self._post_thematic_layer(cur, collection_pk, feature_pk, layer_data)
                
            # Commit the transaction if successful
            self.connection.commit()
           
            
        except Exception as e:
            self.connection.rollback()
            raise e

    def delete_thematic_layer(self, collection_id, feature_id, layer_id):
        """
        Deletes a ThematicLayer and all associated data (Cells, Nodes, Edges).
        
        Args:
            collection_id (str): The collection ID.
            feature_id (str): The indoor feature ID.
            layer_id (str): The layer ID to delete.
            
        Returns:
            bool: True if deleted, False if not found.
        """        
        if self.connection is None or self.connection.closed:
            self.connect()

        try:
            with self.connection.cursor() as cur:
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
                cur.execute("""
                    DELETE FROM connects 
                    USING node_n_edge 
                    WHERE connects.edge_id = node_n_edge.id 
                      AND node_n_edge.thematiclayer_id = %s
                """, (layer_pk,))
                cur.execute("DELETE FROM interlayerconnection WHERE connected_layer_a = %s", (layer_pk,))
                cur.execute("DELETE FROM interlayerconnection WHERE connected_layer_b = %s", (layer_pk,))
                cur.execute("DELETE FROM node_n_edge WHERE thematiclayer_id = %s", (layer_pk,))
                cur.execute("DELETE FROM cell_space_n_boundary WHERE thematiclayer_id = %s", (layer_pk,))
                cur.execute("DELETE FROM thematiclayer WHERE id = %s", (layer_pk,))
            
            self.connection.commit()
            

        except Exception as e:
            self.connection.rollback()
            # Re-raise the exception to be handled by the API (returns 500 or 400)
            raise e
# endregion

# region InterlayerConnections

    def get_interlayer_connections(self, collection_str_id, feature_str_id, 
                                 connected_layer_id=None, topo_type=None, 
                                 limit=10, offset=0):
        """
        Fetches connections for a feature.
        - connected_layer_id: Matches if the ID is in EITHER connectedLayerA OR connectedLayerB.
        - topo_type: Filters by specific topological expression (e.g. EQUALS, WITHIN).
        - limit/offset: Pagination.
        """
        response = {
            "connections": [],
            "numberMatched": 0,
            "numberReturned": 0
        }

        with self.connection.cursor() as cur:
            # 1. Get Context (Collection & Feature PKs)
            cur.execute("""
                SELECT i.id 
                FROM indoorfeature i
                JOIN collection c ON i.collection_id = c.id
                WHERE c.id_str = %s AND i.id_str = %s
            """, (collection_str_id, feature_str_id))
            
            res = cur.fetchone()
            if not res:
                return response # Return empty if feature not found

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
                params.append(topo_type)

            # --- PAGINATION ---
            sql += " ORDER BY c.id ASC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            
            # Handle empty results
            if not rows:
                return response

            # Set metadata from the first row
            response["numberMatched"] = rows[0][9]

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
                response["connections"].append(conn_obj)
                
            response["numberReturned"] = len(response["connections"])
                
        return response

    def post_interlayer_connection(self, collection_str_id, feature_str_id, data):
        """
        Creates a connection.
        UPDATED: Implements Supervisor's "Direct SQL Check" to prevent duplicates 
        within the same Feature scope.
        """
        self.connect()
        
        new_id_str = data.get('id')
        topo = data.get('typeOfTopoExpression', 'others').lower()
        comment = data.get('comment', '')
        
        layers = data.get('connectedLayers', [])
        nodes = data.get('connectedNodes', [])
        cells = data.get('connectedCells', [])

        l1_str, l2_str = (layers[0], layers[1]) if len(layers) >= 2 else (None, None)
        n1_str, n2_str = (nodes[0], nodes[1]) if len(nodes) >= 2 else (None, None)
        c1_str, c2_str = (cells[0], cells[1]) if len(cells) >= 2 else (None, None)

        try:
            with self.connection.cursor() as cur:
                # 1. Resolve Context (Collection & Feature)
                cur.execute("SELECT id FROM collection WHERE id_str = %s", (collection_str_id,))
                res = cur.fetchone()
                if not res: raise Exception("Collection not found")
                coll_pk = res[0]

                cur.execute("SELECT id FROM indoorfeature WHERE id_str = %s AND collection_id = %s", (feature_str_id, coll_pk))
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

                # 5. Insert
                insert_query = """
                    INSERT INTO interlayerconnection 
                    (id_str, collection_id, indoorfeature_id, 
                     connected_layer_a, connected_layer_b, 
                     connected_node_a, connected_node_b,
                     connected_cell_a, connected_cell_b,
                     topo_type, comment)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                cur.execute(insert_query, (
                    new_id_str, coll_pk, feat_pk, 
                    l1_pk, l2_pk, 
                    n1_pk, n2_pk, 
                    c1_pk, c2_pk, 
                    topo, comment
                ))
                
                self.connection.commit()
                return new_id_str

        except Exception as e:
            self.connection.rollback()
            LOGGER.error(f"DB Error: {e}")
            return None
        
    def delete_interlayer_connection(self, collection_str, item_str, connection_id):
        """
        Deletes an InterLayerConnection.
        """
        self.connect()
        
        # FIX: Changed table name from 'interlayer_connection' to 'interlayerconnection'
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
                cur.execute(query, (connection_id, item_str, collection_str))
                
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
            
    def get_primal_features(self, collection_id, item_id, layer_str_id, 
                                         level=None, poi=None, is_virtual=None, cell_space_name=None):
        """
        1. Resolves layer metadata.
        2. Fetches Spaces (Filtered by level, poi, name).
        3. Fetches Boundaries (Filtered by is_virtual AND parent Spaces).
        Returns: layer_row, spaces_list, boundaries_list
        """
        
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
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
            cur.execute(layer_query, (layer_str_id, collection_id, item_id))
            layer_row = cur.fetchone()

            if not layer_row:
                return None, [], []

            layer_internal_id = layer_row['id']
            
            # -----------------------------------------------------------------
            # STEP 2: Fetch Spaces (with Filters)
            # -----------------------------------------------------------------
            spaces_query = """
                SELECT 
                    cs.id, cs.id_str, cs.cell_name, cs.level, cs.poi, 
                    cs.external_reference,
                    cs.bounded_by_cell_id,
                    ST_AsText("2D_geometry") as geometry_2d, 
                    "3D_geometry" as geometry_3d,
                    ne.id_str as duality_ref 
                FROM cell_space_n_boundary cs
                LEFT JOIN node_n_edge ne ON cs.duality_id = ne.id
                WHERE cs.thematiclayer_id = %s AND cs.type = 'space'
            """
            spaces_params = [layer_internal_id]

            # --- Apply Space Filters ---
            if level is not None:
                spaces_query += " AND cs.level = %s"
                spaces_params.append(level)
            
            if poi is not None:
                spaces_query += " AND cs.poi = %s"
                spaces_params.append(poi)

            if cell_space_name:
                spaces_query += " AND cs.cell_name ILIKE %s"                
                spaces_params.append(f"%{cell_space_name}%")
            
            cur.execute(spaces_query, tuple(spaces_params))
            space_rows = cur.fetchall()

            # Collect Space IDs to filter boundaries later
            found_space_ids = [row['id'] for row in space_rows]
            spaces = []

            for row in space_rows:
                geom = {
                    "geometry2D": self.wkt_to_json(row['geometry_2d']),
                    "geometry3D": row['geometry_3d']
                }
                spaces.append({
                    "internal_id": row['id'], 
                    "json": {
                        "id": row['id_str'],
                        "featureType": "CellSpace",
                        "cellSpaceName": row['cell_name'],
                        "level": row['level'],
                        "poi": row['poi'],
                        "duality": f"{row['duality_ref']}" if row['duality_ref'] else None,
                        "cellSpaceGeom": geom,
                        "externalReference": row['external_reference'],
                        "boundedBy": [] # To be filled
                    }
                })

            # -----------------------------------------------------------------
            # STEP 3: Fetch Boundaries (Dependent on Spaces)
            # -----------------------------------------------------------------
            # If we filtered spaces and found NONE, we should not fetch boundaries (unless query was boundaries-only?)
            # Usually in PrimalSpace, if you filter "Level 1", you want Level 1 walls.
            
            should_fetch_boundaries = True
            # Logic: If we applied space filters (level/poi/name) and found nothing, stop.
            if (level or poi or cell_space_name) and not found_space_ids:
                should_fetch_boundaries = False
            
            boundaries = []
            boundaries_map = {} 

            if should_fetch_boundaries:
                LOGGER.debug("Fetch Cell boundaries")
                bound_query = """
                    SELECT 
                        cs.id_str, cs.is_virtual, cs.external_reference,
                        cs.bounded_by_cell_id,
                        ST_AsText(cs."2D_geometry") as geometry_2d, 
                        cs."3D_geometry" as geometry_3d,
                        ne.id_str as duality_ref
                    FROM cell_space_n_boundary cs
                    LEFT JOIN node_n_edge ne ON cs.duality_id = ne.id
                    WHERE cs.thematiclayer_id = %s AND cs.type = 'boundary'
                """
                bound_params = [layer_internal_id]

                # Filter A: Only boundaries relevant to the spaces we found
                if level or poi or cell_space_name:
                    LOGGER.debug(found_space_ids)
                    bound_query += " AND cs.bounded_by_cell_id = ANY(%s)"
                    bound_params.append(found_space_ids)
                
                # Filter B: Virtual Status
                if is_virtual:
                    bound_query += " AND cs.is_virtual = %s"
                    bound_params.append(is_virtual)

                cur.execute(bound_query, tuple(bound_params))
                bound_rows = cur.fetchall()

                for row in bound_rows:
                    geom = {
                        "geometry2D": self.wkt_to_json(row['geometry_2d']),
                        "geometry3D": row['geometry_3d']
                    }
                    boundary_ref = f"{row['id_str']}"
                    
                    # Map boundary to parent space
                    parent_id = row['bounded_by_cell_id']
                    if parent_id:
                        if parent_id not in boundaries_map:
                            boundaries_map[parent_id] = []
                        boundaries_map[parent_id].append(boundary_ref)

                    boundaries.append({
                        "id": row['id_str'],
                        "featureType": "CellBoundary",
                        "isVirtual": row['is_virtual'],
                        "duality": f"{row['duality_ref']}" if row['duality_ref'] else None,
                        "cellBoundaryGeom": geom,
                        "externalReference": row['external_reference']
                    })

            # STEP 4: Link Boundaries to Spaces
            final_spaces = []
            for sp in spaces:
                internal_id = sp['internal_id']
                if internal_id in boundaries_map:
                    sp['json']['boundedBy'] = boundaries_map[internal_id]
                final_spaces.append(sp['json'])
            
            return layer_row, final_spaces, boundaries
        
    # Creates a CellSpace or CellBoundary member in the specified layer.
    def post_primal_member(self, collection_str_id, item_str_id, layer_str_id, data):
        self.connect()

        try: 
            
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                
                # --- A. Lookup Context ---
                lookup_sql = """
                    SELECT t.id, t.collection_id, t.indoorfeature_id 
                    FROM thematiclayer t
                    WHERE t.id_str = %s
                      AND t.indoorfeature_id = (SELECT id FROM indoorfeature WHERE id_str = %s)
                      AND t.collection_id = (SELECT id FROM collection WHERE id_str = %s)
                """
                cur.execute(lookup_sql, (layer_str_id, item_str_id, collection_str_id))
                layer_row = cur.fetchone()
                
                if not layer_row:
                    print(f"Layer context not found for {layer_str_id}")
                    return None

                # --- B. Parse Data ---
                f_type = data.get('featureType')
                id_str = data.get('id')
                external_ref = json.dumps(data.get('externalReference')) if data.get('externalReference') else None
                
                # Safe integer conversion for duality
                duality_raw = str(data.get('duality', ''))
                duality_id = int(duality_raw.replace('#', '')) if duality_raw.replace('#', '').isdigit() else None

                db_type = None
                cell_name = None
                level = None
                poi = False
                is_virtual = False
                geom_2d_json = None
                geom_3d_json = None
                bounded_by_refs = [] 

                if f_type == 'CellSpace':
                    db_type = 'space'
                    cell_name = data.get('cellSpaceName') or data.get('cellSpaceName:')
                    level = data.get('level')
                    poi = data.get('poi', False)
                    
                    raw_bounds = data.get('boundedBy', [])
                    for b_ref in raw_bounds:
                        bounded_by_refs.append(b_ref.replace('#', ''))

                    # --- C. Validation ---
                    if bounded_by_refs:
                        unique_refs = list(set(bounded_by_refs))
                        check_sql = """
                            SELECT COUNT(*) as cnt 
                            FROM cell_space_n_boundary 
                            WHERE id_str = ANY(%s) 
                              AND thematiclayer_id = %s
                              AND type = 'boundary'
                        """
                        cur.execute(check_sql, (unique_refs, layer_row['id']))
                        res = cur.fetchone()
                        
                        if res['cnt'] != len(unique_refs):
                            print(f"Validation Failed: Missing boundaries in layer {layer_str_id}")
                            return None 

                    geom_root = data.get('cellSpaceGeom', {})
                    if geom_root.get('geometry2D'): geom_2d_json = json.dumps(geom_root['geometry2D'])
                    if geom_root.get('geometry3D'): geom_3d_json = json.dumps(geom_root['geometry3D'])

                elif f_type == 'CellBoundary':
                    db_type = 'boundary'
                    is_virtual = data.get('isVirtual', False)
                    geom_root = data.get('cellBoundaryGeom', {})
                    geom_2d_wkt = self.json_to_wkt(geom_root.get('geometry2D'))
                    geom_3d_wkt = self.json_to_wkt(geom_root.get('geometry3D'))
                
                else:
                    return None 

                # --- D. Insert ---
                insert_query = """
                    INSERT INTO cell_space_n_boundary (
                        id_str, type, collection_id, indoorfeature_id, thematiclayer_id,
                        "2D_geometry", "3D_geometry", 
                        cell_name, duality_id, level, poi, is_virtual, external_reference
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        ST_GeomFromText(%s, 0), 
                        ST_GeomFromText(%s, 0), 4326),
                        %s, %s, %s, %s, %s, %s
                    ) RETURNING id, id_str
                """
                
                cur.execute(insert_query, (
                    id_str, db_type, layer_row['collection_id'], layer_row['indoorfeature_id'], layer_row['id'],
                    geom_2d_wkt, geom_3d_wkt,
                    cell_name, duality_id, level, poi, is_virtual, external_ref
                ))
                
                new_row = cur.fetchone()
                new_internal_id = new_row['id']
                new_str_id = new_row['id_str']

                # --- E. Link Boundaries ---
                # WARNING: This overwrites the boundary's parent. 
                # If this boundary is shared between two rooms, the first room loses the link.
                if f_type == 'CellSpace' and bounded_by_refs:
                    update_boundaries_sql = """
                        UPDATE cell_space_n_boundary
                        SET bounded_by_cell_id = %s
                        WHERE id_str = ANY(%s) 
                          AND thematiclayer_id = %s
                    """
                    cur.execute(update_boundaries_sql, (
                        new_internal_id, 
                        bounded_by_refs, 
                        layer_row['id']
                    ))

                # 4. FIX: Commit only if we get here successfully
                self.connection.commit()
                return new_str_id

        except Exception as e:
            # 5. FIX: Rollback on any error (lookup, validation, or insert)
            if self.connection:
                self.connection.rollback()
            print(f"Insert Error: {e}")
            return None
            
    def delete_primal_member(self, collection_str, item_str, layer_str, member_id):
        """
        Deletes a CellSpace.
        1. Finds the Dual Node.
        2. Breaks connections in 'connects' table (Topological Delete).
        3. KEEPS the Edge features (Geometric Preservation).
        4. Deletes the Node and CellSpace.
        """
        self.connect()

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. START ATOMIC TRANSACTION
                cur.execute("BEGIN;")

                # --- STEP A: Verify Space Existence ---
                check_sql = """
                    SELECT id FROM cell_space_n_boundary
                    WHERE id_str = %s 
                    AND type = 'space'
                    AND thematiclayer_id = (
                        SELECT t.id FROM thematiclayer t
                        JOIN collection col ON t.collection_id = col.id
                        JOIN indoorfeature i ON t.indoorfeature_id = i.id
                        WHERE t.id_str = %s AND col.id_str = %s AND i.id_str = %s
                    )
                """
                cur.execute(check_sql, (member_id, layer_str, collection_str, item_str))
                row = cur.fetchone()
                
                if not row:
                    cur.execute("ROLLBACK;")
                    return False
                
                space_id = row['id']

                # --- STEP B: Find the Dual Node (State) ---
                dual_sql = "SELECT id FROM node_n_edge WHERE duality_id = %s"
                cur.execute(dual_sql, (space_id,))
                node_rows = cur.fetchall()
                
                for node_row in node_rows:
                    node_id = node_row['id']

                    # 1. Delete Interlayer Connections
                    # These are purely logical links, so we delete them.
                    cur.execute("""
                        DELETE FROM interlayerconnection 
                        WHERE state_id_1 = %s OR state_id_2 = %s
                    """, (node_id, node_id))

                    # 2. Find Connected Edges
                    cur.execute("""
                        SELECT edge_id FROM connects 
                        WHERE node_source_id = %s OR node_target_id = %s
                    """, (node_id, node_id))
                    edge_ids = [r['edge_id'] for r in cur.fetchall()]

                    if edge_ids:
                        # 3. Delete ONLY the connection logic
                        # We delete the row from 'connects' because it references the node we are about to kill.
                        # This leaves the Edge Feature (node_n_edge) alive but disconnected.
                        cur.execute("DELETE FROM connects WHERE edge_id = ANY(%s)", (edge_ids,))
                    
                    # 4. Delete the Node (State)
                    # Now safe to delete because 'connects' no longer references it.
                    cur.execute("DELETE FROM node_n_edge WHERE id = %s", (node_id,))

                # --- STEP C: Unlink Boundaries ---
                cur.execute("""
                    UPDATE cell_space_n_boundary 
                    SET bounded_by_cell_id = NULL 
                    WHERE bounded_by_cell_id = %s
                """, (space_id,))

                # --- STEP D: Delete the Space ---
                cur.execute("DELETE FROM cell_space_n_boundary WHERE id = %s", (space_id,))

                cur.execute("COMMIT;")
                return True

        except Exception as e:
            if self.connection:
                self.connection.rollback()
            print(f"Delete Primal Error: {e}")
            return False
        finally:
            self.disconnect()
        
    def get_primal_member(self, collection_str, item_str, layer_str, member_id):
        """
        Fetches a single Primal Member.
        Ensures SQL alias 'duality' matches API handler expectations.
        """
        self.connect()

        query = """
            SELECT 
                parent.id_str, 
                parent.type, 
                parent.cell_name, 
                parent.level, 
                parent.poi, 
                parent.is_virtual, 
                parent.external_reference,
                ST_AsText(parent."2D_geometry") as geometry_2d, 
                ST_AsText(parent."3D_geometry") as geometry_3d,
                
                parent.duality_id as debug_duality_int,

                dual.id_str as duality, 

                (
                    SELECT array_agg(child.id_str)
                    FROM cell_space_n_boundary child
                    WHERE child.bounded_by_cell_id = parent.id
                ) as bounded_by_list

            FROM cell_space_n_boundary parent
            LEFT JOIN node_n_edge dual ON parent.duality_id = dual.id
            
            WHERE parent.id_str = %s 
            AND parent.thematiclayer_id = (
                SELECT t.id FROM thematiclayer t
                WHERE t.id_str = %s
                    AND t.indoorfeature_id = (SELECT id FROM indoorfeature WHERE id_str = %s)
                    AND t.collection_id = (SELECT id FROM collection WHERE id_str = %s)
            )
        """
        
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                # Ensure params match SQL order: member, layer, item, collection
                cur.execute(query, (member_id, layer_str, item_str, collection_str))
                result = cur.fetchone()
                
                if not result:
                    return None

                if result.get('bounded_by_list') is None:
                    result['bounded_by_list'] = []
                

                response = {}
        
                if result['type'] == 'space':
                    response = {
                        "id": result['id_str'],
                        "featureType": "CellSpace",
                        "cellSpaceName": result.get('cell_name'),
                        "level": result.get('level'),
                        "poi": result.get('poi', False),
                        "duality": f"{result['duality_id']}" if result.get('duality_id') else None,
                        "cellSpaceGeom": {
                            "geometry2D": json.loads(result['geometry_2d']) if result.get('geometry_2d') else None,
                            "geometry3D": json.loads(result['geometry_3d']) if result.get('geometry_3d') else None
                        },
                        "externalReference": result.get('external_reference'),
                        # Convert the list of IDs ["B1", "B2"] to URI refs ["#B1", "#B2"]
                        "boundedBy": [f"#{b_id}" for b_id in result['bounded_by_list']] if result.get('bounded_by_list') else []
                    }
                
                elif result['type'] == 'boundary':
                    response = {
                        "id": result['id_str'],
                        "featureType": "CellBoundary",
                        "isVirtual": result.get('is_virtual', False),
                        "duality": f"{result['duality_id']}" if result.get('duality_id') else None,
                        "cellBoundaryGeom": {
                            "geometry2D": self.wkt_to_json(result.get('geometry_2d')),
                            "geometry3D": self.wkt_to_json(result.get('geometry_3d'))
                        },
                        "externalReference": result.get('external_reference')
                    }
                return response 
                
        except Exception as e:
            print(f"Get Member Error: {e}")
            return None
        finally:
            self.disconnect()

    def update_primal_member(self, collection_str, item_str, layer_str, member_id, data):
        """
        Updates a CellSpace. 
        Strictly ignores Geometry updates.
        Allows updating: cell_name, level, poi, is_virtual, duality, external_reference, and boundedBy relationships.
        """
        self.connect()
        
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                
                # --- A. Resolve Parent Layer IDs ---
                lookup_sql = """
                    SELECT t.id 
                    FROM thematiclayer t
                    WHERE t.id_str = %s
                    AND t.indoorfeature_id = (SELECT id FROM indoorfeature WHERE id_str = %s)
                    AND t.collection_id = (SELECT id FROM collection WHERE id_str = %s)
                """
                cur.execute(lookup_sql, (layer_str, item_str, collection_str))
                layer_row = cur.fetchone()
                
                if not layer_row:
                    return False 

                # --- B. Check Member Existence ---
                # We also verify it is a 'space' here
                check_sql = "SELECT id, type FROM cell_space_n_boundary WHERE id_str = %s AND thematiclayer_id = %s"
                cur.execute(check_sql, (member_id, layer_row['id']))
                target_row = cur.fetchone()

                if not target_row or target_row['type'] != 'space':
                    return False 

                internal_id = target_row['id']
                
                # --- C. Dynamic Field Construction ---
                fields = []
                values = []
                
                # Handle client typo/legacy support
                if 'cellSpaceName:' in data: 
                    fields.append("cell_name = %s")
                    values.append(data['cellSpaceName:'])
                
                if 'level' in data:
                    fields.append("level = %s")
                    values.append(data['level'])
                    
                if 'poi' in data:
                    fields.append("poi = %s")
                    values.append(data['poi'])
                    
                if 'isVirtual' in data:
                    fields.append("is_virtual = %s")
                    values.append(data['isVirtual'])

                if 'externalReference' in data:
                    fields.append("external_reference = %s")
                    values.append(json.dumps(data['externalReference']))
                
                if 'duality' in data:
                    d_str = str(data['duality']).replace('#', '')
                    d_val = int(d_str) if d_str.isdigit() else None
                    fields.append("duality_id = %s")
                    values.append(d_val)

                # execute Update if we have fields
                if fields:
                    update_sql = f"UPDATE cell_space_n_boundary SET {', '.join(fields)} WHERE id = %s"
                    values.append(internal_id)
                    cur.execute(update_sql, tuple(values))

                # --- D. Handle 'boundedBy' Relationship ---
                if 'boundedBy' in data:
                    raw_bounds = data['boundedBy'] # e.g., ["#B1", "#B2"]
                    new_boundary_ids = [str(b).replace('#', '') for b in raw_bounds]
                    
                    # 1. Validation: Ensure all new boundaries exist
                    if new_boundary_ids:
                        check_refs = list(set(new_boundary_ids))
                        count_sql = """
                            SELECT COUNT(*) as cnt FROM cell_space_n_boundary 
                            WHERE id_str = ANY(%s) AND thematiclayer_id = %s AND type = 'boundary'
                        """
                        cur.execute(count_sql, (check_refs, layer_row['id']))
                        if cur.fetchone()['cnt'] != len(check_refs):
                            # Rollback is handled by the except block below
                            print("Validation Failed: One or more boundaries do not exist.")
                            raise ValueError("Invalid Boundary References")

                    # 2. Strategy: Unlink ALL, then Link NEW (Simpler & Safer)
                    
                    # Step 2a: Unlink everything this space currently owns
                    unlink_all_sql = "UPDATE cell_space_n_boundary SET bounded_by_cell_id = NULL WHERE bounded_by_cell_id = %s"
                    cur.execute(unlink_all_sql, (internal_id,))

                    # Step 2b: Link the new list (if any)
                    # WARNING: Again, this steals the wall if it belonged to another room.
                    if new_boundary_ids:
                        link_new_sql = """
                            UPDATE cell_space_n_boundary
                            SET bounded_by_cell_id = %s
                            WHERE id_str = ANY(%s) AND thematiclayer_id = %s
                        """
                        cur.execute(link_new_sql, (internal_id, new_boundary_ids, layer_row['id']))

                self.connection.commit()
                return True

        except Exception as e:
            if self.connection:
                self.connection.rollback()
            print(f"Update failed: {e}")
            return False

# endregion

# region DualSpaceLayer

    def post_dual_member(self, collection_str, item_str, layer_str, data):
        self.connect()

        try:
            # Use self.connection instead of self.conn
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                
                # --- Resolve Layer Context ---
                lookup_sql = """
                    SELECT t.id, t.collection_id, t.indoorfeature_id 
                    FROM thematiclayer t
                    WHERE t.id_str = %s
                    AND t.indoorfeature_id = (SELECT id FROM indoorfeature WHERE id_str = %s)
                    AND t.collection_id = (SELECT id FROM collection WHERE id_str = %s)
                """
                cur.execute(lookup_sql, (layer_str, item_str, collection_str))
                layer_row = cur.fetchone()
                if not layer_row: 
                    return None

                f_type = data.get('featureType')
                id_str = data.get('id')
                geom_json = json.dumps(data.get('geometry')) if data.get('geometry') else None

                # ============================
                # CASE A: NODE
                # ============================
                if f_type == 'Node':
                    duality_ref = data.get('duality') 
                    
                    if not duality_ref:
                        raise ValueError("Node must have a 'duality' reference to a CellSpace.")

                    clean_duality = str(duality_ref).replace('#', '')

                    # 1. Verify Duality Target (Must be a Space)
                    check_space_sql = """
                        SELECT id FROM cell_space_n_boundary 
                        WHERE id_str = %s AND indoorfeature_id = %s AND type = 'space'
                    """
                    cur.execute(check_space_sql, (clean_duality, layer_row['indoorfeature_id']))
                    space_row = cur.fetchone()
                    
                    if not space_row:
                        raise ValueError(f"Duality target '{clean_duality}' does not exist or is not a CellSpace.")
                    
                    primal_id = space_row['id']

                    # 2. Insert Node
                    insert_node_sql = """
                        INSERT INTO node_n_edge (
                            id_str, type, collection_id, indoorfeature_id, thematiclayer_id,
                            geometry_val, duality_id
                        ) VALUES (
                            %s, 'node', %s, %s, %s,
                            ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s
                        ) RETURNING id, id_str
                    """
                    cur.execute(insert_node_sql, (
                        id_str, layer_row['collection_id'], layer_row['indoorfeature_id'], layer_row['id'],
                        geom_json, primal_id
                    ))
                    new_node = cur.fetchone()

                    # 3. Reverse Link: Update Space -> Point to Node
                    update_space_sql = "UPDATE cell_space_n_boundary SET duality_id = %s WHERE id = %s"
                    cur.execute(update_space_sql, (new_node['id'], primal_id))
                    
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
                    primal_id = None
                    
                    if duality_ref:
                        clean_duality = str(duality_ref).replace('#', '')
                        # Check if Boundary exists
                        check_bound_sql = """
                            SELECT id FROM cell_space_n_boundary 
                            WHERE id_str = %s AND indoorfeature_id = %s AND type = 'boundary'
                        """
                        cur.execute(check_bound_sql, (clean_duality, layer_row['indoorfeature_id']))
                        bound_row = cur.fetchone()
                        
                        if not bound_row:
                            raise ValueError(f"Duality target '{clean_duality}' does not exist or is not a CellBoundary.")
                        primal_id = bound_row['id']

                    # 2. Resolve Connected Nodes (Handling Directionality!)
                    ref_source = str(connects[0]).replace('#', '')
                    ref_target = str(connects[1]).replace('#', '')
                    
                    check_nodes_sql = "SELECT id, id_str FROM node_n_edge WHERE id_str = ANY(%s) AND thematiclayer_id = %s AND type = 'node'"
                    cur.execute(check_nodes_sql, ([ref_source, ref_target], layer_row['id']))
                    node_rows = cur.fetchall() # Returns list of dicts

                    if len(node_rows) != 2:
                        # Check if it's a loop (connecting to self) or actually missing
                        if ref_source == ref_target and len(node_rows) == 1:
                            pass # Self-loops are rare in indoorGML but possible
                        else:
                            raise ValueError("One or both connected States do not exist.")

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
                            ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s, %s
                        ) RETURNING id, id_str
                    """
                    
                    cur.execute(insert_edge_sql, (
                        id_str, layer_row['collection_id'], layer_row['indoorfeature_id'], layer_row['id'],
                        geom_json, data.get('weight', 1.0), primal_id
                    ))
                    new_edge = cur.fetchone()

                    # 4. Insert 'connects' Link
                    insert_link_sql = "INSERT INTO connects (node_source_id, node_target_id, edge_id) VALUES (%s, %s, %s)"
                    cur.execute(insert_link_sql, (source_id, target_id, new_edge['id']))
                    
                    # 5. Reverse Link (If duality existed)
                    if primal_id:
                        update_bound_sql = "UPDATE cell_space_n_boundary SET duality_id = %s WHERE id = %s"
                        cur.execute(update_bound_sql, (new_edge['id'], primal_id))

                    self.connection.commit()
                    return new_edge['id_str']
                
                return None

        except Exception as e:
            if self.connection:
                self.connection.rollback()
            print(f"Dual Member Creation Error: {e}")
            # Re-raise so the API knows to return 400/500
            raise ValueError(f"Failed to create member: {str(e)}")

    def get_dual_features_and_metadata(self, collection_str, item_str, layer_str, min_weight=None, max_weight=None):
        """
        1. Fetches Layer Metadata.
        2. Fetches Members (Nodes & Edges).
           - EDGES are filtered by min_weight/max_weight.
           - TODO: Only Nodes connected to Edges when filtered.
                All Nodes when Edges are not filtered.
        3. Fetches Topology (Connections) and maps them.
        Returns: meta_row, nodes_list, edges_list
        """
        self.connect()
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                
                # STEP 1: Layer Metadata
                meta_query = """
                    SELECT 
                        t.id, t.id_str, t.dualspace_id_str,
                        t.d_creation_datetime, t.d_termination_datetime
                    FROM thematiclayer t
                    JOIN collection c ON t.collection_id = c.id
                    JOIN indoorfeature i ON t.indoorfeature_id = i.id
                    WHERE t.id_str = %s AND c.id_str = %s AND i.id_str = %s
                """
                cur.execute(meta_query, (layer_str, collection_str, item_str))
                meta_row = cur.fetchone()

                if not meta_row:
                    return None, [], []

                layer_internal_id = meta_row['id']

                # STEP 2: Fetch Raw Members (Nodes & Edges)
                # We get the Duality String here via JOIN
                members_query = """
                    SELECT 
                        ne.id_str, 
                        ne.type, 
                        ne.weight, 
                        ST_AsGeoJSON(ne.geometry_val) as geometry,
                        cs.id_str as duality
                    FROM node_n_edge ne
                    LEFT JOIN cell_space_n_boundary cs ON ne.duality_id = cs.id
                    WHERE ne.thematiclayer_id = %s
                """
                params = [layer_internal_id]

                # --- Apply Edge Filters ---
                # We use (type = 'node' OR ...) to ensure we don't hide the nodes 
                # even if they have no weight.
                
                if min_weight is not None:
                    members_query += " AND (ne.type = 'node' OR ne.weight > %s)"
                    params.append(min_weight)

                if max_weight is not None:
                    members_query += " AND (ne.type = 'node' OR ne.weight < %s)"
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
                filtering_active = (min_weight is not None) or (max_weight is not None)

                # C. Build Final Lists
                for row in member_rows:
                    mid = row['id_str']
                    geom = json.loads(row['geometry']) if row['geometry'] else None
                    
                    # --- PROCESSING EDGE ---
                    if row['type'] == 'edge':
                        # Edges in member_rows are already filtered by SQL. Just add them.
                        obj = {
                            "id": mid,
                            "featureType": "Edge",
                            "duality": row['duality'],
                            "geometry": geom,
                            "weight": row['weight'] if row['weight'] is not None else 0.0,
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

                return meta_row, nodes, edges

        except Exception as e:
            print(f"Dual Layer Error: {e}")
            return None, [], []
        finally:
            self.disconnect()

    def get_dual_member(self, collection_str, item_str, layer_str, member_id):
        """
        Fetches a SINGLE Node or Edge.
        1. Resolves Duality String.
        2. IF EDGE: Fetches Source/Target via JOIN.
        3. IF NODE: Fetches Connected Edges via SUBQUERY.
        """
        self.connect()
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT 
                        ne.id_str, 
                        ne.type, 
                        ne.weight, 
                        ST_AsGeoJSON(ne.geometry_val) as geometry,
                        
                        -- 1. Duality String (Alias 'duality' for API)
                        cs.id_str as duality,

                        -- 2. EDGE TOPOLOGY (If this member is an Edge)
                        n_source.id_str as source_ref,
                        n_target.id_str as target_ref,

                        -- 3. NODE TOPOLOGY (If this member is a Node)
                        -- We aggregate all edges where this node is Source OR Target
                        (
                            SELECT array_agg(e.id_str)
                            FROM connects c
                            JOIN node_n_edge e ON c.edge_id = e.id
                            WHERE c.node_source_id = ne.id OR c.node_target_id = ne.id
                        ) as node_connects_list

                    FROM node_n_edge ne
                    
                    -- Join Duality
                    LEFT JOIN cell_space_n_boundary cs ON ne.duality_id = cs.id
                    
                    -- Join Topology (Works ONLY if 'ne' is an Edge)
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
                cur.execute(query, (member_id, layer_str, collection_str, item_str))
                result = cur.fetchone()


                # 1. Base Response
                response = {
                    "id": result['id_str'],
                    # Map DB 'node'/'edge' -> Schema 'Node'/'Edge'
                    "featureType": "Node" if result['type'] == 'node' else "Edge",
                    "geometry": self.wkt_to_json(result.get('geometry')),
                    "duality": f"{result['duality_ref']}" if result['duality_ref'] else None
                }

                # 2. Add Edge-Specific Fields
                if result['type'] == 'edge':
                    response["weight"] = float(result['weight']) if result['weight'] is not None else 1.0
                    
                    connects = []
                    if result['source_ref']: connects.append(f"{result['source_ref']}")
                    if result['target_ref']: connects.append(f"{result['target_ref']}")
                    
                    response["connects"] = connects
                
                return response

        except Exception as e:
            print(f"Get Dual Member Error: {e}")
            return None
        finally:
            self.disconnect() 

    def update_dual_member(self, collection_str, item_str, layer_str, member_id, data):
        """
        Updates an Edge's weight.
        Strictly prevents updates to Nodes.
        """
        self.connect()

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                # One SQL command to rule them all:
                # 1. Joins the hierarchy to validate the URL path
                # 2. Filters by type='edge' to protect Nodes
                # 3. Updates the weight
                # 4. Returns the ID to confirm success
                update_sql = """
                    UPDATE node_n_edge 
                    SET weight = %s 
                    WHERE id_str = %s 
                    AND type = 'edge'
                    AND thematiclayer_id = (
                        SELECT t.id FROM thematiclayer t
                        JOIN collection col ON t.collection_id = col.id
                        JOIN indoorfeature i ON t.indoorfeature_id = i.id
                        WHERE t.id_str = %s 
                          AND col.id_str = %s 
                          AND i.id_str = %s
                    )
                    RETURNING id;
                """
                
                cur.execute(update_sql, (
                    data.get('weight'), 
                    member_id, 
                    layer_str, 
                    collection_str, 
                    item_str
                ))
                
                result = cur.fetchone()
                
                # In autocommit mode, we don't call .commit()
                # If result exists, the update is already permanent.
                return True if result else False

        except Exception as e:
            print(f"Update Error: {e}")
            return False
        finally:
            # THIS IS THE KEY: Disconnect after every request to force 
            # the next GET request to see the fresh data snapshot.
            self.disconnect()


    def delete_dual_member(self, collection_str, item_str, layer_str, member_id):
        """
        Deletes a Node or Edge from a Thematic Layer.
        
        Cascading Rules:
        1. If Node (State):
           - Remove InterlayerConnections (Links to other Thematic Layers).
           - Remove connected Edges (Intra-layer transitions).
           - Remove 'connects' table entries.
           - Clear Primal Duality (Room references).
        2. If Edge (Transition):
           - Remove 'connects' table entries.
           - Clear Primal Duality (Boundary references).
        """
        self.connect() # autocommit=True

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. START ATOMIC TRANSACTION
                cur.execute("BEGIN;")
                
                # --- Resolve Layer Context ---
                lookup_sql = """
                    SELECT t.id FROM thematiclayer t
                    WHERE t.id_str = %s
                    AND t.indoorfeature_id = (SELECT id FROM indoorfeature WHERE id_str = %s)
                    AND t.collection_id = (SELECT id FROM collection WHERE id_str = %s)
                """
                cur.execute(lookup_sql, (layer_str, item_str, collection_str))
                layer_row = cur.fetchone()
                if not layer_row: 
                    cur.execute("ROLLBACK;")
                    return False
                
                # --- Identify the Member ---
                check_sql = "SELECT id, type FROM node_n_edge WHERE id_str = %s AND thematiclayer_id = %s"
                cur.execute(check_sql, (member_id, layer_row['id']))
                target = cur.fetchone()
                
                if not target: 
                    cur.execute("ROLLBACK;")
                    return False 

                # =========================================================
                # LOGIC BRANCH: NODE vs EDGE
                # =========================================================
                
                if target['type'] == 'node':
                    # --- A. Clean up InterlayerConnections (Cross-Layer Links) ---
                    # If this node links to a node in a DIFFERENT Thematic Layer, delete that link.
                    delete_interlayer_sql = """
                        DELETE FROM interlayerconnection 
                        WHERE state_id_1 = %s OR state_id_2 = %s
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

                # =========================================================
                # COMMON CLEANUP
                # =========================================================

                # --- STEP C: Clean up Reverse Duality (Primal Space) ---
                # Ensure no Primal Space (Room) or Boundary points to this deleted member
                cur.execute("""
                    UPDATE cell_space_n_boundary 
                    SET duality_id = NULL 
                    WHERE duality_id = %s
                """, (target['id'],))

                # --- STEP D: Final Delete of the Member ---
                cur.execute("DELETE FROM node_n_edge WHERE id = %s", (target['id'],))
                
                # Finalize
                cur.execute("COMMIT;")
                return True

        except Exception as e:
            if self.connection:
                self.connection.rollback()
            print(f"Delete Dual Member Error: {e}")
            return False
        finally:
            self.disconnect()

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
