# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#
# Copyright (c) 2023 Tom Kralidis
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

import json
import logging
import time
import gzip
from http import HTTPStatus

from pyld import jsonld
import pytest
from pygeoapi.api import (
    API, APIRequest, FORMAT_TYPES, validate_bbox, validate_datetime,
    validate_subset, F_HTML, F_JSON, F_JSONLD, F_GZIP
)
from pygeoapi.util import yaml_load

from .util import get_test_file_path, mock_request

LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def config_hidden_resources():
    filename = 'pygeoapi-test-config-hidden-resources.yml'
    with open(get_test_file_path(filename)) as fh:
        return yaml_load(fh)


@pytest.fixture()
def openapi():
    with open(get_test_file_path('pygeoapi-test-openapi.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def api_(config):
    return API(config)


@pytest.fixture()
def api_hidden_resources(config_hidden_resources):
    return API(config_hidden_resources)


# API using PostgreSQL provider
@pytest.fixture()
def pg_api_():
    with open(get_test_file_path('pygeoapi-test-config-postgresql.yml')) as fh:
        config = yaml_load(fh)
        return API(config)


def test_apirequest(api_):
    # Test without (valid) locales
    with pytest.raises(ValueError):
        req = mock_request()
        APIRequest(req, [])
        APIRequest(req, None)
        APIRequest(req, ['zz'])

    # Test all supported formats from query args
    for f, mt in FORMAT_TYPES.items():
        req = mock_request({'f': f})
        apireq = APIRequest(req, api_.locales)
        assert apireq.is_valid()
        assert apireq.format == f
        assert apireq.get_response_headers()['Content-Type'] == mt

    # Test all supported formats from Accept header
    for f, mt in FORMAT_TYPES.items():
        req = mock_request(HTTP_ACCEPT=mt)
        apireq = APIRequest(req, api_.locales)
        assert apireq.is_valid()
        assert apireq.format == f
        assert apireq.get_response_headers()['Content-Type'] == mt

    # Test nonsense format
    req = mock_request({'f': 'foo'})
    apireq = APIRequest(req, api_.locales)
    assert not apireq.is_valid()
    assert apireq.format == 'foo'
    assert apireq.is_valid(('foo',))
    assert apireq.get_response_headers()['Content-Type'] == \
           FORMAT_TYPES[F_JSON]

    # Test without format
    req = mock_request()
    apireq = APIRequest(req, api_.locales)
    assert apireq.is_valid()
    assert apireq.format is None
    assert apireq.get_response_headers()['Content-Type'] == \
           FORMAT_TYPES[F_JSON]
    assert apireq.get_linkrel(F_JSON) == 'self'
    assert apireq.get_linkrel(F_HTML) == 'alternate'

    # Test complex format string
    hh = 'text/html,application/xhtml+xml,application/xml;q=0.9,'
    req = mock_request(HTTP_ACCEPT=hh)
    apireq = APIRequest(req, api_.locales)
    assert apireq.is_valid()
    assert apireq.format == F_HTML
    assert apireq.get_response_headers()['Content-Type'] == \
           FORMAT_TYPES[F_HTML]
    assert apireq.get_linkrel(F_HTML) == 'self'
    assert apireq.get_linkrel(F_JSON) == 'alternate'

    # Test accept header with multiple valid formats
    hh = 'plain/text,application/ld+json,application/json;q=0.9,'
    req = mock_request(HTTP_ACCEPT=hh)
    apireq = APIRequest(req, api_.locales)
    assert apireq.is_valid()
    assert apireq.format == F_JSONLD
    assert apireq.get_response_headers()['Content-Type'] == \
           FORMAT_TYPES[F_JSONLD]
    assert apireq.get_linkrel(F_JSONLD) == 'self'
    assert apireq.get_linkrel(F_HTML) == 'alternate'

    # Overrule HTTP content negotiation
    req = mock_request({'f': 'html'}, HTTP_ACCEPT='application/json')  # noqa
    apireq = APIRequest(req, api_.locales)
    assert apireq.is_valid()
    assert apireq.format == F_HTML
    assert apireq.get_response_headers()['Content-Type'] == \
           FORMAT_TYPES[F_HTML]

    # Test data
    for d in (None, '', 'test', {'key': 'value'}):
        req = mock_request(data=d)
        apireq = APIRequest.with_data(req, api_.locales)
        if not d:
            assert apireq.data == b''
        elif isinstance(d, dict):
            assert d == json.loads(apireq.data)
        else:
            assert apireq.data == d.encode()

    # Test multilingual
    test_lang = {
        'nl': ('en', 'en-US'),  # unsupported lang should return default
        'en-US': ('en', 'en-US'),
        'de_CH': ('en', 'en-US'),
        'fr-CH, fr;q=0.9, en;q=0.8': ('fr', 'fr-CA'),
        'fr-CH, fr-BE;q=0.9': ('fr', 'fr-CA'),
    }
    sup_lang = ('en-US', 'fr_CA')
    for lang_in, (lang_out, cl_out) in test_lang.items():
        # Using l query parameter
        req = mock_request({'lang': lang_in})
        apireq = APIRequest(req, sup_lang)
        assert apireq.raw_locale == lang_in
        assert apireq.locale.language == lang_out
        assert apireq.get_response_headers()['Content-Language'] == cl_out

        # Using Accept-Language header
        req = mock_request(HTTP_ACCEPT_LANGUAGE=lang_in)
        apireq = APIRequest(req, sup_lang)
        assert apireq.raw_locale == lang_in
        assert apireq.locale.language == lang_out
        assert apireq.get_response_headers()['Content-Language'] == cl_out

    # Test language override
    req = mock_request({'lang': 'fr'}, HTTP_ACCEPT_LANGUAGE='en_US')
    apireq = APIRequest(req, sup_lang)
    assert apireq.raw_locale == 'fr'
    assert apireq.locale.language == 'fr'
    assert apireq.get_response_headers()['Content-Language'] == 'fr-CA'

    # Test locale territory
    req = mock_request({'lang': 'en-GB'})
    apireq = APIRequest(req, sup_lang)
    assert apireq.raw_locale == 'en-GB'
    assert apireq.locale.language == 'en'
    assert apireq.locale.territory == 'US'
    assert apireq.get_response_headers()['Content-Language'] == 'en-US'

    # Test without Accept-Language header or 'lang' query parameter
    # (should return default language from YAML config)
    req = mock_request()
    apireq = APIRequest(req, api_.locales)
    assert apireq.raw_locale is None
    assert apireq.locale.language == api_.default_locale.language
    assert apireq.get_response_headers()['Content-Language'] == 'en-US'

    # Test without Accept-Language header or 'lang' query param
    # (should return first in custom list of languages)
    sup_lang = ('de', 'fr', 'en')
    apireq = APIRequest(req, sup_lang)
    assert apireq.raw_locale is None
    assert apireq.locale.language == 'de'
    assert apireq.get_response_headers()['Content-Language'] == 'de'


def test_api(config, api_, openapi):
    assert api_.config == config
    assert isinstance(api_.config, dict)

    req = mock_request(HTTP_ACCEPT='application/json')
    rsp_headers, code, response = api_.openapi(req, openapi)
    assert rsp_headers['Content-Type'] == 'application/vnd.oai.openapi+json;version=3.0'  # noqa
    # No language requested: should be set to default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'
    root = json.loads(response)
    assert isinstance(root, dict)

    a = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    req = mock_request(HTTP_ACCEPT=a)
    rsp_headers, code, response = api_.openapi(req, openapi)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML] == \
           FORMAT_TYPES[F_HTML]

    assert 'Swagger UI' in response

    a = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    req = mock_request({'ui': 'redoc'}, HTTP_ACCEPT=a)
    rsp_headers, code, response = api_.openapi(req, openapi)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML] == \
           FORMAT_TYPES[F_HTML]

    assert 'ReDoc' in response

    req = mock_request({'f': 'foo'})
    rsp_headers, code, response = api_.openapi(req, openapi)
    assert rsp_headers['Content-Language'] == 'en-US'
    assert code == HTTPStatus.BAD_REQUEST

    assert api_.get_collections_url() == 'http://localhost:5000/collections'


