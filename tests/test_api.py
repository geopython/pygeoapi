# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
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

import json
import os
import logging

from pyld import jsonld
import pytest
from werkzeug.test import create_environ
from werkzeug.wrappers import Request
from pygeoapi.api import API, check_async, check_format, validate_bbox, validate_datetime
from pygeoapi.util import yaml_load

LOGGER = logging.getLogger(__name__)


def get_test_file_path(filename):
    """helper function to open test file safely"""

    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


def make_req_headers(**kwargs):
    environ = create_environ('/collections/obs/items',
                             'http:/localhost:5000/')
    environ.update(kwargs)
    request = Request(environ)
    return request.headers


def make_lakes_req_headers(**kwargs):
    environ = create_environ('/collections/lakes/items',
                             'http://localhost:5000/')
    environ.update(kwargs)
    request = Request(environ)
    return request.headers


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def openapi():
    with open(get_test_file_path('pygeoapi-test-openapi.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def api_(config):
    return API(config)


def test_api(config, api_, openapi):
    assert api_.config == config
    assert isinstance(api_.config, dict)

    req_headers = make_req_headers(HTTP_CONTENT_TYPE='application/json')
    rsp_headers, code, response = api_.openapi(req_headers, {}, openapi)
    assert rsp_headers['Content-Type'] ==\
        'application/vnd.oai.openapi+json;version=3.0'
    root = json.loads(response)

    assert isinstance(root, dict)

    a = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    req_headers = make_req_headers(HTTP_ACCEPT=a)
    rsp_headers, code, response = api_.openapi(req_headers, {}, openapi)
    assert rsp_headers['Content-Type'] == 'text/html'

    req_headers = make_req_headers()
    rsp_headers, code, response = api_.openapi(req_headers, {'f': 'foo'},
                                               openapi)
    assert code == 400


def test_api_exception(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.landing_page(req_headers, {'f': 'foo'})
    assert code == 400


def test_root(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.landing_page(req_headers, {})
    root = json.loads(response)

    assert rsp_headers['Content-Type'] == 'application/json'
    assert rsp_headers['X-Powered-By'].startswith('pygeoapi')

    assert isinstance(root, dict)
    assert 'links' in root
    assert root['links'][0]['rel'] == 'self'
    assert root['links'][0]['type'] == 'application/json'
    assert root['links'][0]['href'].endswith('?f=json')
    assert any(link['href'].endswith('f=jsonld') and link['rel'] == 'alternate'
               for link in root['links'])
    assert any(link['href'].endswith('f=html') and link['rel'] == 'alternate'
               for link in root['links'])
    assert len(root['links']) == 7
    assert 'title' in root
    assert root['title'] == 'pygeoapi default instance'
    assert 'description' in root
    assert root['description'] == 'pygeoapi provides an API to geospatial data'

    rsp_headers, code, response = api_.landing_page(req_headers, {'f': 'html'})
    assert rsp_headers['Content-Type'] == 'text/html'


def test_root_structured_data(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.landing_page(
        req_headers, {"f": "jsonld"})
    root = json.loads(response)

    assert rsp_headers['Content-Type'] == 'application/ld+json'
    assert rsp_headers['X-Powered-By'].startswith('pygeoapi')

    assert isinstance(root, dict)
    assert 'description' in root
    assert root['description'] == 'pygeoapi provides an API to geospatial data'

    assert '@context' in root
    assert root['@context'] == 'https://schema.org/docs/jsonldcontext.jsonld'
    expanded = jsonld.expand(root)[0]
    assert '@type' in expanded
    assert 'http://schema.org/DataCatalog' in expanded['@type']
    assert 'http://schema.org/description' in expanded
    assert root['description'] == expanded['http://schema.org/description'][0][
        '@value']
    assert 'http://schema.org/keywords' in expanded
    assert len(expanded['http://schema.org/keywords']) == 3
    assert '@value' in expanded['http://schema.org/keywords'][0].keys()
    assert 'http://schema.org/provider' in expanded
    assert expanded['http://schema.org/provider'][0]['@type'][
        0] == 'http://schema.org/Organization'
    assert expanded['http://schema.org/name'][0]['@value'] == root['name']


def test_conformance(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.conformance(req_headers, {})
    root = json.loads(response)

    assert isinstance(root, dict)
    assert 'conformsTo' in root
    assert len(root['conformsTo']) == 9

    rsp_headers, code, response = api_.conformance(req_headers, {'f': 'foo'})
    assert code == 400

    rsp_headers, code, response = api_.conformance(req_headers, {'f': 'html'})
    assert rsp_headers['Content-Type'] == 'text/html'


def test_describe_collections(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.describe_collections(
        req_headers, {'f': 'foo'})
    assert code == 400

    req_headers = make_req_headers()
    rsp_headers, code, response = api_.describe_collections(
        req_headers, {'f': 'html'})
    assert rsp_headers['Content-Type'] == 'text/html'

    rsp_headers, code, response = api_.describe_collections(req_headers, {})
    collections = json.loads(response)

    assert len(collections) == 2
    assert len(collections['collections']) == 4
    assert len(collections['links']) == 3

    rsp_headers, code, response = api_.describe_collections(
        req_headers, {}, 'foo')
    collection = json.loads(response)

    assert code == 400

    rsp_headers, code, response = api_.describe_collections(
        req_headers, {}, 'obs')
    collection = json.loads(response)

    assert collection['id'] == 'obs'
    assert collection['title'] == 'Observations'
    assert collection['description'] == 'My cool observations'
    assert len(collection['links']) == 10
    assert collection['extent'] == {
        'spatial': {
            'bbox': [[-180, -90, 180, 90]],
            'crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
        },
        'temporal': {
            'interval': [
                ['2000-10-30T18:24:39+00:00', '2007-10-30T08:57:29+00:00']
            ],
            'trs': 'http://www.opengis.net/def/uom/ISO-8601/0/Gregorian'
        }
    }

    rsp_headers, code, response = api_.describe_collections(
        req_headers, {'f': 'html'}, 'obs')
    assert rsp_headers['Content-Type'] == 'text/html'

    rsp_headers, code, response = api_.describe_collections(
        req_headers, {}, 'gdps-temperature')
    collection = json.loads(response)

    assert collection['id'] == 'gdps-temperature'
    assert len(collection['links']) == 12


def test_get_collection_queryables(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.get_collection_queryables(
        req_headers, {}, 'notfound')
    assert code == 400

    req_headers = make_req_headers()
    rsp_headers, code, response = api_.get_collection_queryables(
        req_headers, {'f': 'html'}, 'obs')
    assert rsp_headers['Content-Type'] == 'text/html'

    rsp_headers, code, response = api_.get_collection_queryables(
        req_headers, {'f': 'json'}, 'obs')
    queryables = json.loads(response)

    assert 'queryables' in queryables
    assert len(queryables['queryables']) == 6

    # test with provider filtered properties
    api_.config['resources']['obs']['providers'][0]['properties'] = ['stn_id']

    rsp_headers, code, response = api_.get_collection_queryables(
        req_headers, {'f': 'json'}, 'obs')
    queryables = json.loads(response)

    assert 'queryables' in queryables
    assert len(queryables['queryables']) == 1


def test_describe_collections_json_ld(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.describe_collections(
        req_headers, {'f': 'jsonld'}, 'obs')
    collection = json.loads(response)

    assert '@context' in collection
    expanded = jsonld.expand(collection)[0]
    # Metadata is about a schema:DataCollection that contains a schema:Dataset
    assert not expanded['@id'].endswith('obs')
    assert 'http://schema.org/dataset' in expanded
    assert len(expanded['http://schema.org/dataset']) == 1
    dataset = expanded['http://schema.org/dataset'][0]
    assert dataset['@type'][0] == 'http://schema.org/Dataset'
    assert len(dataset['http://schema.org/distribution']) == 10
    assert all(dist['@type'][0] == 'http://schema.org/DataDownload'
               for dist in dataset['http://schema.org/distribution'])

    assert 'http://schema.org/Organization' in expanded[
        'http://schema.org/provider'][0]['@type']

    assert 'http://schema.org/Place' in dataset[
        'http://schema.org/spatial'][0]['@type']
    assert 'http://schema.org/GeoShape' in dataset[
        'http://schema.org/spatial'][0]['http://schema.org/geo'][0]['@type']
    assert dataset['http://schema.org/spatial'][0]['http://schema.org/geo'][
        0]['http://schema.org/box'][0]['@value'] == '-180,-90 180,90'

    assert 'http://schema.org/temporalCoverage' in dataset
    assert dataset['http://schema.org/temporalCoverage'][0][
        '@value'] == '2000-10-30T18:24:39+00:00/2007-10-30T08:57:29+00:00'


def test_get_collection_items(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {}, 'foo')
    features = json.loads(response)

    assert code == 400

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'f': 'foo'}, 'obs')
    features = json.loads(response)

    assert code == 400

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'bbox': '1,2,3'}, 'obs')
    features = json.loads(response)

    assert code == 400

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'bbox': '1,2,3,4c'}, 'obs')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'f': 'html'}, 'obs')
    assert rsp_headers['Content-Type'] == 'text/html'

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {}, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 5

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'resulttype': 'hits'}, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 0

    # Invalid limit
    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'limit': 0}, 'obs')
    features = json.loads(response)

    assert code == 400

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'limit': 2}, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 2
    assert features['features'][1]['properties']['stn_id'] == '35'

    links = features['links']
    assert len(links) == 5
    assert '/collections/obs/items?f=json' in links[0]['href']
    assert links[0]['rel'] == 'self'
    assert '/collections/obs/items?f=jsonld' in links[1]['href']
    assert links[1]['rel'] == 'alternate'
    assert '/collections/obs/items?f=html' in links[2]['href']
    assert links[2]['rel'] == 'alternate'
    assert '/collections/obs/items?startindex=2&limit=2' in links[3]['href']
    assert links[3]['rel'] == 'next'
    assert '/collections/obs' in links[4]['href']
    assert links[4]['rel'] == 'collection'

    # Invalid startindex
    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'startindex': -1}, 'obs')
    features = json.loads(response)

    assert code == 400

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'startindex': 2}, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 3
    assert features['features'][1]['properties']['stn_id'] == '2147'

    links = features['links']
    assert len(links) == 5
    assert '/collections/obs/items?f=json' in links[0]['href']
    assert links[0]['rel'] == 'self'
    assert '/collections/obs/items?f=jsonld' in links[1]['href']
    assert links[1]['rel'] == 'alternate'
    assert '/collections/obs/items?f=html' in links[2]['href']
    assert links[2]['rel'] == 'alternate'
    assert '/collections/obs/items?startindex=0' in links[3]['href']
    assert links[3]['rel'] == 'prev'
    assert '/collections/obs' in links[4]['href']
    assert links[4]['rel'] == 'collection'

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {
            'startindex': 1,
            'limit': 1,
            'bbox': '-180,90,180,90'
        }, 'obs')
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
    assert '/collections/obs/items?startindex=0&limit=1&bbox=-180,90,180,90' \
        in links[3]['href']
    assert links[3]['rel'] == 'prev'
    assert '/collections/obs/items?startindex=2&limit=1&bbox=-180,90,180,90' \
        in links[4]['href']
    assert links[4]['rel'] == 'next'
    assert '/collections/obs' in links[5]['href']
    assert links[5]['rel'] == 'collection'

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {
            'sortby': 'bad-property',
            'stn_id': '35'
        }, 'obs')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {
            'sortby': 'stn_id:FOO',
            'stn_id': '35',
            'value': '89.9'
        }, 'obs')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'sortby': 'stn_id:A'}, 'obs')
    features = json.loads(response)
    # FIXME? this test errors out currently
    assert code == 200

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'f': 'csv'}, 'obs')

    assert rsp_headers['Content-Type'] == 'text/csv; charset=utf-8'

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'datetime': '2003'}, 'obs')

    assert code == 200

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'datetime': '1999'}, 'obs')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'datetime': '2010-04-22'}, 'obs')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'datetime': '2001-11-11/2003-12-18'}, 'obs')

    assert code == 200

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'datetime': '../2003-12-18'}, 'obs')

    assert code == 200

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'datetime': '2001-11-11/..'}, 'obs')

    assert code == 200

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'datetime': '1999/2005-04-22'}, 'obs')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'datetime': '2002/2014-04-22'}, 'obs')

    api_.config['resources']['obs']['extents'].pop('temporal')

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'datetime': '2002/2014-04-22'}, 'obs')

    assert code == 200

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'skipGeometry': 'true'}, 'obs')

    assert json.loads(response)['features'][0]['geometry'] is None

    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {'properties': 'foo,bar'}, 'obs')

    assert code == 400


