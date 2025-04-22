# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Bernhard Mallinger <bernhard.mallinger@eox.at>
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


from http import HTTPStatus

from pygeoapi.api.maps import get_collection_map

from tests.util import mock_api_request


def test_get_collection_map(config, api_):
    req = mock_api_request()
    rsp_headers, code, response = get_collection_map(api_, req, 'notfound')
    assert code == HTTPStatus.NOT_FOUND

    req = mock_api_request()
    rsp_headers, code, response = get_collection_map(
        api_, req, 'mapserver_world_map')
    assert code == HTTPStatus.OK
    assert isinstance(response, bytes)
    assert response[1:4] == b'PNG'

def test_map_crs_transform(config, api_):
    
    # Florida in EPSG:4326
    params = {
        'bbox': '-88.374023,24.826625,-78.112793,31.015279',
        # crs is 4326 by implicit since it is the default
    }
    req = mock_api_request(params)
    _, code, floridaIn4326 = get_collection_map(
        api_, req, 'mapserver_world_map')
    assert code == HTTPStatus.OK

    # Area that isn't florida in the ocean; used to make sure 
    # the same coords with different crs are not the same
    params = {
        'bbox': '-88.374023,24.826625,-78.112793,31.015279',
        'bbox-crs': 'http://www.opengis.net/def/crs/EPSG/0/3857',
    }

    req = mock_api_request(params)
    _, code, florida4326InWrongCRS = get_collection_map(
        api_, req, 'mapserver_world_map')
    assert code == HTTPStatus.OK

    assert florida4326InWrongCRS != floridaIn4326 

    # Florida again, but this time in EPSG:3857
    params = {
        'bbox': '-9837751.2884,2854464.3843,-8695476.3377,3634733.5690',
        'bbox-crs': 'http://www.opengis.net/def/crs/EPSG/0/3857'
    }
    req = mock_api_request(params)
    _, code, floridaProjectedIn3857 = get_collection_map(
        api_, req, 'mapserver_world_map')
    assert code == HTTPStatus.OK


    assert floridaIn4326 == floridaProjectedIn3857
