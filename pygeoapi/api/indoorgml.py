import logging
import json
import random
from http import HTTPStatus
from typing import Tuple
from pygeoapi.plugin import PLUGINS
from pygeoapi.api import API, APIRequest, SYSTEM_LOCALE, F_HTML, F_JSON 
import pygeoapi.api as core_api
from pygeoapi.util import to_json
from pygeoapi.util import render_j2_template, to_json
import os
from jsonschema import validate, ValidationError
from datetime import datetime
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy import func, and_

# --- Database Imports ---
from pygeoapi.provider.postgresql_indoordb import PostgresIndoorDB
from src.database import get_db
from src.models import *
import psycopg2

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

def geojson_to_wkt(geom_dict):
    if not geom_dict: return None
    
    g_type = geom_dict.get('type')
    coords = geom_dict.get('coordinates')

    if g_type == 'Point':
        return f"SRID=4326;POINT({coords[0]} {coords[1]})"
    
    elif g_type == 'LineString':
        # Convert [[1,1], [3,1]] -> "1 1, 3 1"
        pairs = ", ".join([f"{p[0]} {p[1]}" for p in coords])
        return f"SRID=4326;LINESTRING({pairs})"
    
    elif g_type == 'Polygon':
        # Convert [[[1,1], [2,2], [1,1]]]
        rings = []
        for ring in coords:
            pairs = ", ".join([f"{p[0]} {p[1]}" for p in ring])
            rings.append(f"({pairs})")
        return f"SRID=4326;POLYGON({', '.join(rings)})"
    
    return None
    
LOGGER = logging.getLogger(__name__)

