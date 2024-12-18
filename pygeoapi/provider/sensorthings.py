# =================================================================
#
# Authors: Benjamin Webb <benjamin.miller.webb@gmail.com>
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2024 Benjamin Webb
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
import logging
from requests import Session
from urllib.parse import urlparse

from pygeoapi.config import get_config
from pygeoapi.provider.base import (
    BaseProvider, ProviderQueryError, ProviderConnectionError)
from pygeoapi.util import (
    url_join, get_provider_default, crs_transform, get_base_url)

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
    'ObservedProperties': 'Datastreams/Thing/Locations',
    'Datastreams': """
        Sensor
        ,ObservedProperty
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
    expand = EXPAND

    def __init__(self, provider_def):
        """
        STA Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class

        :returns: pygeoapi.provider.sensorthings.SensorThingsProvider
        """
        LOGGER.debug('Setting SensorThings API (STA) provider')
        self.linked_entity = {}
        super().__init__(provider_def)

        self._generate_mappings(provider_def)
        LOGGER.debug(f'STA endpoint: {self.data}, Entity: {self.entity}')

        # Start session
        self.http = Session()
        self.get_fields()

    def get_fields(self):
        """
        Get fields of STA Provider

        :returns: dict of fields
        """
        if not self._fields:
            r = self._get_response(self._url, {'$top': 1})
            try:
                results = r['value'][0]
            except IndexError:
                LOGGER.warning('could not get fields; returning empty set')
                return {}

            for (n, v) in results.items():
                if isinstance(v, (int, float)) or \
                   (isinstance(v, (dict, list)) and n in ENTITY):
                    self._fields[n] = {'type': 'number'}
                elif isinstance(v, str):
                    self._fields[n] = {'type': 'string'}

        return self._fields

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
        Query STA by id

        :param identifier: feature id

        :returns: dict of single GeoJSON feature
        """
        response = self._get_response(f'{self._url}({identifier})')
        return self._make_feature(response)

    def _load(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None):
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

        # Make defaults
        fc = {'type': 'FeatureCollection', 'features': []}
        params = {
            '$skip': str(offset),
            '$top': str(limit)
        }

        if properties or bbox or datetime_:
            params['$filter'] = self._make_filter(properties, bbox, datetime_)

        if sortby:
            params['$orderby'] = self._make_orderby(sortby)

        # Send request
        LOGGER.debug('Sending query')
        if resulttype == 'hits':
            LOGGER.debug('Returning hits')
            params['$count'] = 'true'
            response = self._get_response(url=self._url, params=params)
            fc['numberMatched'] = response.get('@iot.count')
            return fc

        # Make features
        response = self._get_response(url=self._url, params=params)

        matched = response.get('@iot.count')
        if matched:
            fc['numberMatched'] = matched

        # Query if values are less than expected
        v = response.get('value')
        while len(v) < limit:
            try:
                LOGGER.debug('Fetching next set of values')
                next_ = response['@iot.nextLink']

                # Ensure we only use provided network location
                next_ = next_.replace(urlparse(next_).netloc,
                                      urlparse(self.data).netloc)

                response = self._get_response(next_)
                v.extend(response['value'])
            except (ProviderConnectionError, KeyError):
                break

        hits_ = min(limit, len(v))
        props = (select_properties, skip_geometry)
        fc['features'] = [self._make_feature(e, *props) for e in v[:hits_]]
        fc['numberReturned'] = hits_

        return fc

    def _make_feature(self, feature, select_properties=[], skip_geometry=False,
                      entity=None):
        """
        Private function: Create feature from entity

        :param feature: `dict` of STA entity
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param entity: SensorThings entity name

        :returns: dict of GeoJSON Feature
        """
        _ = feature.pop(self.id_field)
        id = f"'{_}'" if isinstance(_, str) else str(_)
        f = {
            'type': 'Feature', 'id': id, 'properties': {}, 'geometry': None
        }

        # Make geometry
        if not skip_geometry:
            f['geometry'] = self._geometry(feature, entity)

        # Fill properties block
        try:
            f['properties'] = self._expand_properties(
                feature, select_properties, entity)
        except KeyError as err:
            LOGGER.error(err)
            raise ProviderQueryError(err)

        return f

    def _get_response(self, url, params={}, entity=None, expand=None):
        """
        Private function: Get STA response

        :param url: request url
        :param params: query parameters
        :param entity: SensorThings entity name
        :param expand: SensorThings expand query


        :returns: STA response
        """
        if expand:
            params.update({'$expand': expand})
        else:
            entity_ = entity or self.entity
            params.update({'$expand': self.expand[entity_]})

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

    def _make_filter(self, properties, bbox=[], datetime_=None,
                     entity=None):
        """
        Private function: Make STA filter from query properties

        :param properties: list of tuples (name, value)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param entity: SensorThings entity name

        :returns: STA $filter string of properties
        """
        ret = []
        for (name, value) in properties:
            if name in ENTITY:
                ret.append(f'{name}/@iot.id eq {value}')
            else:
                ret.append(f'{name} eq {value}')

        if bbox:
            entity_ = entity or self.entity
            ret.append(self._make_bbox(bbox, entity_))

        if datetime_ is not None:
            if self.time_field is None:
                msg = 'time_field not enabled for collection'
                LOGGER.error(msg)
                raise ProviderQueryError(msg)

            if '/' in datetime_:
                time_start, time_end = datetime_.split('/')
                if time_start != '..':
                    ret.append(f'{self.time_field} ge {time_start}')
                if time_end != '..':
                    ret.append(f'{self.time_field} le {time_end}')
            else:
                ret.append(f'{self.time_field} eq {datetime_}')

        return ' and '.join(ret)

    @staticmethod
    def _make_bbox(bbox, entity):
        minx, miny, maxx, maxy = bbox
        bbox_ = f'POLYGON(({minx} {miny},{maxx} {miny},{maxx} {maxy},{minx} {maxy},{minx} {miny}))' # noqa
        if entity == 'Things':
            loc = 'Locations/location'
        elif entity == 'Datastreams':
            loc = 'Thing/Locations/location'
        elif entity == 'Observations':
            loc = 'FeatureOfInterest/feature'
        elif entity == 'ObservedProperties':
            loc = 'Datastreams/observedArea'
        return f"st_within({loc},geography'{bbox_}')"

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

    def _geometry(self, feature, entity=None):
        """
        Private function: Retrieve STA geometry

        :param feature: SensorThings entity
        :param entity: SensorThings entity name

        :returns: GeoJSON Geometry for feature
        """
        entity_ = entity or self.entity
        try:
            if entity_ == 'Things':
                return feature['Locations'][0]['location']

            elif entity_ == 'Observations':
                return feature['FeatureOfInterest'].pop('feature')

            elif entity_ == 'Datastreams':
                try:
                    return feature['Observations'][0]['FeatureOfInterest'].pop('feature')  # noqa
                except (KeyError, IndexError):
                    return feature['Thing'].pop('Locations')[0]['location']

            elif entity_ == 'ObservedProperties':
                return feature['Datastreams'][0]['Thing']['Locations'][0]['location'] # noqa

        except (KeyError, IndexError):
            LOGGER.warning('No geometry found')
            return None

    def _expand_properties(self, feature, keys=(), uri='',
                           entity=None):
        """
        Private function: Parse STA entity into feature

        :param feature: `dict` of SensorThings entity
        :param keys: keys used in properties block
        :param uri: uri of STA entity
        :param entity: SensorThings entity name

        :returns: dict of SensorThings feature properties
        """
        # Properties filter & display
        keys = (() if not self.properties and not keys else
                set(self.properties) | set(keys))

        entity = entity or self.entity
        if entity == 'Things':
            self._expand_location(feature)
        elif 'Thing' in feature.keys():
            self._expand_location(feature['Thing'])

        # Retain URI if present
        if feature.get('properties') and self.uri_field:
            uri = feature['properties']

        # Create intra links
        for k, v in feature.items():
            if k in self.linked_entity:
                feature[k] = [self._get_uri(_v, **self.linked_entity[k])
                              for _v in v]
                LOGGER.debug(f'Created link for {k}')
            elif f'{k}s' in self.linked_entity:
                feature[k] = \
                    self._get_uri(v, **self.linked_entity[f'{k}s'])
                LOGGER.debug(f'Created link for {k}')

        # Make properties block
        if feature.get('properties'):
            feature.update(feature.pop('properties'))

        if keys:
            ret = {k: feature.pop(k) for k in keys}
            feature = ret

        if self.uri_field is not None and uri != '':
            feature[self.uri_field] = uri

        return feature

    @staticmethod
    def _expand_location(entity):
        """
        Private function: Get STA item uri

        :param entity: `dict` of STA entity

        :returns: None
        """
        try:
            extra_props = entity['Locations'][0]['properties']
            entity['properties'].update(extra_props)
        except (KeyError, IndexError):
            selfLink = entity['@iot.selfLink']
            LOGGER.debug(f'{selfLink} has no Location properties')

    def _get_uri(self, entity, cnm, cid='@iot.id', uri=''):
        """
        Private function: Get STA item uri

        :param entity: `dict` of STA entity
        :param cnm: `str` of OAPI collection name
        :param cid: `str` of OAPI collection id field
        :param uri: `str` of STA entity uri field

        :returns: `str` of item uri
        """
        if uri:
            return entity['properties'][uri]
        else:
            id_ = entity[cid]
            id_ = f"'{id_}'" if isinstance(id_, str) else str(id_)
            uri = (self.rel_link, 'collections', cnm, 'items', id_)
            return url_join(*uri)

    @staticmethod
    def _get_entity(uri):
        """
        Private function: Parse STA Entity from uri

        :param uri: `str` of STA entity uri

        :returns: `str` of STA Entity
        """
        e = uri.split('/').pop()
        if e in ENTITY:
            return e
        else:
            return ''

    def _generate_mappings(self, provider_def: dict):
        """
        Generate mappings for the STA entity and set up intra-links.

        This function sets up the necessary mappings and configurations for
        the STA entity based on the provided provider definition.

        :param provider_def: `dict` of provider definition containing
                            configuration details for the STA entity.
        """
        self.data.rstrip('/')
        try:
            self.entity = provider_def['entity']
            self._url = url_join(self.data, self.entity)
        except KeyError:
            LOGGER.debug('Attempting to parse Entity from provider data')
            if not self._get_entity(self.data):
                raise RuntimeError('Entity type required')
            self.entity = self._get_entity(self.data)
            self._url = self.data
            self.data = self._url.rstrip(f'/{self.entity}')

        # Default id
        if self.id_field:
            LOGGER.debug(f'Using id field: {self.id_field}')
        else:
            LOGGER.debug('Using default @iot.id for id field')
            self.id_field = '@iot.id'

        # Custom expand
        if provider_def.get('expand'):
            EXPAND[self.entity] = provider_def['expand']

        # Create intra-links
        self.intralink = provider_def.get('intralink', False)
        if self.intralink and provider_def.get('rel_link'):
            # For pytest
            self.rel_link = provider_def['rel_link']

        elif self.intralink:
            # Read from pygeoapi config
            CONFIG = get_config()
            self.rel_link = get_base_url(CONFIG)

            for name, rs in CONFIG['resources'].items():
                pvs = rs.get('providers')
                p = get_provider_default(pvs)
                e = p.get('entity') or self._get_entity(p['data'])
                if any([
                    not pvs,  # No providers in resource
                    not p.get('intralink'),  # No configuration for intralinks
                    not e,  # No STA entity found
                    self.data not in p.get('data')  # No common STA endpoint
                ]):
                    continue

                if p.get('uri_field'):
                    LOGGER.debug(f'Linking {e} with field: {p["uri_field"]}')
                else:
                    LOGGER.debug(f'Linking {e} with collection: {name}')

                self.linked_entity[e] = {
                    'cnm': name,  # OAPI collection name,
                    'cid': p.get('id_field', '@iot.id'),  # OAPI id_field
                    'uri': p.get('uri_field')  # STA uri_field
                }

    def __repr__(self):
        return f'<SensorThingsProvider> {self.data}, {self.entity}'
