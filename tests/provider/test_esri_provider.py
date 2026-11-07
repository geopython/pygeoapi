# =================================================================
#
# Authors: Benjamin Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2022 Benjamin Webb
# Copyright (c) 2026 Tom Kralidis
# Copyright (c) 2026 Frédéric Morin
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

from datetime import datetime
import json

import pytest
from pygeofilter.parsers.cql2_text import parse as parse_cql2_text

from pygeoapi.provider.base import ProviderInvalidQueryError
from pygeoapi.provider.esri import ESRIServiceProvider
from pygeoapi.util import DATETIME_FORMAT

TIME_FIELD = 'Date_Time'

BASE_URL = 'https://sampleserver6.arcgisonline.com/arcgis/rest/services'


@pytest.fixture()
def config():
    # National Hurricane Center
    # source: ESRI, NOAA/National Weather Service
    return {
        'name': 'ESRI',
        'type': 'feature',
        'data': f'{BASE_URL}/Hurricanes/MapServer/0',
        'id_field': 'OBJECTID',
        'time_field': TIME_FIELD
    }


@pytest.fixture()
def config_alt_id():
    # Emergency Facilities
    # source: ESRI
    return {
        'name': 'ESRI',
        'type': 'feature',
        'data': f'{BASE_URL}/EmergencyFacilities/FeatureServer/0',
        'id_field': 'facilityid'
    }


def test_query(config):
    p = ESRIServiceProvider(config)

    results = p.query()
    assert results['features'][0]['id'] == 1
    assert results['numberReturned'] == 10

    results = p.query(limit=50)
    assert results['numberReturned'] == 50

    results = p.query(offset=10)
    assert results['features'][0]['id'] == 11
    assert results['numberReturned'] == 10

    results = p.query(limit=10)
    assert len(results['features']) == 10
    assert results['numberMatched'] == 406

    results = p.query(limit=10001, resulttype='hits')
    assert results['numberMatched'] == 406


def test_no_count(config):
    p = ESRIServiceProvider(config)
    results = p.query()
    assert results['numberMatched'] == 406
    assert results['numberReturned'] == 10

    config['count'] = False
    p = ESRIServiceProvider(config)
    results = p.query()
    assert 'numberMatched' not in results
    assert results['numberReturned'] == 10


def test_geometry(config):
    p = ESRIServiceProvider(config)

    results = p.query()
    geometry = results['features'][0]['geometry']
    assert geometry['coordinates'] == [-17.99999999990007, 10.800000000099885]

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None

    config['storage_crs'] = 'http://www.opengis.net/def/crs/EPSG/0/3857'
    p = ESRIServiceProvider(config)
    results = p.query()
    geometry = results['features'][0]['geometry']
    assert geometry['coordinates'] == [-2003750.8342678, 1209433.8422282021]

    results = p.query(skip_geometry=True)
    assert results['features'][0]['geometry'] is None


def test_query_bbox(config):
    p = ESRIServiceProvider(config)

    bbox = [-171, 18, -67, 71]
    results = p.query(bbox=bbox)
    assert results['numberReturned'] == 10
    assert results['numberMatched'] == 128

    feature = results['features'][0]
    assert feature['properties']['EVENTID'] == 'Beryl'

    x, y = feature['geometry']['coordinates']
    xmin, ymin, xmax, ymax = bbox
    assert xmin <= x <= xmax
    assert ymin <= y <= ymax