def manage_collection(api: API, request: APIRequest, action: str, dataset: str = None) -> Tuple[dict, int, str]:
    """
    PNU STEMLab: Manages IndoorGML Collections via Provider
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    
    # Initialize Provider
    provider = PostgresIndoorDB()

    try:
        # --- Action: CREATE ---
        if action == 'create':
            # 1. Safe JSON Parsing
            try:
                data = request.data
                if isinstance(data, bytes):
                    data = json.loads(data.decode('utf-8'))
            except Exception:
                return api.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format, 
                    'InvalidParameterValue', 'Invalid JSON body')

            c_id = data.get('id')
            title = data.get('title')
            # Use .get() defaults to prevent errors
            description = data.get('description', '')
            item_type = data.get('itemType', 'indoorfeature')

            if not c_id or not title:
                return api.get_exception(
                    HTTPStatus.BAD_REQUEST, headers, request.format, 
                    'MissingParameterValue', 'Required fields: id, title')

            # 2. Call Provider to Create
            # We don't need to touch api.config anymore. The DB is the authority.
            success = provider.create_collection(c_id, title, description, item_type)

            if not success:
                 return api.get_exception(
                    HTTPStatus.CONFLICT, headers, request.format,
                    'Conflict', f'Collection {c_id} already exists')

            response_data = {'id': c_id, 'status': 'created'}
            return headers, HTTPStatus.CREATED, to_json(response_data, api.pretty_print)

        # --- Action: DELETE ---
        elif action == 'delete':
            collection_id = str(dataset)
            
            # 1. Call Provider to Delete
            # We trust the provider to handle the cascade
            success = provider.delete_collection(collection_id)
            
            if not success:
                return api.get_exception(
                    HTTPStatus.NOT_FOUND, headers, request.format,
                    'NotFound', f'Collection {collection_id} not found')

            # Note: No need to delete from api.config because we never added it there!
            
            return headers, HTTPStatus.NO_CONTENT, ''

    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        provider.disconnect()

    return headers, HTTPStatus.METHOD_NOT_ALLOWED, ''


def get_collection(api: API, request: APIRequest, dataset=None) -> Tuple[dict, int, str]:
    """
    GET /collections/{collectionId}
    Retrieves a single collection's metadata from the IndoorGML Database.
    """
    collection_id = str(dataset)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    
    # Initialize Provider
    provider = PostgresIndoorDB()

    try:
        # 1. Fetch from DB
        collection_data = provider.get_collection(collection_id)

        # 2. Handle Not Found
        if not collection_data:
            return api.get_exception(
                HTTPStatus.NOT_FOUND, headers, request.format,
                'NotFound', f'Collection {collection_id} not found.')

        # 3. Construct Response
        # We manually build the response to ensure it matches OGC standards
        response = {
            "id": collection_data['id'],
            "title": collection_data['title'],
            "description": collection_data.get('description', ''),
            "itemType": collection_data.get('itemType', 'indoorfeature'),
            "keywords": [], # Empty defaults to prevent crashes
            "links": [],
        }

        # Add Links
        response['links'].append({
            "href": f"{api.config['server']['url']}/collections/{collection_id}?f=json", 
            "rel": "self", "type": "application/json", "title": "Metadata"
        })
        response['links'].append({
            "href": f"{api.config['server']['url']}/collections/{collection_id}/items?f=json", 
            "rel": "items", "type": "application/geo+json", "title": "IndoorGML Features"
        })

        return headers, HTTPStatus.OK, to_json(response, api.pretty_print)
    
    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        provider.disconnect()


def manage_collection_item(api: API, request: APIRequest, action, 
                           dataset, identifier=None) -> Tuple[dict, int, str]:
    """
    Adds an item to a collection

    :param request: A request object
    :param dataset: dataset name

    :returns: tuple of headers, status code, content
    """
    if not request.is_valid(PLUGINS['formatter'].keys()):
        return api.get_format_exception(request)
    
    headers = request.get_response_headers(SYSTEM_LOCALE)
    pidb_provider = PostgresIndoorDB()
    executed, collections = get_list_of_collections_id()
    if executed is False:
        msg = str(collections)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)
    
    if dataset not in collections:
        msg = 'Collection not found'
        LOGGER.error(msg)
        return api.get_exception(
            HTTPStatus.NOT_FOUND,
            headers, request.format, 'NotFound', msg)
    
    collection_str_id = str(dataset)
    ifeature_id = identifier
    if action == 'create':
        if not request.data:
            msg = 'No data found'
            LOGGER.error(msg)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg) 
        data = request.data
        try:
            # Parse bytes data, if applicable
            data = data.decode()
            LOGGER.debug(data)
        except (UnicodeDecodeError, AttributeError):
            pass

        try:
            data = json.loads(data)
        except (json.decoder.JSONDecodeError, TypeError) as err:
            # Input does not appear to be valid JSON
            LOGGER.error(err)
            msg = 'invalid request data'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
        LOGGER.debug('Creating item')  
        try:
            pidb_provider.connect()
            validate(instance=data, schema=INDOOR_SCHEMA)
            ifeature_id = pidb_provider.post_indoorfeature(
                collection_str_id, data
            )
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pidb_provider.disconnect()
        headers['Location'] = '{}/{}/items/{}'.format(
            api.get_collections_url(), dataset, ifeature_id)

        return headers, 201, to_json({"status": "Created", "id": ifeature_id}, api.pretty_print)  
    
    if action == 'delete':
        LOGGER.debug('Deleting item')  

        try:
            pidb_provider.connect()  
            pidb_provider.delete_indoorfeature(
                collection_str_id, ifeature_id
            )
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pidb_provider.disconnect()

        return headers, HTTPStatus.NO_CONTENT, ''    

def get_collection_items(api: API, request: APIRequest, dataset) -> Tuple[dict, int, str]:
    """
    GET /collections/{cId}/items
    Returns a list of building metadata (metaGeoJSON) from the Database.
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    
    headers = request.get_response_headers(SYSTEM_LOCALE)
    executed, collections = get_list_of_collections_id()
    collection_str_id = str(dataset)
    if executed is False:
        msg = str(collections)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)

    if collection_str_id not in collections:
        msg = 'Collection not found'
        LOGGER.error(msg)
        return api.get_exception(
            HTTPStatus.NOT_FOUND,
            headers, request.format, 'NotFound', msg)
    LOGGER.debug('Processing query parameters')

    LOGGER.debug('Processing offset parameter')
    try:
        offset = int(request.params.get('offset'))
        if offset < 0:
            msg = 'offset value should be positive or zero'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        offset = 0
    except ValueError:
        msg = 'offset value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    LOGGER.debug('Processing limit parameter')
    try:
        limit = int(request.params.get('limit'))
        # TODO: We should do more validation, against the min and max
        #       allowed by the server configuration
        if limit <= 0:
            msg = 'limit value should be strictly positive'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
        if limit > 100:
            msg = 'limit value should be less than or equal to 100'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        limit = int(api.config['server']['limit'])
    except ValueError:
        msg = 'limit value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)
    
    LOGGER.debug('Processing bbox parameter')
    bbox = request.params.get('bbox')

    if bbox is None: 
        bbox = []
    else:
        try:
            bbox = validate_bbox(bbox)
        except ValueError as err:
            msg = str(err)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    LOGGER.debug('Querying provider')
    LOGGER.debug('offset: {}'.format(offset))
    LOGGER.debug('limit: {}'.format(limit))
    LOGGER.debug('bbox: {}'.format(bbox))

    pidb_provider = PostgresIndoorDB()
    try:
        pidb_provider.connect()
        features, number_matched, number_returned = \
            pidb_provider.get_features(collection_id=collection_str_id,
                                        bbox=bbox, limit=limit, offset=offset)
        content = {
            "type": "FeatureCollection",
            "numberMatched": number_matched,
            "numberReturned": number_returned,
            "features": features,
            "links": [
                # Standard links usually go here (self, next, prev, etc.)
                # You can use api.get_items_links() if pygeoapi provides it, 
                # or build them manually.
                 {
                    "type": "application/geo+json",
                    "rel": "self",
                    "title": "This document",
                    "href": f"{api.base_url}/collections/{collection_str_id}/items"
                }
            ],
            "timeStamp": "" # Optional: add current timestamp
        }
        # Add "next" link for pagination if there are more results
        if number_matched > (offset + limit):
            next_offset = offset + limit
            content["links"].append({
                "rel": "next",
                "title": "Next page",
                "href": f"{api.base_url}/collections/{collection_str_id}/items?offset={next_offset}&limit={limit}"
            })
    except (Exception, psycopg2.Error) as error:
        LOGGER.error(f"Database error: {error}")
        msg = str(error)
        return api.get_exception(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            headers, request.format, 'ConnectingError', msg)
    finally:
        pidb_provider.disconnect()
    return headers, HTTPStatus.OK, content
    


