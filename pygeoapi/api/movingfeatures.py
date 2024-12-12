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

from datetime import datetime
from functools import partial
import json
import logging
import re
from typing import Tuple
import urllib.parse

from dateutil.parser import parse as dateparse
import pytz
from http import HTTPStatus

from pygeoapi.plugin import PLUGINS

from pymeos import (STBox, TsTzSpan, TTextSeq, TFloatSeq,
                    TGeomPointSeq, Temporal, pymeos_initialize)
import psycopg2
from pygeoapi.provider.postgresql_mobilitydb import PostgresMobilityDB
from . import (API, APIRequest, SYSTEM_LOCALE,
               FORMAT_TYPES, F_JSON)
from pygeoapi.util import (to_json)

LOGGER = logging.getLogger(__name__)


CONFORMANCE_CLASSES_MOVINGFEATURES = [
    "http://www.opengis.net/spec/ogcapi-movingfeatures-1/1.0/conf/common",
    "http://www.opengis.net/spec/ogcapi-movingfeatures-1/1.0/conf/mf-collection",  # noqa
    "http://www.opengis.net/spec/ogcapi-movingfeatures-1/1.0/conf/movingfeatures"  # noqa
]


def manage_collection(api: API, request: APIRequest,
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
            return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

    if action == 'create':
        try:
            pmdb_provider.connect()
            collection_id = pmdb_provider.post_collection(data)
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()

        url = '{}/{}'.format(api.get_collections_url(), collection_id)

        headers['Location'] = url
        return headers, HTTPStatus.CREATED, ''

    if action == 'update':
        LOGGER.debug('Updating item')
        try:
            pmdb_provider.connect()
            pmdb_provider.put_collection(collection_id, data)
        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()

        return headers, HTTPStatus.NO_CONTENT, ''


def get_collection(api: API, request: APIRequest,
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
        return api.get_format_exception(request)
    headers = request.get_response_headers()

    try:
        pmdb_provider.connect()
        result = pmdb_provider.get_collection(collection_id)
        if len(result) > 0:
            row = result[0]
        else:
            msg = 'Collection not found'
            LOGGER.error(msg)
            return api.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)
    except (Exception, psycopg2.Error) as error:
        msg = str(error)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)

    collection = {}
    if row is not None:
        pymeos_initialize()
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
                api.get_collections_url(), collection_id),
            'rel': request.get_linkrel(F_JSON),
            'type': FORMAT_TYPES[F_JSON]
        })

    return headers, HTTPStatus.OK, to_json(collection, api.pretty_print)


