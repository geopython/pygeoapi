# =================================================================
#
# Authors: Jorge Samuel Mendes de Jesus <jorge.dejesus@protonmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#          Mary Bucknell <mbucknell@usgs.gov>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Bernhard Mallinger <bernhard.mallinger@eox.at>
#          Colton Loftus <cloftus@lincolninst.edu>
#
# Copyright (c) 2018 Jorge Samuel Mendes de Jesus
# Copyright (c) 2025 Tom Kralidis
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
# Copyright (c) 2025 Francesco Bartoli
# Copyright (c) 2024 Bernhard Mallinger
# Copyright (c) 2025 Colton Loftus
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
from datetime import datetime
from decimal import Decimal
import functools
import logging
from typing import Optional, Any

from geoalchemy2 import Geometry  # noqa - this isn't used explicitly but is needed to process Geometry columns
from geoalchemy2.functions import ST_MakeEnvelope, ST_Intersects
from geoalchemy2.shape import to_shape, from_shape
from pygeofilter.backends.sqlalchemy.evaluate import to_filter
import shapely
from sqlalchemy.sql import func
from sqlalchemy import (
    create_engine,
    MetaData,
    PrimaryKeyConstraint,
    asc,
    desc,
    delete
)
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import (
    ConstraintColumnNotFoundError,
    InvalidRequestError,
    OperationalError
)
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session, load_only
from sqlalchemy.sql.expression import and_
from sqlalchemy.schema import Table

from pygeoapi.crs import get_transform_from_spec, get_srid
from pygeoapi.provider.base import (
    BaseProvider,
    ProviderConnectionError,
    ProviderInvalidDataError,
    ProviderQueryError,
    ProviderItemNotFoundError
)

LOGGER = logging.getLogger(__name__)


