# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
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

from datetime import datetime
import io
from json import loads
import logging
import os

from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
                                    ProviderNotFoundError)
from pygeoapi.util import file_modified_iso8601, get_path_basename, url_join

LOGGER = logging.getLogger(__name__)


class FileSystemProvider(BaseProvider):
    """filesystem Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.filesystem.FileSystemProvider
        """

        super().__init__(provider_def)

        if not os.path.exists(self.data):
            msg = f'Directory does not exist: {self.data}'
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

            depth = dirpath.count('/')
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

        LOGGER.debug('Checking if path exists as raw file or directory')
        if data_path.endswith(tuple(self.file_types)):
            resource_type = 'raw_file'
        elif os.path.exists(data_path):
            resource_type = 'directory'
        else:
            LOGGER.debug('Checking if path exists as file via file_types')
            for ft in self.file_types:
                tmp_path = f'{data_path}{ft}'
                if os.path.exists(tmp_path):
                    resource_type = 'file'
                    data_path = tmp_path
                    break

        if resource_type is None:
            msg = f'Resource does not exist: {data_path}'
            LOGGER.error(msg)
            raise ProviderNotFoundError(msg)

        if resource_type == 'raw_file':
            with io.open(data_path, 'rb') as fh:
                return fh.read()

        elif resource_type == 'directory':
            content['type'] = 'Catalog'
            dirpath2 = os.listdir(data_path)
            dirpath2.sort()
            for dc in dirpath2:
                # TODO: handle a generic directory for tiles
                if dc == "tiles":
                    continue

                fullpath = os.path.join(data_path, dc)
                filectime = file_modified_iso8601(fullpath)
                filesize = os.path.getsize(fullpath)

                if os.path.isdir(fullpath):
                    newpath = os.path.join(baseurl, urlpath, dc)
                    child_links.append({
                        'rel': 'child',
                        'href': newpath,
                        'type': 'text/html',
                        'created': filectime,
                        'entry:type': 'Catalog'
                    })
                elif os.path.isfile(fullpath):
                    basename, extension = os.path.splitext(dc)
                    newpath = os.path.join(baseurl, urlpath, basename)
                    newpath2 = f'{newpath}{extension}'
                    if extension in self.file_types:
                        fullpath = os.path.join(data_path, dc)
                        child_links.append({
                            'rel': 'item',
                            'href': newpath,
                            'title': get_path_basename(newpath2),
                            'created': filectime,
                            'file:size': filesize,
                            'entry:type': 'Item'
                        })

        elif resource_type == 'file':
            filename = os.path.basename(data_path)

            id_ = os.path.splitext(filename)[0]
            if urlpath:
                filename = filename.replace(id_, '')
            url = f'{baseurl}/{urlpath}{filename}'

            filectime = file_modified_iso8601(data_path)
            filesize = os.path.getsize(data_path)

            content = {
                'id': id_,
                'type': 'Feature',
                'properties': {},
                'links': [],
                'assets': {}
            }

            content.update(_describe_file(data_path))

            content['assets']['default'] = {
                'href': url,
                'created': filectime,
                'file:size': filesize
            }

        content['links'].extend(child_links)

        return content

    def __repr__(self):
        return f'<FileSystemProvider> {self.data}'


