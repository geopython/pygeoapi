# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Bernhard Mallinger <bernhard.mallinger@eox.at>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2026 Tom Kralidis
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
# Copyright (c) 2026 Francesco Bartoli
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
import gzip
from http import HTTPStatus

from pyld import jsonld
import pytest

from pygeoapi.api import (
    API, APIRequest, CONFORMANCE_CLASSES, FORMAT_TYPES, F_HTML, F_JSON,
    F_JSONLD, F_GZIP, __version__, validate_bbox, validate_datetime,
    evaluate_limit, validate_subset, landing_page, openapi_, conformance,
    describe_collections, get_collection_schema,
)
from pygeoapi.util import yaml_load, get_api_rules, get_base_url

from tests.util import (get_test_file_path, mock_api_request, mock_flask,
                        mock_starlette, mock_request)


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
def enclosure_api(config_enclosure, openapi):
    """ Returns an API instance with a collection with enclosure links. """
    return API(config_enclosure, openapi)


@pytest.fixture()
def rules_api(config_with_rules, openapi):
    """ Returns an API instance with URL prefix and strict slashes policy.
    The API version is extracted from the current version here.
    """
    return API(config_with_rules, openapi)


@pytest.fixture()
def api_hidden_resources(config_hidden_resources, openapi):
    return API(config_hidden_resources, openapi)


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
        apireq = APIRequest.from_flask(req, api_.locales)
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
        assert links[0]['rel'] == 'about'
        assert all(
            href.startswith(base_url) for href in (rel['href'] for rel in links[1:])  # noqa
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
        assert links[0]['rel'] == 'about'
        assert all(
            href.startswith(base_url) for href in (rel['href'] for rel in links[1:])  # noqa
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


def test_openapi(config, api_, openapi):
    assert api_.config == config
    assert isinstance(api_.config, dict)

    req = mock_api_request(HTTP_ACCEPT='application/json')
    rsp_headers, code, response = openapi_(api_, req)
    assert rsp_headers['Content-Type'] == 'application/vnd.oai.openapi+json;version=3.0'  # noqa
    # No language requested: should be set to default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'
    root = json.loads(response)
    assert isinstance(root, dict)

    a = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    req = mock_api_request(HTTP_ACCEPT=a)
    rsp_headers, code, response = openapi_(api_, req)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML] == \
           FORMAT_TYPES[F_HTML]

    assert 'Swagger UI' in response

    a = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    req = mock_api_request({'ui': 'redoc'}, HTTP_ACCEPT=a)
    rsp_headers, code, response = openapi_(api_, req)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML] == \
           FORMAT_TYPES[F_HTML]

    assert 'ReDoc' in response

    assert api_.get_collections_url() == 'http://localhost:5000/collections'


def test_api_exception(config, api_):

    with mock_flask('pygeoapi-test-config.yml') as flask_client:
        response = flask_client.get('?f=foo')
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.headers['Content-Language'] == 'en-US'

        # When a language is set, the exception should still be English
        response = flask_client.get('?f=foo&lang=fr')
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.headers['Content-Language'] == 'en-US'

    with mock_starlette('pygeoapi-test-config.yml') as starlette_client:
        response = starlette_client.get('?f=foo')
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.headers['Content-Language'] == 'en-US'

        # When a language is set, the exception should still be English
        response = starlette_client.get('?f=foo&lang=fr')
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.headers['Content-Language'] == 'en-US'


