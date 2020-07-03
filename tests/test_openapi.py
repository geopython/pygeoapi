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
    """helper function to open test file safely"""
    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-config-local-openapi.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def get_oas_30_(config):
    return get_oas_30(config)


@pytest.fixture()
def components(get_oas_30_):
    return get_oas_30_['components']


@pytest.fixture()
def schemas(components):
    return components['schemas']


@pytest.fixture()
def paths(get_oas_30_):
    return get_oas_30_['paths']


@pytest.fixture()
def collections(config):
    return filter_dict_by_key_value(config['resources'],
                                    'type',
                                    'collection')


def items_path(collName):
    return '/collections/{}/items'.format(collName)


def item_path(collName):
    return '/collections/{}/items/{{featureId}}'.format(collName)


def supports_transactions(collection):
    if 'transactions' not in collection['extents']:
        return False
    return collection['extents']['transactions']


def test_nameValuePairObj(schemas):
    assert 'nameValuePairObj' in schemas
    assert 'name' in schemas['nameValuePairObj']['properties']
    assert 'value' in schemas['nameValuePairObj']['properties']


def post_schema_assertions(verbs):
    """assertions for post in openapidoc"""
    # assertion for post
    assert 'post' in verbs
    post = verbs['post']
    assert isinstance(post, dict)

    # assertion for post attributes
    postAttrib = ['summary',
                  'description',
                  'tags',
                  'requestBody',
                  'responses']
    for attrib in postAttrib:
        assert attrib in post

    # assertion for post request attributes
    postReqAttrib = ['required',
                     'content']
    postReq = post['requestBody']
    assert isinstance(postReq, dict)
    for attrib in postReqAttrib:
        assert attrib in postReq

    # assertion for post request content attributes
    postReqContentAttrib = ['type',
                            'geometry',
                            'properties']
    postReqContent = postReq['content']['application/geo+json']
    assert isinstance(postReqContent, dict)
    postReqContentSchema = postReqContent['schema']
    assert isinstance(postReqContentSchema, dict)
    for attrib in postReqContentAttrib:
        assert attrib in postReqContentSchema['properties']

    # assertion for post response attributes
    postRespAttrib = [201,
                      400,
                      404,
                      500]
    postResp = post['responses']
    for attrib in postRespAttrib:
        assert attrib in postResp


def patch_schema_assertions(verbs):
    """assertions for patch in openapidoc"""
    # assertion for patch
    assert 'patch' in verbs
    patch = verbs['patch']
    assert isinstance(patch, dict)

    # assertion for patch attributes
    patchAttrib = ['summary',
                   'description',
                   'tags',
                   'parameters',
                   'requestBody',
                   'responses']
    for attrib in patchAttrib:
        assert attrib in patch

    # assertion for patch request attributes
    patchReqAttrib = ['required',
                      'content']
    patchReq = patch['requestBody']
    assert isinstance(patchReq, dict)
    for attrib in patchReqAttrib:
        assert attrib in patchReq

    # assertion for patch request content attributes
    patchReqContentAttrib = ['add',
                             'modify',
                             'remove']
    patchReqContent = patchReq['content']['application/json']
    assert isinstance(patchReqContent, dict)
    patchReqContentSchema = patchReqContent['schema']
    assert isinstance(patchReqContentSchema, dict)
    for attrib in patchReqContentAttrib:
        assert attrib in patchReqContentSchema['properties']

    # assertion for patch response attributes
    patchRespAttrib = [200,
                       400,
                       404,
                       500]
    patchResp = patch['responses']
    assert isinstance(patchResp, dict)
    for attrib in patchRespAttrib:
        assert attrib in patchResp


def put_schema_assertions(verbs):
    """assertions for put in openapidoc"""
    # assertion for put
    assert 'put' in verbs
    put = verbs['put']
    assert isinstance(put, dict)

    # assertion for put attributes
    putAttrib = ['summary',
                 'description',
                 'tags',
                 'parameters',
                 'requestBody',
                 'responses']
    for attrib in putAttrib:
        assert attrib in put

    # assertion for put request attributes
    putReqAttrib = ['required',
                    'content']
    putReq = put['requestBody']
    assert isinstance(putReq, dict)
    for attrib in putReqAttrib:
        assert attrib in putReq

    # assertion for put request content attributes
    putReqContentAttrib = ['type',
                           'geometry',
                           'properties']
    putReqContent = putReq['content']['application/geo+json']
    assert isinstance(putReqContent, dict)
    putReqContentSchema = putReqContent['schema']
    assert isinstance(putReqContentSchema, dict)
    for attrib in putReqContentAttrib:
        assert attrib in putReqContentSchema['properties']

    # assertion for put response attributes
    putRespAttrib = [200,
                     400,
                     404,
                     500]
    putResp = put['responses']
    assert isinstance(putResp, dict)
    for attrib in putRespAttrib:
        assert attrib in putResp


def delete_schema_assertions(verbs):
    """assertions for delete in openapidoc"""

    # assertion for delete
    assert 'delete' in verbs
    delete = verbs['delete']
    assert isinstance(delete, dict)

    # assertion for delete attributes
    deleteAttrib = ['summary',
                    'description',
                    'tags',
                    'parameters',
                    'responses']
    for attrib in deleteAttrib:
        assert attrib in delete

    # assertion for delete response attributes
    deleteRespAttrib = [200,
                        400,
                        404,
                        500]
    deleteResp = delete['responses']
    assert isinstance(deleteResp, dict)
    for attrib in deleteRespAttrib:
        assert attrib in deleteResp


def check_transaction_schemas_present(collName, paths):
    itemsPathVerbs = paths[items_path(collName)]
    post_schema_assertions(itemsPathVerbs)

    itemPathVerbs = paths[item_path(collName)]
    patch_schema_assertions(itemPathVerbs)
    put_schema_assertions(itemPathVerbs)
    delete_schema_assertions(itemPathVerbs)


def check_transaction_schemas_abscent(collName, paths):
    itemsPathVerbs = paths[items_path(collName)]
    assert 'post' not in itemsPathVerbs

    itemPathVerbs = paths[item_path(collName)]
    assert 'patch' not in itemPathVerbs
    assert 'put' not in itemPathVerbs
    assert 'delete' not in itemPathVerbs


def test_transaction_a_b(collections, paths):
    for collName, collCont in collections.items():

        if supports_transactions(collCont):
            check_transaction_schemas_present(collName, paths)

        else:
            check_transaction_schemas_abscent(collName, paths)
