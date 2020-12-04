# =================================================================
#
# Author: Luís Moreira de Sousa <luis.de.sousa@protonmail.ch>
#
# Copyright (c) 2019 Luís Moreira de Sousa
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

import pytest

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.geosparql import GeoSPARQLProvider


@pytest.fixture()
def config():
    return {
        'name': 'GeoSPARQL',
        'type': 'feature',
        'data': 'http://localhost:8890/sparql',
        'id_prefix': 'http://www.example.org/POI#'
    }


def test_get(config):
    """Testing query for a specific GeoSPARQL feature with geometry"""

    rdf_label = "http://www.w3.org/2000/01/rdf-schema#label"
    p = GeoSPARQLProvider(config)
    result = p.get("http://www.example.org/POI#WashingtonMonument")
    assert isinstance(result, dict)
    assert 'geometry' in result
    assert 'properties' in result
    assert 'Washington Monument' in result['properties'][0][rdf_label][0]['@value']



