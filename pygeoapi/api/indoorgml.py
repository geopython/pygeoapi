import logging
import json
import random
from http import HTTPStatus
from typing import Tuple

import urllib
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

# region IndoorFeatureCollections
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
# endregion

# region IndoorFeatures
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
            #TODO: validate(instance=data, schema=INDOOR_SCHEMA)
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

    # --- OFFSET PARAMETER ---
    LOGGER.debug('Processing offset parameter')
    try:
        offset = int(request.params.get('offset'))
        if offset < 0:
            msg = 'offset value should be positive or zero'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError:
        # DEFAULT is 0
        offset = 0
    except ValueError:
        msg = 'offset value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    # --- LIMIT PARAMETER ---
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
    except TypeError:
        limit=10
    except ValueError:
        msg = 'limit value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)
    
    # --- BBOX PARAMETER ---
    LOGGER.debug('Processing bbox parameter')
    bbox_param = request.params.get('bbox')
    bbox = None

    if bbox_param:
        try:
            bbox = validate_bbox(bbox_param)
        except ValueError as err:
            msg = str(err)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
        
    # --- CALL PROVIDER ---
    # We pass the cleaned params to the DB layer
    LOGGER.debug(f'Querying provider with offset: {offset}, limit: {limit}, bbox: {bbox}')
    provider = PostgresIndoorDB()
    try:
        content, number_matched = provider.get_collection_items(
            collection_id=collection_str_id,
            bbox=bbox,
            limit=limit,
            offset=offset,
        )
    except Exception as err:
        LOGGER.error(f"Provider error: {err}")
        return api.get_exception(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            headers, request.format, 'NoApplicableCode', 'Internal Server Error')

    # --- GENERATE LINKS (Pagination) ---
    links = []
    
    # 1. Self Link
    # Reconstructs current URL with current params
    self_href = f"{api.base_url}/collections/{collection_str_id}/items?offset={offset}&limit={limit}"
    if bbox:
        self_href += f"&bbox={','.join(map(str, bbox))}"
    
    links.append({
        'rel': 'self',
        'type': 'application/geo+json',
        'title': 'This document',
        'href': self_href
    })

    # 2. Next Link
    # Only show if there are more items remaining
    if (offset + limit) < number_matched:
        next_offset = offset + limit
        next_href = f"{api.base_url}/collections/{collection_str_id}/items?offset={next_offset}&limit={limit}"
        if bbox:
            next_href += f"&bbox={','.join(map(str, bbox))}"
        
        links.append({
            'rel': 'next',
            'type': 'application/geo+json',
            'title': 'Next page',
            'href': next_href
        })

    # 3. Previous Link
    # Only show if we are not on the first page
    if offset > 0:
        prev_offset = max(0, offset - limit)
        prev_href = f"{api.base_url}/collections/{collection_str_id}/items?offset={prev_offset}&limit={limit}"
        if bbox:
            prev_href += f"&bbox={','.join(map(str, bbox))}"
            
        links.append({
            'rel': 'prev',
            'type': 'application/geo+json',
            'title': 'Previous page',
            'href': prev_href
        })

    # --- CONSTRUCT RESPONSE ---
    feature_collection = {
        'type': 'FeatureCollection',
        'numberMatched': number_matched,
        'numberReturned': len(content),
        'links': links,
        'features': content
    }
    
    # 1. Get Headers (Standard OGC headers)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    
    # 2. Serialize the content to a string
    content_body = to_json(feature_collection, api.pretty_print)
    
    # 3. Return in the correct order: Headers, Status, Content
    return headers, HTTPStatus.OK, content_body
    
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

    # --- Extract Level Parameter ---
    level = request.params.get('level')
    # You might want to strip whitespace if it's a string
    if level:
        level = str(level).strip()

    try:
        pidb_provider.connect()

        # --- Pass level to the provider ---
        result = pidb_provider.get_feature(
            collection_str_id, 
            ifeature_str_id, 
            level=level 
        )
        
        # If the result is None (e.g., ID doesn't exist), handle 404
        if not result:
             msg = f'Item {identifier} not found'
             return api.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)
        
       # --- Construct Self Link with Query Params ---
        base_url = f"{api.config['server']['url']}/collections/{collection_str_id}/items/{ifeature_str_id}"
        
        self_href = base_url
        
        # If level parameter exists, append it to the URL
        if level:
            query_params = {'level': level}
            self_href += "?" + urllib.parse.urlencode(query_params)

        result['links'].append({
            "href": self_href,
            "rel": "self",
            "type": "application/geo+json",
            "title": "IndoorFeature Metadata"
        })

    except (Exception, psycopg2.Error) as error:
        msg = str(error)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)
    
    return headers, HTTPStatus.OK, to_json(result, api.pretty_print)
