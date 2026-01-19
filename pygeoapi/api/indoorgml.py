import logging
import json
import random
from http import HTTPStatus
from typing import Tuple

from pygeoapi.api import API, APIRequest, SYSTEM_LOCALE, F_HTML, F_JSON 
import pygeoapi.api as core_api
from pygeoapi.util import to_json
from pygeoapi.util import render_j2_template, to_json
import os
from jsonschema import validate, ValidationError
from datetime import datetime
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

# --- Database Imports ---
from src.database import get_db
from src.models import (
    Collection, IndoorFeature, ThematicLayer, 
    CellSpaceBoundary, NodeEdge, Connects, InterLayerConnection,
    SpaceType, CellType, NodeEdgeType
)
# --- Helper to manage DB sessions easily ---
def get_db_session():
    """Helper to get a fresh session"""
    return next(get_db())
# --- Helper for ID Generation ---
def generate_id():
    """Generates a random BigInt for Primary Keys"""
    return random.randint(1, 9223372036854775800)

# --- Helper for ID Translation --
def resolve_db_id(db, model_class, string_id):
    """
    Maps a public String ID (from URL) to a private Integer ID (for DB Foreign Keys).
    Example: 'AIST_Main' -> 93847102
    """
    if not string_id:
        return None
        
    result = db.query(model_class.id).filter(model_class.id_str == string_id).first()
    return result[0] if result else None

# Load schema once when the module is loaded
SCHEMA_PATH = 'data/indoorjson_schema.json'
with open(SCHEMA_PATH, 'r') as f:
    INDOOR_SCHEMA = json.load(f)


    
LOGGER = logging.getLogger(__name__)