def test_gzip(config, openapi):

    common = {'Accept_Encoding': F_GZIP}
    headers_gzip_json = {**common, 'Accept': FORMAT_TYPES[F_JSON]}
    headers_gzip_jsonld = {**common, 'Accept': FORMAT_TYPES[F_JSONLD]}
    headers_gzip_html = {**common, 'Accept': FORMAT_TYPES[F_HTML]}
    headers_gzip_gzip = {**common, 'Accept': 'application/gzip'}

    with mock_flask('pygeoapi-test-config.yml') as flask_client:
        response_json = flask_client.get("", headers=headers_gzip_json)
        assert response_json.headers['Content-Type'] == FORMAT_TYPES[F_JSON]

        response_jsonld = flask_client.get("", headers=headers_gzip_jsonld)
        assert response_jsonld.headers['Content-Type'] == \
            FORMAT_TYPES[F_JSONLD]

        response_html = flask_client.get("", headers=headers_gzip_html)
        assert response_html.headers['Content-Type'] == FORMAT_TYPES[F_HTML]

        response_gzip = flask_client.get("", headers=headers_gzip_gzip)
        assert response_gzip.headers['Content-Type'] == FORMAT_TYPES[F_JSON]

    with mock_flask('pygeoapi-test-config.yml') as flask_client:
        from pygeoapi import flask_app

        # Add gzip to server and use utf-16 encoding
        config['server']['gzip'] = True
        enc_16 = 'utf-16'
        config['server']['encoding'] = enc_16
        flask_app.api_ = API(config, openapi)

        response = flask_client.get("", headers=headers_gzip_json)
        # Validate compressed json response
        assert response.headers['Content-Type'] == \
            f'{FORMAT_TYPES[F_JSON]}; charset={enc_16}'
        assert response.headers['Content-Encoding'] == F_GZIP
        parsed_gzip_json = gzip.decompress(response.data).decode(enc_16)
        assert isinstance(parsed_gzip_json, str)
        parsed_gzip_json = json.loads(parsed_gzip_json)
        assert isinstance(parsed_gzip_json, dict)
        assert parsed_gzip_json == response_json.json

        # Validate compressed jsonld response
        response = flask_client.get("", headers=headers_gzip_jsonld)
        assert response.headers['Content-Type'] == \
            f'{FORMAT_TYPES[F_JSONLD]}; charset={enc_16}'
        assert response.headers['Content-Encoding'] == F_GZIP
        parsed_gzip_jsonld = gzip.decompress(response.data).decode(enc_16)
        assert isinstance(parsed_gzip_jsonld, str)
        parsed_gzip_jsonld = json.loads(parsed_gzip_jsonld)
        assert isinstance(parsed_gzip_jsonld, dict)
        assert parsed_gzip_jsonld == response_jsonld.json

        # Validate compressed html response
        response = flask_client.get("", headers=headers_gzip_html)
        assert response.headers['Content-Type'] == \
            f'{FORMAT_TYPES[F_HTML]}; charset={enc_16}'
        assert response.headers['Content-Encoding'] == F_GZIP
        parsed_gzip_html = gzip.decompress(response.data).decode(enc_16)
        assert isinstance(parsed_gzip_html, str)
        assert parsed_gzip_html == response_html.text

        # Validate compressed gzip response
        response = flask_client.get("", headers=headers_gzip_gzip)
        assert response.headers['Content-Type'] == \
            f'{FORMAT_TYPES[F_GZIP]}; charset={enc_16}'
        assert response.headers['Content-Encoding'] == F_GZIP
        parsed_gzip_gzip = gzip.decompress(response.data).decode(enc_16)
        assert isinstance(parsed_gzip_gzip, str)
        parsed_gzip_gzip = json.loads(parsed_gzip_gzip)
        assert isinstance(parsed_gzip_gzip, dict)


def test_root(config, api_):
    req = mock_api_request()
    rsp_headers, code, response = landing_page(api_, req)
    root = json.loads(response)

    assert rsp_headers['Content-Type'] == 'application/json' == \
           FORMAT_TYPES[F_JSON]
    assert rsp_headers['X-Powered-By'].startswith('pygeoapi')
    assert rsp_headers['Content-Language'] == 'en-US'

    assert isinstance(root, dict)
    assert 'links' in root
    assert root['links'][0]['rel'] == 'about'
    assert root['links'][0]['type'] == 'text/html'
    assert root['links'][0]['href'] == 'http://example.org'
    assert root['links'][1]['rel'] == 'self'
    assert root['links'][1]['type'] == FORMAT_TYPES[F_JSON]
    assert root['links'][1]['href'].endswith('?f=json')
    assert any(link['href'].endswith('f=jsonld') and link['rel'] == 'alternate'
               for link in root['links'])
    assert any(link['href'].endswith('f=html') and link['rel'] == 'alternate'
               for link in root['links'])
    assert len(root['links']) == 12
    assert 'title' in root
    assert root['title'] == 'pygeoapi default instance'
    assert 'description' in root
    assert root['description'] == 'pygeoapi provides an API to geospatial data'

    req = mock_api_request({'f': 'html'})
    rsp_headers, code, response = landing_page(api_, req)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    assert rsp_headers['Content-Language'] == 'en-US'