def get_collection_items(
        api: API, request: APIRequest,
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
        return api.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE)

    excuted, collections = get_list_of_collections_id()
    collection_id = dataset
    if excuted is False:
        msg = str(collections)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)

    if collection_id not in collections:
        msg = 'Collection not found'
        LOGGER.error(msg)
        return api.get_exception(
            HTTPStatus.NOT_FOUND,
            headers, request.format, 'NotFound', msg)
    LOGGER.debug('Processing query parameters')

    LOGGER.debug('Processing offset parameter')
    try:
        offset = int(request.params.get('offset'))
        if offset < 0:
            msg = 'offset value should be positive or zero'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        offset = 0
    except ValueError:
        msg = 'offset value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    LOGGER.debug('Processing limit parameter')
    try:
        limit = int(request.params.get('limit'))
        # TODO: We should do more validation, against the min and max
        #       allowed by the server configuration
        if limit <= 0:
            msg = 'limit value should be strictly positive'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
        if limit > 10000:
            msg = 'limit value should be less than or equal to 10000'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        limit = int(api.config['server']['limit'])
    except ValueError:
        msg = 'limit value should be an integer'
        return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

    LOGGER.debug('Processing datetime parameter')
    datetime_ = request.params.get('datetime')
    try:
        datetime_ = validate_datetime(datetime_)
    except ValueError as err:
        msg = str(err)
        return api.get_exception(
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
        return api.get_exception(
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
    uri = '{}/{}/items'.format(api.get_collections_url(), collection_id)

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
    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def manage_collection_item(
        api: API, request: APIRequest,
        action, dataset, identifier=None) -> Tuple[dict, int, str]:
    """
    Adds an item to a collection

    :param request: A request object
    :param dataset: dataset name

    :returns: tuple of headers, status code, content
    """

    if not request.is_valid(PLUGINS['formatter'].keys()):
        return api.get_format_exception(request)

    # Set Content-Language to system locale until provider locale
    # has been determined
    headers = request.get_response_headers(SYSTEM_LOCALE)

    pmdb_provider = PostgresMobilityDB()
    excuted, collections = get_list_of_collections_id()

    if excuted is False:
        msg = str(collections)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)

    if dataset not in collections:
        msg = 'Collection not found'
        LOGGER.error(msg)
        return api.get_exception(
            HTTPStatus.NOT_FOUND,
            headers, request.format, 'NotFound', msg)

    collection_id = dataset
    mfeature_id = identifier
    if action == 'create':
        if not request.data:
            msg = 'No data found'
            LOGGER.error(msg)
            return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        if check_required_field_feature(data) is False:
            # TODO not all processes require input
            msg = 'The required tag (e.g., type,temporalgeometry) \
                is missing from the request data.'
            return api.get_exception(
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
                        return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()

        headers['Location'] = '{}/{}/items/{}'.format(
            api.get_collections_url(), dataset, mfeature_id)

        return headers, HTTPStatus.CREATED, ''

    if action == 'delete':
        LOGGER.debug('Deleting item')

        try:
            pmdb_provider.connect()
            pmdb_provider.delete_movingfeature(
                "AND mfeature_id ='{0}'".format(mfeature_id))

        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()

        return headers, HTTPStatus.NO_CONTENT, ''


def get_collection_item(api: API, request: APIRequest,
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
        return api.get_format_exception(request)
    headers = request.get_response_headers()

    try:
        pmdb_provider.connect()
        result = pmdb_provider.get_feature(collection_id, mfeature_id)
        if len(result) > 0:
            row = result[0]
        else:
            msg = 'Feature not found'
            LOGGER.error(msg)
            return api.get_exception(
                HTTPStatus.NOT_FOUND,
                headers, request.format, 'NotFound', msg)
    except (Exception, psycopg2.Error) as error:
        msg = str(error)
        return api.get_exception(
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
                api.get_collections_url(), collection_id, mfeature_id),
            'rel': request.get_linkrel(F_JSON),
            'type': FORMAT_TYPES[F_JSON]
        })
    return headers, HTTPStatus.OK, to_json(mfeature, api.pretty_print)


def get_collection_items_tGeometry(api: API, request: APIRequest,
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
        return api.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE)

    excuted, feature_list = get_list_of_features_id()
    if excuted is False:
        msg = str(feature_list)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)

    if [dataset, identifier] not in feature_list:
        msg = 'Feature not found'
        LOGGER.error(msg)
        return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        offset = 0
    except ValueError:
        msg = 'offset value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    LOGGER.debug('Processing limit parameter')
    try:
        limit = int(request.params.get('limit'))
        # TODO: We should do more validation, against the min and max
        #       allowed by the server configuration
        if limit <= 0:
            msg = 'limit value should be strictly positive'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
        if limit > 10000:
            msg = 'limit value should be less than or equal to 10000'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        limit = int(api.config['server']['limit'])
    except ValueError:
        msg = 'limit value should be an integer'
        return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

    leaf_ = request.params.get('leaf')
    LOGGER.debug('Processing leaf parameter')
    try:
        leaf_ = validate_leaf(leaf_)
    except ValueError as err:
        msg = str(err)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    sub_trajectory = request.params.get('subTrajectory')
    if sub_trajectory is None:
        sub_trajectory = False

    if (leaf_ != '' and leaf_ is not None) \
            and (sub_trajectory or sub_trajectory == 'true'):
        msg = 'Cannot use both parameter `subTrajectory` \
            and `leaf` at the same time'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    LOGGER.debug('Processing datetime parameter')
    datetime_ = request.params.get('datetime')
    try:
        datetime_ = validate_datetime(datetime_)
    except ValueError as err:
        msg = str(err)
        return api.get_exception(
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
        return api.get_exception(
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
        api.get_collections_url(), collection_id, mfeature_id)

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
    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def manage_collection_item_tGeometry(
        api: API, request: APIRequest,
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
        return api.get_format_exception(request)

    # Set Content-Language to system locale until provider locale
    # has been determined
    headers = request.get_response_headers(SYSTEM_LOCALE)

    pmdb_provider = PostgresMobilityDB()
    excuted, feature_list = get_list_of_features_id()

    if excuted is False:
        msg = str(feature_list)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)

    if [dataset, identifier] not in feature_list:
        msg = 'Feature not found'
        LOGGER.error(msg)
        return api.get_exception(
            HTTPStatus.NOT_FOUND,
            headers, request.format, 'NotFound', msg)

    collection_id = dataset
    mfeature_id = identifier
    tGeometry_id = tGeometry
    if action == 'create':
        if not request.data:
            msg = 'No data found'
            LOGGER.error(msg)
            return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        if check_required_field_temporal_geometries(data) is False:
            # TODO not all processes require input
            msg = 'The required tag (e.g., type,prisms) \
                is missing from the request data.'
            return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()

        headers['Location'] = '{}/{}/items/{}/tgsequence/{}'.format(
            api.get_collections_url(), dataset, mfeature_id, tGeometry_id)

        return headers, HTTPStatus.CREATED, ''

    if action == 'delete':
        LOGGER.debug('Deleting item')

        try:
            pmdb_provider.connect()
            pmdb_provider.delete_temporalgeometry(
                "AND tgeometry_id ='{0}'".format(tGeometry_id))

        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()

        return headers, HTTPStatus.NO_CONTENT, ''


def get_collection_items_tGeometry_velocity(api: API, request: APIRequest,
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
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)
    try:
        pmdb_provider.connect()
        content = pmdb_provider.get_velocity(
            collection_id, mfeature_id, tgeometry_id, datetime_)
    except (Exception, psycopg2.Error) as error:
        msg = str(error)
        return api.get_exception(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            headers, request.format, 'Server Internal Error', msg)
    finally:
        pmdb_provider.disconnect()

    return headers, HTTPStatus.OK, content


def get_collection_items_tGeometry_distance(api: API, request: APIRequest,
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
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)
    try:
        pmdb_provider.connect()
        content = pmdb_provider.get_distance(
            collection_id, mfeature_id, tgeometry_id, datetime_)
    except (Exception, psycopg2.Error) as error:
        msg = str(error)
        return api.get_exception(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            headers, request.format, 'ConnectingError', msg)
    finally:
        pmdb_provider.disconnect()

    return headers, HTTPStatus.OK, content


def get_collection_items_tGeometry_acceleration(api: API, request: APIRequest,
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
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)
    try:
        pmdb_provider.connect()
        content = pmdb_provider.get_acceleration(
            collection_id, mfeature_id, tgeometry_id, datetime_)
    except (Exception, psycopg2.Error) as error:
        msg = str(error)
        return api.get_exception(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            headers, request.format, 'ConnectingError', msg)
    finally:
        pmdb_provider.disconnect()

    return headers, HTTPStatus.OK, content


def get_collection_items_tProperty(api: API, request: APIRequest,
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
        return api.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE)

    excuted, feature_list = get_list_of_features_id()
    if excuted is False:
        msg = str(feature_list)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)

    if [dataset, identifier] not in feature_list:
        msg = 'Feature not found'
        LOGGER.error(msg)
        return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        offset = 0
    except ValueError:
        msg = 'offset value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    LOGGER.debug('Processing limit parameter')
    try:
        limit = int(request.params.get('limit'))
        # TODO: We should do more validation, against the min and max
        #       allowed by the server configuration
        if limit <= 0:
            msg = 'limit value should be strictly positive'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
        if limit > 10000:
            msg = 'limit value should be less than or equal to 10000'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        limit = int(api.config['server']['limit'])
    except ValueError:
        msg = 'limit value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    LOGGER.debug('Processing datetime parameter')
    datetime_ = request.params.get('datetime')
    try:
        datetime_ = validate_datetime(datetime_)
    except ValueError as err:
        msg = str(err)
        return api.get_exception(
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
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)

        # TODO: translate titles
    uri = '{}/{}/items/{}/tProperties'.format(
        api.get_collections_url(), collection_id, mfeature_id)

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
    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def manage_collection_item_tProperty(
        api: API, request: APIRequest,
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
        return api.get_format_exception(request)

    # Set Content-Language to system locale until provider locale
    # has been determined
    headers = request.get_response_headers(SYSTEM_LOCALE)

    pmdb_provider = PostgresMobilityDB()
    excuted, feature_list = get_list_of_features_id()

    if excuted is False:
        msg = str(feature_list)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)

    if [dataset, identifier] not in feature_list:
        msg = 'Feature not found'
        LOGGER.error(msg)
        return api.get_exception(
            HTTPStatus.NOT_FOUND,
            headers, request.format, 'NotFound', msg)

    collection_id = dataset
    mfeature_id = identifier
    tProperties_name = tProperty
    if action == 'create':
        if not request.data:
            msg = 'No data found'
            LOGGER.error(msg)
            return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        if check_required_field_temporal_property(data) is False:
            # TODO not all processes require input
            msg = 'The required tag (e.g., datetimes,interpolation) \
                is missing from the request data.'
            return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()

        location_list = []
        for tProperties_name in tProperties_name_list:
            location_list.append('{}/{}/items/{}/tProperties/{}'.format(
                api.get_collections_url(), dataset, mfeature_id,
                tProperties_name))
        headers['Locations'] = location_list

        return headers, HTTPStatus.CREATED, ''

    if action == 'delete':
        LOGGER.debug('Deleting item')

        try:
            pmdb_provider.connect()
            pmdb_provider.delete_temporalproperties(
                """AND collection_id ='{0}' AND mfeature_id ='{1}'
                AND tproperties_name ='{2}'""".format(
                    collection_id, mfeature_id, tProperties_name))

        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()

        return headers, HTTPStatus.NO_CONTENT, ''


