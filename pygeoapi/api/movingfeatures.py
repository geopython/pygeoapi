# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Sander Schaminee <sander.schaminee@geocat.net>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#
# Copyright (c) 2022 Tom Kralidis
# Copyright (c) 2020 Francesco Bartoli
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
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
""" Root level code of pygeoapi, parsing content provided by web framework.
Returns content from plugins and sets responses.
"""

from copy import deepcopy
from datetime import datetime
from functools import partial
import json
import logging
import re
from typing import Any, Tuple, Union
import urllib.parse

from dateutil.parser import parse as dateparse
import pytz
from http import HTTPStatus

from pygeoapi import l10n
from pygeoapi.log import setup_logger
from pygeoapi.linked_data import (jsonldify)
from pygeoapi.plugin import PLUGINS
from pygeoapi.process.manager.base import get_manager

from pymeos import (STBox, TsTzSpan, TTextSeq, TFloatSeq,
                    TGeomPointSeq, Temporal, pymeos_initialize)
import psycopg2
from pygeoapi.provider.postgresql_mobilitydb import PostgresMobilityDB
from pygeoapi.api import (
    pre_process, gzip, APIRequest, SYSTEM_LOCALE, CHARSET,
    TEMPLATES, FORMAT_TYPES, F_JSON, F_HTML, F_GZIP)
from pygeoapi.util import (
    UrlPrefetcher, get_api_rules, get_base_url, render_j2_template,
    to_json)
LOGGER = logging.getLogger(__name__)