def manage_collection(api: API, request: APIRequest, action: str, dataset: str = None) -> Tuple[dict, int, str]:
    """
    PNU STEMLab: Manages IndoorGML Collections (Sites/Campuses)
    This handles the POST /collections registration and DELETE /collections/{id}.
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    db = get_db_session()  # Open DB connection
    
    try:
        # --- Action: CREATE ---
        if action == 'create':
            # 1. Get the data from the request
            try:
                data = request.data
                if isinstance(data, bytes):
                    data = json.loads(data.decode('utf-8'))
            except Exception as e:
                return api.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format, 
                    'InvalidParameterValue', 'Invalid JSON body')

            # 2. Extract Data
            c_id = data.get('id')
            title = data.get('title')
            description = data.get('description', '')
            item_type = data.get('itemType', 'indoorfeature')

            if not c_id or not title:
                return api.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format, 
                    'MissingParameterValue', 'Required fields: id, title')

            # 3. DB Check: Does it already exist?
            existing = db.query(Collection).filter(Collection.id_str == c_id).first()
            if existing:
                return api.get_exception(
                    HTTPStatus.CONFLICT, headers, request.format,
                    'Conflict', f'Collection {c_id} already exists')

            # 4. Save to Database (PERSISTENCE)
            # Note: Generating a random BigInt for 'id' since your SQL schema wasn't SERIAL
            new_collection = Collection(
                id=random.randint(1, 9223372036854775800), 
                id_str=c_id,
                collection_property={
                    'title': title, 
                    'description': description,
                    'itemType': item_type
                }
            )
            db.add(new_collection)
            db.commit()

            # 5. Update In-Memory Config (AVAILABILITY)
            # This ensures pygeoapi can serve it immediately without a restart
            api.config['resources'][c_id] = {
                'type': 'collection',
                'itemType': item_type,
                'title': title,
                'description': description,
                # We point the provider to the DB now (conceptual, requires a DB Provider implementation)
                # For now, we keep the metadata active so the /collections endpoint sees it.
                'providers': [{'type': 'feature', 'name': 'PostgreSQL', 'data': c_id}] 
            }

            response_data = {'id': c_id, 'status': 'created'}
            return headers, HTTPStatus.CREATED, to_json(response_data, api.pretty_print)

        # --- Action: DELETE ---
        elif action == 'delete':
            collection_id = str(dataset)
            
            # 1. Get the Collection Object (and its Integer ID)
            collection_obj = db.query(Collection).filter(Collection.id_str == collection_id).first()
            
            if not collection_obj:
                return api.get_exception(
                    HTTPStatus.NOT_FOUND, headers, request.format,
                    'NotFound', f'Collection {collection_id} does not exist in DB')

            coll_pk = collection_obj.id  # We need the Integer ID for the cleanup

            # 2. CASCADE CLEANUP (The "Deep Clean")
            # We must delete data from the bottom up to satisfy Foreign Keys.
            
            # A. Delete Connections (Edges between nodes)
            # Find all nodes in this entire collection
            subquery_nodes = db.query(NodeEdge.id).filter(NodeEdge.collection_id == coll_pk)
            # Delete any connection touching these nodes
            db.query(Connects).filter(
                (Connects.node_source_id.in_(subquery_nodes)) | 
                (Connects.node_target_id.in_(subquery_nodes))
            ).delete(synchronize_session=False)

            # B. Delete Inter-Layer Connections
            db.query(InterLayerConnection).filter(InterLayerConnection.collection_id == coll_pk).delete()

            # C. Delete Spatial Elements (Nodes & Cells)
            db.query(NodeEdge).filter(NodeEdge.collection_id == coll_pk).delete()
            db.query(CellSpaceBoundary).filter(CellSpaceBoundary.collection_id == coll_pk).delete()

            # D. Delete Thematic Layers
            db.query(ThematicLayer).filter(ThematicLayer.collection_id == coll_pk).delete()

            # E. Delete IndoorFeatures
            db.query(IndoorFeature).filter(IndoorFeature.collection_id == coll_pk).delete()

            # F. FINALLY: Delete the Collection itself
            db.delete(collection_obj)
            db.commit()

            # 3. Delete from In-Memory Config
            if collection_id in api.config['resources']:
                del api.config['resources'][collection_id]
            
            return headers, HTTPStatus.NO_CONTENT, ''

    except Exception as e:
        db.rollback()
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        db.close()  # Always close the connection

    return headers, HTTPStatus.METHOD_NOT_ALLOWED, ''

def get_collection(api: API, request: APIRequest, dataset=None) -> Tuple[dict, int, str]:
    """
    GET /collections/{collectionId}
    Retrieves collection metadata from PostGIS.
    """
    collection_id = str(dataset)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    db = next(get_db())  # Standardized DB session

    try:
        # 1. Query the DB (We need the full object, not just the ID)
        collection_row = db.query(Collection).filter(Collection.id_str == collection_id).first()

        if not collection_row:
            return api.get_exception(
                HTTPStatus.NOT_FOUND, headers, request.format,
                'NotFound', f'Collection {collection_id} not found.')

        # Extract metadata
        props = collection_row.collection_property or {}
        
        # 2. Handle HTML UI (The "Injection" Trick)
        # We temporarily inject this DB data into the API config so the Jinja2 templates can render it.
        if request.format == 'html':
            if collection_id not in api.config['resources']:
                api.config['resources'][collection_id] = {
                    'title': props.get('title', collection_id),
                    'description': props.get('description', ''),
                    # OGC requires 'extents', so we provide a default global box
                    'extents': {'spatial': {'bbox': [-180, -90, 180, 90], 'crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'}}
                }
            # Delegate to the core pygeoapi logic to render the HTML template
            return core_api.describe_collections(api, request, collection_id)

        # 3. Handle JSON API (Clean Output)
        collection_response = {
            "id": collection_id,
            "title": props.get('title', collection_id),
            "description": props.get('description', ''),
            "links": [
                {
                    "href": f"{api.config['server']['url']}/collections/{collection_id}", 
                    "rel": "self", "type": "application/json", "title": "Metadata"
                },
                {
                    "href": f"{api.config['server']['url']}/collections/{collection_id}/items", 
                    "rel": "items", "type": "application/geo+json", "title": "IndoorGML Features"
                }
            ],
            "itemType": props.get('itemType', 'indoorfeature')
        }

        return headers, HTTPStatus.OK, to_json(collection_response, api.pretty_print)
    
    except Exception as e:
        # Catch unexpected DB errors
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
        
    finally:
        db.close()

def describe_collections(api: API, request: APIRequest) -> Tuple[dict, int, str]:
    """
    GET /collections
    Reads directly from the DB to list all registered sites.
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    db = get_db_session()
    
    try:
        # 1. Fetch all collections
        all_collections = db.query(Collection).all()
        collections_list = []

        for row in all_collections:
            props = row.collection_property or {}
            c_id = row.id_str
            
            collections_list.append({
                'id': c_id,
                'title': props.get('title', c_id),
                'itemType': props.get('itemType', 'feature'),
                'links': [
                    {'href': f"{api.config['server']['url']}/collections/{c_id}", 'rel': 'self', 'type': 'application/json'},
                    {'href': f"{api.config['server']['url']}/collections/{c_id}/items", 'rel': 'items', 'type': 'application/geo+json'}
                ]
            })

        content = {'collections': collections_list, 'links': []}
        return headers, HTTPStatus.OK, to_json(content, api.pretty_print)

    finally:
        db.close()

def get_oas_30(cfg: dict, locale: str) -> tuple[list[dict], dict]:
    """
    Generates the OpenAPI documentation fragments for IndoorGML.
    This ensures your POST /collections shows up in Swagger.
    """
    paths = {}
    
    # Define the POST /collections path
    paths['/collections'] = {
        'post': {
            'summary': 'Register a new IndoorGML site',
            'tags': ['IndoorGML Management'],
            'operationId': 'createCollection',
            'requestBody': {
                'required': True,
                'content': {
                    'application/json': {
                        'schema': {
                            'type': 'object',
                            'required': ['id', 'title'],
                            'properties': {
                                'id': {'type': 'string'},
                                'title': {'type': 'string'},
                                'description': {'type': 'string'}
                            }
                        }
                    }
                }
            },
            'responses': {
                '201': {'description': 'Collection Created'},
                '400': {'description': 'Invalid Request'}
            }
        }
    }
    
    return [{'name': 'IndoorGML Management'}], paths

