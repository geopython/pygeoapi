# =================================================================
#
# Authors: Benjamin Webb <benjamin.miller.webb@gmail.com>
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2023 Benjamin Webb
# Copyright (c) 2022 Tom Kralidis
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

from json.decoder import JSONDecodeError
import os
import logging
from requests import Session

from pygeoapi.provider.base import (BaseProvider, ProviderQueryError,
                                    ProviderConnectionError)
from pygeoapi.util import yaml_load, url_join, get_provider_default

LOGGER = logging.getLogger(__name__)

ENTITY = {
    'Thing', 'Things', 'Observation', 'Observations',
    'Location', 'Locations', 'Sensor', 'Sensors',
    'Datastream', 'Datastreams', 'ObservedProperty',
    'ObservedProperties', 'FeatureOfInterest', 'FeaturesOfInterest',
    'HistoricalLocation', 'HistoricalLocations'
}
_EXPAND = {
    'Things': 'Locations,Datastreams',
    'Observations': 'Datastream,FeatureOfInterest',
    'Datastreams': """
        Sensor
        ,ObservedProperty
        ,Thing
        ,Thing/Locations
        ,Observations(
            $select=@iot.id;
            $orderby=phenomenonTime_desc
            )
        ,Observations/FeatureOfInterest(
            $select=feature
            )
    """
}
EXPAND = {k: ''.join(v.split()).replace('_', ' ')
          for (k, v) in _EXPAND.items()}


