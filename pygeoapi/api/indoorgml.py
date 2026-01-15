import logging
import json
from http import HTTPStatus
from typing import Tuple

from pygeoapi.api import API, APIRequest, SYSTEM_LOCALE, F_HTML, F_JSON 
import pygeoapi.api as core_api
from pygeoapi.util import to_json
from pygeoapi.util import render_j2_template, to_json
import os

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

def get_collection(api: API, request: APIRequest, dataset=None) -> Tuple[dict, int, str]:
    collection_id = str(dataset)
    headers = request.get_response_headers(SYSTEM_LOCALE)

    # CRITICAL: Prevent the Jinja2 UndefinedError
    if collection_id not in api.config['resources']:
        return api.get_exception(404, headers, request.format, 'NotFound', 'Resource missing from memory. Please re-POST.')

    # JSON Spec (Always works)
    if request.format == 'json':
        resource = api.config['resources'][collection_id]
        collection = {
            "id": collection_id,
            "title": resource.get('title', collection_id),
            "description": resource.get('description', ''),
            "links": [
                {"href": f"{api.config['server']['url']}/collections/{collection_id}", "rel": "self", "type": "application/json"},
                {"href": f"{api.config['server']['url']}/collections/{collection_id}/items", "rel": "items", "type": "application/geo+json"}
            ],
            "itemType": resource.get('itemType', 'indoorfeature')
        }
        return headers, 200, to_json(collection, api.pretty_print)

    # HTML UI (Safety Injection)
    resource = api.config['resources'][collection_id]
    resource.setdefault('keywords', [])
    resource.setdefault('extents', {'spatial': {'bbox': [0,0,0,0]}, 'temporal': None})
    return core_api.describe_collections(api, request, collection_id)

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