def test_query_properties(config):
    p = ESRIServiceProvider(config)

    results = p.query()
    assert len(results['features'][0]['properties']) == 10

    # Query by property
    results = p.query(properties=[('EVENTID', 'Beryl'), ])
    assert results['features'][0]['properties']['EVENTID'] == 'Beryl'

    results = p.query(properties=[('EVENTID', 'Alberto'), ], resulttype='hits')
    assert results['numberMatched'] == 87

    # Query for property
    results = p.query(select_properties=['WINDSPEED', 'PRESSURE'])
    assert len(results['features'][0]['properties']) == 2
    assert 'WINDSPEED' in results['features'][0]['properties']

    # Query with configured properties
    config['properties'] = ['OBJECTID', 'EVENTID', 'TIME']
    p = ESRIServiceProvider(config)

    results = p.query()
    props = results['features'][0]['properties']
    assert all(p in props for p in config['properties'])
    assert len(props) == 3

    results = p.query(properties=[('EVENTID', 'Beryl'), ])
    assert results['features'][0]['properties']['EVENTID'] == 'Beryl'

    results = p.query(select_properties=['GEOGSTATE', ])
    assert len(results['features'][0]['properties']) == 1

    results = p.query(
        properties=[
            ('OBJECTID', "1' OR '1'='1")
        ]
    )

    assert results.get('type') == 'FeatureCollection'
    features = results.get('features')
    assert len(features) == 0


def test_query_sortby_datetime(config):

    p = ESRIServiceProvider(config)

    results = p.query(sortby=[{'property': 'EVENTID', 'order': '+'}])
    assert results['features'][0]['properties']['EVENTID'] == 'Alberto'

    results = p.query(sortby=[{'property': 'EVENTID', 'order': '-'}])
    assert results['features'][0]['properties']['EVENTID'] == 'Nadine'

    def feature_time(r):
        props = r['features'][0]['properties']
        timestamp = props[TIME_FIELD]/1000
        timestamp = datetime.fromtimestamp(timestamp)
        return timestamp.strftime(DATETIME_FORMAT)

    results = p.query(sortby=[{'property': TIME_FIELD, 'order': '+'}])
    assert results['features'][0]['properties'][TIME_FIELD] == 965354400000

    results = p.query(sortby=[{'property': TIME_FIELD, 'order': '-'}])
    assert results['features'][0]['properties'][TIME_FIELD] == 972244800000

    results = p.query(datetime_='../2000-09-01',
                      sortby=[{'property': TIME_FIELD, 'order': '-'}])
    assert results['features'][0]['properties'][TIME_FIELD] == 967212000000

    results = p.query(datetime_='2000-09-01/..',
                      sortby=[{'property': TIME_FIELD, 'order': '+'}])
    assert results['features'][0]['properties'][TIME_FIELD] == 967838400000


def test_get(config):
    p = ESRIServiceProvider(config)

    result = p.get(6)
    assert result['id'] == 6
    assert result['properties']['EVENTID'] == 'Alberto'


def test_alternative_id_field(config_alt_id):
    p = ESRIServiceProvider(config_alt_id)

    result = p.get('F0234')
    assert result['id'] == 'F0234'
    assert result['properties']['facname'] == 'Redlands Community Hospital'


@pytest.fixture()
def provider():
    p = object.__new__(ESRIServiceProvider)
    # empty `_fields` disables attribute-name validation in `_cql2_operand`
    p._fields = {}
    p.properties = []
    return p


def _where(provider, cql2_text):
    """Parse CQL2 text and return the translated ESRI `where` clause."""
    filterq = parse_cql2_text(cql2_text)
    spatial_node, residual = provider._extract_spatial(filterq)
    assert spatial_node is None
    return provider._make_where(filterq=residual)


def test_cql2_comparisons(provider):
    # Esri HQ: 380 New York Street, Redlands, CA (~5000 employees)
    assert _where(provider, "CITY = 'Redlands'") == "CITY = 'Redlands'"
    assert _where(provider, 'EMPLOYEES <> 5000') == 'EMPLOYEES <> 5000'
    assert _where(provider, 'EMPLOYEES > 5000') == 'EMPLOYEES > 5000'
    assert _where(provider, 'EMPLOYEES >= 5000') == 'EMPLOYEES >= 5000'
    assert _where(provider, 'EMPLOYEES < 5000') == 'EMPLOYEES < 5000'
    assert _where(provider, 'EMPLOYEES <= 5000') == 'EMPLOYEES <= 5000'


