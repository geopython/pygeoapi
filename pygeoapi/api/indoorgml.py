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

def get_collection_item_interlayerconnections(api: API, request: APIRequest, dataset, identifier) -> Tuple[dict, int, str]:
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
    raw_interLayerConnections = target_feature.get('layerConnections', [])
    base_url = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/interlayerconnections"

    response = {
        "layerConnections": raw_interLayerConnections,
        "links": [
            {
                "href": base_url,
                "rel": "self",
                "type": "application/json",
                "title": "InterLayer Connections (Full)"
            },
            {
                "href": f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}",
                "rel": "up",
                "type": "application/geo+json",
                "title": "Parent Feature"
            }
        ]
    }


    return headers, HTTPStatus.OK, to_json(response, api.pretty_print)
def manage_collection_item_interlayerconnections(api: API, request: APIRequest, action, dataset, identifier, connection=None) -> Tuple[dict, int, str]:
    if not request.is_valid():
        return api.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE)
    collection_id = str(dataset)
    item_id = str(identifier)
    connection_id = str(connection)
    LOGGER.debug(headers) 

    if action == 'create':
        try:
            # 1. Parse Request Body
            data = json.loads(request.data.decode('utf-8'))
            
            # 2. Create Schema Wrapper for InterLayerConnection Validation
            # We use the definitions from the main INDOOR_SCHEMA but validate against the specific definition
            connection_schema = {
                "$schema": INDOOR_SCHEMA.get("$schema"),
                "$defs": INDOOR_SCHEMA.get("$defs"),
                "$ref": "#/$defs/InterLayerConnection" 
            }
            
            validate(instance=data, schema=connection_schema)

            # 3. Locate the Collection and Feature
            resource = api.config['resources'].get(collection_id)
            if not resource:
                 return api.get_exception(404, headers, request.format, 'NotFound', f'Collection {collection_id} not found')

            items = resource.get('items', [])
            target_feature = next((item for item in items if item.get('id') == item_id), None)
            
            if not target_feature:
                return api.get_exception(404, headers, request.format, 'NotFound', f'Feature {item_id} not found')

            # 4. Prepare the layerConnections Array
            if 'layerConnections' not in target_feature:
                target_feature['layerConnections'] = []

            
            # Check if connection ID already exists
            if any(c.get('id') == data['id'] for c in target_feature['layerConnections']):
                 return api.get_exception(400, headers, request.format, 'InvalidParameter', f"Connection ID {data['id']} already exists")

            # 6. Save (Append) the Connection
            target_feature['layerConnections'].append(data)
            
            # 7. Success Response
            headers['Location'] = f"{api.config['server']['url']}/collections/{collection_id}/items/{item_id}/interlayerconnections/{data['id']}"
            return headers, 201, to_json({"status": "Created", "id": data['id']}, api.pretty_print)

        except ValidationError as v_err:
            return api.get_exception(400, headers, request.format, 'InvalidRequest', f"Schema Error: {v_err.message}")
        except Exception as e:
            return api.get_exception(400, headers, request.format, 'InvalidRequest', str(e))
    
    # actions (DELETE)
  
    elif action == 'delete': 
        # 1. Locate Collection and Feature
        resource = api.config['resources'].get(collection_id)
        if not resource:
             return api.get_exception(404, headers, request.format, 'NotFound', f'Collection {collection_id} not found')

        items = resource.get('items', [])
        target_feature = next((item for item in items if item.get('id') == item_id), None)
        
        if not target_feature:
            return api.get_exception(404, headers, request.format, 'NotFound', f'Feature {item_id} not found')

        # 2. Check if connections exist
        if 'layerConnections' not in target_feature:
             return api.get_exception(404, headers, request.format, 'NotFound', f'Connection {connection_id} not found (No connections exist)')

        current_connections = target_feature['layerConnections']
        original_count = len(current_connections)

        # 3. Filter out the specific connection
        target_feature['layerConnections'] = [c for c in current_connections if c.get('id') != connection_id]

        # 4. Verification
        if len(target_feature['layerConnections']) == original_count:
            return api.get_exception(404, headers, request.format, 'NotFound', f'Connection {connection_id} not found')

        # 5. Success
        return headers, 204, ''