def get_feature(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
    """
    GET /collections/{cId}/items/{itemId}
    Reconstructs the full nested IndoorGML JSON strictly following the new schema.
    """
    collection_str_id = str(dataset)
    feature_str_id = str(identifier)
    headers = request.get_response_headers(api.api_headers)
    db = next(get_db())

    # --- Helper: Resolve Integer ID -> String ID for Duality ---
    def get_duality_str(target_model, target_pk):
        if not target_pk:
            return None
        # Efficiently fetch only the id_str column
        res = db.query(target_model.id_str).filter(target_model.id == target_pk).first()
        return res[0] if res else None

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
        
        # Fetch ALL layers associated with this feature
        db_layers = db.query(ThematicLayer).filter(
            ThematicLayer.indoorfeature_id == feature.id
        ).all()

        json_layers = []

        for layer in db_layers:
            # Base ThematicLayer Object
            layer_obj = {
                "id": layer.id_str,
                "featureType": "ThematicLayer",
                "semanticExtension": layer.semantic_extension or False,
                # Convert Enum back to Title Case or keep as is (e.g., 'physical' -> 'Physical')
                "theme": layer.theme.value.title() if layer.theme else "Unknown" 
            }

            # --- A. PRIMAL SPACE RECONSTRUCTION ---
            # Fetch Cells & Boundaries
            cells = db.query(CellSpaceBoundary).filter(
                CellSpaceBoundary.thematiclayer_id == layer.id,
                CellSpaceBoundary.type == CellType.space
            ).all()

            boundaries = db.query(CellSpaceBoundary).filter(
                CellSpaceBoundary.thematiclayer_id == layer.id,
                CellSpaceBoundary.type == CellType.boundary
            ).all()

            # If this layer has any primal data
            if cells or boundaries:
                cell_members = []
                for cell in cells:
                    # Geometry 2D/3D
                    geom_2d = mapping(to_shape(cell.geometry_2d)) if cell.geometry_2d else None
                    # Resolve Duality (Int -> Str) (Target: Node)
                    dual_str = get_duality_str(NodeEdge, cell.duality_id)
                    # Resolve BoundedBy (Int -> Str) (Target: Boundary)
                    bounded_str = get_duality_str(CellSpaceBoundary, cell.bounded_by_cell_id)

                    cell_obj = {
                        "id": cell.id_str,
                        "featureType": "CellSpace",
                        "cellSpaceName": cell.cell_name,
                        "poi": cell.poi or False,
                        "level": cell.level,
                        "duality": dual_str, 
                        "boundedBy": [bounded_str] if bounded_str else [],
                        "cellSpaceGeom": {
                            "geometry2D": geom_2d
                        }
                    }
                    cell_members.append(cell_obj)

                boundary_members = []
                for bound in boundaries:
                    geom_2d = mapping(to_shape(bound.geometry_2d)) if bound.geometry_2d else None
                    # Resolve Duality (Int -> Str) (Target: Edge)
                    dual_str = get_duality_str(NodeEdge, bound.duality_id)

                    bound_obj = {
                        "id": bound.id_str,
                        "featureType": "CellBoundary",
                        "isVirtual": bound.is_virtual,
                        "duality": dual_str,
                        "cellBoundaryGeom": {
                            "geometry2D": geom_2d
                        }
                    }
                    boundary_members.append(bound_obj)

                # Add PrimalSpace Object
                layer_obj["primalSpace"] = {
                    "id": layer.primalspace_id_str or f"PS-{layer.id_str}",
                    "featureType": "PrimalSpaceLayer",
                    "creationDatetime": layer.p_creation_datetime.isoformat() if layer.p_creation_datetime else None,
                    "cellSpaceMember": cell_members,
                    "cellBoundaryMember": boundary_members
                }

            # --- B. DUAL SPACE RECONSTRUCTION ---
            # Fetch Nodes & Edges
            nodes = db.query(NodeEdge).filter(
                NodeEdge.thematiclayer_id == layer.id,
                NodeEdge.type == NodeEdgeType.node
            ).all()
            
            edges = db.query(NodeEdge).filter(
                NodeEdge.thematiclayer_id == layer.id,
                NodeEdge.type == NodeEdgeType.edge
            ).all()

            # If this layer has any dual data
            if nodes or edges:
                node_members = []
                for n in nodes:
                    g_json = mapping(to_shape(n.geometry_val)) if n.geometry_val else None
                    # Resolve Duality (Int -> Str) (Target: Cell)
                    dual_str = get_duality_str(CellSpaceBoundary, n.duality_id)

                    node_obj = {
                        "id": n.id_str,
                        "featureType": "Node",
                        "geometry": g_json,
                        "duality": dual_str
                    }
                    node_members.append(node_obj)

                edge_members = []
                for e in edges:
                    g_json = mapping(to_shape(e.geometry_val)) if e.geometry_val else None
                    # Resolve Duality (Int -> Str) (Target: Boundary)
                    dual_str = get_duality_str(CellSpaceBoundary, e.duality_id)

                    edge_obj = {
                        "id": e.id_str,
                        "featureType": "Edge",
                        "weight": e.weight or 1.0,
                        "geometry": g_json,
                        "duality": dual_str
                        # Note: 'connects' is harder to reconstruct without a separate association table.
                        # If needed, you must query the 'connects' table if you created it.
                    }
                    edge_members.append(edge_obj)

                # Add DualSpace Object
                layer_obj["dualSpace"] = {
                    "id": layer.dualspace_id_str or f"DS-{layer.id_str}",
                    "featureType": "DualSpaceLayer",
                    "creationDatetime": layer.d_creation_datetime.isoformat() if layer.d_creation_datetime else None,
                    "isLogical": layer.is_logical, 
                    "isDirected": layer.is_directed,
                    "nodeMember": node_members,
                    "edgeMember": edge_members
                }

            json_layers.append(layer_obj)


        # 4. Construct the Root "IndoorFeatures" Object
        indoor_features_doc = {
            "id": feature.id_str,
            "featureType": "IndoorFeatures",
            "layers": json_layers,
            "layerConnections": [] 
        }

        # 5. Create standard OGC Feature Wrapper
        footprint = None
        if feature.geojson_geometry:
             footprint = mapping(to_shape(feature.geojson_geometry))
        else:
             # Default dummy footprint if none exists
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
            # <--- The IndoorGML Content --->
            "IndoorFeatures": indoor_features_doc, 
            "links": [
                {"href": f"{api.config['server']['url']}/collections/{collection_str_id}/items/{feature_str_id}", "rel": "self", "type": "application/json"}
            ]
        }

        return headers, 200, to_json(response, api.pretty_print)

    except Exception as e:
        LOGGER.error(f"Error fetching feature: {e}")
        # Print stack trace for debugging
        import traceback
        traceback.print_exc()
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
    collection_str_id = str(dataset)
    feature_str_id = str(identifier)
    layer_str_id = str(layer) if layer else None
    
    headers = request.get_response_headers(api.api_headers)
    db = next(get_db())

    try:
        # 1. Resolve Parent IDs and Validate Existence
        coll_pk = resolve_db_id(db, Collection, collection_str_id)
        feat_pk = resolve_db_id(db, IndoorFeature, feature_str_id)

        if not coll_pk:
            return api.get_exception(404, headers, request.format, 'NotFound', 'Collection not found')
        
        if not feat_pk:
            return api.get_exception(404, headers, request.format, 'NotFound', 'Feature not found')

        # 2. Strict Hierarchy Check: Feature MUST belong to this Collection
        feature = db.query(IndoorFeature).filter(
            IndoorFeature.id == feat_pk,
            IndoorFeature.collection_id == coll_pk
        ).first()

        if not feature:
            return api.get_exception(404, headers, request.format, 'NotFound', 
                                   f'Feature {feature_str_id} not found in collection {collection_str_id}')

        # =====================================================================
        # ACTION: CREATE (POST)
        # =====================================================================
        if action == 'create':
            try:
                data = json.loads(request.data.decode('utf-8'))
                
                # Schema Validation
                layer_schema = {
                    "$schema": INDOOR_SCHEMA.get("$schema"),
                    "$defs": INDOOR_SCHEMA.get("$defs"), 
                    "$ref": "#/$defs/ThematicLayer"      
                }
                validate(instance=data, schema=layer_schema)

                # Check for ID conflict
                new_layer_id = data.get('id')
                existing = db.query(ThematicLayer).filter(
                    ThematicLayer.indoorfeature_id == feature.id,
                    ThematicLayer.id_str == new_layer_id
                ).first()
                
                if existing:
                    return api.get_exception(409, headers, request.format, 'Conflict', f"Layer {new_layer_id} already exists")

                # Determine Space Type (Primal vs Dual)
                # Note: Schema usually enforces one or the other, or we check keys
                space_type_enum = None
                if 'primalSpace' in data:
                    space_type_enum = SpaceType.primal
                elif 'dualSpace' in data:
                    space_type_enum = SpaceType.dual
                else:
                    # Fallback or error if neither (though schema validation should catch this)
                    space_type_enum = SpaceType.primal 

                # A. Insert ThematicLayer Record
                new_layer = ThematicLayer(
                    id_str=new_layer_id,
                    indoorfeature_id=feature.id,
                    class_name="ThematicLayer",
                    semantic_extension=data.get('semanticExtension', False),
                    space_type=space_type_enum,
                    # Map other fields like 'doc' if present in your model
                )
                db.add(new_layer)
                db.flush() # Flush to get new_layer.id (PK) for children

                # B. Insert Primal Members (CellSpace)
                if space_type_enum == SpaceType.primal and 'primalSpace' in data:
                    primal_data = data['primalSpace']
                    # Assuming 'cellSpaceMember' is a list of objects
                    for cell in primal_data.get('cellSpaceMember', []):
                        
                        # Geometry Conversion: GeoJSON -> DB Format
                        geom_db = None
                        if 'cellSpaceGeom' in cell and 'geometry3D' in cell['cellSpaceGeom']:
                            geojson_geom = cell['cellSpaceGeom']['geometry3D']
                            geom_db = from_shape(shape(geojson_geom))

                        new_cell = CellSpaceBoundary(
                            id_str=cell.get('id'),
                            thematiclayer_id=new_layer.id,
                            cell_name=cell.get('cellSpaceName'),
                            geometry_3d=geom_db,
                            external_reference=None # Fill if schema has it
                        )
                        db.add(new_cell)

                # C. Insert Dual Members (Nodes/Edges)
                elif space_type_enum == SpaceType.dual and 'dualSpace' in data:
                    dual_data = data['dualSpace']
                    
                    # Nodes
                    for node in dual_data.get('nodeMember', []):
                        geom_db = None
                        if 'geometry' in node and node['geometry']:
                            geom_db = from_shape(shape(node['geometry']))
                        
                        new_node = NodeEdge(
                            id_str=node.get('id'),
                            thematiclayer_id=new_layer.id,
                            type=NodeEdgeType.node,
                            geometry_val=geom_db,
                            duality=node.get('duality')
                        )
                        db.add(new_node)

                    # Edges
                    for edge in dual_data.get('edgeMember', []):
                        geom_db = None
                        if 'geometry' in edge and edge['geometry']:
                            geom_db = from_shape(shape(edge['geometry']))

                        new_edge = NodeEdge(
                            id_str=edge.get('id'),
                            thematiclayer_id=new_layer.id,
                            type=NodeEdgeType.edge,
                            geometry_val=geom_db,
                            duality=edge.get('duality'),
                            weight=edge.get('weight', 1.0)
                        )
                        db.add(new_edge)

                db.commit()
                return headers, 201, to_json({"status": "Layer Added", "id": new_layer_id}, api.pretty_print)

            except ValidationError as v_err:
                db.rollback()
                return api.get_exception(400, headers, request.format, 'InvalidRequest', f"Schema Error: {v_err.message}")
            except Exception as e:
                db.rollback()
                LOGGER.error(f"Error creating layer: {e}")
                return api.get_exception(500, headers, request.format, 'ServerError', str(e))

        # =====================================================================
        # ACTION: DELETE (DELETE)
        # =====================================================================
        elif action == 'delete':
            # Find the layer by its String ID and Parent Feature
            target_layer = db.query(ThematicLayer).filter(
                ThematicLayer.id_str == layer_str_id,
                ThematicLayer.indoorfeature_id == feature.id
            ).first()

            if not target_layer:
                return api.get_exception(404, headers, request.format, 'NotFound', f'Layer {layer_str_id} not found')

            try:
                # SQLAlchemy cascade should handle children (Cells/Nodes) if configured in models.
                # Otherwise, you might need to manually delete children here.
                # Assuming standard Cascade delete:
                db.delete(target_layer)
                db.commit()

                return headers, 204, '' # No Content
            except Exception as e:
                db.rollback()
                return api.get_exception(500, headers, request.format, 'ServerError', str(e))

        else:
            return api.get_exception(405, headers, request.format, 'MethodNotAllowed', "Action not yet implemented")

    except Exception as e:
        LOGGER.error(f"Global error in manage_layer: {e}")
        return api.get_exception(500, headers, request.format, 'ServerError', str(e))

    finally:
        db.close()

