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

# Needs to be run like: python3 -m pytest
# Needs an operational pgRouting instance in local with OSM dataset
# of District of Columbia

import pytest

from pygeoapi.process.base import ProcessorItemNotFoundError
from pygeoapi.plugin import load_plugin
from pygeoapi.util import JobStatus

import uuid
import os
PASSWORD = os.environ.get('POSTGRESQL_PASSWORD', 'postgres')


@pytest.fixture()
def config():
    return {
        'name': 'Routes',
        'path': '/tmp',
        'engine': {
            'type': 'pgRouting',
            'connection': {
                'host': '127.0.0.1',
                'dbname': 'district-of-columbia',
                'user': 'postgres',
                'password': PASSWORD,
                'search_path': ['public']
            },
            'table': {
                'ways_id': 'gid',
                'geom_field': 'the_geom'
            },
            'search_buffer': 0.01
        },
        'preferences': ['fastest', 'shortest'],
        'modes': ['vehicle'],
        'units': {
            'speed': 'mph'
        },
        'rel_link': 'http://localhost:5000',
        'intralink': True
    }


@pytest.fixture()
def route_def():
    return {
        'inputs': {
            'name': 'pytest',
            'waypoints': {
                'value': {
                    'type': 'MultiPoint',
                    'coordinates': [
                        [-77.012034, 38.890563],
                        [-77.033604, 38.899064]
                    ]
                }
            },
            'preference': 'fastest'
        }
    }


@pytest.fixture()
def wrong_route_def(route_def):
    wrong_route_def_ = route_def.copy()
    wrong_route_def_['inputs']['waypoints']['value']['coordinates'][0][0] = -70.012034  # noqa
    return wrong_route_def_


@pytest.fixture()
def bbox():
    return [-77.1177422, 38.7924177, -76.9076054, 38.994505]


def test_generate_route(config, route_def):
    manager = load_plugin('process_manager', {'name': 'Dummy',
                          'connection': None, 'output_dir': None})
    routing_process = load_plugin('routes', config)

    route_req = route_def['inputs']
    is_async = False
    job_id = str(uuid.uuid1())
    mime_type, outputs, status = manager.execute_process(
            routing_process, job_id, route_req, is_async)

    assert status == JobStatus.successful
    assert outputs.get('type') == 'FeatureCollection'
    assert outputs.get('name') == route_req['name']

    links = outputs.get('links')
    assert links is not None
    assert len(links) >= 2
    link_rels = [i['rel'] for i in links]
    assert 'self' in link_rels
    assert 'describedby' in link_rels

    route_features = outputs.get('features')
    assert route_features is not None

    route_overiew = route_features[0]
    ro_geometry = route_overiew.get('geometry')
    assert ro_geometry is not None
    assert ro_geometry.get('type') == 'LineString'
    assert len(ro_geometry.get('coordinates', [])) >= 2
    ro_properties = route_overiew.get('properties')
    assert ro_properties is not None
    assert ro_properties.get('type') == 'route overview'
    assert ro_properties.get('length_m', 0.0) > 0.0
    assert ro_properties.get('duration_s', 0.0) > 0.0

    route_start = route_features[1]
    s_geometry = route_start.get('geometry')
    assert s_geometry is not None
    assert s_geometry.get('type') == 'Point'
    assert len(s_geometry.get('coordinates', [])) in [2, 3]
    s_properties = route_start.get('properties')
    assert s_properties is not None
    assert s_properties.get('type') == 'start'

    route_segment = route_features[2]
    sg_geometry = route_segment.get('geometry')
    assert sg_geometry is not None
    assert sg_geometry.get('type') == 'Point'
    assert len(sg_geometry.get('coordinates', [])) in [2, 3]
    sg_properties = route_segment.get('properties')
    assert sg_properties is not None
    assert sg_properties.get('type') == 'segment'
    assert sg_properties.get('length_m') is not None
    assert sg_properties.get('duration_s') is not None

    route_end = route_features[-1]
    e_geometry = route_end.get('geometry')
    assert e_geometry is not None
    assert e_geometry.get('type') == 'Point'
    assert len(e_geometry.get('coordinates', [])) in [2, 3]
    e_properties = route_end.get('properties')
    assert e_properties is not None
    assert e_properties.get('type') == 'end'


