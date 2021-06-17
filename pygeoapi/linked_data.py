# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2019 Tom Kralidis
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

import logging

from pygeoapi.util import is_url
from pygeoapi import l10n
from shapely.geometry import asShape
from shapely.ops import unary_union

LOGGER = logging.getLogger(__name__)


def jsonldify(func):
    """
        Decorator that transforms app configuration\
        to include a JSON-LD representation

        :param func: decorated function

        :returns: `func`
    """

    def inner(*args, **kwargs):
        apireq = args[1]
        format_ = getattr(apireq, 'format', None)
        if not format_ == 'jsonld':
            return func(*args, **kwargs)
        # Function args have been pre-processed, so get locale from APIRequest
        locale_ = getattr(apireq, 'locale', None)
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
          "@id": cfg.get('server', {}).get('url', None),
          "url": cfg.get('server', {}).get('url', None),
          "name": l10n.translate(ident.get('title', None), locale_),
          "description": l10n.translate(
              ident.get('description', None), locale_),
          "keywords": l10n.translate(
              ident.get('keywords', None), locale_),
          "termsOfService": l10n.translate(
              ident.get('terms_of_service', None), locale_),
          "license": meta.get('license', {}).get('url', None),
          "provider": {
            "@type": "Organization",
            "name": l10n.translate(provider.get('name', None), locale_),
            "url": provider.get('url', None),
            "address": {
                "@type": "PostalAddress",
                "streetAddress": contact.get('address', None),
                "postalCode": contact.get('postalcode', None),
                "addressLocality": contact.get('city', None),
                "addressRegion": contact.get('stateorprovince', None),
                "addressCountry": contact.get('country', None)
            },
            "contactPoint": {
                "@type": "Contactpoint",
                "email": contact.get('email', None),
                "telephone": contact.get('phone', None),
                "faxNumber": contact.get('fax', None),
                "url": contact.get('url', None),
                "hoursAvailable": {
                    "opens": contact.get('hours', None),
                    "description": l10n.translate(
                        contact.get('instructions', None), locale_)
                },
                "contactType": l10n.translate(
                    contact.get('role', None), locale_),
                "description": l10n.translate(
                    contact.get('position', None), locale_)
            }
          }
        }
        cls.fcmld = fcmld
        return func(cls, *args[1:], **kwargs)
    return inner


