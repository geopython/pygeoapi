# =================================================================
#
# Authors: Leo Ghignone <leo.ghignone@gmail.com>
#          Colton Loftus <cloftus@lincolninst.edu>
#
# Copyright (c) 2026 Leo Ghignone
# Copyright (c) 2026 Colton Loftus
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

from itertools import chain
import json
import logging

from dateutil.parser import isoparse
import geopandas as gpd
import pyarrow
import pyarrow.compute as pc
import pyarrow.dataset
import pyarrow.types as pat
import s3fs

from pygeoapi.crs import crs_transform
from pygeoapi.provider.base import (
    BaseProvider,
    ProviderConnectionError,
    ProviderGenericError,
    ProviderItemNotFoundError,
    ProviderQueryError,
)

LOGGER = logging.getLogger(__name__)


def arrow_to_pandas_type(arrow_type):
    pd_type = arrow_type.to_pandas_dtype()
    try:
        # Needed for specific types such as dtype('<M8[ns]')
        pd_type = pd_type.type
    except AttributeError:
        pd_type = pd_type
    return pd_type


def has_geoparquet_bbox_column(
    pyarrow_geo_metadata: dict, primary_geometry_column_name: str
) -> bool:
    """
    Check if the metadata on the parquet dataset
    indicates there is a geoparquet bbox column

    :param pyarrow_geo_metadata: dict serialized version of the 'geo'
        key within the pyarrow metadata json
    :param primary_geometry_column_name: name of the primary geometry column
        where the geometry is stored as specified in the 'geo' metadata

    :returns: bool whether or not the dataset has a geoparquet bbox column
    """
    primary_column = pyarrow_geo_metadata.get('primary_column')
    if primary_column is None:
        return False

    columns = pyarrow_geo_metadata.get('columns')
    if columns is None:
        return False

    geometry_column_metadata = columns.get(primary_geometry_column_name)
    if geometry_column_metadata is None:
        return False

    geometry_covering = geometry_column_metadata.get('covering')
    if geometry_covering is None:
        return False

    return geometry_covering.get('bbox') is not None