def test_get_collection_items_json_ld(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.get_collection_items(
        req_headers, {
            'f': 'jsonld',
            'limit': 2
        }, 'obs')
    assert rsp_headers['Content-Type'] == 'application/ld+json'
    collection = json.loads(response)

    assert '@context' in collection
    assert collection['@context'][
        0] == 'https://geojson.org/geojson-ld/geojson-context.jsonld'
    assert len(collection['@context']) > 1
    assert 'schema' in collection['@context'][1]
    assert collection['@context'][1]['schema'] == 'https://schema.org/'
    expanded = jsonld.expand(collection)[0]
    featuresUri = 'https://purl.org/geojson/vocab#features'
    assert len(expanded[featuresUri]) == 2
    geometryUri = 'https://purl.org/geojson/vocab#geometry'
    assert all((geometryUri in f) for f in expanded[featuresUri])
    assert all((f[geometryUri][0]['@type'][0] ==
                'https://purl.org/geojson/vocab#Point')
               for f in expanded[featuresUri])
    propertiesUri = 'https://purl.org/geojson/vocab#properties'
    assert all(propertiesUri in f for f in expanded[featuresUri])
    assert all(
        len(f[propertiesUri][0].keys()) > 0 for f in expanded[featuresUri])
    assert all(('https://schema.org/observationDate' in f[propertiesUri][0])
               for f in expanded[featuresUri])
    assert all((f[propertiesUri][0]['https://schema.org/observationDate'][0][
        '@type'] == 'https://schema.org/DateTime')
               for f in expanded[featuresUri])
    assert any((f[propertiesUri][0]['https://schema.org/observationDate'][0][
        '@value'] == '2001-10-30T14:24:55Z') for f in expanded[featuresUri])


def test_get_collection_item(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.get_collection_item(
        req_headers, {'f': 'foo'}, 'obs', '371')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_item(
        req_headers, {'f': 'json'}, 'gdps-temperature', '371')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_item(
        req_headers, {}, 'foo', '371')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_item(
        req_headers, {}, 'obs', 'notfound')

    assert code == 404

    rsp_headers, code, response = api_.get_collection_item(
        req_headers, {'f': 'html'}, 'obs', '371')

    assert rsp_headers['Content-Type'] == 'text/html'

    rsp_headers, code, response = api_.get_collection_item(
        req_headers, {}, 'obs', '371')
    feature = json.loads(response)

    assert feature['properties']['stn_id'] == '35'


def test_get_collection_item_json_ld(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.get_collection_item(
        req_headers, {'f': 'jsonld'}, 'obs', '371')
    assert rsp_headers['Content-Type'] == 'application/ld+json'
    feature = json.loads(response)
    assert '@context' in feature
    assert feature['@context'][
        0] == 'https://geojson.org/geojson-ld/geojson-context.jsonld'
    assert len(feature['@context']) > 1
    assert 'schema' in feature['@context'][1]
    assert feature['@context'][1]['schema'] == 'https://schema.org/'
    assert feature['properties']['stn_id'] == '35'
    assert feature['id'].startswith('http://')
    assert feature['id'].endswith('/collections/obs/items/371')
    expanded = jsonld.expand(feature)[0]
    assert expanded['@id'].startswith('http://')
    assert expanded['@id'].endswith('/collections/obs/items/371')
    assert expanded['https://purl.org/geojson/vocab#properties'][0][
        'https://schema.org/identifier'][0][
            '@type'] == 'https://schema.org/Text'
    assert expanded['https://purl.org/geojson/vocab#properties'][0][
        'https://schema.org/identifier'][0]['@value'] == '35'


def test_get_coverage_domainset(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.get_collection_coverage_domainset(
        req_headers, {}, 'obs')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_coverage_domainset(
        req_headers, {}, 'gdps-temperature')

    domainset = json.loads(response)

    assert domainset['type'] == 'DomainSetType'
    assert domainset['generalGrid']['axisLabels'] == ['Long', 'Lat']
    assert domainset['generalGrid']['gridLimits']['axisLabels'] == ['i', 'j']
    assert domainset['generalGrid']['gridLimits']['axis'][0]['upperBound'] == 2400  # noqa
    assert domainset['generalGrid']['gridLimits']['axis'][1]['upperBound'] == 1201  # noqa


def test_get_collection_coverage_rangetype(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.get_collection_coverage_rangetype(
        req_headers, {}, 'obs')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_coverage_rangetype(
        req_headers, {}, 'gdps-temperature')

    rangetype = json.loads(response)

    assert rangetype['type'] == 'DataRecordType'
    assert len(rangetype['field']) == 1
    assert rangetype['field'][0]['id'] == 1
    assert rangetype['field'][0]['name'] == 'Temperature [C]'
    assert rangetype['field'][0]['uom']['code'] == '[C]'


def test_get_collection_coverage(config, api_):
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.get_collection_coverage(
        req_headers, {}, 'obs')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_coverage(
        req_headers, {'rangeSubset': '12'}, 'gdps-temperature')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_coverage(
        req_headers, {'subset': 'bad_axis(10:20)'}, 'gdps-temperature')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_coverage(
        req_headers, {'f': 'blah'}, 'gdps-temperature')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_coverage(
        req_headers, {'subset': 'Lat(5:10),Long(5:10)'}, 'gdps-temperature')

    assert code == 200
    content = json.loads(response)

    assert content['domain']['axes']['x']['num'] == 35
    assert content['domain']['axes']['y']['num'] == 35
    assert 'TMP' in content['parameters']
    assert 'TMP' in content['ranges']
    assert content['ranges']['TMP']['axisNames'] == ['y', 'x']

    rsp_headers, code, response = api_.get_collection_coverage(
        req_headers, {'bbox': '-79,45,-75,49'}, 'gdps-temperature')

    assert code == 200
    content = json.loads(response)

    assert content['domain']['axes']['x']['start'] == -79.0
    assert content['domain']['axes']['x']['stop'] == -75.0
    assert content['domain']['axes']['y']['start'] == 49.0
    assert content['domain']['axes']['y']['stop'] == 45.0

    rsp_headers, code, response = api_.get_collection_coverage(
        req_headers, {'subset': 'Lat(5:10),Long(5:10)', 'f': 'GRIB'},
        'gdps-temperature')

    assert code == 200
    assert isinstance(response, bytes)

    rsp_headers, code, response = api_.get_collection_coverage(
        req_headers, {'subset': 'time("2006-07-01T06:00:00":"2007-07-01T06:00:00")'}, 'cmip5')  # noqa

    assert code == 200
    assert isinstance(json.loads(response), dict)

    rsp_headers, code, response = api_.get_collection_coverage(
        req_headers, {'subset': 'lat(1:2'}, 'cmip5')

    assert code == 400

    rsp_headers, code, response = api_.get_collection_coverage(
        req_headers, {'subset': 'lat(1:2)'}, 'cmip5')

    assert code == 204


def test_get_collection_tiles(config, api_):
    req_headers = make_lakes_req_headers()
    rsp_headers, code, response = api_.get_collection_tiles(
        req_headers, {}, 'obs')

    assert code == 400

    req_headers = make_lakes_req_headers()
    rsp_headers, code, response = api_.get_collection_tiles(
        req_headers, {}, 'lakes')

    assert code == 200


def test_describe_processes(config, api_):
    req_headers = make_req_headers()

    # Test for undefined process
    rsp_headers, code, response = api_.describe_processes(
        req_headers, {}, 'foo')
    data = json.loads(response)
    assert code == 404
    assert data['code'] == 'NoSuchProcess'

    # Test for description of all processes
    rsp_headers, code, response = api_.describe_processes(
        req_headers, {})
    data = json.loads(response)
    assert code == 200
    assert len(data['processes']) == 1

    # Test for particular, defined procss
    rsp_headers, code, response = api_.describe_processes(
        req_headers, {}, 'hello-world')
    process = json.loads(response)
    assert code == 200
    assert rsp_headers['Content-Type'] == 'application/json'
    assert process['id'] == 'hello-world'
    assert process['version'] == '0.2.0'
    assert process['title'] == 'Hello World'
    assert len(process['keywords']) == 3
    assert len(process['links']) == 2
    assert len(process['inputs']) == 2
    assert len(process['outputs']) == 1
    assert len(process['outputTransmission']) == 1
    assert len(process['jobControlOptions']) == 2
    assert 'sync-execute' in process['jobControlOptions']
    assert 'async-execute' in process['jobControlOptions']

    # Check HTML response when requested in headers
    req_headers = make_req_headers(HTTP_ACCEPT='text/html')
    rsp_headers, code, response = api_.describe_processes(
        req_headers, {}, 'hello-world')
    assert code == 200
    assert rsp_headers['Content-Type'] == 'text/html'

    # Check JSON response when requested in headers
    req_headers = make_req_headers(HTTP_ACCEPT='application/json')
    rsp_headers, code, response = api_.describe_processes(
        req_headers, {}, 'hello-world')
    assert code == 200
    assert rsp_headers['Content-Type'] == 'application/json'

    # Check HTML response when requested with query parameter
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.describe_processes(
        req_headers, {'f': 'html'}, 'hello-world')
    assert code == 200
    assert rsp_headers['Content-Type'] == 'text/html'

    # Check JSON response when requested with query parameter
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.describe_processes(
        req_headers, {'f': 'json'}, 'hello-world')
    assert code == 200
    assert rsp_headers['Content-Type'] == 'application/json'

    # Test for undefined process
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.describe_processes(
        req_headers, {}, 'goodbye-world')
    data = json.loads(response)
    assert code == 404
    assert data['code'] == 'NoSuchProcess'
    assert rsp_headers['Content-Type'] == 'application/json'

def test_execute_process(config, api_):
    req_headers = make_req_headers()
    req_body = {
        'inputs': [{
            'id': 'name',
            'value': 'Test'
        }]
    }
    req_body_2 = {
        'inputs': [{
            'id': 'name',
            'value': 'Tést'
        }]
    }
    req_body_3 = {
        'inputs': [{
            'id': 'name',
            'value': 'Tést'
        }, {
            'id': 'message',
            'value': 'This is a test.'
        }]
    }
    req_body_4 = {
        'inputs': [{
            'id': 'foo',
            'value': 'Tést'
        }]
    }
    req_body_5 = {
        'inputs': []
    }
    req_body_6 = {
        'inputs': [{
            'id': 'name',
            'value': None
        }]
    }
    req_body_7 = {
        'inputs': [{
            'id': 'name'
        }]
    }
    req_body_8 = {
        'inputs': [{
            'value': 'Test'
        }]
    }

    # Test posting empty payload to existing process
    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, '', 'hello-world')
    data = json.loads(response)
    assert code == 400
    assert 'Location' not in rsp_headers
    assert data['code'] == 'MissingParameterValue'

    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, json.dumps(req_body), 'foo')
    data = json.loads(response)
    assert code == 404
    assert 'Location' not in rsp_headers
    assert data['code'] == 'NoSuchProcess'

    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, json.dumps(req_body), 'hello-world')
    data = json.loads(response)
    assert code == 200
    assert 'Location' in rsp_headers
    assert len(data['outputs']) == 1
    assert data['outputs'][0]['id'] == 'echo'
    assert data['outputs'][0]['value'] == 'Hello Test!'

    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, json.dumps(req_body_2), 'hello-world')
    data = json.loads(response)
    assert code == 200
    assert 'Location' in rsp_headers
    assert data['outputs'][0]['value'] == 'Hello Tést!'

    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, json.dumps(req_body_3), 'hello-world')
    data = json.loads(response)
    assert code == 200
    assert 'Location' in rsp_headers
    assert data['outputs'][0]['value'] == 'Hello Tést! This is a test.'

    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, json.dumps(req_body_4), 'hello-world')
    data = json.loads(response)
    assert code == 200
    assert 'Location' in rsp_headers
    assert data['code'] == 'InvalidParameterValue'
    # TODO inspect Location URI and asset 400 status

    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, json.dumps(req_body_5), 'hello-world')
    data = json.loads(response)
    assert code == 200
    assert 'Location' in rsp_headers
    assert data['code'] == 'InvalidParameterValue'
    # TODO inspect Location URI and asset 400 status

    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, json.dumps(req_body_6), 'hello-world')
    data = json.loads(response)
    assert code == 200
    assert 'Location' in rsp_headers
    assert data['code'] == 'InvalidParameterValue'
    assert data['description'] == 'Cannot process without a name'

    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, json.dumps(req_body_7), 'hello-world')
    data = json.loads(response)
    assert code == 400
    assert 'Location' not in rsp_headers
    assert data['code'] == 'InvalidParameterValue'
    assert data['description'] == 'invalid request data'

    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, json.dumps(req_body_8), 'hello-world')
    data = json.loads(response)
    assert code == 400
    assert 'Location' not in rsp_headers
    assert data['code'] == 'InvalidParameterValue'
    assert data['description'] == 'invalid request data'
    req_headers = make_req_headers()
    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, json.dumps(req_body), 'goodbye-world')
    response = json.loads(response)
    assert code == 404
    assert 'Location' not in rsp_headers
    assert response['code'] == 'NoSuchProcess'

    req_headers = make_req_headers()
    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {'sync-execute': 'True'}, json.dumps(req_body), 'hello-world')
    response = json.loads(response)
    assert code == 200

    req_headers = make_req_headers()
    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {'async-execute': 'True'}, json.dumps(req_body), 'hello-world')
    assert 'Location' in rsp_headers
    assert response == ''
    assert code == 202

    # TODO clean up test data?