class GenericSQLProvider(BaseProvider):
    """
    Generic provider for sql databases it can be inherited
    from to create specific providers for different databases
    """

    def __init__(
        self,
        provider_def: dict,
        driver_name: str,
        extra_conn_args: Optional[dict] = {}
    ):
        """
        GenericSQLProvider Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class
                             data contains the connection information
                             for class DatabaseCursor
        :param driver_name: database driver name
        :param extra_conn_args: additional custom connection arguments to
                                pass for a query

        :returns: pygeoapi.provider.GenericSQLProvider
        """
        LOGGER.debug('Initialising GenericSQL provider.')
        super().__init__(provider_def)

        self.table = provider_def['table']
        self.id_field = provider_def['id_field']
        self.geom = provider_def.get('geom_field', 'geom')
        self.driver_name = driver_name

        LOGGER.debug(f'Name: {self.name}')
        LOGGER.debug(f'Table: {self.table}')
        LOGGER.debug(f'ID field: {self.id_field}')
        LOGGER.debug(f'Geometry field: {self.geom}')
        LOGGER.debug(f'Configured Storage CRS: {self.storage_crs}')

        # Read table information from database
        options = provider_def.get('options', {}) | extra_conn_args
        store_db_parameters(self, provider_def['data'], options)
        self._engine = get_engine(
            driver_name,
            self.db_host,
            self.db_port,
            self.db_name,
            self.db_user,
            self._db_password,
            self.db_conn,
            **self.db_options
        )
        self.table_model = get_table_model(
            self.table, self.id_field, self.db_search_path, self._engine
        )

        self.get_fields()

    def query(
        self,
        offset=0,
        limit=10,
        resulttype='results',
        bbox=[],
        datetime_=None,
        properties=[],
        sortby=[],
        select_properties=[],
        skip_geometry=False,
        q=None,
        filterq=None,
        crs_transform_spec=None,
        **kwargs
    ):
        """
        Query sql database for all the content.
        e,g: http://localhost:5000/collections/hotosm_bdi_waterways/items?
        limit=1&resulttype=results

        :param offset: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param q: full-text search term(s)
        :param filterq: CQL query as text string
        :param crs_transform_spec: `CrsTransformSpec` instance, optional

        :returns: GeoJSON FeatureCollection
        """

        LOGGER.debug('Preparing filters')
        property_filters = self._get_property_filters(properties)
        cql_filters = self._get_cql_filters(filterq)
        bbox_filter = self._get_bbox_filter(bbox)
        time_filter = self._get_datetime_filter(datetime_)
        order_by_clauses = self._get_order_by_clauses(sortby, self.table_model)
        selected_properties = self._select_properties_clause(
            select_properties, skip_geometry
        )

        LOGGER.debug('Querying Database')
        # Execute query within self-closing database Session context
        with Session(self._engine) as session:
            results = (
                session.query(self.table_model)
                .filter(property_filters)
                .filter(cql_filters)
                .filter(bbox_filter)
                .filter(time_filter)
                .options(selected_properties)
            )

            LOGGER.debug('Preparing response')
            response = {
                'type': 'FeatureCollection',
                'features': [],
                'numberReturned': 0
            }

            if self.count or resulttype == 'hits':
                matched = results.count()
                response['numberMatched'] = matched
                LOGGER.debug(f'Found {matched} result(s)')
            else:
                LOGGER.debug('Count disabled')

            if resulttype == 'hits' or not results:
                return response

            crs_transform_out = get_transform_from_spec(crs_transform_spec)

            for item in (
                results.order_by(*order_by_clauses).offset(offset).limit(limit)
            ):
                response['numberReturned'] += 1
                response['features'].append(
                    self._sqlalchemy_to_feature(item, crs_transform_out,
                                                select_properties)
                )

        return response

    def get_fields(self):
        """
        Return fields (columns) from database table

        :returns: dict of fields
        """

        LOGGER.debug('Get available fields/properties')

        # sql-schema only allows these types, so we need to map from sqlalchemy
        # string, number, integer, object, array, boolean, null,
        # https://json-schema.org/understanding-json-schema/reference/type.html
        column_type_map = {
            bool: 'boolean',
            datetime: 'string',
            Decimal: 'number',
            dict: 'object',
            float: 'number',
            int: 'integer',
            str: 'string'
        }
        default_type = 'string'

        # https://json-schema.org/understanding-json-schema/reference/string#built-in-formats  # noqa
        column_format_map = {
            'date': 'date',
            'interval': 'duration',
            'time': 'time',
            'timestamp': 'date-time'
        }

        def _column_type_to_json_schema_type(column_type):
            try:
                python_type = column_type.python_type
            except NotImplementedError:
                LOGGER.warning(f'Unsupported column type {column_type}')
                return default_type
            else:
                try:
                    return column_type_map[python_type]
                except KeyError:
                    LOGGER.warning(f'Unsupported column type {column_type}')
                    return default_type

        def _column_format_to_json_schema_format(column_type):
            try:
                ct = str(column_type).lower()
                return column_format_map[ct]
            except KeyError:
                LOGGER.debug('No string format detected')
                return None

        if not self._fields:
            for column in self.table_model.__table__.columns:
                LOGGER.debug(f'Testing {column.name}')
                if column.name == self.geom:
                    continue

                self._fields[str(column.name)] = {
                    'type': _column_type_to_json_schema_type(column.type),
                    'format': _column_format_to_json_schema_format(
                        column.type
                    )
                }

        return self._fields

    def get(self, identifier, crs_transform_spec=None, **kwargs):
        """
        Query the provider for a specific
        feature id e.g: /collections/hotosm_bdi_waterways/items/13990765

        :param identifier: feature id
        :param crs_transform_spec: `CrsTransformSpec` instance, optional

        :returns: GeoJSON FeatureCollection
        """
        LOGGER.debug(f'Get item by ID: {identifier}')

        # Execute query within self-closing database Session context
        with Session(self._engine) as session:
            # Retrieve data from database as feature
            item = session.get(self.table_model, identifier)
            if item is None:
                msg = f'No such item: {self.id_field}={identifier}.'
                raise ProviderItemNotFoundError(msg)
            crs_transform_out = get_transform_from_spec(crs_transform_spec)
            feature = self._sqlalchemy_to_feature(item, crs_transform_out)

            # Drop non-defined properties
            if self.properties:
                props = feature['properties']
                dropping_keys = deepcopy(props).keys()
                for item in dropping_keys:
                    if item not in self.properties:
                        props.pop(item)

            # Add fields for previous and next items
            id_field = getattr(self.table_model, self.id_field)
            prev_item = (
                session.query(self.table_model)
                .order_by(id_field.desc())
                .filter(id_field < identifier)
                .first()
            )
            next_item = (
                session.query(self.table_model)
                .order_by(id_field.asc())
                .filter(id_field > identifier)
                .first()
            )
            feature['prev'] = (
                getattr(prev_item, self.id_field)
                if prev_item is not None
                else identifier
            )
            feature['next'] = (
                getattr(next_item, self.id_field)
                if next_item is not None
                else identifier
            )

        return feature

    def create(self, item):
        """
        Create a new item

        :param item: `dict` of new item

        :returns: identifier of created item
        """

        identifier, json_data = self._load_and_prepare_item(
            item, accept_missing_identifier=True
        )

        new_instance = self._feature_to_sqlalchemy(json_data, identifier)
        with Session(self._engine) as session:
            session.add(new_instance)
            session.commit()
            result_id = getattr(new_instance, self.id_field)

        # NOTE: need to use id from instance in case it's generated
        return result_id

    def update(self, identifier, item):
        """
        Updates an existing item

        :param identifier: feature id
        :param item: `dict` of partial or full item

        :returns: `bool` of update result
        """

        identifier, json_data = self._load_and_prepare_item(
            item, raise_if_exists=False
        )

        new_instance = self._feature_to_sqlalchemy(json_data, identifier)
        with Session(self._engine) as session:
            session.merge(new_instance)
            session.commit()

        return True

    def delete(self, identifier):
        """
        Deletes an existing item

        :param identifier: item id

        :returns: `bool` of deletion result
        """
        with Session(self._engine) as session:
            id_column = getattr(self.table_model, self.id_field)
            result = session.execute(
                delete(self.table_model).where(id_column == identifier)
            )
            session.commit()

        return result.rowcount > 0

    def _sqlalchemy_to_feature(self, item, crs_transform_out=None,
                               select_properties=[]):
        """
        Helper function to transform an SQLAlchemy result to a
        GeoJSON feature.

        :param item: SQLAlchemy result
        :param crs_transform_out: CRS transformation
        :param select_properties: additional properties to filter on

        :returns: `dict` of GeoJSON feature
        """

        feature = {'type': 'Feature', 'properties': {}}

        item_dict = item.__dict__

        # set feature id
        feature['id'] = item_dict[self.id_field]

        # Convert geometry to GeoJSON style
        if item_dict.get(self.geom) is not None:
            wkb_geom = item_dict[self.geom]
            try:
                shapely_geom = to_shape(wkb_geom)
            except TypeError:
                shapely_geom = shapely.geometry.shape(wkb_geom)
            if crs_transform_out is not None:
                shapely_geom = crs_transform_out(shapely_geom)
            geojson_geom = shapely.geometry.mapping(shapely_geom)
            feature['geometry'] = geojson_geom
        else:
            feature['geometry'] = None

        keys = select_properties or self.fields.keys()
        for key in keys:
            if key in item_dict:
                feature['properties'][key] = item_dict[key]

        return feature

    def _feature_to_sqlalchemy(self, json_data, identifier=None):
        attributes = {**json_data['properties']}
        # 'identifier' key maybe be present in geojson properties, but might
        # not be a valid db field
        attributes.pop('identifier', None)
        attributes[self.geom] = from_shape(
            shapely.geometry.shape(json_data['geometry']),
            srid=get_srid(self.storage_crs)
        )
        attributes[self.id_field] = identifier

        try:
            return self.table_model(**attributes)
        except Exception as e:
            LOGGER.exception('Failed to create db model')
            raise ProviderInvalidDataError(str(e))

    def _get_order_by_clauses(self, sort_by, table_model):
        # Build sort_by clauses if provided
        clauses = []
        for sort_by_dict in sort_by:
            model_column = getattr(table_model, sort_by_dict['property'])
            order_function = asc if sort_by_dict['order'] == '+' else desc
            clauses.append(order_function(model_column))

        # Otherwise sort by primary key (to ensure reproducible output)
        if not clauses:
            clauses.append(asc(getattr(table_model, self.id_field)))

        return clauses

    def _get_cql_filters(self, filterq):
        if not filterq:
            return True  # Let everything through

        # Convert filterq into SQL Alchemy filters
        field_mapping = {
            column_name: getattr(self.table_model, column_name)
            for column_name in self.table_model.__table__.columns.keys()
        }
        cql_filters = to_filter(filterq, field_mapping)

        return cql_filters

    def _get_property_filters(self, properties):
        if not properties:
            return True  # Let everything through

        # Convert property filters into SQL Alchemy filters
        # Based on https://stackoverflow.com/a/14887813/3508733
        filter_group = []
        for column_name, value in properties:
            column = getattr(self.table_model, column_name)
            filter_group.append(column == value)
        property_filters = and_(*filter_group)

        return property_filters

    def _get_bbox_filter(self, bbox: list[float]):
        """
        Construct the bounding box filter function that
        will be used in the query; this is dependent on the
        underlying db driver
        """
        raise NotImplementedError

    def _get_datetime_filter(self, datetime_):
        if datetime_ in (None, '../..'):
            return True
        else:
            if self.time_field is None:
                LOGGER.error('time_field not enabled for collection')
                raise ProviderQueryError()

            time_column = getattr(self.table_model, self.time_field)

            if '/' in datetime_:  # envelope
                LOGGER.debug('detected time range')
                time_begin, time_end = datetime_.split('/')
                if time_begin == '..':
                    datetime_filter = time_column <= time_end
                elif time_end == '..':
                    datetime_filter = time_column >= time_begin
                else:
                    datetime_filter = time_column.between(time_begin, time_end)
            else:
                datetime_filter = time_column == datetime_
        return datetime_filter

    def _select_properties_clause(self, select_properties, skip_geometry):
        # List the column names that we want
        if select_properties:
            column_names = sorted(set(select_properties),
                                  key=select_properties.index)
        else:
            # get_fields() doesn't include geometry column
            column_names = self.fields.keys()

        if self.properties:  # optional subset of properties defined in config
            properties_from_config = self.properties
            column_names = column_names and properties_from_config

        if not skip_geometry:
            column_names = list(column_names)
            column_names.append(self.geom)

        # Convert names to SQL Alchemy clause
        selected_columns = []
        for column_name in column_names:
            try:
                column = getattr(self.table_model, column_name)
                selected_columns.append(column)
            except AttributeError:
                pass  # Ignore non-existent columns
        selected_properties_clause = load_only(*selected_columns)

        return selected_properties_clause


