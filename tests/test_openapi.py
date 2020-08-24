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

from pygeoapi.openapi import get_ogc_schemas_location
from pygeoapi.openapi import get_oas_30
import pytest
import os
from pygeoapi.util import yaml_load, filter_dict_by_key_value
import logging

LOGGER = logging.getLogger(__name__)


def test_str2bool():

    default = {
        'url': 'http://localhost:5000'
    }

    osl = get_ogc_schemas_location(default)
    assert osl == 'http://schemas.opengis.net'

    default['ogc_schemas_location'] = 'http://example.org/schemas'
    osl = get_ogc_schemas_location(default)
    assert osl == 'http://example.org/schemas'

    default['ogc_schemas_location'] = '/opt/schemas.opengis.net'
    osl = get_ogc_schemas_location(default)


def get_test_file_path(filename):
    """
    Helper function to open test file safely

    :param filename: file path

    :returns: corrected file path
    """
    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


@pytest.fixture()
def config():
    """
    Get pygeoapi configuration

    :returns: pygeoapi configuration dict
    """
    with open(get_test_file_path('pygeoapi-config-local-openapi.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def get_oas_30_(config):
    """
    Generate OpenAPI 3.0 document from pygeoapi configuration

    :param config: pygeoapi configuration dict

    :returns: OpenAPI definition dict
    """
    return get_oas_30(config)


@pytest.fixture()
def components(get_oas_30_):
    """
    Get components from OpenAPI document

    :param get_oas_30_: OpenAPI definition dict

    :returns: components dict
    """
    return get_oas_30_['components']


@pytest.fixture()
def schemas(components):
    """
    Get schemas from components

    :param components: components dict

    :returns: schemas dict
    """
    return components['schemas']


@pytest.fixture()
def paths(get_oas_30_):
    """
    Get paths from OpenAPI document

    :param get_oas_30_: OpenAPI definition dict

    :returns: paths dict
    """
    return get_oas_30_['paths']


@pytest.fixture()
def collections(config):
    """
    Get collections from pygeoapi configuration

    :param config: pygeoapi configuration dict

    :returns: collections dict
    """
    return filter_dict_by_key_value(config['resources'],
                                    'type',
                                    'collection')


def items_path(coll_name):
    """
    Generate items path from collection name

    :param coll_name: collection name

    :returns: items path
    """
    return '/collections/{}/items'.format(coll_name)


def item_path(coll_name):
    """
    Generate item path from collection name

    :param coll_name: collection name

    :returns: item path
    """
    return '/collections/{}/items/{{featureId}}'.format(coll_name)


def supports_transactions(collection):
    """
    Check if given collection supports transactions

    :param collection: collection dict

    :returns: boolean value
    """
    for provider in collection['providers']:
        if provider['type'] == 'feature' and\
           'extensions' in provider:
            for extension in provider['extensions']:
                if extension['type'] == 'transaction' and\
                   extension['enabled']:
                    return True
    return False


def test_name_value_pair_obj(schemas):
    """
    Assertions for nameValuePairObj in OpenAPI document
    :param schemas: schemas dict
    """
    assert 'nameValuePairObj' in schemas
    assert 'name' in schemas['nameValuePairObj']['properties']
    assert 'value' in schemas['nameValuePairObj']['properties']


def post_schema_assertions(verbs):
    """
    Assertions for post schema in OpenAPI document

    :param verbs: verbs dict
    """
    # assertion for post
    assert 'post' in verbs
    post = verbs['post']
    assert isinstance(post, dict)

    # assertion for post attributes
    post_attrib = ['summary',
                   'description',
                   'tags',
                   'requestBody',
                   'responses']
    for attrib in post_attrib:
        assert attrib in post

    # assertion for post request attributes
    post_req_attrib = ['required',
                       'content']
    post_req = post['requestBody']
    assert isinstance(post_req, dict)
    for attrib in post_req_attrib:
        assert attrib in post_req

    # assertion for post request content attributes
    post_req_content_attrib = ['type',
                               'geometry',
                               'properties']
    post_req_content = post_req['content']['application/geo+json']
    assert isinstance(post_req_content, dict)
    post_req_content_schema = post_req_content['schema']
    assert isinstance(post_req_content_schema, dict)
    for attrib in post_req_content_attrib:
        assert attrib in post_req_content_schema['properties']

    # assertion for post response attributes
    post_resp_attrib = ['201',
                        '400',
                        '404',
                        '500']
    post_resp = post['responses']
    for attrib in post_resp_attrib:
        assert attrib in post_resp


def patch_schema_assertions(verbs):
    """
    Assertions for patch schema in OpenAPI document

    :param verbs: verbs dict
    """
    # assertion for patch
    assert 'patch' in verbs
    patch = verbs['patch']
    assert isinstance(patch, dict)

    # assertion for patch attributes
    patch_attrib = ['summary',
                    'description',
                    'tags',
                    'parameters',
                    'requestBody',
                    'responses']
    for attrib in patch_attrib:
        assert attrib in patch

    # assertion for patch request attributes
    patch_req_attrib = ['required',
                        'content']
    patch_req = patch['requestBody']
    assert isinstance(patch_req, dict)
    for attrib in patch_req_attrib:
        assert attrib in patch_req

    # assertion for patch request content attributes
    patch_req_content_attrib = ['add',
                                'modify',
                                'remove']
    patch_req_content = patch_req['content']['application/json']
    assert isinstance(patch_req_content, dict)
    patch_req_content_schema = patch_req_content['schema']
    assert isinstance(patch_req_content_schema, dict)
    for attrib in patch_req_content_attrib:
        assert attrib in patch_req_content_schema['properties']

    # assertion for patch response attributes
    patch_resp_attrib = ['200',
                         '400',
                         '404',
                         '500']
    patch_resp = patch['responses']
    assert isinstance(patch_resp, dict)
    for attrib in patch_resp_attrib:
        assert attrib in patch_resp


def put_schema_assertions(verbs):
    """
    Assertions for put schema in OpenAPI document
    :param verbs: verbs dict
    """
    # assertion for put
    assert 'put' in verbs
    put = verbs['put']
    assert isinstance(put, dict)

    # assertion for put attributes
    put_attrib = ['summary',
                  'description',
                  'tags',
                  'parameters',
                  'requestBody',
                  'responses']
    for attrib in put_attrib:
        assert attrib in put

    # assertion for put request attributes
    put_req_attrib = ['required',
                      'content']
    put_req = put['requestBody']
    assert isinstance(put_req, dict)
    for attrib in put_req_attrib:
        assert attrib in put_req

    # assertion for put request content attributes
    put_req_content_attrib = ['type',
                              'geometry',
                              'properties']
    put_req_content = put_req['content']['application/geo+json']
    assert isinstance(put_req_content, dict)
    put_req_content_schema = put_req_content['schema']
    assert isinstance(put_req_content_schema, dict)
    for attrib in put_req_content_attrib:
        assert attrib in put_req_content_schema['properties']

    # assertion for put response attributes
    put_resp_attrib = ['200',
                       '400',
                       '404',
                       '500']
    put_resp = put['responses']
    assert isinstance(put_resp, dict)
    for attrib in put_resp_attrib:
        assert attrib in put_resp


def delete_schema_assertions(verbs):
    """
    Assertions for delete schema in OpenAPI document

    :param verbs: verbs dict
    """
    # assertion for delete
    assert 'delete' in verbs
    delete = verbs['delete']
    assert isinstance(delete, dict)

    # assertion for delete attributes
    delete_attrib = ['summary',
                     'description',
                     'tags',
                     'parameters',
                     'responses']
    for attrib in delete_attrib:
        assert attrib in delete

    # assertion for delete response attributes
    delete_resp_attrib = ['200',
                          '400',
                          '404',
                          '500']
    delete_resp = delete['responses']
    assert isinstance(delete_resp, dict)
    for attrib in delete_resp_attrib:
        assert attrib in delete_resp


def check_transaction_schemas_present(coll_name, paths):
    """
    Assertions for precense of transaction schemas

    :param coll_name: collection name
    :param paths: paths dict
    """
    items_path_verbs = paths[items_path(coll_name)]
    post_schema_assertions(items_path_verbs)

    item_path_verbs = paths[item_path(coll_name)]
    patch_schema_assertions(item_path_verbs)
    put_schema_assertions(item_path_verbs)
    delete_schema_assertions(item_path_verbs)


def check_transaction_schemas_abscent(coll_name, paths):
    """
    Assertions for abcense of transaction schemas

    :param coll_name: collection name
    :param paths: paths dict
    """
    items_path_verbs = paths[items_path(coll_name)]
    assert 'post' not in items_path_verbs

    item_path_verbs = paths[item_path(coll_name)]
    assert 'patch' not in item_path_verbs
    assert 'put' not in item_path_verbs
    assert 'delete' not in item_path_verbs


def test_transaction_a_b(collections, paths):
    """
    Assertions for transaction schemas in OpenAPI document

    :param collections: collections dict
    :param paths: paths dict
    """
    for coll_name, coll_cont in collections.items():

        if supports_transactions(coll_cont):
            check_transaction_schemas_present(coll_name, paths)

        else:
            check_transaction_schemas_abscent(coll_name, paths)