def jsonldify_collection(cls, collection, locale_):
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
    interval = temporal_extent.get('interval', [[None, None]])

    spatial_extent = collection.get('extent', {}).get('spatial', {})
    bbox = spatial_extent.get('bbox', None)
    crs = spatial_extent.get('crs', None)
    hascrs84 = crs.endswith('CRS84')

    dataset = {
        "@type": "Dataset",
        "@id": "{}/collections/{}".format(
            cls.config['server']['url'],
            collection['id']
        ),
        "name": l10n.translate(collection['title'], locale_),
        "description": l10n.translate(collection['description'], locale_),
        "license": cls.fcmld['license'],
        "keywords": l10n.translate(collection.get('keywords', None), locale_),
        "spatial": None if (not hascrs84 or not bbox) else [{
            "@type": "Place",
            "geo": {
                "@type": "GeoShape",
                "box": '{},{} {},{}'.format(*_bbox[0:2], *_bbox[2:4])
            }
        } for _bbox in bbox],
        "temporalCoverage": None if not interval else "{}/{}".format(
            *interval[0]
        )
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


def geojson2jsonld(config, data, dataset, identifier=None, id_field='id'):
    """
        Render GeoJSON-LD from a GeoJSON base. Inserts a @context that can be
        read from, and extended by, the pygeoapi configuration for a particular
        dataset.

        :param config: dict of configuration
        :param data: dict of data:
        :param dataset: dataset identifier
        :param identifier: item identifier (optional)
        :param id_field: item identifier_field (optional)

        :returns: string of rendered JSON (GeoJSON-LD)
    """
    context = config['resources'][dataset].get('context', []).copy()
    defaultVocabulary = {
        'schema': 'https://schema.org/',
        id_field: '@id',
        'type': '@type'
    }

    if identifier:
        # Single jsonld
        defaultVocabulary.update({
            'geosparql': 'http://www.opengis.net/ont/geosparql#'
        })

        # Expand properties block
        data.update(data.pop('properties'))

        # Include multiple geometry encodings
        data['type'] = 'schema:Place'
        jsonldify_geometry(data)
        data[id_field] = identifier

    else:
        # Collection of jsonld
        defaultVocabulary.update({
            'features': 'schema:itemListElement',
            'FeatureCollection': 'schema:itemList'
        })

        data['@id'] = '{}/collections/{}/items/'.format(
            config['server']['url'], dataset
        )

        for i, feature in enumerate(data['features']):
            # Get URI for each feature
            identifier = feature.get(id_field,
                                     feature['properties'].get(id_field, ''))
            if not is_url(str(identifier)):
                identifier = '{}/collections/{}/items/{}'.format(
                    config['server']['url'], dataset, feature['id'])

            data['features'][i] = {
                id_field: identifier,
                'type': 'schema:Place'
            }

    if data.get('timeStamp', False):
        data['https://schema.org/sdDatePublished'] = data.pop('timeStamp')

    data['links'] = data.pop('links')

    ldjsonData = {
        '@context': [defaultVocabulary, *(context or [])],
        **data
    }

    return ldjsonData


def jsonldify_geometry(feature):
    """
        Render JSON-LD for feature with GeoJSON, Geosparql/WKT, and
        schema geometry encodings.

        :param feature: feature body to with GeoJSON geometry

        :returns: None
    """

    geo = feature.get('geometry')
    geom = asShape(geo)

    # GeoJSON geometry
    feature['geometry'] = feature.pop('geometry')

    # Geosparql geometry
    feature['geosparql:hasGeometry'] = {
        '@type': f'http://www.opengis.net/ont/sf#{geom.geom_type}',
        'geosparql:asWKT': {
            '@type': 'http://www.opengis.net/ont/geosparql#wktLiteral',
            '@value': f'{geom.wkt}'
        }
    }

    # Schema geometry
    feature['schema:geo'] = geom2schemageo(geom)


def geom2schemageo(geom):
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
        _ = [f'{x},{y}' for (x, y) in geom.coords[:]]
        f['schema:line'] = ' '.join(_)
        return f

    elif geom.geom_type == 'MultiLineString':
        points = list()
        [points.extend(p.coords[:]) for p in geom.geoms]
        _ = [f'{x},{y}' for (x, y) in points]
        f['schema:line'] = ' '.join(_)
        return f

    elif geom.geom_type == 'MultiPoint':
        poly_geom = [(p.x, p.y) for p in geom.geoms]
        poly_geom.append(poly_geom[0])

    elif geom.geom_type == 'Polygon':
        poly_geom = geom.exterior.coords[:]

    elif geom.geom_type == 'MultiPolygon':
        # MultiPolygon to Polygon (buffer of 0 helps ensure manifold polygon)
        poly = unary_union(geom.buffer(0))
        if poly.geom_type.startswith('Multi') or not poly.is_valid:
            LOGGER.debug('Invalid Poly: {}'.format(poly.geom_type))
            poly = poly.convex_hull
            LOGGER.debug('New Poly: {}'.format(poly.geom_type))
        poly_geom = poly.exterior.coords[:]

    else:
        poly_geom = list()
        for p in geom.geoms:
            try:
                poly_geom.extend(p.coords[:])
            except NotImplementedError:
                poly_geom.extend(p.exterior.coords[:])

    _ = [f'{x},{y}' for (x, y) in poly_geom]
    f['schema:polygon'] = ' '.join(_)
    return f
