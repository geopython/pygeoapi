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
           
            self.connection.autocommit = True 
            
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
        
        # REMOVED: new_pk_id = random.randint(...) <- No longer needed!
        
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
        Retrieves just the metadata when not filtered

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
                "type": "Feature",
                "featureType": "IndoorFeatures", # Enum: IndoorFeatures
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
                SELECT id, id_str, primalspace_id_str, dualspace_id_str, semantic_extension, theme
                FROM thematiclayer
                WHERE indoorfeature_id = %s
            """, (feature_pk,))
            
            layer_rows = cur.fetchall()
            
            # Map database ID (pk) to the layer object so we can inject content later
            # keys: layer_pk (int), values: reference to the dict inside result_feature
            layers_by_pk = {}

            for l_row in layer_rows:
                l_pk, l_id, l_p, l_d, l_se, l_t = l_row
                thematic_layer = {
                    "id": l_id,
                    "featureType": "ThematicLayer",
                    "theme": l_t if l_t else "Unknown",
                    "semanticExtension": l_se if l_se else False,
                    
                    # 1. Primal Space Object (ID + Members)
                    "primalSpace": {
                        "id": l_p,
                        "featureType": "PrimalSpaceLayer",
                        # Dates are optional/dummy here, strictly required by schema? 
                        # usually DB has timestamps, adding placeholders if null
                        "creationDatetime": "2026-01-01T00:00:00Z", 
                        "terminationDatetime": "2099-12-31T23:59:59Z",
                        "cellSpaceMember": [],
                        "cellBoundaryMember": []
                    },
                    
                    # 2. Dual Space Object (ID + Members)
                    "dualSpace": {
                        "id": l_d,
                        "featureType": "DualSpaceLayer",
                        "isLogical": True,   # Defaulting based on typical usage
                        "isDirected": True,  # Defaulting based on typical usage
                        "nodeMember": [],
                        "edgeMember": []
                    }
                }
                result_feature["IndoorFeatures"]["layers"].append(thematic_layer)
                layers_by_pk[l_pk] = thematic_layer
            
            # ---------------------------------------------------------
            # 3. Fetch CellSpaces (with Level Filter)
            # ---------------------------------------------------------
            # We select 3D geometry by default, fallback to 2D if needed.
            # Adjust ST_AsGeoJSON param as per your SRID requirements.

            space_sql = """
                SELECT 
                    id, id_str, thematiclayer_id, 
                    ST_AsGeoJSON(COALESCE("3D_geometry", "2D_geometry")), 
                    cell_name, level, external_reference, duality_id, poi
                FROM cell_space_n_boundary
                WHERE indoorfeature_id = %s AND type = 'space'
            """
            space_params = [feature_pk]

            if level:
                space_sql += " AND level = %s"
                space_params.append(str(level))

            cur.execute(space_sql, tuple(space_params))
            space_rows = cur.fetchall()

            valid_space_ids = set() # To filter boundaries later

            for s_row in space_rows:
                s_pk, s_id, layer_pk, s_geom_str, s_name, s_lvl, s_ext, s_duality, s_poi = s_row
                
                valid_space_ids.add(s_pk) # Keep track of valid IDs

                # Parse geometry
                s_geom = json.loads(s_geom_str) if s_geom_str else None
                
                space_obj = {
                    "type": "Feature", 
                    "featureType": "CellSpace",
                    "id": s_id,
                    "geometry": s_geom, # Matches GeoJSON requirement
                    "properties": {
                        "cellSpaceName": s_name,
                        "level": s_lvl,
                        "poi": s_poi if s_poi is not None else False,
                        "duality": s_duality,
                        "externalReference": s_ext
                    }
                }

                # Inject into the correct layer
                if layer_pk in layers_by_pk:
                    layers_by_pk[layer_pk]["primalSpace"]["cellSpaceMember"].append(space_obj)

            # ---------------------------------------------------------
            # 4. Fetch CellSpaceBoundaries (Filtered by Space IDs)
            # ---------------------------------------------------------
            # Logic: If level is set, we ONLY want boundaries connected to the spaces we found.
            # If no spaces were found for this level, we shouldn't fetch any boundaries.
            
            should_fetch_boundaries = True
            if level and not valid_space_ids:
                should_fetch_boundaries = False

            if should_fetch_boundaries:
                bound_sql = """
                    SELECT 
                        id, id_str, thematiclayer_id, 
                        ST_AsGeoJSON(COALESCE("3D_geometry", "2D_geometry")), 
                        external_reference, is_virtual
                    FROM cell_space_n_boundary
                    WHERE indoorfeature_id = %s AND type = 'boundary'
                """
                bound_params = [feature_pk]

                if level:
                    # Filter boundaries to only those pointing to our valid spaces
                    bound_sql += " AND bounded_by_cell_id = ANY(%s)"
                    bound_params.append(list(valid_space_ids))

                cur.execute(bound_sql, tuple(bound_params))
                bound_rows = cur.fetchall()

                for b_row in bound_rows:
                    b_pk, b_id, layer_pk, b_geom_str, b_ext, b_virt = b_row
                    
                    b_geom = json.loads(b_geom_str) if b_geom_str else None

                    bound_obj = {
                        "type": "Feature",
                        "featureType": "CellBoundary",
                        "id": b_id,
                        "geometry": b_geom,
                        "properties": { 
                            "isVirtual": b_virt if b_virt is not None else False,
                            "externalReference": b_ext 
                        }
                    }

                    if layer_pk in layers_by_pk:
                        layers_by_pk[layer_pk]["primalSpace"]["cellBoundaryMember"].append(bound_obj)

            # ---------------------------------------------------------
            # 5 & 6. Fetch Dual Space (Nodes & Edges) from node_n_edge
            # ---------------------------------------------------------
            # We fetch ALL dual space items (no level filtering) in one query for efficiency.
            
            dual_sql = """
                SELECT 
                    id, id_str, type, thematiclayer_id, 
                    ST_AsGeoJSON(geometry_val), 
                    duality_id, weight
                FROM node_n_edge
                WHERE indoorfeature_id = %s
            """
            cur.execute(dual_sql, (feature_pk,))
            dual_rows = cur.fetchall()

            for d_row in dual_rows:
                d_pk, d_id, d_type, layer_pk, d_geom_str, d_duality, d_weight = d_row
                
                d_geom = json.loads(d_geom_str) if d_geom_str else None
                
                # Check type to decide if it's a Node or Edge
                # Assuming 'type' column returns string 'Node' or 'Edge'
                
                # Schema: Node
                if d_type == 'node':
                    node_obj = {
                        "type": "Feature",
                        "featureType": "Node",
                        "id": d_id,
                        "geometry": d_geom,
                        "properties": {
                            "duality": d_duality,
                            "connects": [] # Populated if you have connection data
                        }
                    }
                    if layer_pk in layers_by_pk:
                        layers_by_pk[layer_pk]["dualSpace"]["nodeMember"].append(node_obj)
                
                # Schema: Edge
                elif d_type == 'edge':
                    edge_obj = {
                        "type": "Feature",
                        "featureType": "Edge",
                        "id": d_id,
                        "geometry": d_geom,
                        "properties": {
                            "weight": d_weight if d_weight is not None else 0.0,
                            "duality": d_duality,
                            "connects": [] # Populated if you have connection data
                        }
                    }
                    if layer_pk in layers_by_pk:
                        layers_by_pk[layer_pk]["dualSpace"]["edgeMember"].append(edge_obj)

            # ---------------------------------------------------------
            # 7. Fetch InterLayerConnections 
            # ---------------------------------------------------------
            cur.execute("""
                SELECT id, id_str, connected_layer_a, connected_layer_b, connected_cell_a, connected_cell_b,connected_node_a,connected_node_b,topo_type,comment
                FROM interlayerconnection
                WHERE indoorfeature_id = %s
            """, (feature_pk,))  

            connection_rows = cur.fetchall()
            for c_row in connection_rows:
                c_pk, c_id, layer_a, layer_b, cell_a, cell_b, node_a, node_b, topo, comment = c_row
                # Schema: InterLayerConnection
                interlayer_connection = {
                        "id": c_id,
                        "featureType": "InterLayerConnection",
                        "typeOfTopoExpression": topo,
                        "comment": comment,
                        "connectedLayers": [layer_a, layer_b],
                        "connectedNodes": [node_a, node_b],
                        "connectedCells": [cell_a, cell_b]
                    }
                result_feature["IndoorFeatures"]["layerConnections"].append(interlayer_connection)

        return result_feature
    
    def get_layers(self, collection_id, feature_id, theme = None, level = None, limit=10, offset=0):
        response = {
            "levels": [],
            "layers": [],
            "links": []
        }
        with self.connection.cursor() as cur:
            sql_levels = """
                SELECT DISTINCT cs.level
                FROM cell_space_n_boundary cs
                JOIN thematiclayer tl ON cs.thematiclayer_id = tl.id
                JOIN indoorfeature i ON tl.indoorfeature_id = i.id
                JOIN collection c ON i.collection_id = c.id
                WHERE c.id_str = %s AND cs.level IS NOT NULL
            """
            params_levels = [collection_id]

            if theme:
                sql_levels += " AND tl.theme = %s"
                params_levels.append(theme)
            if level:
                sql_levels += " AND cs.level = %s"
                params_levels.append(level)
            
            sql_levels += " ORDER BY cs.level"
            cur.execute(sql_levels, tuple(params_levels))
            response["levels"] = [row[0] for row in cur.fetchall()]

            # 2. Get Layer Summaries (Optionally filtered)
            sql_layers = """
                SELECT tl.id_str, tl.theme, tl.semantic_extension, i.id_str AS feature_id,
                       ST_XMin(ST_Extent(cs."3D_geometry")) as minx,
                       ST_YMin(ST_Extent(cs."3D_geometry")) as miny,
                       ST_XMax(ST_Extent(cs."3D_geometry")) as maxx,
                       ST_YMax(ST_Extent(cs."3D_geometry")) as maxy
                FROM thematiclayer tl
                JOIN indoorfeature i ON tl.indoorfeature_id = i.id
                JOIN collection c ON i.collection_id = c.id
                LEFT JOIN cell_space_n_boundary cs ON cs.thematiclayer_id = tl.id
                WHERE c.id_str = %s
            """
            params_layers = [collection_id]

            if theme:
                sql_layers += " AND tl.theme = %s"
                params_layers.append(theme)
            
            # For filtering layers by level, we need to ensure the layer HAS cells on that level
            if level:
                sql_layers += " AND cs.level = %s"
                params_layers.append(level)

            sql_layers += " GROUP BY tl.id, tl.id_str, tl.theme, i.id_str"

            cur.execute(sql_layers, tuple(params_layers))

            rows = cur.fetchall()
            for row in rows:
                l_id, l_theme, semantic_extension, feature_id, minx, miny, maxx, maxy = row
                
                bbox = [-180, -90, 180, 90]
                if minx is not None:
                    bbox = [float(minx), float(miny), float(maxx), float(maxy)]

                layer_summary = {
                    "id": l_id,
                    "semanticExtension": semantic_extension,
                    "theme": l_theme if l_theme else "Unknown",
                    "bbox": bbox,
                    "links": []
                }
                response["layers"].append(layer_summary)

        return response
    
    def get_layer(self, collection_id, feature_id, layer_id, level=None, bbox=''):
        """
        Retrieves the complete thematic layer.
        Returns a single Dictionary representing the layer or None if not found.
        """
        result_layer = None
        with self.connection.cursor() as cur:
            # 1. Fetch Layer Metadata
            # We join tables to ensure the layer belongs to the correct Feature and Collection
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
            primal = self._get_primal_space(cur, l_pk, p_id, p_create, level=level)
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

        return result_layer

    def _get_primal_space(self, cur, layer_pk, primalspace_id, p_create, level=None):
        """
        Helper to build PrimalSpaceLayer. 
        Supports optional filtering by 'level'.
        """
        import json
        bounded_by_dict = {}
        cell_map = {}
        bound_map = {}

        primal_space = {
            "id": primalspace_id, 
            "featureType": "PrimalSpaceLayer",
            "creationDatetime": p_create,
            "cellSpaceMember": [],
            "cellBoundaryMember": []
        }
        # --- Fetch Boundaries ---
        cur.execute("""
            SELECT c.id, c.id_str, c.external_reference, ST_AsGeoJSON("2D_geometry"), c.is_virtual, c.bounded_by_cell_id, n.id_str
            FROM cell_space_n_boundary c
            LEFT JOIN node_n_edge n ON c.duality_id = n.id
            WHERE c.thematiclayer_id = %s AND c.type = 'boundary'
        """, (layer_pk,))

        for row in cur.fetchall():
            b_pk, bid, bext, geom_str, is_virtual, bounded_by_c_id, duality = row
            geom = json.loads(geom_str) if geom_str else None
            
            boundary = {
                "id": bid,
                "featureType": "CellBoundary",
                "duality": duality,
                "isVirtual": is_virtual,
                "cellBoundaryGeom": {
                    "geometry2D": geom
                }
            }
            primal_space["cellBoundaryMember"].append(boundary)
            if bounded_by_c_id in bounded_by_dict:
                bounded_by_dict[bounded_by_c_id].append(bid)
            elif bounded_by_c_id:
                bounded_by_dict[bounded_by_c_id] = [bid]
            
            bound_map[bid] = b_pk
        
        # --- Fetch Cells ---
        sql_cells = """
            SELECT c.id, c.id_str, c.cell_name, c.level, c.external_reference, 
                   ST_AsGeoJSON("2D_geometry"), c.poi, n.id_str
            FROM cell_space_n_boundary c
            LEFT JOIN node_n_edge n ON c.duality_id = n.id
            WHERE c.thematiclayer_id = %s AND c.type = 'space'
        """
        params_cells = [layer_pk]

        if level is not None:
            sql_cells += " AND level = %s"
            params_cells.append(level)
            
        cur.execute(sql_cells, tuple(params_cells))
        
        for row in cur.fetchall():
            c_pk, cid, cname, clevel, cext, geom_str, poi, duality = row
            geom = json.loads(geom_str) if geom_str else None
            
            cell = {
                "id": cid,
                "featureType": "CellSpace",
                "duality": duality,
                "cellSpaceName": cname,
                "level": clevel,
                "poi": poi,
                "cellSpaceGeom": {
                    "geometry2D": geom
                },
                "boundedBy": bounded_by_dict.get(c_pk)

            }
            if cext: cell["externalReference"] = {"uri": cext}
            primal_space["cellSpaceMember"].append(cell)
            cell_map[cid] = c_pk
        

        if not primal_space["cellSpaceMember"]:
            return None
            
        return primal_space
    
    def _get_dual_space(self, cur, layer_pk, dualspace_id, d_creat,is_logical, is_directed):
        dual_space = {
            "id": dualspace_id,
            "featureType": "DualSpaceLayer",
            "isLogical": is_logical,
            "isDirected": is_directed,
            "nodeMember": [],
            "edgeMember": [],
            "creationDatetime": d_creat
        }

        node_map = {}
        edge_map = {}
        # --- Fetch Cells ---
        sql_nodes = """
            SELECT n.id_str,
                   ST_AsGeoJSON(n.geometry_val), c.id_str
            FROM node_n_edge n
            LEFT JOIN cell_space_n_boundary c ON n.duality_id = c.id
            WHERE n.thematiclayer_id = %s AND n.type = 'node'
        """
        params_nodes = [layer_pk]
            
        cur.execute(sql_nodes, tuple(params_nodes))
        
        for row in cur.fetchall():
            nid, geom_str, duality = row
            geom = json.loads(geom_str) if geom_str else None
            
            node = {
                "id": nid,
                "featureType": "Node",
                "gemetry": geom,
                "duality": duality,
                "connects": []
            }
        
            dual_space["nodeMember"].append(node)
            node_map[nid] = node

        sql_edges = """
            SELECT n.id_str,
                   ST_AsGeoJSON(n.geometry_val), n.weight, c.id_str
            FROM node_n_edge n
            LEFT JOIN cell_space_n_boundary c ON n.duality_id = c.id
            WHERE n.thematiclayer_id = %s AND n.type = 'edge'
        """
        params_edges = [layer_pk]
            
        cur.execute(sql_edges, tuple(params_edges))
        
        for row in cur.fetchall():
            eid, geom_str, weight, duality = row
            geom = json.loads(geom_str) if geom_str else None
            
            edge = {
                "id": eid,
                "featureType": "Edge",
                "gemetry": geom,
                "duality": duality,
                "weight": weight,
                "connects": []
            }
        
            dual_space["edgeMember"].append(edge)
            edge_map[eid] = edge

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

            if eid in edge_map:
                edge_map[eid]["connects"] = [
                    source_id, target_id
                ]
            if source_id in node_map:
                node_map[source_id]["connects"].append(eid)
            if target_id in node_map:
                node_map[target_id]["connects"].append(eid)

        return dual_space

    def post_indoorfeature(self, collection_str_id, indoorfeature):
        """
        Insert a indoor feature into a collection

        :param collection_id: local identifier of a collection
        :param movingfeature: IndoorFeature object or
                           

        :returns: IndoorFeature ID
        """        
        feature_id_str = indoorfeature.get('id')
        properties = indoorfeature.get('properties', {})
        
        layers = indoorfeature.get('layers', [])

        with self.connection.cursor() as cur:
            try:
                # 2. Resolve Collection DB ID (Integer) from String ID
                cur.execute("SELECT id FROM collection WHERE id_str = %s", (collection_str_id,))
                res = cur.fetchone()
                if not res:
                    raise Exception(f"Collection {collection_str_id} not found.")
                collection_pk = res[0]

                # 3. Insert Main IndoorFeature
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
     
        # Insert Primal Members (Cells/Boundaries)
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
            geom_json = geom_raw.get('geometry2D') or geom_raw.get('geometry3D') or geom_raw.get('geometry')

            # Insert Cell
            # Note: We use ST_SetSRID(ST_GeomFromGeoJSON(...), 4326) to handle the geometry conversion safely
            sql = """
                INSERT INTO cell_space_n_boundary 
                (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, 
                 cell_name, level, "2D_geometry", poi)
                VALUES (%s, 'space', %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s)
                RETURNING id
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
            geom_json = geom_raw.get('geometry2D') or geom_raw.get('geometry3D') or geom_raw.get('geometry')
            # get bounding cell primal key
            boundingCell = boundedBy.get(bound.get('id'))
            
            sql = """
                INSERT INTO cell_space_n_boundary 
                (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, 
                 is_virtual, "2D_geometry", bounded_by_cell_id)
                VALUES (%s, 'boundary', %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s)
                RETURNING id
            """
            cur.execute(sql, (
                bound.get('id'),
                coll_pk,
                feat_pk,
                layer_pk,
                bound.get('isVirtual', False),
                json.dumps(geom_json) if geom_json else None,
                boundingCell
            ))

            # Store boundary pk for duality
            boundary_pk = cur.fetchone()[0]
            duality_of_boundary = bound.get('duality').split(":")[-1]
            dual_boundary[duality_of_boundary] = boundary_pk

        return dual_cell, dual_boundary
            


    def _post_dual_members(self, cur, coll_pk, feat_pk, layer_pk, dual_data, cell_dict, boundary_dict):
        """
        Helper to insert Nodes and Edges
        """
        # 1. Nodes
        node_pk_dict = {}
        for node in dual_data.get('nodeMember', []):
            geom_json = node.get('geometry')
            dual_cell_pk = cell_dict.get(node.get('id'))
            if not dual_cell_pk:
                raise Exception("Duality cell not found")

            sql = """
                INSERT INTO node_n_edge 
                (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, geometry_val, duality_id)
                VALUES (%s, 'node', %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s)
                RETURNING id
            """
            
            cur.execute(sql, (
                node.get('id'),
                coll_pk,
                feat_pk,
                layer_pk,
                json.dumps(geom_json) if geom_json else None,
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
            geom_json = edge.get('geometry')
            dual_boundary_pk = boundary_dict.get(edge.get('id'))
            if not dual_boundary_pk:
                raise Exception("Duality boundary not found")
            sql = """
                INSERT INTO node_n_edge 
                (id_str, type, collection_id, indoorfeature_id, thematiclayer_id, geometry_val, weight, duality_id)
                VALUES (%s, 'edge', %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s, %s)
                RETURNING id
            """
            cur.execute(sql, (
                edge.get('id'),
                coll_pk,
                feat_pk,
                layer_pk,
                json.dumps(geom_json) if geom_json else None,
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
            

    def str_to_pk(self, collection_id_str, feature_id_str):
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

    def get_interlayer_connections(self, collection_str_id, feature_str_id):
        """
        Fetches connections for a feature.
        UPDATED 2026: Scoped by Collection ID to handle non-unique Feature IDs.
        """
        self.connect()
        with self.connection.cursor() as cur:
            # 1. Get Collection Anchor
            # This ensures we are looking in the right 'folder' (e.g. Busan vs Seoul)
            cur.execute("SELECT id FROM collection WHERE id_str = %s", (collection_str_id,))
            res_coll = cur.fetchone()
            if not res_coll: 
                return [] # Collection doesn't exist

            coll_pk = res_coll[0]

            # 2. Get Feature PK (Scoped lookup)
            # We filter by BOTH the feature name AND the collection PK
            cur.execute("SELECT id FROM indoorfeature WHERE id_str = %s AND collection_id = %s", (feature_str_id, coll_pk))
            res_feat = cur.fetchone()
            if not res_feat: 
                return [] # Feature doesn't exist in this collection

            feature_pk = res_feat[0]

            # 3. Fetch Connections (Using the safe feature_pk)
            query = """
                SELECT 
                    c.id_str, 
                    c.topo_type, 
                    c.comment,
                    l1.id_str as l1_id, l2.id_str as l2_id,
                    n1.id_str as n1_id, n2.id_str as n2_id,
                    cs1.id_str as c1_id, cs2.id_str as c2_id
                FROM interlayerconnection c
                LEFT JOIN thematiclayer l1 ON c.connected_layer_a = l1.id
                LEFT JOIN thematiclayer l2 ON c.connected_layer_b = l2.id
                LEFT JOIN node_n_edge n1 ON c.connected_node_a = n1.id
                LEFT JOIN node_n_edge n2 ON c.connected_node_b = n2.id
                LEFT JOIN cell_space_n_boundary cs1 ON c.connected_cell_a = cs1.id
                LEFT JOIN cell_space_n_boundary cs2 ON c.connected_cell_b = cs2.id
                WHERE c.indoorfeature_id = %s
            """
            cur.execute(query, (feature_pk,))
            rows = cur.fetchall()
            
            results = []
            for row in rows:
                # Build lists, filtering out None values (e.g. if a connection has no nodes, just layers)
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
                results.append(conn_obj)
                
        return results


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
            
    def get_primal_features_and_metadata(self, collection_id, item_id, layer_str_id):
        """
        1. Resolves layer metadata.
        2. Fetches members with JOINs for string Duality.
        3. PROCESSES the members to map 'boundedBy' correctly.
        Returns: layer_row, spaces_list, boundaries_list
        """
        self.connect()
        
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
            
            # STEP 2: Fetch Members + Duality String + Hierarchy Info
            # We LEFT JOIN node_n_edge to get the actual ID String (ne.id_str)
            members_query = """
                SELECT 
                    cs.id, 
                    cs.id_str, 
                    cs.type, 
                    cs.cell_name, 
                    cs.level, 
                    cs.poi, 
                    cs.is_virtual, 
                    cs.external_reference,
                    cs.bounded_by_cell_id,  -- Need this to map children to parents
                    ST_AsGeoJSON(cs."2D_geometry") as geometry_2d, 
                    ST_AsGeoJSON(cs."3D_geometry") as geometry_3d,
                    ne.id_str as duality_ref -- Get the String ID, not the Integer
                FROM cell_space_n_boundary cs
                LEFT JOIN node_n_edge ne ON cs.duality_id = ne.id
                WHERE cs.thematiclayer_id = %s
            """
            
            cur.execute(members_query, (layer_internal_id,))
            rows = cur.fetchall()
            
            # STEP 3: Process & Group Data (The "Fix")
            spaces = []
            boundaries = []
            boundaries_map = {} # { parent_id: ["#b1", "#b2"] }

            for row in rows:
                # Helper: Parse Geometry and Duality
                geom = {
                    "geometry2D": json.loads(row['geometry_2d']) if row['geometry_2d'] else None,
                    "geometry3D": json.loads(row['geometry_3d']) if row['geometry_3d'] else None
                }
                duality_val = f"{row['duality_ref']}" if row['duality_ref'] else None

                # -- BRANCH A: BOUNDARY --
                if row['type'] == 'boundary':
                    boundary_ref = f"{row['id_str']}"
                    
                    # Add to parent's bucket (Fixing the inverse relationship)
                    parent_id = row['bounded_by_cell_id']
                    if parent_id:
                        if parent_id not in boundaries_map:
                            boundaries_map[parent_id] = []
                        boundaries_map[parent_id].append(boundary_ref)

                    boundaries.append({
                        "id": row['id_str'],
                        "featureType": "CellBoundary",
                        "isVirtual": row['is_virtual'],
                        "duality": duality_val,
                        "cellBoundaryGeom": geom,
                        "externalReference": row['external_reference']
                    })

                # -- BRANCH B: SPACE --
                elif row['type'] == 'space':
                    spaces.append({
                        "internal_id": row['id'], # Temp ID for mapping
                        "json": {
                            "id": row['id_str'],
                            "featureType": "CellSpace",
                            "cellSpaceName": row['cell_name'],
                            "level": row['level'],
                            "poi": row['poi'],
                            "duality": duality_val,
                            "cellSpaceGeom": geom,
                            "externalReference": row['external_reference'],
                            "boundedBy": [] # Will fill this next
                        }
                    })

            # STEP 4: Inject 'boundedBy' into Spaces
            final_spaces = []
            for sp in spaces:
                internal_id = sp['internal_id']
                if internal_id in boundaries_map:
                    sp['json']['boundedBy'] = boundaries_map[internal_id]
                final_spaces.append(sp['json'])
            
            # Return distinct lists so the API handler is clean
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
                    if geom_root.get('geometry2D'): geom_2d_json = json.dumps(geom_root['geometry2D'])
                    if geom_root.get('geometry3D'): geom_3d_json = json.dumps(geom_root['geometry3D'])
                
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
                        ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 
                        ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                        %s, %s, %s, %s, %s, %s
                    ) RETURNING id, id_str
                """
                
                cur.execute(insert_query, (
                    id_str, db_type, layer_row['collection_id'], layer_row['indoorfeature_id'], layer_row['id'],
                    geom_2d_json, geom_3d_json,
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
                ST_AsGeoJSON(parent."2D_geometry") as geometry_2d, 
                ST_AsGeoJSON(parent."3D_geometry") as geometry_3d,
                
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
                    
                return result 
                
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

                if 'cellSpaceName' in data: 
                    fields.append("cell_name = %s")
                    values.append(data['cellSpaceName'])
                
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

    def get_dual_features_and_metadata(self, collection_str, item_str, layer_str):
        """
        1. Fetches Layer Metadata.
        2. Fetches Members (Nodes & Edges).
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
                cur.execute(members_query, (layer_internal_id,))
                member_rows = cur.fetchall()

                # STEP 3: Fetch Topology (The "Connects" Map)
                # We join to get String IDs for Edge, Source, and Target
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

                # --- STEP 4: Build Aggregation Maps (Python Logic) ---
                
                # For Nodes: { node_id: ["edge_1", "edge_2"] }
                node_connections = {} 
                
                # For Edges: { edge_id: ["node_A", "node_B"] }
                edge_connections = {}

                for row in topo_rows:
                    e_ref = row['edge_ref']
                    s_ref = row['source_ref']
                    t_ref = row['target_ref']

                    # 1. Populate Edge Map (Edges always have 2 nodes)
                    edge_connections[e_ref] = [s_ref, t_ref]

                    # 2. Populate Node Map (Nodes collect edges)
                    # Add Edge to Source Node
                    if s_ref not in node_connections: node_connections[s_ref] = []
                    node_connections[s_ref].append(e_ref)
                    
                    # Add Edge to Target Node
                    if t_ref not in node_connections: node_connections[t_ref] = []
                    node_connections[t_ref].append(e_ref)

                # --- STEP 5: Sort Members and Inject 'connects' ---
                nodes = []
                edges = []

                for row in member_rows:
                    mid = row['id_str']
                    
                    # Parse Geometry
                    geom = json.loads(row['geometry']) if row['geometry'] else None
                    
                    # Common structure
                    obj = {
                        "id": mid,
                        "featureType": "Node" if row['type'] == 'node' else "Transition",
                        "duality": row['duality'], # Uses the Alias from Step 2
                        "geometry": geom,
                        "connects": [] # Default empty
                    }

                    if row['type'] == 'node':
                        # Inject Edges connected to this Node
                        if mid in node_connections:
                            obj['connects'] = node_connections[mid]
                        nodes.append(obj)
                    
                    elif row['type'] == 'edge':
                        # Inject Nodes connected to this Edge
                        obj['weight'] = row['weight']
                        if mid in edge_connections:
                            obj['connects'] = edge_connections[mid]
                        edges.append(obj)

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

                # Ensure list is never None for Nodes
                if result and result.get('node_connects_list') is None:
                    result['node_connects_list'] = []

                return result

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
