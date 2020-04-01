# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
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

import io
import logging
import os
from urllib.parse import urljoin

from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
                                    ProviderNotFoundError)

LOGGER = logging.getLogger(__name__)


class FileSystemProvider(BaseProvider):
    """filesystem Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.filesystem.FileSystemProvider
        """

        BaseProvider.__init__(self, provider_def)

        if not os.path.exists(self.data):
            msg = 'Directory does not exist: {}'.format(self.data)
            LOGGER.error(msg)
            raise ProviderConnectionError(msg)

    def get_data_path(self, baseurl, urlpath, dirpath):
        """
        Gets directory listing or file description or raw file dump

        :param baseurl: base URL of endpoint
        :param urlpath: base path of URL
        :param dirpath: directory basepath (equivalent of URL)

        :returns: `dict` of file listing or `dict` of GeoJSON item or raw file
        """

        thispath = os.path.join(baseurl, urlpath)
        resource_type = None
        root_link = None
        child_links = []

        data_path = os.path.join(self.data, dirpath)
        data_path = self.data + dirpath

        if '/' not in dirpath:  # root
            root_link = baseurl
        else:
            parentpath = urljoin(thispath, '.')
            child_links.append({
                'rel': 'parent',
                'href': '{}?f=json'.format(parentpath),
                'type': 'application/json'
            })
            child_links.append({
                'rel': 'parent',
                'href': parentpath,
                'type': 'text/html'
            })

            depth = dirpath.count('/')
            root_path = '/'.replace('/', '../' * depth, 1)
            root_link = urljoin(thispath, root_path)

        content = {
            'links': [{
                'rel': 'root',
                'href': '{}?f=json'.format(root_link),
                'type': 'application/json'
                }, {
                'rel': 'root',
                'href': root_link,
                'type': 'text/html'
                }, {
                'rel': 'self',
                'href': '{}?f=json'.format(thispath),
                'type': 'application/json',
                }, {
                'rel': 'self',
                'href': thispath,
                'type': 'text/html'
                }
            ]
        }

        LOGGER.debug('Checking if path exists as raw file or directory')
        if data_path.endswith(tuple(self.file_types)):
            resource_type = 'raw_file'
        elif os.path.exists(data_path):
            resource_type = 'directory'
        else:
            LOGGER.debug('Checking if path exists as file via file_types')
            for ft in self.file_types:
                tmp_path = '{}{}'.format(data_path, ft)
                if os.path.exists(tmp_path):
                    resource_type = 'file'
                    data_path = tmp_path
                    break

        if resource_type is None:
            msg = 'Resource does not exist: {}'.format(data_path)
            LOGGER.error(msg)
            raise ProviderNotFoundError(msg)

        if resource_type == 'raw_file':
            with io.open(data_path, 'rb') as fh:
                return fh.read()

        elif resource_type == 'directory':
            for dc in os.listdir(data_path):
                fullpath = os.path.join(data_path, dc)
                if os.path.isdir(fullpath):
                    newpath = os.path.join(baseurl, urlpath, dc)
                    child_links.append({
                        'rel': 'child',
                        'href': '{}?f=json'.format(newpath),
                        'type': 'application/json'
                    })
                    child_links.append({
                        'rel': 'child',
                        'href': newpath,
                        'type': 'text/html'
                    })
                elif os.path.isfile(fullpath):
                    basename, extension = os.path.splitext(dc)
                    newpath = os.path.join(baseurl, urlpath, basename)
                    if extension in self.file_types:
                        child_links.append({
                            'rel': 'item',
                            'href': '{}?f=json'.format(newpath),
                            'type': 'application/json'
                        })
                        child_links.append({
                            'rel': 'item',
                            'href': newpath,
                            'type': 'text/html'
                        })

        elif resource_type == 'file':
            filename = os.path.basename(data_path)
            id_ = os.path.splitext(filename)[0]
            content['id'] = id_
            content['type'] = 'Feature'
            content['properties'] = {}
            content['assets'] = {}

            content.update(_describe_file(data_path))

            content['assets']['default'] = {
                'href': './{}'.format(filename)
            }

        content['links'].extend(child_links)

        return content

    def __repr__(self):
        return '<FileSystemProvider> {}'.format(self.data)


def _describe_file(filepath):
    """
    Helper function to describe a geospatial data

    :param filepath: path to file

    :returns: `dict` of GeoJSON item
    """

    import fiona
    import rasterio

    content = {'properties': {}}

    try:  # raster
        LOGGER.debug('Testing raster data detection')
        d = rasterio.open(filepath)
        content['bbox'] = [
            d.bounds.left,
            d.bounds.bottom,
            d.bounds.right,
            d.bounds.top
        ]
        content['geometry'] = {
            'type': 'Polygon',
            'coordinates': [[
                [d.bounds.left, d.bounds.bottom],
                [d.bounds.left, d.bounds.top],
                [d.bounds.right, d.bounds.top],
                [d.bounds.right, d.bounds.bottom],
                [d.bounds.left, d.bounds.bottom]
            ]]
        }
        for k, v in d.tags(1).items():
            content['properties'][k] = v
    except rasterio.errors.RasterioIOError:
        LOGGER.debug('Testing vector data detection')
        d = fiona.open(filepath)
        content['bbox'] = [
            d.bounds[0],
            d.bounds[1],
            d.bounds[2],
            d.bounds[3]
        ]
        content['geometry'] = {
            'type': 'Polygon',
            'coordinates': [[
                [d.bounds[0], d.bounds[1]],
                [d.bounds[0], d.bounds[3]],
                [d.bounds[2], d.bounds[3]],
                [d.bounds[2], d.bounds[1]],
                [d.bounds[0], d.bounds[1]]
            ]]
        }
        if d.driver == 'ESRI Shapefile':
            id_ = os.path.splitext(os.path.basename(filepath))[0]
            content['assets'] = {}
            for suffix in ['shx', 'dbf', 'prj']:
                content['assets'][suffix] = {
                    'href': './{}.{}'.format(id_, suffix)
                }

    return content
