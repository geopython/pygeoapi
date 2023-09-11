# =================================================================
#
# Authors: Mathieu Tachon <tachon.mathieu@protonmail.com>
#
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


from dataclasses import dataclass
from typing import Any, List, Literal, Optional, Union

from pydantic import create_model, conint, conlist, field_validator


# Types for GeoJSON Features' geometry
GeomType = Literal[
    'Point',
    'LineString',
    'Polygon',
    'MultiPoint',
    'MultiLineString',
    'MultiPolygon',
    'GeometryCollection',
]


def linear_ring_closed(cls, coordinates):
    """Validator function that check whether a linear ring is closed or opened.
    """
    for ring in coordinates:
        assert ring[0] == ring[-1], (
            'First and and last position of linear ring must be the same'
        )
    return coordinates


def multiple_linear_rings_closed(cls, coordinates):
    """Validator function that checks for closed/opened linear rings.
    """
    for poly in coordinates:
        linear_ring_closed(cls, poly)
    return coordinates


def create_GeoJSONGeometry_model(geom_type: GeomType, n_dims: conint(gt=1)):
    """ Create a pydantic model for a GeoJSON Geometry.

    Generic function that creates dynamically a pydantic model for a GeoJSON
    Geometry, based on a geometry type and a N number of coordinate dimensions.

    :param geom_type: type of GeoJSON geometry.
    :type geom_type: `GeomType`
    :param n_dims: number of dimensions of the GeoJSON Geometry's
    coordinates. Must be larger than 1.
    :type n_dims: int

    :returns: pydantic model of GeoJSON Geometry
    :rtype: subclass of `pydantic.BaseModel`
    """
    validators = dict()
    bbox_type = conlist(
        item_type=float,
        min_length=2 * n_dims,
        max_length=2 * n_dims,
    )
    pt_coords = conlist(item_type=float, min_length=n_dims, max_length=n_dims)
    ls_coords = conlist(item_type=pt_coords, min_length=2)
    poly_coords = conlist(
        item_type=conlist(item_type=pt_coords, min_length=4),
        min_length=1,
    )
    if geom_type == 'Point':
        coordinates_type = pt_coords
    elif geom_type == 'LineString':
        coordinates_type = ls_coords
    elif geom_type == 'Polygon':
        validators['polygon_coords_validator'] = field_validator('coordinates')(linear_ring_closed)  # noqa
        coordinates_type = poly_coords
    elif geom_type == 'MultiPoint':
        coordinates_type = conlist(item_type=pt_coords, min_length=1)
    elif geom_type == 'MultiLineString':
        coordinates_type = conlist(item_type=ls_coords, min_length=1)
    elif geom_type == 'MultiPolygon':
        validators['multipolygon_coords_validator'] = field_validator('coordinates')(multiple_linear_rings_closed)  # noqa
        coordinates_type = conlist(item_type=poly_coords, min_length=1)
    elif geom_type == 'GeometryCollection':
        geom_type_models = list()
        for gt in (
            'Point',
            'LineString',
            'Polygon',
            'MultiPoint',
            'MultiLineString',
            'MultiPolygon',
        ):
            geom_type_models.append(create_GeoJSONGeometry_model(gt, n_dims))
        return create_model(
            f'GeoJSON{geom_type}',
            type=(Literal[geom_type], ...),
            geometries=(Union[tuple(geom_type_models)], ...),
            bbox=(bbox_type, Optional),
        )
    return create_model(
        f'GeoJSON{geom_type}',
        type=(Literal[geom_type], ...),
        coordinates=(coordinates_type, ...),
        bbox=(bbox_type, Optional),
        __validators__=validators,
    )


# Records defining GeoJSON properties
@dataclass
class GeoJSONProperty:
    name: str
    dtype: Any  # must be JSON serializable
    nullable: bool
    required: bool