#endregion

# region ThematicLayers
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
    
    headers = request.get_response_headers(SYSTEM_LOCALE) # Use standard locale if api_headers not avail
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
            
    # --- OFFSET VALIDATION ---
    try:
        offset = int(request.params.get('offset'))
        if offset < 0:
            msg = 'offset value should be positive or zero'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError:
        offset = 0
    except ValueError:
        msg = 'offset value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    # --- LIMIT VALIDATION ---
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
    except TypeError:
        # Default to 10 if not provided
        limit = 10 
    except ValueError:
        msg = 'limit value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    # --- THEME & LEVEL ---
    theme = request.params.get('theme')
    level = request.params.get('level')

    pidb_provider = PostgresIndoorDB()

    try:
        pidb_provider.connect()
        data = pidb_provider.get_layers(
            collection_id=collection_str_id, 
            feature_id=ifeature_str_id, 
            theme=theme, 
            level=level,
            limit=limit, 
            offset=offset
        )

        # 4. Construct Lightweight Summary & Base URL
        # We define the full endpoint path here to avoid repetition
        base_url = f"{api.config['server']['url']}/collections/{collection_str_id}/items/{ifeature_str_id}/layers"

        # 1. Add Detail Links to each Layer
        for layer in data["layers"]:
            layer['links'] = [
                {
                    "href": f"{base_url}/{layer.get('id')}",
                    "rel": "item",
                    "type": "application/json",
                    "title": "Layer Detail"
                }
            ]

        # 2. Prepare Query Parameters (Robust Construction)
        # We build a base dictionary for params that stay constant (theme, level, limit)
        base_params = {
            'limit': limit
        }
        if theme:
            base_params['theme'] = theme
        if level:
            base_params['level'] = level

        # Helper to generate URL with specific offset
        def make_link(target_offset):
            params = base_params.copy()
            params['offset'] = target_offset
            return f"{base_url}?{urllib.parse.urlencode(params)}"

        # 3. Add Pagination Links (Self, Next, Prev)
        
        # SELF Link
        data['links'].append({
            "href": make_link(offset),
            "rel": "self",
            "type": "application/json",
            "title": "Thematic Layers"
        })

        # NEXT Link
        number_matched = data.get('numberMatched', 0)
        if (offset + limit) < number_matched:
            data['links'].append({
                "href": make_link(offset + limit),
                "rel": "next",
                "type": "application/json",
                "title": "Next page"
            })

        # PREV Link
        if offset > 0:
            prev_offset = max(0, offset - limit)
            data['links'].append({
                "href": make_link(prev_offset),
                "rel": "prev",
                "type": "application/json",
                "title": "Previous page"
            })  

        return headers, HTTPStatus.OK, to_json(data, api.pretty_print)

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
    bbox = request.params.get('bbox')
    
    if not request.is_valid():
        return api.get_format_exception(request)
    try:
        pidb_provider.connect()
        result = pidb_provider.get_layer(collection_str_id, ifeature_str_id, layer_str_id, bbox=bbox, level=level)


        if result is None:
            msg = f"Layer '{layer_str_id}' not found in feature '{ifeature_str_id}'"
            return api.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)
        
        base_url = f"{api.config['server']['url']}/collections/{collection_str_id}/items/{ifeature_str_id}/layers/{layer_str_id}"
        self_href = base_url

        if level:
            query_params = {'level': level}
            self_href += "?" + urllib.parse.urlencode(query_params)

        result["links"].append(
                {
                    "href": self_href,
                    "rel": "self",
                    "type": "application/json",
                    "title": "Thematic Layer"
                }
            )
        
    except (Exception, psycopg2.Error) as error:
        msg = str(error)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)
    finally:
        pidb_provider.disconnect()
    
    return headers, HTTPStatus.OK, to_json(result, api.pretty_print)