def test_root_structured_data(config, api_):
    req = mock_api_request({"f": "jsonld"})
    rsp_headers, code, response = landing_page(api_, req)
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
    req = mock_api_request()
    rsp_headers, code, response = conformance(api_, req)
    root = json.loads(response)

    assert isinstance(root, dict)
    assert 'conformsTo' in root
    assert len(root['conformsTo']) == 42
    assert 'http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs' \
           in root['conformsTo']

    req = mock_api_request({'f': 'html'})
    rsp_headers, code, response = conformance(api_, req)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    # No language requested: should be set to default from YAML
    assert rsp_headers['Content-Language'] == 'en-US'


def test_conformance_does_not_mutate_global_list(config, api_):
    """Test conformance method does not mutate CONFORMANCE_CLASSES.

    This test verifies that the global CONFORMANCE_CLASSES list is not
    mutated by calls to the conformance function. The base conformance
    classes should remain unchanged after multiple calls.
    """

    # Store the original length and content of the global list
    original_length = len(CONFORMANCE_CLASSES)
    original_classes = list(CONFORMANCE_CLASSES)

    req = mock_api_request()

    # Make multiple calls to conformance
    for _ in range(3):
        conformance(api_, req)

    # The global list should NOT have been mutated
    assert len(CONFORMANCE_CLASSES) == original_length, (
        f'Global CONFORMANCE_CLASSES was mutated! '
        f'Original length: {original_length}, '
        f'Current length: {len(CONFORMANCE_CLASSES)}. '
        f'The conformance() function should create a copy of the list '
        f'before extending it.'
    )
    assert CONFORMANCE_CLASSES == original_classes, (
        'Global CONFORMANCE_CLASSES content was modified'
    )