class ParquetProvider(BaseProvider):

    def __init__(self, provider_def):
        """
        Initialize object

        # Typical ParquetProvider YAML config:

        provider:
            name: Parquet
            data:
                source: s3://example.com/parquet_directory/

            id_field: gml_id


        :param provider_def: provider definition

        :returns: pygeoapi.provider.parquet.ParquetProvider
        """

        super().__init__(provider_def)

        # Source url is required
        self.source = self.data.get('source')
        if not self.source:
            msg = 'Need explicit "source" attr in data' \
                  ' field of provider config'
            LOGGER.error(msg)
            raise ProviderGenericError(msg)

        # Manage AWS S3 sources
        if self.source.startswith('s3'):
            self.source = self.source.split('://', 1)[1]
            self.fs = s3fs.S3FileSystem(default_cache_type='none')
        else:
            # If none, pyarrow will attempt to auto-detect
            self.fs = None

        # Build pyarrow dataset pointing to the data
        self.ds = pyarrow.dataset.dataset(self.source, filesystem=self.fs)

        if not self.id_field:
            LOGGER.info(
                'No "id_field" specified in parquet provider config'
                ' will use pandas index as the identifier'
            )
        else:
            id_type = self.ds.schema.field(self.id_field).type
            if (
                pat.is_integer(id_type)
                or pat.is_decimal(id_type)
                or pat.is_float_value(id_type)
            ):
                LOGGER.warning(
                    f'id_field is of type {id_type},'
                    ' and not numeric; this is harder to query and'
                    ' may cause slow full scans'
                )

        LOGGER.debug('Grabbing field information')
        self.get_fields()  # Must be set to visualise queryables

        # Get the CRS of the data
        if b'geo' in self.ds.schema.metadata:
            geo_metadata = json.loads(self.ds.schema.metadata[b'geo'])

            geom_column = geo_metadata['primary_column']

            if geom_column:
                self.has_geometry = True

            # if the CRS is not set default to EPSG:4326, per geoparquet spec
            self.crs = geo_metadata['columns'][geom_column].get('crs') \
                or 'OGC:CRS84'

            # self.bbox_filterable indicates whether or not
            # we can resolve a bbox request
            # against the data, either by using an explicit
            # bbox column or by using x_field and y_field
            # columns
            self.bbox_filterable = \
                has_geoparquet_bbox_column(geo_metadata, geom_column)
            if self.bbox_filterable:
                # Whether or not the data has the geoparquet
                # standardized bbox column
                self.has_bbox_column = True
                # if there is a bbox column we
                # don't need to parse the x_fields and y_fields
                # and can just return early
                return
            else:
                self.has_bbox_column = False
        else:
            self.has_geometry = False
            self.has_bbox_column = False

        for field_name, field_value in [
            ('x_field', self.x_field),
            ('y_field', self.y_field)
        ]:
            if not field_value:
                LOGGER.warning(
                    f'No geometry for {self.source};'
                    f'missing {field_name} in parquet provider config'
                )
                self.bbox_filterable = False
                self.has_bbox_column = False
                return

        # If there is not a geoparquet bbox column,
        # then we fall back to reading fields for minx, maxx, miny, maxy
        # as direct column names; these can be set and use regardless of
        # whether or not there is 'geo' metadata
        if isinstance(self.x_field, str):
            self.minx = self.x_field
            self.maxx = self.x_field
        else:
            self.minx, self.maxx = self.x_field

        if isinstance(self.y_field, str):
            self.miny = self.y_field
            self.maxy = self.y_field
        else:
            self.miny, self.maxy = self.y_field

        self.bbox_filterable = True

    def _read_parquet(self, return_scanner=False, **kwargs):
        """
        Scan a Parquet dataset with the given arguments

        :returns: generator of RecordBatch with the queried values
        """
        scanner = self.ds.scanner(
            use_threads=True,
            **kwargs
        )
        batches = scanner.to_batches()
        if return_scanner:
            return batches, scanner
        else:
            return batches

    def get_fields(self):
        """
        Get provider field information (names, types)

        :returns: dict of fields
        """

        if not self._fields:
            for field_name, field_type in zip(
                self.ds.schema.names, self.ds.schema.types
            ):
                # Geometry is managed as a special case by pygeoapi
                if field_name == 'geometry':
                    continue
                # if we find the geoparquet bbox column and the
                # type is a struct of any type, either double or
                # float, then we skip it since it isn't
                # meant to be a queryable field, rather just metadata
                if field_name == 'bbox' and 'struct' in str(field_type):
                    self.bbox_filterable = True
                    continue

                field_type = str(field_type)
                converted_type = None
                converted_format = None
                if field_type.startswith(('int', 'uint')):
                    converted_type = 'integer'
                    converted_format = field_type
                elif field_type == 'double' or field_type.startswith('float'):
                    converted_type = 'number'
                    converted_format = field_type
                elif field_type == 'string':
                    converted_type = 'string'
                elif field_type == 'bool':
                    converted_type = 'boolean'
                elif field_type.startswith('timestamp'):
                    converted_type = 'string'
                    converted_format = 'date-time'
                else:
                    LOGGER.error(f'Unsupported field type {field_type}')

                if converted_format is None:
                    self._fields[field_name] = {'type': converted_type}
                else:
                    self._fields[field_name] = {
                        'type': converted_type,
                        'format': converted_format,
                    }

        return self._fields

    @crs_transform
    def query(
        self,
        offset=0,
        limit=10,
        resulttype='results',
        bbox=[],
        datetime_=None,
        properties=[],
        select_properties=[],
        skip_geometry=False,
        q=None,
        **kwargs,
    ):
        """
        Query Parquet source

        :param offset: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent) following ISO-8601
        :param properties: list of tuples (field, comparison, value)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)

        :returns: dict of 0..n GeoJSON features
        """
        try:
            filter_ = pc.scalar(True)

            if bbox:
                if not self.has_geometry:
                    raise ProviderQueryError(
                        (
                            'Dataset does not have a geometry field, '
                            'querying by bbox is not supported.'
                        )
                    )

                if not self.bbox_filterable:
                    raise ProviderQueryError(
                        (
                            'Dataset does not have a proper bbox metadata, '
                            'querying by bbox is not supported.'
                        )
                    )

                minx, miny, maxx, maxy = [float(b) for b in bbox]

                if self.has_bbox_column:
                    # GeoParquet bbox column is a struct
                    # with xmin, ymin, xmax, ymax
                    filter_ = filter_ & (
                        (pc.field('bbox', 'xmin') >= pc.scalar(minx))
                        & (pc.field('bbox', 'ymin') >= pc.scalar(miny))
                        & (pc.field('bbox', 'xmax') <= pc.scalar(maxx))
                        & (pc.field('bbox', 'ymax') <= pc.scalar(maxy))
                    )
                else:
                    filter_ = (
                        (pc.field(self.minx) >= pc.scalar(minx))
                        & (pc.field(self.miny) >= pc.scalar(miny))
                        & (pc.field(self.maxx) <= pc.scalar(maxx))
                        & (pc.field(self.maxy) <= pc.scalar(maxy))
                    )

            if datetime_ is not None:
                if self.time_field is None:
                    msg = (
                        'Dataset does not have a time field, '
                        'querying by datetime is not supported.'
                    )
                    raise ProviderQueryError(msg)
                timefield = pc.field(self.time_field)
                if '/' in datetime_:
                    begin, end = datetime_.split('/')
                    if begin != '..':
                        begin = isoparse(begin)
                        filter_ = filter_ & (timefield >= begin)
                    if end != '..':
                        end = isoparse(end)
                        filter_ = filter_ & (timefield <= end)
                else:
                    target_time = isoparse(datetime_)
                    filter_ = filter_ & (timefield == target_time)

            if properties:
                LOGGER.debug('processing properties')
                for name, value in properties:
                    field = self.ds.schema.field(name)
                    pd_type = arrow_to_pandas_type(field.type)
                    expr = pc.field(name) == pc.scalar(pd_type(value))

                    filter_ = filter_ & expr

            if len(select_properties) == 0:
                select_properties = self.ds.schema.names
            else:  # Load id and geometry together with any specified columns
                if self.has_geometry and 'geometry' not in select_properties:
                    select_properties.append('geometry')
                if self.id_field not in select_properties:
                    select_properties.insert(0, self.id_field)

            if skip_geometry:
                select_properties.remove('geometry')

            # Make response based on resulttype specified
            if resulttype == 'hits':
                LOGGER.debug('hits only specified')
                return self._response_feature_hits(filter_)
            elif resulttype == 'results':
                LOGGER.debug('results specified')
                return self._response_feature_collection(
                    filter_, offset, limit, columns=select_properties
                )
            else:
                LOGGER.error(f'Invalid resulttype: {resulttype}')

        except RuntimeError as err:
            LOGGER.error(err)
            raise ProviderQueryError(err)
        except ProviderConnectionError as err:
            LOGGER.error(err)
            raise ProviderConnectionError(err)
        except Exception as err:
            LOGGER.error(err)
            raise ProviderGenericError(err)

    @crs_transform
    def get(self, identifier, **kwargs):
        """
        Get Feature by id

        :param identifier: feature id

        :returns: a single feature
        """
        try:
            LOGGER.debug(f'Fetching identifier {identifier}')
            id_type = arrow_to_pandas_type(
                self.ds.schema.field(self.id_field).type
            )
            batches = self._read_parquet(
                filter=(
                    pc.field(self.id_field) == pc.scalar(id_type(identifier)
                                                         ))
            )

            for batch in batches:
                if batch.num_rows > 0:
                    assert batch.num_rows == 1, (
                        f'Multiple items found with ID {identifier}'
                    )
                    row = batch.to_pandas()
                    break
            else:
                raise ProviderItemNotFoundError(f'ID {identifier} not found')

            if self.has_geometry:
                geom = gpd.GeoSeries.from_wkb(row['geometry'], crs=self.crs)
            else:
                geom = [None]
            gdf = gpd.GeoDataFrame(row, geometry=geom)
            # If there is an id field, set it as index
            # instead of the default numeric index
            if self.id_field in gdf.columns:
                gdf = gdf.set_index(self.id_field, drop=False)
            LOGGER.debug('results computed')

            # Grab the collection from geopandas geo_interface
            return gdf.__geo_interface__['features'][0]

        except RuntimeError as err:
            LOGGER.error(err)
            raise ProviderQueryError(err)
        except ProviderConnectionError as err:
            LOGGER.error(err)
            raise ProviderConnectionError(err)
        except ProviderItemNotFoundError as err:
            LOGGER.error(err)
            raise ProviderItemNotFoundError(err)
        except Exception as err:
            LOGGER.error(err)
            raise ProviderGenericError(err)

    def __repr__(self):
        return f'<ParquetProvider> {self.data}'

    def _response_feature_collection(self, filter, offset,
                                     limit, columns=None):
        """
        Assembles output from query as
        GeoJSON FeatureCollection structure.

        :returns: GeoJSON FeatureCollection
        """

        LOGGER.debug(f'offset:{offset}, limit:{limit}')

        try:
            batches, scanner = self._read_parquet(
                filter=filter, columns=columns, return_scanner=True
            )

            # Discard batches until offset is reached
            counted = 0
            for batch in batches:
                if counted + batch.num_rows > offset:
                    # Slice current batch to start from the requested row
                    batch = batch.slice(offset=offset - counted)
                    # Build a new generator yielding the current batch
                    # and all following ones

                    batches = chain([batch], batches)
                    break
                else:
                    counted += batch.num_rows

            # batches is a generator, it will now be either fully spent
            # or set to the new generator starting from offset

            # Get the next `limit+1` rows
            # The extra row is used to check if a "next" link is needed
            # (when numberMatched > offset + limit)
            batches_list = []
            read = 0

            for batch in batches:
                read += batch.num_rows
                if read > limit:
                    batches_list.append(batch.slice(0, limit + 1))
                    break
                else:
                    batches_list.append(batch)

            # Passing schema from scanner in case no rows are returned
            table = pyarrow.Table.from_batches(
                batches_list, schema=scanner.projected_schema
            )

            rp = table.to_pandas()

            number_matched = offset + len(rp)

            # Remove the extra row
            if len(rp) > limit:
                rp = rp.iloc[:-1]

            if 'geometry' not in rp.columns:
                # We need a null geometry column to create a GeoDataFrame
                rp['geometry'] = None
                geom = gpd.GeoSeries.from_wkb(rp['geometry'])
            else:
                geom = gpd.GeoSeries.from_wkb(rp['geometry'], crs=self.crs)

            gdf = gpd.GeoDataFrame(rp, geometry=geom)
            # If there is an id_field in the data, set it as index
            # instead of the default numerical index
            if self.id_field in gdf.columns:
                gdf = gdf.set_index(self.id_field, drop=False)
            LOGGER.debug('results computed')
            result = gdf.__geo_interface__

            # Add numberMatched to generate "next" link
            result['numberMatched'] = number_matched

            return result

        except RuntimeError as error:
            LOGGER.error(error)
            raise error

    def _response_feature_hits(self, filter):
        """
        Assembles GeoJSON hits from row count

        :returns: GeoJSON FeaturesCollection
        """

        try:
            scanner = pyarrow.dataset.Scanner.from_dataset(
                self.ds, filter=filter
            )
            return {
                'type': 'FeatureCollection',
                'numberMatched': scanner.count_rows(),
                'features': [],
            }
        except Exception as error:
            LOGGER.error(error)
            raise error
