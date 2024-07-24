# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#
# Copyright (c) 2024 Tom Kralidis
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
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

import copy
import gzip
import json
from http import HTTPStatus

from pyld import jsonld
import pytest
import pyproj
from shapely.geometry import Point

from pygeoapi.api import (API, FORMAT_TYPES, F_GZIP, F_HTML, F_JSONLD,
                          apply_gzip)
from pygeoapi.api.itemtypes import (
    get_collection_queryables, get_collection_item,
    get_collection_items, manage_collection_item)
from pygeoapi.util import yaml_load, get_crs_from_uri

from tests.util import get_test_file_path, mock_api_request


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


def test_get_collection_queryables(config, api_):
    req = mock_api_request()
    rsp_headers, code, response = get_collection_queryables(
        api_, req, 'notfound')
    assert code == HTTPStatus.NOT_FOUND

    req = mock_api_request()
    rsp_headers, code, response = get_collection_queryables(
        api_, req, 'mapserver_world_map')
    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'f': 'html'})
    rsp_headers, code, response = get_collection_queryables(api_, req, 'obs')
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]

    req = mock_api_request({'f': 'json'})
    rsp_headers, code, response = get_collection_queryables(api_, req, 'obs')
    assert rsp_headers['Content-Type'] == 'application/schema+json'
    queryables = json.loads(response)

    assert 'properties' in queryables
    assert len(queryables['properties']) == 5

    # test with provider filtered properties
    api_.config['resources']['obs']['providers'][0]['properties'] = ['stn_id']

    rsp_headers, code, response = get_collection_queryables(api_, req, 'obs')
    queryables = json.loads(response)

    assert 'properties' in queryables
    assert len(queryables['properties']) == 2
    assert 'geometry' in queryables['properties']
    assert queryables['properties']['geometry']['$ref'] == 'https://geojson.org/schema/Geometry.json'  # noqa

    # No language requested: should be set to default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'


