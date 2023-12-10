# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
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

""" Linked data capabilities
Returns content as linked data representations
"""

import json
import logging
from typing import Callable

from pygeoapi.util import is_url, render_j2_template
from pygeoapi import l10n
from shapely.geometry import shape
from shapely.ops import unary_union

LOGGER = logging.getLogger(__name__)


def jsonldify(func: Callable) -> Callable:
    """
    Decorator that transforms app configuration\
    to include a JSON-LD representation

    :param func: decorated function

    :returns: `func`
    """

    def inner(*args, **kwargs):
        apireq = args[1]
        format_ = getattr(apireq, 'format')
        if not format_ == 'jsonld':
            return func(*args, **kwargs)
        # Function args have been pre-processed, so get locale from APIRequest
        locale_ = getattr(apireq, 'locale')
        LOGGER.debug('Creating JSON-LD representation')
        cls = args[0]
        cfg = cls.config
        meta = cfg.get('metadata', {})
        contact = meta.get('contact', {})
        provider = meta.get('provider', {})
        ident = meta.get('identification', {})
        fcmld = {
          "@context": "https://schema.org/docs/jsonldcontext.jsonld",
          "@type": "DataCatalog",
          "@id": cfg.get('server', {}).get('url'),
          "url": cfg.get('server', {}).get('url'),
          "name": l10n.translate(ident.get('title'), locale_),
          "description": l10n.translate(
              ident.get('description'), locale_),
          "keywords": l10n.translate(
              ident.get('keywords'), locale_),
          "termsOfService": l10n.translate(
              ident.get('terms_of_service'), locale_),
          "license": meta.get('license', {}).get('url'),
          "provider": {
            "@type": "Organization",
            "name": l10n.translate(provider.get('name'), locale_),
            "url": provider.get('url'),
            "address": {
                "@type": "PostalAddress",
                "streetAddress": contact.get('address'),
                "postalCode": contact.get('postalcode'),
                "addressLocality": contact.get('city'),
                "addressRegion": contact.get('stateorprovince'),
                "addressCountry": contact.get('country')
            },
            "contactPoint": {
                "@type": "Contactpoint",
                "email": contact.get('email'),
                "telephone": contact.get('phone'),
                "faxNumber": contact.get('fax'),
                "url": contact.get('url'),
                "hoursAvailable": {
                    "opens": contact.get('hours'),
                    "description": l10n.translate(
                        contact.get('instructions'), locale_)
                },
                "contactType": l10n.translate(
                    contact.get('role'), locale_),
                "description": l10n.translate(
                    contact.get('position'), locale_)
            }
          }
        }
        cls.fcmld = fcmld
        return func(cls, *args[1:], **kwargs)
    return inner


def jsonldify_collection(cls, collection: dict, locale_: str) -> dict:
    """
    Transforms collection into a JSON-LD representation

    :param cls: API object
    :param collection: `collection` as prepared for non-LD JSON
                       representation
    :param locale_: The locale to use for translations (if supported)

    :returns: `collection` a dictionary, mapped into JSON-LD, of
              type schema:Dataset
    """
    temporal_extent = collection.get('extent', {}).get('temporal', {})
    interval = temporal_extent.get('interval')
    if interval is not None:
        interval = f'{interval[0][0]}/{interval[0][1]}'

    spatial_extent = collection.get('extent', {}).get('spatial', {})
    bbox = spatial_extent.get('bbox')
    crs = spatial_extent.get('crs')
    hascrs84 = crs.endswith('CRS84')

    dataset = {
        "@type": "Dataset",
        "@id": f"{cls.base_url}/collections/{collection['id']}",
        "name": l10n.translate(collection['title'], locale_),
        "description": l10n.translate(collection['description'], locale_),
        "license": cls.fcmld['license'],
        "keywords": l10n.translate(collection.get('keywords'), locale_),
        "spatial": None if (not hascrs84 or not bbox) else [{
            "@type": "Place",
            "geo": {
                "@type": "GeoShape",
                "box": f'{_bbox[0]},{_bbox[1]} {_bbox[2]},{_bbox[3]}'
            }
        } for _bbox in bbox],
        "temporalCoverage": interval
    }
    dataset['url'] = dataset['@id']

    links = collection.get('links', [])
    if links:
        dataset['distribution'] = list(map(lambda link: {k: v for k, v in {
            "@type": "DataDownload",
            "contentURL": link['href'],
            "encodingFormat": link['type'],
            "description": l10n.translate(link['title'], locale_),
            "inLanguage": link.get(
                'hreflang', l10n.locale2str(cls.default_locale)
            ),
            "author": link['rel'] if link.get(
                'rel', None
            ) == 'author' else None
        }.items() if v is not None}, links))

    return dataset