def create_item(api: API, request: APIRequest, dataset) -> Tuple[dict, int, str]:
    """
    POST /collections/{cId}/items
    OperationId: createItem (Register a new building model)
    Parsing IndoorGML JSON and saving to normalized PostGIS tables.
    """
    collection_str_id = str(dataset)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    
    # 1. Parse & Validate
    try:
        data = json.loads(request.data.decode('utf-8'))
        # validate(instance=data, schema=INDOOR_SCHEMA) # Keep your existing validation
    except Exception as e:
        return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidRequest', str(e))

    db = next(get_db())
    
    try:
        # 2. Verify Collection Exists
        collection = db.query(Collection).filter(Collection.id_str == collection_str_id).first()
        if not collection:
            return api.get_exception(
                HTTPStatus.NOT_FOUND, headers, request.format, 
                'NotFound', f'Collection {collection_str_id} not found')

        # 3. Create Root IndoorFeature
        # We assume 'data' represents the "IndoorFeatures" document
        feature_pk = generate_id()
        indoor_feature = IndoorFeature(
            id=feature_pk,
            id_str=data.get('id', f"IF_{feature_pk}"),
            collection_id=collection.id,
            geojson_properties=data.get('properties', {})
            # geojson_geometry: Usually IndoorFeatures doesn't have its own geometry, 
            # but if provided, use: shape(data['geometry']).wkt
        )
        db.add(indoor_feature)
        
        # --- 4. PARSE PRIMAL SPACE (Cells) ---
        # Assuming JSON structure: data['primalSpaceFeatures']['cellSpaceMember'] = [ ... ]
        primal_features = data.get('primalSpaceFeatures', {})
        cell_members = primal_features.get('cellSpaceMember', [])
        
        # We need a "Primal" ThematicLayer to attach these cells to
        primal_layer_pk = generate_id()
        primal_layer = ThematicLayer(
            id=primal_layer_pk,
            id_str=f"Layer_Primal_{feature_pk}",
            collection_id=collection.id,
            indoorfeature_id=feature_pk,
            semantic_extension=False,
            space_type=SpaceType.primal,
            creation_datetime=datetime.now()
        )
        db.add(primal_layer)

        for cell_json in cell_members:
            # cell_json is likely {'CellSpace': { ... }}
            cell_content = cell_json.get('CellSpace', cell_json)
            
            # Extract Geometry (Solid or Polygon)
            # PostGIS needs WKT. Shapely handles the conversion from GeoJSON dict.
            geom_wkt = None
            if 'geometry' in cell_content:
                geom_wkt = shape(cell_content['geometry']).wkt
            
            db.add(CellSpaceBoundary(
                id=generate_id(),
                id_str=cell_content.get('id'),
                type=CellType.space, # Assuming these are spaces, not boundaries
                collection_id=collection.id,
                indoorfeature_id=feature_pk,
                thematiclayer_id=primal_layer_pk,
                geometry_3d=geom_wkt, # Mapping to the 3D column
                cell_name=cell_content.get('name'),
                external_reference=cell_content.get('externalReference')
            ))

        # --- 5. PARSE DUAL SPACE (Nodes/Edges) ---
        # Assuming JSON structure: data['multiLayeredGraph']['spaceLayers'] = [ ... ]
        graph = data.get('multiLayeredGraph', {})
        layers = graph.get('spaceLayers', [])

        for layer in layers:
            layer_content = layer.get('SpaceLayer', layer)
            layer_pk = generate_id()
            
            # Create the Dual ThematicLayer
            db.add(ThematicLayer(
                id=layer_pk,
                id_str=layer_content.get('id'),
                collection_id=collection.id,
                indoorfeature_id=feature_pk,
                semantic_extension=False,
                space_type=SpaceType.dual,
                creation_datetime=datetime.now()
            ))

            # Nodes
            for node in layer_content.get('nodes', []):
                geom_wkt = None
                if 'geometry' in node:
                    geom_wkt = shape(node['geometry']).wkt
                
                db.add(NodeEdge(
                    id=generate_id(),
                    id_str=node.get('id'),
                    type=NodeEdgeType.node,
                    collection_id=collection.id,
                    indoorfeature_id=feature_pk,
                    thematiclayer_id=layer_pk,
                    geometry_val=geom_wkt
                ))

            # Edges
            for edge in layer_content.get('edges', []):
                geom_wkt = None
                if 'geometry' in edge:
                    geom_wkt = shape(edge['geometry']).wkt

                db.add(NodeEdge(
                    id=generate_id(),
                    id_str=edge.get('id'),
                    type=NodeEdgeType.edge,
                    collection_id=collection.id,
                    indoorfeature_id=feature_pk,
                    thematiclayer_id=layer_pk,
                    geometry_val=geom_wkt,
                    weight=edge.get('weight', 1.0)
                ))

        # 6. Commit Transaction
        db.commit()
        
        return headers, 201, to_json({"status": "Created", "id": indoor_feature.id_str}, api.pretty_print)

    except Exception as e:
        db.rollback()
        # Log the error for debugging
        print(f"❌ DB Error: {e}")
        return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidRequest', str(e))
    finally:
        db.close()