def create_GeoJSONFeature_model(
    properties: Optional[List[GeoJSONProperty]] = None,
    geom_type: Optional[GeomType] = None,
    geom_nullable: bool = True,
    n_dims: conint(gt=1) = 2,
):
    """ Create a pydantic model for a GeoJSON Feature.

    Generic function that creates dynamically a pydantic model for a GeoJSON
    Feature, based on a list of properties, a geometry type and a N number of
    coordinate dimensions.

    :param properties: list of feature's properties.
    :type properties: list of `GeoJSONProperty` objects, optional
    :param geom_type: type of GeoJSON geometry.
    :type geom_type: `GeomType`, optional
    :param geom_nullable: whether the geometry of the GeoJSON Feature can be
        set to 'null'.
    :type geom_nullable: bool, default: True
    :param n_dims: number of dimensions of the coordinates of the feature's
        geometry. Must be larger than 1.
    :type n_dims: int, default: 2

    :returns: pydantic model of GeoJSON Feature
    :rtype: subclass of `pydantic.BaseModel`

    .. note::
        If ``properties`` and/or ``geom_type`` are not given/set to `None`, a
        GeoJSON Feature object will only validate against the returned GeoJSON
        Feature model if its 'properties' and/or 'geometry' members are set to
        'null', respectively.
    """
    bbox_type = conlist(
        item_type=float,
        min_length=2 * n_dims,
        max_length=2 * n_dims,
    )
    if geom_type is None:
        geom_field_def = (Optional[None], ...)
    elif geom_nullable:
        geojson_geom_model = create_GeoJSONGeometry_model(geom_type, n_dims)
        geom_field_def = (Optional[geojson_geom_model], ...)
    else:
        geom_field_def = (create_GeoJSONGeometry_model(geom_type, n_dims), ...)
    if properties is None:
        properties_field_def = (Optional[None], ...)
    else:
        property_fields_def = dict()
        for prop in properties:
            if prop.nullable:
                data_type = Optional[prop.dtype]
            else:
                data_type = prop.dtype
            if prop.required:
                default = ...
            else:
                default = Optional
            property_fields_def[prop.name] = (data_type, default)
        properties_model = create_model(
            'FeaturePropertiesSchema', **property_fields_def,
        )
        properties_field_def = (properties_model, ...)
    return create_model(
        'GeoJSONFeature',
        type=(Literal['Feature'], ...),
        id=(Union[str, float], Optional),
        geometry=geom_field_def,
        properties=properties_field_def,
        bbox=(bbox_type, Optional),
    )


def create_GeoJSONFeatureCollection_model(
    properties: Optional[List[GeoJSONProperty]] = None,
    geom_type: Optional[GeomType] = None,
    geom_nullable: bool = True,
    n_dims: conint(gt=1) = 2,
):
    """ Create a pydantic model for a GeoJSON FeatureCollection.

    Generic function that creates dynamically a pydantic model for a GeoJSON
    FeatureCollection, based on a list of properties, a geometry type and a N
    number of coordinate dimensions.

    :param properties: list of features' properties.
    :type properties: list of `GeoJSONProperty` objects, optional
    :param geom_type: type of GeoJSON geometry.
    :type geom_type: `GeomType`, optional
    :param geom_nullable: whether the geometry of the GeoJSON Features can be
        set to 'null'.
    :type geom_nullable: bool, default: True
    :param n_dims: number of dimensions of the coordinates of the features'
        geometry. Must be larger than 1.
    :type n_dims: int, default: 2

    :returns: pydantic model of GeoJSON FeatureCollection
    :rtype: subclass of `pydantic.BaseModel`

    .. note::
        If ``properties`` and/or ``geom_type`` are not given/set to `None`, a
        GeoJSON FeatureCollection object will only validate against the
        returned GeoJSON FeatureCollection model if all Features have their
        'properties' and/or 'geometry' members set to 'null', respectively.
    """
    bbox_type = conlist(
        item_type=float,
        min_length=2 * n_dims,
        max_length=2 * n_dims,
    )
    feature_model = create_GeoJSONFeature_model(
        properties, geom_type, geom_nullable, n_dims,
    )
    return create_model(
        'GeoJSONFeatureCollection',
        type=(Literal['FeatureCollection'], ...),
        features=(List[feature_model], ...),
        bbox=(bbox_type, Optional),
    )
