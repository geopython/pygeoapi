# =================================================================
#
# Authors: Ben Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2025 Ben Webb
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

from pygeoapi.provider.sensorthings_edr import SensorThingsEDRProvider


@pytest.fixture()
def config():
    return {
        'name': 'SensorThingsEDRProvider',
        'type': 'edr',
        'data': 'http://localhost:8888/FROST-Server/v1.1'
    }


def test_get_fields(config):
    p = SensorThingsEDRProvider(config)
    fields = p.get_fields()

    # Ensure fields is a dictionary
    assert isinstance(fields, dict)

    # Ensure the expected keys are present in the dictionary
    assert '1' in fields
    assert '2' in fields
    assert '3' in fields

    # Validate field types, titles, and units for each field
    assert fields['1']['type'] == 'number'
    assert fields['1']['title'] == 'Water Level Below Ground Surface'
    assert fields['1']['x-ogc-unit'] == 'ft'

    assert fields['3']['type'] == 'number'
    assert fields['3']['title'] == 'Temperature'
    assert fields['3']['x-ogc-unit'] == 'C'


def test_locations(config):
    p = SensorThingsEDRProvider(config)
    locations = p.locations()

    assert locations['type'] == 'FeatureCollection'
    assert len(locations['features']) == 89

    locations = p.locations(select_properties=[3])
    assert len(locations['features']) == 1

    locations = p.locations(select_properties=[1])
    assert len(locations['features']) == 44

    locations = p.locations(select_properties=[1, 2])
    assert len(locations['features']) == 88


def test_get_location(config):
    p = SensorThingsEDRProvider(config)
    response = p.locations(location_id=1)

    # Ensure response is a dictionary
    assert isinstance(response, dict)

    # Check top-level keys
    assert 'type' in response
    assert 'domainType' in response
    assert 'parameters' in response
    assert 'coverages' in response

    # Validate 'type' and 'domainType'
    assert response['type'] == 'CoverageCollection'
    assert response['domainType'] == 'PointSeries'

    # Validate 'parameters'
    parameters = response['parameters']
    assert 'Water+Level+Below+Ground+Surface' in parameters
    assert 'Water+Level+relative+to+datum' in parameters

    # Check parameter structure
    wl_below_ground = parameters['Water+Level+Below+Ground+Surface']
    assert wl_below_ground['type'] == 'Parameter'
    assert (
        wl_below_ground['description']['en']
        == 'Estimated depth to water table below ground surface'
    )
    assert wl_below_ground['unit']['symbol'] == 'ft'

    # Validate 'coverages'
    coverages = response['coverages']
    assert isinstance(coverages, list)
    assert len(coverages) == 2  # Ensure there are 2 coverages

    # Validate each coverage
    for coverage in coverages:
        # Check coverage type and id
        assert coverage['type'] == 'Coverage'
        assert coverage['id'] == '1'

        # Validate domain structure
        domain = coverage['domain']
        assert domain['type'] == 'Domain'
        assert domain['domainType'] == 'PointSeries'
        assert 'axes' in domain

        axes = domain['axes']
        assert 'x' in axes
        assert 'y' in axes
        assert 't' in axes

        # Validate geographic coordinates
        assert axes['x']['values'] == [-108.7483]
        assert axes['y']['values'] == [35.6711]

        # Validate temporal values
        assert len(axes['t']['values']) == 17

        # Validate 'ranges'
        ranges = coverage['ranges']
        assert (
            'Water+Level+Below+Ground+Surface' in ranges
            or 'Water+Level+relative+to+datum' in ranges
        )

        # Validate range data
        if 'Water+Level+Below+Ground+Surface' in ranges:
            wl_range = ranges['Water+Level+Below+Ground+Surface']
            assert wl_range['type'] == 'NdArray'
            assert wl_range['dataType'] == 'float'
            assert len(wl_range['values']) == 17