def get_features(api: API, request: APIRequest, dataset) -> Tuple[dict, int, str]:
    """
    GET /collections/{cId}/items
    Returns a list of building metadata (metaGeoJSON) from the Database.
    """
    collection_str_id = str(dataset)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    db = next(get_db())

    try:
        # 1. Resolve Collection
        collection = db.query(Collection).filter(Collection.id_str == collection_str_id).first()
        if not collection:
            return api.get_exception(
                HTTPStatus.NOT_FOUND, headers, request.format, 
                'NotFound', f'Collection {collection_str_id} not found')

        # 2. Fetch all IndoorFeatures for this collection
        features_db = db.query(IndoorFeature).filter(IndoorFeature.collection_id == collection.id).all()

        meta_features = []
        for feat in features_db:
            # Handle Geometry: Use stored geometry or fallback to a placeholder
            geom_dict = None
            if feat.geojson_geometry is not None:
                # Convert PostGIS Element -> Shapely -> GeoJSON Dict
                geom_dict = mapping(to_shape(feat.geojson_geometry))
            else:
                # Placeholder footprint if none exists
                geom_dict = {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}

            # Construct the summary feature
            meta_feat = {
                "type": "Feature",
                "featureType": "IndoorFeatures",
                "id": feat.id_str,
                "geometry": geom_dict,
                "properties": {
                    "metadata": {
                        "description": feat.geojson_properties.get('description', f"Model {feat.id_str}"),
                        "creationDate": datetime.utcnow().isoformat() + "Z", # Or fetch from DB if you add a column
                        "version": "2.0"
                    }
                },
                "links": [
                    {
                        "href": f"{api.config['server']['url']}/collections/{collection_str_id}/items/{feat.id_str}",
                        "rel": "item", "type": "application/json", "title": "Full IndoorGML Graph"
                    }
                ]
            }
            meta_features.append(meta_feat)

        # 3. Wrap in FeatureCollection
        response = {
            "type": "FeatureCollection",
            "features": meta_features,
            "numberMatched": len(meta_features),
            "numberReturned": len(meta_features),
            "timeStamp": datetime.utcnow().isoformat() + "Z",
            "links": [
                {"href": f"{api.config['server']['url']}/collections/{collection_str_id}/items", "rel": "self", "type": "application/json"}
            ]
        }

        return headers, 200, to_json(response, api.pretty_print)

    finally:
        db.close()