def get_collection_items_tProperty_value(api: API, request: APIRequest,
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
        return api.get_format_exception(request)
    headers = request.get_response_headers(SYSTEM_LOCALE)

    excuted, tproperty_list = get_list_of_tproperties_name()
    if excuted is False:
        msg = str(tproperty_list)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)

    if [dataset, identifier, tProperty] not in tproperty_list:
        msg = 'Temporal Property not found'
        LOGGER.error(msg)
        return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        offset = 0
    except ValueError:
        msg = 'offset value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    LOGGER.debug('Processing limit parameter')
    try:
        limit = int(request.params.get('limit'))
        # TODO: We should do more validation, against the min and max
        #       allowed by the server configuration
        if limit <= 0:
            msg = 'limit value should be strictly positive'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
        if limit > 10000:
            msg = 'limit value should be less than or equal to 10000'
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)
    except TypeError as err:
        LOGGER.warning(err)
        limit = int(api.config['server']['limit'])
    except ValueError:
        msg = 'limit value should be an integer'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    LOGGER.debug('Processing leaf parameter')
    leaf_ = request.params.get('leaf')
    try:
        leaf_ = validate_leaf(leaf_)
    except ValueError as err:
        msg = str(err)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    sub_temporal_value = request.params.get('subTemporalValue')
    if sub_temporal_value is None:
        sub_temporal_value = False

    if (leaf_ != '' and leaf_ is not None) and \
            (sub_temporal_value or sub_temporal_value == 'true'):
        msg = 'Cannot use both parameter `subTemporalValue` \
            and `leaf` at the same time'
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'InvalidParameterValue', msg)

    LOGGER.debug('Processing datetime parameter')
    datetime_ = request.params.get('datetime')
    try:
        datetime_ = validate_datetime(datetime_)
    except ValueError as err:
        msg = str(err)
        return api.get_exception(
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
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)

        # TODO: translate titles
    return headers, HTTPStatus.OK, to_json(content, api.pretty_print)