class MOVING_FEATURES:
    def __init__(self, config, openapi):
        """
        constructor

        :param config: configuration dict
        :param openapi: openapi dict

        :returns: `pygeoapi.API` instance
        """

        self.config = config
        self.openapi = openapi
        self.api_headers = get_api_rules(self.config).response_headers
        self.base_url = get_base_url(self.config)
        self.prefetcher = UrlPrefetcher()

        CHARSET[0] = config['server'].get('encoding', 'utf-8')
        if config['server'].get('gzip'):
            FORMAT_TYPES[F_GZIP] = 'application/gzip'
            FORMAT_TYPES.move_to_end(F_JSON)

        # Process language settings (first locale is default!)
        self.locales = l10n.get_locales(config)
        self.default_locale = self.locales[0]

        if 'templates' not in self.config['server']:
            self.config['server']['templates'] = {'path': TEMPLATES}

        if 'pretty_print' not in self.config['server']:
            self.config['server']['pretty_print'] = False

        self.pretty_print = self.config['server']['pretty_print']

        setup_logger(self.config['logging'])

        # Create config clone for HTML templating with modified base URL
        self.tpl_config = deepcopy(self.config)
        self.tpl_config['server']['url'] = self.base_url

        self.manager = get_manager(self.config)
        LOGGER.info('Process manager plugin loaded')

    @gzip
    @pre_process
    @jsonldify
    def manage_collection(self, request: Union[APIRequest, Any],
                          action, dataset=None) -> Tuple[dict, int, str]:
        """
        Adds a collection

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        headers = request.get_response_headers(SYSTEM_LOCALE)
        pmdb_provider = PostgresMobilityDB()
        collection_id = str(dataset)
        if action in ['create', 'update']:
            data = request.data
            if not data:
                # TODO not all processes require input, e.g. time-dependent or
                #      random value generators
                msg = 'missing request data'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'MissingParameterValue', msg)

            try:
                # Parse bytes data, if applicable
                data = data.decode()
                LOGGER.debug(data)
            except (UnicodeDecodeError, AttributeError):
                pass

            try:
                data = json.loads(data)
            except (json.decoder.JSONDecodeError, TypeError) as err:
                # Input does not appear to be valid JSON
                LOGGER.error(err)
                msg = 'invalid request data'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)

        if action == 'create':
            try:
                pmdb_provider.connect()
                collection_id = pmdb_provider.post_collection(data)
            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pmdb_provider.disconnect()

            url = '{}/{}'.format(self.get_collections_url(), collection_id)

            headers['Location'] = url
            return headers, HTTPStatus.CREATED, ''

        if action == 'update':
            LOGGER.debug('Updating item')
            try:
                pmdb_provider.connect()
                pmdb_provider.put_collection(collection_id, data)
            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pmdb_provider.disconnect()

            return headers, HTTPStatus.NO_CONTENT, ''

        if action == 'delete':
            LOGGER.debug('Deleting item')
            try:
                pmdb_provider.connect()
                pmdb_provider.delete_collection(
                    "AND collection_id ='{0}'".format(collection_id))

            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pmdb_provider.disconnect()

            return headers, HTTPStatus.NO_CONTENT, ''

    @gzip
    @pre_process
    @jsonldify
    def get_collection(self, request: Union[APIRequest, Any],
                       dataset=None) -> Tuple[dict, int, str]:
        """
        Queries collection

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """
        pmdb_provider = PostgresMobilityDB()
        collection_id = str(dataset)
        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        try:
            pmdb_provider.connect()
            result = pmdb_provider.get_collection(collection_id)
            if len(result) > 0:
                row = result[0]
            else:
                msg = 'Collection not found'
                LOGGER.error(msg)
                return self.get_exception(
                    HTTPStatus.NOT_FOUND,
                    headers, request.format, 'NotFound', msg)
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        collection = {}
        if row is not None:
            collection_id = row[0]
            collection = row[1]
            collection['itemType'] = 'movingfeature'
            collection['id'] = collection_id

            crs = None
            trs = None
            if 'crs' in collection:
                crs = collection.pop('crs', None)
            if 'trs' in collection:
                trs = collection.pop('trs', None)

            extend_stbox = STBox(row[3]) if row[3] is not None else None
            lifespan = TsTzSpan(row[2]) if row[2] is not None else None

            bbox = []
            if extend_stbox is not None:
                bbox.append(extend_stbox.xmin())
                bbox.append(extend_stbox.ymin())
                if extend_stbox.zmin() is not None:
                    bbox.append(extend_stbox.zmin())
                bbox.append(extend_stbox.xmax())
                bbox.append(extend_stbox.ymax())
                if extend_stbox.zmax() is not None:
                    bbox.append(extend_stbox.zmax())

                if crs is None:
                    if extend_stbox.srid() == 4326:
                        if extend_stbox.zmax() is not None:
                            crs = 'http://www.opengis.net/def/crs/OGC/0/CRS84h'
                        else:
                            crs = 'http://www.opengis.net/def/crs/\
                            OGC/1.3/CRS84'

            if crs is None:
                crs = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
            if trs is None:
                trs = 'http://www.opengis.net/def/uom/ISO-8601/0/Gregorian'

            time = []
            if lifespan is not None:
                time.append(lifespan.lower().strftime("%Y-%m-%dT%H:%M:%SZ"))
                time.append(lifespan.upper().strftime("%Y-%m-%dT%H:%M:%SZ"))
            else:
                if extend_stbox is not None:
                    if extend_stbox.tmin() is not None:
                        time.append(extend_stbox.tmin().strftime(
                            "%Y-%m-%dT%H:%M:%SZ"))
                        time.append(extend_stbox.tmax().strftime(
                            "%Y-%m-%dT%H:%M:%SZ"))

            collection['extent'] = {
                'spatial': {
                    'bbox': bbox,
                    'crs': crs
                },
                'temporal': {
                    'interval': time,
                    'trs': trs
                }
            }

            collection['links'] = []
            collection['links'].append({
                'href': '{}/{}'.format(
                    self.get_collections_url(), collection_id),
                'rel': request.get_linkrel(F_JSON),
                'type': FORMAT_TYPES[F_JSON]
            })

        return headers, HTTPStatus.OK, to_json(collection, self.pretty_print)

    @gzip
    @pre_process
    def get_collection_items(
            self, request: Union[APIRequest, Any],
            dataset) -> Tuple[dict, int, str]:
        """
        Queries collection

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        # Set Content-Language to system locale until provider locale
        # has been determined
        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers(SYSTEM_LOCALE)

        excuted, collections = get_list_of_collections_id()
        collection_id = dataset
        if excuted is False:
            msg = str(collections)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        if collection_id not in collections:
            msg = 'Collection not found'
            LOGGER.error(msg)
            return self.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)
        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Processing offset parameter')
        try:
            offset = int(request.params.get('offset'))
            if offset < 0:
                msg = 'offset value should be positive or zero'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            offset = 0
        except ValueError:
            msg = 'offset value should be an integer'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing limit parameter')
        try:
            limit = int(request.params.get('limit'))
            # TODO: We should do more validation, against the min and max
            #       allowed by the server configuration
            if limit <= 0:
                msg = 'limit value should be strictly positive'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
            if limit > 10000:
                msg = 'limit value should be less than or equal to 10000'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            limit = int(self.config['server']['limit'])
        except ValueError:
            msg = 'limit value should be an integer'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing bbox parameter')

        bbox = request.params.get('bbox')

        if bbox is None:
            bbox = []
        else:
            try:
                bbox = validate_bbox(bbox)
            except ValueError as err:
                msg = str(err)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing datetime parameter')
        datetime_ = request.params.get('datetime')
        try:
            datetime_ = validate_datetime(datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        sub_trajectory = request.params.get('subTrajectory')
        if sub_trajectory is None:
            sub_trajectory = False

        LOGGER.debug('Querying provider')
        LOGGER.debug('offset: {}'.format(offset))
        LOGGER.debug('limit: {}'.format(limit))
        LOGGER.debug('bbox: {}'.format(bbox))
        LOGGER.debug('datetime: {}'.format(datetime_))

        pmdb_provider = PostgresMobilityDB()
        content = {
            "type": "FeatureCollection",
            "features": [],
            "crs": {},
            "trs": {},
            "links": []
        }

        try:
            pmdb_provider.connect()
            result, number_matched, number_returned = \
                pmdb_provider.get_features(collection_id=collection_id,
                                           bbox=bbox, datetime=datetime_,
                                           limit=limit, offset=offset,
                                           sub_trajectory=sub_trajectory)
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        mfeatures = []
        crs = None
        trs = None

        split_mfeature = {}
        for i in range(len(result)):
            mfeature_id = str(result[i][1])
            if mfeature_id not in split_mfeature:
                split_mfeature[mfeature_id] = []
            split_mfeature[mfeature_id].append(i)

        pymeos_initialize()
        for key, mfeature_row_index in split_mfeature.items():
            row = result[mfeature_row_index[0]]

            mfeature_id = row[1]
            mfeature = row[3]
            mfeature['id'] = mfeature_id
            mfeature['type'] = 'Feature'

            if 'crs' in mfeature and crs is None:
                crs = mfeature['crs']
            if 'trs' in mfeature and trs is None:
                trs = mfeature['trs']

            if row[2] is not None:
                mfeature['geometry'] = json.loads(row[2])
            else:
                mfeature['geometry'] = None

            if 'properties' not in mfeature:
                mfeature['properties'] = None

            if sub_trajectory or sub_trajectory == "true":
                prisms = []
                for row_index in mfeature_row_index:
                    row_tgeometory = result[int(row_index)]
                    if row_tgeometory[7] is not None:
                        mfeature_check = row_tgeometory[1]
                        if mfeature_check == mfeature_id:
                            temporal_geometry = json.loads(
                                Temporal.as_mfjson(
                                    TGeomPointSeq(
                                        str(row_tgeometory[7]).replace(
                                            "'", "")),
                                    False))
                            if 'crs' in temporal_geometry and crs is None:
                                crs = temporal_geometry['crs']
                            if 'trs' in temporal_geometry and trs is None:
                                trs = temporal_geometry['trs']
                            temporal_geometry = \
                                pmdb_provider.\
                                convert_temporalgeometry_to_old_version(
                                    temporal_geometry)
                            temporal_geometry['id'] = row_tgeometory[6]
                            prisms.append(temporal_geometry)
                mfeature['temporalGeometry'] = prisms

            extend_stbox = STBox(row[5]) if row[5] is not None else None
            lifespan = TsTzSpan(row[4]) if row[4] is not None else None

            bbox = []
            if extend_stbox is not None:
                bbox.append(extend_stbox.xmin())
                bbox.append(extend_stbox.ymin())
                if extend_stbox.zmin() is not None:
                    bbox.append(extend_stbox.zmin())
                bbox.append(extend_stbox.xmax())
                bbox.append(extend_stbox.ymax())
                if extend_stbox.zmax() is not None:
                    bbox.append(extend_stbox.zmax())
            mfeature['bbox'] = bbox

            time = []
            if lifespan is not None:
                time.append(lifespan.lower().strftime("%Y-%m-%dT%H:%M:%SZ"))
                time.append(lifespan.upper().strftime("%Y-%m-%dT%H:%M:%SZ"))
            else:
                if extend_stbox is not None:
                    if extend_stbox.tmin() is not None:
                        time.append(extend_stbox.tmin().strftime(
                            "%Y-%m-%dT%H:%M:%SZ"))
                        time.append(extend_stbox.tmax().strftime(
                            "%Y-%m-%dT%H:%M:%SZ"))
            mfeature['time'] = time

            if 'crs' not in mfeature:
                mfeature['crs'] = {
                    "type": "Name",
                    "properties": "urn:ogc:def:crs:OGC:1.3:CRS84"
                }
            if 'trs' not in mfeature:
                mfeature['trs'] = {
                    "type": "Name",
                    "properties": "urn:ogc:data:time:iso8601"
                }
            mfeatures.append(mfeature)

        content['features'] = mfeatures
        if crs is not None:
            content['crs'] = crs
        else:
            content['crs'] = {
                "type": "Name",
                "properties": "urn:ogc:def:crs:OGC:1.3:CRS84"
            }

        if trs is not None:
            content['trs'] = trs
        else:
            content['trs'] = {
                "type": "Name",
                "properties": "urn:ogc:data:time:iso8601"
            }

        # TODO: translate titles
        uri = '{}/{}/items'.format(self.get_collections_url(), collection_id)

        serialized_query_params = ''
        for k, v in request.params.items():
            if k not in ('f', 'offset'):
                serialized_query_params += '&'
                serialized_query_params += urllib.parse.quote(k, safe='')
                serialized_query_params += '='
                serialized_query_params += urllib.parse.quote(str(v), safe=',')

        content['links'] = [
            {'href': '{}?offset={}{}'.format(
                uri, offset, serialized_query_params),
             'rel': request.get_linkrel(F_JSON),
             'type': FORMAT_TYPES[F_JSON]}]

        if len(content['features']) == limit:
            next_ = offset + limit
            content['links'].append(
                {'href': '{}?offset={}{}'.format(
                    uri, next_, serialized_query_params),
                 'type': 'application/geo+json', 'rel': 'next'})

        content['timeStamp'] = datetime.utcnow().strftime(
            '%Y-%m-%dT%H:%M:%S.%fZ')

        content['numberMatched'] = number_matched
        content['numberReturned'] = number_returned
        return headers, HTTPStatus.OK, to_json(content, self.pretty_print)

    @gzip
    @pre_process
    def manage_collection_item(
            self, request: Union[APIRequest, Any],
            action, dataset, identifier=None) -> Tuple[dict, int, str]:
        """
        Adds an item to a collection

        :param request: A request object
        :param dataset: dataset name

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid(PLUGINS['formatter'].keys()):
            return self.get_format_exception(request)

        # Set Content-Language to system locale until provider locale
        # has been determined
        headers = request.get_response_headers(SYSTEM_LOCALE)

        pmdb_provider = PostgresMobilityDB()
        excuted, collections = get_list_of_collections_id()

        if excuted is False:
            msg = str(collections)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        if dataset not in collections:
            msg = 'Collection not found'
            LOGGER.error(msg)
            return self.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)

        collection_id = dataset
        mfeature_id = identifier
        if action == 'create':
            if not request.data:
                msg = 'No data found'
                LOGGER.error(msg)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)

            data = request.data
            try:
                # Parse bytes data, if applicable
                data = data.decode()
                LOGGER.debug(data)
            except (UnicodeDecodeError, AttributeError):
                pass

            try:
                data = json.loads(data)
            except (json.decoder.JSONDecodeError, TypeError) as err:
                # Input does not appear to be valid JSON
                LOGGER.error(err)
                msg = 'invalid request data'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)

            if check_required_field_feature(data) is False:
                # TODO not all processes require input
                msg = 'The required tag (e.g., type,temporalgeometry) \
                    is missing from the request data.'
                return self.get_exception(
                    HTTPStatus.NOT_IMPLEMENTED,
                    headers, request.format, 'MissingParameterValue', msg)

            LOGGER.debug('Creating item')
            try:
                pmdb_provider.connect()
                if data['type'] == 'FeatureCollection':
                    for feature in data['features']:
                        if check_required_field_feature(feature) is False:
                            # TODO not all processes require input
                            msg = 'The required tag \
                                (e.g., type,temporalgeometry) \
                                is missing from the request data.'
                            return self.get_exception(
                                HTTPStatus.NOT_IMPLEMENTED,
                                headers, request.format,
                                'MissingParameterValue', msg)
                        mfeature_id = pmdb_provider.post_movingfeature(
                            collection_id, feature)
                else:
                    mfeature_id = pmdb_provider.post_movingfeature(
                        collection_id, data)
            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pmdb_provider.disconnect()

            headers['Location'] = '{}/{}/items/{}'.format(
                self.get_collections_url(), dataset, mfeature_id)

            return headers, HTTPStatus.CREATED, ''

        if action == 'delete':
            LOGGER.debug('Deleting item')

            try:
                pmdb_provider.connect()
                pmdb_provider.delete_movingfeature(
                    "AND mfeature_id ='{0}'".format(mfeature_id))

            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pmdb_provider.disconnect()

            return headers, HTTPStatus.NO_CONTENT, ''

    @gzip
    @pre_process
    def get_collection_item(self, request: Union[APIRequest, Any],
                            dataset, identifier) -> Tuple[dict, int, str]:
        """
        Get a single collection item

        :param request: A request object
        :param dataset: dataset name
        :param identifier: item identifier

        :returns: tuple of headers, status code, content
        """

        pmdb_provider = PostgresMobilityDB()
        collection_id = str(dataset)
        mfeature_id = str(identifier)
        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers()

        try:
            pmdb_provider.connect()
            result = pmdb_provider.get_feature(collection_id, mfeature_id)
            if len(result) > 0:
                row = result[0]
            else:
                msg = 'Feature not found'
                LOGGER.error(msg)
                return self.get_exception(
                    HTTPStatus.NOT_FOUND,
                    headers, request.format, 'NotFound', msg)
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        mfeature = {}
        if row is not None:
            mfeature_id = row[1]
            mfeature = row[3]
            mfeature['id'] = mfeature_id
            mfeature['type'] = 'Feature'

            if row[2] is not None:
                mfeature['geometry'] = json.loads(row[2])

            extend_stbox = STBox(row[5]) if row[5] is not None else None
            lifespan = TsTzSpan(row[4]) if row[4] is not None else None

            bbox = []
            if extend_stbox is not None:
                bbox.append(extend_stbox.xmin())
                bbox.append(extend_stbox.ymin())
                if extend_stbox.zmin() is not None:
                    bbox.append(extend_stbox.zmin())
                bbox.append(extend_stbox.xmax())
                bbox.append(extend_stbox.ymax())
                if extend_stbox.zmax() is not None:
                    bbox.append(extend_stbox.zmax())
            mfeature['bbox'] = bbox

            print(lifespan)
            time = []
            if lifespan is not None:
                time.append(lifespan.lower().strftime("%Y-%m-%dT%H:%M:%SZ"))
                time.append(lifespan.upper().strftime("%Y-%m-%dT%H:%M:%SZ"))
            else:
                if extend_stbox is not None:
                    if extend_stbox.tmin() is not None:
                        time.append(extend_stbox.tmin().strftime(
                            "%Y-%m-%dT%H:%M:%SZ"))
                        time.append(extend_stbox.tmax().strftime(
                            "%Y-%m-%dT%H:%M:%SZ"))
            mfeature['time'] = time

            if 'crs' not in mfeature:
                mfeature['crs'] = {
                    "type": "Name",
                    "properties": "urn:ogc:def:crs:OGC:1.3:CRS84"
                }
            if 'trs' not in mfeature:
                mfeature['trs'] = {
                    "type": "Name",
                    "properties": "urn:ogc:data:time:iso8601"
                }
            mfeature['links'] = []
            mfeature['links'].append({
                'href': '{}/{}/items/{}'.format(
                    self.get_collections_url(), collection_id, mfeature_id),
                'rel': request.get_linkrel(F_JSON),
                'type': FORMAT_TYPES[F_JSON]
            })
        return headers, HTTPStatus.OK, to_json(mfeature, self.pretty_print)

    @gzip
    @pre_process
    def get_collection_items_tGeometry(self,
                                       request: Union[APIRequest, Any],
                                       dataset, identifier) \
            -> Tuple[dict, int, str]:
        """
        Get temporal Geometry of collection item

        :param request: A request object
        :param dataset: dataset name
        :param identifier: item identifier

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers(SYSTEM_LOCALE)

        excuted, feature_list = get_list_of_features_id()
        if excuted is False:
            msg = str(feature_list)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        if [dataset, identifier] not in feature_list:
            msg = 'Feature not found'
            LOGGER.error(msg)
            return self.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)

        collection_id = dataset
        mfeature_id = identifier
        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Processing offset parameter')
        try:
            offset = int(request.params.get('offset'))
            if offset < 0:
                msg = 'offset value should be positive or zero'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            offset = 0
        except ValueError:
            msg = 'offset value should be an integer'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing limit parameter')
        try:
            limit = int(request.params.get('limit'))
            # TODO: We should do more validation, against the min and max
            #       allowed by the server configuration
            if limit <= 0:
                msg = 'limit value should be strictly positive'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
            if limit > 10000:
                msg = 'limit value should be less than or equal to 10000'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            limit = int(self.config['server']['limit'])
        except ValueError:
            msg = 'limit value should be an integer'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing bbox parameter')

        bbox = request.params.get('bbox')

        if bbox is None:
            bbox = []
        else:
            try:
                bbox = validate_bbox(bbox)
            except ValueError as err:
                msg = str(err)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)

        leaf_ = request.params.get('leaf')
        LOGGER.debug('Processing leaf parameter')
        try:
            leaf_ = validate_leaf(leaf_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        sub_trajectory = request.params.get('subTrajectory')
        if sub_trajectory is None:
            sub_trajectory = False

        if (leaf_ != '' and leaf_ is not None) \
                and (sub_trajectory or sub_trajectory == 'true'):
            msg = 'Cannot use both parameter `subTrajectory` \
                and `leaf` at the same time'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing datetime parameter')
        datetime_ = request.params.get('datetime')
        try:
            datetime_ = validate_datetime(datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Querying provider')
        LOGGER.debug('offset: {}'.format(offset))
        LOGGER.debug('limit: {}'.format(limit))
        LOGGER.debug('bbox: {}'.format(bbox))
        LOGGER.debug('leaf: {}'.format(leaf_))
        LOGGER.debug('datetime: {}'.format(datetime_))

        pmdb_provider = PostgresMobilityDB()
        content = {
            "type": "TemporalGeometrySequence",
            "geometrySequence": [],
            "crs": {},
            "trs": {},
            "links": [],
        }

        crs = None
        trs = None
        try:
            pmdb_provider.connect()
            result, number_matched, number_returned = pmdb_provider.\
                get_temporalgeometries(collection_id=collection_id,
                                       mfeature_id=mfeature_id,
                                       bbox=bbox,
                                       leaf=leaf_,
                                       datetime=datetime_,
                                       limit=limit,
                                       offset=offset,
                                       sub_trajectory=sub_trajectory)
            pymeos_initialize()
            prisms = []
            for row in result:
                temporal_geometry = json.loads(Temporal.as_mfjson(
                    TGeomPointSeq(str(row[3]).replace("'", "")), False))
                if 'crs' in temporal_geometry and crs is None:
                    crs = temporal_geometry['crs']
                if 'trs' in temporal_geometry and trs is None:
                    trs = temporal_geometry['trs']
                temporal_geometry = pmdb_provider\
                    .convert_temporalgeometry_to_old_version(
                        temporal_geometry)
                temporal_geometry['id'] = row[2]

                if (leaf_ != '' and leaf_ is not None) or \
                        (sub_trajectory or sub_trajectory == 'true'):
                    if row[4] is not None:
                        temporal_geometry_filter = json.loads(
                            Temporal.as_mfjson(
                                TGeomPointSeq(str(row[4]).replace("'", "")),
                                False))
                        temporal_geometry['datetimes'] = \
                            temporal_geometry_filter['datetimes']
                        temporal_geometry['coordinates'] = \
                            temporal_geometry_filter['coordinates']
                    else:
                        continue
                        # temporalGeometry['datetimes'] = []
                        # temporalGeometry['coordinates'] = []
                prisms.append(temporal_geometry)
            content["geometrySequence"] = prisms
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        if crs is not None:
            content['crs'] = crs
        else:
            content['crs'] = {
                "type": "Name",
                "properties": "urn:ogc:def:crs:OGC:1.3:CRS84"
            }

        if trs is not None:
            content['trs'] = trs
        else:
            content['trs'] = {
                "type": "Name",
                "properties": "urn:ogc:data:time:iso8601"
            }

        # TODO: translate titles
        uri = '{}/{}/items/{}/tgsequence'.format(
            self.get_collections_url(), collection_id, mfeature_id)

        serialized_query_params = ''
        for k, v in request.params.items():
            if k not in ('f', 'offset'):
                serialized_query_params += '&'
                serialized_query_params += urllib.parse.quote(k, safe='')
                serialized_query_params += '='
                serialized_query_params += urllib.parse.quote(str(v), safe=',')

        content['links'] = [
            {'href': '{}?offset={}{}'.format(
                uri, offset, serialized_query_params),
             'rel': request.get_linkrel(F_JSON),
             'type': FORMAT_TYPES[F_JSON]}]

        if len(content['geometrySequence']) == limit:
            next_ = offset + limit
            content['links'].append(
                {'href': '{}?offset={}{}'.format(
                    uri, next_, serialized_query_params),
                 'type': 'application/geo+json', 'rel': 'next'})

        content['timeStamp'] = datetime.utcnow().strftime(
            '%Y-%m-%dT%H:%M:%S.%fZ')

        content['numberMatched'] = number_matched
        content['numberReturned'] = len(content["geometrySequence"])
        return headers, HTTPStatus.OK, to_json(content, self.pretty_print)

    @gzip
    @pre_process
    def manage_collection_item_tGeometry(
            self, request: Union[APIRequest, Any],
            action, dataset, identifier,
            tGeometry=None) -> Tuple[dict, int, str]:
        """
        Adds Temporal Geometry item to a moving feature

        :param request: A request object
        :param dataset: dataset name
        :param identifier: moving feature's id
        :param tGeometry: Temporal Geometry's id

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid(PLUGINS['formatter'].keys()):
            return self.get_format_exception(request)

        # Set Content-Language to system locale until provider locale
        # has been determined
        headers = request.get_response_headers(SYSTEM_LOCALE)

        pmdb_provider = PostgresMobilityDB()
        excuted, feature_list = get_list_of_features_id()

        if excuted is False:
            msg = str(feature_list)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        if [dataset, identifier] not in feature_list:
            msg = 'Feature not found'
            LOGGER.error(msg)
            return self.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)

        collection_id = dataset
        mfeature_id = identifier
        tGeometry_id = tGeometry
        if action == 'create':
            if not request.data:
                msg = 'No data found'
                LOGGER.error(msg)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)

            data = request.data
            try:
                # Parse bytes data, if applicable
                data = data.decode()
                LOGGER.debug(data)
            except (UnicodeDecodeError, AttributeError):
                pass

            try:
                data = json.loads(data)
            except (json.decoder.JSONDecodeError, TypeError) as err:
                # Input does not appear to be valid JSON
                LOGGER.error(err)
                msg = 'invalid request data'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)

            if check_required_field_temporal_geometries(data) is False:
                # TODO not all processes require input
                msg = 'The required tag (e.g., type,prisms) \
                    is missing from the request data.'
                return self.get_exception(
                    HTTPStatus.NOT_IMPLEMENTED,
                    headers, request.format, 'MissingParameterValue', msg)

            LOGGER.debug('Creating item')
            try:
                pmdb_provider.connect()
                if data['type'] == 'MovingGeometryCollection':
                    for tGeometry in data['prisms']:
                        tGeometry_id = pmdb_provider.\
                            post_temporalgeometry(
                                collection_id, mfeature_id, tGeometry)

                else:
                    tGeometry_id = pmdb_provider.post_temporalgeometry(
                        collection_id, mfeature_id, data)
            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pmdb_provider.disconnect()

            headers['Location'] = '{}/{}/items/{}/tgsequence/{}'.format(
                self.get_collections_url(), dataset, mfeature_id, tGeometry_id)

            return headers, HTTPStatus.CREATED, ''

        if action == 'delete':
            LOGGER.debug('Deleting item')

            try:
                pmdb_provider.connect()
                pmdb_provider.delete_temporalgeometry(
                    "AND tgeometry_id ='{0}'".format(tGeometry_id))

            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pmdb_provider.disconnect()

            return headers, HTTPStatus.NO_CONTENT, ''

    @gzip
    @pre_process
    def get_collection_items_tGeometry_velocity(self,
                                                request:
                                                Union[APIRequest, Any],
                                                dataset, identifier,
                                                tGeometry) \
            -> Tuple[dict, int, str]:

        headers = request.get_response_headers(SYSTEM_LOCALE)
        datetime_ = request.params.get('date-time')
        collection_id = dataset
        mfeature_id = identifier
        tgeometry_id = tGeometry
        pmdb_provider = PostgresMobilityDB()
        try:
            datetime_ = validate_datetime(datetime_, return_type=False)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
        try:
            pmdb_provider.connect()
            print(datetime_)
            content = pmdb_provider.get_velocity(
                collection_id, mfeature_id, tgeometry_id, datetime_)
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                headers, request.format, 'Server Internal Error', msg)
        finally:
            pmdb_provider.disconnect()

        return headers, HTTPStatus.OK, content

    @gzip
    @pre_process
    def get_collection_items_tGeometry_distance(self,
                                                request:
                                                Union[APIRequest, Any],
                                                dataset, identifier,
                                                tGeometry) \
            -> Tuple[dict, int, str]:

        headers = request.get_response_headers(SYSTEM_LOCALE)
        datetime_ = request.params.get('date-time')
        collection_id = str(dataset)
        mfeature_id = str(identifier)
        tgeometry_id = str(tGeometry)
        pmdb_provider = PostgresMobilityDB()
        try:
            datetime_ = validate_datetime(datetime_, return_type=False)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
        try:
            pmdb_provider.connect()
            content = pmdb_provider.get_distance(
                collection_id, mfeature_id, tgeometry_id, datetime_)
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()

        return headers, HTTPStatus.OK, content

    @gzip
    @pre_process
    def get_collection_items_tGeometry_acceleration(self,
                                                    request:
                                                    Union[APIRequest, Any],
                                                    dataset, identifier,
                                                    tGeometry) \
        -> Tuple[dict,
                 int, str]:

        headers = request.get_response_headers(SYSTEM_LOCALE)
        datetime_ = request.params.get('date-time')
        collection_id = dataset
        mfeature_id = identifier
        tgeometry_id = tGeometry
        pmdb_provider = PostgresMobilityDB()
        try:
            datetime_ = validate_datetime(datetime_, return_type=False)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
        try:
            pmdb_provider.connect()
            content = pmdb_provider.get_acceleration(
                collection_id, mfeature_id, tgeometry_id, datetime_)
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return self.get_exception(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()

        return headers, HTTPStatus.OK, content

    @gzip
    @pre_process
    def get_collection_items_tProperty(self, request: Union[APIRequest, Any],
                                       dataset,
                                       identifier) -> Tuple[dict, int, str]:
        """
        Get temporal Properties of collection item

        :param request: A request object
        :param dataset: dataset name
        :param identifier: item identifier

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers(SYSTEM_LOCALE)

        excuted, feature_list = get_list_of_features_id()
        if excuted is False:
            msg = str(feature_list)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        if [dataset, identifier] not in feature_list:
            msg = 'Feature not found'
            LOGGER.error(msg)
            return self.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)

        collection_id = dataset
        mfeature_id = identifier
        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Processing offset parameter')
        try:
            offset = int(request.params.get('offset'))
            if offset < 0:
                msg = 'offset value should be positive or zero'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            offset = 0
        except ValueError:
            msg = 'offset value should be an integer'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing limit parameter')
        try:
            limit = int(request.params.get('limit'))
            # TODO: We should do more validation, against the min and max
            #       allowed by the server configuration
            if limit <= 0:
                msg = 'limit value should be strictly positive'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
            if limit > 10000:
                msg = 'limit value should be less than or equal to 10000'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            limit = int(self.config['server']['limit'])
        except ValueError:
            msg = 'limit value should be an integer'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing datetime parameter')
        datetime_ = request.params.get('datetime')
        try:
            datetime_ = validate_datetime(datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        sub_temporal_value = request.params.get('subTemporalValue')
        if sub_temporal_value is None:
            sub_temporal_value = False

        LOGGER.debug('Querying provider')
        LOGGER.debug('offset: {}'.format(offset))
        LOGGER.debug('limit: {}'.format(limit))
        LOGGER.debug('datetime: {}'.format(datetime_))

        pmdb_provider = PostgresMobilityDB()
        content = {
            "temporalProperties": [],
            "links": []
        }

        try:
            pmdb_provider.connect()
            result, number_matched, number_returned = pmdb_provider.\
                get_temporalproperties(collection_id=collection_id,
                                       mfeature_id=mfeature_id,
                                       datetime=datetime_,
                                       limit=limit, offset=offset,
                                       sub_temporal_value=sub_temporal_value)

            temporal_properties = []
            if sub_temporal_value is False or sub_temporal_value == "false":
                for row in result:
                    temporal_property = row[3] if row[3] is not None else {}
                    temporal_property['name'] = row[2]

                    temporal_properties.append(temporal_property)
            else:
                split_groups = {}
                for i in range(len(result)):
                    group_id = str(result[i][4])
                    if group_id not in split_groups:
                        split_groups[group_id] = []
                    split_groups[group_id].append(i)
                pymeos_initialize()
                for key, group_row_index in split_groups.items():
                    group = {}
                    group["datetimes"] = []
                    for row_index in group_row_index:
                        row = result[int(row_index)]
                        tproperties_name = row[2]
                        group[tproperties_name] \
                            = row[3] if row[3] is not None else {}
                        if row[5] is not None or row[6] is not None:
                            temporal_property_value = Temporal.as_mfjson(
                                TFloatSeq(str(row[5]).replace("'", "")),
                                False) if row[5] \
                                is not None else Temporal.as_mfjson(
                                    TTextSeq(str(row[6]).replace("'", "")),
                                    False)
                            temporal_property_value = pmdb_provider.\
                                convert_temporalproperty_value_to_base_version(
                                    json.loads(temporal_property_value))

                            if 'datetimes' in temporal_property_value:
                                group["datetimes"] = \
                                    temporal_property_value.pop(
                                    "datetimes", None)
                            group[tproperties_name].update(
                                temporal_property_value)
                    temporal_properties.append(group)
            content["temporalProperties"] = temporal_properties
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

            # TODO: translate titles
        uri = '{}/{}/items/{}/tProperties'.format(
            self.get_collections_url(), collection_id, mfeature_id)

        serialized_query_params = ''
        for k, v in request.params.items():
            if k not in ('f', 'offset'):
                serialized_query_params += '&'
                serialized_query_params += urllib.parse.quote(k, safe='')
                serialized_query_params += '='
                serialized_query_params += urllib.parse.quote(str(v), safe=',')

        content['links'] = [
            {'href': '{}?offset={}{}'.format(
                uri, offset, serialized_query_params),
             'rel': request.get_linkrel(F_JSON),
             'type': FORMAT_TYPES[F_JSON]}]

        if len(content['temporalProperties']) == limit:
            next_ = offset + limit
            content['links'].append(
                {'href': '{}?offset={}{}'.format(
                    uri, next_, serialized_query_params),
                 'type': 'application/geo+json', 'rel': 'next', })

        content['timeStamp'] = datetime.utcnow().strftime(
            '%Y-%m-%dT%H:%M:%S.%fZ')

        content['numberMatched'] = number_matched
        content['numberReturned'] = number_returned
        return headers, HTTPStatus.OK, to_json(content, self.pretty_print)

    @gzip
    @pre_process
    def manage_collection_item_tProperty(
            self, request: Union[APIRequest, Any],
            action, dataset, identifier,
            tProperty=None) -> Tuple[dict, int, str]:
        """
        Adds Temporal Property item to a moving feature

        :param request: A request object
        :param dataset: dataset name
        :param identifier: moving feature's id
        :param tProperty: Temporal Property's id

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid(PLUGINS['formatter'].keys()):
            return self.get_format_exception(request)

        # Set Content-Language to system locale until provider locale
        # has been determined
        headers = request.get_response_headers(SYSTEM_LOCALE)

        pmdb_provider = PostgresMobilityDB()
        excuted, feature_list = get_list_of_features_id()

        if excuted is False:
            msg = str(feature_list)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        if [dataset, identifier] not in feature_list:
            msg = 'Feature not found'
            LOGGER.error(msg)
            return self.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)

        collection_id = dataset
        mfeature_id = identifier
        tProperties_name = tProperty
        if action == 'create':
            if not request.data:
                msg = 'No data found'
                LOGGER.error(msg)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)

            data = request.data
            try:
                # Parse bytes data, if applicable
                data = data.decode()
                LOGGER.debug(data)
            except (UnicodeDecodeError, AttributeError):
                pass

            try:
                if not isinstance(data, list):
                    data = json.loads(data)
                else:
                    for d in data:
                        _ = json.loads(d)
            except (json.decoder.JSONDecodeError, TypeError) as err:
                # Input does not appear to be valid JSON
                LOGGER.error(err)
                msg = 'invalid request data'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)

            if check_required_field_temporal_property(data) is False:
                # TODO not all processes require input
                msg = 'The required tag (e.g., datetimes,interpolation) \
                    is missing from the request data.'
                return self.get_exception(
                    HTTPStatus.NOT_IMPLEMENTED,
                    headers, request.format, 'MissingParameterValue', msg)

            LOGGER.debug('Creating item')
            try:
                pmdb_provider.connect()
                # temporalProperties = data['temporalProperties']
                temporal_properties = data
                temporal_properties = [temporal_properties] if not isinstance(
                    temporal_properties, list) else temporal_properties

                can_post = pmdb_provider.check_temporalproperty_can_post(
                    collection_id, mfeature_id, temporal_properties)
                tProperties_name_list = []
                if can_post:
                    for temporalProperty in temporal_properties:
                        tProperties_name_list.extend(
                            pmdb_provider. post_temporalproperties(
                                collection_id, mfeature_id, temporalProperty))
                else:
                    return headers, HTTPStatus.BAD_REQUEST, ''
            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pmdb_provider.disconnect()

            location_list = []
            for tProperties_name in tProperties_name_list:
                location_list.append('{}/{}/items/{}/tProperties/{}'.format(
                    self.get_collections_url(), dataset, mfeature_id,
                    tProperties_name))
            headers['Locations'] = location_list

            return headers, HTTPStatus.CREATED, ''

        if action == 'delete':
            LOGGER.debug('Deleting item')

            try:
                pmdb_provider.connect()
                pmdb_provider.delete_temporalproperties(
                    "AND tproperties_name ='{0}'".format(tProperties_name))

            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pmdb_provider.disconnect()

            return headers, HTTPStatus.NO_CONTENT, ''

    @gzip
    @pre_process
    def get_collection_items_tProperty_value(self,
                                             request: Union[APIRequest, Any],
                                             dataset,
                                             identifier,
                                             tProperty) \
            -> Tuple[dict, int, str]:
        """
        Get temporal Properties of collection item

        :param request: A request object
        :param dataset: dataset name
        :param identifier: item identifier
        :param tProperty: Temporal Property

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid():
            return self.get_format_exception(request)
        headers = request.get_response_headers(SYSTEM_LOCALE)

        excuted, tproperty_list = get_list_of_tproperties_name()
        if excuted is False:
            msg = str(tproperty_list)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        if [dataset, identifier, tProperty] not in tproperty_list:
            msg = 'Temporal Property not found'
            LOGGER.error(msg)
            return self.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)

        collection_id = dataset
        mfeature_id = identifier
        tProperty_name = tProperty
        LOGGER.debug('Processing query parameters')

        LOGGER.debug('Processing offset parameter')
        try:
            offset = int(request.params.get('offset'))
            if offset < 0:
                msg = 'offset value should be positive or zero'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            offset = 0
        except ValueError:
            msg = 'offset value should be an integer'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing limit parameter')
        try:
            limit = int(request.params.get('limit'))
            # TODO: We should do more validation, against the min and max
            #       allowed by the server configuration
            if limit <= 0:
                msg = 'limit value should be strictly positive'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
            if limit > 10000:
                msg = 'limit value should be less than or equal to 10000'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)
        except TypeError as err:
            LOGGER.warning(err)
            limit = int(self.config['server']['limit'])
        except ValueError:
            msg = 'limit value should be an integer'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing leaf parameter')
        leaf_ = request.params.get('leaf')
        try:
            leaf_ = validate_leaf(leaf_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        sub_temporal_value = request.params.get('subTemporalValue')
        if sub_temporal_value is None:
            sub_temporal_value = False

        if (leaf_ != '' and leaf_ is not None) and \
                (sub_temporal_value or sub_temporal_value == 'true'):
            msg = 'Cannot use both parameter `subTemporalValue` \
                and `leaf` at the same time'
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Processing datetime parameter')
        datetime_ = request.params.get('datetime')
        try:
            datetime_ = validate_datetime(datetime_)
        except ValueError as err:
            msg = str(err)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        LOGGER.debug('Querying provider')
        LOGGER.debug('offset: {}'.format(offset))
        LOGGER.debug('limit: {}'.format(limit))
        LOGGER.debug('leaf: {}'.format(leaf_))
        LOGGER.debug('datetime: {}'.format(datetime_))

        pmdb_provider = PostgresMobilityDB()
        content = {}

        try:
            pmdb_provider.connect()
            result = pmdb_provider.get_temporalproperties_value(
                collection_id=collection_id, mfeature_id=mfeature_id,
                tProperty_name=tProperty_name,
                datetime=datetime_, leaf=leaf_,
                sub_temporal_value=sub_temporal_value)
            pymeos_initialize()
            value_sequence = []
            for row in result:
                content = row[3]
                if row[5] is not None or row[6] is not None:
                    temporal_property_value = Temporal.as_mfjson(
                        TFloatSeq(str(row[5]).replace("'", "")),
                        False) if row[5] is not None else Temporal.as_mfjson(
                        TTextSeq(str(row[6]).replace("'", "")),
                        False)
                    value_sequence.append(
                        pmdb_provider.
                        convert_temporalproperty_value_to_base_version(
                            json.loads(
                                temporal_property_value)))
            content["valueSequence"] = value_sequence
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

            # TODO: translate titles
        return headers, HTTPStatus.OK, to_json(content, self.pretty_print)

    @gzip
    @pre_process
    def manage_collection_item_tProperty_value(
            self, request: Union[APIRequest, Any],
            action, dataset, identifier,
            tProperty=None) -> Tuple[dict, int, str]:
        """
        Adds Temporal Property Value item to a Temporal Property

        :param request: A request object
        :param dataset: dataset name
        :param identifier: moving feature's id
        :param tProperty: Temporal Property's id

        :returns: tuple of headers, status code, content
        """

        if not request.is_valid(PLUGINS['formatter'].keys()):
            return self.get_format_exception(request)

        # Set Content-Language to system locale until provider locale
        # has been determined
        headers = request.get_response_headers(SYSTEM_LOCALE)

        pmdb_provider = PostgresMobilityDB()
        excuted, tproperty_list = get_list_of_tproperties_name()
        if excuted is False:
            msg = str(tproperty_list)
            return self.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)

        if [dataset, identifier, tProperty] not in tproperty_list:
            msg = 'Temporal Property not found'
            LOGGER.error(msg)
            return self.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)

        collection_id = dataset
        mfeature_id = identifier
        tProperty_name = tProperty
        if action == 'create':
            if not request.data:
                msg = 'No data found'
                LOGGER.error(msg)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)

            data = request.data
            try:
                # Parse bytes data, if applicable
                data = data.decode()
                LOGGER.debug(data)
            except (UnicodeDecodeError, AttributeError):
                pass

            try:
                data = json.loads(data)
            except (json.decoder.JSONDecodeError, TypeError) as err:
                # Input does not appear to be valid JSON
                LOGGER.error(err)
                msg = 'invalid request data'
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'InvalidParameterValue', msg)

            if check_required_field_temporal_value(data) is False:
                # TODO not all processes require input
                msg = 'The required tag (e.g., datetimes,value) \
                    is missing from the request data.'
                return self.get_exception(
                    HTTPStatus.NOT_IMPLEMENTED,
                    headers, request.format, 'MissingParameterValue', msg)

            LOGGER.debug('Creating item')
            try:
                pmdb_provider.connect()
                can_post = pmdb_provider.check_temporalproperty_can_post(
                    collection_id, mfeature_id, [data], tProperty_name)
                if can_post:
                    pValue_id = pmdb_provider.post_temporalvalue(
                        collection_id, mfeature_id, tProperty_name, data)
                else:
                    return headers, HTTPStatus.BAD_REQUEST, ''
            except (Exception, psycopg2.Error) as error:
                msg = str(error)
                return self.get_exception(
                    HTTPStatus.BAD_REQUEST,
                    headers, request.format, 'ConnectingError', msg)
            finally:
                pmdb_provider.disconnect()
            headers['Location'] = '{}/{}/items/{}/tProperties/{}/pvalue/{}'\
                .format(self.get_collections_url(), dataset, mfeature_id,
                        tProperty_name, pValue_id)

            return headers, HTTPStatus.CREATED, ''

    def get_exception(self, status, headers, format_, code,
                      description) -> Tuple[dict, int, str]:
        """
        Exception handler

        :param status: HTTP status code
        :param headers: dict of HTTP response headers
        :param format_: format string
        :param code: OGC API exception code
        :param description: OGC API exception code

        :returns: tuple of headers, status, and message
        """

        LOGGER.error(description)
        exception = {
            'code': code,
            'description': description
        }

        if format_ == F_HTML:
            headers['Content-Type'] = FORMAT_TYPES[F_HTML]
            content = render_j2_template(
                self.config, 'exception.html', exception, SYSTEM_LOCALE)
        else:
            content = to_json(exception, self.pretty_print)

        return headers, status, content

    def get_format_exception(self, request) -> Tuple[dict, int, str]:
        """
        Returns a format exception.

        :param request: An APIRequest instance.

        :returns: tuple of (headers, status, message)
        """

        # Content-Language is in the system locale (ignore language settings)
        headers = request.get_response_headers(SYSTEM_LOCALE)
        msg = f'Invalid format: {request.format}'
        return self.get_exception(
            HTTPStatus.BAD_REQUEST, headers,
            request.format, 'InvalidParameterValue', msg)

    def get_collections_url(self):
        return '{}/collections'.format(self.config['server']['url'])


