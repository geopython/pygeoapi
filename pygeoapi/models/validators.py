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


from typing import Dict, Optional, Union

from pydantic import field_validator


def format_model_field_validators(
    field_validators: Optional[Dict[str, Union[callable, None]]] = None,
):
    """ Format the field validators for the pydantic models to create.

    :param field_validators: field validator functions mapping. If this
        parameter is passed a value different from `None`, it must be a `dict`
        which keys are the field names of a given pydantic model to validate,
        and which values are the validator functions for the corresponding
        fields. The validator function must have a <Signature (cls,
        field_value)> signature, and return the validated field value.
    :type field_validators: `dict`

    :returns: formatted field validators to pass to the __validators__
        parameter of the :func:`pydantic.create_model` function.
    :rtype: `dict`
    """
    validators = dict()
    if field_validators is not None:
        for f, v in field_validators.items():
            if v is None:
                # Always valid field and return unchanged
                validators[f'{f}_validator'] = field_validator(f)(
                    lambda cls, field_val: field_val
                )
            else:
                validators[f'{f}_validator'] = field_validator(f)(v)
    return validators


def polygon_linear_rings_closed(cls, coordinates):
    """Validator function that checks for closed/opened linear rings in a
    polygon.
    """
    for ring in coordinates:
        assert ring[0] == ring[-1], (
            'First and and last position of linear ring must be the same'
        )
    return coordinates


def multipolygon_linear_rings_closed(cls, coordinates):
    """Validator function that checks for closed/opened linear rings in a
    multipolygon.
    """
    for poly in coordinates:
        polygon_linear_rings_closed(cls, poly)
    return coordinates


def geometry_collection_linear_rings_closed(cls, geometries):
    """Validator function that checks for closed/opened linear rings in a
    geometry collection.
    """
    for geom in geometries:
        if geom.type == 'Polygon':
            _ = polygon_linear_rings_closed(geom, geom.coordinates)
        elif geom.type == 'MultiPolygon':
            _ = multipolygon_linear_rings_closed(geom, geom.coordinates)
    return geometries


def feature_linear_rings_closed(cls, geometry):
    """Validator function that checks for closed/opened linear rings in a
    feature's geometry.
    """
    if geometry:  # Make sure that 'geometry' != 'null'/None
        if geometry.type == 'Polygon':
            _ = polygon_linear_rings_closed(geometry, geometry.coordinates)
        elif geometry.type == 'MultiPolygon':
            _ = multipolygon_linear_rings_closed(
                geometry, geometry.coordinates,
            )
        elif geometry.type == 'GeometryCollection':
            _ = geometry_collection_linear_rings_closed(
                geometry, geometry.geometries,
            )
    return geometry


def feature_collection_linear_rings_closed(cls, features):
    """Validator function that checks for closed/opened linear rings in the
    features' geometry of a feature collection.
    """
    for feature in features:
        _ = feature_linear_rings_closed(feature, feature.geometry)
    return features
