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


import datetime as dt
import itertools

from pydantic import ValidationError
import pytest

from pygeoapi.models.geojson import (
    create_geojson_geometry_model,
    # create_geojson_feature_model,
    # create_geojson_feature_collection_model,
    GeoJSONProperty,
)


@pytest.fixture
def invalid_bboxes() -> list:
    """Returns list of invalid bboxes"""
    return [
        [0, 1.0],
        'wrong_type',
    ]


@pytest.fixture
def invalid_points(invalid_bboxes) -> list:
    """Returns list of invalid GeoJSON Points"""
    invalid_points = [
        {
         'type': 'wrong_type',
         'coordinates': [0.0, 0.0],
        },
        {
         'type': 'Point',
         'coordinates': [0.0, 0.0],
         'wrong_field': 'blabla',
        },
        {
         'type': 'Point',
         # must be at least two dimensional
         'coordinates': [0],
        },
        {
         'type': 'Point',
         'coordinates': [0.0, 0.0],
         # mismatch between number of dimensions for the 'coordinates' and
         # the'bbox' fields
         'bbox': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
    ]
    invalid_points.extend(
        {'type': 'Point', 'coordinates': [0.0, 0.0], 'bbox': bbox}
        for bbox in invalid_bboxes
    )

    invalid_points.append(
        {
         'type': 'Point',
         'coordinates': [0.0, 0.0],
         'bbox': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        }
    )
    return invalid_points


@pytest.fixture
def invalid_linestrings(invalid_bboxes) -> list:
    """Returns list of invalid GeoJSON LineStrings"""
    invalid_linestrings = [
        {
         'type': 'wrong_type',
         'coordinates': [[0.0, 0.0], [1.0, 1.0]],
        },
        {
         'type': 'LineString',
         'coordinates': [[0.0, 0.0], [1.0, 1.0]],
         'wrong_field': 'blabla',
        },
        {
         'type': 'LineString',
         # must be at least two dimensional
         'coordinates': [[0], [1]],
        },
        {
         'type': 'LineString',
         'coordinates': [[0.0, 0.0], [1.0, 1.0]],
         # mismatch between number of dimensions for the 'coordinates' and
         # the'bbox' fields
         'bbox': [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        },
    ]
    invalid_linestrings.extend(
        {
         'type': 'LineString',
         'coordinates': [[0.0, 0.0], [1.0, 1.0]],
         'bbox': bbox,
        }
        for bbox in invalid_bboxes
    )
    return invalid_linestrings


@pytest.fixture
def invalid_polygons(invalid_bboxes) -> list:
    """Returns list of invalid GeoJSON Polygons"""
    invalid_polygons = [
        {
         'type': 'wrong_type',
         'coordinates': [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
        },
        {
         'type': 'Polygon',
         'coordinates': [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
         'wrong_field': 'blabla',
        },
        {
         'type': 'Polygon',
         # must be at least two dimensional
         'coordinates': [[[0.0], [1.0], [2.0], [0.0]]],
        },
        {
         'type': 'Polygon',
         'coordinates': [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
         # mismatch between number of dimensions for the 'coordinates' and
         # the'bbox' fields
         'bbox': [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        },
        {
         'type': 'Polygon',
         # must be an array of at least four positions
         'coordinates': [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]],
        },
    ]
    invalid_polygons.extend(
        {
         'type': 'Polygon',
         'coordinates': [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
         'bbox': bbox,
        }
        for bbox in invalid_bboxes
    )
    invalid_polygons.append(
        {
         'type': 'Polygon',
         # must have closed rings
         'coordinates': [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]]],
        }
    )
    return invalid_polygons


@pytest.fixture
def invalid_multipoints(invalid_bboxes) -> list:
    """Returns list of invalid GeoJSON MultiPoints"""
    invalid_multipoints = [
        {
         'type': 'wrong_type',
         'coordinates': [[0.0, 0.0]],
        },
        {
         'type': 'MultiPoint',
         'coordinates': [[0.0, 0.0]],
         'wrong_field': 'blabla',
        },
        {
         'type': 'MultiPoint',
         'coordinates': [[0.0, 0.0]],
         # mismatch between number of dimensions for the 'coordinates' and
         # the'bbox' fields
         'bbox': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        },
        {
         'type': 'MultiPoint',
         # must be at least two dimensional
         'coordinates': [[0]],
        },
    ]
    invalid_multipoints.extend(
        {
         'type': 'MultiPoint',
         'coordinates': [[0.0, 0.0], [1.0, 1.0]],
         'bbox': bbox,
        }
        for bbox in invalid_bboxes
    )
    return invalid_multipoints


@pytest.fixture
def invalid_multilinestrings(invalid_bboxes) -> list:
    """Returns list of invalid GeoJSON MultiLineStrings"""
    invalid_multilinestrings = [
        {
         'type': 'wrong_type',
         'coordinates': [[[0.0, 0.0], [1.0, 1.0]]],
        },
        {
         'type': 'MultiLineString',
         'coordinates': [[[0.0, 0.0], [1.0, 1.0]]],
         'wrong_field': 'blabla',
        },
        {
         'type': 'MultiLineString',
         # must be at least two dimensional
         'coordinates': [[[0], [1]]],
        },
        {
         'type': 'MultiLineString',
         'coordinates': [[[0.0, 0.0], [1.0, 1.0]]],
         # mismatch between number of dimensions for the 'coordinates' and
         # the'bbox' fields
         'bbox': [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        },
    ]
    invalid_multilinestrings.extend(
        {
         'type': 'MultiLineString',
         'coordinates': [[[0.0, 0.0], [1.0, 1.0]]],
         'bbox': bbox,
        }
        for bbox in invalid_bboxes
    )
    return invalid_multilinestrings


@pytest.fixture
def invalid_multipolygons(invalid_polygons, invalid_bboxes) -> list:
    """Returns list of invalid GeoJSON MultiPolygons"""
    invalid_multipolygons = [
        {
         'type': 'wrong_type',
         'coordinates': [[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]]],
        },
        {
         'type': 'MultiPolygon',
         'coordinates': [[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]]],
         'wrong_field': 'blabla',
        },
        {
         'type': 'MultiPolygon',
         # must be at least two dimensional
         'coordinates': [[[[0.0], [1.0], [2.0], [0.0]]]],
        },
        {
         'type': 'MultiPolygon',
         'coordinates': [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
         # mismatch between number of dimensions for the 'coordinates' and
         # the'bbox' fields
         'bbox': [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        },
    ]
    invalid_multipolygons.extend(
        {
         'type': 'MultiPolygon',
         'coordinates': [[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]]],
         'bbox': bbox,
        }
        for bbox in invalid_bboxes
    )
    return invalid_multipolygons


@pytest.fixture
def invalid_geometrycollections(
    invalid_points,
    invalid_linestrings,
    invalid_polygons,
    invalid_multipoints,
    invalid_multilinestrings,
    invalid_multipolygons,
    invalid_bboxes,
) -> list:
    """Returns list of invalid GeoJSON GeometryCollections"""
    invalid_geometrycollections = [
        {
         'type': 'wrong_type',
         'geometries': [
             {
              'type': 'Point',
              'coordinates': [0.0, 0.0],
             }
         ],
        },
        {
         'type': 'GeometryCollection',
         'geometries': [
             {
              'type': 'Point',
              'coordinates': [0.0, 0.0],
             }
         ],
         'wrong_field': 'blabla',
        },
        {
         'type': 'GeometryCollection',
         'geometries': [
             {
              'type': 'Point',
              'coordinates': [0.0, 0.0],
             }
         ],
         # mismatch between number of dimensions for the 'coordinates' of the
         # GeoJSON Point and the'bbox' fields
         'bbox': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
    ]
    invalid_geometrycollections.extend(
        {
         'type': 'GeometryCollection',
         'geometries': [invalid_geom],
        }
        for invalid_geom in itertools.chain(
            invalid_points,
            invalid_linestrings,
            invalid_polygons,
            invalid_multipoints,
            invalid_multilinestrings,
            invalid_multipolygons,
        )
    )
    invalid_geometrycollections.extend(
        {
         'type': 'GeometryCollection',
         'geometries': [
             {
              'type': 'Point',
              'coordinates': [0.0, 0.0],
             }
         ],
         'bbox': bbox,
        }
        for bbox in invalid_bboxes
    )
    return invalid_geometrycollections


def test_create_geojson_geometry_model(
    invalid_points,
    invalid_linestrings,
    invalid_polygons,
    invalid_multipoints,
    invalid_multilinestrings,
    invalid_multipolygons,
    invalid_geometrycollections,
):
    """Test that pydantic models validate valid GeoJSON geometries and raises
    ValidationError for invalid GeoJSON geometries.
    """
    PointModel2D = create_geojson_geometry_model('Point', 2)

    valid_point = PointModel2D.model_validate(
        {'type': 'Point', 'coordinates': [0.0, 0.0]}
    )

    for point in invalid_points:
        with pytest.raises(ValidationError):
            PointModel2D.model_validate(point)

    PointModel3D = create_geojson_geometry_model('Point', 3)

    valid_point3d = PointModel3D.model_validate(
        {
         'type': 'Point',
         'coordinates': [0.0, 0.0, 0.0],
         'bbox': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )

    LineStringModel2D = create_geojson_geometry_model('LineString', 2)

    valid_linestring = LineStringModel2D.model_validate(
        {'type': 'LineString', 'coordinates': [[0.0, 0.0], [1.0, 1.0]]}
    )

    for linestring in invalid_linestrings:
        with pytest.raises(ValidationError):
            LineStringModel2D.model_validate(linestring)

    LineStringModel3D = create_geojson_geometry_model('LineString', 3)

    valid_linestring3d = LineStringModel3D.model_validate(
        {
         'type': 'LineString',
         'coordinates': [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]],
         'bbox': [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        }
    )

    PolygonModel2D = create_geojson_geometry_model('Polygon', 2)

    valid_polygon = PolygonModel2D.model_validate(
        {
         'type': 'Polygon',
         'coordinates': [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]],
        }
    )

    for polygon in invalid_polygons:
        with pytest.raises(ValidationError):
            PolygonModel2D.model_validate(polygon)

    PolygonModel3D = create_geojson_geometry_model('Polygon', 3)

    valid_polygon3d = PolygonModel3D.model_validate(
        {
         'type': 'Polygon',
         'coordinates': [
             [
              [0.0, 0.0, 0.0],
              [1.0, 0.0, 0.5],
              [1.0, 1.0, 1.0],
              [0.0, 0.0, 0.0],
             ]
         ],
         'bbox': [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        }
    )

    MultiPointModel2D = create_geojson_geometry_model('MultiPoint', 2)

    valid_multipoint = MultiPointModel2D.model_validate(
        {'type': 'MultiPoint', 'coordinates': [[0.0, 0.0]]}
    )

    for multipoint in invalid_multipoints:
        with pytest.raises(ValidationError):
            MultiPointModel2D.model_validate(multipoint)

    MultiPointModel3D = create_geojson_geometry_model('MultiPoint', 3)

    valid_multipoint3d = MultiPointModel3D.model_validate(
        {
         'type': 'MultiPoint',
         'coordinates': [[0.0, 0.0, 0.0]],
         'bbox': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )

    MultiLineStringModel2D = create_geojson_geometry_model(
        'MultiLineString', 2,
    )

    valid_multilinestring = MultiLineStringModel2D.model_validate(
        {'type': 'MultiLineString', 'coordinates': [[[0.0, 0.0], [1.0, 1.0]]]}
    )

    for multilinestring in invalid_multilinestrings:
        with pytest.raises(ValidationError):
            MultiLineStringModel2D.model_validate(multilinestring)

    MultiLineStringModel3D = create_geojson_geometry_model(
        'MultiLineString', 3,
    )

    valid_multilinestring3d = MultiLineStringModel3D.model_validate(
        {
         'type': 'MultiLineString',
         'coordinates': [[[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]],
         'bbox': [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        }
    )

    MultiPolygonModel2D = create_geojson_geometry_model('MultiPolygon', 2)

    valid_multipolygon = MultiPolygonModel2D.model_validate(
        {
         'type': 'MultiPolygon',
         'coordinates': [[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]]],
        }
    )

    for multipolygon in invalid_multipolygons:
        with pytest.raises(ValidationError):
            MultiPolygonModel2D.model_validate(multipolygon)

    MultiPolygonModel3D = create_geojson_geometry_model('MultiPolygon', 3)

    valid_multipolygon3d = MultiPolygonModel3D.model_validate(
        {
         'type': 'MultiPolygon',
         'coordinates': [
             [
              [
               [0.0, 0.0, 0.0],
               [1.0, 0.0, 0.5],
               [1.0, 1.0, 1.0],
               [0.0, 0.0, 0.0],
              ],
             ]
         ],
         'bbox': [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        }
    )

    GeometryCollectionModel2D = create_geojson_geometry_model(
        'GeometryCollection', 2,
    )

    _ = GeometryCollectionModel2D.model_validate(
        {
         'type': 'GeometryCollection',
         'geometries': [
             valid_point.model_dump(exclude_unset=True),
             valid_linestring.model_dump(exclude_unset=True),
             valid_polygon.model_dump(exclude_unset=True),
             valid_multipoint.model_dump(exclude_unset=True),
             valid_multilinestring.model_dump(exclude_unset=True),
             valid_multipolygon.model_dump(exclude_unset=True),
         ],
        }
    )

    for geometrycollection in invalid_geometrycollections:
        with pytest.raises(ValidationError):
            GeometryCollectionModel2D.model_validate(geometrycollection)

    GeometryCollectionModel3D = create_geojson_geometry_model(
        'GeometryCollection', 3,
    )

    _ = GeometryCollectionModel3D.model_validate(
        {
         'type': 'GeometryCollection',
         'geometries': [
             valid_point3d.model_dump(exclude_unset=True),
             valid_linestring3d.model_dump(exclude_unset=True),
             valid_polygon3d.model_dump(exclude_unset=True),
             valid_multipoint3d.model_dump(exclude_unset=True),
             valid_multilinestring3d.model_dump(exclude_unset=True),
             valid_multipolygon3d.model_dump(exclude_unset=True),
         ],
        }
    )


@pytest.fixture
def geojson_properties() -> list:
    """Returns list of `GeoJSONProperty` to create the pydantic models"""
    return [
        GeoJSONProperty(
            name='city', dtype=str, nullable=False, required=True,
        ),
        GeoJSONProperty(
            name='population', dtype=int, nullable=False, required=False,
        ),
        GeoJSONProperty(
            name='area', dtype=float, nullable=True, required=True,
        ),
        GeoJSONProperty(
            name='db_datetime', dtype=dt.datetime, nullable=True, required=False,  # noqa
        ),
    ]


@pytest.fixture
def valid_features():
    """Returns list of valid features"""
    return [
        {
         'type': 'Feature',
         'geometry': {'type': 'Point', 'coordinates': [48.856667, 2.352222]},
         'properties': {
             'city': 'Paris',
             'population': 2_102_650,
             'area': None,
             'db_datetime': dt.datetime(2023, 9, 19),
         },
        },
        {
         'type': 'Feature',
         'geometry': {'type': 'Point', 'coordinates': [40.712778, -74.006111]},
         'properties': {
             'city': 'New York',
             'area': 1_223.59,
             'db_datetime': dt.datetime(2023, 9, 10),
         },
        },
        {
         'type': 'Feature',
         'geometry': {'type': 'Point', 'coordinates': [45.508889, -73.554167]},
         'properties': {
             'city': 'Montreal',
             'population': 1_762_949,
             'area': 431.50,
             'db_datetime': dt.datetime(2023, 9, 10),
         },
        },
        {
         'type': 'Feature',
         'geometry': {'type': 'Point', 'coordinates': [41.893333, 12.482778]},
         'properties': {
             'city': 'Rome',
             'population': 4_342_212,
             'area': 1_285,
             'db_datetime': dt.datetime(2023, 9, 10),
         },
        },
        {
         'type': 'Feature',
         'geometry': {'type': 'Point', 'coordinates': [52.372778, 4.893611]},
         'properties': {
             'city': 'Amsterdam',
             'area': None,
             'db_datetime': dt.datetime(2023, 9, 11),
         },
        },
        {
         'type': 'Feature',
         'geometry': {'type': 'Point', 'coordinates': [37.984167, 23.728056]},
         'properties': {
             'city': 'Athens',
             'population': 3_059_764,
             'area': 412,
         },
        },
        {
         'type': 'Feature',
         'geometry': {'type': 'Point', 'coordinates': [38.725278, -9.15]},
         'properties': {
             'city': 'Lisbon',
             'population': 548_703,
             'area': 100.05,
             'db_datetime': None,
         },
        },
    ]


def test_create_geojson_feature_model():
    pass


def test_create_geojson_feature_collection_model():
    pass