def get_collection_item_layers(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
    """
    Get summary of layers for a collection item (IndoorFeature)
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    
    headers = request.get_response_headers(api.api_headers)
    collection_str_id = str(dataset)
    feature_str_id = str(identifier)
    
    db = next(get_db())

    try:
        # 1. Resolve IDs and Validate Existence
        coll_pk = resolve_db_id(db, Collection, collection_str_id)
        feat_pk = resolve_db_id(db, IndoorFeature, feature_str_id)

        if not coll_pk:
            return api.get_exception(404, headers, request.format, 'NotFound', 'Collection not found')
        
        if not feat_pk:
            return api.get_exception(404, headers, request.format, 'NotFound', 'Feature not found')

        # 2. Strict Check: Feature MUST belong to this Collection
        feature = db.query(IndoorFeature).filter(
            IndoorFeature.id == feat_pk,
            IndoorFeature.collection_id == coll_pk
        ).first()

        if not feature:
            return api.get_exception(404, headers, request.format, 'NotFound', 
                                   f'Feature {feature_str_id} not found in collection {collection_str_id}')

        # 3. Query DB for Layers
        db_layers = db.query(ThematicLayer).filter(
            ThematicLayer.indoorfeature_id == feature.id
        ).all()

        # 4. Construct Lightweight Summary
        layers_summary = []
        base_url = api.config['server']['url']

        for layer in db_layers:
            # Map SpaceType Enum to "Theme" string for readability
            # You can adjust this mapping based on your preference (e.g. 'Primal' vs 'Physical')
            theme_val = "Physical" if layer.space_type == SpaceType.primal else "Virtual"

            layers_summary.append({
                "id": layer.id_str,
                "theme": theme_val,
                "semanticExtension": layer.semantic_extension or False,
                "links": [
                    {
                        "href": f"{base_url}/collections/{collection_str_id}/items/{feature_str_id}/layers/{layer.id_str}",
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
                    "href": f"{base_url}/collections/{collection_str_id}/items/{feature_str_id}/layers",
                    "rel": "self",
                    "type": "application/json"
                },
                {
                    "href": f"{base_url}/collections/{collection_str_id}/items/{feature_str_id}",
                    "rel": "up",
                    "type": "application/geo+json",
                    "title": "Parent Feature"
                }
            ]
        }

        return headers, 200, to_json(response, api.pretty_print)

    except Exception as e:
        LOGGER.error(f"Error fetching layers: {e}")
        return api.get_exception(500, headers, request.format, 'ServerError', str(e))

    finally:
        db.close()

def get_collection_item_layer(api: API, request: APIRequest, dataset, identifier, layer) -> Tuple[dict, int, str]:
    """
    Get metadata, stats, and bbox for a specific layer.
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    
    headers = request.get_response_headers(api.api_headers)
    collection_str_id = str(dataset)
    feature_str_id = str(identifier)
    layer_str_id = str(layer)
    
    db = next(get_db())

    try:
        # 1. Resolve IDs and Validate Hierarchy
        coll_pk = resolve_db_id(db, Collection, collection_str_id)
        feat_pk = resolve_db_id(db, IndoorFeature, feature_str_id)

        if not coll_pk:
            return api.get_exception(404, headers, request.format, 'NotFound', 'Collection not found')
        
        if not feat_pk:
            return api.get_exception(404, headers, request.format, 'NotFound', 'Feature not found')

        # Feature must belong to Collection
        feature = db.query(IndoorFeature).filter(
            IndoorFeature.id == feat_pk,
            IndoorFeature.collection_id == coll_pk
        ).first()

        if not feature:
            return api.get_exception(404, headers, request.format, 'NotFound', 
                                   f'Feature {feature_str_id} not found in collection {collection_str_id}')

        # 2. Find the Specific Layer
        target_layer = db.query(ThematicLayer).filter(
            ThematicLayer.id_str == layer_str_id,
            ThematicLayer.indoorfeature_id == feature.id
        ).first()

        if not target_layer:
            return api.get_exception(404, headers, request.format, 'NotFound', f'Layer {layer_str_id} not found')

        # 3. Calculate Stats & BBOX using DB helpers
        stats = _calculate_layer_stats_db(db, target_layer)
        bbox = _calculate_layer_bbox_db(db, target_layer)

        # 4. Construct Response
        response = {
            "id": target_layer.id_str,
            "featureType": "ThematicLayer",
            "theme": "Physical" if target_layer.space_type == SpaceType.primal else "Virtual",
            "semanticExtension": target_layer.semantic_extension or False,
            
            "summary": stats, # Injected from helper
            "bbox": bbox,     # Injected from helper
            "links": []
        }

        # 5. Generate Dynamic HATEOAS Links
        base_url = f"{api.config['server']['url']}/collections/{collection_str_id}/items/{feature_str_id}/layers/{layer_str_id}"

        response['links'].append({
            "href": base_url,
            "rel": "self",
            "type": "application/json",
            "title": "Layer Metadata"
        })

        # Check stats to decide which links to show
        if stats['primalSpace']['cellSpaceCount'] > 0:
            response['links'].append({
                "href": f"{base_url}/primal",
                "rel": "data",
                "type": "application/json",
                "title": "Primal Space (Geometry)"
            })

        if stats['dualSpace']['nodeCount'] > 0 or stats['dualSpace']['edgeCount'] > 0:
            response['links'].append({
                "href": f"{base_url}/dual",
                "rel": "data",
                "type": "application/json",
                "title": "Dual Space (Topology)"
            })

        return headers, 200, to_json(response, api.pretty_print)

    except Exception as e:
        LOGGER.error(f"Error fetching layer detail: {e}")
        return api.get_exception(500, headers, request.format, 'ServerError', str(e))

    finally:
        db.close()


def _calculate_layer_stats_db(db, layer_row):
    """
    Counts rows in child tables (CellSpaceBoundary, NodeEdge) efficiently.
    """
    stats = {
        "primalSpace": {
            "cellSpaceCount": 0,
            "cellBoundaryCount": 0,
            "level": None
        },
        "dualSpace": {
            "nodeCount": 0,
            "edgeCount": 0,
            "isDirected": False, # Default
            "isLogical": True    # Default
        }
    }

    if layer_row.space_type == SpaceType.primal:
        # Count Cells
        cell_count = db.query(CellSpaceBoundary).filter(
            CellSpaceBoundary.thematiclayer_id == layer_row.id
        ).count()
        stats["primalSpace"]["cellSpaceCount"] = cell_count
        
        # Note: If you separate Boundaries (Walls) from Spaces (Rooms) in the same table
        # you might need a 'type' filter here. For now, we assume this table holds Cells.
        
        # Attempt to get Levels (if stored in external_reference or a specific column)
        # simplistic query for distinct levels if column exists:
        # levels = db.query(distinct(CellSpaceBoundary.level)).filter(...).all()
        pass

    elif layer_row.space_type == SpaceType.dual:
        # Count Nodes
        node_count = db.query(NodeEdge).filter(
            NodeEdge.thematiclayer_id == layer_row.id,
            NodeEdge.type == NodeEdgeType.node
        ).count()
        
        # Count Edges
        edge_count = db.query(NodeEdge).filter(
            NodeEdge.thematiclayer_id == layer_row.id,
            NodeEdge.type == NodeEdgeType.edge
        ).count()

        stats["dualSpace"]["nodeCount"] = node_count
        stats["dualSpace"]["edgeCount"] = edge_count
        
        # You can fetch these bools from the layer_row if you added columns for them
        # stats["dualSpace"]["isDirected"] = layer_row.is_directed 

    return stats


def _calculate_layer_bbox_db(db, layer_row):
    """
    Uses PostGIS ST_Extent to calculate the bounding box of the layer's children.
    Returns: [minx, miny, maxx, maxy] or None
    """
    bbox_result = None

    if layer_row.space_type == SpaceType.primal:
        # Aggregate extent of all Cell geometries
        # ST_Extent returns a bounding box (xmin, ymin, xmax, ymax)
        # To extract values, we can cast to geometry and ask for XMin, etc.
        # But a simpler way in raw SQL is ST_XMin(ST_Extent(geom)), etc.
        
        # Query: SELECT ST_XMin(ext), ST_YMin(ext), ST_XMax(ext), ST_YMax(ext) 
        #        FROM (SELECT ST_Extent(geometry_3d) as ext FROM cellspaceboundary WHERE ...)
        
        subq = db.query(func.ST_Extent(CellSpaceBoundary.geometry_3d).label("ext")).filter(
            CellSpaceBoundary.thematiclayer_id == layer_row.id
        ).subquery()
        
        result = db.query(
            func.ST_XMin(subq.c.ext),
            func.ST_YMin(subq.c.ext),
            func.ST_XMax(subq.c.ext),
            func.ST_YMax(subq.c.ext)
        ).first()
        
        if result and result[0] is not None:
            bbox_result = [result[0], result[1], result[2], result[3]]

    elif layer_row.space_type == SpaceType.dual:
        subq = db.query(func.ST_Extent(NodeEdge.geometry_val).label("ext")).filter(
            NodeEdge.thematiclayer_id == layer_row.id
        ).subquery()
        
        result = db.query(
            func.ST_XMin(subq.c.ext),
            func.ST_YMin(subq.c.ext),
            func.ST_XMax(subq.c.ext),
            func.ST_YMax(subq.c.ext)
        ).first()

        if result and result[0] is not None:
            bbox_result = [result[0], result[1], result[2], result[3]]

    return bbox_result

def get_collection_item_interlayerconnections(api: API, request: APIRequest, collection_id: str, item_id: str) -> Tuple[dict, int, str]:
    """
    GET /collections/{id}/items/{featureId}/interlayerconnections
    Retrieves the connections for a specific feature.
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    provider = PostgresIndoorDB()

    try:
        # Fetch connections (Clean name, no 'nested')
        connections_data = provider.get_interlayer_connections(item_id)
        
        response = {
            "layerConnections": connections_data,
            "links": [
                {
                    "href": f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/interlayerconnections",
                    "rel": "self",
                    "type": "application/json",
                    "title": "InterLayer Connections"
                }
            ]
        }
        return headers, HTTPStatus.OK, to_json(response, api.pretty_print)
        
    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        provider.disconnect()


def manage_collection_item_interlayerconnections(api: API, request: APIRequest, action: str, collection_id: str, item_id: str, connection_id: str = None) -> Tuple[dict, int, str]:
    """
    POST / DELETE for Interlayer Connections
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    provider = PostgresIndoorDB()

    try:
        if action == 'create':
            try:
                data = request.data
                if isinstance(data, bytes):
                    data = json.loads(data.decode('utf-8'))
            except Exception:
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'Invalid JSON')

            # Pass collection_id and item_id (feature_id) to helper for ID resolution
            new_id = provider.create_interlayer_connection(collection_id, item_id, data)
            
            if new_id:
                headers['Location'] = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/interlayerconnections/{new_id}"
                return headers, HTTPStatus.CREATED, to_json({"status": "Created", "id": new_id}, api.pretty_print)
            else:
                return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', 'Creation failed (check logs)')

        elif action == 'delete':
            if not connection_id:
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'MissingParameterValue', 'ID required')

            success = provider.delete_interlayer_connection(connection_id)
            if success:
                return headers, HTTPStatus.NO_CONTENT, ''
            else:
                return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Connection not found')

    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        provider.disconnect()

    return headers, HTTPStatus.METHOD_NOT_ALLOWED, ''


