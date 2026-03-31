# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2025 Tom Kralidis
# Copyright (c) 2025 Francesco Bartoli
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

from unittest import mock
import pytest

from pygeoapi.provider.base import ProviderItemNotFoundError
from pygeoapi.provider.csw_facade import CSWFacadeProvider

CSW_PROVIDER = 'pygeoapi.provider.csw_facade.CatalogueServiceWeb'


@pytest.fixture()
def config():
    return {
        'name': 'CSWFacade',
        'type': 'record',
        'data': 'https://demo.pycsw.org/cite/csw',
        'id_field': 'identifier',
        'time_field': 'date'
    }


@pytest.fixture()
def mock_csw_record():
    """Mock owslib CSW record"""
    record = mock.MagicMock()
    record.identifier = 'urn:uuid:19887a8a-f6b0-4a63-ae56-7fba0e17801f'
    record.title = 'Lorem ipsum'
    record.abstract = 'Lorem ipsum dolor sit amet'
    record.type = 'http://purl.org/dc/dcmitype/Image'
    record.subjects = ['Tourism--Greece']
    record.date = '2006-03-26'
    record.created = None
    record.modified = None
    record.rights = None
    record.language = None
    record.bbox = None  # No geometry for first record
    record.references = []
    record.uris = []
    return record


@pytest.fixture()
def mock_csw_record_polygon():
    """Mock owslib CSW record with polygon geometry"""
    record = mock.MagicMock()
    record.identifier = 'urn:uuid:1ef30a8b-876d-4828-9246-c37ab4510bbd'
    record.title = 'Maecenas enim'
    record.abstract = 'Maecenas enim'
    record.type = 'http://purl.org/dc/dcmitype/Text'
    record.subjects = []
    record.date = '2006-05-12'
    record.created = None
    record.modified = None
    record.rights = None
    record.language = None
    record.bbox = mock.MagicMock()
    record.bbox.minx = '13.754'
    record.bbox.miny = '60.042'
    record.bbox.maxx = '15.334'
    record.bbox.maxy = '61.645'
    record.references = []
    record.uris = []
    return record


@pytest.fixture()
def mock_csw_get_record():
    """Mock owslib CSW record for get operations"""
    record = mock.MagicMock()
    record.identifier = 'urn:uuid:a06af396-3105-442d-8b40-22b57a90d2f2'
    record.title = 'Lorem ipsum dolor sit amet'
    record.abstract = 'Lorem ipsum dolor sit amet'
    record.type = 'http://purl.org/dc/dcmitype/Image'
    record.subjects = []
    record.date = None
    record.created = None
    record.modified = None
    record.rights = None
    record.language = None
    record.bbox = None
    record.references = []
    record.uris = []
    return record