def test_check_format():
    args = {'f': 'html'}

    req_headers = {}

    assert check_format({}, req_headers) is None

    assert check_format(args, req_headers) == 'html'

    args['f'] = 'json'
    assert check_format(args, req_headers) == 'json'

    args['f'] = 'jsonld'
    assert check_format(args, req_headers) == 'jsonld'

    args['f'] = 'html'
    assert check_format(args, req_headers) == 'html'

    req_headers['Accept'] = 'text/html'
    assert check_format({}, req_headers) == 'html'

    req_headers['Accept'] = 'application/json'
    assert check_format({}, req_headers) == 'json'

    req_headers['Accept'] = 'application/ld+json'
    assert check_format({}, req_headers) == 'jsonld'

    req_headers['accept'] = 'text/html'
    assert check_format({}, req_headers) == 'html'

    hh = 'text/html,application/xhtml+xml,application/xml;q=0.9,'

    req_headers['Accept'] = hh
    assert check_format({}, req_headers) == 'html'

    req_headers['accept'] = hh
    assert check_format({}, req_headers) == 'html'

    req_headers = make_req_headers(HTTP_ACCEPT=hh)
    assert check_format({}, req_headers) == 'html'

    req_headers = make_req_headers(HTTP_ACCEPT='text/html')
    assert check_format({}, req_headers) == 'html'

    req_headers = make_req_headers(HTTP_ACCEPT='application/json')
    assert check_format({}, req_headers) == 'json'

    req_headers = make_req_headers(HTTP_ACCEPT='application/ld+json')
    assert check_format({}, req_headers) == 'jsonld'

    # Overrule HTTP content negotiation
    args['f'] = 'html'
    assert check_format(args, req_headers) == 'html'

    req_headers = make_req_headers(HTTP_ACCEPT='text/html')
    args['f'] = 'json'
    assert check_format(args, req_headers) == 'json'

