# =================================================================
#
# Authors: Andreas Kosubek <andreas.kosubek@ama.gv.at>
#
# Copyright (c) 2023 Andreas Kosubek
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

# Needs to be run like: python3 -m pytest
# Create testdata: SQLPLUS SYS@DBNAME AS SYSDBA @./data/oracle_lakes.sql

import os
import json
import pytest
from http import HTTPStatus

from pygeoapi.api import API

from pygeoapi.provider.base import (
    ProviderConnectionError,
    ProviderItemNotFoundError,
    ProviderQueryError
)
from pygeoapi.provider.oracle import OracleProvider

USERNAME = os.environ.get('PYGEOAPI_ORACLE_USER', 'geo_test')
PASSWORD = os.environ.get('PYGEOAPI_ORACLE_PASSWD', 'geo_test')
SERVICE_NAME=os.environ.get('PYGEOAPI_ORACLE_SERVICE_NAME', 'XEPDB1')
HOST = os.environ.get('PYGEOAPI_ORACLE_HOST', '127.0.0.1')
PORT = os.environ.get('PYGEOAPI_ORACLE_PORT', '1521')

@pytest.fixture()
def config():
    return {
        'name': 'Oracle',
        'type': 'feature',
        'data': {'host': HOST,
                 'port': PORT,
                 'service_name': SERVICE_NAME,
                 'user': USERNAME,
                 'password': PASSWORD
                 },
        'id_field': 'id',
        'table': 'lakes',
        'geom_field': 'geometry'
    }


def test_query(config):
    """Testing query for a valid JSON object with geometry"""
    p = OracleProvider(config)
    feature_collection = p.query()
    assert feature_collection.get('type') == 'FeatureCollection'
    features = feature_collection.get('features')
    assert features is not None
    feature = features[0]
    properties = feature.get('properties')
    assert properties is not None
    geometry = feature.get('geometry')
    assert geometry is not None