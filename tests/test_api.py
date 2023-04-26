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

import copy
import json
import logging
import time
import gzip
from http import HTTPStatus
import re

from pyld import jsonld
import pytest
import pyproj
from shapely.geometry import Point

from pygeoapi.api import (
    API, APIRequest, validate_bbox, validate_datetime,
    validate_subset, __version__
)
from pygeoapi.util import (yaml_load, F_JSON, F_HTML, F_JSONLD,
                           F_GZIP, FORMAT_TYPES,
                           get_crs_from_uri, get_api_rules, get_base_url)

from .util import (get_test_file_path, mock_request,
                   mock_flask, mock_starlette)

LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def config_with_rules() -> dict:
    """ Returns a pygeoapi configuration with default API rules. """
    with open(get_test_file_path('pygeoapi-test-config-apirules.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def config_enclosure() -> dict:
    """ Returns a pygeoapi configuration with enclosure links. """
    with open(get_test_file_path('pygeoapi-test-config-enclosure.yml')) as fh:
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
def enclosure_api(config_enclosure):
    """ Returns an API instance with a collection with enclosure links. """
    return API(config_enclosure)


@pytest.fixture()
def rules_api(config_with_rules):
    """ Returns an API instance with URL prefix and strict slashes policy.
    The API version is extracted from the current version here.
    """
    return API(config_with_rules)


@pytest.fixture()
def api_hidden_resources(config_hidden_resources):
    return API(config_hidden_resources)


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


def test_apirules_active(config_with_rules, rules_api):
    assert rules_api.config == config_with_rules
    rules = get_api_rules(config_with_rules)
    base_url = get_base_url(config_with_rules)

    # Test Flask
    flask_prefix = rules.get_url_prefix('flask')
    with mock_flask('pygeoapi-test-config-apirules.yml') as flask_client:
        # Test happy path
        response = flask_client.get(f'{flask_prefix}/conformance')
        assert response.status_code == 200
        assert response.headers['X-API-Version'] == __version__
        assert response.request.url == \
               flask_client.application.url_for('pygeoapi.conformance')
        response = flask_client.get(f'{flask_prefix}/static/img/pygeoapi.png')
        assert response.status_code == 200
        # Test that static resources also work without URL prefix
        response = flask_client.get('/static/img/pygeoapi.png')
        assert response.status_code == 200

        # Test strict slashes
        response = flask_client.get(f'{flask_prefix}/conformance/')
        assert response.status_code == 404
        # For the landing page ONLY, trailing slashes are actually preferred.
        # See https://docs.opengeospatial.org/is/17-069r4/17-069r4.html#_api_landing_page  # noqa
        # Omitting the trailing slash should lead to a redirect.
        response = flask_client.get(f'{flask_prefix}/')
        assert response.status_code == 200
        response = flask_client.get(flask_prefix)
        assert response.status_code in (307, 308)

        # Test links on landing page for correct URLs
        response = flask_client.get(flask_prefix, follow_redirects=True)
        assert response.status_code == 200
        assert response.is_json
        links = response.json['links']
        assert all(
            href.startswith(base_url) for href in (rel['href'] for rel in links)  # noqa
        )

    # Test Starlette
    starlette_prefix = rules.get_url_prefix('starlette')
    with mock_starlette('pygeoapi-test-config-apirules.yml') as starlette_client:  # noqa
        # Test happy path
        response = starlette_client.get(f'{starlette_prefix}/conformance')
        assert response.status_code == 200
        assert response.headers['X-API-Version'] == __version__
        response = starlette_client.get(f'{starlette_prefix}/static/img/pygeoapi.png')  # noqa
        assert response.status_code == 200
        # Test that static resources also work without URL prefix
        response = starlette_client.get('/static/img/pygeoapi.png')
        assert response.status_code == 200

        # Test strict slashes
        response = starlette_client.get(f'{starlette_prefix}/conformance/')
        assert response.status_code == 404
        # For the landing page ONLY, trailing slashes are actually preferred.
        # See https://docs.opengeospatial.org/is/17-069r4/17-069r4.html#_api_landing_page  # noqa
        # Omitting the trailing slash should lead to a redirect.
        response = starlette_client.get(f'{starlette_prefix}/')
        assert response.status_code == 200
        response = starlette_client.get(starlette_prefix)
        assert response.status_code in (307, 308)

        # Test links on landing page for correct URLs
        response = starlette_client.get(starlette_prefix, follow_redirects=True)  # noqa
        assert response.status_code == 200
        links = response.json()['links']
        assert all(
            href.startswith(base_url) for href in (rel['href'] for rel in links)  # noqa
        )


def test_apirules_inactive(config, api_):
    assert api_.config == config
    rules = get_api_rules(config)

    # Test Flask
    flask_prefix = rules.get_url_prefix('flask')
    assert flask_prefix == ''
    with mock_flask('pygeoapi-test-config.yml') as flask_client:
        response = flask_client.get('')
        assert response.status_code == 200
        response = flask_client.get('/conformance')
        assert response.status_code == 200
        assert 'X-API-Version' not in response.headers
        assert response.request.url == \
               flask_client.application.url_for('pygeoapi.conformance')
        response = flask_client.get('/static/img/pygeoapi.png')
        assert response.status_code == 200

        # Test trailing slashes
        response = flask_client.get('/')
        assert response.status_code == 200
        response = flask_client.get('/conformance/')
        assert response.status_code == 200
        assert 'X-API-Version' not in response.headers

    # Test Starlette
    starlette_prefix = rules.get_url_prefix('starlette')
    assert starlette_prefix == ''
    with mock_starlette('pygeoapi-test-config.yml') as starlette_client:
        response = starlette_client.get('')
        assert response.status_code == 200
        response = starlette_client.get('/conformance')
        assert response.status_code == 200
        assert 'X-API-Version' not in response.headers
        assert str(response.url) == f"{starlette_client.base_url}/conformance"
        response = starlette_client.get('/static/img/pygeoapi.png')
        assert response.status_code == 200

        # Test trailing slashes
        response = starlette_client.get('/')
        assert response.status_code == 200
        response = starlette_client.get('/conformance/', follow_redirects=True)
        assert response.status_code == 200
        assert 'X-API-Version' not in response.headers


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


def test_gzip_csv(config, api_):
    req_csv = mock_request({'f': 'csv'})
    rsp_csv_headers, _, rsp_csv = api_.get_collection_items(req_csv, 'obs')
    assert rsp_csv_headers['Content-Type'] == 'text/csv; charset=utf-8'
    rsp_csv = rsp_csv.decode('utf-8')

    req_csv = mock_request({'f': 'csv'}, HTTP_ACCEPT_ENCODING=F_GZIP)
    rsp_csv_headers, _, rsp_csv_gzip = api_.get_collection_items(req_csv, 'obs') # noqa
    assert rsp_csv_headers['Content-Type'] == 'text/csv; charset=utf-8'
    rsp_csv_ = gzip.decompress(rsp_csv_gzip).decode('utf-8')
    assert rsp_csv == rsp_csv_

    # Use utf-16 encoding
    config['server']['encoding'] = 'utf-16'
    api_ = API(config)

    req_csv = mock_request({'f': 'csv'}, HTTP_ACCEPT_ENCODING=F_GZIP)
    rsp_csv_headers, _, rsp_csv_gzip = api_.get_collection_items(req_csv, 'obs') # noqa
    assert rsp_csv_headers['Content-Type'] == 'text/csv; charset=utf-8'
    rsp_csv_ = gzip.decompress(rsp_csv_gzip).decode('utf-8')
    assert rsp_csv == rsp_csv_


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
    assert len(root['conformsTo']) == 25
    assert 'http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs' \
           in root['conformsTo']

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
    assert len(collections['collections']) == 8
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

    # OAPIF Part 2 CRS 6.2.1 A, B, configured CRS + defaults
    assert collection['crs'] is not None
    crs_set = [
        'http://www.opengis.net/def/crs/EPSG/0/28992',
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        'http://www.opengis.net/def/crs/EPSG/0/4326',
    ]
    for crs in crs_set:
        assert crs in collection['crs']
    assert collection['storageCRS'] is not None
    assert collection['storageCRS'] == 'http://www.opengis.net/def/crs/OGC/1.3/CRS84' # noqa
    assert 'storageCrsCoordinateEpoch' not in collection

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

    # OAPIF Part 2 CRS 6.2.1 B, defaults when not configured
    assert collection['crs'] is not None
    default_crs_list = [
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84h',
    ]
    contains_default = False
    for crs in default_crs_list:
        if crs in default_crs_list:
            contains_default = True
    assert contains_default
    assert collection['storageCRS'] is not None
    assert collection['storageCRS'] == 'http://www.opengis.net/def/crs/OGC/1.3/CRS84' # noqa
    assert collection['storageCrsCoordinateEpoch'] == 2017.23


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

    req = mock_request({'bbox': '1,2,3,4', 'bbox-crs': 'bad_value'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    req = mock_request({'bbox-crs': 'bad_value'})
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    # bbox-crs must be in configured values for Collection
    req = mock_request({'bbox': '1,2,3,4', 'bbox-crs': 'http://www.opengis.net/def/crs/EPSG/0/4258'}) # noqa
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.BAD_REQUEST

    # bbox-crs must be in configured values for Collection (CSV will ignore)
    req = mock_request({'bbox': '52,4,53,5', 'bbox-crs': 'http://www.opengis.net/def/crs/EPSG/0/4326'}) # noqa
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.OK

    # bbox-crs can be a default even if not configured
    req = mock_request({'bbox': '4,52,5,53', 'bbox-crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'}) # noqa
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.OK

    # bbox-crs can be a default even if not configured
    req = mock_request({'bbox': '4,52,5,53'}) # noqa
    rsp_headers, code, response = api_.get_collection_items(req, 'obs')

    assert code == HTTPStatus.OK

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


def test_get_collection_items_crs(config, api_):

    # Invalid CRS query parameter
    req = mock_request({'crs': '4326'})
    rsp_headers, code, response = api_.get_collection_items(req, 'norway_pop')

    assert code == HTTPStatus.BAD_REQUEST

    # Unsupported CRS
    req = mock_request({'crs': 'http://www.opengis.net/def/crs/EPSG/0/32633'})
    rsp_headers, code, response = api_.get_collection_items(req, 'norway_pop')

    assert code == HTTPStatus.BAD_REQUEST

    # Supported CRSs
    default_crs = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
    storage_crs = 'http://www.opengis.net/def/crs/EPSG/0/25833'
    crs_4258 = 'http://www.opengis.net/def/crs/EPSG/0/4258'
    supported_crs_list = [default_crs, storage_crs, crs_4258]

    for crs in supported_crs_list:
        req = mock_request({'crs': crs})
        rsp_headers, code, response = api_.get_collection_items(
            req, 'norway_pop',
        )

        assert code == HTTPStatus.OK
        assert rsp_headers['Content-Crs'] == f'<{crs}>'

    # With CRS query parameter, using storageCRS
    req = mock_request({'crs': storage_crs})
    rsp_headers, code, response = api_.get_collection_items(req, 'norway_pop')

    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Crs'] == f'<{storage_crs}>'

    features_25833 = json.loads(response)

    # With CRS query parameter resulting in coordinates transformation
    req = mock_request({'crs': crs_4258})
    rsp_headers, code, response = api_.get_collection_items(req, 'norway_pop')

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
    req = mock_request({})
    rsp_headers, code, response = api_.get_collection_items(req, 'norway_pop')

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
    req = mock_request()
    _, code, _ = api_.manage_collection_item(req, 'options', 'foo')
    assert code == HTTPStatus.NOT_FOUND

    req = mock_request()
    rsp_headers, code, _ = api_.manage_collection_item(req, 'options', 'obs')
    assert code == HTTPStatus.OK
    assert rsp_headers['Allow'] == 'HEAD, GET'

    req = mock_request()
    rsp_headers, code, _ = api_.manage_collection_item(
        req, 'options', 'obs', 'ressource_id')
    assert code == HTTPStatus.OK
    assert rsp_headers['Allow'] == 'HEAD, GET'


def test_manage_collection_item_editable_options_req(config):
    """Test OPTIONS request on a editable items endpoint"""
    config = copy.deepcopy(config)
    config['resources']['obs']['providers'][0]['editable'] = True
    api_ = API(config)

    req = mock_request()
    rsp_headers, code, _ = api_.manage_collection_item(req, 'options', 'obs')
    assert code == HTTPStatus.OK
    assert rsp_headers['Allow'] == 'HEAD, GET, POST'

    req = mock_request()
    rsp_headers, code, _ = api_.manage_collection_item(
        req, 'options', 'obs', 'ressource_id')
    assert code == HTTPStatus.OK
    assert rsp_headers['Allow'] == 'HEAD, GET, PUT, DELETE'


def test_describe_collections_enclosures(config_enclosure, enclosure_api):
    original_enclosures = {
        lnk['title']: lnk
        for lnk in config_enclosure['resources']['objects']['links']
        if lnk['rel'] == 'enclosure'
    }

    req = mock_request()
    _, _, response = enclosure_api.describe_collections(req, 'objects')
    features = json.loads(response)
    modified_enclosures = {
        lnk['title']: lnk for lnk in features['links']
        if lnk['rel'] == 'enclosure'
    }

    # If type and length is set, do not verify/update link
    assert original_enclosures['download link 1'] == \
           modified_enclosures['download link 1']
    # If length is missing, modify link type and length
    assert original_enclosures['download link 2']['type'] == \
           modified_enclosures['download link 2']['type']
    assert modified_enclosures['download link 2']['type'] == \
           modified_enclosures['download link 3']['type']
    assert 'length' not in original_enclosures['download link 2']
    assert modified_enclosures['download link 2']['length'] > 0
    assert modified_enclosures['download link 2']['length'] == \
           modified_enclosures['download link 3']['length']
    assert original_enclosures['download link 3']['type'] != \
           modified_enclosures['download link 3']['type']


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


@pytest.mark.parametrize(
    'limit, expected_len_processes, expected_len_links', [
        pytest.param(1, 1, 5),
        pytest.param(None, 2, 3),
    ]
)
def test_list_processes(
        config, api_, limit, expected_len_processes, expected_len_links):
    req = mock_request({'limit': limit} if limit is not None else {})
    # Test for description of single processes
    rsp_headers, code, response = api_.list_processes(req)
    data = json.loads(response)
    assert code == HTTPStatus.OK
    assert len(data['processes']) == expected_len_processes
    assert len(data['links']) == expected_len_links


def test_get_process(config, api_):
    req = mock_request()

    # Test for undefined process
    rsp_headers, code, response = api_.get_process(req, 'foo')
    data = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND
    assert data['code'] == 'NoSuchProcess'

    # Test for particular, defined process
    rsp_headers, code, response = api_.get_process(req, 'hello-world')
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
    rsp_headers, code, response = api_.get_process(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    # No language requested: return default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check JSON response when requested in headers
    req = mock_request(HTTP_ACCEPT='application/json')
    rsp_headers, code, response = api_.get_process(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check HTML response when requested with query parameter
    req = mock_request({'f': 'html'})
    rsp_headers, code, response = api_.get_process(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    # No language requested: return default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check JSON response when requested with query parameter
    req = mock_request({'f': 'json'})
    rsp_headers, code, response = api_.get_process(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'en-US'

    # Check JSON response when requested with French language parameter
    req = mock_request({'lang': 'fr'})
    rsp_headers, code, response = api_.get_process(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'fr-CA'
    process = json.loads(response)
    assert process['title'] == 'Bonjour le Monde'

    # Check JSON response when language requested in headers
    req = mock_request(HTTP_ACCEPT_LANGUAGE='fr')
    rsp_headers, code, response = api_.get_process(req, 'hello-world')
    assert code == HTTPStatus.OK
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]
    assert rsp_headers['Content-Language'] == 'fr-CA'

    # Test for undefined process
    req = mock_request()
    rsp_headers, code, response = api_.get_process(req, 'goodbye-world')
    data = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND
    assert data['code'] == 'NoSuchProcess'
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_JSON]


@pytest.mark.parametrize(
    'process_id, payload, expected_status_code, expected_error_code',
    [
        pytest.param(
            'hello-world',
            '',
            HTTPStatus.BAD_REQUEST,
            'MissingParameterValue'
        ),
        pytest.param(
            'foo',
            {'inputs': {'name': 'test'}},
            HTTPStatus.NOT_FOUND,
            'NoSuchProcess'
        ),
        pytest.param(
            'hello-world',
            {'inputs': {'foo': 'Tèst'}},
            HTTPStatus.BAD_REQUEST,
            'MissingParameterValue',
        ),
        pytest.param(
            'hello-world',
            {'inputs': {}},
            HTTPStatus.BAD_REQUEST,
            'MissingParameterValue',
        ),
        pytest.param(
            'hello-world',
            {'inputs': {'name': None}},
            HTTPStatus.BAD_REQUEST,
            'InvalidParameterValue',
        ),
    ]
)
def test_execute_process_invalid_parameters(
        config, api_, process_id, payload,
        expected_status_code, expected_error_code
):
    req = mock_request(data=payload)
    rsp_headers, code, response = api_.execute_process(req, process_id)
    assert rsp_headers['Content-Language'] == 'en-US'
    assert code == expected_status_code
    assert 'Location' not in rsp_headers
    data = json.loads(response)
    assert data['code'] == expected_error_code


@pytest.mark.parametrize('payload, expected_status, expected_payload', [
    pytest.param(
        {
            'inputs': {'name': 'Test'},
            'response': 'document'
        },
        HTTPStatus.OK,
        '{"echo": "Hello Test!"}'
    ),
    pytest.param(
        {
            'inputs': {'name': 'Tést'},
            'response': 'document'
        },
        HTTPStatus.OK,
        '{"echo": "Hello Tést!"}'
    ),
    pytest.param(
        {
            'inputs': {
                'name': 'Tést',
                'message': 'This is a test.'
            },
            'response': 'document'
        },
        HTTPStatus.OK,
        '{"echo": "Hello Tést! This is a test."}'
    ),
    pytest.param(
        {
            'inputs': {'name': 'Test'},
            'response': 'document'
        },
        HTTPStatus.OK,
        '{"echo": "Hello Test!"}'
    ),
])
def test_execute_process_document_response(
        config, api_, payload, expected_status, expected_payload):
    req = mock_request(data=payload)
    rsp_headers, code, response = api_.execute_process(req, 'hello-world')
    print(f"response: {response}")
    assert code == expected_status
    assert 'Link' in rsp_headers
    assert response == expected_payload


@pytest.mark.parametrize('payload, expected_status', [
    pytest.param(
        {
            'inputs': {'name': 'Test'},
            'response': 'document'
        },
        HTTPStatus.CREATED,
    ),
])
def test_execute_process_document_async(
        config, api_, payload, expected_status):
    req = mock_request(data=payload, HTTP_Prefer='respond-async')
    rsp_headers, code, response = api_.execute_process(req, 'hello-world')
    print(f"response_code: {code}")
    print(f"response_headers: {rsp_headers}")
    print(f"response: {response}")
    assert code == expected_status
    assert 'Location' in rsp_headers
    data = json.loads(response)
    assert isinstance(data, dict)
    assert data.get('jobID') is not None
    assert data.get('processID') is not None
    assert data.get('status') == 'accepted'


def test_delete_job_non_existent(api_):
    req = mock_request()
    rsp_headers, code, response = api_.delete_job(req, 'does-not-exist')
    assert code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize('headers, payload, check_response_header', [
    pytest.param(
        None,
        {'inputs': {'name': 'Sync test deletion'}},
        'Link',
    ),
    pytest.param(
        {'HTTP_Prefer': 'respond-async'},
        {'inputs': {'name': 'Async test deletion'}},
        'Location'
    ),
])
def test_delete_job(api_, headers, payload, check_response_header):
    # create the job
    req = mock_request(
        data=payload, **headers if headers is not None else {})
    rsp_headers, code, response = api_.execute_process(
        req, 'hello-world')

    print(f'response: {response}')
    print(f'response headers: {rsp_headers}')

    if 'respond-async' in (headers.values() if headers else []):
        # wait a bit in order to allow the generation of any inputs (for
        # async processes)
        time.sleep(2)

    # now ask for it to be deleted
    job_id = re.search(
        r'http://localhost:5000/jobs/(?P<job_id>[0-9a-z\-]+)',
        rsp_headers[check_response_header]
    ).groupdict()['job_id']
    rsp_headers, deletion_code, deletion_response = api_.delete_job(
        mock_request(), job_id)
    assert deletion_code == HTTPStatus.OK
    deletion_data = json.loads(deletion_response)
    assert deletion_data['jobID'] == job_id
    assert deletion_data['status'] == 'dismissed'

    # double check that it is not there anymore
    rsp_headers, code, response = api_.delete_job(mock_request(), job_id)
    assert code == HTTPStatus.NOT_FOUND

    # async_req = mock_request(
    #     data={'inputs': {'name': 'Async test deletion demo'}},
    #     HTTP_Prefer='respond-async'
    # )
    # rsp_headers, code, response = api_.execute_process(
    #     async_req, 'hello-world')
    # time.sleep(2)  # Allow time for async execution to complete
    # job_id = response.json()['jobID']
    # rsp_headers, code, response = api_.delete_job(job_id)
    # assert code == HTTPStatus.OK
    # deletion_data = response.json()
    # assert deletion_data['status'] == 'dismissed'
    # assert deletion_data['jobID'] == job_id
    # rsp_headers, code, response = api_.delete_job(job_id)
    # assert code == HTTPStatus.NOT_FOUND


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