def validate_bbox(value=None) -> list:
    """
    Helper function to validate bbox parameter

    :param value: `list` of minx, miny, maxx, maxy

    :returns: bbox as `list` of `float` values
    """

    if value is None:
        LOGGER.debug('bbox is empty')
        return []

    bbox = value.split(',')

    if len(bbox) != 4 and len(bbox) != 6:
        msg = 'bbox should be 4 values (minx,miny,maxx,maxy) or \
            6 values (minx,miny,minz,maxx,maxy,maxz)'
        LOGGER.debug(msg)
        raise ValueError(msg)

    try:
        bbox = [float(c) for c in bbox]
    except ValueError as err:
        msg = 'bbox values must be numbers'
        err.args = (msg,)
        LOGGER.debug(msg)
        raise

    if len(bbox) == 4:
        if bbox[1] > bbox[3]:
            msg = 'miny should be less than maxy'
            LOGGER.debug(msg)
            raise ValueError(msg)

        if bbox[0] > bbox[2]:
            msg = 'minx is greater than maxx (possibly antimeridian bbox)'
            LOGGER.debug(msg)
            raise ValueError(msg)

    if len(bbox) == 6:
        if bbox[2] > bbox[5]:
            msg = 'minz should be less than maxz'
            LOGGER.debug(msg)
            raise ValueError(msg)

        if bbox[1] > bbox[4]:
            msg = 'miny should be less than maxy'
            LOGGER.debug(msg)
            raise ValueError(msg)

        if bbox[0] > bbox[3]:
            msg = 'minx is greater than maxx (possibly antimeridian bbox)'
            LOGGER.debug(msg)
            raise ValueError(msg)

    return bbox


