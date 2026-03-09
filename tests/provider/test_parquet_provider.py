# =================================================================
#
# Authors: Leo Ghignone <leo.ghignone@gmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2024 Leo Ghignone
# Copyright (c) 2025 Tom Kralidis
# Copyright (c) 2026 Colton Loftus
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

from copy import copy

import pytest

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.parquet import ParquetProvider

from ..util import get_test_file_path


@pytest.fixture()
def config_parquet():
    return {
        'name': 'Parquet',
        'type': 'feature',
        'data': {
            'source': get_test_file_path('data/parquet/naive/random.parquet'),
        },
        'id_field': 'id',
        'time_field': 'time',
        'x_field': 'lon',
        'y_field': 'lat'
    }


@pytest.fixture()
def config_parquet_nogeom_notime():
    return {
        'name': 'ParquetNoGeomNoTime',
        'type': 'feature',
        'data': {
            'source': get_test_file_path(
                'data/parquet/naive/random_nogeom.parquet')
        },
        'id_field': 'id'
    }


@pytest.fixture()
def config_parquet_nocrs():
    return {
        'name': 'ParquetNoCrs',
        'type': 'feature',
        'data': {
            'source': get_test_file_path(
                'data/parquet/naive/random_nocrs.parquet')
        },
        'id_field': 'id',
        'time_field': 'time',
        'x_field': 'lon',
        'y_field': 'lat'
    }


@pytest.fixture
def geoparquet_no_bbox():
    # Data originating from
    # https://github.com/opengeospatial/geoparquet/blob/main/test_data/data-polygon-encoding_wkb.parquet

    # As CSV:
    # "col","geometry"
    # 0,"POLYGON ((30 10, 40 40, 20 40, 10 20, 30 10))"
    # 1,"POLYGON ((35 10, 45 45, 15 40, 10 20, 35 10), (20 30, 35 35, 30 20, 20 30))" # noqa
    # 2,"POLYGON EMPTY"
    # 3,
    return {
        'name': 'GeoparquetNoBbox',
        'type': 'feature',
        'data': {
            'source': get_test_file_path(
                'data/parquet/geoparquet1.1/data-polygon-encoding_wkb_no_bbox.parquet'  # noqa
            )
        }
    }


@pytest.fixture
def geoparquet_with_bbox():
    # Geneated with the overture python CLI
    # overturemaps download --bbox=-74,40.98,-73.98,41 -f geoparquet --type=building -o nyc_subset_overture.parquet # noqa
    return {
        'name': 'GeoparquetWithBbox',
        'type': 'feature',
        'data': {
            'source': get_test_file_path(
                'data/parquet/geoparquet1.1/nyc_subset_overture.parquet'
            )
        }
    }