def store_db_parameters(
    self: GenericSQLProvider | Any,
    connection_data: str | dict[str],
    options: dict[str, str]
) -> None:
    """
    Store database connection parameters

    :self: instance of provider or manager class
    :param connection_data: connection string or dict of connection params
    :param options: additional connection options

    :returns: None
    """
    if isinstance(connection_data, str):
        self.db_conn = connection_data
        connection_data = {}
    else:
        self.db_conn = None
    # OR
    self.db_user = connection_data.get('user')
    self.db_host = connection_data.get('host')
    self.db_port = connection_data.get('port', self.default_port)
    self.db_name = (
        connection_data.get('dbname') or connection_data.get('database')
    )
    self.db_query = connection_data.get('query')
    self._db_password = connection_data.get('password')
    # db_search_path gets converted to a tuple here in order to ensure it
    # is hashable - which allows us to use functools.cache() when
    # reflecting the table definition from the DB
    self.db_search_path = tuple(
        connection_data.get('search_path') or
        options.pop('search_path', ['public'])
    )
    self.db_options = {
        k: v
        for k, v in options.items()
        if not isinstance(v, dict)
    }


@functools.cache
def get_engine(
    driver_name: str,
    host: str,
    port: str,
    database: str,
    user: str,
    password: str,
    conn_str: Optional[str] = None,
    **connect_args
) -> Engine:
    """
    Get SQL Alchemy engine.

    :param driver_name: database driver name
    :param host: database host
    :param port: database port
    :param database: database name
    :param user: database user
    :param password: database password
    :param conn_str: optional connection URL
    :param connect_args: custom connection arguments to pass to create_engine()

    :returns: SQL Alchemy engine
    """
    if conn_str is None:
        conn_str = URL.create(
            drivername=driver_name,
            username=user,
            password=password,
            host=host,
            port=int(port),
            database=database
        )

    engine = create_engine(
        conn_str, connect_args=connect_args, pool_pre_ping=True
    )

    LOGGER.debug(f'Created engine for {repr(engine.url)}.')
    return engine


