import logging
import json
from http import HTTPStatus
from typing import Tuple

from pygeoapi.api import API, APIRequest, SYSTEM_LOCALE, F_HTML, F_JSON 
import pygeoapi.api as core_api
from pygeoapi.util import to_json
from pygeoapi.util import render_j2_template, to_json

LOGGER = logging.getLogger(__name__)

def manage_collection(api: API, request: APIRequest, action: str) -> Tuple[dict, int, str]:
    """
    PNU STEMLab: Manages IndoorGML Collections (Sites/Campuses)
    This handles the POST /collections registration.
    """
    headers = request.get_response_headers(SYSTEM_LOCALE)
    
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

        # 2. Extract your specific schema: {id, title, description}
        c_id = data.get('id')
        title = data.get('title')
        description = data.get('description', '')

        if not c_id or not title:
            return api.get_exception(
                HTTPStatus.BAD_REQUEST, headers, request.format, 
                'MissingParameterValue', 'Required fields: id, title')

        # 3. Update the Server Configuration in-memory
        # Note: In a production 'Moving Features' style, this might save to a DB
        api.config['resources'][c_id] = {
            'type': 'collection',
            'itemType': 'indoorfeature',  # <--- ADD THIS LINE HERE
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

    return headers, HTTPStatus.METHOD_NOT_ALLOWED, ''

def get_collection(api: API, request: APIRequest, dataset=None) -> Tuple[dict, int, str]:
    """
    GET /collections/{collectionId}
    Provides the specific 'indoorfeature' metadata for JSON requests
    and redirects to core_api for a stable HTML UI.
    """
    # 1. Handle HTML UI: Let the core handle it to avoid the UnboundLocalError
    if request.format == F_HTML:
        return core_api.describe_collections(api, request, dataset)

    # 2. Handle JSON API: Return your custom IndoorGML metadata
    headers = request.get_response_headers(SYSTEM_LOCALE)
    collection_id = str(dataset)

    # We check if this resource actually exists in our current session
    if collection_id not in api.config['resources']:
        return api.get_exception(
            HTTPStatus.NOT_FOUND, headers, request.format,
            'NotFound', 'Collection not found')

    collection = {
        'id': collection_id,
        'itemType': 'indoorfeature',  # Essential for PNU/AIST frontend logic
        'title': api.config['resources'][collection_id].get('title', collection_id),
        'description': api.config['resources'][collection_id].get('description', ''),
        'links': [
            {
                'href': f"{api.config['server']['url']}/collections/{collection_id}/items",
                'rel': 'items',
                'type': 'application/geo+json',
                'title': 'Indoor Features (Cells and Nodes)'
            },
            {
                'href': f"{api.config['server']['url']}/collections/{collection_id}",
                'rel': 'self',
                'type': 'application/json',
                'title': 'Metadata for this collection'
            }
        ]
    }

    return headers, HTTPStatus.OK, to_json(collection, api.pretty_print)

    if request.format == F_HTML:
        # Do the same for the detail view
        return headers, HTTPStatus.OK, render_j2_template(
            api.config, collection, str(request.locale), 'collections/collection.html')

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