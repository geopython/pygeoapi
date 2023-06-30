# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Mathieu Tachon <tachon.mathieu@protonmail.com>
#
# Copyright (c) 2022 Tom Kralidis
# Copyright (c) 2023 Mathieu Tachon
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


from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


# Enum of data schema types depending on request action
class SchemaType(Enum):
    item = 'item'
    create = 'create'
    update = 'update'
    replace = 'replace'


# Enum of valid GeoJSON geometry types
class GeomType(Enum):
    point = 'Point'
    linestring = 'LineString'
    polygon = 'Polygon'
    multipoint = 'MultiPoint'
    multilinestring = 'MultiLineString'
    multipolygon = 'MultiPolygon'
    geometrycollection = 'GeometryCollection'


# Records defining GeoJSON properties
@dataclass
class GeoJSONProperty:
    name: str
    type: str
    nullable: bool
    required: bool

    def to_schema(self) -> dict:
        if self.nullable:
            return {'oneOf': [{'type': None}, {'type': self.type}]}
        else:
            return {'type': self.type}


def get_geometry_schema(
    geom_type: GeomType, geom_nullable: bool = True, n_dims: int = 2,
) -> dict:
    """Get JSON schema of GeoJSON geometry.

    :param geom_type: type of GeoJSON geometry.
    :type geom_type: `GeomType`
    :param geom_nullable: whether the geometry of the GeoJSON feature can be
        set to 'null'.
    :type geom_nullable: bool
    :param n_dims: number of dimensions of the geometry's coordinates.
    :type n_dims: int

    :returns: JSON schema of geometry.
    :rtype: dict
    """
    # Common for all GeoJSON geometries
    geom_schema = {
        'type': 'object',
        'properties': {
            'bbox': {
                'type': 'array',
                'items': {'type': 'number'},
                'minItems': 2 * n_dims,
                'maxItems': 2 * n_dims,
            },
        },
        'required': ['type']
    }
    properties = geom_schema['properties']
    required = geom_schema['required']

    # For 'GeometryCollection', call function recursively with all other
    # geometry types
    if geom_type == GeomType.geometrycollection:
        properties['type'] = {'const': 'GeometryCollection'}
        required.append('geometries')
        properties['geometries'] = {
            'type': 'array',
            'items': {
                'oneOf': [
                    get_geometry_schema(gt, geom_nullable=False, n_dims=n_dims)
                    for gt in GeomType if gt != GeomType.geometrycollection
                ],
            }
        }
        if geom_nullable:
            return {'oneOf': [{'type': None}, geom_schema]}
        return geom_schema
    # Geometry type different from 'GeometryCollection'
    required.append('coordinates')
    pt_coords = {
        'type': 'array',
        'items': {'type': 'number'},
        'minItems': n_dims,
        'maxItems': n_dims,
    }
    ls_coords = {
        'type': 'array',
        'items': pt_coords,
        'minItems': 2,
    }
    poly_coords = {
        'type': 'array',
        'items': {
            'type': 'array',
            'items': pt_coords,
            'minItems': 4,
        },
    }
    if geom_type == GeomType.point:
        properties['type'] = {'const': 'Point'}
        properties['coordinates'] = pt_coords
    elif geom_type == GeomType.linestring:
        properties['type'] = {'const': 'LineString'}
        properties['coordinates'] = ls_coords
    elif geom_type == GeomType.polygon:
        properties['type'] = {'const': 'Polygon'}
        properties['coordinates'] = poly_coords
    elif geom_type == GeomType.multipoint:
        properties['type'] = {'const': 'MultiPoint'}
        properties['coordinates'] = {
            'type': 'array',
            'items': pt_coords,
        }
    elif geom_type == GeomType.multilinestring:
        properties['type'] = {'const': 'MultiLineString'}
        properties['coordinates'] = {
            'type': 'array',
            'items': ls_coords,
        }
    elif geom_type == GeomType.multipolygon:
        properties['type'] = {'const': 'MultiPolygon'}
        properties['coordinates'] = {
            'type': 'array',
            'items': poly_coords,
        }
    if geom_nullable:
        return {'oneOf': [{'type': None}, geom_schema]}
    return geom_schema


def get_geojson_schema(
    properties: Optional[List[GeoJSONProperty]] = None,
    geom_type: Optional[GeomType] = None,
    geom_nullable: bool = True,
    n_dims: int = 2,
) -> dict:
    """Get JSON schema of GeoJSON feature.

    :param properties: list of feature's properties.
    :type properties: list of `GeoJSONProperty` objects, optional
    :param geom_type: type of GeoJSON geometry.
    :type geom_type: `GeomType`, optional
    :param geom_nullable: whether the geometry of the GeoJSON feature can be
        set to 'null'.
    :type geom_nullable: bool
    :param n_dims: number of dimensions of the coordinates of the feature's
        geometry.
    :type n_dims: int

    :returns: JSON schema of feature.
    :rtype: dict

    .. note::
        If ``properties`` and/or ``geom_type`` are not given/set to `None`, a
        GeoJSON feature will only validate against the returned JSON schema if
        its 'properties' and/or 'geometry' members are set to 'null',
        respectively.
    """
    if geom_type is None:
        geometry_schema = {'type': None}
    else:
        geometry_schema = get_geometry_schema(
            geom_type, geom_nullable, n_dims=n_dims,
        )
    geojson_schema = {
        'type': 'object',
        'properties': {
            'type': {'const': 'Feature'},
            'geometry': geometry_schema,
        },
        'required': ['type', 'geometry', 'properties'],
    }
    if properties is None:
        geojson_schema['properties']['properties'] = {'type': None}
    else:
        geojson_schema['properties']['properties'] = defaultdict(list)
        properties_obj = geojson_schema['properties']['properties']
        properties_obj.update({'type': 'object', 'properties': dict()})
        for p in properties:
            properties_obj['properties'][p.name] = p.to_schema()
            if p.required:
                properties_obj['required'].append(p.name)
    return geojson_schema
