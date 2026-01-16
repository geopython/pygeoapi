import logging
import json
from http import HTTPStatus
from typing import Tuple

from pygeoapi.api import API, APIRequest, SYSTEM_LOCALE, F_HTML, F_JSON 
import pygeoapi.api as core_api
from pygeoapi.util import to_json
from pygeoapi.util import render_j2_template, to_json
import os
from jsonschema import validate, ValidationError
from datetime import datetime

# Load schema once when the module is loaded
SCHEMA_PATH = 'data/indoorjson_schema.json'
with open(SCHEMA_PATH, 'r') as f:
    INDOOR_SCHEMA = json.load(f)

with open('data/thematiclayer_schema.json' ,'r') as f:
    THEMATIC_SCHEMA= json.load(f)
    
LOGGER = logging.getLogger(__name__)

def manage_collection(api: API, request: APIRequest, action: str, dataset: str = None) -> Tuple[dict, int, str]:
    """
    PNU STEMLab: Manages IndoorGML Collections (Sites/Campuses)
    This handles the POST /collections registration and DELETE /collections/{id}.
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    
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

        # 2. Extract your dynamic schema
        c_id = data.get('id')
        title = data.get('title')
        description = data.get('description', '')
        # Get itemType from body, default to 'indoorfeature'
        item_type = data.get('itemType', 'indoorfeature') 

        if not c_id or not title:
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format, 
                'MissingParameterValue', 'Required fields: id, title')

        # 3. Update the Server Configuration in-memory
        api.config['resources'][c_id] = {
            'type': 'collection',
            'itemType': item_type,  # <--- Dynamically set from the POST body
            'title': title,
            'description': description,
            'providers': [{
                'type': 'feature',
                'name': 'IndoorGML',
                'data': f'data/{c_id}.json'
            }]
        }

        # 4. Success Response
        response_data = {'id': c_id, 'status': 'created'}
        return headers, HTTPStatus.CREATED, to_json(response_data, api.pretty_print)

    # --- Action: DELETE ---
    elif action == 'delete':
        collection_id = str(dataset)
        
        # 1. Check if it exists in memory
        if collection_id not in api.config['resources']:
            return api.get_exception(
                HTTPStatus.NOT_FOUND, headers, request.format,
                'NotFound', f'Collection {collection_id} does not exist')

        # 2. Cascade Delete: Physically remove the JSON file from the /data folder
        file_path = os.path.join('data', f'{collection_id}.json')
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                # We log the error but continue to ensure memory is cleared
                pass

        # 3. Remove from in-memory configuration
        del api.config['resources'][collection_id]
        
        # 4. Success Response: 204 No Content
        return headers, HTTPStatus.NO_CONTENT, ''

    return headers, HTTPStatus.METHOD_NOT_ALLOWED, ''

def get_collection(api: API, request: APIRequest, dataset=None) -> Tuple[dict, int, str]:
    """
    GET /collections/{collectionId}
    """
    collection_id = str(dataset)
    headers = request.get_response_headers(SYSTEM_LOCALE)

    # 1. THE PERSISTENCE CHECK
    # If the server was restarted, this resource will be missing.
    if collection_id not in api.config['resources']:
        return api.get_exception(
            404, headers, request.format,
            'NotFound', f'Collection {collection_id} not found. If you restarted the server, please re-run your POST request.')

    # 2. Handle HTML UI: The "Safe Injection"
    if request.format == 'html':
        resource = api.config['resources'][collection_id]
        
        # Inject mandatory OGC fields that the HTML templates require
        resource.setdefault('keywords', [])
        if 'extents' not in resource:
            resource['extents'] = {
                'spatial': {'bbox': [0, 0, 0, 0], 'crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'},
                'temporal': None
            }
        
        # Call the core API to render the page
        return core_api.describe_collections(api, request, collection_id)

    # 3. Handle JSON API: Your Clean Design
    resource = api.config['resources'][collection_id]
    collection = {
        "id": collection_id,
        "title": resource.get('title', collection_id),
        "description": resource.get('description', ''),
        "links": [
            {
                "href": f"{api.config['server']['url']}/collections/{collection_id}",
                "rel": "self", "type": "application/json", "title": "Metadata"
            },
            {
                "href": f"{api.config['server']['url']}/collections/{collection_id}/items",
                "rel": "items", "type": "application/geo+json", "title": "Items"
            }
        ],
        "itemType": resource.get('itemType', 'indoorfeature')
    }

    return headers, 200, to_json(collection, api.pretty_print)

def describe_collections(api: API, request: APIRequest) -> Tuple[dict, int, str]:
    """
    GET /collections
    Injects virtual metadata for HTML UI, returns clean design for JSON.
    """
    # 1. Handle HTML UI: The "Virtual Metadata" injection
    if request.format == F_HTML:
        # Create a temporary 'safe' version of the config
        original_resources = api.config['resources']
        virtual_resources = {}

        for c_id, resource in original_resources.items():
            # Copy your clean data and add only what the UI template demands
            v_res = resource.copy()
            v_res.setdefault('keywords', [])
            v_res.setdefault('extents', {'spatial': {'bbox': [0,0,0,0]}, 'temporal': None})
            virtual_resources[c_id] = v_res
        
        # Swap in the virtual config, render the UI, then swap back immediately
        api.config['resources'] = virtual_resources
        try:
            response = core_api.describe_collections(api, request)
        finally:
            api.config['resources'] = original_resources
        
        return response

    # 2. Handle JSON: Your clean, original design (No keywords, No junk)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    collections_list = []

    for c_id, resource in api.config['resources'].items():
        if resource.get('type') == 'collection':
            collections_list.append({
                'id': c_id,
                'title': resource.get('title', c_id),
                'itemType': resource.get('itemType', 'feature'),
                'links': [
                    {'href': f"{api.config['server']['url']}/collections/{c_id}", 'rel': 'self', 'type': 'application/json'},
                    {'href': f"{api.config['server']['url']}/collections/{c_id}/items", 'rel': 'items', 'type': 'application/geo+json'}
                ]
            })

    content = {'collections': collections_list, 'links': []}
    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)

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
    """
    collection_id = str(dataset)
    headers = request.get_response_headers(SYSTEM_LOCALE)

    try:
        # 1. Parse incoming IndoorFeatures JSON
        data = json.loads(request.data.decode('utf-8'))
        
        validate(instance=data, schema=INDOOR_SCHEMA)

        resource = api.config['resources'][collection_id]
        if 'items' not in resource:
            resource['items'] = []
        
        resource['items'].append(data)
        
        return headers, 201, to_json({"status": "Created", "id": data.get('id', 'unnamed')}, api.pretty_print)

    except ValidationError as v_err:
        # Returns exactly where the schema failed (e.g. "Edge weight must be a number")
        return api.get_exception(400, headers, request.format, 
                                'InvalidRequest', f"Schema Error: {v_err.message}")
    except Exception as e:
        return api.get_exception(400, headers, request.format, 'InvalidRequest', str(e))