def test_cql2_logical(provider):
    where = _where(provider, "CITY = 'Redlands' AND EMPLOYEES > 5000")
    assert where == "(CITY = 'Redlands' AND EMPLOYEES > 5000)"

    where = _where(provider, "CITY = 'Redlands' OR CITY = 'Vienna'")
    assert where == "(CITY = 'Redlands' OR CITY = 'Vienna')"

    where = _where(provider, "NOT CITY = 'Redlands'")
    assert where == "(NOT CITY = 'Redlands')"


def test_cql2_like(provider):
    assert _where(provider, "CITY LIKE 'Red%'") == "CITY LIKE 'Red%'"


def test_cql2_in(provider):
    where = _where(provider, "CITY IN ('Redlands', 'Vienna')")
    assert where == "CITY IN ('Redlands', 'Vienna')"


def test_cql2_between(provider):
    where = _where(provider, 'EMPLOYEES BETWEEN 1000 AND 5000')
    assert where == 'EMPLOYEES BETWEEN 1000 AND 5000'


def test_cql2_is_null(provider):
    assert _where(provider, 'EMPLOYEES IS NULL') == 'EMPLOYEES IS NULL'
    assert _where(provider, 'EMPLOYEES IS NOT NULL') == 'EMPLOYEES IS NOT NULL'


def test_cql2_temporal(provider):
    # Esri was founded on 1969-01-01
    where = _where(provider, "FOUNDED T_AFTER DATE('1969-01-01')")
    assert where == "FOUNDED > TIMESTAMP '1969-01-01 00:00:00'"

    where = _where(provider, "FOUNDED T_BEFORE DATE('1969-01-01')")
    assert where == "FOUNDED < TIMESTAMP '1969-01-01 00:00:00'"

    where = _where(
        provider,
        "FOUNDED T_DURING "
        "INTERVAL('1969-01-01T00:00:00Z','1969-12-31T00:00:00Z')")
    assert where == ("FOUNDED BETWEEN TIMESTAMP '1969-01-01 00:00:00' "
                     "AND TIMESTAMP '1969-12-31 00:00:00'")


def test_cql2_sql_injection_escaped(provider):
    # Single quotes in literals must be doubled to prevent SQL injection
    assert (provider._cql2_operand("Redlands' OR '1'='1")
            == "'Redlands'' OR ''1''=''1'")


def test_cql2_invalid_property(provider):
    provider._fields = {'CITY': {'type': 'esriFieldTypeString'}}
    with pytest.raises(ProviderInvalidQueryError):
        _where(provider, "DOESNOTEXIST = 'x'")


def test_cql2_spatial_bbox(provider):
    # Bounding box around Esri HQ in Redlands, CA
    filterq = parse_cql2_text('BBOX(geometry, -117.2, 34.0, -117.19, 34.06)')
    spatial_node, residual = provider._extract_spatial(filterq)
    assert residual is None
    params = provider._spatial_to_params(spatial_node)
    assert params['geometryType'] == 'esriGeometryEnvelope'
    assert params['spatialRel'] == 'esriSpatialRelIntersects'
    assert params['geometry'] == '-117.2,34.0,-117.19,34.06'


def test_cql2_spatial_intersects(provider):
    # Polygon around the Esri campus in Redlands, CA
    wkt = ('POLYGON((-117.20 34.05, -117.19 34.05, '
           '-117.19 34.06, -117.20 34.06, -117.20 34.05))')
    filterq = parse_cql2_text(f'S_INTERSECTS(geometry, {wkt})')
    spatial_node, residual = provider._extract_spatial(filterq)
    assert residual is None
    params = provider._spatial_to_params(spatial_node)
    assert params['geometryType'] == 'esriGeometryPolygon'
    assert params['spatialRel'] == 'esriSpatialRelIntersects'
    geometry = json.loads(params['geometry'])
    assert geometry['rings'][0][0] == [-117.20, 34.05]
    assert geometry['spatialReference'] == {'wkid': 4326}


