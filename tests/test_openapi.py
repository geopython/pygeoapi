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
from pygeoapi.util import yaml_load
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
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def get_oas_30_(config):
    return get_oas_30(config)

def test_simple_transactions(get_oas_30_):
    """assertions for simple transactions schemas in openapidoc"""

    assert isinstance(get_oas_30_, dict)

    ############################ components ################################################################

    #assertion for nameValuePairObj schema
    assert 'nameValuePairObj' in get_oas_30_['components']['schemas']
    assert 'name' in get_oas_30_['components']['schemas']['nameValuePairObj']['properties']
    assert 'value' in get_oas_30_['components']['schemas']['nameValuePairObj']['properties']

    ############################### post ###################################################################

    #assertion for post
    assert 'post' in get_oas_30_['paths']['/collections/obs/items']
    assert isinstance(get_oas_30_['paths']['/collections/obs/items']['post'], dict)

    #assertion for post attributes
    postAttrib = ['summary', 'description', 'tags', 'requestBody', 'responses']
    for attrib in postAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items']['post']

    #assertion for post request attributes
    postReqAttrib = ['required', 'content']
    for attrib in postReqAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items']['post']['requestBody']

    #assertion for post request content attributes
    postReqContentAttrib = ['type', 'geometry', 'properties']
    for attrib in postReqContentAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items']['post']['requestBody']['content']['application/geo+json']['schema']['properties']     

    #assertion for post response attributes
    postRespAttrib = [201, 400, 404, 500]
    for attrib in postRespAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items']['post']['responses']

    ############################### patch ##################################################################

    #assertion for patch
    assert 'patch' in get_oas_30_['paths']['/collections/obs/items/{featureId}']
    assert isinstance(get_oas_30_['paths']['/collections/obs/items/{featureId}']['patch'], dict)

    #assertion for patch attributes
    patchAttrib = ['summary', 'description', 'tags', 'parameters', 'requestBody', 'responses']
    for attrib in patchAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items/{featureId}']['patch']

    #assertion for patch request attributes
    patchReqAttrib = ['required', 'content']
    for attrib in patchReqAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items/{featureId}']['patch']['requestBody']

    #assertion for patch request content attributes
    patchReqContentAttrib = ['add', 'modify', 'remove']
    for attrib in patchReqContentAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items/{featureId}']['patch']['requestBody']['content']['application/json']['schema']['properties']       

    #assertion for patch response attributes
    patchRespAttrib = [200, 400, 404, 500]
    for attrib in patchRespAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items/{featureId}']['patch']['responses']

    ############################### put ###################################################################

    #assertion for put
    assert 'put' in get_oas_30_['paths']['/collections/obs/items/{featureId}']
    assert isinstance(get_oas_30_['paths']['/collections/obs/items/{featureId}']['put'], dict)

    #assertion for put attributes
    putAttrib = ['summary', 'description', 'tags', 'parameters', 'requestBody', 'responses']
    for attrib in putAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items/{featureId}']['put']

    #assertion for put request attributes
    putReqAttrib = ['required', 'content']
    for attrib in putReqAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items/{featureId}']['put']['requestBody']

    #assertion for put request content attributes
    putReqContentAttrib = ['type', 'geometry', 'properties']
    for attrib in putReqContentAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items/{featureId}']['put']['requestBody']['content']['application/geo+json']['schema']['properties']      

    #assertion for put response attributes
    putRespAttrib = [200, 400, 404, 500]
    for attrib in putRespAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items/{featureId}']['put']['responses']

    ############################### delete ################################################################

    #assertion for delete
    assert 'delete' in get_oas_30_['paths']['/collections/obs/items/{featureId}']
    assert isinstance(get_oas_30_['paths']['/collections/obs/items/{featureId}']['delete'], dict)

    #assertion for delete attributes
    deleteAttrib = ['summary', 'description', 'tags', 'parameters', 'responses']
    for attrib in deleteAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items/{featureId}']['delete']  

    #assertion for delete response attributes
    deleteRespAttrib = [200, 400, 404, 500]
    for attrib in deleteRespAttrib:
        assert attrib in get_oas_30_['paths']['/collections/obs/items/{featureId}']['delete']['responses']