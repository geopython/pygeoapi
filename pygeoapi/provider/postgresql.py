# =================================================================
#
# Authors: Jorge Samuel Mendes de Jesus <jorge.dejesus@protonmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#          Mary Bucknell <mbucknell@usgs.gov>
#          John A Stevenson <jostev@bgs.ac.uk>
#          Colin Blackburn <colb@bgs.ac.uk>
#
# Copyright (c) 2018 Jorge Samuel Mendes de Jesus
# Copyright (c) 2021 Tom Kralidis
# Copyright (c) 2022 John A Stevenson and Colin Blackburn
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

# Testing local docker:
# docker run --name "postgis" \
# -v postgres_data:/var/lib/postgresql -p 5432:5432 \
# -e ALLOW_IP_RANGE=0.0.0.0/0 \
# -e POSTGRES_USER=postgres \
# -e POSTGRES_PASS=postgres \
# -e POSTGRES_DBNAME=test \
# -d -t kartoza/postgis

# Import dump:
# gunzip < tests/data/hotosm_bdi_waterways.sql.gz |
#  psql -U postgres -h 127.0.0.1 -p 5432 test

import logging
from pygeoapi.provider.base import BaseProvider, \
    ProviderConnectionError, ProviderQueryError, ProviderItemNotFoundError

from sqlalchemy import create_engine, MetaData, PrimaryKeyConstraint, asc, desc
from sqlalchemy.exc import InvalidRequestError, OperationalError
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker, load_only
from sqlalchemy.sql.expression import and_
from geoalchemy2 import Geometry  # noqa - this isn't used explicitly but is needed to process Geometry columns
from pygeofilter.backends.sqlalchemy.evaluate import to_filter

import shapely
from geoalchemy2.shape import to_shape

LOGGER = logging.getLogger(__name__)