def validate_leaf(leaf_=None) -> str:
    """
    Helper function to validate temporal parameter

    :param resource_def: `dict` of configuration resource definition
    :param datetime_: `str` of datetime parameter

    :returns: `str` of datetime input, if valid
    """

    # TODO: pass datetime to query as a `datetime` object
    # we would need to ensure partial dates work accordingly
    # as well as setting '..' values to `None` so that underlying
    # providers can just assume a `datetime.datetime` object
    #
    # NOTE: needs testing when passing partials from API to backend

    unix_epoch = datetime(1970, 1, 1, 0, 0, 0)
    dateparse_ = partial(dateparse, default=unix_epoch)

    leaf_invalid = False

    if leaf_ is not None:
        LOGGER.debug('detected leaf_')
        LOGGER.debug('Validating time windows')
        leaf_list = leaf_.split(',')

        leaf_ = ''
        if (len(leaf_list) > 0):
            datetime_ = dateparse_(leaf_list[0])
            leaf_ = datetime_.strftime('%Y-%m-%d %H:%M:%S.%f')

        for i in range(1, len(leaf_list)):
            datetime_pre = dateparse_(leaf_list[i - 1])
            datetime_ = dateparse_(leaf_list[i])

            if datetime_pre != '..':
                if datetime_pre.tzinfo is None:
                    datetime_pre = datetime_pre.replace(tzinfo=pytz.UTC)

            if datetime_ != '..':
                if datetime_.tzinfo is None:
                    datetime_ = datetime_.replace(tzinfo=pytz.UTC)

            if datetime_pre >= datetime_:
                leaf_invalid = True
                break
            leaf_ += ',' + datetime_.strftime('%Y-%m-%d %H:%M:%S.%f')

    if leaf_invalid:
        msg = 'invalid leaf'
        LOGGER.debug(msg)
        raise ValueError(msg)
    return leaf_


