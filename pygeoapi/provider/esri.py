# =================================================================
#
# Authors: Benjamin Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2022 Benjamin Webb
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

from copy import deepcopy
import json
import logging
from requests import Session, codes

from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
                                    ProviderTypeError, ProviderQueryError)
from pygeoapi.util import format_datetime, crs_transform

LOGGER = logging.getLogger(__name__)

ARCGIS_URL = 'https://www.arcgis.com'
GENERATE_TOKEN_URL = 'https://www.arcgis.com/sharing/rest/generateToken'


class ESRIServiceProvider(BaseProvider):
    """ESRI Feature/Map Service Provider"""

    def __init__(self, provider_def):
        """
        ESRI Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data, id_field, name set in parent class

        :returns: pygeoapi.provider.esri.ESRIServiceProvider
        """
        LOGGER.debug('Logger ESRI Init')

        super().__init__(provider_def)

        self.url = f'{self.data}/query'
        self.crs = provider_def.get('crs', '4326')
        self.username = provider_def.get('username')
        self.password = provider_def.get('password')
        self.token = None

        self.session = Session()

        self.login()
        self.get_fields()

    def get_fields(self):
        """
         Get fields of ESRI Provider

        :returns: `dict` of fields
        """

        if not self.fields:
            # Load fields
            params = {'f': 'pjson'}
            resp = self.get_response(self.data, params=params)

            if resp.get('error') is not None:
                msg = f"Connection error: {resp['error']['message']}"
                LOGGER.error(msg)
                raise ProviderConnectionError(msg)

            try:
                # Verify Feature/Map Service supports required capabilities
                advCapabilities = resp['advancedQueryCapabilities']
                assert advCapabilities['supportsPagination']
                assert advCapabilities['supportsOrderBy']
                assert 'geoJSON' in resp['supportedQueryFormats']
            except KeyError:
                msg = f'Could not access resource {self.data}'
                LOGGER.error(msg)
                raise ProviderConnectionError(msg)
            except AssertionError as err:
                msg = f'Unsupported Feature/Map Server: {err}'
                LOGGER.error(msg)
                raise ProviderTypeError(msg)

            for _ in resp['fields']:
                self.fields.update({_['name']: {'type': _['type']}})

        return self.fields

    @crs_transform
    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, **kwargs):
        """
        ESRI query

        :param offset: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param q: full-text search term(s)

        :returns: `dict` of GeoJSON FeatureCollection
        """

        # Default feature collection and request parameters

        params = {
            'f': 'geoJSON',
            'outSR': self.crs,
            'outFields': self._make_fields(select_properties),
            'where': self._make_where(properties, datetime_)
            }

        if bbox != []:
            xmin, ymin, xmax, ymax = bbox
            params['inSR'] = '4326'
            params['geometryType'] = 'esriGeometryEnvelope'
            params['geometry'] = f'{xmin},{ymin},{xmax},{ymax}'

        fc = {
            'type': 'FeatureCollection',
            'features': [],
            'numberMatched': self._get_count(params)
        }

        if resulttype == 'hits':
            return fc

        params['orderByFields'] = self._make_orderby(sortby)

        params['returnGeometry'] = 'false' if skip_geometry else 'true'
        params['resultOffset'] = offset
        params['resultRecordCount'] = limit

        hits_ = min(limit, fc['numberMatched'])
        fc['features'] = self._get_all(params, hits_)

        fc['numberReturned'] = len(fc['features'])

        return fc

    @crs_transform
    def get(self, identifier, **kwargs):
        """
        Query ESRI by id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """

        LOGGER.debug(f'Fetching item: {identifier}')
        params = {
            'f': 'geoJSON',
            'outSR': self.crs,
            'objectIds': identifier,
            'outFields': self._make_fields()
        }

        resp = self.get_response(self.url, params=params)
        LOGGER.debug('Returning item')
        return resp['features'].pop()

    def login(self):
        # Generate token from username and password
        if self.token is None:

            if None in [self.username, self.password]:
                msg = 'Missing ESRI login information, not setting token'
                LOGGER.debug(msg)
                return

            params = {
                'f': 'pjson',
                'username': self.username,
                'password': self.password,
                'referer': ARCGIS_URL
            }

            LOGGER.debug('Logging in')
            with self.session.post(GENERATE_TOKEN_URL, data=params) as r:
                self.token = r.json().get('token')
                # https://enterprise.arcgis.com/en/server/latest/administer/windows/about-arcgis-tokens.htm
                self.session.headers.update({
                    'X-Esri-Authorization': f'Bearer {self.token}'
                })

    def get_response(self, url, **kwargs):
        # Form URL for GET request
        LOGGER.debug('Sending query')
        with self.session.get(url, **kwargs) as r:

            if r.status_code == codes.bad:
                LOGGER.error('Bad http response code')
                raise ProviderConnectionError('Bad http response code')
            try:
                return r.json()
            except json.decoder.JSONDecodeError as err:
                LOGGER.error(f'Bad response at {self.url}')
                raise ProviderQueryError(err)

    @staticmethod
    def _make_orderby(sortby):
        """
        Private function: Make ESRI filter from query properties

        :param sortby: `list` of dicts (property, order)

        :returns: ESRI query `order` clause
        """
        if sortby == []:
            return None

        __ = {'+': 'ASC', '-': 'DESC'}
        ret = [f'{_["property"]} {__[_["order"]]}' for _ in sortby]

        return ','.join(ret)

    def _make_fields(self, select_properties=[]):
        """
        Make ESRI out fields clause

        :param select_properties: list of property names

        :returns: ESRI query `outFields` clause
        """
        if self.properties == [] and select_properties == []:
            return '*'

        if self.properties != [] and select_properties != []:
            outFields = set(self.properties) & set(select_properties)
        else:
            outFields = set(self.properties) | set(select_properties)

        return ','.join(outFields)

    def _make_where(self, properties=[], datetime_=None):
        """
        Make ESRI filter from query properties

        :param properties: `list` of tuples (name, value)
        :param datetime_: `str` temporal (datestamp or extent)

        :returns: ESRI query `where` clause
        """

        if properties == [] and datetime_ is None:
            return '1 = 1'

        p = []

        if properties != []:

            for (k, v) in properties:
                if 'String' in self.fields[k]['type']:
                    p.append(f"{k} = '{v}'")
                else:
                    p.append(f"{k} = {v}")

        if datetime_ is not None:

            def esri_dt(dt):
                dt_ = format_datetime(dt, '%Y-%m-%d %H:%M:%S')
                return f"TIMESTAMP '{dt_}'"

            tf = self.time_field
            if '/' in datetime_:
                time_start, time_end = datetime_.split('/')
                if time_start != '..':
                    p.append(f'{tf} >= {esri_dt(time_start)}')
                if time_end != '..':
                    p.append(f'{tf} <= {esri_dt(time_end)}')
            else:
                p.append(f'{tf} = {self.esri_date(datetime_)}')

        return ' AND '.join(p)

    def _get_count(self, params):
        """
        Count number of features from query args

        :param params: `dict` of query params

        :returns: `int` of feature count
        """
        params = deepcopy(params)

        params['returnCountOnly'] = 'true'
        params['f'] = 'pjson'

        response = self.get_response(self.url, params=params)
        return response.get('count', 0)

    def _get_all(self, params, hits_):
        """
        Get all features from query args

        :param properties: `dict` of query params
        :param hits_: `int` of number of features to expect

        :returns: `list` of features
        """
        params = deepcopy(params)

        # Return feature collection
        features = self.get_response(self.url, params=params).get('features')
        step = len(features)

        # Query if values are less than expected
        while len(features) < hits_:
            LOGGER.debug('Fetching next set of values')
            params['resultOffset'] += step
            params['resultRecordCount'] += step

            fs = self.get_response(self.url, params=params).get('features')
            if len(fs) != 0:
                features.extend(fs)
            else:
                break

        return features

    def __exit__(self, **kwargs):
        self.session.close()

    def __repr__(self):
        return f'<ESRIServiceProvider> {self.data}'