def test_api_exception(config, api_):
    req = mock_request({'f': 'foo'})
    rsp_headers, code, response = api_.landing_page(req)
    assert rsp_headers['Content-Language'] == 'en-US'
    assert code == HTTPStatus.BAD_REQUEST

    # When a language is set, the exception should still be English
    req = mock_request({'f': 'foo', 'lang': 'fr'})
    rsp_headers, code, response = api_.landing_page(req)
    assert rsp_headers['Content-Language'] == 'en-US'
    assert code == HTTPStatus.BAD_REQUEST


def test_gzip(config, api_):
    # Requests for each response type and gzip encoding
    req_gzip_json = mock_request(HTTP_ACCEPT=FORMAT_TYPES[F_JSON],
                                 HTTP_ACCEPT_ENCODING=F_GZIP)
    req_gzip_jsonld = mock_request(HTTP_ACCEPT=FORMAT_TYPES[F_JSONLD],
                                   HTTP_ACCEPT_ENCODING=F_GZIP)
    req_gzip_html = mock_request(HTTP_ACCEPT=FORMAT_TYPES[F_HTML],
                                 HTTP_ACCEPT_ENCODING=F_GZIP)
    req_gzip_gzip = mock_request(HTTP_ACCEPT='application/gzip',
                                 HTTP_ACCEPT_ENCODING=F_GZIP)

    # Responses from server config without gzip compression
    rsp_headers, _, rsp_json = api_.landing_page(req_gzip_json)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    rsp_headers, _, rsp_jsonld = api_.landing_page(req_gzip_jsonld)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSONLD]
    rsp_headers, _, rsp_html = api_.landing_page(req_gzip_html)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    rsp_headers, _, _ = api_.landing_page(req_gzip_gzip)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]

    # Add gzip to server and use utf-16 encoding
    config['server']['gzip'] = True
    enc_16 = 'utf-16'
    config['server']['encoding'] = enc_16
    api_ = API(config)

    # Responses from server with gzip compression
    rsp_json_headers, _, rsp_gzip_json = api_.landing_page(req_gzip_json)
    rsp_jsonld_headers, _, rsp_gzip_jsonld = api_.landing_page(req_gzip_jsonld)
    rsp_html_headers, _, rsp_gzip_html = api_.landing_page(req_gzip_html)
    rsp_gzip_headers, _, rsp_gzip_gzip = api_.landing_page(req_gzip_gzip)

    # Validate compressed json response
    assert rsp_json_headers['Content-Type'] == \
        f'{FORMAT_TYPES[F_JSON]}; charset={enc_16}'
    assert rsp_json_headers['Content-Encoding'] == F_GZIP

    parsed_gzip_json = gzip.decompress(rsp_gzip_json).decode(enc_16)
    assert isinstance(parsed_gzip_json, str)
    parsed_gzip_json = json.loads(parsed_gzip_json)
    assert isinstance(parsed_gzip_json, dict)
    assert parsed_gzip_json == json.loads(rsp_json)

    # Validate compressed jsonld response
    assert rsp_jsonld_headers['Content-Type'] == \
        f'{FORMAT_TYPES[F_JSONLD]}; charset={enc_16}'
    assert rsp_jsonld_headers['Content-Encoding'] == F_GZIP

    parsed_gzip_jsonld = gzip.decompress(rsp_gzip_jsonld).decode(enc_16)
    assert isinstance(parsed_gzip_jsonld, str)
    parsed_gzip_jsonld = json.loads(parsed_gzip_jsonld)
    assert isinstance(parsed_gzip_jsonld, dict)
    assert parsed_gzip_jsonld == json.loads(rsp_jsonld)

    # Validate compressed html response
    assert rsp_html_headers['Content-Type'] == \
        f'{FORMAT_TYPES[F_HTML]}; charset={enc_16}'
    assert rsp_html_headers['Content-Encoding'] == F_GZIP

    parsed_gzip_html = gzip.decompress(rsp_gzip_html).decode(enc_16)
    assert isinstance(parsed_gzip_html, str)
    assert parsed_gzip_html == rsp_html

    # Validate compressed gzip response
    assert rsp_gzip_headers['Content-Type'] == \
        f'{FORMAT_TYPES[F_GZIP]}; charset={enc_16}'
    assert rsp_gzip_headers['Content-Encoding'] == F_GZIP

    parsed_gzip_gzip = gzip.decompress(rsp_gzip_gzip).decode(enc_16)
    assert isinstance(parsed_gzip_gzip, str)
    parsed_gzip_gzip = json.loads(parsed_gzip_gzip)
    assert isinstance(parsed_gzip_gzip, dict)

    # Requests without content encoding header
    req_json = mock_request(HTTP_ACCEPT=FORMAT_TYPES[F_JSON])
    req_jsonld = mock_request(HTTP_ACCEPT=FORMAT_TYPES[F_JSONLD])
    req_html = mock_request(HTTP_ACCEPT=FORMAT_TYPES[F_HTML])

    # Responses without content encoding
    _, _, rsp_json_ = api_.landing_page(req_json)
    _, _, rsp_jsonld_ = api_.landing_page(req_jsonld)
    _, _, rsp_html_ = api_.landing_page(req_html)

    # Confirm each request is the same when decompressed
    assert rsp_json_ == rsp_json == \
        gzip.decompress(rsp_gzip_json).decode(enc_16)

    assert rsp_jsonld_ == rsp_jsonld == \
        gzip.decompress(rsp_gzip_jsonld).decode(enc_16)

    assert rsp_html_ == rsp_html == \
        gzip.decompress(rsp_gzip_html).decode(enc_16)