def test_get_cube(config):
    p = SensorThingsEDRProvider(config)
    response = p.cube(bbox=[-84, 32, -73, 38])

    # Ensure response is a dictionary
    assert isinstance(response, dict)

    # Check top-level keys
    assert 'type' in response
    assert 'domainType' in response
    assert 'parameters' in response
    assert 'coverages' in response

    # Validate 'type' and 'domainType'
    assert response['type'] == 'CoverageCollection'
    assert response['domainType'] == 'PointSeries'

    # Validate 'parameters'
    parameters = response['parameters']
    assert 'Temperature' in parameters

    # Check parameter structure
    temperature_param = parameters['Temperature']
    assert temperature_param['type'] == 'Parameter'
    assert temperature_param['description']['en'] == 'Temperature measurement'
    assert temperature_param['observedProperty']['id'] == 'Temperature'
    assert temperature_param['unit']['symbol'] == 'C'

    # Validate 'coverages'
    coverages = response['coverages']
    assert isinstance(coverages, list)
    assert len(coverages) == 1  # Ensure there is 1 coverage

    # Validate coverage structure
    coverage = coverages[0]
    assert 'type' in coverage
    assert 'id' in coverage
    assert 'domain' in coverage
    assert 'ranges' in coverage

    # Check coverage type and id
    assert coverage['type'] == 'Coverage'
    assert coverage['id'] == '60'

    # Validate domain structure
    domain = coverage['domain']
    assert domain['type'] == 'Domain'
    assert domain['domainType'] == 'PointSeries'
    assert 'axes' in domain

    axes = domain['axes']
    assert 'x' in axes
    assert 'y' in axes
    assert 't' in axes

    # Validate geographic coordinates
    assert axes['x']['values'] == [-78.9307]
    assert axes['y']['values'] == [35.9997]

    # Validate temporal values
    assert len(axes['t']['values']) == 100

    # Validate 'referencing'
    referencing = domain['referencing']
    assert len(referencing) == 2
    assert referencing[0]['coordinates'] == ['x', 'y']
    assert referencing[0]['system']['type'] == 'GeographicCRS'
    assert referencing[1]['coordinates'] == ['t']
    assert referencing[1]['system']['type'] == 'TemporalRS'

    # Validate 'ranges'
    ranges = coverage['ranges']
    assert 'Temperature' in ranges

    # Check range data
    temperature_range = ranges['Temperature']
    assert temperature_range['type'] == 'NdArray'
    assert temperature_range['dataType'] == 'float'
    assert temperature_range['axisNames'] == ['t']
    assert temperature_range['shape'] == [100]
    assert len(temperature_range['values']) == 100

    assert temperature_range['values'][0] == 0.1696
    assert temperature_range['values'][-1] == 200


