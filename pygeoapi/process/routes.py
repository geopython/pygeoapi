# =================================================================
#
# Authors: Ignacio Correas <nacho@skymantics.com>
#
# Copyright (c) 2022 Skymantics LLC
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

import logging
import time
import json
import os
import uuid
import threading

from psycopg2.sql import SQL, Identifier, Literal

from pygeoapi.process.base import (BaseProcessor, ProcessorExecuteError,
    ProcessorCannotComputeError, ProcessorItemNotFoundError)
from pygeoapi.provider.postgresql import DatabaseConnection as pgRoutingConnection

LOGGER = logging.getLogger(__name__)

#: Process metadata and description
PROCESS_METADATA = {
    'version': '0.1.0',
    'id': 'routes-processor',
    'title': 'Routes',
    'description': 'A routing processor to test OGC API - Routes and the Route '
              'Exchange Model draft specs, using pgRouting as routing engine. ',
    'keywords': ['routes', 'REM', 'OGC', 'API'],
    'links': [{
        'type': 'text/html',
        'rel': 'about',
        'title': 'information',
        'href': 'https://example.org/process',
        'hreflang': 'en-US'
    }],
    'inputs': {
        'name': {
            'title': 'Name',
            'description': 'Name of the route (optional).',
            'schema': {
                'type': 'string'
            },
            'minOccurs': 0,
            'maxOccurs': 1
        },
        'waypoints': {
            'title': 'Waypoints',
            'description': 'The start and end point of the route, as well as '
                'any other intermediate point.',
            'minOccurs': 1,
            'maxOccurs': 1,
            'schema': {
                'allOf': [
                    { 'format': 'geojson-geometry' },
                    {
                        'type': 'object',
                        'title': 'GeoJSON MultiPoint',
                        'required': [ 'type', 'coordinates' ],
                        'properties': {
                            'type': {
                                'type': 'string',
                                'enum': [ 'MultiPoint' ]
                            },
                            'coordinates': {
                                'type': 'array',
                                'items': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'number',
                                        'minItems': 2,
                                        'maxItems': 3
                                    },
                                    'minItems': 2
                                }
                            }
                        }
                    }
                ]
            }
        },
        'preference': {
            'title': 'Preference',
            'description': 'Preference or cost function.',
            'schema': {
                'type': 'string',
                'enum': [  ]
            },
            'minOccurs': 0,
            'maxOccurs': 1
        },
        'mode': {
            'title': 'Mode',
            'description': 'Type of transport desired.',
            'schema': {
                'type': 'string',
                'enum': [  ]
            },
            'minOccurs': 0,
            'maxOccurs': 1
        },
        'obstacles': {
            'title': 'Obstacles',
            'description': 'Multiple obstacles that block roads and prevent routing.',
            'schema': {
                'allOf': [
                    { 'format': 'geojson-geometry' },
                    { '$ref': 'https://geojson.org/schema/MultiPolygon.json' }
                ]
            },
            'minOccurs': 0,
            'maxOccurs': 1
        }
    },
    'outputs': {
        'REM': {
            'title': 'Route Exchange Model',
            'description': 'The resulting route, encoded in Route Exchange '
                           'model format.',
            'schema': {
                'allOf': [
                    { 'format': 'geojson-feature-collection' },
                    { '$ref': 'https://geojson.org/schema/FeatureCollection.json' }
                ]
            }
        }
    },
    'example': {
        'inputs': {
            'name': 'San Diego sample route',
            'waypoints' : {
                'value' : {
                    'type' : 'MultiPoint',
                    'coordinates' : [
                       [ -117.157431, 32.714538 ],
                       [ -117.157440, 32.717815 ]
                    ]
               }
            },
            'preference' : 'fastest'
        }
    }
}