@functools.cache
def get_table_model(
    table_name: str,
    id_field: str,
    db_search_path: tuple[str],
    engine: Engine
) -> Table:
    """
    Reflect table using SQLAlchemy Automap.

    :param table_name: name of table to reflect
    :param id_field: name of primary key field
    :param db_search_path: tuple of database schemas to search for the table
    :param engine: SQLAlchemy engine to use for reflection

    :returns: SQLAlchemy model of the reflected table
    """
    LOGGER.debug('Reflecting table definition from database')
    metadata = MetaData()

    # Look for table in the first schema in the search path
    schema = db_search_path[0]
    try:
        LOGGER.debug(f'Looking for table {table_name} in schema {schema}')
        metadata.reflect(
            bind=engine, schema=schema, only=[table_name], views=True
        )
    except OperationalError:
        raise ProviderConnectionError(
            f'Could not connect to {repr(engine.url)} (password hidden).'
        )
    except InvalidRequestError:
        msg = (
            f"Table '{table_name}' not found in schema '{schema}' "
            f'on {repr(engine.url)}.'
        )
        LOGGER.error(msg)

        if len(db_search_path) > 1:
            # If the table is not found in the first schema, try the next one
            return get_table_model(
                table_name,
                id_field,
                db_search_path[1:],
                engine
            )
        else:
            # If the table is not found in any schema, raise an error
            raise ProviderQueryError(msg)

    # Create SQLAlchemy model from reflected table
    # It is necessary to add the primary key constraint because SQLAlchemy
    # requires it to reflect the table, but a view in a PostgreSQL database
    # does not have a primary key defined.
    sqlalchemy_table_def = metadata.tables[f'{schema}.{table_name}']
    try:
        sqlalchemy_table_def.append_constraint(PrimaryKeyConstraint(id_field))
    except (ConstraintColumnNotFoundError, KeyError):
        raise ProviderQueryError(
            f'No such id_field column ({id_field}) on {schema}.{table_name}.'
        )

    _Base = automap_base(metadata=metadata)
    _Base.prepare(
        name_for_scalar_relationship=_name_for_scalar_relationship,
    )
    return getattr(_Base.classes, table_name)


