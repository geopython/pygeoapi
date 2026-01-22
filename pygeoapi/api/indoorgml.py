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

# Load schema once when the module is loaded
SCHEMA_PATH = 'data/indoorjson_schema.json'
with open(SCHEMA_PATH, 'r') as f:
    INDOOR_SCHEMA = json.load(f)

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

def is_indoor_collection(collection_id: String) -> bool:
    pidb_provider = PostgresIndoorDB()
    try:
        pidb_provider.connect()
        if pidb_provider.is_indoor_collection(collection_id):
            return True
    
    except Exception as e:
            LOGGER.error(f"Error checking collection type: {e}")
    finally:
        pidb_provider.disconnect()

    return False

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
    
def get_collection_item(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
    """
    Get a single collection item

    :param request: A request object
    :param dataset: dataset name
    :param identifier: item identifier

    :returns: tuple of headers, status code, content
    """    
    pidb_provider = PostgresIndoorDB()
    collection_str_id = str(dataset)
    ifeature_str_id = str(identifier)
    if not request.is_valid():
        return api.get_format_exception(request)
    headers = request.get_response_headers()
    try:
        pidb_provider.connect()
        result = pidb_provider.get_feature(collection_str_id, ifeature_str_id)

        base_url = f"{api.config['server']['url']}/collections/{collection_str_id}/items/{ifeature_str_id}"

        result['links'].append({
            "href": base_url,
            "rel": "self",
            "type": "application/geo+json",
            "title": "Indoorfeature metadata"
        })

    except (Exception, psycopg2.Error) as error:
        msg = str(error)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)
    
    return headers, HTTPStatus.OK, to_json(result, api.pretty_print)

def manage_collection_item_layer(api: API, request: APIRequest, action, dataset, identifier, layer=None) -> Tuple[dict, int, str]:
    
    if not request.is_valid(PLUGINS['formatter'].keys()):
        return api.get_format_exception(request)
    
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
    headers = request.get_response_headers(api.api_headers)
    pidb_provider = PostgresIndoorDB()
    collection_str_id = str(dataset)
    feature_str_id = str(identifier)
    layer_str_id = str(layer) if layer else None
    try:
        pidb_provider.connect()
        # =====================================================================
        # ACTION: CREATE (POST)
        # =====================================================================
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
                # Schema Validation
                layer_schema = {
                    "$schema": INDOOR_SCHEMA.get("$schema"),
                    "$defs": INDOOR_SCHEMA.get("$defs"), 
                    "$ref": "#/$defs/ThematicLayer"      
                }
                validate(instance=data, schema=layer_schema)
                pidb_provider.post_thematic_layer(
                    collection_str_id, 
                    feature_str_id,
                    data
                )
                layer_str_id = data.get("id")
            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return api.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pidb_provider.disconnect()
            headers['Location'] = '{}/{}/items/{}'.format(
                api.get_collections_url(), dataset, layer_str_id)

            return headers, 201, to_json({"status": "Created", "id": layer_str_id}, api.pretty_print)  
        # =====================================================================
        # ACTION: DELETE (DELETE)
        # =====================================================================
        elif action == 'delete':
            LOGGER.debug('Deleting layer')
            
            try:
                pidb_provider.connect()
                pidb_provider.delete_thematic_layer(collection_str_id, feature_str_id, layer_str_id)
 
            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return api.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pidb_provider.disconnect()
                return headers, 204, '' # No Content

        else:
            return api.get_exception(405, headers, request.format, 'MethodNotAllowed', "Action not yet implemented")

    except Exception as e:
        LOGGER.error(f"Global error in manage_layer: {e}")
        return api.get_exception(500, headers, request.format, 'ServerError', str(e))

    finally:
        pidb_provider.disconnect()

