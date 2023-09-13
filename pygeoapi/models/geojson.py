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
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import create_model, conint, conlist, field_validator

from pygeoapi.models.validators import (
    geometry_collection_linear_rings_closed,
    feature_linear_rings_closed,
    feature_collection_linear_rings_closed,
    format_model_field_validators,
    multipolygon_linear_rings_closed,
    polygon_linear_rings_closed,
)


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


def get_bbox_type(n_dims: conint(gt=1)):
    """ Get data type for 'bbox' field.

    :param n_dims: number of coordinate dimensions. Must be larger than 1.
    :type n_dims: int

    :returns: data type of the 'bbox'
    :rtype: `typing._AnnotatedAlias`
    """
    return conlist(
        item_type=float, min_length=2 * n_dims, max_length=2 * n_dims,
    )


def create_geojson_geometry_model(
    geom_type: GeomType,
    n_dims: conint(gt=1),
    field_validators: Optional[Dict[str, Union[callable, None]]] = None,
):
    """ Create a pydantic model for a GeoJSON Geometry.

    Generic function that creates dynamically a pydantic model for a GeoJSON
    Geometry, based on a geometry type and a N number of coordinate dimensions.

    :param geom_type: type of GeoJSON geometry.
    :type geom_type: `GeomType`
    :param n_dims: number of dimensions of the GeoJSON Geometry's
        coordinates. Must be larger than 1.
    :type n_dims: int
    :param field_validators: field validator functions. If this parameter is
        passed a value different from `None`, it must be a `dict` which keys
        are the field names of a GeoJSON Geometry to validate
        (e.g. 'coordinates'), and which values are the validator functions for
        the corresponding fields. The validator function must have a <Signature
        (cls, field_value)> signature, and return the validated field value.
    :type field_validators: `dict`

    :returns: pydantic model of GeoJSON Geometry
    :rtype: subclass of `pydantic.BaseModel`

    .. note::
        - If ``field_validators`` is not specified or set to `None`, the
          geometry model for 'Polygon' and 'MultiPolygon' geometry types will
          have default validators which ensure that linear rings in the
          'coordinates' field are closed, as per the `GeoJSON Specification
          (RFC 7946) <https://datatracker.ietf.org/doc/html/rfc7946>`_. The
          same default validation will be applied to 'Polygon' and
          'MultiPolygon' geometries inside a 'GeometryCollection'. If a
          validator function is specified for a given field, it will override
          the corresponding default validator function.
        - The value of a key-value pair of the ``field_validators`` `dict` can
          be set to `None` instead of a `callable` if one wants to deactivate
          one of the default validators.
    """
    validators = format_model_field_validators(field_validators)
    bbox_type = get_bbox_type(n_dims)
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
        if 'coordinates_validator' not in validators.keys():
            validators['coordinates_validator'] = field_validator('coordinates')(polygon_linear_rings_closed)  # noqa
        coordinates_type = poly_coords
    elif geom_type == 'MultiPoint':
        coordinates_type = conlist(item_type=pt_coords, min_length=1)
    elif geom_type == 'MultiLineString':
        coordinates_type = conlist(item_type=ls_coords, min_length=1)
    elif geom_type == 'MultiPolygon':
        if 'coordinates_validator' not in validators.keys():
            validators['coordinates_validator'] = field_validator('coordinates')(multipolygon_linear_rings_closed)  # noqa
        coordinates_type = conlist(item_type=poly_coords, min_length=1)
    elif geom_type == 'GeometryCollection':
        if 'geometries_validator' not in validators.keys():
            validators['geometries_validator'] = field_validator('geometries')(geometry_collection_linear_rings_closed)  # noqa
        geom_type_models = list()
        for gt in (
            'Point',
            'LineString',
            'Polygon',
            'MultiPoint',
            'MultiLineString',
            'MultiPolygon',
        ):
            geom_type_models.append(
                create_geojson_geometry_model(
                    gt,
                    n_dims,
                    # Deactivate default validator function for 'coordinates'
                    # field of internal geometries
                    field_validators={'coordinates': None},
                )
            )
        return create_model(
            f'GeoJSON{geom_type}',
            type=(Literal[geom_type], ...),
            geometries=(Union[tuple(geom_type_models)], ...),
            bbox=(bbox_type, Optional),
            __validators__=validators,
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


def create_geojson_feature_model(
    properties: Optional[List[GeoJSONProperty]] = None,
    geom_type: Optional[GeomType] = None,
    geom_nullable: bool = True,
    n_dims: conint(gt=1) = 2,
    field_validators: Optional[Dict[str, Union[callable, None]]] = None,
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
    :param field_validators: field validator functions. If this parameter is
        passed a value different from `None`, it must be a `dict` which keys
        are the field names of a GeoJSON Feature to validate
        (e.g. 'geometry'), and which values are the validator functions for
        the corresponding fields. The validator function must have a <Signature
        (cls, field_value)> signature, and return the validated field value.
    :type field_validators: `dict`

    :returns: pydantic model of GeoJSON Feature
    :rtype: subclass of `pydantic.BaseModel`

    .. note::
        - If ``properties`` and/or ``geom_type`` are not given/set to `None`, a
          GeoJSON Feature object will only validate against the returned
          GeoJSON Feature model if its 'properties' and/or 'geometry' members
          are set to 'null', respectively.
        - If ``field_validators`` is not specified or set to `None`, the
          'geometry' field has a default validator, which ensure that 'Polygon'
          and 'MultiPolygon' geometries have closed linear rings, as per the
          `GeoJSON Specification (RFC 7946)
          <https://datatracker.ietf.org/doc/html/rfc7946>`_. If a validator
          function is specified for the 'geometry' field, it will override the
          corresponding default validator function.
        - The value of the 'geometry' field validator can be set to `None`
          instead of a `callable` if one wants to deactivate the default
          validator.
    """
    validators = format_model_field_validators(field_validators)
    if 'geometry_validator' not in validators.keys():
        validators['geometry_validator'] = field_validator('geometry')(feature_linear_rings_closed)  # noqa
    bbox_type = get_bbox_type(n_dims)
    if geom_type is None:
        geom_field_def = (Optional[None], ...)
    elif geom_nullable:
        geojson_geom_model = create_geojson_geometry_model(geom_type, n_dims)
        geom_field_def = (Optional[geojson_geom_model], ...)
    else:
        geom_field_def = (
            create_geojson_geometry_model(geom_type, n_dims), ...,
        )
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
        __validators__=validators,
    )


def create_geojson_feature_collection_model(
    properties: Optional[List[GeoJSONProperty]] = None,
    geom_type: Optional[GeomType] = None,
    geom_nullable: bool = True,
    n_dims: conint(gt=1) = 2,
    field_validators: Optional[Dict[str, Union[callable, None]]] = None,
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
    :param field_validators: field validator functions. If this parameter is
        passed a value different from `None`, it must be a `dict` which keys
        are the field names of a GeoJSON FeatureCollection to validate
        (e.g. 'features'), and which values are the validator functions for
        the corresponding fields. The validator function must have a <Signature
        (cls, field_value)> signature, and return the validated field value.
    :type field_validators: `dict`

    :returns: pydantic model of GeoJSON FeatureCollection
    :rtype: subclass of `pydantic.BaseModel`

    .. note::
        - If ``properties`` and/or ``geom_type`` are not given/set to `None`, a
          GeoJSON FeatureCollection object will only validate against the
          returned GeoJSON FeatureCollection model if all Features have their
          'properties' and/or 'geometry' members set to 'null', respectively.
        - If ``field_validators`` is not specified or set to `None`, the
          'features' field has a default validator, which ensure that 'Polygon'
          and 'MultiPolygon' geometries have closed linear rings, as per the
          `GeoJSON Specification (RFC 7946)
          <https://datatracker.ietf.org/doc/html/rfc7946>`_. If a validator
          function is specified for the 'features' field, it will override the
          corresponding default validator function.
        - The value of the 'features' field validator can be set to `None`
          instead of a `callable` if one wants to deactivate the default
          validator.
    """
    validators = format_model_field_validators(field_validators)
    if 'features_validator' not in validators.keys():
        validators['features_validator'] = field_validator('features')(feature_collection_linear_rings_closed)  # noqa
    bbox_type = get_bbox_type(n_dims)
    feature_model = create_geojson_feature_model(
        properties, geom_type, geom_nullable, n_dims,
    )
    return create_model(
        'GeoJSONFeatureCollection',
        type=(Literal['FeatureCollection'], ...),
        features=(List[feature_model], ...),
        bbox=(bbox_type, Optional),
        __validators__=validators,
    )