def validate_datetime(datetime_=None, return_type=True) -> str:
    """
    Helper function to validate temporal parameter

    :param resource_def: `dict` of configuration resource definition
    :param datetime_: `str` of datetime parameter

    :returns: `str` of datetime input, if valid
    """

    # TODO: pass datetime to query as a `datetime` object
    # we would need to ensure partial dates work accordingly
    # as well as setting '..' values to `None` so that underlying
    # providers can just assume a `datetime.datetime` object
    #
    # NOTE: needs testing when passing partials from API to backend

    datetime_invalid = False

    if datetime_ is not None and datetime_ != '':
        dateparse_begin = partial(dateparse, default=datetime.min)
        dateparse_end = partial(dateparse, default=datetime.max)
        unix_epoch = datetime(1970, 1, 1, 0, 0, 0)
        dateparse_ = partial(dateparse, default=unix_epoch)

        if '/' in datetime_:  # envelope
            LOGGER.debug('detected time range')
            LOGGER.debug('Validating time windows')

            # normalize "" to ".." (actually changes datetime_)
            datetime_ = re.sub(r'^/', '../', datetime_)
            datetime_ = re.sub(r'/$', '/..', datetime_)

            datetime_begin, datetime_end = datetime_.split('/')
            if datetime_begin != '..':
                datetime_begin = dateparse_begin(datetime_begin)
                if datetime_begin.tzinfo is None:
                    datetime_begin = datetime_begin.replace(
                        tzinfo=pytz.UTC)
            else:
                datetime_begin = datetime(1, 1, 1, 0, 0, 0).replace(
                    tzinfo=pytz.UTC)

            if datetime_end != '..':
                datetime_end = dateparse_end(datetime_end)
                if datetime_end.tzinfo is None:
                    datetime_end = datetime_end.replace(tzinfo=pytz.UTC)
            else:
                datetime_end = datetime(9999, 1, 1, 0, 0, 0).replace(
                    tzinfo=pytz.UTC)

            datetime_invalid = any([
                (datetime_begin > datetime_end)
            ])
            datetime_ = datetime_begin.strftime(
                '%Y-%m-%d %H:%M:%S.%f') + ',' + \
                datetime_end.strftime('%Y-%m-%d %H:%M:%S.%f')
        else:  # time instant
            LOGGER.debug('detected time instant')
            datetime__ = dateparse_(datetime_)
            if datetime__ != '..':
                if datetime__.tzinfo is None:
                    datetime__ = datetime__.replace(tzinfo=pytz.UTC)
            datetime_invalid = any([
                (datetime__ == '..')
            ])
            if return_type:
                datetime_ = datetime__.strftime(
                    '%Y-%m-%d %H:%M:%S.%f') + ',' + \
                    datetime__.strftime('%Y-%m-%d %H:%M:%S.%f')
            else:
                datetime_ = datetime__.strftime('%Y-%m-%d %H:%M:%S.%f')

    if datetime_invalid:
        msg = 'datetime parameter out of range'
        LOGGER.debug(msg)
        raise ValueError(msg)
    return datetime_