def test_root(config, api_):
    req = mock_request()
    rsp_headers, code, response = api_.landing_page(req)
    root = json.loads(response)

    assert rsp_headers['Content-Type'] == 'application/json' == \
           FORMAT_TYPES[F_JSON]
    assert rsp_headers['X-Powered-By'].startswith('pygeoapi')
    assert rsp_headers['Content-Language'] == 'en-US'

    assert isinstance(root, dict)
    assert 'links' in root
    assert root['links'][0]['rel'] == 'self'
    assert root['links'][0]['type'] == FORMAT_TYPES[F_JSON]
    assert root['links'][0]['href'].endswith('?f=json')
    assert any(link['href'].endswith('f=jsonld') and link['rel'] == 'alternate'
               for link in root['links'])
    assert any(link['href'].endswith('f=html') and link['rel'] == 'alternate'
               for link in root['links'])
    assert len(root['links']) == 9
    assert 'title' in root
    assert root['title'] == 'pygeoapi default instance'
    assert 'description' in root
    assert root['description'] == 'pygeoapi provides an API to geospatial data'

    req = mock_request({'f': 'html'})
    rsp_headers, code, response = api_.landing_page(req)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    assert rsp_headers['Content-Language'] == 'en-US'


def test_root_structured_data(config, api_):
    req = mock_request({"f": "jsonld"})
    rsp_headers, code, response = api_.landing_page(req)
    root = json.loads(response)

    assert rsp_headers['Content-Type'] == 'application/ld+json' == \
           FORMAT_TYPES[F_JSONLD]
    assert rsp_headers['Content-Language'] == 'en-US'
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
    req = mock_request()
    rsp_headers, code, response = api_.conformance(req)
    root = json.loads(response)

    assert isinstance(root, dict)
    assert 'conformsTo' in root
    assert len(root['conformsTo']) == 22

    req = mock_request({'f': 'foo'})
    rsp_headers, code, response = api_.conformance(req)
    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'f': 'html'})
    rsp_headers, code, response = api_.conformance(req)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    # No language requested: should be set to default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'


def test_describe_collections(config, api_):
    req = mock_request({"f": "foo"})
    rsp_headers, code, response = api_.describe_collections(req)
    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({"f": "html"})
    rsp_headers, code, response = api_.describe_collections(req)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]

    req = mock_request()
    rsp_headers, code, response = api_.describe_collections(req)
    collections = json.loads(response)

    assert len(collections) == 2
    assert len(collections['collections']) == 7
    assert len(collections['links']) == 3

    rsp_headers, code, response = api_.describe_collections(req, 'foo')
    collection = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND

    rsp_headers, code, response = api_.describe_collections(req, 'obs')
    collection = json.loads(response)

    assert rsp_headers['Content-Language'] == 'en-US'
    assert collection['id'] == 'obs'
    assert collection['title'] == 'Observations'
    assert collection['description'] == 'My cool observations'
    assert len(collection['links']) == 12
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

    # French language request
    req = mock_request({'lang': 'fr'})
    rsp_headers, code, response = api_.describe_collections(req, 'obs')
    collection = json.loads(response)

    assert rsp_headers['Content-Language'] == 'fr-CA'
    assert collection['title'] == 'Observations'
    assert collection['description'] == 'Mes belles observations'

    # Check HTML request in an unsupported language
    req = mock_request({'f': 'html', 'lang': 'de'})
    rsp_headers, code, response = api_.describe_collections(req, 'obs')
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    assert rsp_headers['Content-Language'] == 'en-US'

    req = mock_request()
    rsp_headers, code, response = api_.describe_collections(req,
                                                            'gdps-temperature')
    collection = json.loads(response)

    assert collection['id'] == 'gdps-temperature'
    assert len(collection['links']) == 14

    # hiearchical collections
    rsp_headers, code, response = api_.describe_collections(
        req, 'naturalearth/lakes')
    collection = json.loads(response)
    assert collection['id'] == 'naturalearth/lakes'


def test_describe_collections_hidden_resources(
        config_hidden_resources, api_hidden_resources):
    req = mock_request({})
    rsp_headers, code, response = api_hidden_resources.describe_collections(req)  # noqa
    assert code == HTTPStatus.OK

    assert len(config_hidden_resources['resources']) == 3

    collections = json.loads(response)
    assert len(collections['collections']) == 1


def test_get_collection_queryables(config, api_):
    req = mock_request()
    rsp_headers, code, response = api_.get_collection_queryables(req,
                                                                 'notfound')
    assert code == HTTPStatus.NOT_FOUND

    req = mock_request({'f': 'html'})
    rsp_headers, code, response = api_.get_collection_queryables(req, 'obs')
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]

    req = mock_request({'f': 'json'})
    rsp_headers, code, response = api_.get_collection_queryables(req, 'obs')
    assert rsp_headers['Content-Type'] == 'application/schema+json'
    queryables = json.loads(response)

    assert 'properties' in queryables
    assert len(queryables['properties']) == 5

    # test with provider filtered properties
    api_.config['resources']['obs']['providers'][0]['properties'] = ['stn_id']

    rsp_headers, code, response = api_.get_collection_queryables(req, 'obs')
    queryables = json.loads(response)

    assert 'properties' in queryables
    assert len(queryables['properties']) == 2
    assert 'geometry' in queryables['properties']
    assert queryables['properties']['geometry']['$ref'] == 'https://geojson.org/schema/Geometry.json'  # noqa

    # No language requested: should be set to default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'