def test_check_async():
    args = {}
    req_headers = {}

    assert check_async(args, req_headers) is False

    args['f'] = 'html'
    assert check_async(args, req_headers) is False

    args['sync-execute'] = 'True'
    assert check_async(args, req_headers) is False

    req_headers['async-execute'] = 'True'
    assert check_async(args, req_headers) is False # Args precede headers

    args['async-execute'] = 'True'
    assert check_async(args, req_headers) is True # Async precedes sync

    args = {}
    req_headers['async-execute'] = 'True'
    assert check_async(args, req_headers) is True

    req_headers['sync-execute'] = 'True'
    assert check_async(args, req_headers) is True # Async precedes sync

    args['async-execute'] = 'True'
    args['sync-execute'] = 'True'
    assert check_async(args, req_headers) is True # Async precedes sync

    args['async-execute'] = 'True'
    args['sync-execute'] = 'False'
    req_headers['async-execute'] = 'True'
    req_headers['sync-execute'] = 'False'
    assert check_async(args, req_headers) is True


def test_delete_job(api_):
    rsp_headers, code, response = api_.delete_job('does-not-exist', 'does-not-exist')
    assert code == 404

    req_headers = make_req_headers()
    req_body = {
        'inputs': [{
            'id': 'name',
            'value': 'Test Deletion'
        }]
    }

    rsp_headers, code, response = api_.execute_process(
        'POST', req_headers, {}, json.dumps(req_body), 'hello-world')
    data = json.loads(response)
    assert code == 200
    assert 'Location' in rsp_headers
    assert data['outputs'][0]['value'] == 'Hello Test Deletion!'

    job_id = rsp_headers['Location'].split('/')[-1]
    rsp_headers, code, response = api_.delete_job('hello-world', job_id)
    assert code == 204

    rsp_headers, code, response = api_.delete_job('hello-world', job_id)
    assert code == 404