def get_feature(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
    """
    GET /collections/{cId}/items/{itemId}
    Reconstructs the full nested IndoorGML JSON strictly following the new IndoorJSON schema.
    """
    collection_str_id = str(dataset)
    feature_str_id = str(identifier)
    headers = request.get_response_headers(api.api_headers)
    db = next(get_db())

    try:
        # 1. Resolve IDs and Validate Existence
        coll_pk = resolve_db_id(db, Collection, collection_str_id)
        feat_pk = resolve_db_id(db, IndoorFeature, feature_str_id)

        if not coll_pk:
            return api.get_exception(404, headers, request.format, 'NotFound', 'Collection not found')
        
        if not feat_pk:
            return api.get_exception(404, headers, request.format, 'NotFound', 'Feature not found')

        # 2. Strict Query: Feature MUST belong to this Collection
        feature = db.query(IndoorFeature).filter(
            IndoorFeature.id == feat_pk,
            IndoorFeature.collection_id == coll_pk
        ).first()

        if not feature:
            return api.get_exception(404, headers, request.format, 'NotFound', 
                                   f'Feature {feature_str_id} not found in collection {collection_str_id}')

        # =====================================================================
        # 3. RECONSTRUCTION: Build "layers" Array
        # =====================================================================
        
        # We fetch ALL layers (Primal + Dual) associated with this feature
        db_layers = db.query(ThematicLayer).filter(
            ThematicLayer.indoorfeature_id == feature.id
        ).all()

        json_layers = []

        for layer in db_layers:
            # Base ThematicLayer Object (Schema Definition)
            # Required: id, featureType, semanticExtension, theme
            layer_obj = {
                "id": layer.id_str,
                "featureType": "ThematicLayer",
                "semanticExtension": layer.semantic_extension or False,
                "theme": "Physical" if layer.space_type == SpaceType.primal else "Virtual" 
                # Note: You might want to map 'theme' explicitly if stored in DB
            }

            # --- A. PRIMAL SPACE LAYER ---
            if layer.space_type == SpaceType.primal:
                # Fetch Cells
                cells = db.query(CellSpaceBoundary).filter(
                    CellSpaceBoundary.thematiclayer_id == layer.id
                ).all()

                cell_members = []
                for cell in cells:
                    # Geometry conversion
                    geom_3d = None
                    if cell.geometry_3d is not None:
                        geom_3d = mapping(to_shape(cell.geometry_3d))
                    
                    # Construct CellSpace Object
                    cell_obj = {
                        "id": cell.id_str,
                        "featureType": "CellSpace",
                        "cellSpaceName": cell.cell_name,
                        "poi": False, # Defaulting to False if not in DB
                        "cellSpaceGeom": {
                            "geometry3D": geom_3d
                        }
                    }
                    if cell.external_reference:
                        # Assuming external_reference column is a JSON string or dict matching schema
                        # If it's just a URI string, you might need to wrap it.
                        pass 

                    cell_members.append(cell_obj)

                # Add PrimalSpaceLayer to the ThematicLayer
                if cell_members:
                    layer_obj["primalSpace"] = {
                        "id": f"PrimalSpace_{layer.id_str}", # Generate/Store ID if needed
                        "featureType": "PrimalSpaceLayer",
                        "cellSpaceMember": cell_members
                    }

            # --- B. DUAL SPACE LAYER ---
            elif layer.space_type == SpaceType.dual:
                # Fetch Nodes
                nodes = db.query(NodeEdge).filter(
                    NodeEdge.thematiclayer_id == layer.id,
                    NodeEdge.type == NodeEdgeType.node
                ).all()
                
                # Fetch Edges
                edges = db.query(NodeEdge).filter(
                    NodeEdge.thematiclayer_id == layer.id,
                    NodeEdge.type == NodeEdgeType.edge
                ).all()

                node_members = []
                for n in nodes:
                    g_json = mapping(to_shape(n.geometry_val)) if n.geometry_val else None
                    node_obj = {
                        "id": n.id_str,
                        "featureType": "Node",
                        "geometry": g_json,
                        "duality": n.duality # Ensure this column exists or is handled
                    }
                    node_members.append(node_obj)

                edge_members = []
                for e in edges:
                    g_json = mapping(to_shape(e.geometry_val)) if e.geometry_val else None
                    # We need 'connects' array for edges (minItems: 2)
                    # If you store this in DB, load it. If not, this schema validation might fail 
                    # if we don't provide it.
                    connects_list = [] # You need to populate this from DB if available
                    
                    edge_obj = {
                        "id": e.id_str,
                        "featureType": "Edge",
                        "weight": e.weight or 1.0,
                        "geometry": g_json,
                        "connects": connects_list, 
                        "duality": e.duality
                    }
                    edge_members.append(edge_obj)

                # Add DualSpaceLayer to the ThematicLayer
                # Only add if we actually have content to avoid empty objects if strictly validated
                layer_obj["dualSpace"] = {
                    "id": f"DualSpace_{layer.id_str}",
                    "featureType": "DualSpaceLayer",
                    "isLogical": True,   # Default or fetch from DB
                    "isDirected": False, # Default or fetch from DB
                    "nodeMember": node_members,
                    "edgeMember": edge_members
                }

            json_layers.append(layer_obj)


        # 4. Construct the Root "IndoorFeatures" Object
        indoor_features_doc = {
            "id": feature.id_str,
            "featureType": "IndoorFeatures",
            "layers": json_layers,
            "layerConnections": [] # Optional in schema properties, can leave empty or populate
        }

        # 5. Create standard GeoJSON Feature Wrapper
        footprint = None
        if feature.geojson_geometry:
             footprint = mapping(to_shape(feature.geojson_geometry))
        else:
             footprint = {"type": "Polygon", "coordinates": [[[0,0], [10,0], [10,10], [0,10], [0,0]]]}

        response = {
            "type": "Feature",
            "featureType": "IndoorFeatures",
            "id": feature.id_str,
            "geometry": footprint,
            "properties": {
                "metadata": {
                    "description": f"IndoorGML 2.0 model for {feature.id_str}",
                    "creationDate": datetime.utcnow().isoformat() + "Z",
                    "version": "2.0"
                }
            },
            # <--- The Field You Requested --->
            "IndoorFeatures": indoor_features_doc, 
            "links": [
                {"href": f"{api.config['server']['url']}/collections/{collection_str_id}/items/{feature_str_id}", "rel": "self", "type": "application/json"}
            ]
        }

        return headers, 200, to_json(response, api.pretty_print)

    except Exception as e:
        LOGGER.error(f"Error fetching feature: {e}")
        return api.get_exception(500, headers, request.format, 'ServerError', str(e))

    finally:
        db.close()

def delete_feature(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
    collection_str_id = str(dataset) # <--- Get Collection ID
    feature_str_id = str(identifier)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    db = next(get_db())

    try:
        # 1. Resolve IDs
        coll_pk = resolve_db_id(db, Collection, collection_str_id)
        feat_pk = resolve_db_id(db, IndoorFeature, feature_str_id)
        
        if not coll_pk or not feat_pk:
             return api.get_exception(404, headers, request.format, 'NotFound', 'Resource not found')

        # 2. SAFETY CHECK: Ensure this feature actually belongs to this collection
        # We don't need the full object, just a check.
        exists_check = db.query(IndoorFeature.id).filter(
            IndoorFeature.id == feat_pk, 
            IndoorFeature.collection_id == coll_pk
        ).first()

        if not exists_check:
             return api.get_exception(404, headers, request.format, 'NotFound', 
                                    f'Feature {feature_str_id} not found in collection {collection_str_id}')

        # 3. CASCADE DELETE (Same as before)
        db.query(InterLayerConnection).filter(InterLayerConnection.indoorfeature_id == feat_pk).delete()
        
        subquery_nodes = db.query(NodeEdge.id).filter(NodeEdge.indoorfeature_id == feat_pk)
        db.query(Connects).filter(
            (Connects.node_source_id.in_(subquery_nodes)) | 
            (Connects.node_target_id.in_(subquery_nodes))
        ).delete(synchronize_session=False)

        db.query(NodeEdge).filter(NodeEdge.indoorfeature_id == feat_pk).delete()
        db.query(CellSpaceBoundary).filter(CellSpaceBoundary.indoorfeature_id == feat_pk).delete()
        db.query(ThematicLayer).filter(ThematicLayer.indoorfeature_id == feat_pk).delete()
        
        # Finally delete the root
        db.query(IndoorFeature).filter(IndoorFeature.id == feat_pk).delete()
        
        db.commit()

        return headers, HTTPStatus.NO_CONTENT, ""

    except Exception as e:
        db.rollback()
        print(f"❌ Delete Failed: {e}")
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        db.close()

def manage_collection_item_layer(api: API, request: APIRequest, action, dataset, identifier, layer=None) -> Tuple[dict, int, str]:
    collection_id = str(dataset)
    item_id = str(identifier)
    layer_id = str(layer)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    LOGGER.debug(headers)



    # 2. Get the Resource Configuration
    # We look for the collection, but NOT the item id here
    resource_config = api.config['resources'].get(collection_id)
    if not resource_config:
        return api.get_exception(404, headers, request.format, 'NotFound', f'Collection {collection_id} not found')

    if action == 'create':
        try:
            data = json.loads(request.data.decode('utf-8'))
            layer_schema = {
                "$schema": INDOOR_SCHEMA.get("$schema"),
                "$defs": INDOOR_SCHEMA.get("$defs"), # Copy definitions so references work
                "$ref": "#/$defs/ThematicLayer"      # Point to the specific type you want
            }
            validate(instance=data, schema=layer_schema)

            # --- FIX STARTS HERE ---
            # Instead of api.config['resources'][col][item], 
            # we find the item in the 'items' list
            items_list = resource_config.get('items', [])
            
            # Find the specific building/feature by its String ID
            target_feature = next((item for item in items_list if item.get('id') == item_id), None)

            if target_feature is None:
                return api.get_exception(404, headers, request.format, 'NotFound', f'Feature {item_id} not found')

            # Initialize layers if they don't exist
            if 'layers' not in target_feature:
                target_feature['layers'] = []
            
            target_feature['layers'].append(data)
            # --- FIX ENDS HERE ---
            
            return headers, 201, to_json({"status": "Layer Added", "id": data.get('id', 'unnamed')}, api.pretty_print)

        except ValidationError as v_err:
            return api.get_exception(400, headers, request.format, 'InvalidRequest', f"Schema Error: {v_err.message}")
        except Exception as e:
            return api.get_exception(400, headers, request.format, 'InvalidRequest', str(e))
    elif action == 'delete':
        # 1. Find the specific Feature/Building
        items_list = resource_config.get('items', [])
        target_feature = next((item for item in items_list if item.get('id') == item_id), None)

        if target_feature is None:
            return api.get_exception(404, headers, request.format, 'NotFound', f'Feature {item_id} not found')

        # 2. Get the current list of layers
        # If 'layers' key doesn't exist, there is nothing to delete
        if 'layers' not in target_feature:
             return api.get_exception(404, headers, request.format, 'NotFound', f'Layer {layer_id} not found (No layers exist)')

        current_layers = target_feature['layers']
        original_count = len(current_layers)

        # 3. Perform Deletion via Filtering
        # We keep all layers where the ID does NOT match the requested layer_id
        target_feature['layers'] = [l for l in current_layers if l.get('id') != layer_id]

        # 4. Check if deletion actually happened
        # If the length is the same, the ID was not found
        if len(target_feature['layers']) == original_count:
            return api.get_exception(404, headers, request.format, 'NotFound', f'Layer {layer_id} not found')

        # 5. Success Response (204 No Content is standard for DELETE)
        return headers, 204, ''
    
    else:
        # Placeholder for GET/UPDATE by ID
        return api.get_exception(405, headers, request.format, 'MethodNotAllowed', "Action not yet implemented")
        
def get_collection_item_layers(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
    """
    Get temporal Geometry of collection item

    :param request: A request object
    :param dataset: dataset name
    :param identifier: item identifier

    :returns: tuple of headers, status code, content
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    collection_id = str(dataset)
    item_id = str(identifier)
    LOGGER.debug(headers)
    # 1. Access the Collection
    resource = api.config['resources'].get(collection_id)
    if not resource:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', f'Collection {collection_id} not found'
        )

    # 2. Find the Specific IndoorFeature (Building)
    items = resource.get('items', [])
    target_feature = next((item for item in items if item.get('id') == item_id), None)

    if not target_feature:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', f'Feature {item_id} not found'
        )

    # 3. Extract and Summarize Layers
    raw_layers = target_feature.get('layers', [])
    
    # We create a lightweight summary list with links to the detail endpoint
    layers_summary = []
    base_url = api.config['server']['url']
    
    for l in raw_layers:
        l_id = l.get('id', 'unknown')
        layers_summary.append({
            "id": l_id,
            "theme": l.get('theme', 'Unknown'),
            "semanticExtension": l.get('semanticExtension', False),
            "links": [
                {
                    "href": f"{base_url}/collections/{collection_id}/items/{item_id}/layers/{l_id}",
                    "rel": "item",
                    "type": "application/json",
                    "title": "Layer Detail"
                }
            ]
        })

    response = {
        "layers": layers_summary,
        "links": [
            {
                "href": f"{base_url}/collections/{collection_id}/items/{item_id}/layers",
                "rel": "self",
                "type": "application/json"
            },
            {
                "href": f"{base_url}/collections/{collection_id}/items/{item_id}",
                "rel": "up",
                "type": "application/geo+json",
                "title": "Parent Feature"
            }
        ]
    }

    return headers, HTTPStatus.OK, to_json(response, api.pretty_print)

def get_collection_item_layer(api: API, request: APIRequest, dataset, identifier, layer) -> Tuple[dict, int, str]:
    """
    Get temporal Geometry of collection item

    :param request: A request object
    :param dataset: dataset name
    :param identifier: item identifier
    :param layer: layer identifier

    :returns: tuple of headers, status code, content
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    collection_id = str(dataset)
    item_id = str(identifier)
    layer_id = str(layer)
    LOGGER.debug(headers) 
    
    # 1. Access the Collection
    resource = api.config['resources'].get(collection_id)
    if not resource:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', f'Collection {collection_id} not found'
        )

    # 2. Find the Specific IndoorFeature
    items = resource.get('items', [])
    target_feature = next((item for item in items if item.get('id') == item_id), None)

    if not target_feature:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', f'Feature {item_id} not found'
        )

    # 3. Find the Specific Layer
    target_layer = next((l for l in target_feature.get('layers', []) if l.get('id') == layer_id), None)

    if not target_layer:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', f'Layer {layer_id} not found'
        )
    # 1. Calculate BBOX (Existing)
    bbox = _calculate_layer_bbox(target_layer)

    # 2. Calculate STATS (New)
    stats = _calculate_layer_stats(target_layer)
    # 4. Return the Layer JSON
    # We optionally add a 'link' back to self/up for HATEOAS compliance, 
    # but strictly speaking, returning the raw layer object is also fine based on your schema.
    
    # Using a copy to avoid modifying the in-memory data with response-specific links if not desired
    response = {
        "id": target_layer.get("id"),
        "featureType": "ThematicLayer",
        "theme": target_layer.get("theme"),
        "semanticExtension": target_layer.get("semanticExtension"),
        
        "summary": {
            "primalSpace":{
                "cellSpaceCount": stats['cellSpaceCount'],
                "cellBoudaryCount": stats['cellBoundaryCount'],
                "level": stats['level']
            },
            "dualSpace":{
                "nodeCount": stats['nodeCount'],
                "edgeCount": stats['edgeCount'],
                "isDirected": stats['isDirected'],
                "isLogical": stats['isLogical']
            }
        },
        
        "bbox": bbox,
        "links": []
    }

    # 3. GENERATE DYNAMIC LINKS (HATEOAS)
    base_url = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}"

    # Link to Self
    response['links'].append({
        "href": base_url,
        "rel": "self",
        "type": "application/json",
        "title": "Layer Metadata"
    })

    # Link to Primal Space (Geometry) - Only if it exists in the data
    if "primalSpace" in target_layer:
        response['links'].append({
            "href": f"{base_url}/primal",
            "rel": "data", # 'data' or 'item' is appropriate here
            "type": "application/json",
            "title": "Primal Space (Geometry)"
        })

    # Link to Dual Space (Topology) - Only if it exists
    if "dualSpace" in target_layer:
        response['links'].append({
            "href": f"{base_url}/dual",
            "rel": "data",
            "type": "application/json",
            "title": "Dual Space (Topology)"
        })

    return headers, HTTPStatus.OK, to_json(response, api.pretty_print)