def test_describe_collections_json_ld(config, api_):
    req = mock_request({'f': 'jsonld'})
    rsp_headers, code, response = api_.describe_collections(req, 'obs')
    collection = json.loads(response)

    assert '@context' in collection
    expanded = jsonld.expand(collection)[0]
    # Metadata is about a schema:DataCollection that contains a schema:Dataset
    assert not expanded['@id'].endswith('obs')
    assert 'http://schema.org/dataset' in expanded
    assert len(expanded['http://schema.org/dataset']) == 1
    dataset = expanded['http://schema.org/dataset'][0]
    assert dataset['@type'][0] == 'http://schema.org/Dataset'
    assert len(dataset['http://schema.org/distribution']) == 12
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

    # No language requested: should be set to default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'


def test_get_collection_items(config, api_):
    req = mock_request()
    rsp_headers, code, response = api_.get_collection_items(req, 'foo')
    features = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND

    req = mock_request({'f': 'foo'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    features = json.loads(response)

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'bbox': '1,2,3'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    features = json.loads(response)

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'bbox': '1,2,3,4c'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'f': 'html', 'lang': 'fr'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    assert rsp_headers['Content-Language'] == 'fr-CA'

    req = mock_request()
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    features = json.loads(response)
    # No language requested: should be set to default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'

    assert len(features['features']) == 5

    req = mock_request({'resulttype': 'hits'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 0

    # Invalid limit
    req = mock_request({'limit': 0})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    features = json.loads(response)

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'stn_id': '35'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 2
    assert features['numberMatched'] == 2

    req = mock_request({'stn_id': '35', 'value': '93.9'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    features = json.loads(response)

    assert len(features['features']) == 1
    assert features['numberMatched'] == 1

    req = mock_request({'limit': 2})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
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
    assert '/collections/obs/items?offset=2&limit=2' in links[3]['href']
    assert links[3]['rel'] == 'next'
    assert '/collections/obs' in links[4]['href']
    assert links[4]['rel'] == 'collection'

    # Invalid offset
    req = mock_request({'offset': -1})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    features = json.loads(response)

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'offset': 2})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
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

    req = mock_request({
        'offset': 1,
        'limit': 1,
        'bbox': '-180,90,180,90'
    })
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
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
    assert '/collections/obs/items?offset=2&limit=1&bbox=-180,90,180,90' \
        in links[4]['href']
    assert links[4]['rel'] == 'next'
    assert '/collections/obs' in links[5]['href']
    assert links[5]['rel'] == 'collection'

    req = mock_request({
        'sortby': 'bad-property',
        'stn_id': '35'
    })
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'sortby': 'stn_id'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    features = json.loads(response)
    assert code == HTTPStatus.OK

    req = mock_request({'sortby': '+stn_id'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    features = json.loads(response)
    assert code == HTTPStatus.OK

    req = mock_request({'sortby': '-stn_id'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')
    features = json.loads(response)
    assert code == HTTPStatus.OK

    req = mock_request({'f': 'csv'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert rsp_headers['Content-Type'] == 'text/csv; charset=utf-8'

    req = mock_request({'datetime': '2003'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_request({'datetime': '1999'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'datetime': '2010-04-22'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'datetime': '2001-11-11/2003-12-18'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_request({'datetime': '../2003-12-18'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_request({'datetime': '2001-11-11/..'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_request({'datetime': '1999/2005-04-22'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_request({'datetime': '1999/2000-04-22'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    api_.config['resources']['obs']['extents'].pop('temporal')

    req = mock_request({'datetime': '2002/2014-04-22'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.OK

    req = mock_request({'scalerank': 1})
    rsp_headers, code, response = api_.get_collection_items(
        req, 'naturalearth/lakes')
    features = json.loads(response)

    assert len(features['features']) == 10
    assert features['numberMatched'] == 11
    assert features['numberReturned'] == 10

    req = mock_request({'datetime': '2005-04-22'})
    rsp_headers, code, response = api_.get_collection_items(
        req, 'naturalearth/lakes')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'skipGeometry': 'true'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert json.loads(response)['features'][0]['geometry'] is None

    req = mock_request({'properties': 'foo,bar'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST


def test_get_collection_items_postgresql_cql(pg_api_):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.
    """
    # Arrange
    cql_query = 'osm_id BETWEEN 80800000 AND 80900000 AND name IS NULL'
    expected_ids = [80835474, 80835483]

    # Act
    req = mock_request({
        'filter-lang': 'cql-text',
        'filter': cql_query
    })
    rsp_headers, code, response = pg_api_.get_collection_items(
        req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.OK
    features = json.loads(response)
    ids = [item['id'] for item in features['features']]
    assert ids == expected_ids

    # Act, no filter-lang
    req = mock_request({
        'filter': cql_query
    })
    rsp_headers, code, response = pg_api_.get_collection_items(
        req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.OK
    features = json.loads(response)
    ids = [item['id'] for item in features['features']]
    assert ids == expected_ids


def test_get_collection_items_postgresql_cql_invalid_filter_language(pg_api_):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.

    Test for invalid filter language
    """
    # Arrange
    cql_query = 'osm_id BETWEEN 80800000 AND 80900000 AND name IS NULL'

    # Act
    req = mock_request({
        'filter-lang': 'cql-json',  # Only cql-text is valid for GET
        'filter': cql_query
    })
    rsp_headers, code, response = pg_api_.get_collection_items(
        req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.BAD_REQUEST
    error_response = json.loads(response)
    assert error_response['code'] == 'InvalidParameterValue'
    assert error_response['description'] == 'Invalid filter language'


@pytest.mark.parametrize("bad_cql", [
    'id IN (1, ~)',
    'id EATS (1, 2)',  # Valid CQL relations only
    'id IN (1, 2'  # At some point this may return UnexpectedEOF
])
def test_get_collection_items_postgresql_cql_bad_cql(pg_api_, bad_cql):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.

    Test for bad cql
    """
    # Act
    req = mock_request({
        'filter': bad_cql
    })
    rsp_headers, code, response = pg_api_.get_collection_items(
        req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.BAD_REQUEST
    error_response = json.loads(response)
    assert error_response['code'] == 'InvalidParameterValue'
    assert error_response['description'] == f'Bad CQL string : {bad_cql}'


def test_post_collection_items_postgresql_cql(pg_api_):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.
    """
    # Arrange
    cql = {"and": [{"between": {"value": {"property": "osm_id"},
                                "lower": 80800000,
                                "upper": 80900000}},
                   {"isNull": {"property": "name"}}]}
    # werkzeug requests use a value of CONTENT_TYPE 'application/json'
    # to create Content-Type in the Request object. So here we need to
    # overwrite the default CONTENT_TYPE with the required one.
    headers = {'CONTENT_TYPE': 'application/query-cql-json'}
    expected_ids = [80835474, 80835483]

    # Act
    req = mock_request({
        'filter-lang': 'cql-json'
    }, data=cql, **headers)
    rsp_headers, code, response = pg_api_.post_collection_items(
        req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.OK
    features = json.loads(response)
    ids = [item['id'] for item in features['features']]
    assert ids == expected_ids


def test_post_collection_items_postgresql_cql_invalid_filter_language(pg_api_):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.

    Test for invalid filter language
    """
    # Arrange
    # CQL should never be parsed
    cql = {"in": {"value": {"property": "id"}, "list": [1, 2]}}
    headers = {'CONTENT_TYPE': 'application/query-cql-json'}

    # Act
    req = mock_request({
        'filter-lang': 'cql-text'  # Only cql-json is valid for POST
    }, data=cql, **headers)
    rsp_headers, code, response = pg_api_.post_collection_items(
        req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.BAD_REQUEST
    error_response = json.loads(response)
    assert error_response['code'] == 'InvalidParameterValue'
    assert error_response['description'] == 'Invalid filter language'


@pytest.mark.parametrize("bad_cql", [
    # Valid CQL relations only
    {"eats": {"value": {"property": "id"}, "list": [1, 2]}},
    # At some point this may return UnexpectedEOF
    '{"in": {"value": {"property": "id"}, "list": [1, 2}}'
])
def test_post_collection_items_postgresql_cql_bad_cql(pg_api_, bad_cql):
    """
    Test for PostgreSQL CQL - requires local PostgreSQL with appropriate
    data.  See pygeoapi/provider/postgresql.py for details.

    Test for bad cql
    """
    # Arrange
    headers = {'CONTENT_TYPE': 'application/query-cql-json'}

    # Act
    req = mock_request({
        'filter-lang': 'cql-json'
    }, data=bad_cql, **headers)
    rsp_headers, code, response = pg_api_.post_collection_items(
        req, 'hot_osm_waterways')

    # Assert
    assert code == HTTPStatus.BAD_REQUEST
    error_response = json.loads(response)
    assert error_response['code'] == 'InvalidParameterValue'
    assert error_response['description'].startswith('Bad CQL string')


def test_get_collection_items_json_ld(config, api_):
    req = mock_request({
        'f': 'jsonld',
        'limit': 2
    })
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

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
    req = mock_request({'f': 'foo'})
    rsp_headers, code, response = api_.get_collection_item(req, 'obs', '371')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'f': 'json'})
    rsp_headers, code, response = api_.get_collection_item(
        req, 'gdps-temperature', '371')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request()
    rsp_headers, code, response = api_.get_collection_item(req, 'foo', '371')

    assert code == HTTPStatus.NOT_FOUND

    rsp_headers, code, response = api_.get_collection_item(
        req, 'obs', 'notfound')

    assert code == HTTPStatus.NOT_FOUND

    req = mock_request({'f': 'html'})
    rsp_headers, code, response = api_.get_collection_item(req, 'obs', '371')

    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    assert rsp_headers['Content-Language'] == 'en-US'

    req = mock_request()
    rsp_headers, code, response = api_.get_collection_item(req, 'obs', '371')
    feature = json.loads(response)

    assert feature['properties']['stn_id'] == 35
    assert 'prev' not in feature['links']
    assert 'next' not in feature['links']


def test_get_collection_item_json_ld(config, api_):
    req = mock_request({'f': 'jsonld'})
    rsp_headers, _, response = api_.get_collection_item(req, 'objects', '3')
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSONLD]
    assert rsp_headers['Content-Language'] == 'en-US'
    feature = json.loads(response)
    assert '@context' in feature
    assert all((f in feature['@context'][0] for
                f in ('schema', 'type', 'geosparql')))
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

    _, _, response = api_.get_collection_item(req, 'objects', '2')
    feature = json.loads(response)
    assert feature['geometry']['type'] == 'MultiPoint'
    expanded = jsonld.expand(feature)[0]
    assert expanded['http://www.opengis.net/ont/geosparql#hasGeometry'][0][
            'http://www.opengis.net/ont/geosparql#asWKT'][0][
            '@value'] == 'MULTIPOINT (10 40, 40 30, 20 20, 30 10)'
    assert expanded['https://schema.org/geo'][0][
            'https://schema.org/polygon'][0][
            '@value'] == "10.0,40.0 40.0,30.0 20.0,20.0 30.0,10.0 10.0,40.0"

    _, _, response = api_.get_collection_item(req, 'objects', '1')
    feature = json.loads(response)
    expanded = jsonld.expand(feature)[0]
    assert expanded['http://www.opengis.net/ont/geosparql#hasGeometry'][0][
            'http://www.opengis.net/ont/geosparql#asWKT'][0][
            '@value'] == 'LINESTRING (30 10, 10 30, 40 40)'
    assert expanded['https://schema.org/geo'][0][
            'https://schema.org/line'][0][
            '@value'] == '30.0,10.0 10.0,30.0 40.0,40.0'

    _, _, response = api_.get_collection_item(req, 'objects', '4')
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

    _, _, response = api_.get_collection_item(req, 'objects', '5')
    feature = json.loads(response)
    expanded = jsonld.expand(feature)[0]
    assert expanded['http://www.opengis.net/ont/geosparql#hasGeometry'][0][
            'http://www.opengis.net/ont/geosparql#asWKT'][0][
            '@value'] == 'POLYGON ((30 10, 40 40, 20 40, 10 20, 30 10))'
    assert expanded['https://schema.org/geo'][0][
            'https://schema.org/polygon'][0][
            '@value'] == '30.0,10.0 40.0,40.0 20.0,40.0 10.0,20.0 30.0,10.0'

    _, _, response = api_.get_collection_item(req, 'objects', '7')
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

    req = mock_request({'f': 'jsonld', 'lang': 'fr'})
    rsp_headers, code, response = api_.get_collection_item(req, 'obs', '371')
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSONLD]
    assert rsp_headers['Content-Language'] == 'fr-CA'


def test_get_coverage_domainset(config, api_):
    req = mock_request()
    rsp_headers, code, response = api_.get_collection_coverage_domainset(
        req, 'obs')

    assert code == HTTPStatus.INTERNAL_SERVER_ERROR

    rsp_headers, code, response = api_.get_collection_coverage_domainset(
        req, 'gdps-temperature')

    domainset = json.loads(response)

    assert domainset['type'] == 'DomainSet'
    assert domainset['generalGrid']['axisLabels'] == ['Long', 'Lat']
    assert domainset['generalGrid']['gridLimits']['axisLabels'] == ['i', 'j']
    assert domainset['generalGrid']['gridLimits']['axis'][0]['upperBound'] == 2400  # noqa
    assert domainset['generalGrid']['gridLimits']['axis'][1]['upperBound'] == 1201  # noqa


def test_get_collection_coverage_rangetype(config, api_):
    req = mock_request()
    rsp_headers, code, response = api_.get_collection_coverage_rangetype(
        req, 'obs')

    assert code == HTTPStatus.INTERNAL_SERVER_ERROR

    rsp_headers, code, response = api_.get_collection_coverage_rangetype(
        req, 'gdps-temperature')

    rangetype = json.loads(response)

    assert rangetype['type'] == 'DataRecord'
    assert len(rangetype['field']) == 1
    assert rangetype['field'][0]['id'] == 1
    assert rangetype['field'][0]['name'] == 'Temperature [C]'
    assert rangetype['field'][0]['uom']['code'] == '[C]'


def test_get_collection_coverage(config, api_):
    req = mock_request()
    rsp_headers, code, response = api_.get_collection_coverage(
        req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'properties': '12'})
    rsp_headers, code, response = api_.get_collection_coverage(
        req, 'gdps-temperature')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'subset': 'bad_axis(10:20)'})
    rsp_headers, code, response = api_.get_collection_coverage(
        req, 'gdps-temperature')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'f': 'blah'})
    rsp_headers, code, response = api_.get_collection_coverage(
        req, 'gdps-temperature')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'f': 'html'})
    rsp_headers, code, response = api_.get_collection_coverage(
        req, 'gdps-temperature')

    assert code == HTTPStatus.BAD_REQUEST
    assert rsp_headers['Content-Type'] == 'text/html'

    req = mock_request(HTTP_ACCEPT='text/html')
    rsp_headers, code, response = api_.get_collection_coverage(
        req, 'gdps-temperature')

    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == 'application/prs.coverage+json'

    req = mock_request({'subset': 'Lat(5:10),Long(5:10)'})
    rsp_headers, code, response = api_.get_collection_coverage(
        req, 'gdps-temperature')

    assert code == HTTPStatus.OK
    content = json.loads(response)

    assert content['domain']['axes']['x']['num'] == 35
    assert content['domain']['axes']['y']['num'] == 35
    assert 'TMP' in content['parameters']
    assert 'TMP' in content['ranges']
    assert content['ranges']['TMP']['axisNames'] == ['y', 'x']

    req = mock_request({'bbox': '-79,45,-75,49'})
    rsp_headers, code, response = api_.get_collection_coverage(
        req, 'gdps-temperature')

    assert code == HTTPStatus.OK
    content = json.loads(response)

    assert content['domain']['axes']['x']['start'] == -79.0
    assert content['domain']['axes']['x']['stop'] == -75.0
    assert content['domain']['axes']['y']['start'] == 49.0
    assert content['domain']['axes']['y']['stop'] == 45.0

    req = mock_request({
        'subset': 'Lat(5:10),Long(5:10)',
        'f': 'GRIB'
    })
    rsp_headers, code, response = api_.get_collection_coverage(
        req, 'gdps-temperature')

    assert code == HTTPStatus.OK
    assert isinstance(response, bytes)

    # req = mock_request({
    #     'subset': 'time("2006-07-01T06:00:00":"2007-07-01T06:00:00")'
    # })
    # rsp_headers, code, response = api_.get_collection_coverage(req, 'cmip5')
    #
    # assert code == HTTPStatus.OK
    # assert isinstance(json.loads(response), dict)

    # req = mock_request({'subset': 'lat(1:2'})
    # rsp_headers, code, response = api_.get_collection_coverage(req, 'cmip5')
    #
    # assert code == HTTPStatus.BAD_REQUEST
    #
    # req = mock_request({'subset': 'lat(1:2)'})
    # rsp_headers, code, response = api_.get_collection_coverage(req, 'cmip5')
    #
    # assert code == HTTPStatus.NO_CONTENT


def test_get_collection_map(config, api_):
    req = mock_request()
    rsp_headers, code, response = api_.get_collection_map(req, 'notfound')
    assert code == HTTPStatus.NOT_FOUND

    req = mock_request()
    rsp_headers, code, response = api_.get_collection_map(
        req, 'mapserver_world_map')
    assert code == HTTPStatus.OK
    assert isinstance(response, bytes)
    assert response[1:4] == b'PNG'


def test_get_collection_tiles(config, api_):
    req = mock_request()
    rsp_headers, code, response = api_.get_collection_tiles(req, 'obs')
    assert code == HTTPStatus.BAD_REQUEST

    rsp_headers, code, response = api_.get_collection_tiles(
        req, 'naturalearth/lakes')
    assert code == HTTPStatus.OK

    # Language settings should be ignored (return system default)
    req = mock_request({'lang': 'fr'})
    rsp_headers, code, response = api_.get_collection_tiles(
        req, 'naturalearth/lakes')
    assert rsp_headers['Content-Language'] == 'en-US'
    content = json.loads(response)
    assert len(content['links']) > 0
    assert len(content['tilesets']) > 0


def test_describe_processes(config, api_):
    req = mock_request()

    # Test for undefined process
    rsp_headers, code, response = api_.describe_processes(req, 'foo')
    data = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND
    assert data['code'] == 'NoSuchProcess'

    # Test for description of all processes
    rsp_headers, code, response = api_.describe_processes(req)
    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert len(data['processes']) == 1
    assert len(data['links']) == 3

    # Test for particular, defined process
    rsp_headers, code, response = api_.describe_processes(req, 'hello-world')
    process = json.loads(response)
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert process['id'] == 'hello-world'
    assert process['version'] == '0.2.0'
    assert process['title'] == 'Hello World'
    assert len(process['keywords']) == 3
    assert len(process['links']) == 6
    assert len(process['inputs']) == 2
    assert len(process['outputs']) == 1
    assert len(process['outputTransmission']) == 1
    assert len(process['jobControlOptions']) == 2
    assert 'sync-execute' in process['jobControlOptions']
    assert 'async-execute' in process['jobControlOptions']

    # Check HTML response when requested in headers
    req = mock_request(HTTP_ACCEPT='text/html')
    rsp_headers, code, response = api_.describe_processes(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    # No language requested: return default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check JSON response when requested in headers
    req = mock_request(HTTP_ACCEPT='application/json')
    rsp_headers, code, response = api_.describe_processes(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check HTML response when requested with query parameter
    req = mock_request({'f': 'html'})
    rsp_headers, code, response = api_.describe_processes(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    # No language requested: return default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check JSON response when requested with query parameter
    req = mock_request({'f': 'json'})
    rsp_headers, code, response = api_.describe_processes(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check JSON response when requested with French language parameter
    req = mock_request({'lang': 'fr'})
    rsp_headers, code, response = api_.describe_processes(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'fr-CA'
    process = json.loads(response)
    assert process['title'] == 'Bonjour le Monde'

    # Check JSON response when language requested in headers
    req = mock_request(HTTP_ACCEPT_LANGUAGE='fr')
    rsp_headers, code, response = api_.describe_processes(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'fr-CA'

    # Test for undefined process
    req = mock_request()
    rsp_headers, code, response = api_.describe_processes(req, 'goodbye-world')
    data = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND
    assert data['code'] == 'NoSuchProcess'
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]


def test_execute_process(config, api_):
    req_body_0 = {
        'inputs': {
            'name': 'Test'
        }
    }
    req_body_1 = {
        'inputs': {
            'name': 'Test'
        },
        'response': 'document'
    }
    req_body_2 = {
        'inputs': {
            'name': 'Tést'
        }
    }
    req_body_3 = {
        'inputs': {
            'name': 'Tést',
            'message': 'This is a test.'
        }
    }
    req_body_4 = {
        'inputs': {
            'foo': 'Tést'
        }
    }
    req_body_5 = {
        'inputs': {}
    }
    req_body_6 = {
        'inputs': {
            'name': None
        }
    }

    cleanup_jobs = set()

    # Test posting empty payload to existing process
    req = mock_request(data='')
    rsp_headers, code, response = api_.execute_process(req, 'hello-world')
    assert rsp_headers['Content-Language'] == 'en-US'

    data = json.loads(response)
    assert code == HTTPStatus.BAD_REQUEST
    assert 'Location' not in rsp_headers
    assert data['code'] == 'MissingParameterValue'

    req = mock_request(data=req_body_0)
    rsp_headers, code, response = api_.execute_process(req, 'foo')

    data = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND
    assert 'Location' not in rsp_headers
    assert data['code'] == 'NoSuchProcess'

    rsp_headers, code, response = api_.execute_process(req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers

    assert len(data.keys()) == 2
    assert data['id'] == 'echo'
    assert data['value'] == 'Hello Test!'

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_request(data=req_body_1)
    rsp_headers, code, response = api_.execute_process(req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers

    assert len(data.keys()) == 1
    assert data['outputs'][0]['id'] == 'echo'
    assert data['outputs'][0]['value'] == 'Hello Test!'

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_request(data=req_body_2)
    rsp_headers, code, response = api_.execute_process(req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers
    assert data['value'] == 'Hello Tést!'

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_request(data=req_body_3)
    rsp_headers, code, response = api_.execute_process(req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers
    assert data['value'] == 'Hello Tést! This is a test.'

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_request(data=req_body_4)
    rsp_headers, code, response = api_.execute_process(req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers
    assert data['code'] == 'InvalidParameterValue'
    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_request(data=req_body_5)
    rsp_headers, code, response = api_.execute_process(req, 'hello-world')
    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers
    assert data['code'] == 'InvalidParameterValue'
    assert data['description'] == 'Error updating job'

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_request(data=req_body_6)
    rsp_headers, code, response = api_.execute_process(req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers
    assert data['code'] == 'InvalidParameterValue'
    assert data['description'] == 'Error updating job'

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req = mock_request(data=req_body_0)
    rsp_headers, code, response = api_.execute_process(req, 'goodbye-world')

    response = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND
    assert 'Location' not in rsp_headers
    assert response['code'] == 'NoSuchProcess'

    rsp_headers, code, response = api_.execute_process(req, 'hello-world')

    response = json.loads(response)
    assert code == HTTPStatus.OK

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    req_body_1['mode'] = 'async'
    req = mock_request(data=req_body_1)
    rsp_headers, code, response = api_.execute_process(req, 'hello-world')

    assert 'Location' in rsp_headers
    response = json.loads(response)
    assert isinstance(response, dict)
    assert code == HTTPStatus.CREATED

    cleanup_jobs.add(tuple(['hello-world',
                            rsp_headers['Location'].split('/')[-1]]))

    # Cleanup
    time.sleep(2)  # Allow time for any outstanding async jobs
    for _, job_id in cleanup_jobs:
        rsp_headers, code, response = api_.delete_job(job_id)
        assert code == HTTPStatus.OK


def test_delete_job(api_):
    rsp_headers, code, response = api_.delete_job('does-not-exist')

    assert code == HTTPStatus.NOT_FOUND

    req_body_sync = {
        'inputs': {
            'name': 'Sync Test Deletion'
        }
    }

    req_body_async = {
        'mode': 'async',
        'inputs': {
            'name': 'Async Test Deletion'
        }
    }

    req = mock_request(data=req_body_sync)
    rsp_headers, code, response = api_.execute_process(
        req, 'hello-world')

    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert 'Location' in rsp_headers
    assert data['value'] == 'Hello Sync Test Deletion!'

    job_id = rsp_headers['Location'].split('/')[-1]
    rsp_headers, code, response = api_.delete_job(job_id)

    assert code == HTTPStatus.OK

    rsp_headers, code, response = api_.delete_job(job_id)
    assert code == HTTPStatus.NOT_FOUND

    req = mock_request(data=req_body_async)
    rsp_headers, code, response = api_.execute_process(
        req, 'hello-world')

    assert code == HTTPStatus.CREATED
    assert 'Location' in rsp_headers

    time.sleep(2)  # Allow time for async execution to complete
    job_id = rsp_headers['Location'].split('/')[-1]
    rsp_headers, code, response = api_.delete_job(job_id)
    assert code == HTTPStatus.OK

    rsp_headers, code, response = api_.delete_job(job_id)
    assert code == HTTPStatus.NOT_FOUND


def test_get_collection_edr_query(config, api_):
    # edr resource
    req = mock_request()
    rsp_headers, code, response = api_.describe_collections(req, 'icoads-sst')
    collection = json.loads(response)
    parameter_names = list(collection['parameter-names'].keys())
    parameter_names.sort()
    assert len(parameter_names) == 4
    assert parameter_names == ['AIRT', 'SST', 'UWND', 'VWND']

    # no coords parameter
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.BAD_REQUEST

    # bad query type
    req = mock_request({'coords': 'POINT(11 11)'})
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'corridor')
    assert code == HTTPStatus.BAD_REQUEST

    # bad coords parameter
    req = mock_request({'coords': 'gah'})
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.BAD_REQUEST

    # bad parameter-name parameter
    req = mock_request({
        'coords': 'POINT(11 11)', 'parameter-name': 'bad'
    })
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.BAD_REQUEST

    # all parameters
    req = mock_request({'coords': 'POINT(11 11)'})
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.OK

    data = json.loads(response)

    axes = list(data['domain']['axes'].keys())
    axes.sort()
    assert len(axes) == 3
    assert axes == ['TIME', 'x', 'y']

    assert data['domain']['axes']['x']['start'] == 11.0
    assert data['domain']['axes']['x']['stop'] == 11.0
    assert data['domain']['axes']['y']['start'] == 11.0
    assert data['domain']['axes']['y']['stop'] == 11.0

    parameters = list(data['parameters'].keys())
    parameters.sort()
    assert len(parameters) == 4
    assert parameters == ['AIRT', 'SST', 'UWND', 'VWND']

    # single parameter
    req = mock_request({
        'coords': 'POINT(11 11)', 'parameter-name': 'SST'
    })
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.OK

    data = json.loads(response)

    assert len(data['parameters'].keys()) == 1
    assert list(data['parameters'].keys())[0] == 'SST'

    # some data
    req = mock_request({
        'coords': 'POINT(11 11)', 'datetime': '2000-01-16'
    })
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.OK

    # no data
    req = mock_request({
        'coords': 'POINT(11 11)', 'datetime': '2000-01-17'
    })
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.NO_CONTENT

    # position no coords
    req = mock_request({
        'datetime': '2000-01-17'
    })
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'position')
    assert code == HTTPStatus.BAD_REQUEST

    # cube bbox parameter 4 dimensional
    req = mock_request({
        'bbox': '0,0,10,10'
    })
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'cube')
    assert code == HTTPStatus.OK

    # cube bad bbox parameter
    req = mock_request({
        'bbox': '0,0,10'
    })
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'cube')
    assert code == HTTPStatus.BAD_REQUEST

    # cube no bbox parameter
    req = mock_request({})
    rsp_headers, code, response = api_.get_collection_edr_query(
        req, 'icoads-sst', None, 'cube')
    assert code == HTTPStatus.BAD_REQUEST


def test_validate_bbox():
    assert validate_bbox('1,2,3,4') == [1, 2, 3, 4]
    assert validate_bbox('1,2,3,4,5,6') == [1, 2, 3, 4, 5, 6]
    assert validate_bbox('-142,42,-52,84') == [-142, 42, -52, 84]
    assert (validate_bbox('-142.1,42.12,-52.22,84.4') ==
            [-142.1, 42.12, -52.22, 84.4])
    assert (validate_bbox('-142.1,42.12,-5.28,-52.22,84.4,7.39') ==
            [-142.1, 42.12, -5.28, -52.22, 84.4, 7.39])

    assert (validate_bbox('177.0,65.0,-177.0,70.0') ==
            [177.0, 65.0, -177.0, 70.0])

    with pytest.raises(ValueError):
        validate_bbox('1,2,4')

    with pytest.raises(ValueError):
        validate_bbox('1,2,4,5,6')

    with pytest.raises(ValueError):
        validate_bbox('3,4,1,2')

    with pytest.raises(ValueError):
        validate_bbox('1,2,6,4,5,3')


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
    assert validate_datetime(config, '2004/') == '2004/..'
    assert validate_datetime(config, '/2005') == '../2005'
    assert validate_datetime(config, '2004-10/2005-10') == '2004-10/2005-10'
    assert (validate_datetime(config, '2001-10-30/2002-10-30') ==
            '2001-10-30/2002-10-30')

    with pytest.raises(ValueError):
        _ = validate_datetime(config, '2007-11-01/..')
    with pytest.raises(ValueError):
        _ = validate_datetime(config, '2009/..')
    with pytest.raises(ValueError):
        _ = validate_datetime(config, '../2000-09')
    with pytest.raises(ValueError):
        _ = validate_datetime(config, '../1999')


@pytest.mark.parametrize("value, expected", [
    ('time(2000-11-11)', {'time': ['2000-11-11']}),
    ('time("2000-11-11")', {'time': ['2000-11-11']}),
    ('time("2000-11-11T00:11:11")', {'time': ['2000-11-11T00:11:11']}),
    ('time("2000-11-11T11:12:13":"2021-12-22T:13:33:33")', {'time': ['2000-11-11T11:12:13', '2021-12-22T:13:33:33']}),  # noqa
    ('lat(40)', {'lat': [40]}),
    ('lat(0:40)', {'lat': [0, 40]}),
    ('foo("bar")', {'foo': ['bar']}),
    ('foo("bar":"baz")', {'foo': ['bar', 'baz']})
])
def test_validate_subset(value, expected):
    assert validate_subset(value) == expected

    with pytest.raises(ValueError):
        validate_subset('foo("bar)')


def test_get_exception(config, api_):
    d = api_.get_exception(500, {}, 'json', 'NoApplicableCode', 'oops')
    assert d[0] == {}
    assert d[1] == 500
    content = json.loads(d[2])
    assert content['code'] == 'NoApplicableCode'
    assert content['description'] == 'oops'

    d = api_.get_exception(500, {}, 'html', 'NoApplicableCode', 'oops')
    assert d[0] == {'Content-Type': 'text/html'}