def get_features(api: API, request: APIRequest, dataset) -> Tuple[dict, int, str]:
    """
    GET /collections/{cId}/items
    Returns a list of building metadata (metaGeoJSON) wrapped in a FeatureCollection.
    """
    collection_id = str(dataset)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    
    resource = api.config['resources'].get(collection_id)
    items = resource.get('items', [])

    # 1. Transform each building into metaGeoJSON (Summary only)
    meta_features = []
    for item in items:
        item_id = item.get('id', 'unnamed')
        
        # Extract metadata from the item or use defaults
        # In a real scenario, you'd pull 'creationDate' from the layers
        meta_feat = {
            "type": "Feature",
            "featureType": "IndoorFeatures",
            "id": item_id,
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]] # Placeholder footprint
            },
            "properties": {
                "metadata": {
                    "description": f"Metadata for IndoorGML model: {item_id}",
                    "creationDate": datetime.utcnow().isoformat() + "Z",
                    "version": "2.0"
                }
            },
            "links": [
                {
                    "href": f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}",
                    "rel": "item",
                    "type": "application/json",
                    "title": "Full IndoorGML Graph"
                }
            ]
        }
        meta_features.append(meta_feat)

    # 2. Wrap in featureCollectionGeoJSON structure
    response = {
        "type": "FeatureCollection",
        "features": meta_features,
        "numberMatched": len(items),
        "numberReturned": len(items),
        "timeStamp": datetime.utcnow().isoformat() + "Z",
        "links": [
            {
                "href": f"{api.config['server']['url']}/collections/{collection_id}/items",
                "rel": "self",
                "type": "application/json"
            }
        ]
    }

    return headers, 200, to_json(response, api.pretty_print)
    
