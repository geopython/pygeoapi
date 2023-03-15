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

from requests import Session, get, codes
import logging
from pygeoapi.provider.base import (BaseProvider, ProviderQueryError,
                                    ProviderConnectionError,
                                    ProviderItemNotFoundError)
from json.decoder import JSONDecodeError
from pygeoapi.util import yaml_load, url_join, crs_transform

LOGGER = logging.getLogger(__name__)

ENTITY = {
    'Thing', 'Things', 'Observation', 'Observations',
    'Location', 'Locations', 'Sensor', 'Sensors',
    'Datastream', 'Datastreams', 'ObservedProperty',
    'ObservedProperties', 'FeatureOfInterest', 'FeaturesOfInterest',
    'HistoricalLocation', 'HistoricalLocations'
    }
_EXPAND = {
    'Things': """
        Locations
        ,Datastreams
    """,
    'Observations': """
        Datastream
        ,FeatureOfInterest
    """,
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
    """SensorThings API (STA) Provider
    """

    def __init__(self, provider_def):
        """
        STA Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class

        :returns: pygeoapi.provider.base.SensorThingsProvider
        """
        LOGGER.debug("Logger STA Init")

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
        if self.id_field is None or not self.id_field:
            self.id_field = '@iot.id'

        # Create intra-links
        self.intralink = provider_def.get('intralink', False)
        self._linkables = {}
        if provider_def.get('rel_link') and self.intralink:   # For pytest
            self._rel_link = provider_def['rel_link']
        else:
            self._from_env()

        self.get_fields()

    def get_fields(self):
        """
         Get fields of STA Provider

        :returns: dict of fields
        """
        if not self.fields:
            p = {'$expand': EXPAND[self.entity], '$top': 1}
            r = get(self._url, params=p)
            try:
                results = r.json()['value'][0]
            except JSONDecodeError as err:
                LOGGER.error(f'Entity {self.entity} error: {err}')
                LOGGER.error(f'Bad url response at {r.url}')
                raise ProviderQueryError(err)
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

    @crs_transform
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

    @crs_transform
    def get(self, identifier, **kwargs):
        """
        Query the STA by id

        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """
        return self._load(identifier=identifier)

    def _from_env(self):
        """
        Private function: Load environment data into
        provider attributes

        """
        import os
        with open(os.getenv('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
            CONFIG = yaml_load(fh)
            self._rel_link = CONFIG['server']['url']

            # Validate intra-links
            for (name, rs) in CONFIG['resources'].items():
                if not rs.get('providers') or \
                   rs['providers'][0]['name'] != 'SensorThings':
                    continue

                _entity = rs['providers'][0].get('entity')
                uri = rs['providers'][0].get('uri_field', '')

                for p in rs['providers']:
                    # Validate linkable provider
                    if (p['name'] != 'SensorThings'
                            or not p.get('intralink', False)
                            or p['data'] != self.data):
                        continue

                    if p.get('default', False):
                        _entity = p['entity']
                        uri = p['uri_field']

                    self._linkables[_entity] = {}
                    self._linkables[_entity].update({
                        'n': name, 'u': uri
                    })

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
        feature_collection = {
            'type': 'FeatureCollection', 'features': []
        }
        # Make params
        params = {
            '$expand': EXPAND[self.entity],
            '$skip': str(offset),
            '$top': str(limit),
            '$count': 'true'
        }
        if properties or bbox or datetime_:
            params['$filter'] = self._make_filter(properties, bbox, datetime_)
        if sortby:
            params['$orderby'] = self._make_orderby(sortby)

        # Start session
        s = Session()

        # Form URL for GET request
        LOGGER.debug('Sending query')
        if identifier:
            r = s.get(f'{self._url}({identifier})', params=params)
        else:
            r = s.get(self._url, params=params)

        if r.status_code == codes.bad:
            LOGGER.error('Bad http response code')
            raise ProviderConnectionError('Bad http response code')
        response = r.json()

        # if hits, return count
        if resulttype == 'hits':
            LOGGER.debug('Returning hits')
            feature_collection['numberMatched'] = response.get('@iot.count')
            return feature_collection

        # Query if values are less than expected
        v = [response, ] if identifier else response.get('value')
        hits_ = 1 if identifier else min(limit, response.get('@iot.count'))
        while len(v) < hits_:
            LOGGER.debug('Fetching next set of values')
            next_ = response.get('@iot.nextLink')
            if next_ is None:
                break
            else:
                with s.get(next_) as r:
                    response = r.json()
                    v.extend(response.get('value'))

        # End session
        s.close()

        # Properties filter & display
        keys = (() if not self.properties and not select_properties else
                set(self.properties) | set(select_properties))

        for entity in v[:hits_]:
            # Make feature
            id = entity.pop(self.id_field)
            id = f"'{id}'" if isinstance(id, str) else str(id)
            f = {
                'type': 'Feature', 'properties': {},
                'geometry': None, 'id': id
            }

            # Make geometry
            if not skip_geometry:
                f['geometry'] = self._geometry(entity)

            # Fill properties block
            try:
                f['properties'] = self._expand_properties(entity, keys)
            except KeyError as err:
                LOGGER.error(err)
                raise ProviderQueryError(err)

            feature_collection['features'].append(f)

        feature_collection['numberReturned'] = len(
            feature_collection['features'])

        if identifier:
            return f
        else:
            return feature_collection

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
            if (self.id_field == '@iot.id'
                    and _['property'] in ENTITY):
                ret.append(f"{_['property']}/@iot.id {_map[_['order']]}")
            else:
                ret.append(f"{_['property']} {_map[_['order']]}")
        return ','.join(ret)

    def _geometry(self, entity):
        """
        Private function: Retrieve STA geometry

        :param entity: SensorThings entity

        :returns: GeoJSON Geometry for feature
        """
        try:
            if self.entity == 'Things':
                return entity.get('Locations')[0]['location']
            elif self.entity == 'Datastreams':
                try:
                    geo = entity['Observations'][0][
                        'FeatureOfInterest'].pop('feature')
                except KeyError:
                    geo = entity['Thing'].pop('Locations')[
                        0]['location']
                return geo
            elif self.entity == 'Observations':
                return entity.get('FeatureOfInterest').pop('feature')
        except ProviderItemNotFoundError as err:
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)

    def _expand_properties(self, entity, keys=(), uri=''):
        """
        Private function: Parse STA entity into feature

        :param entity: SensorThings entity
        :param keys: keys used in properties block
        :param uri: uri of STA entity

        :returns: dict of SensorThings feature properties
        """
        if self.entity == 'Things':
            extra_props = entity['Locations'][0].get('properties', {})
            entity['properties'].update(extra_props)
        elif 'Thing' in entity.keys():
            t = entity.get('Thing')
            extra_props = t['Locations'][0].get('properties', {})
            t['properties'].update(extra_props)

        for k, v in entity.items():
            # Create intra links
            ks = f'{k}s'
            if self.uri_field is not None and k in ['properties']:
                uri = v.get(self.uri_field, '')

            elif k in self._linkables.keys():
                if self._linkables[k]['u'] != '':
                    for i, _v in enumerate(v):
                        v[i] = _v['properties'][self._linkables[k]['u']]
                    continue
                for i, _v in enumerate(v):
                    id_ = _v[self.id_field]
                    id_ = f"'{id_}'" if isinstance(id_, str) else str(id_)
                    v[i] = url_join(self._rel_link, f"collections/{self._linkables[k]['n']}/items/{id_}")  # noqa

            elif ks in self._linkables.keys():
                if self._linkables[ks]['u'] != '':
                    entity[k] = v['properties'][self._linkables[ks]['u']]
                    continue
                id = v[self.id_field]
                id = f"'{id}'" if isinstance(id, str) else str(id)
                entity[k] = url_join(
                    self._rel_link,
                    f"collections/{self._linkables[ks]['n']}/items/{id_}")

        # Make properties block
        if entity.get('properties'):
            entity.update(entity.pop('properties'))

        if keys:
            ret = {}
            for k in keys:
                ret[k] = entity.pop(k)
            entity = ret

        # Retain URI if present
        if self.uri_field is not None and uri != '':
            entity[self.uri_field] = uri

        return entity

    def __repr__(self):
        return f'<SensorThingsProvider> {self.data}, {self.entity}'
