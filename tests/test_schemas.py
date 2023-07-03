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


import itertools

from pygeoapi import schemas
from pygeoapi.schemas import GeomType


def test_get_geometry_schema():
    for gt, gn, nd in itertools.product(
        (gt for gt in GeomType if gt != GeomType.geometrycollection),
        (True, False),
        (2, 3),
    ):
        geom_schema = schemas.get_geometry_schema(
            geom_type=gt,
            geom_nullable=gn,
            n_dims=nd,
        )
        if gn:
            assert {'type': None} in geom_schema['oneOf']
            assert len(geom_schema['oneOf']) == 2

            for sub_schema in geom_schema['oneOf']:
                if sub_schema != {'type': None}:
                    break
            geom_schema = sub_schema

        assert geom_schema['type'] == 'object'
        assert 'type' in geom_schema['required']
        assert 'coordinates' in geom_schema['required']

        obj_props = geom_schema['properties']

        for p in ('type', 'coordinates', 'bbox'):
            assert p in obj_props.keys()

        assert obj_props['type'] == {'const': gt.value}

        bbox = obj_props['bbox']

        assert bbox['type'] == 'array'
        assert bbox['items'] == {'type': 'number'}
        assert bbox['minItems'] == 2 * nd
        assert bbox['maxItems'] == 2 * nd

        coordinates = obj_props['coordinates']

        def validate_pt_coords_schema(pt_coords_schema: dict):

            assert pt_coords_schema['type'] == 'array'
            assert pt_coords_schema['items']['type'] == 'number'
            assert pt_coords_schema['minItems'] == nd
            assert pt_coords_schema['maxItems'] == nd

        def validate_ls_coords_schema(ls_coords_schema: dict):

            assert ls_coords_schema['type'] == 'array'
            assert ls_coords_schema['minItems'] == 2

            pt_coords_schema = ls_coords_schema['items']
            validate_pt_coords_schema(pt_coords_schema)

        def validate_poly_coords_schema(poly_coords_schema: dict):

            assert poly_coords_schema['type'] == 'array'

            lr_coords_schema = poly_coords_schema['items']

            assert lr_coords_schema['type'] == 'array'
            assert lr_coords_schema['minItems'] == 4

            pt_coords_schema = lr_coords_schema['items']
            validate_pt_coords_schema(pt_coords_schema)

        def validate_multigeom_coords_schema(
            multigeom_coords_schema: dict,
            validate_geom_coords_schema: callable,
        ):

            assert multigeom_coords_schema['type'] == 'array'

            geom_coords_schema = multigeom_coords_schema['items']
            validate_geom_coords_schema(geom_coords_schema)

        if gt == GeomType.point:
            validate_pt_coords_schema(coordinates)

        elif gt == GeomType.linestring:
            validate_ls_coords_schema(coordinates)

        elif gt == GeomType.polygon:
            validate_poly_coords_schema(coordinates)

        elif gt == GeomType.multipoint:
            validate_multigeom_coords_schema(
                coordinates, validate_pt_coords_schema,
            )

        elif gt == GeomType.multilinestring:
            validate_multigeom_coords_schema(
                coordinates, validate_ls_coords_schema,
            )

        elif gt == GeomType.multipolygon:
            validate_multigeom_coords_schema(
                coordinates, validate_poly_coords_schema,
            )