def _extract_coords(geometry):
    """Recursively extract all [x, y] or [x, y, z] coordinates from a geometry object."""
    coords = []
    
    # Base case: Point or simple coordinate list
    if not isinstance(geometry, dict):
        return []
    
    # Handle standard GeoJSON-like types
    g_type = geometry.get('type')
    coordinates = geometry.get('coordinates', [])

    if g_type == 'Point':
        coords.append(coordinates)
    elif g_type == 'LineString':
        coords.extend(coordinates)
    elif g_type == 'Polygon':
        # Polygon coords are list of rings: [[[x,y], [x,y]], [[hole...]]]
        for ring in coordinates:
            coords.extend(ring)
    elif g_type == 'MultiPolygon':
        for poly in coordinates:
            for ring in poly:
                coords.extend(ring)
    # Handle IndoorGML 3D types (Solid/Polyhedron usually appear as complex nested lists)
    elif g_type == 'Polyhedron' or g_type == 'Solid':
        # These are often deeply nested: Shells -> Faces -> Rings -> Coords
        # A simple flatten approach for bbox is often sufficient
        def flatten(lst):
            for item in lst:
                if isinstance(item, list) and len(item) > 0 and isinstance(item[0], (int, float)):
                    coords.append(item)
                elif isinstance(item, list):
                    flatten(item)
        flatten(coordinates)
        
    return coords