def get_feature(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
    """
    GET /collections/{cId}/items/{itemId}
    Transforms raw data into the featureGeoJSON schema.
    """
    collection_id = str(dataset)
    item_id = str(identifier)
    headers = request.get_response_headers(SYSTEM_LOCALE)

    resource = api.config['resources'].get(collection_id)
    items = resource.get('items', [])

    # Find the raw data
    raw_data = next((item for item in items if item.get('id') == item_id), None)

    if not raw_data:
        return api.get_exception(404, headers, request.format, 'NotFound', f'Feature {item_id} not found.')

    # TRANSFORM TO featureGeoJSON SCHEMA
    # We'll calculate a simple footprint from the first layer for the root 'geometry'
    footprint = {
        "type": "Polygon",
        "coordinates": [[[0,0], [10,0], [10,10], [0,10], [0,0]]] # Placeholder footprint
    }

    feature_geojson = {
        "type": "Feature",
        "featureType": "IndoorFeatures",
        "id": item_id,
        "geometry": footprint, # Standard GeoJSON geometry
        "properties": {
            "metadata": {
                "description": f"IndoorGML model for {item_id}",
                "creationDate": "2026-01-16T15:00:00Z", # You can grab this from data if exists
                "version": "2.0"
            }
        },
        "IndoorFeatures": raw_data, # This is the "massive IndoorGML graph"
        "links": [
            {
                "href": f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}",
                "rel": "self",
                "type": "application/json"
            }
        ]
    }

    return headers, 200, to_json(feature_geojson, api.pretty_print)

def delete_feature(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
    """
    DELETE /collections/{cId}/items/{itemId}
    Remove a building model from the collection.
    """
    collection_id = str(dataset)
    item_id = str(identifier)
    headers = request.get_response_headers(SYSTEM_LOCALE)

    resource = api.config['resources'].get(collection_id)
    items = resource.get('items', [])

    # Find the index of the item
    for i, item in enumerate(items):
        if item.get('id') == item_id:
            items.pop(i)
            return headers, 204, ""  # 204 No Content is standard for successful DELETE

    return api.get_exception(404, headers, request.format, 'NotFound', f'Feature {item_id} not found.')

def manage_collection_item_layer(api: API, request: APIRequest, action, dataset, identifier, layer=None) -> Tuple[dict, int, str]:
    collection_id = str(dataset)
    item_id = str(identifier)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    LOGGER.debug(headers)
    real_action = action
    real_collection_id = collection_id
    real_item_id = item_id

    # action 자리에 collection_id가 들어온 것으로 의심되는 경우
    # (예: action='IndoorGML_Data', col_id='AIST_Waterfront_Center', item_id=None)
    if action not in ['create', 'update', 'delete'] and collection_id is not None:
        LOGGER.warning("Arguments seem shifted! Auto-fixing...")
        
        # request.method가 POST면 action은 'create'라고 가정
        if hasattr(request, 'method') and request.method == 'POST':
            real_action = 'create'
        else:
            real_action = 'get' # 기본값
        
        real_collection_id = action  # 첫 번째 인자가 컬렉션 ID였음
        real_item_id = collection_id # 두 번째 인자가 아이템 ID였음
        
        LOGGER.info(f"Fixed Args -> action: {real_action}, col_id: {real_collection_id}, item_id: {real_item_id}")
    if action == 'create':
        
        try:
            # 1. Parse incoming IndoorFeatures JSON
            data = json.loads(request.data.decode('utf-8'))
            
            validate(instance=data, schema=THEMATIC_SCHEMA)

            resource = api.config['resources'][collection_id][item_id]
            if 'layers' not in resource:
                resource['layers'] = []
            
            resource['layers'].append(data)
            
            return headers, 201, to_json({"status": "Created", "id": data.get('id', 'unnamed')}, api.pretty_print)

        except ValidationError as v_err:
            # Returns exactly where the schema failed (e.g. "Edge weight must be a number")
            return api.get_exception(400, headers, request.format, 
                                    'InvalidRequest', f"Schema Error: {v_err.message}")
        except Exception as e:
            return api.get_exception(400, headers, request.format, 'InvalidRequest', str(e))
    else:
        print("wrong way")
        
def get_collection_item_layer(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
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
    LOGGER.debug(headers)
    
    
    