def get_list_of_collections_id():
    pmdb_provider = PostgresMobilityDB()
    try:
        pmdb_provider.connect()
        result = pmdb_provider.get_collections_list()
        collections_id = []
        for row in result:
            collections_id.append(row[0])
        return True, collections_id
    except (Exception, psycopg2.Error) as error:
        return False, error
    finally:
        pmdb_provider.disconnect()


def get_list_of_features_id():
    pmdb_provider = PostgresMobilityDB()
    try:
        pmdb_provider.connect()
        result = pmdb_provider.get_features_list()
        features_list = []
        for row in result:
            features_list.append([row[0], row[1]])
        return True, features_list
    except (Exception, psycopg2.Error) as error:
        return False, error
    finally:
        pmdb_provider.disconnect()


def get_list_of_tproperties_name():
    pmdb_provider = PostgresMobilityDB()
    try:
        pmdb_provider.connect()
        result = pmdb_provider.get_tProperties_name_list()
        tproperties_name_list = []
        for row in result:
            tproperties_name_list.append([row[0], row[1], row[2]])
        return True, tproperties_name_list
    except (Exception, psycopg2.Error) as error:
        return False, error
    finally:
        pmdb_provider.disconnect()


def check_required_field_feature(feature):
    if 'type' in feature:
        if feature['type'] == 'FeatureCollection':
            return True
    if 'type' not in feature or 'temporalGeometry' not in feature:
        return False
    if check_required_field_temporal_geometries(
            feature['temporalGeometry']) is False:
        return False
    if 'temporalProperties' in feature:
        if check_required_field_temporal_property(
                feature['temporalProperties']) is False:
            return False
    if 'geometry' in feature:
        if check_required_field_geometries(feature['geometry']) is False:
            return False
    if 'crs' in feature:
        if check_required_field_crs(feature['crs']) is False:
            return False
    if 'trs' in feature:
        if check_required_field_trs(feature['trs']) is False:
            return False
    return True