def _calculate_layer_bbox(layer):
    """
    Iterates through PrimalSpace and DualSpace to calculate the layer extent.
    Returns: [minx, miny, maxx, maxy] (or None if empty)
    """
    all_coords = []

    # 1. Check Primal Space (Rooms/Cells)
    if 'primalSpace' in layer:
        primal = layer['primalSpace']
        # Check CellSpaces (Rooms)
        for cell in primal.get('cellSpaceMember', []):
            geom = cell.get('cellSpaceGeom', {})
            # Prefer 2D for API bbox, fallback to 3D
            if 'geometry2D' in geom:
                all_coords.extend(_extract_coords(geom['geometry2D']))
            elif 'geometry3D' in geom:
                all_coords.extend(_extract_coords(geom['geometry3D']))
        
        # Check CellBoundaries (Walls)
        for bound in primal.get('cellBoundaryMember', []):
            geom = bound.get('cellBoundaryGeom', {})
            if 'geometry2D' in geom:
                all_coords.extend(_extract_coords(geom['geometry2D']))

    # 2. Check Dual Space (Nodes)
    if 'dualSpace' in layer:
        dual = layer['dualSpace']
        for node in dual.get('nodeMember', []):
            if 'geometry' in node:
                all_coords.extend(_extract_coords(node['geometry']))

    if not all_coords:
        return None

    # 3. Calculate Extent
    min_x = min(c[0] for c in all_coords)
    max_x = max(c[0] for c in all_coords)
    min_y = min(c[1] for c in all_coords)
    max_y = max(c[1] for c in all_coords)

    return [min_x, min_y, max_x, max_y]
    
