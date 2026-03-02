# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Sander Schaminee <sander.schaminee@geocat.net>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2026 Tom Kralidis
# Copyright (c) 2026 Francesco Bartoli
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
# Copyright (c) 2023 Ricardo Garcia Silva
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
import logging

from pygeoapi import l10n
from pygeoapi.formats import (F_JSON, F_JSONLD, F_HTML, F_JPEG,
                              F_PNG, FORMAT_TYPES)
from pygeoapi.crs import DEFAULT_STORAGE_CRS, get_supported_crs_list
from pygeoapi.plugin import load_plugin
from pygeoapi.provider import get_provider_by_type, get_provider_default
from pygeoapi.provider.base import ProviderConnectionError, ProviderTypeError
from pygeoapi.util import dategetter, get_dataset_formatters

LOGGER = logging.getLogger(__name__)

OGC_RELTYPES_BASE = 'http://www.opengis.net/def/rel/ogc/1.0'


def gen_collection(api, request, dataset: str,
                   locale_: str) -> dict:
    """
    Generate OGC API Collection description

    :param api: `APIRequest` object
    :param dataset: `str` of dataset name
    :param locale_: `str` of requested locale

    :returns: `dict` of OGC API Collection description
    """

    config = api.config['resources'][dataset]

    data = {
        'id': dataset,
        'links': []
    }

    collection_data = get_provider_default(config['providers'])
    collection_data_type = collection_data['type']

    collection_data_format = None

    if 'format' in collection_data:
        collection_data_format = collection_data['format']

    is_vector_tile = (collection_data_type == 'tile' and
                      collection_data_format['name'] not
                      in [F_PNG, F_JPEG])

    data.update({
        'title': l10n.translate(config['title'], locale_),
        'description': l10n.translate(config['description'], locale_),
        'keywords': l10n.translate(config['keywords'], locale_),
    })

    extents = deepcopy(config['extents'])

    bbox = extents['spatial']['bbox']
    LOGGER.debug('Setting spatial extents from configuration')
    # The output should be an array of bbox, so if the user only
    # provided a single bbox, wrap it in a array.
    if not isinstance(bbox[0], list):
        bbox = [bbox]

    data['extent'] = {
        'spatial': {
            'bbox': bbox
        }
    }

    if 'crs' in extents['spatial']:
        data['extent']['spatial']['crs'] = extents['spatial']['crs']

    t_ext = extents.get('temporal', {})
    if t_ext:
        LOGGER.debug('Setting temporal extents from configuration')
        begins = dategetter('begin', t_ext)
        ends = dategetter('end', t_ext)
        data['extent']['temporal'] = {
            'interval': [[begins, ends]]
        }
        if 'trs' in t_ext:
            data['extent']['temporal']['trs'] = t_ext['trs']
        if 'resolution' in t_ext:
            data['extent']['temporal']['grid'] = {
                'resolution': t_ext['resolution']
            }
        if 'default' in t_ext:
            data['extent']['temporal']['default'] = t_ext['default']

    _ = extents.pop('spatial', None)
    _ = extents.pop('temporal', None)

    for ek, ev in extents.items():
        LOGGER.debug(f'Adding extent {ek}')
        data['extent'][ek] = {
            'definition': ev['url'],
            'interval': [ev['range']]
        }
        if 'units' in ev:
            data['extent'][ek]['unit'] = ev['units']

        if 'values' in ev:
            data['extent'][ek]['grid'] = {
                'cellsCount': len(ev['values']),
                'coordinates': ev['values']
            }

    LOGGER.debug('Processing configured collection links')
    for link in l10n.translate(config.get('links', []), locale_):
        lnk = {
            'type': link['type'],
            'rel': link['rel'],
            'title': l10n.translate(link['title'], locale_),
            'href': l10n.translate(link['href'], locale_),
        }
        if 'hreflang' in link:
            lnk['hreflang'] = l10n.translate(
                link['hreflang'], locale_)
        content_length = link.get('length', 0)

        if lnk['rel'] == 'enclosure' and content_length == 0:
            # Issue HEAD request for enclosure links without length
            lnk_headers = api.prefetcher.get_headers(lnk['href'])
            content_length = int(lnk_headers.get('content-length', 0))
            content_type = lnk_headers.get('content-type', lnk['type'])
            if content_length == 0:
                # Skip this (broken) link
                LOGGER.debug(f"Enclosure {lnk['href']} is invalid")
                continue
            if content_type != lnk['type']:
                # Update content type if different from specified
                lnk['type'] = content_type
                LOGGER.debug(
                    f"Fixed media type for enclosure {lnk['href']}")

        if content_length > 0:
            lnk['length'] = content_length

        data['links'].append(lnk)

    # TODO: provide translations
    LOGGER.debug('Adding JSON and HTML link relations')
    data['links'].extend([{
        'type': FORMAT_TYPES[F_JSON],
        'rel': 'root',
        'title': l10n.translate('The landing page of this server as JSON', locale_),  # noqa
        'href': f"{api.base_url}?f={F_JSON}"
    }, {
        'type': FORMAT_TYPES[F_HTML],
        'rel': 'root',
        'title': l10n.translate('The landing page of this server as HTML', locale_),  # noqa
        'href': f"{api.base_url}?f={F_HTML}"
    }, {
        'type': FORMAT_TYPES[F_JSON],
        'rel': request.get_linkrel(F_JSON),
        'title': l10n.translate('This document as JSON', locale_),
        'href': f'{api.get_collections_url()}/{dataset}?f={F_JSON}'
    }, {
        'type': FORMAT_TYPES[F_JSONLD],
        'rel': request.get_linkrel(F_JSONLD),
        'title': l10n.translate('This document as RDF (JSON-LD)', locale_),
        'href': f'{api.get_collections_url()}/{dataset}?f={F_JSONLD}'
    }, {
        'type': FORMAT_TYPES[F_HTML],
        'rel': request.get_linkrel(F_HTML),
        'title': l10n.translate('This document as HTML', locale_),
        'href': f'{api.get_collections_url()}/{dataset}?f={F_HTML}'
    }])

    if collection_data_type == 'record':
        data['links'].extend([{
            'type': FORMAT_TYPES[F_JSON],
            'rel': f'{OGC_RELTYPES_BASE}/ogc-catalog',
            'title': l10n.translate('Record catalogue as JSON', locale_),
            'href': f'{api.get_collections_url()}/{dataset}?f={F_JSON}'
        }, {
            'type': FORMAT_TYPES[F_HTML],
            'rel': f'{OGC_RELTYPES_BASE}/ogc-catalog',
            'title': l10n.translate('Record catalogue as HTML', locale_),
            'href': f'{api.get_collections_url()}/{dataset}?f={F_HTML}'
        }])

    if collection_data_type in ['feature', 'coverage', 'record']:
        data['links'].extend([{
            'type': 'application/schema+json',
            'rel': f'{OGC_RELTYPES_BASE}/schema',
            'title': l10n.translate('Schema of collection in JSON', locale_),
            'href': f'{api.get_collections_url()}/{dataset}/schema?f={F_JSON}'
        }, {
            'type': FORMAT_TYPES[F_HTML],
            'rel': f'{OGC_RELTYPES_BASE}/schema',
            'title': l10n.translate('Schema of collection in HTML', locale_),
            'href': f'{api.get_collections_url()}/{dataset}/schema?f={F_HTML}'
        }])

    if is_vector_tile or collection_data_type in ['feature', 'record']:
        # TODO: translate
        data['itemType'] = collection_data_type
        LOGGER.debug('Adding feature/record based links')
        data['links'].extend([{
            'type': 'application/schema+json',
            'rel': f'{OGC_RELTYPES_BASE}/queryables',
            'title': l10n.translate('Queryables for this collection as JSON', locale_),  # noqa
            'href': f'{api.get_collections_url()}/{dataset}/queryables?f={F_JSON}'  # noqa
        }, {
            'type': FORMAT_TYPES[F_HTML],
            'rel': f'{OGC_RELTYPES_BASE}/queryables',
            'title': l10n.translate('Queryables for this collection as HTML', locale_),  # noqa
            'href': f'{api.get_collections_url()}/{dataset}/queryables?f={F_HTML}'  # noqa
        }, {
            'type': 'application/geo+json',
            'rel': 'items',
            'title': l10n.translate('Items as GeoJSON', locale_),
            'href': f'{api.get_collections_url()}/{dataset}/items?f={F_JSON}'
        }, {
            'type': FORMAT_TYPES[F_JSONLD],
            'rel': 'items',
            'title': l10n.translate('Items as RDF (GeoJSON-LD)', locale_),
            'href': f'{api.get_collections_url()}/{dataset}/items?f={F_JSONLD}'
        }, {
            'type': FORMAT_TYPES[F_HTML],
            'rel': 'items',
            'title': l10n.translate('Items as HTML', locale_),  # noqa
            'href': f'{api.get_collections_url()}/{dataset}/items?f={F_HTML}'
        }])

        for key, value in get_dataset_formatters(config).items():
            data['links'].append({
                'type': value.mimetype,
                'rel': 'items',
                'title': l10n.translate(f'Items as {key}', locale_),  # noqa
                'href': f'{api.get_collections_url()}/{dataset}/items?f={value.f}'  # noqa
            })

    # OAPIF Part 2 - list supported CRSs and StorageCRS
    if collection_data_type in ['edr', 'feature']:
        data['crs'] = get_supported_crs_list(collection_data)
        data['storageCrs'] = collection_data.get('storage_crs', DEFAULT_STORAGE_CRS)  # noqa
        if 'storage_crs_coordinate_epoch' in collection_data:
            data['storageCrsCoordinateEpoch'] = collection_data.get('storage_crs_coordinate_epoch')  # noqa

    elif collection_data_type == 'coverage':
        LOGGER.debug('Adding coverage based links')
        data['links'].append({
            'type': 'application/prs.coverage+json',
            'rel': f'{OGC_RELTYPES_BASE}/coverage',
            'title': l10n.translate('Coverage data', locale_),
            'href': f'{api.get_collections_url()}/{dataset}/coverage?f={F_JSON}'  # noqa
        })
        if collection_data_format is not None:
            title_ = l10n.translate('Coverage data as', locale_)
            title_ = f"{title_} {collection_data_format['name']}"
            data['links'].append({
                'type': collection_data_format['mimetype'],
                'rel': f'{OGC_RELTYPES_BASE}/coverage',
                'title': title_,
                'href': f"{api.get_collections_url()}/{dataset}/coverage?f={collection_data_format['name']}"  # noqa
            })
        if dataset is not None:
            LOGGER.debug('Creating extended coverage metadata')
            try:
                provider_def = get_provider_by_type(
                    api.config['resources'][dataset]['providers'],
                    'coverage')
                p = load_plugin('provider', provider_def)
            except ProviderConnectionError:
                raise
            except ProviderTypeError:
                pass
            else:
                data['extent']['spatial']['grid'] = [{
                    'cellsCount': p._coverage_properties['width'],
                    'resolution': p._coverage_properties['resx']
                }, {
                    'cellsCount': p._coverage_properties['height'],
                    'resolution': p._coverage_properties['resy']
                }]
                if 'time_range' in p._coverage_properties:
                    data['extent']['temporal'] = {
                        'interval': [p._coverage_properties['time_range']]
                    }
                    if 'restime' in p._coverage_properties:
                        data['extent']['temporal']['grid'] = {
                            'resolution': p._coverage_properties['restime']
                        }
                if 'uad' in p._coverage_properties:
                    data['extent'].update(p._coverage_properties['uad'])

    try:
        tile = get_provider_by_type(config['providers'], 'tile')
        p = load_plugin('provider', tile)
    except ProviderConnectionError:
        raise
    except ProviderTypeError:
        tile = None

    if tile:
        LOGGER.debug('Adding tile links')
        data['links'].extend([{
            'type': FORMAT_TYPES[F_JSON],
            'rel': f'{OGC_RELTYPES_BASE}/tilesets-{p.tile_type}',
            'title': l10n.translate('Tiles as JSON', locale_),
            'href': f'{api.get_collections_url()}/{dataset}/tiles?f={F_JSON}'
        }, {
            'type': FORMAT_TYPES[F_HTML],
            'rel': f'{OGC_RELTYPES_BASE}/tilesets-{p.tile_type}',
            'title': l10n.translate('Tiles as HTML', locale_),
            'href': f'{api.get_collections_url()}/{dataset}/tiles?f={F_HTML}'
        }])

    try:
        map_ = get_provider_by_type(config['providers'], 'map')
        p = load_plugin('provider', map_)
    except ProviderTypeError:
        map_ = None

    if map_:
        LOGGER.debug('Adding map links')

        map_mimetype = map_['format']['mimetype']
        map_format = map_['format']['name']

        title_ = l10n.translate('Map as', locale_)
        title_ = f'{title_} {map_format}'

        data['links'].append({
            'type': map_mimetype,
            'rel': f'{OGC_RELTYPES_BASE}/map',
            'title': title_,
            'href': f'{api.get_collections_url()}/{dataset}/map?f={map_format}'
        })

        if p._fields:
            schema_reltype = f'{OGC_RELTYPES_BASE}/schema',
            schema_links = [s for s in data['links'] if
                            schema_reltype in s]

            if not schema_links:
                title_ = l10n.translate('Schema of collection in JSON', locale_)  # noqa
                data['links'].append({
                    'type': 'application/schema+json',
                    'rel': f'{OGC_RELTYPES_BASE}/schema',
                    'title': title_,
                    'href': f'{api.get_collections_url()}/{dataset}/schema?f=json'  # noqa
                })
                title_ = l10n.translate('Schema of collection in HTML', locale_)  # noqa
                data['links'].append({
                    'type': 'text/html',
                    'rel': f'{OGC_RELTYPES_BASE}/schema',
                    'title': title_,
                    'href': f'{api.get_collections_url()}/{dataset}/schema?f=html'  # noqa
                })

    try:
        edr = get_provider_by_type(config['providers'], 'edr')
        p = load_plugin('provider', edr)
    except ProviderConnectionError:
        raise
    except ProviderTypeError:
        edr = None

    if edr:
        # TODO: translate
        LOGGER.debug('Adding EDR links')
        data['data_queries'] = {}
        parameters = p.get_fields()
        if parameters:
            data['parameter_names'] = {}
            for key, value in parameters.items():
                data['parameter_names'][key] = {
                    'id': key,
                    'type': 'Parameter',
                    'name': value['title'],
                    'observedProperty': {
                        'label': {
                            'id': key,
                            'en': value['title']
                        },
                    },
                    'unit': {
                        'label': {
                            'en': value['title']
                        },
                        'symbol': {
                            'value': value['x-ogc-unit'],
                            'type': 'http://www.opengis.net/def/uom/UCUM/'
                        }
                    }
                }

                data['parameter_names'][key].update({
                    'description': value['description']}
                        if 'description' in value else {}
                )

        for qt in p.get_query_types():
            data_query = {
                'link': {
                    'href': f'{api.get_collections_url()}/{dataset}/{qt}',
                    'rel': 'data',
                    'variables': {
                        'query_type': qt
                    }
                }
            }

            if request.format is not None and request.format == 'json':
                data_query['link']['type'] = 'application/vnd.cov+json'

            data['data_queries'][qt] = data_query

            title1 = l10n.translate('query for this collection as JSON', locale_)  # noqa
            title1 = f'{qt} {title1}'
            title2 = l10n.translate('query for this collection as HTML', locale_)  # noqa
            title2 = f'{qt} {title2}'

            data['links'].extend([{
                'type': 'application/json',
                'rel': 'data',
                'title': title1,
                'href': f'{api.get_collections_url()}/{dataset}/{qt}?f={F_JSON}'  # noqa
            }, {
                'type': FORMAT_TYPES[F_HTML],
                'rel': 'data',
                'title': title2,
                'href': f'{api.get_collections_url()}/{dataset}/{qt}?f={F_HTML}'  # noqa 
            }])

            for key, value in get_dataset_formatters(config).items():
                title3 = f'{qt} query for this collection as {key}'
                data['links'].append({
                    'type': value.mimetype,
                    'rel': 'data',
                    'title': title3,
                    'href': f'{api.get_collections_url()}/{dataset}/{qt}?f={value.f}'  # noqa
                })

    return data