class RoutesProcessor(BaseProcessor):

    def __init__(self, processor_def):
        """
        Initialize object

        :param processor_def: provider definition

        :returns: pygeoapi.process.routes.RoutesProcessor
        """

        super().__init__(processor_def, PROCESS_METADATA)
        
        self.undefined_name = "Unnamed route"
        self.path = processor_def['path']
        self.url = ""
        self.f_json = ""

        self.preferences = processor_def['preferences']
        PROCESS_METADATA['inputs']['preference']['schema']['enum'] = \
            processor_def['preferences']
        
        self.modes = processor_def['modes']
        PROCESS_METADATA['inputs']['mode']['schema']['enum'] = \
            processor_def['modes']

        self.engine_type = processor_def['engine']['type']
        if self.engine_type == 'pgRouting':
            self.engine_conn = processor_def['engine']['connection']
            self.ways_id = processor_def['engine']['table']['ways_id']
            self.geom = processor_def['engine']['table'].get('geom_field', 'geom')
            self.search_buffer = processor_def['engine']['search_buffer']

        return
            
    def get_metadata(self, server_url, f_json):
        """
        Gets metadata used in route generation and formatting

        :param server_url: server URL
        :param f_json: JSON content type, defined in api.py
        """
        
        self.url = server_url
        self.f_json = f_json

        return

    def fetch_node_nearby(self, coordinates):
        """
        Search for the closest node, within self.search_buffer (in degrees)

        :param coordinates: input coordinates

        :returns: [ node ID, longitude, latitude, distance ]
        """
        
        with pgRoutingConnection(self.engine_conn, "", context="routes") as db:
            cursor = db.conn.cursor()

            node_buffer_clause = SQL("""{} && 
                ST_Buffer('POINT({})', {})""").format(
                Identifier(self.geom), SQL(' ').join(
                [Literal(coordinate) for coordinate in coordinates]),
                Literal(self.search_buffer))
            distance_var = SQL("""ST_Distance({},
                'SRID=4326;POINT({})') AS dist""").format(
                Identifier(self.geom), SQL(' ').join(
                [Literal(coordinate) for coordinate in coordinates]))
            sql_query = SQL("""SELECT id, lon, lat, {}
                FROM ways_vertices_pgr WHERE {}
                ORDER BY dist LIMIT 1;""").format(distance_var, node_buffer_clause)

            cursor.execute(sql_query)                              
            node = cursor.fetchone()
            
        return node

    def create_join_query(self, route_def):
        """
        Create the SQL part for the table join query
        This affects performance; it should be done only if needed

        :param route_def: route definition

        :returns: join_query
        """
        
        # Need to join osm_ways table if height or weight limits requested
        height_limit = route_def.get('height')
        weight_limit = route_def.get('weight')
        if height_limit is None and weight_limit is None:
            return SQL('')
        else:
            return SQL('INNER JOIN osm_ways ON (osm_ways.osm_id = w.osm_id)')

    def create_cost_query(self, route_def):
        """
        Create the SQL part for the cost query

        :param route_def: route definition

        :returns: cost_query
        """

        # Default preference will be the first in settings
        preference = self.preferences[0]
        requested_preference = route_def.get('preference')

        # If preference requested and in settings
        if requested_preference in self.preferences:
            preference = route_def['preference']

        # Add or modify preference definitions at will
        if preference == 'shortest':
            cost_query = SQL('w.cost AS cost, w.reverse_cost AS reverse_cost')
        elif preference == 'fastest':
            cost_query = SQL('w.cost_s AS cost, w.reverse_cost_s AS reverse_cost')
        else:
            cost_query = SQL('')

        return cost_query

    def create_height_query(self, route_def):
        """
        Create the SQL part for the height query

        :param route_def: route definition

        :returns: height_query
        """

        height_limit = route_def.get('height')
        if height_limit is None:
            return SQL('')
        else:
            return SQL("""((osm_ways.tags->''maxheight'' is NULL) OR 
                (CAST(osm_ways.tags->''maxheight'' AS DECIMAL) > {}))
                AND""").format(Literal(height_limit))

    def create_weight_query(self, route_def):
        """
        Create the SQL part for the weight query

        :param route_def: route definition

        :returns: weight_query
        """

        weight_limit = route_def.get('weight')
        if weight_limit is None:
            return SQL('')
        else:
            return SQL("""((osm_ways.tags->''maxweight'' is NULL) OR 
                (CAST(osm_ways.tags->''maxweight'' AS DECIMAL) > {}))
                AND""").format(Literal(weight_limit))

    def create_obstacles_query(self, route_def):
        """
        Create the SQL part for the obstacles query

        :param route_def: route definition

        :returns: obstacles_query
        """

        obstacles = route_def.get('obstacles')
        if obstacles is None or 'value' not in obstacles:
            return SQL('')
        else:
            return SQL("""NOT(w.the_geom && 
                ST_GeomFromGeoJSON(''{}'')) AND""").format( \
                SQL(json.dumps(obstacles["value"]).replace("'", '"')))

    def create_optimization_query(self, orig_coords, dest_coords):
        """
        Create the SQL part to minimize graph size and optimize performance

        :param orig_coords: orig coordinates
        :param dest_coords: dest coordinates

        :returns: optimization_query
        """

        opt_query = SQL("""(w.the_geom && ST_Buffer(''LINESTRING({}, 
                    {})'', {}))""").format(SQL(' ').join(
                    [Literal(orig_coord) for orig_coord in orig_coords]),
                    SQL(' ').join(
                    [Literal(dest_coord) for dest_coord in dest_coords]),
                    Literal(10 * self.search_buffer))

        return opt_query

    def calculate_route_pgrouting(self, route_def):
        """
        Calculate the route using pgRouting engine

        :param route_def: route definition

        :returns: route sequence, orig node coords, dest node coords
        """
        route_seq = []
        orig_coordinates, dest_coordinates, waypoint_sequence = None, None, 0

        way_coords = route_def['waypoints']['value']['coordinates']
        for waypoint in way_coords:
            waypoint_sequence += 1
            if orig_coordinates is None:
                orig_coordinates, orig_node_id, dest_node_id = waypoint, None, None
            else:
                dest_coordinates = waypoint

                if orig_node_id is None:
                    orig_node = self.fetch_node_nearby(orig_coordinates)
                    if orig_node is None:
                        LOGGER.debug("Origin node not found")
                        raise ProcessorCannotComputeError('Origin node not found')
                    else:
                        LOGGER.debug("Orig node:", orig_node)
                        [ orig_node_id, orig_lon, orig_lat, d ] = orig_node
                dest_node = self.fetch_node_nearby(dest_coordinates)
                if dest_node is None:
                    LOGGER.debug("Destination node not found")
                    raise ProcessorCannotComputeError('Destination node not found')
                else:
                    LOGGER.debug("Dest node:", dest_node)
                    [ dest_node_id, dest_lon, dest_lat, d ] = dest_node

                join_query = self.create_join_query(route_def)
                cost_query = self.create_cost_query(route_def)
                height_query = self.create_height_query(route_def)
                weight_query = self.create_weight_query(route_def)
                obstacles_query = self.create_obstacles_query(route_def)
                optimization_query = self.create_optimization_query( \
                    orig_coordinates, dest_coordinates)

                with pgRoutingConnection(self.engine_conn, "",
                     context="routes") as db:
                    cursor = db.conn.cursor()
                    
                    # Using bidirectional Dijkstra as the routing algorithm
                    # pgr_bdDijkstra(edges_sql, start_id, end_id  [, directed])
                    edges_sql = SQL("""'SELECT w.{} AS id, w.source, w.target,
                        {} FROM ways AS w {} WHERE {} {} {} {}'""").format(
                        Identifier(self.ways_id), cost_query,
                        join_query, height_query, weight_query,
                        obstacles_query, optimization_query)
                    sql_query = SQL("""SELECT * FROM pgr_bdDijkstra({}, {}, {},
                        directed := true);""").format(edges_sql,
                        Literal(orig_node_id), Literal(dest_node_id))
                    cursor.execute(sql_query)
                    route_segment_sql = cursor.fetchall()

                # Avoid duplicating intermediate waypoints in sequence
                if waypoint_sequence < len(way_coords): route_segment_sql.pop()
                route_seq += route_segment_sql

                orig_coordinates = dest_coordinates
                orig_node_id, dest_coordinates = dest_node_id, None

        # Return the real coordinates used in route generation
        if len(route_seq) > 0:
            orig_lat = float(orig_lat)
            orig_lon = float(orig_lon)
            dest_lat = float(dest_lat)
            dest_lon = float(dest_lon)
            return route_seq, [orig_lon, orig_lat], [dest_lon, dest_lat]
        else:
            LOGGER.debug("Nodes ok but no route found")
            raise ProcessorCannotComputeError('A route was not found from origin to destination')

    def calculate_route(self, route_def):
        """
        Calculate the route calling the appropriate engine

        :param route_def: route definition

        :returns: route sequence, orig node coords, dest node coords
        """
        if self.engine_type == 'pgRouting':
            return self.calculate_route_pgrouting(route_def)
        else:
            return None, None, None

    def format_route(self, route_seq, orig_coords, dest_coords, route_def, route_id):
        """
        Format the resulting route output in Route Exchange Model format

        :param route_seq: sequences of nodes of the optimal route
        :param orig_coords: coordinates of the origin node
        :param dest_coords: coordinates of the destination node
        :param route_def: route definition as requested

        :returns: route_output
        """

        # Fetch all data from database at once
        list_of_edges = tuple([ route_step[3] for route_step in route_seq ])
        with pgRoutingConnection(self.engine_conn, "", context='routes') as db:
            cursor = db.conn.cursor()
            # Fetch edge's info and last point coordinate
            sql_query = SQL("""SELECT gid, length_m, cost_s, reverse_cost_s,
                               name, source, target, x1, y1, x2, y2 FROM ways
                               WHERE gid IN ({});""").format(SQL(', ').join(
                               [Literal(edge_id) for edge_id in list_of_edges]))
            cursor.execute(sql_query)
            edge_info = cursor.fetchall()
            edge_info_dict = { i[0] : i[1:] for i in edge_info }

            # Fetch segment's full coordinate list
            sql_query = SQL("""SELECT gid,
                array_agg(ARRAY[ST_X((dp).geom), ST_Y((dp).geom)])
                FROM (SELECT gid, ST_DumpPoints(the_geom) AS dp FROM ways
                WHERE gid IN ({})) AS edgepoints GROUP BY gid;
                """).format(SQL(', ').join(
                [Literal(edge_id) for edge_id in list_of_edges]))
            cursor.execute(sql_query)
            edge_points = cursor.fetchall()
            edge_points_dict = { i[0] : i[1:][0] for i in edge_points }

        route_output = {
            'type': 'FeatureCollection',
            'name': '',
            'links': [],
            'features': []
        }

        route_output['links'].append({
            'type': self.f_json,
            'rel': 'self',
            'title': 'this route',
            'href': '{}/routes/{}'.format(self.url, route_id)
        })
        route_output['links'].append({
            'type': self.f_json,
            'rel': 'describedby',
            'title': 'the definition for this route',
            'href': '{}/routes/{}/definition'.format(self.url, route_id)
        })

        # TODO: get the units from configuration
        speedLimitUnit = 'kph'  # kph or mph
        route_output['name'] = route_def.get('name', self.undefined_name)

        # Format route overview
        route_overview = {}
        route_overview['type'] = 'Feature'
        route_overview['id'] = 1
        route_overview['geometry'] = {}
        route_overview['geometry']['type'] = 'LineString'
        route_overview['geometry']['coordinates'] = []
        route_overview['properties'] = {}
        route_overview['properties']['type'] = 'route overview'
        route_overview['properties']['length_m'] = 0.0
        route_overview['properties']['duration_s'] = 0.0
        route_output['features'].append(route_overview)

        # Format start point
        start_point = {}
        start_point['type'] = 'Feature'
        start_point['id'] = route_output['features'][-1]['id'] + 1
        start_point['geometry'] = {}
        start_point['geometry']['type'] = 'Point'
        start_point['geometry']['coordinates'] = orig_coords
        start_point['properties'] = {}
        start_point['properties']['type'] = 'start'
        route_output['features'].append(start_point)
        prev_node = route_seq[0][1] # Source node of the first segment
        segment = None
        prev_edge_name = None

        for route_step in route_seq:
            # End point has no edge (value == -1)
            if route_step[3] == -1:
                # Format end point
                end_point = {}
                end_point['type'] = 'Feature'
                end_point['id'] = route_output['features'][-1]['id'] + 1
                end_point['geometry'] = {}
                end_point['geometry']['type'] = 'Point'
                end_point['geometry']['coordinates'] = dest_coords
                # Add last point coordinates in overview
                route_output['features'][0]['geometry']['coordinates'].append(
                    end_point['geometry']['coordinates'])
                end_point['properties'] = {}
                end_point['properties']['type'] = 'end'

                # Append last segment and end point
                segment['properties']['length_m'] = \
                    round(segment['properties']['length_m'], 2)
                segment['properties']['duration_s'] = \
                    round(segment['properties']['duration_s'], 2)
                route_output['features'].append(segment)
                route_output['features'].append(end_point)
            else:
                edge_id = route_step[3]
                edge_length = edge_info_dict[edge_id][0]
                edge_name = edge_info_dict[edge_id][3]
                edge_source = edge_info_dict[edge_id][4]
                edge_target = edge_info_dict[edge_id][5]
                
                if route_step[2] == edge_source:
                    # Proper direction
                    edge_duration = edge_info_dict[edge_id][1]
                    segment_coordinates = [
                        round(edge_info_dict[edge_id][8], 6),
                        round(edge_info_dict[edge_id][9], 6) ]
                else:
                    # Reverse direction
                    edge_duration = edge_info_dict[edge_id][2]
                    segment_coordinates = [
                        round(edge_info_dict[edge_id][6], 6),
                        round(edge_info_dict[edge_id][7], 6) ]
                    edge_points_dict[edge_id].reverse()

                # Update route total length and duration
                route_output["features"][0]["properties"]["length_m"] += \
                    edge_length
                route_output["features"][0]["properties"]["duration_s"] += \
                    edge_duration

                # Avoid last point duplication
                edge_points_dict[edge_id].pop(-1)

                for edge_point in edge_points_dict[edge_id]:
                    route_output['features'][0]['geometry']['coordinates'].append([
                        round(edge_point[0], 6),
                        round(edge_point[1], 6) ])

                # Group all edges with the same name
                if edge_name is not None and edge_name == prev_edge_name:
                    segment['geometry']['coordinates'] = segment_coordinates
                    segment['properties']['length_m'] += edge_length
                    segment['properties']['duration_s'] += edge_duration
                # Append segment and create new one, if diff name
                else:
                    if segment is not None:
                        segment['properties']['length_m'] = \
                            round(segment['properties']['length_m'], 2)
                        segment['properties']['duration_s'] = \
                            round(segment['properties']['duration_s'], 2)
                        route_output["features"].append(segment)
                    prev_edge_name = edge_name
                    # Format route segment
                    segment = {}
                    segment['type'] = 'Feature'
                    segment['id'] = route_output['features'][-1]['id'] + 1
                    segment['geometry'] = {}
                    segment['geometry']['type'] = 'Point'
                    segment['geometry']['coordinates'] = segment_coordinates
                    segment['properties'] = {}
                    segment['properties']['type'] = 'segment'
                    if edge_name is not None:
                        segment['properties']['roadName'] = edge_name
                    segment['properties']['length_m'] = edge_length
                    segment['properties']['duration_s'] = edge_duration

        route_output["features"][0]["properties"]["length_m"] = \
            round(route_output["features"][0]["properties"]["length_m"], 2)
        route_output["features"][0]["properties"]["duration_s"] = \
            round(route_output["features"][0]["properties"]["duration_s"], 2)

        return route_output
        
    def get_route_id(self, route_def):
        """
        Get a unique id for this route.
        If the name of the route exists in the saved routes, then use the same
        route id of the stored route. Otherwise, create a new one.

        :param route_def: route definition as requested

        :returns: route_id
        """
        
        route_req_name = route_def.get('name', self.undefined_name)
        # Use undefined_name if requested route name is empty
        if route_req_name == '':
            route_req_name = self.undefined_name
        
        route_id = None
        for item in os.listdir(self.path):
            # Item must be a file with .json extension
            if os.path.isfile(os.path.join(self.path, item)) and \
                item.endswith('.json'):
                
                filename = '{}/{}'.format(self.path, item)
                with open(filename, 'r+') as f:
                    route_content = json.load(f)
                route_std_name = route_content.get('name', self.undefined_name)
                # Use undefined_name if stored route name is empty
                if route_std_name == '':
                    route_std_name = self.undefined_name
                # Stored route name is the same as requested route name
                if route_std_name == route_req_name:
                    route_id = item.replace('.json', '')
                    break

        # Route name not found amongst the saved routes. Create a random id
        if route_id is None:
            route_id = str(uuid.uuid1())
        
        return route_id

    def get_routes(self, bbox, requested_html):
        """
        Get a list of stored routes.
        If the requested format is HTML, provide extent information.

        :param bbox: bbox extent set in routes configuration
        :param requested_html: whether the requested format is HTML

        :returns: route_list
        """

        routes_list = {}
        routes_list['links'] = []
        routes_list['links'].append({
            'type': self.f_json,
            'rel': 'self',
            'title': 'this document',
            'href': '{}/routes'.format(self.url)
        })
        
        # If requested format is HTML add summary and extent information
        if requested_html:
            routes_list['routes'] = []
            if not isinstance(bbox[0], list):
                bbox = [bbox]
            routes_list['extent'] = {
                'spatial': {
                    'bbox': bbox
                }
            }
        
        for item in os.listdir(self.path):
            if os.path.isfile(os.path.join(self.path, item)) and \
                item.endswith('.json'):
                route_id = item.replace('.json', '')
                filename = '{}/{}'.format(self.path, item)
                with open(filename, 'r+') as f:
                    route_content = json.load(f)

                route_name = route_content.get('name', self.undefined_name)
                routes_list['links'].append({
                    'type': self.f_json,
                    'rel': 'item',
                    'title': route_name,
                    'href': '{}/routes/{}'.format(self.url, route_id)
                    })

                if requested_html:
                    routes_list['routes'].append({
                        'title': route_name,
                        'href': '{}/routes/{}'.format(self.url, route_id),
                        'routeid': route_id,
                        'description': "Length: {} m. Duration: {} s.".format(
                            str(round(route_content['features'][0]['properties']['length_m'])),
                            str(round(route_content['features'][0]['properties']['duration_s'])))
                        })

        return routes_list

    def get_route(self, route_id):
        """
        Get stored route.

        :param route_id: route unique identifier

        :returns: route
        """
        filename = '{}/{}.json'.format(self.path, route_id)
        if os.path.isfile(filename):
            with open(filename, 'r+') as f:
                route = json.load(f)
        else:
            raise ProcessorItemNotFoundError('Route not found.')
        route['name'] = route.get('name', self.undefined_name)

        return route

    def get_route_def(self, route_id):
        """
        Get stored route defintion.

        :param route_id: route unique identifier

        :returns: route_def
        """
        filename = '{}/routedefs/{}.json'.format(self.path, route_id)
        if os.path.isfile(filename):
            with open(filename, 'r+') as f:
                routedef = json.load(f)
        else:
            raise ProcessorItemNotFoundError('Route definition not found.')
            
        return routedef

    def del_route(self, route_id):
        """
        Delete stored route.

        :param route_id: route unique identifier
        """
        route_f = '{}/{}.json'.format(self.path, route_id)
        if os.path.isfile(route_f):
            os.remove(route_f)
        routedef_f = '{}/routedefs/{}.json'.format(self.path, route_id)
        if os.path.isfile(routedef_f):
            os.remove(routedef_f)

        return

    def store_route(self, route_id, route_def, route):
        """
        Store a route and its definition.

        :param route_id: the unique id of a route
        :param route_def: the definition of a route
        :param route: the generated route
        """
        
        filename = '{}/{}.json'.format(self.path, route_id)
        with open(filename, 'w+', encoding='utf8') as f:
            json.dump(route, f, indent=4)
        def_filename = '{}/routedefs/{}.json'.format(self.path, route_id)
        with open(def_filename, 'w+', encoding='utf8') as df:
            json.dump(route_def, df, indent=4)

        return

    def execute(self, route_def):

        route_id = self.get_route_id(route_def)

        mimetype = 'application/json'
        waypoints = route_def.get('waypoints')
        if waypoints is None:
            raise ProcessorExecuteError('Cannot generate a route without waypoints')
        if 'value' not in waypoints or 'coordinates' \
            not in waypoints['value']:
            raise ProcessorExecuteError('Waypoints not properly formed')
        way_coords = waypoints['value']['coordinates']
        if not isinstance(way_coords, list) or len(way_coords) < 2:
            raise ProcessorExecuteError('Need at least two waypoints to generate a route')

        start_time = time.time()
        route_seq, orig_coords, dest_coords = self.calculate_route(route_def)
        LOGGER.debug("ROUTE CALCULATED --- %s seconds ---" % (time.time() - start_time))
        LOGGER.debug("TOTAL EDGE SEQUENCE: ", len(route_seq))

        if len(route_seq) == 0:
            raise ProcessorExecuteError('Route not able to compute')

        formatted_route = self.format_route(route_seq, orig_coords,
                dest_coords, route_def, route_id)

        LOGGER.debug("ROUTE FORMATTED --- %s seconds ---" % (time.time() - start_time))
        
        saving_process = threading.Thread(target=self.store_route, \
            args=(route_id, route_def, formatted_route))
        saving_process.start()
        
        return mimetype, formatted_route

    def __repr__(self):
        return '<RoutesProcessor> {}'.format(self.name)