def check_required_field_geometries(geometry):
    if (check_required_field_geometry_array(geometry) is False
            and check_required_field_geometry_single(geometry) is False):
        return False
    return True


def check_required_field_geometry_array(geometry):
    if ('type' not in geometry
            or 'geometries' not in geometry):
        return False
    geometries = geometry['geometries']
    geometries = [geometries] if not isinstance(
        geometries, list) else geometries
    for l_geometry in geometries:
        if check_required_field_geometry_single(l_geometry) is False:
            return False
    return True


def check_required_field_geometry_single(geometry):
    if ('type' not in geometry
            or 'coordinates' not in geometry):
        return False
    return True


def check_required_field_temporal_geometries(temporal_geometries):
    if (check_required_field_temporal_geometry_array(
        temporal_geometries) is False
            and check_required_field_temporal_geometry_single
            (temporal_geometries) is False):
        return False
    return True


def check_required_field_temporal_geometry_array(temporal_geometries):
    if ('type' not in temporal_geometries
            or 'prisms' not in temporal_geometries):
        return False
    prisms = temporal_geometries['prisms']
    prisms = [prisms] if not isinstance(prisms, list) else prisms
    for temporal_geometry in prisms:
        if check_required_field_temporal_geometry_single(
                temporal_geometry) is False:
            return False
    if 'crs' in temporal_geometries:
        if check_required_field_crs(temporal_geometry['crs']) is False:
            return False
    if 'trs' in temporal_geometries:
        if check_required_field_trs(temporal_geometry['trs']) is False:
            return False
    return True