def get_collection_item_layers(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
    """
    Get summary of layers for a collection item (IndoorFeature)
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    
    headers = request.get_response_headers(api.api_headers)
    executed, collections = get_list_of_collections_id()
    collection_str_id = str(dataset)
    ifeature_str_id = str(identifier)
    
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
    pidb_provider = PostgresIndoorDB()
    LOGGER.debug('Processing theme parameter')

    LOGGER.debug('Processing level parameter')
    theme = request.params.get('theme')
    level = request.params.get('level')
    try:
        pidb_provider.connect()
        data = \
            pidb_provider.get_layers(collection_id=collection_str_id, feature_id=ifeature_str_id, theme=theme, level=level
                                        ,limit=limit, offset=offset)

        # 4. Construct Lightweight Summary
        
        for layer in data["layers"]:

            base_url = api.config['server']['url']
            layer['links']= [
                {
                    "href": f"{base_url}/collections/{collection_str_id}/items/{ifeature_str_id}/layers/{layer.get("id")}",
                    "rel": "item",
                    "type": "application/json",
                    "title": "Layer Detail"
                }
            ]

        data['links'].append(
                {
                    "href": f"{base_url}/collections/{collection_str_id}/items/{ifeature_str_id}/layers",
                    "rel": "self",
                    "type": "application/json"
                }
        )  

        return headers, 200, to_json(data, api.pretty_print)

    except Exception as e:
        LOGGER.error(f"Error fetching layers: {e}")
        return api.get_exception(500, headers, request.format, 'ServerError', str(e))

    finally:
        pidb_provider.disconnect()

def get_collection_item_layer(api: API, request: APIRequest, dataset, identifier, layer) -> Tuple[dict, int, str]:
    """
    Get a single thematic layer

    :param request: A request object
    :param dataset: dataset name
    :param identifier: item identifier
    :param layer: layer identifier

    :returns: tuple of headers, status code, content
    """    
    if not request.is_valid():
        return api.get_format_exception(request)
    
    headers = request.get_response_headers(api.api_headers)
    collection_str_id = str(dataset)
    ifeature_str_id = str(identifier)
    layer_str_id = str(layer)
    pidb_provider = PostgresIndoorDB()
    level = request.params.get('level')
    if not request.is_valid():
        return api.get_format_exception(request)
    try:
        pidb_provider.connect()
        result = pidb_provider.get_layer(collection_str_id, ifeature_str_id, layer_str_id)


        if result is None:
            msg = f"Layer '{layer_str_id}' not found in feature '{ifeature_str_id}'"
            return api.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)
        
    except (Exception, psycopg2.Error) as error:
        msg = str(error)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)
    finally:
        pidb_provider.disconnect()
    
    return headers, HTTPStatus.OK, to_json(result, api.pretty_print)


# def _calculate_layer_stats_db(db, layer_row):
#     """
#     Counts rows in child tables (CellSpaceBoundary, NodeEdge) efficiently.
#     """
#     stats = {
#         "primalSpace": {
#             "cellSpaceCount": 0,
#             "cellBoundaryCount": 0,
#             "level": None
#         },
#         "dualSpace": {
#             "nodeCount": 0,
#             "edgeCount": 0,
#             "isDirected": False, # Default
#             "isLogical": True    # Default
#         }
#     }

#     if layer_row.space_type == SpaceType.primal:
#         # Count Cells
#         cell_count = db.query(CellSpaceBoundary).filter(
#             CellSpaceBoundary.thematiclayer_id == layer_row.id
#         ).count()
#         stats["primalSpace"]["cellSpaceCount"] = cell_count
        
#         # Note: If you separate Boundaries (Walls) from Spaces (Rooms) in the same table
#         # you might need a 'type' filter here. For now, we assume this table holds Cells.
        
#         # Attempt to get Levels (if stored in external_reference or a specific column)
#         # simplistic query for distinct levels if column exists:
#         # levels = db.query(distinct(CellSpaceBoundary.level)).filter(...).all()
#         pass

#     elif layer_row.space_type == SpaceType.dual:
#         # Count Nodes
#         node_count = db.query(NodeEdge).filter(
#             NodeEdge.thematiclayer_id == layer_row.id,
#             NodeEdge.type == NodeEdgeType.node
#         ).count()
        
#         # Count Edges
#         edge_count = db.query(NodeEdge).filter(
#             NodeEdge.thematiclayer_id == layer_row.id,
#             NodeEdge.type == NodeEdgeType.edge
#         ).count()

#         stats["dualSpace"]["nodeCount"] = node_count
#         stats["dualSpace"]["edgeCount"] = edge_count
        
#         # You can fetch these bools from the layer_row if you added columns for them
#         # stats["dualSpace"]["isDirected"] = layer_row.is_directed 

#     return stats


# def _calculate_layer_bbox_db(db, layer_row):
#     """
#     Uses PostGIS ST_Extent to calculate the bounding box of the layer's children.
#     Returns: [minx, miny, maxx, maxy] or None
#     """
#     bbox_result = None

#     if layer_row.space_type == SpaceType.primal:
#         # Aggregate extent of all Cell geometries
#         # ST_Extent returns a bounding box (xmin, ymin, xmax, ymax)
#         # To extract values, we can cast to geometry and ask for XMin, etc.
#         # But a simpler way in raw SQL is ST_XMin(ST_Extent(geom)), etc.
        
#         # Query: SELECT ST_XMin(ext), ST_YMin(ext), ST_XMax(ext), ST_YMax(ext) 
#         #        FROM (SELECT ST_Extent(geometry_3d) as ext FROM cellspaceboundary WHERE ...)
        
#         subq = db.query(func.ST_Extent(CellSpaceBoundary.geometry_3d).label("ext")).filter(
#             CellSpaceBoundary.thematiclayer_id == layer_row.id
#         ).subquery()
        
#         result = db.query(
#             func.ST_XMin(subq.c.ext),
#             func.ST_YMin(subq.c.ext),
#             func.ST_XMax(subq.c.ext),
#             func.ST_YMax(subq.c.ext)
#         ).first()
        
#         if result and result[0] is not None:
#             bbox_result = [result[0], result[1], result[2], result[3]]

#     elif layer_row.space_type == SpaceType.dual:
#         subq = db.query(func.ST_Extent(NodeEdge.geometry_val).label("ext")).filter(
#             NodeEdge.thematiclayer_id == layer_row.id
#         ).subquery()
        
#         result = db.query(
#             func.ST_XMin(subq.c.ext),
#             func.ST_YMin(subq.c.ext),
#             func.ST_XMax(subq.c.ext),
#             func.ST_YMax(subq.c.ext)
#         ).first()

#         if result and result[0] is not None:
#             bbox_result = [result[0], result[1], result[2], result[3]]

#     return bbox_result

def get_collection_item_interlayerconnections(api: API, request: APIRequest, collection_id: str, item_id: str) -> Tuple[dict, int, str]:
    """
    GET /collections/{id}/items/{featureId}/interlayerconnections
    Retrieves the connections for a specific feature.
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    provider = PostgresIndoorDB()

    try:
        # Fetch connections (Clean name, no 'nested')
        connections_data = provider.get_interlayer_connections(collection_id, item_id)

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


            success = provider.delete_interlayer_connection(collection_id, item_id, connection_id)
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

def get_primal(api: API, request: APIRequest, collection_id: str, item_id: str, layer_id: str) -> Tuple[dict, int, str]:
    """
    GET /collections/{id}/items/{featureId}/layers/{layerId}/primal
    Retrieves the PrimalSpaceLayer, populated with its CellSpaces and CellBoundaries.
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    provider = PostgresIndoorDB()

    try:
        # Fetch metadata AND members
        layer_meta, raw_members = provider.get_primal_features_and_metadata(collection_id, item_id, layer_id)

        # Handle 404 if layer doesn't exist
        if layer_meta is None:
            return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Layer not found')
        
        # Construct response
        response = {
            "id": layer_id,
            "featureType": "PrimalSpaceLayer",
            "creationDatetime": layer_meta['p_creation_datetime'].isoformat() if layer_meta['p_creation_datetime'] else None,
            "terminationDatetime": layer_meta['p_termination_datetime'].isoformat() if layer_meta['p_termination_datetime'] else None,
            "cellSpaceMember": [],
            "cellBoundaryMember": []
        }

        # Iterate through the raw DB rows and sort them into the correct list
        for row in raw_members:
            if row['type'] == 'space':
                cell_space = {
                    "id": row['id_str'],
                    "featureType": "CellSpace",
                    "cellSpaceName": row.get('cell_name'),
                    "level": row.get('level'),
                    "poi": row.get('poi', False),
                    "duality": f"#{row.get('duality_id')}" if row.get('duality_id') else None,
                    "cellSpaceGeom": {
                        "geometry2D": json.loads(row['geometry_2d']) if row.get('geometry_2d') else None,
                        "geometry3D": json.loads(row['geometry_3d']) if row.get('geometry_3d') else None
                    },
                    "externalReference": row.get('external_reference')
                    # Note: 'boundedBy' would require a separate join/query or array_agg in SQL
                }
                # Remove keys that are None if you want a cleaner response (optional)
                response["cellSpaceMember"].append(cell_space)
            
            elif row['type'] == 'boundary':
                cell_boundary = {
                    "id": row['id_str'],
                    "featureType": "CellBoundary",
                    "isVirtual": row.get('is_virtual', False),
                    "duality": f"#{row.get('duality_id')}" if row.get('duality_id') else None,
                    "cellBoundaryGeom": {
                        "geometry2D": json.loads(row['geometry_2d']) if row.get('geometry_2d') else None,
                        "geometry3D": json.loads(row['geometry_3d']) if row.get('geometry_3d') else None
                    },
                    "externalReference": row.get('external_reference')
                }
                response["cellBoundaryMember"].append(cell_boundary)

        # Add HATEOAS links
        response["links"] = [
            {
                "href": f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/primal",
                "rel": "self",
                "type": "application/json",
                "title": "Primal Space Layer"
            }
        ]
        
        return headers, HTTPStatus.OK, to_json(response, api.pretty_print)
        
    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        provider.disconnect()

def manage_primal(api: API, request: APIRequest, action: str, collection_id: str, item_id: str, layer_id: str, member_id: str = None) -> Tuple[dict, int, str]:
    headers = request.get_response_headers(SYSTEM_LOCALE)
    provider = PostgresIndoorDB()

    try:
        if action == 'create':
            # 1. Parse JSON Body
            try:
                data = request.data
                if isinstance(data, bytes):
                    data = json.loads(data.decode('utf-8'))
            except Exception:
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'Invalid JSON')

            # 2. Check FeatureType (Space vs Boundary)
            feature_type = data.get('featureType')
            if feature_type not in ['CellSpace', 'CellBoundary']:
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'featureType must be CellSpace or CellBoundary')

            # 3. Create in DB with Error Handling
            try:
                new_id = provider.post_primal_member(collection_id, item_id, layer_id, data)
                
                if new_id:
                    # Success: Return 201 Created and the Location header
                    headers['Location'] = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/primal/{new_id}"
                    return headers, HTTPStatus.CREATED, to_json({"status": "Created", "id": new_id}, api.pretty_print)
                else:
                    # Returns None if the parent Layer/Collection/Item IDs were invalid
                    return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Layer or Parent Feature not found')

            except ValueError as ve:
                # Catch the "Boundaries do not exist" validation error here
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', str(ve))

        # --- DELETE (DELETE) ---
        elif action == 'delete':
            if not member_id:
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'MissingParameterValue', 'ID required for deletion')

            # If you want to ONLY allow deleting CellSpaces (and protect Boundaries),
            # the provider function will return False if the ID belongs to a Boundary.
            success = provider.delete_primal_member(collection_id, item_id, layer_id, member_id)
            
            if success:
                # 204 No Content is the standard success response for DELETE
                return headers, HTTPStatus.NO_CONTENT, ''
            else:
                # If False, it means either the ID didn't exist OR it was a protected Boundary
                return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Member not found (or cannot be deleted)')

        # --- UPDATE (PATCH) ---
        elif action == 'update':
            if not member_id:
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'MissingParameterValue', 'ID required for update')

            try:
                data = request.data
                if isinstance(data, bytes):
                    data = json.loads(data.decode('utf-8'))
                
                # We don't check featureType strictness here because PATCH might be partial
                # But the provider will enforce that the target is a CellSpace

                success = provider.update_primal_member(collection_id, item_id, layer_id, member_id, data)
                
                if success:
                    return headers, HTTPStatus.NO_CONTENT, ''
                else:
                    return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Member not found, is not a CellSpace, or Layer invalid')

            except Exception:
                 return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'Invalid JSON')

    except Exception as e:
        # Catch unexpected server crashes
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        provider.disconnect()