class TestParquetProviderWithNaiveOrMissingGeometry:
    """Tests for parquet that do not comply to geoparquet standard"""

    def test_get_fields(self, config_parquet):
        """Testing field types"""

        p = ParquetProvider(config_parquet)
        assert p.bbox_filterable
        assert p.has_geometry
        assert not p.has_bbox_column
        results = p.get_fields()
        assert results['lat']['type'] == 'number'
        assert results['lon']['format'] == 'double'
        assert results['time']['format'] == 'date-time'

    def test_get(self, config_parquet):
        """Testing query for a specific object"""

        p = ParquetProvider(config_parquet)
        result = p.get('42')
        assert result['id'] == '42'
        assert result['properties']['lon'] == 4.947447

    def test_get_not_existing_feature_raise_exception(
        self, config_parquet
    ):
        """Testing query for a not existing object"""
        p = ParquetProvider(config_parquet)
        with pytest.raises(ProviderItemNotFoundError):
            p.get(-1)

    def test_query_hits(self, config_parquet):
        """Testing query on entire collection for hits"""

        p = ParquetProvider(config_parquet)
        feature_collection = p.query(resulttype='hits')
        assert feature_collection.get('type') == 'FeatureCollection'
        features = feature_collection.get('features')
        assert len(features) == 0
        hits = feature_collection.get('numberMatched')
        assert hits is not None
        assert hits == 100

    def test_query_bbox_hits(self, config_parquet):
        """Testing query for a valid JSON object with geometry"""

        p = ParquetProvider(config_parquet)
        feature_collection = p.query(
            bbox=[100, -50, 150, 0],
            resulttype='hits')
        assert feature_collection.get('type') == 'FeatureCollection'
        features = feature_collection.get('features')
        assert len(features) == 0
        hits = feature_collection.get('numberMatched')
        assert hits is not None
        assert hits == 6

    def test_query_with_limit(self, config_parquet):
        """Testing query for a valid JSON object with geometry"""

        p = ParquetProvider(config_parquet)
        feature_collection = p.query(limit=2, resulttype='results')
        assert feature_collection.get('type') == 'FeatureCollection'
        features = feature_collection.get('features')
        assert len(features) == 2
        hits = feature_collection.get('numberMatched')
        assert hits > 2
        feature = features[0]
        properties = feature.get('properties')
        assert properties is not None
        geometry = feature.get('geometry')
        assert geometry is not None

    def test_query_with_offset(self, config_parquet):
        """Testing query for a valid JSON object with geometry"""

        p = ParquetProvider(config_parquet)
        feature_collection = p.query(offset=20, limit=10, resulttype='results')
        assert feature_collection.get('type') == 'FeatureCollection'
        features = feature_collection.get('features')
        assert len(features) == 10
        hits = feature_collection.get('numberMatched')
        assert hits > 30
        feature = features[0]
        properties = feature.get('properties')
        assert properties is not None
        assert feature['id'] == '21'
        assert properties['lat'] == 66.264988
        geometry = feature.get('geometry')
        assert geometry is not None

    def test_query_with_property(self, config_parquet):
        """Testing query for a valid JSON object with property filter"""

        p = ParquetProvider(config_parquet)
        feature_collection = p.query(
            resulttype='results',
            properties=[('lon', -12.855022)])
        assert feature_collection.get('type') == 'FeatureCollection'
        features = feature_collection.get('features')
        assert len(features) == 1
        for feature in features:
            assert feature['properties']['lon'] == -12.855022

    def test_query_with_skip_geometry(self, config_parquet):
        """Testing query for a valid JSON object with property filter"""

        p = ParquetProvider(config_parquet)
        feature_collection = p.query(skip_geometry=True)
        for feature in feature_collection['features']:
            assert feature.get('geometry') is None

    def test_query_with_datetime(self, config_parquet):
        """Testing query for a valid JSON object with time"""

        p = ParquetProvider(config_parquet)
        feature_collection = p.query(
            datetime_='2022-05-01T00:00:00Z/2022-05-31T23:59:59Z')
        assert feature_collection.get('type') == 'FeatureCollection'
        features = feature_collection.get('features')
        assert len(features) == 7
        for feature in feature_collection['features']:
            time = feature['properties'][config_parquet['time_field']]
            assert time.year == 2022
            assert time.month == 5

    def test_query_nogeom(self, config_parquet_nogeom_notime):
        """Testing query for a valid JSON object without geometry"""

        p = ParquetProvider(config_parquet_nogeom_notime)
        assert not p.has_geometry
        assert not p.bbox_filterable
        feature_collection = p.query(resulttype='results')
        assert feature_collection.get('type') == 'FeatureCollection'
        assert len(feature_collection.get('features')) > 0
        for feature in feature_collection['features']:
            assert feature.get('geometry') is None

    def test_query_nocrs(self, config_parquet_nocrs):
        """Testing a parquet provider without CRS"""

        p = ParquetProvider(config_parquet_nocrs)
        assert p.bbox_filterable
        assert p.has_geometry
        assert not p.has_bbox_column
        results = p.get_fields()
        assert results['lat']['type'] == 'number'
        assert results['lon']['format'] == 'double'
        assert results['time']['format'] == 'date-time'


class TestParquetProviderWithGeoparquetMetadata:

    def test_file_without_bbox_without_id_specified(self, geoparquet_no_bbox):

        p = ParquetProvider(geoparquet_no_bbox)
        assert not p.bbox_filterable
        assert not p.has_bbox_column
        assert p.id_field is None
        results = p.get_fields()
        assert results['col']['type'] == 'integer'

        feature_collection = p.query(resulttype='results')
        assert feature_collection.get('type') == 'FeatureCollection'
        assert feature_collection['features'][0]['geometry']['coordinates'] == ( # noqa
            (
                ((30, 10), (40, 40), (20, 40), (10, 20), (30, 10)),)
        )
        assert feature_collection['features'][0]['properties']['col'] == 0

    def test_file_without_bbox_with_id_specified(self, geoparquet_no_bbox):
        config = copy(geoparquet_no_bbox)
        config['id_field'] = 'col'

        p = ParquetProvider(
            config
        )
        results = p.get_fields()
        assert p.id_field == 'col'
        assert results['col']['type'] == 'integer'

        feature_collection = p.query(resulttype='results')
        assert feature_collection.get('type') == 'FeatureCollection'
        assert feature_collection['features'][0]['geometry']['coordinates'] == ( # noqa
            (((30, 10), (40, 40), (20, 40), (10, 20), (30, 10)),)
        )
        assert feature_collection['features'][0]['properties']['col'] == 0
        assert feature_collection['features'][0]['id'] == '0'

    def test_get_by_id(self, geoparquet_no_bbox):

        config = copy(geoparquet_no_bbox)
        config['id_field'] = 'col'
        p = ParquetProvider(
            config
        )

        feature = p.get('2')
        assert feature.get('type') == 'Feature'
        assert feature['geometry'] is None

    def test_file_with_bbox(self, geoparquet_with_bbox):

        p = ParquetProvider(geoparquet_with_bbox)
        assert p.has_bbox_column
        assert p.bbox_filterable
        assert p.has_geometry

        hits = p.query(resulttype='hits')['numberMatched']
        assert hits == 679

        huge_bbox = p.query(bbox=[-90, -90, 90, 90], resulttype='hits')[
            'numberMatched'
        ]
        dataset_bounds = p.query(bbox=[-74.1, 40.97, -73.95, 41.1],
                                 resulttype='hits')['numberMatched']
        assert huge_bbox == dataset_bounds