# endregion

# region InterLayerConnections
def get_collection_item_interlayerconnections(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
    """
    GET /collections/{id}/items/{featureId}/interlayerconnections
    Retrieves the connections for a specific feature.
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    
    headers = request.get_response_headers(SYSTEM_LOCALE)
    collection_id = str(dataset)
    item_id = str(identifier)
    
    # ---------------------------------------------------------
    # 1. Parse & Validate Pagination (Limit/Offset)
    # ---------------------------------------------------------
    try:
        offset = int(request.params.get('offset'))
        if offset < 0: raise ValueError
    except (TypeError, ValueError):
        offset = 0

    try:
        limit = int(request.params.get('limit'))
        if limit <= 0 or limit > 10000: raise ValueError
    except (TypeError, ValueError):
        limit = 10 

    # ---------------------------------------------------------
    # 2. Parse Filters
    # ---------------------------------------------------------
    # Map API parameter names to Provider arguments
    connected_layer_param = request.params.get('connectedLayerId')
    topo_type_param = request.params.get('typeOfTopoExpression')

    provider = PostgresIndoorDB()

    try:
        provider.connect()
        
        # 3. Call Provider
        # Returns: {'connections': [...], 'numberMatched': X, 'numberReturned': Y}
        data = provider.get_interlayer_connections(
            collection_id, 
            item_id,
            connected_layer_id=connected_layer_param,
            topo_type=topo_type_param,
            limit=limit,
            offset=offset
        )

        # 4. Construct Links
        base_url = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/interlayerconnections"
        
        # Build query string for links to persist filters
        query_params = f"?limit={limit}"
        if connected_layer_param: query_params += f"&connectedLayerId={connected_layer_param}"
        if topo_type_param: query_params += f"&typeOfTopoExpression={topo_type_param}"

        links = []

        # SELF Link
        links.append({
            "href": f"{base_url}{query_params}&offset={offset}",
            "rel": "self",
            "type": "application/json",
            "title": "Current Page"
        })

        # NEXT Link
        number_matched = data.get('numberMatched', 0)
        if (offset + limit) < number_matched:
            next_offset = offset + limit
            links.append({
                "href": f"{base_url}{query_params}&offset={next_offset}",
                "rel": "next",
                "type": "application/json",
                "title": "Next Page"
            })

        # PREV Link
        if offset > 0:
            prev_offset = max(0, offset - limit)
            links.append({
                "href": f"{base_url}{query_params}&offset={prev_offset}",
                "rel": "prev",
                "type": "application/json",
                "title": "Previous Page"
            })

        data['links'] = links

        return headers, HTTPStatus.OK, to_json(data, api.pretty_print)
        
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
            new_id = provider.post_interlayer_connection(collection_id, item_id, data)
            
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

# endregion

# region PrimalSpace
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
    Retrieves the PrimalSpaceLayer.
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    
    headers = request.get_response_headers(SYSTEM_LOCALE)
    pidb_provider = PostgresIndoorDB()

    # ---------------------------------------------------------
    # 1. Parse Query Parameters
    # ---------------------------------------------------------
    level = request.params.get('level')
    cell_space_name = request.params.get('cellSpaceName')
    poi = request.params.get('poi')
    is_virtual = request.params.get('isVirtual')
    try:
        # ---------------------------------------------------------
        # 2. Call Provider with Filters
        # ---------------------------------------------------------
        pidb_provider.connect()
        layer_meta, spaces, boundaries = pidb_provider.get_primal_features(
            collection_id, 
            item_id, 
            layer_id,
            level=level,
            poi=poi,
            is_virtual=is_virtual,
            cell_space_name=cell_space_name
        )

        if layer_meta is None:
            return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Layer not found')
        
        # 3. Construct Response
        response = {
            "id": layer_meta['primalspace_id_str'],
            "featureType": "PrimalSpaceLayer",
            "creationDatetime": layer_meta['p_creation_datetime'].isoformat() if layer_meta['p_creation_datetime'] else None,
            "terminationDatetime": layer_meta['p_termination_datetime'].isoformat() if layer_meta['p_termination_datetime'] else None,
            "cellSpaceMember": spaces,
            "cellBoundaryMember": boundaries
        }

        # 4. Construct Self Link (Persisting filters is good practice)
        base_url = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/primal"
        
        # Rebuild query string
        params_list = []
        if level: params_list.append(f"level={level}")
        if cell_space_name: params_list.append(f"cellSpaceName={cell_space_name}")
        if poi is not None: params_list.append(f"poi={str(poi).lower()}")
        if is_virtual is not None: params_list.append(f"isVirtual={str(is_virtual).lower()}")
        
        query_string = "?" + "&".join(params_list) if params_list else ""

        response["links"] = [
            {
                "href": f"{base_url}{query_string}",
                "rel": "self",
                "type": "application/json",
                "title": "Primal Space Layer"
            }
        ]
        
        return headers, HTTPStatus.OK, to_json(response, api.pretty_print)
        
    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        pidb_provider.disconnect()

def manage_primal(api: API, request: APIRequest, action: str, collection_id: str, item_id: str, layer_id: str, member_id: str = None) -> Tuple[dict, int, str]:
    if not request.is_valid(PLUGINS['formatter'].keys()):
        return api.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    executed, collections = get_list_of_collections_id()
    if executed is False:
        msg = str(collections)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)
    
    if collection_id not in collections:
        msg = 'Collection not found'
        LOGGER.error(msg)
        return api.get_exception(
            HTTPStatus.NOT_FOUND,
            headers, request.format, 'NotFound', msg)
        
    pidb_provider = PostgresIndoorDB()

    if action in ['create', 'update']:
        data = request.data
        # 1. Parse JSON Body
        if not data:
            msg = 'No data found'
            LOGGER.error(msg)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg) 
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
        
    if action == 'create':
        # 2. Check FeatureType (Space vs Boundary)
        feature_type = data.get('featureType')
        if feature_type not in ['CellSpace', 'CellBoundary']:
            return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'featureType must be CellSpace or CellBoundary')

        # 3. Create in DB with Error Handling
        try:
            pidb_provider.connect()
            new_id = pidb_provider.post_primal_member(collection_id, item_id, layer_id, data)
            
            if new_id:
                # Success: Return 201 Created and the Location header
                headers['Location'] = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/primal/{new_id}"
                return headers, HTTPStatus.CREATED, to_json({"status": "Created", "id": new_id}, api.pretty_print)
            else:
                # Returns None if the parent Layer/Collection/Item IDs were invalid
                return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Query parameters or data body error')

        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pidb_provider.disconnect()

    # --- DELETE (DELETE) ---
    elif action == 'delete':
        if not member_id:
            return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'MissingParameterValue', 'ID required for deletion')
        try:
            pidb_provider.connect()
            success = pidb_provider.delete_primal_member(collection_id, item_id, layer_id, member_id)
            
            if success:
                # 204 No Content is the standard success response for DELETE
                return headers, HTTPStatus.NO_CONTENT, ''
            else:
                # If False, it means either the ID didn't exist OR it was a protected Boundary
                return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Member not found (or cannot be deleted)')
            
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pidb_provider.disconnect()

    # --- UPDATE (PATCH) ---
    elif action == 'update':
        if not member_id:
            return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'MissingParameterValue', 'ID required for update')

        try:
            pidb_provider.connect()
            success = pidb_provider.update_primal_member(collection_id, item_id, layer_id, member_id, data)
            
            if success:
                return headers, HTTPStatus.NO_CONTENT, 'update success'
            else:
                return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Member not found, is not a CellSpace, or Layer invalid')

        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pidb_provider.disconnect()


def get_primal_member(api: API, request: APIRequest, collection_id: str, item_id: str, layer_id: str, member_id: str) -> Tuple[dict, int, str]:
    """
    GET /collections/{id}/items/{featureId}/layers/{layerId}/primal/{memberId}
    Retrieves a specific CellSpace or CellBoundary.
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    pidb_provider = PostgresIndoorDB()

    try:
        pidb_provider.connect()
        member_data = pidb_provider.get_primal_member(collection_id, item_id, layer_id, member_id)

        if not member_data:
            return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Member not found')

        # Add HATEOAS Links
        member_data["links"] = [
            {
                "href": f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/primal/{member_id}",
                "rel": "self",
                "type": "application/json",
                "title": "Primal Member"
            },
        ]
        
        return headers, HTTPStatus.OK, to_json(member_data, api.pretty_print)
        
    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        pidb_provider.disconnect()
# endregion

# region dualSpace
def get_dual(api: API, request: APIRequest, collection_id: str, item_id: str, layer_id: str) -> Tuple[dict, int, str]:
    """
    GET /collections/{id}/items/{featureId}/layers/{layerId}/dual
    Retrieves the DualSpaceLayer (MultiLayeredGraph).
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    
    headers = request.get_response_headers(SYSTEM_LOCALE)
    pidb_provider = PostgresIndoorDB()

    # 1. Extract and Parse Query Parameters
    min_weight_param = request.params.get('minWeight')
    max_weight_param = request.params.get('maxWeight')

    try:
        min_weight = float(min_weight_param) if min_weight_param else None
        max_weight = float(max_weight_param) if max_weight_param else None
    except ValueError:
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameter', "Weights must be valid numbers")

    try:
        pidb_provider.connect()
        # 2. Call the Provider function
        meta, nodes, edges = pidb_provider.get_dual_features(
            collection_id, 
            item_id, 
            layer_id, 
            min_weight=min_weight, 
            max_weight=max_weight
        )

        if not meta:
             return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Layer not found')

        # 3. Construct Self Link with Query Params (Robust Method)
        base_url = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/dual"

        query_params = {}
        if min_weight:
            query_params['minWeight'] = min_weight
        if max_weight:
            query_params['maxWeight'] = max_weight
            
        self_href = base_url
        if query_params:
            self_href += "?" + urllib.parse.urlencode(query_params)

        # 4. Construct Response
        response = {
            "id": meta['dualspace_id_str'],
            "featureType": "DualSpaceLayer",
            "isLogical": meta.get('is_logical', False), 
            "isDirected": meta.get('is_directed', False),
            "creationDatetime": meta['d_creation_datetime'].isoformat() if meta.get('d_creation_datetime') else None,
            "terminationDatetime": meta['d_termination_datetime'].isoformat() if meta.get('d_termination_datetime') else None,
            
            "nodeMember": nodes, 
            "edgeMember": edges,
            
            "links": [
                {
                    "href": self_href,
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
        pidb_provider.disconnect()

def get_dual_member(api: API, request: APIRequest, collection_id: str, item_id: str, layer_id: str, member_id: str) -> Tuple[dict, int, str]:
    """
    GET /collections/.../layers/{layerId}/dual/{memberId}
    Retrieves a single Node or Edge.
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    
    headers = request.get_response_headers(SYSTEM_LOCALE)
    pidb_provider = PostgresIndoorDB()
    try:
        pidb_provider.connect()
        # Fetch the specific member data
        member = pidb_provider.get_dual_member(collection_id, item_id, layer_id, member_id)
        
        if not member:
            return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Member not found')

        # 3. HATEOAS Links
        member["links"] = [
            {
                "href": f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/dual/{member_id}",
                "rel": "self",
                "type": "application/json",
                "title": "Dual Member"
            },
        ]
        
        return headers, HTTPStatus.OK, to_json(member, api.pretty_print)

    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        pidb_provider.disconnect()

def manage_dual(api: API, request: APIRequest, action: str, collection_id: str, item_id: str, layer_id: str, member_id: str = None) -> Tuple[dict, int, str]:
    """
    POST /collections/.../layers/{tId}/dual
    Manages dual members (Edges and Nodes) within a layer.
    DELETE, PATCH /collections/.../layers/{tId}/dual/{mId}
    Deletes or updates a specific dual member.
    """
    if not request.is_valid(PLUGINS['formatter'].keys()):
        return api.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    executed, collections = get_list_of_collections_id()
    if executed is False:
        msg = str(collections)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)
    
    if collection_id not in collections:
        msg = 'Collection not found'
        LOGGER.error(msg)
        return api.get_exception(
            HTTPStatus.NOT_FOUND,
            headers, request.format, 'NotFound', msg)
    
    pidb_provider = PostgresIndoorDB()

    if action in ['create', 'update']:
        data = request.data
        # 1. Parse JSON Body
        if not data:
            msg = 'No data found'
            LOGGER.error(msg)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg) 
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

   
    # --- CREATE (POST) ---
    if action == 'create':
        feature_type = data.get('featureType')
        if feature_type not in ['Node', 'Edge']: 
            return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'featureType must be Node or Edge')

        try:
            pidb_provider.connect()
            new_id = pidb_provider.post_dual_member(collection_id, item_id, layer_id, data)
            if new_id:
                headers['Location'] = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/dual/{new_id}"
                return headers, HTTPStatus.CREATED, to_json({"status": "Created", "id": new_id}, api.pretty_print)
            else:
                return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Layer invalid')
        except Exception as e:
            return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
        finally:
            pidb_provider.disconnect()

    # --- UPDATE (PATCH) ---
    elif action == 'update':
        if not member_id:
            return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'MissingParameterValue', 'ID required')

        # Check for empty update
        if 'weight' not in data:
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'Only "weight" can be updated')
        try:
            pidb_provider.connect()
            success = pidb_provider.update_dual_member(collection_id, item_id, layer_id, member_id, data)
            
            if success:
                return headers, HTTPStatus.NO_CONTENT, ''
            else:
                return api.get_exception(HTTPStatus.BAD_REQUEST, headers, request.format, 'InvalidParameterValue', 'Update failed: Item is not a Transition, or ID not found')
        except Exception as e:
            return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
        finally:
            pidb_provider.disconnect()

    # --- DELETE (DELETE) ---
    elif action == 'delete':
        try:
            pidb_provider.connect()
        # Assuming you allow deleting both Nodes and Edges
            success = pidb_provider.delete_dual_member(collection_id, item_id, layer_id, member_id)
            if success:
                return headers, HTTPStatus.NO_CONTENT, ''
            else:
                return api.get_exception(HTTPStatus.NOT_FOUND, headers, request.format, 'NotFound', 'Member not found')
        except Exception as e:
            return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
        finally:
            pidb_provider.disconnect()