def test_cql2_spatial_within(provider):
    wkt = ('POLYGON((-117.20 34.05, -117.19 34.05, '
           '-117.19 34.06, -117.20 34.06, -117.20 34.05))')
    filterq = parse_cql2_text(f'S_WITHIN(geometry, {wkt})')
    spatial_node, _ = provider._extract_spatial(filterq)
    params = provider._spatial_to_params(spatial_node)
    assert params['spatialRel'] == 'esriSpatialRelWithin'


def test_cql2_spatial_combined_with_attribute(provider):
    wkt = ('POLYGON((-117.20 34.05, -117.19 34.05, '
           '-117.19 34.06, -117.20 34.06, -117.20 34.05))')
    filterq = parse_cql2_text(
        f"S_INTERSECTS(geometry, {wkt}) AND CITY = 'Redlands'")
    spatial_node, residual = provider._extract_spatial(filterq)
    assert spatial_node is not None
    where = provider._make_where(filterq=residual)
    assert where == "CITY = 'Redlands'"


def test_cql2_point_geometry(provider):
    # Esri HQ coordinates (longitude, latitude)
    filterq = parse_cql2_text(
        'S_INTERSECTS(geometry, POINT(-117.1956 34.0556))')
    spatial_node, _ = provider._extract_spatial(filterq)
    params = provider._spatial_to_params(spatial_node)
    assert params['geometryType'] == 'esriGeometryPoint'
    geometry = json.loads(params['geometry'])
    assert geometry['x'] == -117.1956
    assert geometry['y'] == 34.0556


def test_cql2_disjoint_unsupported(provider):
    wkt = ('POLYGON((-117.20 34.05, -117.19 34.05, '
           '-117.19 34.06, -117.20 34.06, -117.20 34.05))')
    filterq = parse_cql2_text(f'S_DISJOINT(geometry, {wkt})')
    spatial_node, _ = provider._extract_spatial(filterq)
    with pytest.raises(ProviderInvalidQueryError):
        provider._spatial_to_params(spatial_node)


def test_cql2_multiple_spatial_unsupported(provider):
    wkt = ('POLYGON((-117.20 34.05, -117.19 34.05, '
           '-117.19 34.06, -117.20 34.06, -117.20 34.05))')
    filterq = parse_cql2_text(
        f'S_INTERSECTS(geometry, {wkt}) AND S_WITHIN(geometry, {wkt})')
    with pytest.raises(ProviderInvalidQueryError):
        provider._extract_spatial(filterq)


def test_cql2_spatial_under_or_unsupported(provider):
    wkt = ('POLYGON((-117.20 34.05, -117.19 34.05, '
           '-117.19 34.06, -117.20 34.06, -117.20 34.05))')
    filterq = parse_cql2_text(
        f"S_INTERSECTS(geometry, {wkt}) OR CITY = 'Redlands'")
    with pytest.raises(ProviderInvalidQueryError):
        provider._extract_spatial(filterq)


def test_cql2_bbox_with_spatial_filter(provider):
    # Combining a bbox with a CQL2 spatial predicate must be rejected before
    # any network call is made.
    provider.srid = 4326
    filterq = parse_cql2_text(
        'S_INTERSECTS(geometry, '
        'POLYGON((-117.20 34.05, -117.19 34.05, '
        '-117.19 34.06, -117.20 34.06, -117.20 34.05)))')
    with pytest.raises(ProviderInvalidQueryError):
        provider.query(bbox=[-117.2, 34.0, -117.19, 34.06], filterq=filterq)


def test_cql2_query_live(config):
    p = ESRIServiceProvider(config)
    filterq = parse_cql2_text("EVENTID = 'Beryl'")
    results = p.query(filterq=filterq)
    assert results['type'] == 'FeatureCollection'
    for feature in results['features']:
        assert feature['properties']['EVENTID'] == 'Beryl'