def _calculate_layer_stats(layer):
    """
    Analyzes the layer to return summary counts and level info.
    """
    stats = {
        "cellSpaceCount": 0,
        "cellBoundaryCount": 0,
        "nodeCount": 0,
        "edgeCount": 0,
        "isDirected": None,
        "isLogical": None,
        "level": None
    }

    # 1. Analyze Primal Space (Cells & Level)
    if 'primalSpace' in layer:
        cells = layer['primalSpace'].get('cellSpaceMember', [])
        boudaries = layer['primalSpace'].get('cellBoundaryMember', [])
        stats['cellSpaceCount'] = len(cells)
        stats['cellBoundaryCount'] = len(boudaries)
        # Extract unique levels from cells to describe the layer
        # Assumes your CellSpace has a "level" property as per your earlier schema
        found_levels = set()
        for c in cells:
            lvl = c.get('level')
            if lvl: found_levels.add(str(lvl))
        
        if found_levels:
            # Join sorted levels (e.g., "1F" or "1F, 2F")
            stats['level'] = ", ".join(sorted(list(found_levels)))

    # 2. Analyze Dual Space (Nodes)
    if 'dualSpace' in layer:
        nodes = layer['dualSpace'].get('nodeMember', [])
        edges = layer['dualSpace'].get('edgeMember', [])
        stats['nodeCount'] = len(nodes)
        stats['edgeCount'] = len(edges)
        stats['isDirected'] = layer['dualSpace'].get('isDirected')
        stats['isLogical'] = layer['dualSpace'].get('isLogical')
    return stats