def check_required_field_temporal_geometry_single(temporal_geometry):
    if ('type' not in temporal_geometry
            or 'datetimes' not in temporal_geometry
            or 'coordinates' not in temporal_geometry):
        return False
    if 'crs' in temporal_geometry:
        if check_required_field_crs(temporal_geometry['crs']) is False:
            return False
    if 'trs' in temporal_geometry:
        if check_required_field_trs(temporal_geometry['trs']) is False:
            return False
    return True

# TODO Do you still have the 'temporalProperties' key?
# def checkRequiredFieldTemporalProperties(temporalProperties):
#     if 'temporalProperties' not in temporalProperties:
#         return False
#     if check_required_field_temporal_property\
#           (temporalProperties['temporalProperties']) is False:
#         return False
#     return True


def check_required_field_temporal_property(temporal_properties):
    temporal_properties = [temporal_properties] if not isinstance(
        temporal_properties, list) else temporal_properties
    for temporal_property in temporal_properties:
        if ('datetimes' not in temporal_property):
            return False
        for tproperties_name in temporal_property:
            if tproperties_name != 'datetimes' and (
                'values'
                not
                in
                temporal_property
                [tproperties_name]
                or
                'interpolation'
                not
                in
                temporal_property
                    [tproperties_name]):
                return False
    return True


def check_required_field_temporal_value(temporalValue):
    if ('datetimes' not in temporalValue
            or 'values' not in temporalValue
            or 'interpolation' not in temporalValue):
        return False
    return True


def check_required_field_crs(crs):
    if ('type' not in crs
            or 'properties' not in crs):
        return False
    return True


def check_required_field_trs(trs):
    if ('type' not in trs
            or 'properties' not in trs):
        return False
    return True