def geojson2jsonld(cls, data: dict, dataset: str,
                   identifier: str = None, id_field: str = 'id') -> str:
    """
    Render GeoJSON-LD from a GeoJSON base. Inserts a @context that can be
    read from, and extended by, the pygeoapi configuration for a particular
    dataset.

    :param cls: API object
    :param data: dict of data:
    :param dataset: dataset identifier
    :param identifier: item identifier (optional)
    :param id_field: item identifier_field (optional)

    :returns: string of rendered JSON (GeoJSON-LD)
    """

    LOGGER.debug('Fetching context and template from resource configuration')
    jsonld = cls.config['resources'][dataset].get('linked-data', {})
    ds_url = f"{cls.get_collections_url()}/{dataset}"

    context = jsonld.get('context', []).copy()
    template = jsonld.get('item_template', None)

    defaultVocabulary = {
        'schema': 'https://schema.org/',
        'type': '@type'
    }

    if identifier:
        # Single jsonld
        defaultVocabulary.update({
            'gsp': 'http://www.opengis.net/ont/geosparql#'
        })

        # Expand properties block
        data.update(data.pop('properties'))

        # Include multiple geometry encodings
        if (data.get('geometry') is not None):
            data['type'] = 'schema:Place'
            jsonldify_geometry(data)

        data['@id'] = identifier

    else:
        # Collection of jsonld
        defaultVocabulary.update({
            'features': 'schema:itemListElement',
            'FeatureCollection': 'schema:itemList'
        })

        data['@id'] = ds_url

        for i, feature in enumerate(data['features']):
            # Get URI for each feature
            identifier_ = feature.get(id_field,
                                      feature['properties'].get(id_field, ''))
            if not is_url(str(identifier_)):
                identifier_ = f"{ds_url}/items/{feature['id']}"  # noqa

            data['features'][i] = {
                '@id': identifier_,
                'type': 'schema:Place'
            }

    if data.get('timeStamp', False):
        data['https://schema.org/sdDatePublished'] = data.pop('timeStamp')

    data['links'] = data.pop('links')

    ldjsonData = {
        '@context': [defaultVocabulary, *(context or [])],
        **data
    }

    if None in (template, identifier):
        return ldjsonData
    else:
        # Render jsonld template for single item with template configured
        LOGGER.debug(f'Rendering JSON-LD template: {template}')
        content = render_j2_template(cls.config, template, ldjsonData)
        ldjsonData = json.loads(content)
        return ldjsonData


def jsonldify_geometry(feature: dict) -> None:
    """
    Render JSON-LD for feature with GeoJSON, Geosparql/WKT, and
    schema geometry encodings.

    :param feature: feature body to with GeoJSON geometry

    :returns: None
    """

    geo = feature.get('geometry')
    geom = shape(geo)

    # GeoJSON geometry
    feature['geometry'] = feature.pop('geometry')

    # Geosparql geometry
    feature['gsp:hasGeometry'] = {
        '@type': f'http://www.opengis.net/ont/sf#{geom.geom_type}',
        'gsp:asWKT': {
            '@type': 'http://www.opengis.net/ont/geosparql#wktLiteral',
            '@value': f'{geom.wkt}'
        }
    }

    # Schema geometry
    feature['schema:geo'] = geom2schemageo(geom)


def geom2schemageo(geom: shape) -> dict:
    """
    Render Schema Geometry from a GeoJSON base.

    :param geom: shapely geom of feature

    :returns: dict of rendered schema:geo geometry
    """
    f = {'@type': 'schema:GeoShape'}
    if geom.geom_type == 'Point':
        return {
            '@type': 'schema:GeoCoordinates',
            'schema:longitude': geom.x,
            'schema:latitude': geom.y
        }

    elif geom.geom_type == 'LineString':
        points = [f'{x},{y}' for (x, y, *_) in geom.coords[:]]
        f['schema:line'] = ' '.join(points)
        return f

    elif geom.geom_type == 'MultiLineString':
        points = list()
        for line in geom.geoms:
            points.extend([f'{x},{y}' for (x, y, *_) in line.coords[:]])
        f['schema:line'] = ' '.join(points)
        return f

    elif geom.geom_type == 'MultiPoint':
        points = [(x, y) for pt in geom.geoms for (x, y, *_) in pt.coords]
        points.append(points[0])

    elif geom.geom_type == 'Polygon':
        points = geom.exterior.coords[:]

    elif geom.geom_type == 'MultiPolygon':
        # MultiPolygon to Polygon (buffer of 0 helps ensure manifold polygon)
        poly = unary_union(geom.buffer(0))
        if poly.geom_type.startswith('Multi') or not poly.is_valid:
            LOGGER.debug(f'Invalid MultiPolygon: {poly.geom_type}')
            poly = poly.convex_hull
            LOGGER.debug(f'New MultiPolygon: {poly.geom_type}')
        points = poly.exterior.coords[:]

    else:
        points = list()
        for p in geom.geoms:
            try:
                points.extend(p.coords[:])
            except NotImplementedError:
                points.extend(p.exterior.coords[:])

    schema_polygon = [f'{x},{y}' for (x, y, *_) in points]

    f['schema:polygon'] = ' '.join(schema_polygon)

    return f
