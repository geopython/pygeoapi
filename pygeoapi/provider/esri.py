# =================================================================
#
# Authors: Benjamin Webb <bwebb@lincolninst.edu>
#
# Copyright (c) 2022 Benjamin Webb
# Copyright (c) 2026 Tom Kralidis
# Copyright (c) 2026 Frédéric Morin
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
from datetime import date, datetime
import json
import logging
from requests import Session, codes

from pygeoapi.crs import get_srid
from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
                                    ProviderTypeError, ProviderQueryError,
                                    ProviderInvalidQueryError)
from pygeoapi.util import format_datetime

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
        self.srid = get_srid(self.storage_crs)
        self.username = provider_def.get('username')
        self.password = provider_def.get('password')
        self.token_url = provider_def.get('token_service', ARCGIS_URL)
        self.token_referer = provider_def.get('referer', GENERATE_TOKEN_URL)
        self.token = None
        self.session = Session()

        self.using_deafult_id = any(
            kw == self.id_field
            for kw in ['OBJECTID', 'objectid', 'fid']
        )

        self.login()
        self.get_fields()

    def get_fields(self):
        """
         Get fields of ESRI Provider

        :returns: `dict` of fields
        """

        if not self._fields:
            # Load fields
            try:
                resp = self.get_response(self.data, params={'f': 'pjson'})
            except ProviderConnectionError as err:
                msg = f'Could not access resource {self.data}: {err}'
                LOGGER.error(msg)
                return {}

            if resp.get('error') is not None:
                msg = f"Connection error: {resp['error']['message']}"
                LOGGER.error(msg)
                return {}

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
                self._fields.update({_['name']: {'type': _['type']}})

        return self._fields

    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False,
              crs_transform_spec=None, filterq=None, **kwargs):
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
        :param crs_transform_spec: `CrsTransformSpec` instance, optional
        :param filterq: CQL2 filter expression (`pygeofilter.ast.Node`)

        :returns: `dict` of GeoJSON FeatureCollection
        """

        # Default feature collection and request parameters

        spatial_node, filterq = self._extract_spatial(filterq)

        params = {
            'f': 'geoJSON',
            'outSR': self._get_srid(crs_transform_spec),
            'outFields': self._make_fields(select_properties),
            'where': self._make_where(properties, datetime_, filterq)
            }

        if spatial_node is not None and bbox != []:
            msg = ('Cannot combine a bbox parameter with a CQL2 spatial '
                   'filter')
            LOGGER.error(msg)
            raise ProviderInvalidQueryError(msg)

        if spatial_node is not None:
            params.update(self._spatial_to_params(spatial_node))
        elif bbox != []:
            xmin, ymin, xmax, ymax = bbox
            params['inSR'] = '4326'
            params['geometryType'] = 'esriGeometryEnvelope'
            params['geometry'] = f'{xmin},{ymin},{xmax},{ymax}'

        fc = {
            'type': 'FeatureCollection',
            'features': [],
        }

        if self.count or resulttype == 'hits':
            matched = self._get_count(params)
            LOGGER.debug(f'Found {matched} result(s)')
            fc['numberMatched'] = matched

        if resulttype == 'hits':
            return fc

        params['orderByFields'] = self._make_orderby(sortby)

        params['returnGeometry'] = 'false' if skip_geometry else 'true'
        params['resultOffset'] = offset
        params['resultRecordCount'] = limit

        hits_ = min(limit, matched) if self.count else limit
        fc['features'] = self._get_all(params, hits_)

        fc['numberReturned'] = len(fc['features'])

        return fc

    def get(self, identifier, crs_transform_spec=None, **kwargs):
        """
        Query ESRI by id

        :param identifier: feature id
        :param crs_transform_spec: `CrsTransformSpec` instance, optional

        :returns: dict of single GeoJSON feature
        """

        LOGGER.debug(f'Fetching item: {identifier}')
        params = {
            'f': 'geoJSON',
            'outSR': self._get_srid(crs_transform_spec),
            'outFields': self._make_fields()
        }

        if self.using_deafult_id:
            params['objectIds'] = identifier
        else:
            params['where'] = self._make_where(
                [(self.id_field, identifier)]
            )

        LOGGER.debug('Returning item')
        [feature] = self._make_features(
            self.get_response(params=params)
        )

        return feature

    def login(self):
        """
        Generate login token from username and password
        """
        if self.token is None:

            if None in [self.username, self.password]:
                msg = 'Missing ESRI login information, not setting token'
                LOGGER.debug(msg)
                return
            params = {
                'f': 'pjson',
                'username': self.username,
                'password': self.password,
                'referer': self.token_referer
            }

            LOGGER.debug('Logging in')
            with self.session.post(self.token_url, data=params) as r:
                self.token = r.json().get('token')
                # https://enterprise.arcgis.com/en/server/latest/administer/windows/about-arcgis-tokens.htm
                self.session.headers.update({
                    'X-Esri-Authorization': f'Bearer {self.token}'
                })

    def get_response(self, url: str = None, **kwargs):
        """
        Get response from ESRI service

        :param url: `str` of ESRI service URL if not using default

        :returns: `dict` of ESRI response
        """
        if url is None:
            url = self.url

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

    def _make_where(self, properties=[], datetime_=None, filterq=None):
        """
        Make ESRI filter from query properties

        :param properties: `list` of tuples (name, value)
        :param datetime_: `str` temporal (datestamp or extent)
        :param filterq: CQL2 filter expression (`pygeofilter.ast.Node`)

        :returns: ESRI query `where` clause
        """

        if properties == [] and datetime_ is None and filterq is None:
            return '1 = 1'

        p = []

        if properties:
            for (k, v) in properties:
                p.append(f'{k} = {self.sanitize_attribute_value(v)}')

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

        if filterq is not None:
            p.append(self._cql2_to_sql(filterq))

        return ' AND '.join(p)

    # CQL2 spatial predicate -> ESRI spatialRel mapping
    _SPATIAL_REL = {
        'GeometryIntersects': 'esriSpatialRelIntersects',
        'GeometryWithin': 'esriSpatialRelWithin',
        'GeometryContains': 'esriSpatialRelContains',
        'GeometryCrosses': 'esriSpatialRelCrosses',
        'GeometryTouches': 'esriSpatialRelTouches',
        'GeometryOverlaps': 'esriSpatialRelOverlaps',
    }

    # GeoJSON geometry type -> ESRI geometryType
    _GEOMETRY_TYPE = {
        'Point': 'esriGeometryPoint',
        'MultiPoint': 'esriGeometryMultipoint',
        'LineString': 'esriGeometryPolyline',
        'MultiLineString': 'esriGeometryPolyline',
        'Polygon': 'esriGeometryPolygon',
        'MultiPolygon': 'esriGeometryPolygon',
    }

    def _extract_spatial(self, filterq):
        """
        Extract a single top-level spatial predicate from a CQL2 filter.

        At most one spatial predicate is supported, either standalone or
        combined with attribute/temporal expressions via a top-level AND.
        Spatial predicates nested under OR/NOT, multiple spatial predicates,
        or unsupported spatial operators (e.g. S_DISJOINT) raise
        `ProviderInvalidQueryError`.

        :param filterq: CQL2 filter expression (`pygeofilter.ast.Node`)

        :returns: `tuple` of (spatial node or None, residual filter or None)
        """
        if filterq is None:
            return None, None

        from pygeofilter import ast

        def count_spatial(node):
            if node is None:
                return 0
            if self._is_spatial(node):
                return 1
            total = 0
            for attr in ('lhs', 'rhs', 'sub_node'):
                child = getattr(node, attr, None)
                if isinstance(child, ast.Node):
                    total += count_spatial(child)
            return total

        total_spatial = count_spatial(filterq)

        if total_spatial == 0:
            return None, filterq

        if total_spatial > 1:
            msg = 'Only a single spatial predicate is supported'
            LOGGER.error(msg)
            raise ProviderInvalidQueryError(msg)

        # Exactly one spatial predicate
        # optionally combined with attributes via a top-level AND chain.
        if self._is_spatial(filterq):
            return filterq, None

        if isinstance(filterq, ast.And):
            if self._is_spatial(filterq.lhs):
                return filterq.lhs, filterq.rhs
            if self._is_spatial(filterq.rhs):
                return filterq.rhs, filterq.lhs
            # spatial nested deeper on one side
            left, l_res = self._extract_spatial(filterq.lhs)
            if left is not None:
                residual = (ast.And(l_res, filterq.rhs) if l_res
                            else filterq.rhs)
                return left, residual
            right, r_res = self._extract_spatial(filterq.rhs)
            if right is not None:
                residual = (ast.And(filterq.lhs, r_res) if r_res
                            else filterq.lhs)
                return right, residual

        msg = ('Spatial predicates may only be combined with attribute '
               'filters using AND')
        LOGGER.error(msg)
        raise ProviderInvalidQueryError(msg)

    @staticmethod
    def _is_spatial(node):
        """
        Check whether a node is a spatial predicate.

        :param node: `pygeofilter.ast.Node`

        :returns: `bool`
        """
        from pygeofilter import ast

        spatial_types = (
            ast.GeometryIntersects, ast.GeometryWithin, ast.GeometryContains,
            ast.GeometryCrosses, ast.GeometryTouches, ast.GeometryOverlaps,
            ast.GeometryDisjoint, ast.BBox
        )
        return isinstance(node, spatial_types)

    def _spatial_to_params(self, node):
        """
        Translate a CQL2 spatial predicate into ESRI query parameters.

        :param node: spatial `pygeofilter.ast.Node`

        :returns: `dict` of ESRI geometry query parameters
        """
        from pygeofilter import ast

        if isinstance(node, ast.BBox):
            return {
                'inSR': '4326',
                'geometryType': 'esriGeometryEnvelope',
                'geometry': f'{node.minx},{node.miny},{node.maxx},{node.maxy}',
                'spatialRel': 'esriSpatialRelIntersects'
            }

        node_type = type(node).__name__

        if isinstance(node, ast.GeometryDisjoint):
            msg = 'S_DISJOINT is not supported by the ESRI provider'
            LOGGER.error(msg)
            raise ProviderInvalidQueryError(msg)

        spatial_rel = self._SPATIAL_REL.get(node_type)
        if spatial_rel is None:
            msg = f'Unsupported spatial predicate: {node_type}'
            LOGGER.error(msg)
            raise ProviderInvalidQueryError(msg)

        geojson = node.rhs.geometry
        esri_geom = self._geojson_to_esri(geojson)

        return {
            'inSR': '4326',
            'geometryType': self._GEOMETRY_TYPE[geojson['type']],
            'geometry': json.dumps(esri_geom),
            'spatialRel': spatial_rel
        }

    @staticmethod
    def _geojson_to_esri(geojson):
        """
        Convert a GeoJSON geometry into an ESRI JSON geometry.

        :param geojson: `dict` GeoJSON geometry

        :returns: `dict` ESRI JSON geometry
        """
        gtype = geojson['type']
        coords = geojson['coordinates']
        sr = {'wkid': 4326}

        if gtype == 'Point':
            return {'x': coords[0], 'y': coords[1], 'spatialReference': sr}
        if gtype == 'MultiPoint':
            return {'points': [list(c) for c in coords],
                    'spatialReference': sr}
        if gtype == 'LineString':
            return {'paths': [[list(c) for c in coords]],
                    'spatialReference': sr}
        if gtype == 'MultiLineString':
            return {'paths': [[list(c) for c in line] for line in coords],
                    'spatialReference': sr}
        if gtype == 'Polygon':
            return {'rings': [[list(c) for c in ring] for ring in coords],
                    'spatialReference': sr}
        if gtype == 'MultiPolygon':
            rings = []
            for polygon in coords:
                for ring in polygon:
                    rings.append([list(c) for c in ring])
            return {'rings': rings, 'spatialReference': sr}

        msg = f'Unsupported geometry type: {gtype}'
        LOGGER.error(msg)
        raise ProviderInvalidQueryError(msg)

    def _cql2_to_sql(self, node):
        """
        Translate a CQL2 (pygeofilter) AST into an ESRI SQL `where` clause.

        Supported: logical (AND/OR/NOT), comparisons
        (=, <>, <, <=, >, >=), LIKE, IN, BETWEEN, IS NULL.
        Spatial and temporal predicates are not supported and raise
        `ProviderQueryError`.

        :param node: `pygeofilter.ast.Node` (or literal value)

        :returns: `str` ESRI SQL `where` fragment
        """
        from pygeofilter import ast

        # Logical combinations
        if isinstance(node, ast.And):
            return (f'({self._cql2_to_sql(node.lhs)} AND '
                    f'{self._cql2_to_sql(node.rhs)})')
        if isinstance(node, ast.Or):
            return (f'({self._cql2_to_sql(node.lhs)} OR '
                    f'{self._cql2_to_sql(node.rhs)})')
        if isinstance(node, ast.Not):
            return f'(NOT {self._cql2_to_sql(node.sub_node)})'

        # Binary comparisons
        comparisons = {
            ast.Equal: '=', ast.NotEqual: '<>',
            ast.LessThan: '<', ast.LessEqual: '<=',
            ast.GreaterThan: '>', ast.GreaterEqual: '>='
        }
        for cls, op in comparisons.items():
            if isinstance(node, cls):
                return (f'{self._cql2_operand(node.lhs)} {op} '
                        f'{self._cql2_operand(node.rhs)}')

        # LIKE
        if isinstance(node, ast.Like):
            field = self._cql2_operand(node.lhs)
            pattern = str(node.pattern).replace("'", "''")
            if node.nocase:
                clause = f"UPPER({field}) LIKE UPPER('{pattern}')"
            else:
                clause = f"{field} LIKE '{pattern}'"
            return f'(NOT {clause})' if node.not_ else clause

        # IN
        if isinstance(node, ast.In):
            field = self._cql2_operand(node.lhs)
            values = ', '.join(
                self._cql2_operand(v) for v in node.sub_nodes)
            op = 'NOT IN' if node.not_ else 'IN'
            return f'{field} {op} ({values})'

        # BETWEEN
        if isinstance(node, ast.Between):
            field = self._cql2_operand(node.lhs)
            low = self._cql2_operand(node.low)
            high = self._cql2_operand(node.high)
            op = 'NOT BETWEEN' if node.not_ else 'BETWEEN'
            return f'{field} {op} {low} AND {high}'

        # IS NULL
        if isinstance(node, ast.IsNull):
            field = self._cql2_operand(node.lhs)
            op = 'IS NOT NULL' if node.not_ else 'IS NULL'
            return f'{field} {op}'

        # Temporal predicates (T_BEFORE, T_AFTER, T_DURING, T_EQUALS)
        if isinstance(node, ast.TimeBefore):
            return (f'{self._cql2_operand(node.lhs)} < '
                    f'{self._cql2_temporal(node.rhs)}')
        if isinstance(node, ast.TimeAfter):
            return (f'{self._cql2_operand(node.lhs)} > '
                    f'{self._cql2_temporal(node.rhs)}')
        if isinstance(node, ast.TimeEquals):
            return (f'{self._cql2_operand(node.lhs)} = '
                    f'{self._cql2_temporal(node.rhs)}')
        if isinstance(node, ast.TimeDuring):
            field = self._cql2_operand(node.lhs)
            start, end = self._cql2_interval(node.rhs)
            return f'{field} BETWEEN {start} AND {end}'

        msg = (f'Unsupported CQL2 expression for ESRI provider: '
               f'{type(node).__name__}')
        LOGGER.error(msg)
        raise ProviderInvalidQueryError(msg)

    def _cql2_operand(self, node):
        """
        Translate a CQL2 operand (attribute or literal) into ESRI SQL.

        :param node: `pygeofilter.ast.Attribute` or literal value

        :returns: `str` ESRI SQL operand
        """
        from pygeofilter import ast

        if isinstance(node, ast.Attribute):
            name = node.name
            if self._fields and name not in self._fields:
                msg = f'Invalid property name: {name}'
                LOGGER.error(msg)
                raise ProviderInvalidQueryError(msg)
            return name

        if isinstance(node, ast.Node):
            msg = (f'Unsupported CQL2 operand for ESRI provider: '
                   f'{type(node).__name__}')
            LOGGER.error(msg)
            raise ProviderInvalidQueryError(msg)

        if node is None:
            return 'NULL'
        if isinstance(node, bool):
            return '1' if node else '0'
        if isinstance(node, (int, float)):
            return str(node)
        if isinstance(node, (date, datetime)):
            return self._cql2_temporal(node)

        return "'" + str(node).replace("'", "''") + "'"

    @staticmethod
    def _cql2_temporal(value):
        """
        Format a date/datetime literal as an ESRI TIMESTAMP operand.

        :param value: `datetime.date` or `datetime.datetime`

        :returns: `str` ESRI TIMESTAMP literal
        """
        if isinstance(value, datetime):
            dt_ = value.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(value, date):
            dt_ = value.strftime('%Y-%m-%d 00:00:00')
        else:
            raise ProviderInvalidQueryError(
                f'Invalid temporal literal: {value!r}')
        return f"TIMESTAMP '{dt_}'"

    def _cql2_interval(self, value):
        """
        Translate a CQL2 interval into (start, end) ESRI TIMESTAMP operands.

        :param value: `pygeofilter.values.Interval`

        :returns: `tuple` of ESRI TIMESTAMP literals
        """
        from pygeofilter import values

        if not isinstance(value, values.Interval):
            msg = f'Invalid temporal interval: {value!r}'
            LOGGER.error(msg)
            raise ProviderInvalidQueryError(msg)

        return (self._cql2_temporal(value.start),
                self._cql2_temporal(value.end))

    def _get_count(self, params):
        """
        Count number of features from query args

        :param params: `dict` of query params

        :returns: `int` of feature count
        """
        params = deepcopy(params)

        params['returnCountOnly'] = 'true'
        params['f'] = 'pjson'

        response = self.get_response(params=params)
        return response.get('count', 0)

    def _get_srid(self, crs_transform_spec):
        """
        Get SRID from CrsTransformSpec

        :param crs_transform_spec: `CrsTransformSpec` instance

        :returns: `int` of SRID
        """
        if crs_transform_spec is not None:
            return get_srid(crs_transform_spec.target_crs)

        return self.srid

    def _get_all(self, params, hits_):
        """
        Get all features from query args

        :param properties: `dict` of query params
        :param hits_: `int` of number of features to expect

        :returns: `list` of features
        """
        params = deepcopy(params)

        # Return feature collection
        features = self._make_features(
            self.get_response(params=params)
        )
        step = len(features)

        # Query if values are less than expected
        while len(features) < hits_:
            LOGGER.debug('Fetching next set of values')
            params['resultOffset'] += step
            params['resultRecordCount'] += step

            fs = self._make_features(
                self.get_response(params=params)
            )
            if len(fs) != 0:
                features.extend(fs)
            else:
                break

        return features

    def _make_features(self, feature_collection: dict = {}):
        """
        Make a feature from features list

        :param features: `dict` of features

        :returns: `dict` of single feature
        """
        features = feature_collection.get('features', [])

        for feature in features:
            if not self.using_deafult_id:
                feature['id'] = \
                    feature['properties'][self.id_field]

        return features

    def __exit__(self, **kwargs):
        """
        Exit and close session
        """
        self.session.close()

    def __repr__(self):
        return f'<ESRIServiceProvider> {self.data}'