def test_get_collection_items(config, api_):
    req = mock_api_request()
    rsp_headers, code, response = get_collection_items(api_, req, 'foo')
    features = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND

    req = mock_api_request({'f': 'foo'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'bbox': '1,2,3'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'bbox': '1,2,3,4c'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'bbox': '1,2,3,4', 'bbox-crs': 'bad_value'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'bbox-crs': 'bad_value'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    # bbox-crs must be in configured values for Collection
    req = mock_api_request({'bbox': '1,2,3,4', 'bbox-crs': 'http://www.opengis.net/def/crs/EPSG/0/4258'}) # noqa
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    # bbox-crs must be in configured values for Collection (CSV will ignore)
    req = mock_api_request({'bbox': '52,4,53,5', 'bbox-crs': 'http://www.opengis.net/def/crs/EPSG/0/4326'}) # noqa
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.OK

    # bbox-crs can be a default even if not configured
    req = mock_api_request({'bbox': '4,52,5,53', 'bbox-crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'}) # noqa
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.OK

    # bbox-crs can be a default even if not configured
    req = mock_api_request({'bbox': '4,52,5,53'}) # noqa
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_api_request({'f': 'html', 'lang': 'fr'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    assert rsp_headers['Content-Language'] == 'fr-CA'

    req = mock_api_request()
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)
    # No language requested: should be set to default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'

    assert len(features['features']) == 5

    req = mock_api_request({'resulttype': 'hits'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 0

    # Invalid limit
    req = mock_api_request({'limit': 0})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'stn_id': '35'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 2
    assert features['numberMatched'] == 2

    req = mock_api_request({'stn_id': '35', 'value': '93.9'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 1
    assert features['numberMatched'] == 1

    req = mock_api_request({'limit': 2})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 2
    assert features['features'][1]['properties']['stn_id'] == 35

    links = features['links']
    assert len(links) == 5
    assert '/collections/obs/items?f=json' in links[0]['href']
    assert links[0]['rel'] == 'self'
    assert '/collections/obs/items?f=jsonld' in links[1]['href']
    assert links[1]['rel'] == 'alternate'
    assert '/collections/obs/items?f=html' in links[2]['href']
    assert links[2]['rel'] == 'alternate'
    assert '/collections/obs' in links[3]['href']
    assert links[3]['rel'] == 'next'
    assert links[4]['rel'] == 'collection'

    # Invalid offset
    req = mock_api_request({'offset': -1})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'offset': 2})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 3
    assert features['features'][1]['properties']['stn_id'] == 2147

    links = features['links']
    assert len(links) == 5
    assert '/collections/obs/items?f=json' in links[0]['href']
    assert links[0]['rel'] == 'self'
    assert '/collections/obs/items?f=jsonld' in links[1]['href']
    assert links[1]['rel'] == 'alternate'
    assert '/collections/obs/items?f=html' in links[2]['href']
    assert links[2]['rel'] == 'alternate'
    assert '/collections/obs/items?offset=0' in links[3]['href']
    assert links[3]['rel'] == 'prev'
    assert '/collections/obs' in links[4]['href']
    assert links[4]['rel'] == 'collection'

    req = mock_api_request({
        'offset': 1,
        'limit': 1,
        'bbox': '-180,90,180,90'
    })
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 1

    links = features['links']
    assert len(links) == 6
    assert '/collections/obs/items?f=json&limit=1&bbox=-180,90,180,90' in \
        links[0]['href']
    assert links[0]['rel'] == 'self'
    assert '/collections/obs/items?f=jsonld&limit=1&bbox=-180,90,180,90' in \
        links[1]['href']
    assert links[1]['rel'] == 'alternate'
    assert '/collections/obs/items?f=html&limit=1&bbox=-180,90,180,90' in \
        links[2]['href']
    assert links[2]['rel'] == 'alternate'
    assert '/collections/obs/items?offset=0&limit=1&bbox=-180,90,180,90' \
        in links[3]['href']
    assert links[3]['rel'] == 'prev'
    assert '/collections/obs' in links[4]['href']
    assert links[3]['rel'] == 'prev'
    assert links[4]['rel'] == 'next'
    assert links[5]['rel'] == 'collection'

    req = mock_api_request({
        'sortby': 'bad-property',
        'stn_id': '35'
    })
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'sortby': 'stn_id'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)
    assert code == HTTPStatus.OK

    req = mock_api_request({'sortby': '+stn_id'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)
    assert code == HTTPStatus.OK

    req = mock_api_request({'sortby': '-stn_id'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')
    features = json.loads(response)
    assert code == HTTPStatus.OK

    req = mock_api_request({'f': 'csv'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert rsp_headers['Content-Type'] == 'text/csv; charset=utf-8'

    req = mock_api_request({'datetime': '2003'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_api_request({'datetime': '1999'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'datetime': '2010-04-22'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'datetime': '2001-11-11/2003-12-18'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_api_request({'datetime': '../2003-12-18'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_api_request({'datetime': '2001-11-11/..'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_api_request({'datetime': '1999/2005-04-22'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_api_request({'datetime': '1999/2000-04-22'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    api_.config['resources']['obs']['extents'].pop('temporal')

    req = mock_api_request({'datetime': '2002/2014-04-22'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_api_request({'scalerank': 1})
    rsp_headers, code, response = get_collection_items(
        api_, req, 'naturalearth/lakes')
    features = json.loads(response)

    assert len(features['features']) == 10
    assert features['numberMatched'] == 11
    assert features['numberReturned'] == 10

    req = mock_api_request({'datetime': '2005-04-22'})
    rsp_headers, code, response = get_collection_items(
        api_, req, 'naturalearth/lakes')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request({'skipGeometry': 'true'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert json.loads(response)['features'][0]['geometry'] is None

    req = mock_api_request({'properties': 'foo,bar'})
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST


def test_collection_items_gzip_csv(config, api_, openapi):
    # Add gzip to server
    config['server']['gzip'] = True
    api_ = API(config, openapi)

    req_csv = mock_api_request({'f': 'csv'})
    rsp_csv_headers, _, rsp_csv = get_collection_items(api_, req_csv, 'obs')
    rsp_csv = apply_gzip(rsp_csv_headers, rsp_csv)
    assert rsp_csv_headers['Content-Type'] == 'text/csv; charset=utf-8'
    rsp_csv = rsp_csv.decode('utf-8')

    req_csv = mock_api_request({'f': 'csv'}, HTTP_ACCEPT_ENCODING=F_GZIP)
    rsp_csv_headers, _, rsp_csv_gzip = get_collection_items(api_, req_csv, 'obs') # noqa
    rsp_csv_gzip = apply_gzip(rsp_csv_headers, rsp_csv_gzip)
    assert rsp_csv_headers['Content-Type'] == 'text/csv; charset=utf-8'
    rsp_csv_ = gzip.decompress(rsp_csv_gzip).decode('utf-8')
    assert rsp_csv == rsp_csv_

    # Use utf-16 encoding
    config['server']['encoding'] = 'utf-16'
    api_ = API(config, openapi)

    req_csv = mock_api_request({'f': 'csv'}, HTTP_ACCEPT_ENCODING=F_GZIP)
    rsp_csv_headers, _, rsp_csv_gzip = get_collection_items(api_, req_csv, 'obs') # noqa
    rsp_csv_gzip = apply_gzip(rsp_csv_headers, rsp_csv_gzip)
    assert rsp_csv_headers['Content-Type'] == 'text/csv; charset=utf-8'
    rsp_csv_ = gzip.decompress(rsp_csv_gzip).decode('utf-8')
    assert rsp_csv == rsp_csv_


def test_get_collection_items_crs(config, api_):

    # Invalid CRS query parameter
    req = mock_api_request({'crs': '4326'})
    rsp_headers, code, response = get_collection_items(api_, req, 'norway_pop')

    assert code == HTTPStatus.BAD_REQUEST

    # Unsupported CRS
    req = mock_api_request(
        {'crs': 'http://www.opengis.net/def/crs/EPSG/0/32633'})
    rsp_headers, code, response = get_collection_items(api_, req, 'norway_pop')

    assert code == HTTPStatus.BAD_REQUEST

    # Supported CRSs
    default_crs = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
    storage_crs = 'http://www.opengis.net/def/crs/EPSG/0/25833'
    crs_4258 = 'http://www.opengis.net/def/crs/EPSG/0/4258'
    supported_crs_list = [default_crs, storage_crs, crs_4258]

    for crs in supported_crs_list:
        req = mock_api_request({'crs': crs})
        rsp_headers, code, response = get_collection_items(
            api_, req, 'norway_pop')

        assert code == HTTPStatus.OK
        assert rsp_headers['Content-Crs'] == f'<{crs}>'

    # With CRS query parameter, using storageCRS
    req = mock_api_request({'crs': storage_crs})
    rsp_headers, code, response = get_collection_items(
        api_, req, 'norway_pop')

    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Crs'] == f'<{storage_crs}>'

    features_25833 = json.loads(response)

    # With CRS query parameter resulting in coordinates transformation
    req = mock_api_request({'crs': crs_4258})
    rsp_headers, code, response = get_collection_items(
        api_, req, 'norway_pop')

    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Crs'] == f'<{crs_4258}>'

    features_4258 = json.loads(response)
    transform_func = pyproj.Transformer.from_crs(
        pyproj.CRS.from_epsg(25833),
        pyproj.CRS.from_epsg(4258),
        always_xy=False,
    ).transform
    for feat_orig in features_25833['features']:
        id_ = feat_orig['id']
        x, y, *_ = feat_orig['geometry']['coordinates']
        loc_transf = Point(transform_func(x, y))
        for feat_out in features_4258['features']:
            if id_ == feat_out['id']:
                loc_out = Point(feat_out['geometry']['coordinates'][:2])

                assert loc_out.equals_exact(loc_transf, 1e-5)
                break

    # Without CRS query parameter: assume Transform to default WGS84 lon,lat
    req = mock_api_request({})
    rsp_headers, code, response = get_collection_items(
        api_, req, 'norway_pop')

    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Crs'] == f'<{default_crs}>'

    features_wgs84 = json.loads(response)

    # With CRS query parameter resulting in coordinates transformation
    transform_func = pyproj.Transformer.from_crs(
        pyproj.CRS.from_epsg(4258),
        get_crs_from_uri(default_crs),
        always_xy=False,
    ).transform
    for feat_orig in features_4258['features']:
        id_ = feat_orig['id']
        x, y, *_ = feat_orig['geometry']['coordinates']
        loc_transf = Point(transform_func(x, y))
        for feat_out in features_wgs84['features']:
            if id_ == feat_out['id']:
                loc_out = Point(feat_out['geometry']['coordinates'][:2])

                assert loc_out.equals_exact(loc_transf, 1e-5)
                break


def test_manage_collection_item_read_only_options_req(config, api_):
    """Test OPTIONS request on a read-only items endpoint"""
    req = mock_api_request()
    _, code, _ = manage_collection_item(api_, req, 'options', 'foo')
    assert code == HTTPStatus.NOT_FOUND

    req = mock_api_request()
    rsp_headers, code, _ = manage_collection_item(api_, req, 'options', 'obs')
    assert code == HTTPStatus.OK
    assert rsp_headers['Allow'] == 'HEAD, GET'

    req = mock_api_request()
    rsp_headers, code, _ = manage_collection_item(
        api_, req, 'options', 'obs', 'ressource_id')
    assert code == HTTPStatus.OK
    assert rsp_headers['Allow'] == 'HEAD, GET'


def test_manage_collection_item_editable_options_req(config, openapi):
    """Test OPTIONS request on a editable items endpoint"""
    config = copy.deepcopy(config)
    config['resources']['obs']['providers'][0]['editable'] = True
    api_ = API(config, openapi)

    req = mock_api_request()
    rsp_headers, code, _ = manage_collection_item(api_, req, 'options', 'obs')
    assert code == HTTPStatus.OK
    assert rsp_headers['Allow'] == 'HEAD, GET, POST'

    req = mock_api_request()
    rsp_headers, code, _ = manage_collection_item(
        api_, req, 'options', 'obs', 'ressource_id')
    assert code == HTTPStatus.OK
    assert rsp_headers['Allow'] == 'HEAD, GET, PUT, DELETE'


def test_get_collection_items_json_ld(config, api_):
    req = mock_api_request({
        'f': 'jsonld',
        'limit': 2
    })
    rsp_headers, code, response = get_collection_items(api_, req, 'obs')

    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSONLD]
    # No language requested: return default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'
    collection = json.loads(response)

    assert '@context' in collection
    assert all((f in collection['@context'][0] for
                f in ('schema', 'type', 'features', 'FeatureCollection')))
    assert len(collection['@context']) > 1
    assert collection['@context'][1]['schema'] == 'https://schema.org/'
    expanded = jsonld.expand(collection)[0]
    featuresUri = 'https://schema.org/itemListElement'
    assert len(expanded[featuresUri]) == 2


def test_get_collection_item(config, api_):
    req = mock_api_request({'f': 'json'})
    rsp_headers, code, response = get_collection_item(
        api_, req, 'gdps-temperature', '371')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_api_request()
    rsp_headers, code, response = get_collection_item(api_, req, 'foo', '371')

    assert code == HTTPStatus.NOT_FOUND

    rsp_headers, code, response = get_collection_item(
        api_, req, 'obs', 'notfound')

    assert code == HTTPStatus.NOT_FOUND

    req = mock_api_request({'f': 'html'})
    rsp_headers, code, response = get_collection_item(api_, req, 'obs', '371')

    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    assert rsp_headers['Content-Language'] == 'en-US'

    req = mock_api_request()
    rsp_headers, code, response = get_collection_item(api_, req, 'obs', '371')
    feature = json.loads(response)

    assert feature['properties']['stn_id'] == 35
    assert 'prev' not in feature['links']
    assert 'next' not in feature['links']


def test_get_collection_item_json_ld(config, api_):
    req = mock_api_request({'f': 'jsonld'})
    rsp_headers, _, response = get_collection_item(api_, req, 'objects', '3')
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSONLD]
    assert rsp_headers['Content-Language'] == 'en-US'
    feature = json.loads(response)
    assert '@context' in feature
    assert all((f in feature['@context'][0] for
                f in ('schema', 'type', 'gsp')))
    assert len(feature['@context']) == 1
    assert 'schema' in feature['@context'][0]
    assert feature['@context'][0]['schema'] == 'https://schema.org/'
    assert feature['id'] == 3
    expanded = jsonld.expand(feature)[0]

    assert expanded['@id'].startswith('http://')
    assert expanded['@id'].endswith('/collections/objects/items/3')
    assert expanded['http://www.opengis.net/ont/geosparql#hasGeometry'][0][
            'http://www.opengis.net/ont/geosparql#asWKT'][0][
            '@value'] == 'POINT (-85 33)'
    assert expanded['https://schema.org/geo'][0][
            'https://schema.org/latitude'][0][
            '@value'] == 33
    assert expanded['https://schema.org/geo'][0][
            'https://schema.org/longitude'][0][
            '@value'] == -85

    _, _, response = get_collection_item(api_, req, 'objects', '2')
    feature = json.loads(response)
    assert feature['geometry']['type'] == 'MultiPoint'
    expanded = jsonld.expand(feature)[0]
    assert expanded['http://www.opengis.net/ont/geosparql#hasGeometry'][0][
            'http://www.opengis.net/ont/geosparql#asWKT'][0][
            '@value'] == 'MULTIPOINT (10 40, 40 30, 20 20, 30 10)'
    assert expanded['https://schema.org/geo'][0][
            'https://schema.org/polygon'][0][
            '@value'] == "10.0,40.0 40.0,30.0 20.0,20.0 30.0,10.0 10.0,40.0"

    _, _, response = get_collection_item(api_, req, 'objects', '1')
    feature = json.loads(response)
    expanded = jsonld.expand(feature)[0]
    assert expanded['http://www.opengis.net/ont/geosparql#hasGeometry'][0][
            'http://www.opengis.net/ont/geosparql#asWKT'][0][
            '@value'] == 'LINESTRING (30 10, 10 30, 40 40)'
    assert expanded['https://schema.org/geo'][0][
            'https://schema.org/line'][0][
            '@value'] == '30.0,10.0 10.0,30.0 40.0,40.0'

    _, _, response = get_collection_item(api_, req, 'objects', '4')
    feature = json.loads(response)
    expanded = jsonld.expand(feature)[0]
    assert expanded['http://www.opengis.net/ont/geosparql#hasGeometry'][0][
            'http://www.opengis.net/ont/geosparql#asWKT'][0][
            '@value'] == 'MULTILINESTRING ((10 10, 20 20, 10 40), ' \
        '(40 40, 30 30, 40 20, 30 10))'
    assert expanded['https://schema.org/geo'][0][
            'https://schema.org/line'][0][
            '@value'] == '10.0,10.0 20.0,20.0 10.0,40.0 40.0,40.0 ' \
        '30.0,30.0 40.0,20.0 30.0,10.0'

    _, _, response = get_collection_item(api_, req, 'objects', '5')
    feature = json.loads(response)
    expanded = jsonld.expand(feature)[0]
    assert expanded['http://www.opengis.net/ont/geosparql#hasGeometry'][0][
            'http://www.opengis.net/ont/geosparql#asWKT'][0][
            '@value'] == 'POLYGON ((30 10, 40 40, 20 40, 10 20, 30 10))'
    assert expanded['https://schema.org/geo'][0][
            'https://schema.org/polygon'][0][
            '@value'] == '30.0,10.0 40.0,40.0 20.0,40.0 10.0,20.0 30.0,10.0'

    _, _, response = get_collection_item(api_, req, 'objects', '7')
    feature = json.loads(response)
    expanded = jsonld.expand(feature)[0]
    assert expanded['http://www.opengis.net/ont/geosparql#hasGeometry'][0][
            'http://www.opengis.net/ont/geosparql#asWKT'][0][
            '@value'] == 'MULTIPOLYGON (((30 20, 45 40, 10 40, 30 20)), '\
        '((15 5, 40 10, 10 20, 5 10, 15 5)))'
    assert expanded['https://schema.org/geo'][0][
            'https://schema.org/polygon'][0][
            '@value'] == '15.0,5.0 5.0,10.0 10.0,40.0 '\
        '45.0,40.0 40.0,10.0 15.0,5.0'

    req = mock_api_request({'f': 'jsonld', 'lang': 'fr'})
    rsp_headers, code, response = get_collection_item(api_, req, 'obs', '371')
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSONLD]
    assert rsp_headers['Content-Language'] == 'fr-CA'