def _name_for_scalar_relationship(base, local_cls, referred_cls, constraint):
    """Function used when automapping classes and relationships from
    database schema and fixes potential naming conflicts.
    """
    name = referred_cls.__name__.lower()
    local_table = local_cls.__table__
    if name in local_table.columns:
        newname = name + '_'
        LOGGER.debug(
            f'Already detected column name {name!r} in table '
            f'{local_table!r}. Using {newname!r} for relationship name.'
        )
        return newname
    return name


class PostgreSQLProvider(GenericSQLProvider):
    """
    A provider for querying a PostgreSQL database
    """
    default_port = 5432

    def __init__(self, provider_def: dict):
        """
        PostgreSQLProvider Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class
                             data contains the connection information
                             for class DatabaseCursor
        :returns: pygeoapi.provider.sql.PostgreSQLProvider
        """

        driver_name = 'postgresql+psycopg2'
        extra_conn_args = {
            'client_encoding': 'utf8',
            'application_name': 'pygeoapi'
        }
        super().__init__(provider_def, driver_name, extra_conn_args)

    def _get_bbox_filter(self, bbox: list[float]):
        """
        Construct the bounding box filter function
        """
        if not bbox:
            return True  # Let everything through if no bbox

        storage_srid = get_srid(self.storage_crs)
        envelope = ST_MakeEnvelope(*bbox, storage_srid)

        geom_column = getattr(self.table_model, self.geom)
        bbox_filter = ST_Intersects(envelope, geom_column)

        return bbox_filter


class MySQLProvider(GenericSQLProvider):
    """
    A provider for a MySQL database
    """
    default_port = 3306

    def __init__(self, provider_def: dict):
        """
        MySQLProvider Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class
                             data contains the connection information
                             for class DatabaseCursor
        :returns: pygeoapi.provider.sql.MySQLProvider
        """

        driver_name = 'mysql+pymysql'
        extra_conn_args = {
            'charset': 'utf8mb4'
        }
        super().__init__(provider_def, driver_name, extra_conn_args)

    def _get_bbox_filter(self, bbox: list[float]):
        """
        Construct the bounding box filter function
        """
        if not bbox:
            return True  # Let everything through if no bbox

        # If we are using mysql we can't use ST_MakeEnvelope since it is
        # postgis specific and thus we have to use MBRContains with a WKT
        # POLYGON

        # Create WKT POLYGON from bbox: (minx, miny, maxx, maxy)
        minx, miny, maxx, maxy = bbox
        polygon_wkt = f'POLYGON(({minx} {miny}, {maxx} {miny}, {maxx} {maxy}, {minx} {maxy}, {minx} {miny}))'  # noqa
        geom_column = getattr(self.table_model, self.geom)
        # Use MySQL MBRContains for index-accelerated bounding box checks
        bbox_filter = func.MBRContains(
            func.ST_GeomFromText(polygon_wkt), geom_column
        )
        return bbox_filter
