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

import logging

from pygeoapi.provider.base import ProviderNoDataError
from pygeoapi.provider.base_edr import BaseEDRProvider
from pygeoapi.provider.sensorthings import SensorThingsProvider

LOGGER = logging.getLogger(__name__)

GEOGRAPHIC_CRS = {
    'coordinates': ['x', 'y'],
    'system': {
        'type': 'GeographicCRS',
        'id': 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
    }
}

TEMPORAL_RS = {
    'coordinates': ['t'],
    'system': {'type': 'TemporalRS', 'calendar': 'Gregorian'}
}


class SensorThingsEDRProvider(BaseEDRProvider, SensorThingsProvider):
    def __init__(self, provider_def):
        """
        Initialize the SensorThingsEDRProvider instance.

        :param provider_def: provider definition
        """

        provider_def['entity'] = 'ObservedProperties'
        BaseEDRProvider.__init__(self, provider_def)
        SensorThingsProvider.__init__(self, provider_def)
        self.expand['ObservedProperties'] = (
            'Datastreams/Thing/Locations,Datastreams/Observations'
        )
        self.time_field = 'Datastreams/Observations/resultTime'
        self._fields = {}
        self.get_fields()

    def get_fields(self):
        """
        Retrieve and store ObservedProperties field definitions.

        :returns: A dictionary mapping field IDs to their properties.
        """

        if not self._fields:
            r = self._get_response(
                self._url, entity='ObservedProperties', expand='Datastreams'
            )
            try:
                _ = r['value'][0]
            except IndexError:
                LOGGER.warning('could not get fields; returning empty set')
                return {}

            for feature in r['value']:
                id = str(feature['@iot.id'])
                key = feature['name']
                try:
                    uom = feature['Datastreams'][0]['unitOfMeasurement']
                except IndexError:
                    continue

                self._fields[id] = {
                    'type': 'number',
                    'title': key,
                    'x-ogc-unit': uom['symbol']
                }

        return self._fields

    def items(self, **kwargs):
        """
        Retrieve a collection of items.

        :param kwargs: Additional parameters for the request.
        :returns: A GeoJSON representation of the items.
        """

        # This method is empty due to the way pygeoapi handles items requests
        # We implement this method inside of the feature provider
        pass

    def locations(
        self,
        select_properties: list = [],
        bbox: list = [],
        datetime_: str = None,
        location_id: str = None,
        **kwargs
    ):
        """
        Extract and return location data from ObservedProperties.

        :param select_properties: List of properties to include.
        :param bbox: Bounding box geometry for spatial queries.
        :param datetime_: Temporal filter for observations.
        :param location_id: Identifier of the location to filter by.

        :returns: A GeoJSON FeatureCollection of locations.
        """

        fc = {'type': 'FeatureCollection', 'features': []}

        params = {}
        expand = [
            'Datastreams($select=description,name,unitOfMeasurement)',
            'Datastreams/Thing($select=@iot.id)',
            'Datastreams/Thing/Locations($select=location)'
        ]

        if select_properties:
            properties = [
                ['@iot.id', f"'{p}'" if isinstance(p, str) else p]
                for p in select_properties
            ]
            ret = [f'{name} eq {value}' for (name, value) in properties]
            params['$filter'] = ' or '.join(ret)

        filter_ = f'$filter={self._make_dtf(datetime_)};' if datetime_ else ''
        if location_id:
            expand[0] = (
                f'Datastreams($filter=Thing/@iot.id eq {location_id};'
                '$select=description,name,unitOfMeasurement)'
            )
            expand.append(
                f'Datastreams/Observations({filter_}$orderby=phenomenonTime;'
                '$select=result,phenomenonTime,resultTime)'
            )
        else:
            expand.append(
                f'Datastreams/Observations({filter_}$select=result;$top=1)')

        if bbox:
            geom_filter = self._make_bbox(bbox, 'Datastreams')
            expand[0] = f'Datastreams($filter={geom_filter})'

        expand = ','.join(expand)
        response = self._get_response(
            url=self._url, params=params,
            entity='ObservedProperties', expand=expand
        )

        if location_id:
            return self._make_coverage_collection(response)

        for property in response['value']:
            for datastream in property['Datastreams']:
                if len(datastream['Observations']) == 0:
                    continue

                fc['features'].append(
                    self._make_feature(datastream['Thing'], entity='Things')
                )

        return fc

    def cube(
        self,
        select_properties: list = [],
        bbox: list = [],
        datetime_: str = None,
        **kwargs
    ):
        """
        Extract and return coverage data from ObservedProperties.

        :param select_properties: List of properties to include.
        :param bbox: Bounding box geometry for spatial queries.
        :param datetime_: Temporal filter for observations.

        :returns: A CovJSON CoverageCollection.
        """

        params = {}

        geom_filter = self._make_bbox(bbox, 'Datastreams')
        expand = [
            (
             f'Datastreams($filter={geom_filter};'
             '$select=description,name,unitOfMeasurement)'
            ),
            'Datastreams/Thing($select=@iot.id)',
            'Datastreams/Thing/Locations($select=location)'
        ]

        if select_properties:
            properties = [
                ['@iot.id', f"'{p}'" if isinstance(p, str) else p]
                for p in select_properties
            ]
            ret = [f'{name} eq {value}' for (name, value) in properties]
            params['$filter'] = ' or '.join(ret)

        filter_ = f'$filter={self._make_dtf(datetime_)};' if datetime_ else ''
        expand.append(
            f'Datastreams/Observations({filter_}$orderby=phenomenonTime;'
            '$select=result,phenomenonTime,resultTime)'
        )

        expand = ','.join(expand)
        response = self._get_response(
            url=self._url, params=params,
            entity='ObservedProperties', expand=expand
        )

        return self._make_coverage_collection(response)

    def area(
        self,
        wkt: str,
        select_properties: list = [],
        datetime_: str = None,
        **kwargs
    ):
        """
        Extract and return coverage data from a specified area.

        :param wkt: Well-Known Text (WKT) representation of the
                    geometry for the area.
        :param select_properties: List of properties to include
                                  in the response.
        :param datetime_: Temporal filter for observations.

        :returns: A CovJSON CoverageCollection.
        """

        params = {}

        expand = [
            (
             'Datastreams($filter=st_within('
             f"Thing/Locations/location,geography'{wkt}');"
             '$select=description,name,unitOfMeasurement)'
            ),
            'Datastreams/Thing($select=@iot.id)',
            'Datastreams/Thing/Locations($select=location)'
        ]

        if select_properties:
            properties = [
                ['@iot.id', f"'{p}'" if isinstance(p, str) else p]
                for p in select_properties
            ]
            ret = [f'{name} eq {value}' for (name, value) in properties]
            params['$filter'] = ' or '.join(ret)

        filter_ = f'$filter={self._make_dtf(datetime_)};' if datetime_ else ''
        expand.append(
            f'Datastreams/Observations({filter_}$orderby=phenomenonTime;'
            '$select=result,phenomenonTime,resultTime)'
        )

        expand = ','.join(expand)
        response = self._get_response(
            url=self._url, params=params,
            entity='ObservedProperties', expand=expand
        )

        return self._make_coverage_collection(response)

    def _generate_coverage(self, datastream: dict, id: str) -> dict:
        """
        Generate a coverage object for a datastream.

        :param datastream: The datastream data to generate coverage for.
        :param id: The ID to use for the coverage.

        :returns: A dict containing the coverage object.
        """

        times, values = self._expand_observations(datastream)
        thing = datastream['Thing']
        coords = thing['Locations'][0]['location']['coordinates']
        length = len(values)

        return {
            'type': 'Coverage',
            'id': str(thing['@iot.id']),
            'domain': {
                'type': 'Domain',
                'domainType': 'PointSeries',
                'axes': {
                    'x': {'values': [coords[0]]},
                    'y': {'values': [coords[1]]},
                    't': {'values': times}
                },
                'referencing': [GEOGRAPHIC_CRS, TEMPORAL_RS]
            },
            'ranges': {
                id: {
                    'type': 'NdArray',
                    'dataType': 'float',
                    'axisNames': ['t'],
                    'shape': [length],
                    'values': values
                }
            }
        }, length

    @staticmethod
    def _generate_paramters(datastream: dir, label: str) -> dict:
        """
        Generate parameters for a given datastream.

        :param datastream: The datastream data to generate parameters for.
        :param label: The label for the parameter.

        :returns: A dictionary containing the parameter definition.
        """

        return {
            'type': 'Parameter',
            'description': {'en': datastream['description']},
            'observedProperty': {'id': label, 'label': {'en': label}},
            'unit': {
                'label': {'en': datastream['unitOfMeasurement']['name']},
                'symbol': datastream['unitOfMeasurement']['symbol']
            }
        }

    @staticmethod
    def _make_dtf(datetime_: str) -> str:
        """
        Create a Date-Time filter for querying.

        :param datetime_: Temporal filter.

        :returns: A string datetime filter for use in queries.
        """

        dtf_r = []
        if '/' in datetime_:
            time_start, time_end = datetime_.split('/')
            if time_start != '..':
                dtf_r.append(f'phenomenonTime ge {time_start}')

            if time_end != '..':
                dtf_r.append(f'phenomenonTime le {time_end}')

        else:
            dtf_r.append(f'phenomenonTime eq {datetime_}')

        return ' and '.join(dtf_r)

    def _make_coverage_collection(self, response):
        """
        Build a CoverageCollection from the SensorThings API response.

        :param response: source response from SensorThings.

        :returns: The updated CoverageCollection object.
        """

        cc = {
            'type': 'CoverageCollection',
            'domainType': 'PointSeries',
            'parameters': {},
            'coverages': []
        }

        for feature in response['value']:
            if len(feature['Datastreams']) == 0:
                continue

            id = feature['name'].replace(' ', '+')

            for datastream in feature['Datastreams']:
                coverage, length = self._generate_coverage(datastream, id)
                if length > 0:
                    cc['coverages'].append(coverage)
                    cc['parameters'][id] = self._generate_paramters(
                        datastream, feature['name']
                    )

        if cc['parameters'] == {} or cc['coverages'] == []:
            msg = 'No data found'
            LOGGER.warning(msg)
            raise ProviderNoDataError(msg)

        return cc

    @staticmethod
    def _expand_observations(datastream: dict):
        """
        Expand and extract observation times and values from a datastream.

        :param datastream: The datastream containing observations.

        :returns: A tuple containing lists of times and values.
        """

        times = []
        values = []
        # TODO: Expand observations when 'Observations@iot.nextLink'
        # or '@iot.nextLink' is present
        for obs in datastream['Observations']:
            resultTime = obs['resultTime'] or obs['phenomenonTime']
            if obs['result'] is not None and resultTime:
                try:
                    result = float(obs['result'])
                except ValueError:
                    result = obs['result']
                times.append(resultTime)
                values.append(result)

        return times, values