def test_validate_bbox():
    assert validate_bbox('1,2,3,4') == [1, 2, 3, 4]
    assert validate_bbox('-142,42,-52,84') == [-142, 42, -52, 84]
    assert (validate_bbox('-142.1,42.12,-52.22,84.4') ==
            [-142.1, 42.12, -52.22, 84.4])

    with pytest.raises(ValueError):
        validate_bbox('1,2,4')

    with pytest.raises(ValueError):
        validate_bbox('3,4,1,2')


def test_validate_datetime():
    config = yaml_load('''
        temporal:
            begin: 2000-10-30T18:24:39Z
            end: 2007-10-30T08:57:29Z
    ''')

    # test time instant
    assert validate_datetime(config, '2004') == '2004'
    assert validate_datetime(config, '2004-10') == '2004-10'
    assert validate_datetime(config, '2001-10-30') == '2001-10-30'

    with pytest.raises(ValueError):
        _ = validate_datetime(config, '2009-10-30')
    with pytest.raises(ValueError):
        _ = validate_datetime(config, '2000-09-09')
    with pytest.raises(ValueError):
        _ = validate_datetime(config, '2000-10-30T17:24:39Z')
    with pytest.raises(ValueError):
        _ = validate_datetime(config, '2007-10-30T08:58:29Z')

    # test time envelope
    assert validate_datetime(config, '2004/2005') == '2004/2005'
    assert validate_datetime(config, '2004-10/2005-10') == '2004-10/2005-10'
    assert (validate_datetime(config, '2001-10-30/2002-10-30') ==
            '2001-10-30/2002-10-30')
    assert validate_datetime(config, '2004/..') == '2004/..'
    assert validate_datetime(config, '../2005') == '../2005'
    assert validate_datetime(config, '2004-10/2005-10') == '2004-10/2005-10'
    assert (validate_datetime(config, '2001-10-30/2002-10-30') ==
            '2001-10-30/2002-10-30')

    with pytest.raises(ValueError):
        _ = validate_datetime(config, '1999/..')
    with pytest.raises(ValueError):
        _ = validate_datetime(config, '../2010')