@pytest.fixture()
def mock_csw(mock_csw_record, mock_csw_record_polygon, mock_csw_get_record):
    """Mock CSW service"""
    with mock.patch(CSW_PROVIDER) as mock_csw_class:
        csw_instance = mock.MagicMock()
        mock_csw_class.return_value = csw_instance

        def mock_getrecords2(*args, **kwargs):
            # Simulate different responses based on parameters
            limit = kwargs.get('maxrecords', 10)
            offset = kwargs.get('startposition', 0)
            constraints = kwargs.get('constraints', [])

            # All available records
            all_records = [
                (
                    'urn:uuid:19887a8a-f6b0-4a63-ae56-7fba0e17801f',
                    mock_csw_record
                ),
                (
                    'urn:uuid:1ef30a8b-876d-4828-9246-c37ab4510bbd',
                    mock_csw_record_polygon
                )
            ]

            # Simulate filtering based on query constraints
            filtered_records = all_records[:]

            # Simulate different total counts based on constraints
            total_matches = 12  # Default total
            if constraints:
                # If there are constraints
                # simulate fewer matches
                constraint_str = str(constraints)
                if 'lorem' in constraint_str.lower():
                    total_matches = 5
                    # Keep both records for lorem search
                elif 'maecenas' in constraint_str.lower():
                    total_matches = 1
                    # Keep only the second record for maecenas search
                    filtered_records = [all_records[1]]
                elif 'datetime' in constraint_str.lower():
                    total_matches = 1 if '2006-05-12' in constraint_str else 3
                    # Keep appropriate records based on date
                    if '2006-05-12' in constraint_str:
                        # Second record has matching date
                        filtered_records = [all_records[1]]

            # Apply offset and limit to filtered records
            paginated_records = filtered_records[offset:offset+limit]

            # Convert to dictionary format expected by CSW
            csw_instance.records = {
                record_id: record for record_id, record in paginated_records
            }
            csw_instance.results = {
                'matches': total_matches,
                'returned': len(paginated_records)
            }

        def mock_getrecordbyid(identifiers, **kwargs):
            identifier = identifiers[0]
            if identifier == 'urn:uuid:a06af396-3105-442d-8b40-22b57a90d2f2':
                csw_instance.records = {identifier: mock_csw_get_record}
            else:
                csw_instance.records = {}

        def mock_getdomain(property_name, **kwargs):
            # Mock domain values for testing
            domain_values = {
                'type': [
                    'http://purl.org/dc/dcmitype/Image',
                    'http://purl.org/dc/dcmitype/Text',
                    'http://purl.org/dc/dcmitype/Dataset',
                    'http://purl.org/dc/dcmitype/Service'
                ]
            }
            csw_instance.results = {
                'values': domain_values.get(property_name, [])
            }

        csw_instance.getrecords2.side_effect = mock_getrecords2
        csw_instance.getrecordbyid.side_effect = mock_getrecordbyid
        csw_instance.getdomain.side_effect = mock_getdomain

        yield csw_instance


def test_domains(config, mock_csw):
    p = CSWFacadeProvider(config)

    domains, current = p.get_domains()

    assert current

    expected_properties = ['date', 'description', 'keywords', 'title', 'type']

    assert sorted(domains.keys()) == expected_properties

    assert len(domains['type']) == 4

    domains, current = p.get_domains(['type'])

    assert current

    assert list(domains.keys()) == ['type']


def test_query(config, mock_csw):
    p = CSWFacadeProvider(config)

    fields = p.get_fields()
    assert len(fields) == 9

    for key, value in fields.items():
        assert value['type'] == 'string'

    results = p.query()
    assert len(results['features']) == 2  # Mock returns 2 records
    assert results['numberMatched'] == 12
    assert results['numberReturned'] == 2
    assert results['features'][0]['id'] == 'urn:uuid:19887a8a-f6b0-4a63-ae56-7fba0e17801f'  # noqa
    assert results['features'][0]['geometry'] is None
    assert results['features'][0]['properties']['title'] == 'Lorem ipsum'
    assert results['features'][0]['properties']['keywords'][0] == 'Tourism--Greece'  # noqa

    assert results['features'][1]['geometry']['type'] == 'Polygon'
    assert results['features'][1]['geometry']['coordinates'][0][0][0] == 13.754
    assert results['features'][1]['geometry']['coordinates'][0][0][1] == 60.042

    results = p.query(limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == 'urn:uuid:19887a8a-f6b0-4a63-ae56-7fba0e17801f'  # noqa

    results = p.query(offset=1, limit=1)
    assert len(results['features']) == 1
    assert results['features'][0]['id'] == 'urn:uuid:1ef30a8b-876d-4828-9246-c37ab4510bbd' # noqa

    results = p.query(resulttype='hits')
    assert results['numberMatched'] == 12

    results = p.query(bbox=[-10, 40, 0, 60])
    assert len(results['features']) == 2

    results = p.query(bbox=[-10, 40, 0, 60, 0, 0])
    assert len(results['features']) == 2

    results = p.query(properties=[('title', 'Maecenas enim')])
    assert len(results['features']) == 2


def test_get(config, mock_csw):
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


def test_get_not_existing_item_raise_exception(config, mock_csw):
    """Testing query for a not existing object"""
    p = CSWFacadeProvider(config)
    with pytest.raises(ProviderItemNotFoundError):
        p.get('404')