def get_list_of_collections_id():
    pidb_provider = PostgresIndoorDB()
    try:
        pidb_provider.connect()
        result = pidb_provider.get_collections_list()
        collections_id = []
        for row in result:
            collections_id.append(row.get('id'))
        return True, collections_id
    except (Exception, psycopg2.Error) as error:
        return False, error
    finally:
        pidb_provider.disconnect()

def validate_bbox(value=None) -> list:
    """
    Helper function to validate bbox parameter

    :param value: `list` of minx, miny, maxx, maxy

    :returns: bbox as `list` of `float` values
    """

    if value is None:
        LOGGER.debug('bbox is empty')
        return []

    bbox = value.split(',')

    if len(bbox) != 4 and len(bbox) != 6:
        msg = 'bbox should be 4 values (minx,miny,maxx,maxy) or \
            6 values (minx,miny,minz,maxx,maxy,maxz)'
        LOGGER.debug(msg)
        raise ValueError(msg)

    try:
        bbox = [float(c) for c in bbox]
    except ValueError as err:
        msg = 'bbox values must be numbers'
        err.args = (msg,)
        LOGGER.debug(msg)
        raise

    if len(bbox) == 4:
        if bbox[1] > bbox[3]:
            msg = 'miny should be less than maxy'
            LOGGER.debug(msg)
            raise ValueError(msg)

        if bbox[0] > bbox[2]:
            msg = 'minx is greater than maxx (possibly antimeridian bbox)'
            LOGGER.debug(msg)
            raise ValueError(msg)

    if len(bbox) == 6:
        if bbox[2] > bbox[5]:
            msg = 'minz should be less than maxz'
            LOGGER.debug(msg)
            raise ValueError(msg)

        if bbox[1] > bbox[4]:
            msg = 'miny should be less than maxy'
            LOGGER.debug(msg)
            raise ValueError(msg)

        if bbox[0] > bbox[3]:
            msg = 'minx is greater than maxx (possibly antimeridian bbox)'
            LOGGER.debug(msg)
            raise ValueError(msg)

    return bbox

