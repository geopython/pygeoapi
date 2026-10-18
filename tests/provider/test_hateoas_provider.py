# =================================================================
#
# Authors: Ashutosh Panda <ashutoshpanda.india@gmail.com>
#
# Copyright (c) 2026 Ashutosh Panda
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

import json
import os

import pytest

from pygeoapi.provider.hateoas import HateoasProvider


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as fh:
        json.dump(content, fh)


def _item(item_id):
    return {
        'type': 'Feature',
        'id': item_id,
        'assets': {},
        'properties': {'datetime': '2026-01-01T00:00:00Z'},
        'links': []
    }


def _collection(collection_id, hrefs):
    return {
        'type': 'Collection',
        'id': collection_id,
        'license': 'MIT',
        'links': [{'rel': 'item', 'href': href} for href in hrefs]
    }


@pytest.fixture()
def config(tmp_path):
    # shared-folder layout: items/<id>.json, as recommended by the
    # STAC catalog layout best practices
    shared = tmp_path / 'sharedcol'
    _write(str(shared / 'collection.json'), _collection(
        'sharedcol', ['./items/item-a.json', './items/item-b.json']))
    _write(str(shared / 'items' / 'item-a.json'), _item('item-a'))
    _write(str(shared / 'items' / 'item-b.json'), _item('item-b'))

    # legacy layout: <id>/<id>.json
    legacy = tmp_path / 'legacycol'
    _write(str(legacy / 'collection.json'), _collection(
        'legacycol', ['./item-a/item-a.json', './item-b/item-b.json']))
    _write(str(legacy / 'item-a' / 'item-a.json'), _item('item-a'))
    _write(str(legacy / 'item-b' / 'item-b.json'), _item('item-b'))

    return {
        'name': 'Hateoas',
        'type': 'stac',
        'data': str(tmp_path)
    }


def _item_links(content):
    return [link for link in content['links'] if link['rel'] == 'item']


def test_get_data_path_shared_folder_items(config):
    p = HateoasProvider(config)

    r = p.get_data_path('http://example.org/stac', 'sharedcol',
                        '/sharedcol')

    links = _item_links(r)
    assert [link['title'] for link in links] == ['item-a', 'item-b']
    assert [link['href'] for link in links] == [
        'http://example.org/stac/sharedcol/item-a',
        'http://example.org/stac/sharedcol/item-b'
    ]


def test_get_data_path_shared_folder_item(config):
    p = HateoasProvider(config)

    r = p.get_data_path('http://example.org/stac', 'sharedcol/item-a',
                        '/sharedcol/item-a')

    assert r['id'] == 'item-a'


def test_get_data_path_legacy_layout_items(config):
    p = HateoasProvider(config)

    r = p.get_data_path('http://example.org/stac', 'legacycol',
                        '/legacycol')

    links = _item_links(r)
    assert [link['title'] for link in links] == ['item-a', 'item-b']
    assert [link['href'] for link in links] == [
        'http://example.org/stac/legacycol/item-a',
        'http://example.org/stac/legacycol/item-b'
    ]

    r = p.get_data_path('http://example.org/stac', 'legacycol/item-b',
                        '/legacycol/item-b')

    assert r['id'] == 'item-b'
