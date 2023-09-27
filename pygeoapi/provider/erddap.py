# =================================================================
#
# Authors: David Berry <david.i.berry@wmo.int>
#          Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2023 David Inglis Berry
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

# feature provider for ERDDAP integrations
#
# Tabledap sample configuration
# -----------------------------
#
# providers:
#     -   type: feature
#         name: pygeoapi.provider.erddap.TabledapProvider
#         data: http://osmc.noaa.gov/erddap/tabledap/OSMC_Points
#         id_field: id
#         options:
#             filters: "&parameter=\"SLP\"&platform!=\"C-MAN%20WEATHER%20STATIONS\"&platform!=\"TIDE GAUGE STATIONS (GENERIC)\""   # noqa
#             max_age_hours: 12


from datetime import datetime, timedelta, timezone
import logging

import requests

from pygeoapi.provider.base import (
    BaseProvider, ProviderNotFoundError, ProviderQueryError)

LOGGER = logging.getLogger(__name__)


class TabledapProvider(BaseProvider):
    def __init__(self, provider_def):
        super().__init__(provider_def)

        LOGGER.debug('Setting provider query filters')
        self.filters = self.options.get('filters')
        self.fields = self.get_fields()

    def get_fields(self):
        LOGGER.debug('Fetching one feature for field definitions')
        properties = self.query(limit=1)['features'][0]['properties']

        for key, value in properties.items():
            LOGGER.debug(f'Field: {key}={value}')

            data_type = type(value).__name__

            if data_type == 'str':
                data_type = 'string'
            if data_type == 'float':
                data_type = 'number'
            properties[key] = {'type': data_type}

        return properties

    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None,
              filterq=None, **kwargs):

        query_params = []

        max_age_hours = self.options.get('max_age_hours')
        url = f'{self.data}.geoJson'

        if self.filters is not None:
            LOGGER.debug(f'Setting filters ({self.filters})')
            query_params.append(self.filters)

        if max_age_hours is not None:
            LOGGER.debug(f'Setting default time filter {max_age_hours} hours')
            currenttime = datetime.now(timezone.utc)
            mintime = currenttime - timedelta(hours=max_age_hours)
            mintime = mintime.strftime('%Y-%m-%dT%H:%M:%SZ')
            query_params.append(f'time>={mintime}')

        elif datetime_ is not None:
            LOGGER.debug('Setting datetime filters')

            LOGGER.debug('Setting datetime filters')
            if '/' in datetime_:  # envelope
                LOGGER.debug('detected time range')
                time_begin, time_end = datetime_.split('/')

                if time_begin != '..':
                    LOGGER.debug('Setting time_begin')
                    query_params.append(f'time>={time_begin}')
                if time_end != '..':
                    LOGGER.debug('Setting time_end')
                    query_params.append(f'time<={time_end}')
            else:
                query_params.append(f'time={datetime_}')

        if bbox:
            LOGGER.debug('Setting bbox')
            query_params.extend([
                f'latitude>={bbox[1]}',
                f'latitude<={bbox[3]}',
                f'longitude>={bbox[0]}',
                f'longitude<={bbox[2]}'
            ])

        url = f'{url}?{"&".join(query_params)}'

        LOGGER.debug(f'Fetching data from {url}')
        response = requests.get(url)
        LOGGER.debug(f'Response: {response}')
        data = response.json()
        LOGGER.debug(f'Data: {data}')

        matched = len(data['features'])
        returned = limit

        data = data['features'][offset:limit]

        # add id to each feature as this is required by pygeoapi
        for idx in range(len(data)):
            # ID used to extract individual features
            try:
                id_ = data[idx]['properties'][self.id_field]
            except KeyError:
                # ERDDAP changes case of parameters depending on result
                id_ = data[idx]['properties'][self.id_field]
            except Exception as err:
                msg = 'Cannot determine station identifier'
                LOGGER.error(msg, err)
                raise ProviderQueryError(msg)

            obs_time = data[idx]['properties']['time']
            obs_id = f'{id_}.{obs_time}'
            data[idx]['id'] = obs_id

        return {
            'type': 'FeatureCollection',
            'features': data,
            'numberMatched': matched,
            'numberReturned': returned
        }

    def get(self, identifier, **kwargs):

        query_params = []

        url = f'{self.data}.geoJson'

        if self.filters is not None:
            LOGGER.debug(f'Setting filters ({self.filters})')
            query_params.append(self.filters)

        id_, obs_time = identifier.split('.')

        query_params.extend([
            f'time={obs_time}',
            f'{self.id_field}=%22{id_}%22'
        ])

        url = f'{url}?{"&".join(query_params)}'
        LOGGER.debug(f'Fetching data from {url}')

        response = requests.get(url)
        LOGGER.debug(f'Response: {response}')
        data = response.json()
        LOGGER.debug(f'Data: {data}')

        if len(data['features']) < 1:
            msg = 'No features found'
            LOGGER.error(msg)
            raise ProviderNotFoundError(msg)

        LOGGER.debug('Truncating to first feature')
        data = data['features'][0]
        data['id'] = identifier

        return data