def get_primal_member(api: API, request: APIRequest, collection_id: str, item_id: str, layer_id: str, member_id: str) -> Tuple[dict, int, str]:
    """
    GET /collections/{id}/items/{featureId}/layers/{layerId}/primal/{memberId}
    Retrieves a specific CellSpace or CellBoundary.
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    provider = PostgresIndoorDB()

    try:
        # Fetch member data (returns None if not found)
        member_data = provider.get_primal_member(collection_id, item_id, layer_id, member_id)

        if not member_data:
            return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Member not found')

        # Format Response based on Type
        response = {}
        
        if member_data['type'] == 'space':
            response = {
                "id": member_data['id_str'],
                "featureType": "CellSpace",
                "cellSpaceName": member_data.get('cell_name'),
                "level": member_data.get('level'),
                "poi": member_data.get('poi', False),
                "duality": f"#{member_data['duality_id']}" if member_data.get('duality_id') else None,
                "cellSpaceGeom": {
                    "geometry2D": json.loads(member_data['geometry_2d']) if member_data.get('geometry_2d') else None,
                    "geometry3D": json.loads(member_data['geometry_3d']) if member_data.get('geometry_3d') else None
                },
                "externalReference": member_data.get('external_reference'),
                # Convert the list of IDs ["B1", "B2"] to URI refs ["#B1", "#B2"]
                "boundedBy": [f"#{b_id}" for b_id in member_data['bounded_by_list']] if member_data.get('bounded_by_list') else []
            }
        
        elif member_data['type'] == 'boundary':
            response = {
                "id": member_data['id_str'],
                "featureType": "CellBoundary",
                "isVirtual": member_data.get('is_virtual', False),
                "duality": f"#{member_data['duality_id']}" if member_data.get('duality_id') else None,
                "cellBoundaryGeom": {
                    "geometry2D": json.loads(member_data['geometry_2d']) if member_data.get('geometry_2d') else None,
                    "geometry3D": json.loads(member_data['geometry_3d']) if member_data.get('geometry_3d') else None
                },
                "externalReference": member_data.get('external_reference')
            }

        # Add HATEOAS Links
        response["links"] = [
            {
                "href": f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/primal/{member_id}",
                "rel": "self",
                "type": "application/json",
                "title": "Primal Member"
            },
            {
                "href": f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/primal",
                "rel": "collection",
                "type": "application/json",
                "title": "Primal Space Layer"
            }
        ]
        
        return headers, HTTPStatus.OK, to_json(response, api.pretty_print)
        
    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        provider.disconnect()

# api/indoorgml.py

def get_dual(api: API, request: APIRequest, collection_id: str, item_id: str, layer_id: str) -> Tuple[dict, int, str]:
    """
    GET /collections/.../layers/{layerId}/dual
    Returns all States (Nodes) and Transitions (Edges) in the layer.
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    provider = PostgresIndoorDB()

    try:
        # Fetch all members
        members = provider.get_dual_layer(collection_id, item_id, layer_id)
        
        # Helper to format a single member
        def format_member(m):
            base = {
                "id": m['id_str'],
                "featureType": "State" if m['type'] == 'node' else "Transition",
                "geometry": json.loads(m['geometry']) if m['geometry'] else None,
                "duality": f"#{m['duality_ref']}" if m['duality_ref'] else None,
                "externalReference": m.get('external_reference')
            }
            if m['type'] == 'edge':
                # Edges have 'weight' and 'connects'
                base["weight"] = m['weight']
                if m['source_ref'] and m['target_ref']:
                    base["connects"] = [f"#{m['source_ref']}", f"#{m['target_ref']}"]
            return base

        response = {
            "type": "FeatureCollection",
            "features": [format_member(m) for m in members],
            "links": [
                {
                    "href": f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/dual",
                    "rel": "self",
                    "type": "application/json",
                    "title": "Dual Space Layer"
                }
            ]
        }
        
        return headers, HTTPStatus.OK, to_json(response, api.pretty_print)

    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        provider.disconnect()


