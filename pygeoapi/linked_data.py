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

import json
import logging

from pygeoapi.util import is_url

LOGGER = logging.getLogger(__name__)


def jsonldify(func):
    """
        Decorator that transforms app configuration\
        to include a JSON-LD representation

        :param func: decorated function

        :returns: `func`
    """

    def inner(*args, **kwargs):
        format_ = args[2]
        if not format_ == 'jsonld':
            return func(*args, **kwargs)
        LOGGER.debug('Creating JSON-LD representation')
        cls = args[0]
        cfg = cls.config
        meta = cfg.get('metadata', {})
        contact = meta.get('contact', {})
        provider = meta.get('provider', {})
        ident = meta.get('identification', {})
        fcmld = {
          "@context": "https://schema.org",
          "@type": "DataCatalog",
          "@id": cfg.get('server', {}).get('url', None),
          "url": cfg.get('server', {}).get('url', None),
          "name": ident.get('title', None),
          "description": ident.get('description', None),
          "keywords": ident.get('keywords', None),
          "termsOfService": ident.get('terms_of_service', None),
          "license": meta.get('license', {}).get('url', None),
          "provider": {
            "@type": "Organization",
            "name": provider.get('name', None),
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
                    "description": contact.get('instructions', None)
                },
                "contactType": contact.get('role', None),
                "description": contact.get('position', None)
            }
          }
        }
        cls.fcmld = fcmld
        return func(cls, *args[1:], **kwargs)
    return inner


def jsonldify_collection(cls, collection):
    """
        Transforms collection into a JSON-LD representation

        :param cls: API object
        :param collection: `collection` as prepared for non-LD JSON
                           representation

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
        "name": collection['title'],
        "description": collection['description'],
        "license": cls.fcmld['license'],
        "keywords": collection.get('keywords', None),
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
            "description": link['title'],
            "inLanguage": link.get(
                'hreflang', cls.config.get('server', {}).get('language', None)
            ),
            "author": link['rel'] if link.get(
                'rel', None
            ) == 'author' else None
        }.items() if v is not None}, links))

    return dataset


def geojson2geojsonld(config, data, dataset, identifier=None):
    """
    Render GeoJSON-LD from a GeoJSON base. Inserts a @context that can be
    read from, and extended by, the pygeoapi configuration for a particular
    dataset.

    :param config: dict of configuration
    :param data: dict of data:
    :param dataset: dataset identifier
    :param identifier: item identifier (optional)

    :returns: string of rendered JSON (GeoJSON-LD)
    """
    context = config['resources'][dataset].get('context', [])
    data['id'] = (
        '{uri}' if identifier
        else '{url}/collections/{ds}/items'
    ).format(
        *[uri=data['properties']['uri'],url=config['server']['url'], ds=dataset]
    )
    if data.get('timeStamp', False):
        data['https://schema.org/sdDatePublished'] = data.pop('timeStamp')
    defaultVocabulary = "https://geojson.org/geojson-ld/geojson-context.jsonld"
    ldjsonData = {
        "@context": [defaultVocabulary, *(context or [])],
        **data
    }
    isCollection = identifier is None
    if isCollection:
        for i, feature in enumerate(data['features']):
            featureId = feature.get(
                'id', None
            ) or feature.get('properties', {}).get('id', None)
            if featureId is None:
                continue
            # Note: @id or https://schema.org/url or both or something else?
            if is_url(str(featureId)):
                feature['id'] = featureId
            else:
                feature['id'] = '{}/{}'.format(data['id'], featureId)

    return json.dumps(ldjsonData)