# endregion

# region Services

def get_route(api: API, request: APIRequest, collection_id: str, item_id: str, layer_id: str) -> Tuple[dict, int, str]:
    """
    GET /collections/{id}/items/{featureId}/layers/{layerId}/dual/route
    Computes an indoor route using the dual graph.

    :param collection_id: Collection ID
    :param item_id: Item ID
    :param layer_id: Layer ID
    :param start_node: Start node ID
    :param end_node: End node ID

    :return: Route information
    """
    if not request.is_valid():
        return api.get_format_exception(request)
    
    headers = request.get_response_headers(SYSTEM_LOCALE)
    provider = PostgresIndoorDB()

    # 1. Extract Start (sn) and Destination (dn) nodes from query parameters
    sn = request.params.get('sn')
    dn = request.params.get('dn')

    if not sn or not dn:
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'MissingParameter', "Both 'sn' and 'dn' are required")

    try:
        # 2. Call the Provider (The logic we discussed earlier)
        # Expecting a list of nodes/edges or a GeoJSON LineString
        route_data = provider.get_indoor_route(collection_id, item_id, layer_id, sn, dn)

        if not route_data or not route_data.get('geometry'):
             return api.get_exception(
                 HTTPStatus.NOT_FOUND, 
                 headers, request.format, 'NotFound', 'No path found between the specified nodes')

        # 3. Construct Self Link
        base_url = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/layers/{layer_id}/dual/route"
        self_href = f"{base_url}?sn={urllib.parse.quote(sn)}&dn={urllib.parse.quote(dn)}"

        # 4. Construct the RouteResults Response
        response = {
            "type": "RouteResult",
            "inputs": {
                "sn": sn,
                "dn": dn
            },
            "cost": {
                "totalWeight": route_data.get('total_weight')
            },
            "route": {
                "creationDate": route_data['creation_date'].isoformat() if route_data.get('creation_date') else None,
                "routeNodes": route_data.get('route_nodes', []),
                "routeEdges": route_data.get('route_edges', [])
            },
            "links": [
                {
                    "href": self_href,
                    "rel": "self",
                    "type": "application/json",
                    "title": "Indoor Route Result"
                }
            ]
        }
        
        return headers, HTTPStatus.OK, to_json(response, api.pretty_print)

    except Exception as e:
        return api.get_exception(HTTPStatus.INTERNAL_SERVER_ERROR, headers, request.format, 'ServerError', str(e))
    finally:
        provider.disconnect()

# endregion