def _describe_file(filepath):
    """
    Helper function to describe a geospatial data
    First checks if a sidecar mcf file is available, if so uses that
    if not, script will parse the file to retrieve some info from the file

    :param filepath: path to file

    :returns: `dict` of GeoJSON item
    """

    content = {
        'bbox': None,
        'geometry': None,
        'properties': {}
    }

    mcf_file = f'{os.path.splitext(filepath)[0]}.yml'

    if os.path.isfile(mcf_file):
        try:
            from pygeometa.core import read_mcf, MCFReadError
            from pygeometa.schemas.stac import STACItemOutputSchema

            md = read_mcf(mcf_file)
            stacjson = STACItemOutputSchema.write(STACItemOutputSchema, md)
            stacdata = loads(stacjson)
            for k, v in stacdata.items():
                content[k] = v
        except ImportError:
            LOGGER.debug('pygeometa not found')
        except MCFReadError as err:
            LOGGER.warning(f'MCF error: {err}')
    else:
        LOGGER.debug(f'No mcf found at: {mcf_file}')

    if content['geometry'] is None and content['bbox'] is None:
        try:
            import rasterio
            from rasterio.crs import CRS
            from rasterio.warp import transform_bounds
        except ImportError as err:
            LOGGER.warning('rasterio not found')
            LOGGER.warning(err)
            return content

        try:
            import fiona
        except ImportError as err:
            LOGGER.warning('fiona not found')
            LOGGER.warning(err)
            return content

        try:  # raster
            LOGGER.debug('Testing raster data detection')
            d = rasterio.open(filepath)
            scrs = CRS(d.crs)
            LOGGER.debug(f'CRS: {d.crs}')
            LOGGER.debug(f'bounds: {d.bounds}')
            LOGGER.debug(f'Is geographic: {scrs.is_geographic}')
            if not scrs.is_geographic:
                LOGGER.debug('Reprojecting coordinates')
                tcrs = CRS.from_epsg(4326)
                bnds = transform_bounds(scrs, tcrs,
                                        d.bounds[0], d.bounds[1],
                                        d.bounds[2], d.bounds[3])
                content['properties']['projection'] = scrs.to_epsg()
            else:
                bnds = [d.bounds.left, d.bounds.bottom,
                        d.bounds.right, d.bounds.top]
            content['bbox'] = bnds
            content['geometry'] = {
                'type': 'Polygon',
                'coordinates': [[
                    [bnds[0],  bnds[1]],
                    [bnds[0],  bnds[3]],
                    [bnds[2], bnds[3]],
                    [bnds[2], bnds[1]],
                    [bnds[0],  bnds[1]]
                ]]
            }
            for k, v in d.tags(d.count).items():
                content['properties'][k] = v
                if k in ['GRIB_REF_TIME']:
                    value = int(v.split()[0])
                    datetime_ = datetime.fromtimestamp(value)
                    content['properties']['datetime'] = datetime_.isoformat() + 'Z'  # noqa
        except rasterio.errors.RasterioIOError:
            try:
                LOGGER.debug('Testing vector data detection')
                d = fiona.open(filepath)
                LOGGER.debug(f'CRS: {d.crs}')
                LOGGER.debug(f'bounds: {d.bounds}')
                scrs = CRS(d.crs)
                LOGGER.debug(f'CRS: {d.crs}')
                LOGGER.debug(f'bounds: {d.bounds}')
                LOGGER.debug(f'Is geographic: {scrs.is_geographic}')
                if not scrs.is_geographic:
                    LOGGER.debug('Reprojecting coordinates')
                    tcrs = CRS.from_epsg(4326)
                    bnds = transform_bounds(scrs, tcrs,
                                            d.bounds[0], d.bounds[1],
                                            d.bounds[2], d.bounds[3])
                    content['properties']['projection'] = scrs.to_epsg()
                else:
                    bnds = d.bounds

                if d.schema['geometry'] not in [None, 'None']:
                    content['bbox'] = [
                        bnds[0],
                        bnds[1],
                        bnds[2],
                        bnds[3]
                    ]
                    content['geometry'] = {
                        'type': 'Polygon',
                        'coordinates': [[
                            [bnds[0], bnds[1]],
                            [bnds[0], bnds[3]],
                            [bnds[2], bnds[3]],
                            [bnds[2], bnds[1]],
                            [bnds[0], bnds[1]]
                        ]]
                    }

                for k, v in d.schema['properties'].items():
                    content['properties'][k] = v

                if d.driver == 'ESRI Shapefile':
                    id_ = os.path.splitext(os.path.basename(filepath))[0]
                    content['assets'] = {}
                    for suffix in ['shx', 'dbf', 'prj']:
                        fullpath = f'{os.path.splitext(filepath)[0]}.{suffix}'

                        if os.path.exists(fullpath):
                            filectime = file_modified_iso8601(fullpath)
                            filesize = os.path.getsize(fullpath)

                            content['assets'][suffix] = {
                                'href': f'./{id_}.{suffix}',
                                'created': filectime,
                                'file:size': filesize
                            }

            except fiona.errors.DriverError:
                LOGGER.debug('Could not detect raster or vector data')

    return content