def test_describe_collections(config, api_):
    req = mock_api_request({"f": "html"})
    rsp_headers, code, response = describe_collections(api_, req)
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]

    req = mock_api_request()
    rsp_headers, code, response = describe_collections(api_, req)
    collections = json.loads(response)

    assert len(collections) == 2
    assert len(collections['collections']) == 10
    assert len(collections['links']) == 3

    rsp_headers, code, response = describe_collections(api_, req, 'foo')
    collection = json.loads(response)
    assert code == HTTPStatus.NOT_FOUND

    rsp_headers, code, response = describe_collections(api_, req, 'obs')
    collection = json.loads(response)

    assert rsp_headers['Content-Language'] == 'en-US'
    assert collection['id'] == 'obs'
    assert collection['title'] == 'Observations'
    assert collection['description'] == 'My cool observations'
    assert len(collection['links']) == 15

    assert collection['extent'] == {
        'spatial': {
            'bbox': [[-180, -90, 180, 90]],
            'crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
        },
        'temporal': {
            'interval': [
                ['2000-10-30T18:24:39+00:00', '2007-10-30T08:57:29+00:00']
            ],
            'trs': 'http://www.opengis.net/def/uom/ISO-8601/0/Gregorian',
            'grid': {
                'resolution': 'P1D'
            },
            'default': '2000-10-30T18:24:39+00:00'
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
    assert collection['storageCrs'] is not None
    assert collection['storageCrs'] == 'http://www.opengis.net/def/crs/OGC/1.3/CRS84' # noqa
    assert 'storageCrsCoordinateEpoch' not in collection

    # French language request
    req = mock_api_request({'lang': 'fr'})
    rsp_headers, code, response = describe_collections(api_, req, 'obs')
    collection = json.loads(response)

    assert rsp_headers['Content-Language'] == 'fr-CA'
    assert collection['title'] == 'Observations'
    assert collection['description'] == 'Mes belles observations'

    # Check HTML request in an unsupported language
    req = mock_api_request({'f': 'html', 'lang': 'de'})
    rsp_headers, code, response = describe_collections(api_, req, 'obs')
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]
    assert rsp_headers['Content-Language'] == 'en-US'

    # hiearchical collections
    req = mock_api_request()
    rsp_headers, code, response = describe_collections(
        api_, req, 'naturalearth/lakes')

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
    assert collection['storageCrs'] is not None
    assert collection['storageCrs'] == 'http://www.opengis.net/def/crs/OGC/1.3/CRS84' # noqa
    assert collection['storageCrsCoordinateEpoch'] == 2017.23

    # test custom extents
    rsp_headers, code, response = describe_collections(
       api_, req, 'mapserver_world_map')

    collection = json.loads(response)

    assert collection['extent'] == {
        'spatial': {
            'bbox': [[-180, -90, 180, 90]],
            'crs': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
        },
        'custom-extent': {
            'definition': 'https://example.org/custom-extent',
            'interval': [[0, 10]],
            'unit': '°C',
            'grid': {
                'cellsCount': 3,
                'coordinates': [0, 5, 10]
            }
        }
    }


def test_describe_collections_hidden_resources(
        config_hidden_resources, api_hidden_resources):
    req = mock_api_request({})
    rsp_headers, code, response = describe_collections(api_hidden_resources, req)  # noqa
    assert code == HTTPStatus.OK

    assert len(config_hidden_resources['resources']) == 3

    collections = json.loads(response)
    assert len(collections['collections']) == 1


def test_describe_collections_json_ld(config, api_):
    req = mock_api_request({'f': 'jsonld'})
    rsp_headers, code, response = describe_collections(api_, req, 'obs')
    collection = json.loads(response)

    assert '@context' in collection
    expanded = jsonld.expand(collection)[0]
    # Metadata is about a schema:DataCollection that contains a schema:Dataset
    assert not expanded['@id'].endswith('obs')
    assert 'http://schema.org/dataset' in expanded
    assert len(expanded['http://schema.org/dataset']) == 1
    dataset = expanded['http://schema.org/dataset'][0]
    assert dataset['@type'][0] == 'http://schema.org/Dataset'
    assert len(dataset['http://schema.org/distribution']) == 15
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


def test_describe_collections_enclosures(config_enclosure, enclosure_api):
    original_enclosures = {
        lnk['title']: lnk
        for lnk in config_enclosure['resources']['objects']['links']
        if lnk['rel'] == 'enclosure'
    }

    req = mock_api_request()
    _, _, response = describe_collections(enclosure_api, req, 'objects')
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


def test_get_collection_schema(config, api_):
    req = mock_api_request()
    rsp_headers, code, response = get_collection_schema(api_, req, 'notfound')
    assert code == HTTPStatus.NOT_FOUND

    req = mock_api_request({'f': 'html'})
    rsp_headers, code, response = get_collection_schema(api_, req, 'obs')
    assert rsp_headers['Content-Type'] == FORMAT_TYPES[F_HTML]

    req = mock_api_request({'f': 'json'})
    rsp_headers, code, response = get_collection_schema(api_, req, 'obs')
    assert rsp_headers['Content-Type'] == 'application/schema+json'
    schema = json.loads(response)

    assert 'properties' in schema
    assert len(schema['properties']) == 5


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

    d = api_.get_exception(204, {}, 'html', 'NoApplicableCode', 'oops')
    assert len(d[2]) == 0
    d = api_.get_exception(204, {}, 'json', 'NoApplicableCode', 'oops')
    assert len(d[2]) == 0


def test_evaluate_limit():
    collection = {}
    server = {}

    with pytest.raises(ValueError):
        assert evaluate_limit('1.1', server, collection) == 10

    with pytest.raises(ValueError):
        assert evaluate_limit('-12', server, collection) == 10

    assert evaluate_limit('1', server, collection) == 1

    collection = {}
    server = {'default_items': 2, 'max_items': 3}

    assert evaluate_limit(None, server, collection) == 2
    assert evaluate_limit('1', server, collection) == 1
    assert evaluate_limit('4', server, collection) == 3

    collection = {'default_items': 10, 'max_items': 50}
    server = {'default_items': 100, 'max_items': 1000}

    assert evaluate_limit(None, server, collection) == 10
    assert evaluate_limit('40', server, collection) == 40
    assert evaluate_limit('60', server, collection) == 50

    collection = {}
    server = {'default_items': 2, 'max_items': 3, 'on_exceed': 'error'}

    with pytest.raises(ValueError):
        assert evaluate_limit('40', server, collection) == 40

    collection = {'default_items': 10}
    server = {'default_items': 2, 'max_items': 3}

    assert evaluate_limit(None, server, collection) == 10
    assert evaluate_limit('40', server, collection) == 3
