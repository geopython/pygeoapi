# =================================================================
#
# Authors: yves.choquette <yves.choquette@NRCan-RNCan.gc.ca>
#
# Copyright (c) 2022 Yves Choquette
# Copyright (c) 2023 Tom Kralidis
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

import requests
import logging
import os
import json

from pygeoapi.provider.base import (BaseProvider, ProviderNotFoundError)
from pygeoapi.util import url_join

LOGGER = logging.getLogger(__name__)


class HateoasProvider(BaseProvider):
    """HateoasProvider Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.hateoas.HateoasProvider
        """

        super().__init__(provider_def)

    def get_data_path(self, baseurl, urlpath, entrypath):
        """
        Gets directory listing or file description or raw file dump

        :param baseurl: base URL of endpoint
        :param urlpath: base path of URL
        :param entrypath: basepath of the entry selected (equivalent of URL)

        :returns: `dict` of catalogs/collections or `dict` of GeoJSON item
        """

        thispath = os.path.join(baseurl, urlpath)

        resource_type = None
        root_link = None
        child_links = []

        data_path = self.data + entrypath

        if '/' not in entrypath:  # root
            root_link = baseurl
        else:
            parentpath = url_join(thispath, '.')
            child_links.append({
                'rel': 'parent',
                'href': f'{parentpath}?f=json',
                'type': 'application/json'
            })
            child_links.append({
                'rel': 'parent',
                'href': parentpath,
                'type': 'text/html'
            })

            depth = entrypath.count('/')
            root_path = '/'.replace('/', '../' * depth, 1)
            root_link = url_join(thispath, root_path)

        content = {
            'links': [{
                'rel': 'root',
                'href': f'{root_link}?f=json',
                'type': 'application/json'
                }, {
                'rel': 'root',
                'href': root_link,
                'type': 'text/html'
                }, {
                'rel': 'self',
                'href': f'{thispath}?f=json',
                'type': 'application/json',
                }, {
                'rel': 'self',
                'href': thispath,
                'type': 'text/html'
                }
            ]
        }

        LOGGER.debug('Checking if path exists as Catalog, Collection or Asset')
        try:
            jsondata = _get_json_data(f'{data_path}/catalog.json')
            resource_type = 'Catalog'
        except Exception:
            try:
                jsondata = _get_json_data(f'{data_path}/collection.json')
                resource_type = 'Collection'
            except Exception:
                try:
                    filename = os.path.basename(data_path)
                    jsondata = _get_json_data(f'{data_path}/{filename}.json')
                    resource_type = 'Assets'
                except Exception:
                    msg = f'Resource does not exist: {data_path}'
                    LOGGER.error(msg)
                    raise ProviderNotFoundError(msg)

        if resource_type == 'Catalog' or resource_type == 'Collection':
            content['type'] = resource_type

            link_href_list = []
            for link in jsondata["links"]:
                if resource_type in ['Catalog', 'Collection'] \
                   and link["rel"] in ["child", "item"]:
                    link_href_list.append(link["href"].replace('\\', '/'))
            link_href_list.sort()

            for link in link_href_list:
                unused, path_ending, entry_type = link.split('/')
                newpath = os.path.join(baseurl, urlpath, path_ending).replace('\\', '/') # noqa

                if entry_type == 'catalog.json':
                    child_links.append({
                        'rel': 'child',
                        'href': newpath,
                        'type': 'text/html',
                        'created': "-",
                        'entry:type': 'Catalog'
                    })
                elif entry_type == 'collection.json':
                    child_links.append({
                        'rel': 'child',
                        'href': newpath,
                        'type': 'text/html',
                        'created': "-",
                        'entry:type': 'Collection'
                    })
                else:
                    child_links.append({
                        'rel': 'item',
                        'href': newpath,
                        'title': path_ending,
                        'created': "-",
                        'entry:type': 'Item'
                    })

            if resource_type == "Collection" and len(link_href_list) == 0:
                content = jsondata
                content = _modify_content_for_display(
                    content,
                    baseurl,
                    urlpath
                )

        elif resource_type == 'Assets':
            content = jsondata
            content = _modify_content_for_display(content, baseurl, urlpath)

        content['links'].extend(child_links)

        return content

    def __repr__(self):
        return f'<HateoasProvider> {self.data}'


def _modify_content_for_display(
        content: dict,
        baseurl: str,
        urlpath: str) -> dict:
    """
    Helper function to fill in required information for HTML display.

    :param content: `dict` of JSON item
    :param baseurl: base URL of endpoint
    :param urlpath: base path of URL

    :returns: `dict` of JSON item
    """
    content['assets']['default'] = {
        'href': os.path.join(baseurl, urlpath).replace('\\', '/'),
    }
    for key in content['assets']:
        content['assets'][key]['file:size'] = 0
        try:
            content['assets'][key]['created'] = content["properties"]["datetime"] # noqa
        except Exception as err:
            LOGGER.debug(err)
            LOGGER.debug('no properties included in STAC')
    return content


def _get_json_data(jsonpath):
    """
    Helper function used to load a json file that is located on the WEB
    (HTTP request) or on the server file system

    :param jsonpath: path to the json file

    :returns: `dict` of JSON item
    """

    if jsonpath[0:4].upper() == 'HTTP':
        jsondata = requests.get(jsonpath).json()
    else:
        with open(jsonpath) as fh:
            jsondata = json.load(fh)

    return jsondata