def get_dual_member(api: API, request: APIRequest, collection_id: str, item_id: str, layer_id: str, member_id: str) -> Tuple[dict, int, str]:
    """
    GET /collections/.../layers/{layerId}/dual/{memberId}
    Returns a single State or Transition.
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    provider = PostgresIndoorDB()

    try:
        member = provider.get_dual_member(collection_id, item_id, layer_id, member_id)
        
        if not member:
            return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Member not found')

        # Format Response
        response = {
            "id": member['id_str'],
            "featureType": "State" if member['type'] == 'node' else "Transition",
            "geometry": json.loads(member['geometry']) if member['geometry'] else None,
            "duality": f"#{member['duality_ref']}" if member['duality_ref'] else None,
            "externalReference": member.get('external_reference')
        }

        if member['type'] == 'edge':
             response["weight"] = member['weight']
             if member['source_ref'] and member['target_ref']:
                 response["connects"] = [f"#{member['source_ref']}", f"#{member['target_ref']}"]

        response["links"] = [
            {
                "href": f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/dual/{member_id}",
                "rel": "self",
                "type": "application/json",
                "title": "Dual Member"
            }
        ]
        
        return headers, HTTPStatus.OK, to_json(response, api.pretty_print)

    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        provider.disconnect()

def manage_dual(api: API, request: APIRequest, action: str, collection_id: str, item_id: str, layer_id: str, member_id: str = None) -> Tuple[dict, int, str]:
    headers = request.get_response_headers(SYSTEM_LOCALE)
    provider = PostgresIndoorDB()

    try:
        # --- CREATE (POST) ---
        if action == 'create':
            try:
                data = request.data
                if isinstance(data, bytes):
                    data = json.loads(data.decode('utf-8'))
            except Exception:
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'Invalid JSON')

            feature_type = data.get('featureType')
            if feature_type not in ['State', 'Transition']: # OGC terminology
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'featureType must be State or Transition')

            try:
                new_id = provider.post_dual_member(collection_id, item_id, layer_id, data)
                if new_id:
                    headers['Location'] = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/dual/{new_id}"
                    return headers, HTTPStatus.CREATED, to_json({"status": "Created", "id": new_id}, api.pretty_print)
                else:
                    return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Layer invalid')
            except ValueError as ve:
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', str(ve))

        # --- UPDATE (PATCH) ---
        elif action == 'update':
            if not member_id:
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'MissingParameterValue', 'ID required')

            try:
                data = request.data
                if isinstance(data, bytes):
                    data = json.loads(data.decode('utf-8'))
                
                # Check for empty update
                if 'weight' not in data:
                     return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'Only "weight" can be updated')

                success = provider.update_dual_member(collection_id, item_id, layer_id, member_id, data)
                
                if success:
                    return headers, HTTPStatus.NO_CONTENT, ''
                else:
                    return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'Update failed: Item is not a Transition, or ID not found')

            except Exception:
                 return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'Invalid JSON')

        # --- DELETE (DELETE) ---
        elif action == 'delete':
            # Assuming you allow deleting both Nodes and Edges
            success = provider.delete_dual_member(collection_id, item_id, layer_id, member_id)
            if success:
                return headers, HTTPStatus.NO_CONTENT, ''
            else:
                return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Member not found')

    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        provider.disconnect()