def test_get_cube_time_filter(config):
    p = SensorThingsEDRProvider(config)

    # Define the time range for filtering
    time_start = '2021-01-31T14:57:00Z'
    time_end = '2021-01-31T17:00:00Z'
    datetime_ = f'{time_start}/{time_end}'

    # Call the cube method with the time filter
    response = p.cube(bbox=[-84, 32, -73, 38], datetime_=datetime_)

    # Ensure response is a dictionary
    assert isinstance(response, dict)

    # Check top-level keys
    assert 'type' in response
    assert 'domainType' in response
    assert 'parameters' in response
    assert 'coverages' in response

    # Validate 'type' and 'domainType'
    assert response['type'] == 'CoverageCollection'
    assert response['domainType'] == 'PointSeries'

    # Validate 'parameters'
    parameters = response['parameters']
    assert 'Temperature' in parameters

    # Check parameter structure
    temperature_param = parameters['Temperature']
    assert temperature_param['type'] == 'Parameter'
    assert temperature_param['description']['en'] == 'Temperature measurement'
    assert temperature_param['observedProperty']['id'] == 'Temperature'
    assert temperature_param['unit']['symbol'] == 'C'

    # Validate 'coverages'
    coverages = response['coverages']
    assert isinstance(coverages, list)

    # Check that the coverage entries are filtered by the specified time range
    coverage = coverages[0]
    assert 'type' in coverage
    assert 'id' in coverage
    assert 'domain' in coverage
    assert 'ranges' in coverage

    # Validate coverage type and id
    assert coverage['type'] == 'Coverage'
    assert coverage['id'] == '60'

    # Validate domain structure
    domain = coverage['domain']
    assert domain['type'] == 'Domain'
    assert domain['domainType'] == 'PointSeries'
    assert 'axes' in domain

    axes = domain['axes']
    assert 'x' in axes
    assert 'y' in axes
    assert 't' in axes

    # Validate geographic coordinates
    assert axes['x']['values'] == [-78.9307]
    assert axes['y']['values'] == [35.9997]

    # Validate filtered temporal values
    temporal_values = axes['t']['values']
    assert len(temporal_values) > 0
    for time in temporal_values:
        assert time >= time_start
        assert time <= time_end

    # Validate 'referencing'
    referencing = domain['referencing']
    assert len(referencing) == 2
    assert referencing[0]['coordinates'] == ['x', 'y']
    assert referencing[0]['system']['type'] == 'GeographicCRS'
    assert referencing[1]['coordinates'] == ['t']
    assert referencing[1]['system']['type'] == 'TemporalRS'

    # Validate 'ranges'
    ranges = coverage['ranges']
    assert 'Temperature' in ranges

    # Check range data
    temperature_range = ranges['Temperature']
    assert temperature_range['type'] == 'NdArray'
    assert temperature_range['dataType'] == 'float'
    assert temperature_range['axisNames'] == ['t']
    assert len(temperature_range['values']) > 0

    assert temperature_range['values'][0] == 0.1696
    assert temperature_range['values'][-1] == 0.623


def test_get_area(config):
    p = SensorThingsEDRProvider(config)

    # Query the area with a sample WKT polygon
    response = p.area(wkt='POLYGON ((-108 34, -108 35, -107 35, -107 34, -108 34))')  # noqa

    # Check the overall type
    assert response.get('type') == 'CoverageCollection'

    # Check domain type
    assert response.get('domainType') == 'PointSeries'

    # Check parameters
    parameters = response.get('parameters')
    assert parameters is not None
    assert 'Water+Level+Below+Ground+Surface' in parameters
    wl_below_ground = parameters['Water+Level+Below+Ground+Surface']
    assert wl_below_ground['type'] == 'Parameter'
    assert (
        wl_below_ground['description']['en']
        == 'Estimated depth to water table below ground surface'
    )
    assert (
        wl_below_ground['observedProperty']['id']
        == 'Water Level Below Ground Surface'
    )
    assert (
        wl_below_ground['unit']['label']['en'] == 'feet'
    )

    assert 'Water+Level+relative+to+datum' in parameters
    wl_relative_datum = parameters['Water+Level+relative+to+datum']
    assert wl_relative_datum['type'] == 'Parameter'
    assert (
        wl_relative_datum['description']['en']
        == 'Measured water level relative to National Geodetic Vertical Datum of 1929' # noqa
    )
    assert (
        wl_relative_datum['observedProperty']['id']
        == 'Water Level relative to datum'
    )
    assert wl_relative_datum['unit']['label']['en'] == 'feet'

    # Check coverages
    coverages = response.get('coverages')
    assert coverages is not None
    assert len(coverages) == 10

    # Check Coverage 23
    coverage_23 = coverages[0]
    assert coverage_23.get('type') == 'Coverage'
    assert coverage_23.get('id') == '23'

    domain_23 = coverage_23.get('domain')
    assert domain_23.get('domainType') == 'PointSeries'

    axes_23 = domain_23.get('axes')
    assert axes_23['x']['values'] == [-107.979]
    assert axes_23['y']['values'] == [34.0582]
    assert len(axes_23['t']['values']) == 31

    ranges_23 = coverage_23.get('ranges')
    assert 'Water+Level+Below+Ground+Surface' in ranges_23
    assert ranges_23['Water+Level+Below+Ground+Surface']['type'] == 'NdArray'
    assert ranges_23['Water+Level+Below+Ground+Surface']['dataType'] == 'float'
    assert ranges_23['Water+Level+Below+Ground+Surface']['shape'] == [31]
