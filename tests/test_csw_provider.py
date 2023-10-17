# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2023 Tom Kralidis
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

import pytest

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.csw_facade import CSWFacadeProvider


@pytest.fixture()
def config():
    return {
        'name': 'CSWFacade',
        'type': 'record',
        # 'data': 'https://demo.pycsw.org/cite/csw',
        'data': 'http://localhost:8000',
        'id_field': 'identifier',
        'time_field': 'date'
    }


def test_query(config):
    p = CSWFacadeProvider(config)

    fields = p.get_fields()
    assert len(fields) == 9

    for key, value in fields.items():
        assert value['type'] == 'string'

    results = p.query()
    assert len(results['features']) == 10
    assert results['numberMatched'] == 12
    assert results['numberReturned'] == 10
    assert results['features'][0]['id'] == 'urn:uuid:19887a8a-f6b0-4a63-ae56-7fba0e17801f'  # noqa
    assert results['features'][0]['geometry'] is None
    assert results['features'][0]['properties']['title'] == 'Lorem ipsum'
    assert results['features'][0]['properties']['keywords'][0] == 'Tourism--Greece'  # noqa

    assert results['features'][1]['geometry']['type'] == 'Polygon'
    assert results['features'][1]['geometry']['coordinates'][0][0][0] == 17.92
    assert results['features'][1]['geometry']['coordinates'][0][0][1] == 60.042

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == 'urn:uuid:19887a8a-f6b0-4a63-ae56-7fba0e17801f'  # noqa

    results = p.query(offset=2, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == 'urn:uuid:1ef30a8b-876d-4828-9246-c37ab4510bbd' # noqa

    assert len(results['features'][0]['properties']) == 2

    results = p.query(q='lorem')
    assert results['numberMatched'] == 5

    results = p.query(q='lorem', sortby=[{'property': 'title', 'order': '-'}])
    assert results['numberMatched'] == 5

    results = p.query(resulttype='hits')
    assert len(results['features']) == 0
    assert results['numberMatched'] == 12

    results = p.query(bbox=[-10, 40, 0, 60])
    assert len(results['features']) == 2

    results = p.query(properties=[('title', 'Maecenas enim')])
    assert len(results['features']) == 1

    properties = [
        ('title', 'Maecenas enim'),
        ('type', 'http://purl.org/dc/dcmitype/Text')
    ]
    results = p.query(properties=properties)
    assert len(results['features']) == 1

    results = p.query(datetime_='2006-05-12')
    assert len(results['features']) == 1

    results = p.query(datetime_='2004/2007')
    assert len(results['features']) == 3


def test_get(config):
    p = CSWFacadeProvider(config)

    result = p.get('urn:uuid:a06af396-3105-442d-8b40-22b57a90d2f2')
    assert result['id'] == 'urn:uuid:a06af396-3105-442d-8b40-22b57a90d2f2'
    assert result['geometry'] is None
    assert result['properties']['title'] == 'Lorem ipsum dolor sit amet'
    assert result['properties']['type'] == 'http://purl.org/dc/dcmitype/Image'

    xml_link = result['links'][0]
    assert xml_link['rel'] == 'alternate'
    assert xml_link['type'] == 'application/xml'
    assert 'service=CSW' in xml_link['href']


def test_get_not_existing_item_raise_exception(config):
    """Testing query for a not existing object"""
    p = CSWFacadeProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get('404')