def test_get_routes(config, bbox):
    routing_process = load_plugin('routes', config)
    routes = routing_process.get_routes(bbox, False)
    links = routes.get('links', [])
    assert len(links) > 0

    link_rels = [i['rel'] for i in links]
    assert 'self' in link_rels
    assert 'item' in link_rels


def test_get_route(config):
    routing_process = load_plugin('routes', config)
    routes = routing_process.get_routes(bbox, False)
    links = routes.get('links', [])
    route_id = None
    for link in links:
        if link['rel'] == 'item':
            route_id = link['href'].split('/')[-1]
            break
    assert route_id is not None
    route = routing_process.get_route(route_id)
    assert route.get('type') == 'FeatureCollection'
    assert route.get('name') is not None

    route_links = route.get('links')
    assert route_links is not None

    route_features = route.get('features')
    assert route_features is not None
    route_overiew = route_features[0]
    ro_geometry = route_overiew.get('geometry')
    assert ro_geometry is not None
    assert ro_geometry.get('type') == 'LineString'
    ro_properties = route_overiew.get('properties')
    assert ro_properties is not None
    assert ro_properties.get('type') == 'route overview'
    route_start = route_features[1]
    s_geometry = route_start.get('geometry')
    assert s_geometry is not None
    assert s_geometry.get('type') == 'Point'
    s_properties = route_start.get('properties')
    assert s_properties is not None
    assert s_properties.get('type') == 'start'
    route_segment = route_features[2]
    sg_geometry = route_segment.get('geometry')
    assert sg_geometry is not None
    assert sg_geometry.get('type') == 'Point'
    sg_properties = route_segment.get('properties')
    assert sg_properties is not None
    assert sg_properties.get('type') == 'segment'
    route_end = route_features[-1]
    e_geometry = route_end.get('geometry')
    assert e_geometry is not None
    assert e_geometry.get('type') == 'Point'
    e_properties = route_end.get('properties')
    assert e_properties is not None
    assert e_properties.get('type') == 'end'


def test_get_route_def(config):
    routing_process = load_plugin('routes', config)
    routes = routing_process.get_routes(bbox, False)
    links = routes.get('links', [])
    route_id = None
    for link in links:
        if link['rel'] == 'item':
            route_id = link['href'].split('/')[-1]
            break
    assert route_id is not None
    route_def = routing_process.get_route_def(route_id)
    assert route_def is not None
    assert route_def.get('name') is not None
    waypoints = route_def.get('waypoints')
    assert waypoints is not None
    waypoints_v = waypoints.get('value')
    assert waypoints_v is not None
    assert waypoints_v.get('type') == 'MultiPoint'
    assert len(waypoints_v.get('coordinates', [])) >= 2


def test_delete_route(config):
    routing_process = load_plugin('routes', config)
    routes = routing_process.get_routes(bbox, False)
    links = routes.get('links', [])
    route_id = None
    for link in links:
        if link['rel'] == 'item':
            route_id = link['href'].split('/')[-1]
            break
    assert route_id is not None
    routing_process.del_route(route_id)
    assert not os.path.exists('{}/{}'.format(config['path'], route_id))
    assert not os.path.exists(
        '{}/routedefs/{}'.format(config['path'], route_id))


def test_get_nonexistent_route(config):
    routing_process = load_plugin('routes', config)
    with pytest.raises(ProcessorItemNotFoundError):
        _ = routing_process.get_route('nonexistent-id')


def test_generate_outofboundaries_route(config, wrong_route_def):
    manager = load_plugin('process_manager', {'name': 'Dummy',
                          'connection': None, 'output_dir': None})
    routing_process = load_plugin('routes', config)
    route_req = wrong_route_def['inputs']
    is_async = False
    job_id = str(uuid.uuid1())
    mime_type, outputs, status = manager.execute_process(
        routing_process, job_id, route_req, is_async)
    assert status == JobStatus.failed
    assert outputs['code'] == 'NotAbleToCompute'