def manage_collection_item_tProperty_value(
        api: API, request: APIRequest,
        action, dataset, identifier,
        tProperty=None, tvalue=None) -> Tuple[dict, int, str]:
    """
    Adds Temporal Property Value item to a Temporal Property

    :param request: A request object
    :param dataset: dataset name
    :param identifier: moving feature's id
    :param tProperty: Temporal Property's id

    :returns: tuple of headers, status code, content
    """

    if not request.is_valid(PLUGINS['formatter'].keys()):
        return api.get_format_exception(request)

    # Set Content-Language to system locale until provider locale
    # has been determined
    headers = request.get_response_headers(SYSTEM_LOCALE)

    pmdb_provider = PostgresMobilityDB()
    excuted, tproperty_list = get_list_of_tproperties_name()
    if excuted is False:
        msg = str(tproperty_list)
        return api.get_exception(
            HTTPStatus.BAD_REQUEST,
            headers, request.format, 'ConnectingError', msg)
    if [dataset, identifier, tProperty] not in tproperty_list:
        msg = 'Temporal Property not found'
        LOGGER.error(msg)
        return api.get_exception(
            HTTPStatus.NOT_FOUND,
            headers, request.format, 'NotFound', msg)

    collection_id = dataset
    mfeature_id = identifier
    tProperty_name = tProperty
    tvalue_id = tvalue
    if action == 'create':
        if not request.data:
            msg = 'No data found'
            LOGGER.error(msg)
            return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'InvalidParameterValue', msg)

        if check_required_field_temporal_value(data) is False:
            # TODO not all processes require input
            msg = 'The required tag (e.g., datetimes,value) \
                is missing from the request data.'
            return api.get_exception(
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
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()
        headers['Location'] = '{}/{}/items/{}/tProperties/{}/pvalue/{}'\
            .format(api.get_collections_url(), dataset, mfeature_id,
                    tProperty_name, pValue_id)

        return headers, HTTPStatus.CREATED, ''

    if action == 'delete':
        LOGGER.debug('Deleting item')

        try:
            pmdb_provider.connect()
            pmdb_provider.delete_temporalvalue(
                "AND tvalue_id ='{0}'".format(tvalue_id))

        except (Exception, psycopg2.Error) as error:
            msg = str(error)
            return api.get_exception(
                HTTPStatus.BAD_REQUEST,
                headers, request.format, 'ConnectingError', msg)
        finally:
            pmdb_provider.disconnect()

        return headers, HTTPStatus.NO_CONTENT, ''


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

# fmt: off
def get_oas_30(cfg: dict, locale: str) -> tuple[list[dict[str, str]], dict[str, dict]]:  # noqa
    """
    Get OpenAPI fragments

    :param cfg: `dict` of configuration
    :param locale: `str` of locale

    :returns: `tuple` of `list` of tag objects, and `dict` of path objects
    """
    from pygeoapi.openapi import OPENAPI_YAML

    paths = {}
    collections_collectionId_path = '/collections/{collectionId}'
    paths[collections_collectionId_path] = {
        "get": {
            "operationId": "accessMetadata",
            "summary": "Access metadata about the collection",
            "description": "A user can access metadata with id `collectionId`.\n",  # noqa
            "tags": [
                "MovingFeatureCollection"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                }
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/Collection"  # noqa
                },
                "404": {
                    "description": "A collection with the specified id was not found."  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        },
        "delete": {
            "operationId": "deleteCollection",
            "summary": "Delete the collection",
            "description": "The collection catalog with id `collectionId` and including metadata and moving features SHOULD be deleted.\n",  # noqa
            "tags": [
                "MovingFeatureCollection"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                }
            ],
            "responses": {
                "204": {
                    "description": "Successfully deleted."
                },
                "404": {
                    "description": "A collection with the specified name was not found."  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        },
        "put": {
            "operationId": "replaceMetadata",
            "summary": "Replace metadata about the collection",
            "description": "A user SHOULD replace metadata with id `collectionId`.\n\nThe request body schema is the same the POST's one. \n\nHowever, `updateFrequency` property is NOT updated.\n",  # noqa
            "tags": [
                "MovingFeatureCollection"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                }
            ],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/schemas/collection-body"  # noqa
                        },
                        "example": {
                            "title": "moving_feature_collection_sample",
                            "updateFrequency": 1000,
                            "description": "example",
                            "itemType": "movingfeature"
                        }
                    }
                }
            },
            "responses": {
                "204": {
                    "description": "Successfully replaced."
                },
                "404": {
                    "description": "A collection with the specified name was not found."  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        }
    }

    collections_collectionId_items_path = '/collections/{collectionId}/items'
    paths[collections_collectionId_items_path] = {
        "get": {
            "operationId": "retrieveMovingFeatures",
            "summary": "Retrieve moving feature collection",
            "description": "A user can retrieve moving feature collection to access the static information of the moving feature by simple filtering and a limit.\n\nSpecifically, if the `subTrajectory` parameter is \"true\", it will return the temporal geometry within the time interval specified by `datetime` parameter.\n",  # noqa
            "tags": [
                "MovingFeatures"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/bbox"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/datetime"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/limit"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/subtrajectory"  # noqa
                }
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/MovingFeatures"  # noqa
                },
                "404": {
                    "description": "A collection with the specified id was not found."  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        },
        "post": {
            "operationId": "insertMovingFeatures",
            "summary": "Insert moving features",
            "description": "A user SHOULD insert a set of moving features or a moving feature into a collection with id `collectionId`.\n\nThe request body schema SHALL follows the [MovingFeature object](https://docs.opengeospatial.org/is/19-045r3/19-045r3.html#mfeature) or \n[MovingFeatureCollection object](https://docs.opengeospatial.org/is/19-045r3/19-045r3.html#mfeaturecollection) in the OGC MF-JSON.\n",  # noqa
            "tags": [
                "MovingFeatures"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                }
            ],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "oneOf": [
                                {
                                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/schemas/movingFeature-mfjson"  # noqa
                                },
                                {
                                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/schemas/movingFeatureCollection"  # noqa
                                }
                            ]
                        },
                        "example": {
                            "type": "Feature",
                            "crs": {
                                "type": "Name",
                                "properties": {
                                    "name": "urn:ogc:def:crs:OGC:1.3:CRS84"  # noqa
                                }
                            },
                            "trs": {
                                "type": "Link",
                                "properties": {
                                    "type": "OGCDEF",
                                    "href": "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian"  # noqa
                                }
                            },
                            "temporalGeometry": {
                                "type": "MovingPoint",
                                "datetimes": [
                                    "2011-07-14T22:01:01Z",
                                    "2011-07-14T22:01:02Z",
                                    "2011-07-14T22:01:03Z",
                                    "2011-07-14T22:01:04Z",
                                    "2011-07-14T22:01:05Z"
                                ],
                                "coordinates": [
                                    [
                                        139.757083,
                                        35.627701,
                                        0.5
                                    ],
                                    [
                                        139.757399,
                                        35.627701,
                                        2
                                    ],
                                    [
                                        139.757555,
                                        35.627688,
                                        4
                                    ],
                                    [
                                        139.757651,
                                        35.627596,
                                        4
                                    ],
                                    [
                                        139.757716,
                                        35.627483,
                                        4
                                    ]
                                ],
                                "interpolation": "Linear",
                                "base": {
                                    "type": "glTF",
                                    "href": "http://www.opengis.net/spec/movingfeatures/json/1.0/prism/example/car3dmodel.gltf"  # noqa
                                },
                                "orientations": [
                                    {
                                        "scales": [
                                            1,
                                            1,
                                            1
                                        ],
                                        "angles": [
                                            0,
                                            0,
                                            0
                                        ]
                                    },
                                    {
                                        "scales": [
                                            1,
                                            1,
                                            1
                                        ],
                                        "angles": [
                                            0,
                                            355,
                                            0
                                        ]
                                    },
                                    {
                                        "scales": [
                                            1,
                                            1,
                                            1
                                        ],
                                        "angles": [
                                            0,
                                            0,
                                            330
                                        ]
                                    },
                                    {
                                        "scales": [
                                            1,
                                            1,
                                            1
                                        ],
                                        "angles": [
                                            0,
                                            0,
                                            300
                                        ]
                                    },
                                    {
                                        "scales": [
                                            1,
                                            1,
                                            1
                                        ],
                                        "angles": [
                                            0,
                                            0,
                                            270
                                        ]
                                    }
                                ]
                            },
                            "temporalProperties": [
                                {
                                    "datetimes": [
                                        "2011-07-14T22:01:01.450Z",
                                        "2011-07-14T23:01:01.450Z",
                                        "2011-07-15T00:01:01.450Z"
                                    ],
                                    "length": {
                                        "type": "Measure",
                                        "form": "http://qudt.org/vocab/quantitykind/Length",  # noqa
                                        "values": [
                                            1,
                                            2.4,
                                            1
                                        ],
                                        "interpolation": "Linear"
                                    },
                                    "discharge": {
                                        "type": "Measure",
                                        "form": "MQS",
                                        "values": [
                                            3,
                                            4,
                                            5
                                        ],
                                        "interpolation": "Step"
                                    }
                                },
                                {
                                    "datetimes": [
                                        1465621816590,
                                        1465711526300
                                    ],
                                    "camera": {
                                        "type": "Image",
                                        "values": [
                                            "http://www.opengis.net/spec/movingfeatures/json/1.0/prism/example/image1",  # noqa
                                            "iVBORw0KGgoAAAANSUhEU......"
                                        ],
                                        "interpolation": "Discrete"
                                    },
                                    "labels": {
                                        "type": "Text",
                                        "values": [
                                            "car",
                                            "human"
                                        ],
                                        "interpolation": "Discrete"
                                    }
                                }
                            ],
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [
                                    [
                                        139.757083,
                                        35.627701,
                                        0.5
                                    ],
                                    [
                                        139.757399,
                                        35.627701,
                                        2
                                    ],
                                    [
                                        139.757555,
                                        35.627688,
                                        4
                                    ],
                                    [
                                        139.757651,
                                        35.627596,
                                        4
                                    ],
                                    [
                                        139.757716,
                                        35.627483,
                                        4
                                    ]
                                ]
                            },
                            "properties": {
                                "name": "car1",
                                "state": "test1",
                                "video": "http://www.opengis.net/spec/movingfeatures/json/1.0/prism/example/video.mpeg"  # noqa
                            },
                            "bbox": [
                                139.757083,
                                35.627483,
                                0,
                                139.757716,
                                35.627701,
                                4.5
                            ],
                            "time": [
                                "2011-07-14T22:01:01Z",
                                "2011-07-15T01:11:22Z"
                            ],
                            "id": "mf-1"
                        }
                    }
                }
            },
            "responses": {
                "201": {
                    "description": "Successful create a set of moving features or a moving feature into a specific collection.\n",  # noqa
                    "headers": {
                        "Locations": {
                            "description": "A list of URI of the newly added resources",  # noqa
                            "schema": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "example": [
                                    "https://data.example.org/collections/mfc-1/items/mf-1",  # noqa
                                    "https://data.example.org/collections/mfc-1/items/109301273"  # noqa
                                ]
                            }
                        }
                    }
                },
                "400": {
                    "description": "A query parameter was not validly used."
                },
                "404": {
                    "description": "A collection with the specified id was not found."  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        }
    }

    collections_collectionId_items_mFeatureId_path = '/collections/{collectionId}/items/{mFeatureId}'  # noqa
    paths[collections_collectionId_items_mFeatureId_path] = {
        "get": {
            "operationId": "accessMovingFeature",
            "summary": "Access the static data of the moving feature",
            "description": "A user can access a static data of a moving feature with id `mFeatureId`.\n\nThe static data of a moving feature is not included temporal geometries and temporal properties.\n",  # noqa
            "tags": [
                "MovingFeatures"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                }
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/MovingFeature"  # noqa
                },
                "404": {
                    "description": "- A collection with the specified id was not found.\n- Or a moving feature with the specified id was not found.\n"  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        },
        "delete": {
            "operationId": "deleteMovingFeature",
            "summary": "Delete a single moving feature",
            "description": "The moving feature with id `mFeatureId` and including temporal geometries and properties SHOULD be deleted.\n",  # noqa
            "tags": [
                "MovingFeatures"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                }
            ],
            "responses": {
                "204": {
                    "description": "Successfully deleted."
                },
                "404": {
                    "description": "- A collection with the specified id was not found.\n- Or a moving feature with the specified id was not found.\n"  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        }
    }
    collections_collectionId_items_mFeatureId_tgsequence_path = '/collections/{collectionId}/items/{mFeatureId}/tgsequence'  # noqa
    paths[collections_collectionId_items_mFeatureId_tgsequence_path] = {
        "get": {
            "operationId": "retrieveTemporalGeometrySequence",
            "summary": "Retrieve the movement data of the single moving feature",  # noqa
            "description": "A user can retrieve only the movement data of a moving feature with id `mFeatureId` by simple filtering and a limit.\n",  # noqa
            "tags": [
                "TemporalGeometry"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/bbox"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/datetime"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/limit"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/leaf"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/subtrajectory"  # noqa
                }
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/TemporalGeometrySequence"  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        },
        "post": {
            "operationId": "insertTemporalPrimitiveGeometry",
            "summary": "Add movement data into the moving feature",
            "description": "A user SHOULD add more movement data into a moving feature with id `mFeatureId`.\n\nThe request body schema SHALL follows the [TemporalPrimitiveGeometry object](https://docs.ogc.org/is/19-045r3/19-045r3.html#tprimitive) in the OGC MF-JSON.\n",  # noqa
            "tags": [
                "TemporalGeometry"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                }
            ],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/schemas/temporalPrimitiveGeometry"  # noqa
                        },
                        "example": {
                            "type": "MovingPoint",
                            "datetimes": [
                                "2011-07-14T22:01:06Z",
                                "2011-07-14T22:01:07Z",
                                "2011-07-14T22:01:08Z",
                                "2011-07-14T22:01:09Z",
                                "2011-07-14T22:01:10Z"
                            ],
                            "coordinates": [
                                [
                                    139.757083,
                                    35.627701,
                                    0.5
                                ],
                                [
                                    139.757399,
                                    35.627701,
                                    2
                                ],
                                [
                                    139.757555,
                                    35.627688,
                                    4
                                ],
                                [
                                    139.757651,
                                    35.627596,
                                    4
                                ],
                                [
                                    139.757716,
                                    35.627483,
                                    4
                                ]
                            ],
                            "interpolation": "Linear",
                            "base": {
                                "type": "glTF",
                                "href": "https://www.opengis.net/spec/movingfeatures/json/1.0/prism/example/car3dmodel.gltf"  # noqa
                            },
                            "orientations": [
                                {
                                    "scales": [
                                        1,
                                        1,
                                        1
                                    ],
                                    "angles": [
                                        0,
                                        0,
                                        0
                                    ]
                                },
                                {
                                    "scales": [
                                        1,
                                        1,
                                        1
                                    ],
                                    "angles": [
                                        0,
                                        355,
                                        0
                                    ]
                                },
                                {
                                    "scales": [
                                        1,
                                        1,
                                        1
                                    ],
                                    "angles": [
                                        0,
                                        0,
                                        330
                                    ]
                                },
                                {
                                    "scales": [
                                        1,
                                        1,
                                        1
                                    ],
                                    "angles": [
                                        0,
                                        0,
                                        300
                                    ]
                                },
                                {
                                    "scales": [
                                        1,
                                        1,
                                        1
                                    ],
                                    "angles": [
                                        0,
                                        0,
                                        270
                                    ]
                                }
                            ]
                        }
                    }
                }
            },
            "responses": {
                "201": {
                    "description": "Successful add more movement data into a specified moving feature.\n",  # noqa
                    "headers": {
                        "Location": {
                            "description": "A URI of the newly added resource",  # noqa
                            "schema": {
                                "type": "string",
                                "example": "https://data.example.org/collections/mfc-1/items/mf-1/tgsequence/tg-2"  # noqa
                            }
                        }
                    }
                },
                "400": {
                    "description": "A query parameter was not validly used."  # noqa
                },
                "404": {
                    "description": "- A collection with the specified id was not found.\n- Or a moving feature with the specified id was not found.\n"  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        }
    }

    collections_collectionId_items_mFeatureId_tgsequence_tGeometryId_path = '/collections/{collectionId}/items/{mFeatureId}/tgsequence/{tGeometryId}'  # noqa
    paths[collections_collectionId_items_mFeatureId_tgsequence_tGeometryId_path] = {  # noqa
        "delete": {
            "operationId": "deleteTemporalPrimitiveGeometry",
            "summary": "Delete a singe temporal primitive geometry",
            "description": "The temporal primitive geometry with id `tGeometryId` SHOULD be deleted.\n",  # noqa
            "tags": [
                "TemporalGeometry"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/tGeometryId"  # noqa
                }
            ],
            "responses": {
                "204": {
                    "description": "Successfully deleted."
                },
                "404": {
                    "description": "- A collection with the specified id was not found.\n- Or a moving feature with the specified id was not found.\n- Or a temporal primitive geometry with the specified id was not found.\n"  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        }
    }

    collections_collectionId_items_mFeatureId_tgsequence_tGeometryId_distance_path = '/collections/{collectionId}/items/{mFeatureId}/tgsequence/{tGeometryId}/distance'  # noqa
    paths[collections_collectionId_items_mFeatureId_tgsequence_tGeometryId_distance_path] = {  # noqa
        "get": {
            "operationId": "getDistanceOfTemporalPrimitiveGeometry",
            "summary": "Get a time-to-distance curve of a temporal primitive geometry",  # noqa
            "description": "A user can get time-to-distance curve of a temporal primitive geometry with id `tGeometryId`.\n",  # noqa
            "tags": [
                "TemporalGeometryQuery"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/tGeometryId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/datetime"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/leaf"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/subtemporalvalue"  # noqa
                }
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/DistanceQuery"  # noqa
                },
                "400": {
                    "description": "A query parameter was not validly used."  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        }
    }

    collections_collectionId_items_mFeatureId_tgsequence_tGeometryId_velocity_path = '/collections/{collectionId}/items/{mFeatureId}/tgsequence/{tGeometryId}/velocity'  # noqa
    paths[collections_collectionId_items_mFeatureId_tgsequence_tGeometryId_velocity_path] = {  # noqa
        "get": {
            "operationId": "getVelocityOfTemporalPrimitiveGeometry",
            "summary": "Get a time-to-velocity curve of a temporal primitive geometry",  # noqa
            "description": "A user can get time-to-velocity curve of a temporal primitive geometry with id `tGeometryId`.\n",  # noqa
            "tags": [
                "TemporalGeometryQuery"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/tGeometryId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/datetime"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/leaf"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/subtemporalvalue"  # noqa
                }
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/VelocityQuery"  # noqa
                },
                "400": {
                    "description": "A query parameter was not validly used."
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        }
    }

    collections_collectionId_items_mFeatureId_tgsequence_tGeometryId_acceleration_path = '/collections/{collectionId}/items/{mFeatureId}/tgsequence/{tGeometryId}/acceleration'  # noqa
    paths[collections_collectionId_items_mFeatureId_tgsequence_tGeometryId_acceleration_path] = {  # noqa
        "get": {
            "operationId": "getAccelerationOfTemporalPrimitiveGeometry",
            "summary": "Get a time-to-acceleration curve of a temporal primitive geometry",  # noqa
            "description": "A user can get time-to-acceleration curve of a temporal primitive geometry with id `tGeometryId`.\n",  # noqa
            "tags": [
                "TemporalGeometryQuery"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/tGeometryId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/datetime"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/leaf"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/subtemporalvalue"  # noqa
                }
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/AccelerationQuery"  # noqa
                },
                "400": {
                    "description": "A query parameter was not validly used."  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        }
    }

    collections_collectionId_items_mFeatureId_tproperties_path = '/collections/{collectionId}/items/{mFeatureId}/tproperties'  # noqa
    paths[collections_collectionId_items_mFeatureId_tproperties_path] = {  # noqa
        "get": {
            "operationId": "retrieveTemporalProperties",
            "summary": "Retrieve a set of the temporal property data",
            "description": "A user can retrieve the static information of the temporal property data that included a single moving feature with id `mFeatureId`.\n\nThe static data of a temporal property is not included temporal values (property `valueSequence`).\n\nAlso a user can retrieve the sub sequence of the temporal information of the temporal property data for the specified time interval with `subTemporalValue` query parameter. \nIn this case, `temporalProperties` property schema SHALL follows the [TemporalProperties object](https://docs.ogc.org/is/19-045r3/19-045r3.html#tproperties) in the OGC MF-JSON.\n",  # noqa
            "tags": [
                "TemporalProperty"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/datetime"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/limit"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/subtemporalvalue"  # noqa
                }
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/TemporalProperties"  # noqa
                },
                "400": {
                    "description": "A query parameter was not validly used."  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        },
        "post": {
            "operationId": "insertTemporalProperty",
            "summary": "Add temporal property data",
            "description": "A user SHOULD add new temporal property data into a moving feature with id `mFeatureId`.\n\nThe request body schema SHALL follows the [TemporalProperties object](https://docs.opengeospatial.org/is/19-045r3/19-045r3.html#tproperties) in the OGC MF-JSON.\n",  # noqa
            "tags": [
                "TemporalProperty"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                }
            ],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/schemas/temporalProperties-mfjson"  # noqa
                        },
                        "example": [
                            {
                                "datetimes": [
                                    "2011-07-14T22:01:01.450Z",
                                    "2011-07-14T23:01:01.450Z",
                                    "2011-07-15T00:01:01.450Z"
                                ],
                                "length": {
                                    "type": "Measure",
                                    "form": "http://qudt.org/vocab/quantitykind/Length",  # noqa
                                    "values": [
                                        1,
                                        2.4,
                                        1
                                    ],
                                    "interpolation": "Linear"
                                },
                                "discharge": {
                                    "type": "Measure",
                                    "form": "MQS",
                                    "values": [
                                        3,
                                        4,
                                        5
                                    ],
                                    "interpolation": "Step"
                                }
                            },
                            {
                                "datetimes": [
                                    "2011-07-14T22:01:01.450Z",
                                    "2011-07-14T23:01:01.450Z"
                                ],
                                "camera": {
                                    "type": "Image",
                                    "values": [
                                        "http://www.opengis.net/spec/movingfeatures/json/1.0/prism/example/image1",  # noqa
                                        "iVBORw0KGgoAAAANSUhEU......"
                                    ],
                                    "interpolation": "Discrete"
                                },
                                "labels": {
                                    "type": "Text",
                                    "values": [
                                        "car",
                                        "human"
                                    ],
                                    "interpolation": "Discrete"
                                }
                            }
                        ]
                    }
                }
            },
            "responses": {
                "201": {
                    "description": "Successful add more temporal property into a specified moving feature.\n",  # noqa
                    "headers": {
                        "Locations": {
                            "description": "A list of URI of the newly added resources",  # noqa
                            "schema": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "example": [
                                    "https://data.example.org/collections/mfc-1/items/mf-1/tproperties/length",  # noqa
                                    "https://data.example.org/collections/mfc-1/items/mf-1/tproperties/discharge",  # noqa
                                    "https://data.example.org/collections/mfc-1/items/mf-1/tproperties/camera",  # noqa
                                    "https://data.example.org/collections/mfc-1/items/mf-1/tproperties/labels"  # noqa
                                ]
                            }
                        }
                    }
                },
                "404": {
                    "description": "- A collection with the specified id was not found.\n- Or a moving feature with the specified id was not found.\n"  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        }
    }

    collections_collectionId_items_mFeatureId_tproperties_tPropertyName_path = '/collections/{collectionId}/items/{mFeatureId}/tproperties/{tPropertyName}'  # noqa
    paths[collections_collectionId_items_mFeatureId_tproperties_tPropertyName_path] = {  # noqa
        "get": {
            "operationId": "retrieveTemporalProperty",
            "summary": "Retrieve a temporal property",
            "description": "A user can retrieve only the temporal values with a specified name `tPropertyName` of temporal property.\n",  # noqa
            "tags": [
                "TemporalProperty"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/tPropertyName"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/datetime"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/leaf"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/subtemporalvalue"  # noqa
                }
            ],
            "responses": {
                "200": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/TemporalProperty"  # noqa
                },
                "400": {
                    "description": "A query parameter was not validly used."  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        },
        "post": {
            "operationId": "insertTemporalPrimitiveValue",
            "summary": "Add temporal primitive value data",
            "description": "A user SHOULD add more temporal primitive value data into a temporal property with id `tPropertyName`.\n",  # noqa
            "tags": [
                "TemporalProperty"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/tPropertyName"  # noqa
                }
            ],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/schemas/temporalPrimitiveValue"  # noqa
                        },
                        "example": {
                            "datetimes": [
                                "2011-07-15T08:00:00Z",
                                "2011-07-15T08:00:01Z",
                                "2011-07-15T08:00:02Z"
                            ],
                            "values": [
                                0,
                                20,
                                50
                            ],
                            "interpolation": "Linear"
                        }
                    }
                }
            },
            "responses": {
                "201": {
                    "description": "Successful add more temporal primitive value data into a specified temporal property.\n",  # noqa
                    "headers": {
                        "Location": {
                            "description": "A URI of the newly added resource",
                            "schema": {
                                "type": "string",
                                "example": "https://data.example.org/collections/mfc-1/items/mf-1/tproperties/tvalue/tpv-1"  # noqa
                            }
                        }
                    }
                },
                "404": {
                    "description": "- A collection with the specified id was not found.\n- Or a moving feature with the specified id was not found.\n- Or a temporal property with the specified id was not found.\n"  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        },
        "delete": {
            "operationId": "deleteTemporalProperty",
            "summary": "Delete a specified temporal property",
            "description": "The temporal property with id `tPropertyName` SHOULD be deleted.\n",  # noqa
            "tags": [
                "TemporalProperty"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/tPropertyName"  # noqa
                }
            ],
            "responses": {
                "204": {
                    "description": "Successfully deleted."
                },
                "404": {
                    "description": "- A collection with the specified id was not found.\n- Or a moving feature with the specified id was not found.\n- Or a temporal property with the specified id was not found.\n"  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        }
    }

    collections_collectionId_items_mFeatureId_tproperties_tPropertyName_tValueId_path = '/collections/{collectionId}/items/{mFeatureId}/tproperties/{tPropertyName}/{tValueId}'  # noqa
    paths[collections_collectionId_items_mFeatureId_tproperties_tPropertyName_tValueId_path] = {  # noqa
        "delete": {
            "operationId": "deleteTemporalPrimitiveValue",
            "summary": "Delete a singe temporal primitive value",
            "description": "The temporal primitive value with id `tValueId` SHOULD be deleted.\n",  # noqa
            "tags": [
                "TemporalProperty"
            ],
            "parameters": [
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/collectionId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/mFeatureId"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/tPropertyName"  # noqa
                },
                {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/parameters/tValueId"  # noqa
                }
            ],
            "responses": {
                "204": {
                    "description": "Successfully deleted."
                },
                "404": {
                    "description": "- A collection with the specified id was not found.\n- Or a moving feature with the specified id was not found.\n- Or a temporal property with the specified id was not found.\n- Or a temporal primitive primitive with the specified id was not found.\n"  # noqa
                },
                "500": {
                    "$ref": f"{OPENAPI_YAML['movingfeature']}#/components/responses/ServerError"  # noqa
                }
            }
        }
    }

    return [{'name': 'MovingFeatureCollection'}], {'paths': paths}
# fmt: on