class PostgreSQLProvider(BaseProvider):
    """Generic provider for Postgresql based on psycopg2
    using sync approach and server side
    cursor (using support class DatabaseCursor)
    """
    def __init__(self, provider_def):
        """
        PostgreSQLProvider Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class
                             data contains the connection information
                             for class DatabaseCursor

        :returns: pygeoapi.provider.base.PostgreSQLProvider
        """
        LOGGER.debug('Initialising PostgreSQL provider.')
        super().__init__(provider_def)

        self.table = provider_def['table']
        self.id_field = provider_def['id_field']
        self.geom = provider_def.get('geom_field', 'geom')

        LOGGER.debug('Name: {}'.format(self.name))
        LOGGER.debug('Table: {}'.format(self.table))
        LOGGER.debug('ID field: {}'.format(self.id_field))
        LOGGER.debug('Geometry field: {}'.format(self.geom))

        # Store database parameters
        self.conn_dic = provider_def['data']

        # Read table information from database
        self._store_db_parameters(provider_def['data'])
        self.engine = self._create_engine()
        LOGGER.debug('DB connection: {}'.format(repr(self.engine)))
        self.table_model = self._reflect_table_model()
        self.fields = self.get_fields()

    def query(self, offset=0, limit=10, resulttype='results',
              bbox=[], datetime_=None, properties=[], sortby=[],
              select_properties=[], skip_geometry=False, q=None,
              cql_ast=None, **kwargs):
        """
        Query Postgis for all the content.
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

        :returns: GeoJSON FeaturesCollection
        """
        LOGGER.debug('Querying PostGIS')
        # Create session to run a query
        Session = sessionmaker(bind=self.engine)
        session = Session()

        # Prepare filters
        property_filters = self._get_property_filters(properties)
        cql_filters = self._get_cql_filters(cql_ast)
        order_by_clauses = self._get_order_by_clauses(sortby, self.table_model)
        selected_properties = self._select_properties_clause(select_properties,
                                                             skip_geometry)

        # Execute the query
        results = (session.query(self.table_model)
                   .filter(property_filters)
                   .filter(cql_filters)
                   .order_by(*order_by_clauses)
                   .options(selected_properties)
                   .offset(offset))

        # Prepare and return feature collection response
        response = {
            'type': 'FeatureCollection',
            'features': []
        }

        if resulttype == "hits":
            # User requested hit count
            response['numberMatched'] = results.count()
            return response

        if not results:
            # Empty response
            return response

        for item in results.limit(limit):
            response['features'].append(
                self._sqlalchemy_to_feature(item)
            )

        return response

    def get_fields(self):
        """
        Return fields (columns) from PostgreSQL table

        :returns: dict of fields
        """
        LOGGER.debug('Get available fields/properties')

        fields = {}
        for column in self.table_model.__table__.columns:
            fields[column.name] = str(column.type)

        fields.pop(self.geom)  # Exclude geometry column

        return fields

    def get(self, identifier, **kwargs):
        """
        Query the provider for a specific
        feature id e.g: /collections/hotosm_bdi_waterways/items/13990765

        :param identifier: feature id

        :returns: GeoJSON FeaturesCollection
        """
        LOGGER.debug(f'Get item by ID: {identifier}')
        Session = sessionmaker(bind=self.engine)
        session = Session()

        # Retrieve data from database as feature
        query = session.query(self.table_model)
        item = query.get(identifier)
        if item is None:
            msg = f"No such item: {self.id_field}={identifier}."
            raise ProviderItemNotFoundError(msg)
        feature = self._sqlalchemy_to_feature(item)

        # Add fields for previous and next items
        id_field = getattr(self.table_model, self.id_field)
        prev_item = (session.query(self.table_model)
                     .order_by(id_field.desc())
                     .filter(id_field < identifier)
                     .first())
        next_item = (session.query(self.table_model)
                     .order_by(id_field.asc())
                     .filter(id_field > identifier)
                     .first())
        feature['prev'] = (getattr(prev_item, self.id_field)
                           if prev_item is not None else identifier)
        feature['next'] = (getattr(next_item, self.id_field)
                           if next_item is not None else identifier)

        return feature

    def _store_db_parameters(self, parameters):
        self.db_user = parameters.get('user')
        self.db_host = parameters.get('host')
        self.db_port = parameters.get('port', 5432)
        self.db_name = parameters.get('dbname')
        self.db_search_path = parameters.get('search_path', ['public'])
        self._db_password = parameters.get('password')

    def _create_engine(self):
        """
        Create a SQL Alchemy engine for the database. It doesn't connect at
        this point.
        """
        conn_str = (
            'postgresql+psycopg2://'
            f'{self.db_user}:{self._db_password}@'
            f'{self.db_host}:{self.db_port}/'
            f'{self.db_name}'
        )
        engine = create_engine(conn_str)
        return engine

    def _reflect_table_model(self):
        """
        Reflect database metadata to create a SQL Alchemy model corresponding
        to target table.  The database is first connected here.
        """
        metadata = MetaData(self.engine)

        # Look for table in the first schema in the search path
        try:
            schema = self.db_search_path[0]
            metadata.reflect(schema=schema, only=[self.table], views=True)
        except OperationalError:
            msg = (f"Could not connect to {repr(self.engine.url)} "
                   "(password hidden).")
            raise ProviderConnectionError(msg)
        except InvalidRequestError:
            msg = (f"Table '{self.table}' not found in schema '{schema}' "
                   f"on {repr(self.engine.url)}.")
            raise ProviderQueryError(msg)

        # Create SQLAlchemy model from reflected table
        # It is necessary to add the primary key constraint because SQLAlchemy
        # requires it to reflect the table, but a view in a PostgreSQL database
        # does not have a primary key defined.
        sqlalchemy_table_def = metadata.tables[f'{schema}.{self.table}']
        try:
            sqlalchemy_table_def.append_constraint(
                PrimaryKeyConstraint(self.id_field)
            )
        except KeyError:
            msg = (f"No such id_field column ({self.id_field}) on "
                   f"{schema}.{self.table}.")
            raise ProviderQueryError(msg)

        Base = automap_base(metadata=metadata)
        Base.prepare()
        TableModel = getattr(Base.classes, self.table)

        return TableModel

    def _sqlalchemy_to_feature(self, item):
        feature = {
            'type': 'Feature'
        }

        # Add properties from item
        item_dict = item.__dict__
        item_dict.pop('_sa_instance_state')  # Internal SQLAlchemy metadata
        feature['properties'] = item_dict
        feature['id'] = item_dict.pop(self.id_field)

        # Convert geometry to GeoJSON style
        if feature['properties'].get(self.geom):
            wkb_geom = feature['properties'].pop(self.geom)
            shapely_geom = to_shape(wkb_geom)
            geojson_geom = shapely.geometry.mapping(shapely_geom)
            feature['geometry'] = geojson_geom
        else:
            feature['geometry'] = None

        return feature

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

    def _get_cql_filters(self, cql_ast):
        if not cql_ast:
            return True  # Let everything through

        # Convert cql_ast into SQL Alchemy filters
        field_mapping = {
            column_name: getattr(self.table_model, column_name)
            for column_name in self.table_model.__table__.columns.keys()}
        cql_filters = to_filter(cql_ast, field_mapping)

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

    def _select_properties_clause(self, select_properties, skip_geometry):
        # List the column names that we want
        if select_properties:
            # if we don't create a fresh list here and modify select_properties
            # instead, it breaks the tests which check for match between
            # requested and returned
            column_names = select_properties.copy()
        else:
            # get_fields() doesn't include geometry column
            column_names = list(self.get_fields().keys())

        if not skip_geometry:
            column_names.append(self.geom)

        # Convert names to SQL Alchemy clause
        selected_columns = []
        for column_name in column_names:
            column = getattr(self.table_model, column_name)
            selected_columns.append(column)
        selected_properties_clause = load_only(*selected_columns)

        return selected_properties_clause
