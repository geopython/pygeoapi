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
import logging
import os

from azure.storage.blob import BlobServiceClient

from pygeoapi.provider.base import (BaseProvider, ProviderConnectionError,
                                    ProviderNotFoundError)
from pygeoapi.util import file_modified_iso8601, get_path_basename, url_join

LOGGER = logging.getLogger(__name__)


class AzureBlobStorageProvider(BaseProvider):
    """Azure blob storage Provider"""

    def __init__(self, provider_def):
        """
        Initialize object

        :param provider_def: provider definition

        :returns: pygeoapi.provider.filesystem.FileSystemProvider
        """

        super().__init__(provider_def)

        if os.environ.get('AZURE_STORAGE_CONNECTION_STRING') is None:
            msg = 'AZURE_STORAGE_CONNECTION_STRING not set!'
            LOGGER.error(msg)
            raise ProviderConnectionError()

        self.blob_service_client = BlobServiceClient.from_connection_string(
            os.environ.get('AZURE_STORAGE_CONNECTION_STRING'))
        self.container_client = self.blob_service_client.get_container_client(
            self.data)

    def get_data_path(self, baseurl, urlpath, dirpath):
        """
        Gets directory listing or file description or raw file dump

        :param baseurl: base URL of endpoint
        :param urlpath: base path of URL
        :param dirpath: directory basepath (equivalent of URL)

        :returns: `dict` of file listing or `dict` of GeoJSON item or raw file
        """

        urlpath = urlpath.split('/')[0]
        thispath = os.path.join(baseurl, urlpath)

        LOGGER.debug(f'basepath: {baseurl}')
        LOGGER.debug(f'urlpath: {urlpath}')
        LOGGER.debug(f'path: {thispath}')

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

        LOGGER.debug(f'data path: {data_path}')
        data_path = data_path.replace(self.data, '').lstrip('/')
        LOGGER.debug(f'data path: {data_path}')

        if data_path == '':
            LOGGER.debug('Root of container')

        self.blob_client = self.blob_service_client.get_blob_client(
            container=self.data, blob=data_path+'/')

        LOGGER.debug('Checking if path exists as raw file or directory')
        if data_path.endswith(tuple(self.file_types)):
            resource_type = 'raw_file'
        elif self.container_client.walk_blobs(name_starts_with=data_path, prefix='/') or data_path == '':  # noqa
            resource_type = 'directory'

        LOGGER.debug('Checking if path exists as file via file_types')
        for ft in self.file_types:
            tmp_path = f'{data_path}{ft}'
            blob_tmp_path = self.blob_service_client.get_blob_client(
                container=self.data.lstrip('/'), blob=tmp_path)

            if blob_tmp_path.exists():
                resource_type = 'file'
                data_path = tmp_path
                break

        LOGGER.debug(f'Resource type: {resource_type}')
        if resource_type is None:
            msg = f'Resource does not exist: {data_path}'
            LOGGER.error(msg)
            raise ProviderNotFoundError(msg)

        if resource_type == 'raw_file':
            data = self.blob_service_client.get_blob_client(
                container=self.data.lstrip('/'), blob=data_path)
            return data.download_blob().read()

        elif resource_type == 'directory':
            content['type'] = 'Catalog'
            LOGGER.debug(f'DATA PATH: {data_path}')
            for dc in self.container_client.walk_blobs(
                    name_starts_with=data_path, prefix='/'):
                fullpath = dc.name

                LOGGER.debug(f'FULLPATH: {fullpath}')
                if fullpath.endswith('/'):
                    newpath = os.path.join(baseurl, urlpath, str(dc.name))
                    child_links.append({
                        'rel': 'child',
                        'href': newpath,
                        'type': 'text/html',
                        'entry:type': 'Catalog'
                    })

                else:
                    basename, extension = os.path.splitext(dc.name)
                    newpath = os.path.join(baseurl, urlpath, basename)
                    newpath2 = f'{newpath}{extension}'
                    if extension in self.file_types:
                        fullpath = os.path.join(data_path, dc.name)
                        child_links.append({
                            'rel': 'item',
                            'href': newpath,
                            'title': get_path_basename(newpath2),
                            'created': dc.creation_time,
                            'file:size': dc.size,
                            'entry:type': 'Item'
                        })

        elif resource_type == 'file':
            blob_tmp_path = self.blob_service_client.get_blob_client(
                container=self.data.lstrip('/'), blob=tmp_path)
            blob_properties = blob_tmp_path.get_blob_properties()
            filename = os.path.basename(data_path)

            id_ = os.path.splitext(filename)[0]
            if urlpath:
                filename = filename.replace(id_, '')
            url = f'{baseurl}/{urlpath}/{tmp_path}'

            filectime = blob_properties.creation_time
            filesize = blob_properties.size

            content = {
                'id': id_,
                'type': 'Feature',
                'properties': {},
                'links': [],
                'assets': {}
            }

            content.update(_describe_file(blob_tmp_path.download_blob()))

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
    Helper function to describe geospatial data
    Parse file using rasterio/fiona to retrieve properties

    :param filepath: path to file

    :returns: `dict` of GeoJSON item
    """

    content = {
        'bbox': None,
        'geometry': None,
        'properties': {}
    }

    if content['geometry'] is None and content['bbox'] is None:
        try:
            import rasterio
            from rasterio.crs import CRS
            from rasterio.io import MemoryFile
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

            with MemoryFile(filepath) as memfile:
                with memfile.open() as d:
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
                            [bnds[0], bnds[1]],
                            [bnds[0], bnds[3]],
                            [bnds[2], bnds[3]],
                            [bnds[2], bnds[1]],
                            [bnds[0], bnds[1]]
                        ]]
                    }
                    for k, v in d.tags(d.count).items():
                        content['properties'][k] = v
                        if k in ['GRIB_REF_TIME']:
                            value = int(v.split()[0])
                            datetime_ = datetime.fromtimestamp(value)
                            content['properties']['datetime'] = datetime_.isoformat() + 'Z'  # noqa
        except rasterio.errors.RasterioIOError as err:
            LOGGER.debug(err)
            try:
                LOGGER.debug('Testing vector data detection')
                d = fiona.open(filepath)
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