class SensorThingsProvider(BaseProvider):
    """SensorThings API (STA) Provider"""

    def __init__(self, provider_def):
        """
        STA Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class

        :returns: pygeoapi.provider.base.SensorThingsProvider
        """
        LOGGER.debug('Setting SensorThings API properties')

        super().__init__(provider_def)
        try:
            self.entity = provider_def['entity']
            self._url = url_join(self.data, self.entity)
        except KeyError:
            if self.data.split('/').pop() in ENTITY:
                self.entity = self.data.split('/').pop()
                self._url = self.data
            else:
                raise RuntimeError('Entity type required')

        # Default id
        if not self.id_field:
            self.id_field = '@iot.id'

        # Create intra-links
        self.intralink = provider_def.get('intralink', False)
        self.links = {}
        if self.intralink and provider_def.get('rel_link'):   # For pytest
            self._rel = provider_def['rel_link']
        elif self.intralink:
            with open(os.getenv('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
                CONFIG = yaml_load(fh)

            self._rel = CONFIG['server']['url']

            # Validate intra-links
            for (name, rs) in CONFIG['resources'].items():
                pvs = rs.get('providers')
                p = get_provider_default(pvs)

                if not pvs or not p.get('intralink'):
                    continue

                entity = p['entity'] if p.get(
                    'entity') else p['data'].split('/').pop()

                self.links[entity] = {
                    'n': name, 'u': p.get('uri_field', '')
                }

        # Start session
        self.http = Session()
        self.get_fields()

    def get_fields(self):
        """
        Get fields of STA Provider

        :returns: dict of fields
        """
        if not self.fields:
            r = self._get_response(self._url)
            try:
                results = r['value'][0]
            except IndexError:
                LOGGER.warning('could not get fields; returning empty set')
                return {}

            for (n, v) in results.items():
                if isinstance(v, (int, float)) or \
                   (isinstance(v, (dict, list)) and n in ENTITY):
                    self.fields[n] = {'type': 'number'}
                elif isinstance(v, str):
                    self.fields[n] = {'type': 'string'}

        return self.fields

    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None, **kwargs):
        """
        STA query

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

        :returns: dict of GeoJSON FeatureCollection
        """

        return self._load(offset, limit, resulttype, bbox=bbox,
                          datetime_=datetime_, properties=properties,
                          sortby=sortby, select_properties=select_properties,
                          skip_geometry=skip_geometry)

    def get(self, identifier, **kwargs):
        """
        Query STA by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """
        return self._load(identifier=identifier)

    def _load(self, offset=0, limit=10, resulttype='results',
              identifier=None, bbox=[], datetime_=None, properties=[],
              sortby=[], select_properties=[], skip_geometry=False, q=None):
        """
        Private function: Load STA data

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

        :returns: dict of GeoJSON FeatureCollection
        """

        fc = {'type': 'FeatureCollection', 'features': []}

        # Make params
        params = {
            '$skip': str(offset),
            '$top': str(limit)
        }

        if properties or bbox or datetime_:
            params['$filter'] = self._make_filter(properties, bbox, datetime_)

        if sortby:
            params['$orderby'] = self._make_orderby(sortby)

        def make_feature(entity):
            _ = entity.pop(self.id_field)
            id = f"'{_}'" if isinstance(_, str) else str(_)
            f = {
                'type': 'Feature', 'id': id, 'properties': {}, 'geometry': None
            }

            # Make geometry
            if not skip_geometry:
                f['geometry'] = self._geometry(entity)

            # Fill properties block
            try:
                f['properties'] = self._expand_properties(
                    entity, select_properties)
            except KeyError as err:
                LOGGER.error(err)
                raise ProviderQueryError(err)

            return f

        # Form URL for GET request
        LOGGER.debug('Sending query')
        if identifier:
            url = f'{self._url}({identifier})'
            response = self._get_response(url=url, params=params)
            return make_feature(response)
        elif resulttype == 'hits':
            LOGGER.debug('Returning hits')
            params['$count'] = 'true'
            response = self._get_response(url=self._url, params=params)
            fc['numberMatched'] = response.get('@iot.count')
            return fc
        else:
            response = self._get_response(url=self._url, params=params)
            count = len(response.get('value'))

        hits_ = min(limit, count)
        # Query if values are less than expected
        v = response['value']
        while len(v) < hits_:
            LOGGER.debug('Fetching next set of values')
            next_ = response.get('@iot.nextLink')
            if next_:
                response = self._get_response(next_)
                v.extend(response.get('value'))
            else:
                break

        # Make features
        fc['features'] = [make_feature(entity) for entity in v[:hits_]]
        fc['numberReturned'] = len(fc['features'])

        return fc

    def _get_response(self, url: str, params: dict = {}):
        """
        Private function: Get STA response

        :param url: request url
        :param params: query parameters

        :returns: STA response
        """
        params.update({'$expand': EXPAND[self.entity]})

        r = self.http.get(url, params=params)

        if not r.ok:
            LOGGER.error('Bad http response code')
            raise ProviderConnectionError('Bad http response code')

        try:
            response = r.json()
        except JSONDecodeError as err:
            LOGGER.error('JSON decode error')
            raise ProviderQueryError(err)

        return response

    def _make_filter(self, properties, bbox=[], datetime_=None):
        """
        Private function: Make STA filter from query properties

        :param properties: list of tuples (name, value)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)

        :returns: STA $filter string of properties
        """
        ret = []
        for (name, value) in properties:
            if name in ENTITY:
                ret.append(f'{name}/@iot.id eq {value}')
            else:
                ret.append(f'{name} eq {value}')

        if bbox:
            minx, miny, maxx, maxy = bbox
            bbox_ = f'POLYGON (({minx} {miny}, {maxx} {miny}, \
                     {maxx} {maxy}, {minx} {maxy}, {minx} {miny}))'
            if self.entity == 'Things':
                loc = 'Locations/location'
            elif self.entity == 'Datastreams':
                loc = 'Thing/Locations/location'
            elif self.entity == 'Observations':
                loc = 'FeatureOfInterest/feature'
            ret.append(f"st_within({loc}, geography'{bbox_}')")

        if datetime_ is not None:
            if self.time_field is None:
                LOGGER.error('time_field not enabled for collection')
                raise ProviderQueryError()

            if '/' in datetime_:
                time_start, time_end = datetime_.split('/')
                if time_start != '..':
                    ret.append(f'{self.time_field} ge {time_start}')
                if time_end != '..':
                    ret.append(f'{self.time_field} le {time_end}')
            else:
                ret.append(f'{self.time_field} eq {datetime_}')

        return ' and '.join(ret)

    def _make_orderby(self, sortby):
        """
        Private function: Make STA filter from query properties

        :param sortby: list of dicts (property, order)

        :returns: STA $orderby string
        """
        ret = []
        _map = {'+': 'asc', '-': 'desc'}
        for _ in sortby:
            prop = _['property']
            order = _map[_['order']]
            if prop in ENTITY:
                ret.append(f'{prop}/@iot.id {order}')
            else:
                ret.append(f'{prop} {order}')
        return ','.join(ret)

    def _geometry(self, entity):
        """
        Private function: Retrieve STA geometry

        :param entity: SensorThings entity

        :returns: GeoJSON Geometry for feature
        """
        try:
            if self.entity == 'Things':
                return entity['Locations'][0]['location']
            elif self.entity == 'Datastreams':
                try:
                    geo = entity['Observations'][0][
                        'FeatureOfInterest'].pop('feature')
                except (KeyError, IndexError):
                    geo = entity['Thing'].pop('Locations')[
                        0]['location']
                return geo
            elif self.entity == 'Observations':
                return entity['FeatureOfInterest'].pop('feature')
        except (KeyError, IndexError):
            LOGGER.warning('No geometry found')
            return None

    def _expand_properties(self, entity, keys=(), uri=''):
        """
        Private function: Parse STA entity into feature

        :param entity: SensorThings entity
        :param keys: keys used in properties block
        :param uri: uri of STA entity

        :returns: dict of SensorThings feature properties
        """
        LOGGER.debug('Adding extra properties')

        # Properties filter & display
        keys = (() if not self.properties and not keys else
                set(self.properties) | set(keys))

        def expand_location(thing):
            try:
                extra_props = thing['Locations'][0].get('properties', {})
                thing['properties'].update(extra_props)
            except (KeyError, IndexError):
                LOGGER.warning(f'{self.entity} missing Location')

        def get_id(v_, k_):
            id_ = v_[self.id_field]
            id_ = f"'{id_}'" if isinstance(id_, str) else str(id_)
            return url_join(
                self._rel, 'collections', self.links[k_]['n'], 'items', id_)

        if self.entity == 'Things':
            expand_location(entity)
        elif 'Thing' in entity.keys():
            expand_location(entity['Thing'])

        # Create intra links
        LOGGER.debug('Creating intralinks')
        for k, v in entity.items():
            ks = f'{k}s'

            if self.uri_field is not None and k in ['properties']:
                uri = v.get(self.uri_field)

            elif k in self.links:
                link = self.links[k]
                if link['u']:
                    for i, _v in enumerate(v):
                        v[i] = _v['properties'][link['u']]
                else:
                    for i, _v in enumerate(v):
                        v[i] = get_id(_v, k)

            elif ks in self.links:
                link = self.links[ks]
                entity[k] = \
                    v['properties'][link['u']] if link['u'] else get_id(v, ks)

        # Make properties block
        LOGGER.debug('Making properties block')
        if entity.get('properties'):
            entity.update(entity.pop('properties'))

        if keys:
            ret = {k: entity.pop(k) for k in keys}
            entity = ret

        # Retain URI if present
        if self.uri_field is not None and uri != '':
            entity[self.uri_field] = uri

        return entity

    def __repr__(self):
        return f'<SensorThingsProvider> {self.data}, {self.entity}'
