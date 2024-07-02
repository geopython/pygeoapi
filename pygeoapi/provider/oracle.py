# =================================================================
#
# Authors: Andreas Kosubek <andreas.kosubek@ama.gv.at>
# Authors: Moritz Langer <moritz.b.langer@gmail.com>
#
# Copyright (c) 2023 Andreas Kosubek
# Copyright (c) 2024 Moritz Langer
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

import importlib
import json
import logging
import os
import threading
from typing import Optional

import oracledb
import pyproj

from pygeoapi.api import DEFAULT_STORAGE_CRS

from pygeoapi.provider.base import (
    BaseProvider,
    ProviderConnectionError,
    ProviderGenericError,
    ProviderInvalidQueryError,
    ProviderItemNotFoundError,
    ProviderQueryError,
)

from pygeoapi.util import get_crs_from_uri

LOGGER = logging.getLogger(__name__)


class DatabaseConnection:
    """Database connection class to be used as 'with' statement.
    The class returns a connection object.
    """
    pool = None  # Class-level connection pool
    lock = threading.Lock()

    @classmethod
    def create_pool(cls, conn_dict, oracle_pool_min, oracle_pool_max):
        """Initialize the connection pool for the class
           Lock is implemented before function call at __init__"""
        dsn = cls._make_dsn(conn_dict)
        # Create the pool

        p = oracledb.create_pool(
                    user=conn_dict["user"],
                    password=conn_dict["password"],
                    dsn=dsn,
                    min=oracle_pool_min,
                    max=oracle_pool_max,
                    increment=1,
                )
        LOGGER.debug("Connection pool created successfully.")

        return p

    def __init__(self, conn_dic, table, properties=[], context="query"):
        """
        OracleProvider Class constructor

        :param conn_dic: dictionary with connection parameters
            service_name - the service name of the database instance
            sid - sid of the database instance
            tns_name - name of the tnsnames.ora entry
            external_auth - External authentication e.g. wallet
            tns_admin - path to tnsnames.ora configuration file
            user - user name used to authenticate
            password - password used to authenticate
            host - database host address
            port - connection port number
             (defaults to 1521 if not provided)
            init_oracle_client -

        :param table: table name containing the data. This variable is used to
                assemble column information
        :param properties: User-specified subset of column names to expose
        :param context: query or hits, if query then it will determine
                table column otherwise will not do it
        :returns: DatabaseConnection
        """

        self.conn_dict = conn_dic
        self.table = table
        self.context = context
        self.columns = (
            None  # Comma sepparated string with column names (for SQL query)
        )
        self.properties = [item.lower() for item in properties]
        self.fields = {}  # Dict of columns. Key is col name, value is type
        oracle_pool_min = int(os.environ.get('ORACLE_POOL_MIN', 0))
        oracle_pool_max = int(os.environ.get('ORACLE_POOL_MAX', 0))
        # Initialize the connection pool if it hasn't been initialized
        if oracle_pool_min and oracle_pool_max:
            LOGGER.debug("Found environment variables for session pooling:")
            LOGGER.debug(f"ORACLE_POOL_MIN: {oracle_pool_min}")
            LOGGER.debug(f"ORACLE_POOL_MAX: {oracle_pool_max}")
            with DatabaseConnection.lock:
                if DatabaseConnection.pool is None:
                    LOGGER.debug(f"self.conn_dict contains {self.conn_dict}")
                    DatabaseConnection.pool = DatabaseConnection.create_pool(
                        self.conn_dict, oracle_pool_min, oracle_pool_max
                    )
                    LOGGER.debug(
                        "Initialized connection pool with "
                        f"{DatabaseConnection.pool.max} connections"
                    )

    @staticmethod
    def _make_dsn(conn_dict):
        if conn_dict.get("init_oracle_client", False):
            oracledb.init_oracle_client()

        # Connect with tnsnames.ora entry and Login with Oracle Wallet
        if conn_dict.get("external_auth") == "wallet":
            LOGGER.debug(
                "Oracle connect with tnsnames.ora entry \
                and login with Oracle Wallet"
            )
            if "tns_name" not in conn_dict:
                raise ProviderConnectionError(
                    "tns_name must be set for external authentication!"
                )

            dsn = conn_dict["tns_name"]

        # Connect with SERVICE_NAME
        if "service_name" in conn_dict:
            LOGGER.debug(
                f"Oracle connect with service_name: \
                    {conn_dict['service_name']}"
            )

            if "host" not in conn_dict:
                raise ProviderConnectionError(
                    "Host must be set for connection with service_name!"
                )

            dsn = oracledb.makedsn(
                conn_dict["host"],
                conn_dict.get("port", 1521),
                service_name=conn_dict["service_name"],
            )

        # Connect with SID
        elif "sid" in conn_dict:
            LOGGER.debug(
                f"Oracle connect with sid: {conn_dict['sid']}"
            )

            if "host" not in conn_dict:
                raise ProviderConnectionError(
                    "Host must be set for connection with sid!"
                )

            dsn = oracledb.makedsn(
                conn_dict["host"],
                conn_dict.get("port", 1521),
                sid=conn_dict["sid"],
            )

        # Connect with tnsnames.ora entry
        elif "tns_name" in conn_dict:
            LOGGER.debug(
                f"Oracle connect with tns_name: \
                    {conn_dict['tns_name']}"
            )
            dsn = conn_dict["tns_name"]

        else:
            raise ProviderConnectionError(
                "One of service_name, sid or tns_name must be specified!"
            )

        LOGGER.debug(f"Oracle DSN string: {dsn}")

        return dsn

    def __enter__(self):
        """Acquires a connection from the pool."""
        try:
            if DatabaseConnection.pool:
                self.conn = DatabaseConnection.pool.acquire()
                LOGGER.debug("Connection acquired from pool .")
                LOGGER.debug(f"Connection from pool is {self.conn}.")
            else:
                dsn = self._make_dsn(self.conn_dict)
                LOGGER.debug(f"Created dsn for single connection with params: {dsn}")  # noqa
                # Connect with tnsnames.ora entry and Login with Oracle Wallet  # noqa
                if self.conn_dict.get("external_auth") == "wallet":
                    self.conn = oracledb.connect(externalauth=True, dsn=dsn)

                # Connect with tnsnames.ora entry,
                # TNS_ADMIN is set via configuration
                if "tns_admin" in self.conn_dict:
                    self.conn = oracledb.connect(
                        user=self.conn_dict["user"],
                        password=self.conn_dict["password"],
                        dsn=dsn,
                        config_dir=self.conn_dict["tns_admin"],
                    )

                # Connect with user / password via dsn string
                # When dsn is a TNS name, the environment variable TNS_ADMIN must   # noqa
                # be set (Path to tnsnames.ora file)
                else:
                    self.conn = oracledb.connect(
                        user=self.conn_dict["user"],
                        password=self.conn_dict["password"],
                        dsn=dsn,
                    )

        except oracledb.DatabaseError as e:
            if DatabaseConnection.pool:
                LOGGER.error("Couldn't acquire a connection from the pool.")
                LOGGER.error(e)
            else:
                LOGGER.error(
                    f"Couldn't connect to Oracle using:{str(self.conn_dict)}"
                )
                LOGGER.error(e)
            raise ProviderConnectionError(e)

        # Check if table name has schema/owner inside
        # If not, current user is set
        table_parts = self.table.split(".")
        if len(table_parts) == 2:
            schema = table_parts[0]
            table = table_parts[1]
        else:
            schema = self.conn_dict["user"]
            table = self.table

        LOGGER.debug("Schema: " + schema)
        LOGGER.debug("Table: " + table)

        if self.context == "query":
            columns = dict(self._get_table_columns(schema, table))

            # Populate dictionary for columns with column type
            # NOTE: we want all columns available here because they are
            #       used for filtering in the where clause, not only
            #       the ones that are returned to the client.
            for k, v in columns.items():
                self.fields[k.lower()] = {"type": v}

            filtered_columns = set(self.fields)
            if self.properties:
                filtered_columns &= {k.lower() for k in self.properties}

            # fields which are part of the output
            self.filtered_fields = {
                k: v for k, v in self.fields.items() if k in filtered_columns
            }

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Releases the connection back to the pool.
        """
        try:
            if DatabaseConnection.pool:
                DatabaseConnection.pool.release(self.conn)
                LOGGER.debug("Connection released back to pool.")
            else:
                self.conn.close()
                LOGGER.debug("Single Connection closed")
        except oracledb.DatabaseError as e:
            LOGGER.error("Error closing the connection.")
            LOGGER.error(e)

    def _get_table_columns(self, schema, table):
        """
        Returns an array with all column names and data types
        from Oracle table ALL_TAB_COLUMNS.
        Lookup for public and private synonyms.
        Throws ProviderGenericError when table not exist or accessible.
        """

        sql = """
              SELECT COUNT(1)
                FROM all_objects
               WHERE object_type IN ('VIEW','TABLE','MATERIALIZED VIEW')
                 AND object_name = UPPER(:table_name)
                 AND owner = UPPER(:owner)
              """
        with self.conn.cursor() as cur:
            cur.execute(sql, {"table_name": table, "owner": schema})
            result = cur.fetchone()

        if result[0] == 0:
            sql = """
                  SELECT COUNT(1)
                    FROM all_synonyms
                   WHERE synonym_name = UPPER(:table_name)
                     AND owner = UPPER(:owner)
                  """
            with self.conn.cursor() as cur:
                cur.execute(sql, {"table_name": table, "owner": schema})
                result = cur.fetchone()

            if result[0] == 0:
                sql = """
                      SELECT COUNT(1)
                        FROM all_synonyms
                       WHERE synonym_name = UPPER(:table_name)
                         AND owner = 'PUBLIC'
                      """
                with self.conn.cursor() as cur:
                    cur.execute(sql, {"table_name": table})
                    result = cur.fetchone()

                if result[0] == 0:
                    raise ProviderGenericError(
                        f"Table {schema}.{table} not found!"
                    )

                else:
                    schema = "PUBLIC"

            sql = """
                  SELECT table_owner, table_name
                    FROM all_synonyms
                   WHERE synonym_name = UPPER(:table_name)
                     AND owner = UPPER(:owner)
                  """
            with self.conn.cursor() as cur:
                cur.execute(sql, {"table_name": table, "owner": schema})
                result = cur.fetchone()

            schema = result[0]
            table = result[1]

        # Get table column names and types, excluding geometry
        query_cols = """
                     SELECT column_name, data_type
                       FROM all_tab_columns
                      WHERE table_name = UPPER(:table_name)
                        AND owner = UPPER(:owner)
                        AND data_type != 'SDO_GEOMETRY'
                     """
        with self.conn.cursor() as cur:
            cur.execute(query_cols, {"table_name": table, "owner": schema})
            result = cur.fetchall()

        return result


class OracleProvider(BaseProvider):
    def __init__(self, provider_def):
        """
        OracleProvider Class constructor

        :param provider_def: provider definitions from yml pygeoapi-config.
                             data,id_field, name set in parent class
                             data contains the connection information
                             for class DatabaseCursor

        :returns: pygeoapi.provider.base.OracleProvider
        """

        super().__init__(provider_def)

        # Table properties
        self.table = provider_def["table"]
        self.id_field = provider_def["id_field"]
        self.conn_dic = provider_def["data"]
        self.geom = provider_def["geom_field"]
        self.properties = [item.lower() for item in self.properties]
        self.mandatory_properties = provider_def.get("mandatory_properties")
        self.extra_properties = provider_def.get("extra_properties", [])

        # SQL manipulator properties
        self.sql_manipulator = provider_def.get("sql_manipulator")
        self.sql_manipulator_options = provider_def.get(
            "sql_manipulator_options"
        )

        # CRS properties
        storage_crs_uri = provider_def.get("storage_crs", DEFAULT_STORAGE_CRS)
        self.storage_crs = get_crs_from_uri(storage_crs_uri)

        # TODO See Issue #1393
        # default_crs_uri = provider_def.get("default_crs", DEFAULT_CRS)
        # self.default_crs = get_crs_from_uri(default_crs_uri)

        # SDO properties
        self.sdo_param = provider_def.get("sdo_param")
        self.sdo_operator = provider_def.get("sdo_operator", "sdo_filter")

        LOGGER.debug("Setting Oracle properties:")
        LOGGER.debug(f"Name:{self.name}")
        LOGGER.debug(f"ID_field:{self.id_field}")
        LOGGER.debug(f"Table:{self.table}")
        LOGGER.debug(f"sdo_param: {self.sdo_param}")
        LOGGER.debug(f"sdo_operator: {self.sdo_operator}")
        LOGGER.debug(f"storage_crs {self.storage_crs}")

        # TODO See Issue #1393
        # LOGGER.debug(f"default_crs: {self.default_crs}")

        self.get_fields()

    def get_fields(self):
        """
        Get fields from Oracle table (columns are field)

        :returns: dict of fields
        """
        LOGGER.debug("Get available fields/properties")

        if not self.fields:
            with DatabaseConnection(
                self.conn_dic, self.table, properties=self.properties
            ) as db:
                self.fields = db.fields
        return self.fields

    def _get_where_clauses(
        self,
        properties,
        bbox,
        bbox_crs,
        sdo_param=None,
        sdo_operator="sdo_filter",
    ):
        """
        Generarates WHERE conditions to be implemented in query.
        Private method mainly associated with query method
        :param properties: list of tuples (name, value)
        :param bbox: bounding box [minx,miny,maxx,maxy]

        :returns: Dictionary with sql where clause and bind variables
        """
        LOGGER.debug("Get where clause with bind variables as dictionary")

        where_dict = {"clause": "", "properties": {}}

        where_conditions = []

        if properties:
            prop_clauses = [f"{key} = :{key}" for key, value in properties]
            where_conditions += prop_clauses
            where_dict["properties"] = dict(properties)

        if bbox:
            bbox_dict = {"clause": "", "properties": {}}

            if sdo_operator == "sdo_relate":
                if not sdo_param:
                    sdo_param = "mask=anyinteract"

                bbox_dict["properties"] = {
                    "srid": self._get_srid_from_crs(bbox_crs),
                    "minx": bbox[0],
                    "miny": bbox[1],
                    "maxx": bbox[2],
                    "maxy": bbox[3],
                    "sdo_param": sdo_param,
                }

                bbox_query = f"""
                sdo_relate({self.geom},
                           mdsys.sdo_geometry(2003,
                                              :srid,
                                              NULL,
                                              mdsys.sdo_elem_info_array(
                                                    1,
                                                    1003,
                                                    3
                                              ),
                                              mdsys.sdo_ordinate_array(
                                                    :minx,
                                                    :miny,
                                                    :maxx,
                                                    :maxy
                                              )
                           ),
                           :sdo_param
                ) = 'TRUE'
                """

            else:
                bbox_dict["properties"] = {
                    "srid": self._get_srid_from_crs(bbox_crs),
                    "minx": bbox[0],
                    "miny": bbox[1],
                    "maxx": bbox[2],
                    "maxy": bbox[3],
                    "sdo_param": sdo_param,
                }

                bbox_query = f"""
                sdo_filter({self.geom},
                           mdsys.sdo_geometry(2003,
                                              :srid,
                                              NULL,
                                              mdsys.sdo_elem_info_array(
                                                    1,
                                                    1003,
                                                    3
                                              ),
                                              mdsys.sdo_ordinate_array(
                                                    :minx,
                                                    :miny,
                                                    :maxx,
                                                    :maxy
                                              )
                           ),
                           :sdo_param
                ) = 'TRUE'
                """

            bbox_dict["clause"] = bbox_query

            where_conditions.append(bbox_dict["clause"])
            where_dict["properties"].update(bbox_dict["properties"])

        if where_conditions:
            where_dict["clause"] = f" WHERE {' AND '.join(where_conditions)}"

        LOGGER.debug(where_dict)

        return where_dict

    def _get_orderby(self, sortby):
        """
        Private function: Get ORDER BY clause

        :param sortby: list of dicts (property, order)

        :returns: STA $orderby string
        """
        sort_map = {"+": "ASC", "-": "DESC"}
        ret = [
            f"{sort['property']} {sort_map[sort['order']]}" for sort in sortby
        ]

        return f"ORDER BY {','.join(ret)}"

    def _get_extra_columns_expression(self):
        """Returns part of SELECT clause for extra properties"""
        return "".join(
            f", {e_prop}" for e_prop in self.extra_properties
        )

    def _output_type_handler(
        self, cursor, name, default_type, size, precision, scale
    ):
        """
        Output type handler for Oracle LOB datatypes
        """
        if default_type == oracledb.DB_TYPE_CLOB:
            return cursor.var(
                oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize
            )
        if default_type == oracledb.DB_TYPE_BLOB:
            return cursor.var(
                oracledb.DB_TYPE_LONG_RAW, arraysize=cursor.arraysize
            )

    def _get_srid_from_crs(self, crs):
        """
        Works only for EPSG codes!
        Anything else is hard coded!
        """
        if crs == "OGC:CRS84":
            srid = 4326
        elif crs == "OGC:CRS84h":
            srid = 4326
        else:
            srid = crs.to_epsg()

        return srid

    def query(
        self,
        offset=0,
        limit=10,
        resulttype="results",
        bbox=None,
        datetime_=None,
        properties=[],
        sortby=[],
        skip_geometry=False,
        select_properties=[],
        crs_transform_spec=None,
        q=None,
        language=None,
        filterq=None,
        **kwargs,
    ):
        """
        Query Oracle for all the content.

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

        :returns: GeoJSON FeaturesCollection
        """

        # Check mandatory filter properties
        property_dict = dict(properties)
        if self.mandatory_properties:
            for mand_col in self.mandatory_properties:
                if mand_col == "bbox" and not bbox:
                    raise ProviderInvalidQueryError(
                        f"Missing mandatory filter property: {mand_col}"
                    )
                else:
                    if mand_col not in property_dict:
                        raise ProviderInvalidQueryError(
                            f"Missing mandatory filter property: {mand_col}"
                        )

        with DatabaseConnection(
            self.conn_dic,
            self.table,
            properties=self.properties,
            context="hits",
        ) as db:
            cursor = db.conn.cursor()

            where_dict = self._get_where_clauses(
                properties=properties,
                bbox=bbox,
                bbox_crs=self.storage_crs,
                sdo_param=self.sdo_param,
                sdo_operator=self.sdo_operator,
            )

            # Not dangerous to use self.table as substitution,
            # because of getFields ...
            sql_query = f"SELECT COUNT(1) AS hits \
                            FROM {self.table} \
                            {where_dict['clause']}"
            try:
                cursor.execute(sql_query, where_dict["properties"])
            except oracledb.Error as err:
                LOGGER.error(
                    f"Error executing sql_query: {sql_query}: {err}"
                )
                raise ProviderQueryError()

            hits = cursor.fetchone()[0]
            LOGGER.debug(f"hits: {str(hits)}")

        with DatabaseConnection(
            self.conn_dic, self.table, properties=self.properties
        ) as db:
            db.conn.outputtypehandler = self._output_type_handler

            cursor = db.conn.cursor()

            # Create column list.
            #   Uses columns field that was generated in the Connection class
            #   or the configured columns from the Yaml file.
            props = ", ".join(
                select_properties
                if select_properties
                else db.filtered_fields
            )

            where_dict = self._get_where_clauses(
                properties=properties,
                bbox=bbox,
                bbox_crs=self.storage_crs,
                sdo_param=self.sdo_param,
                sdo_operator=self.sdo_operator,
            )

            # Get correct SRID
            if crs_transform_spec is not None:
                source_crs = pyproj.CRS.from_wkt(
                    crs_transform_spec.source_crs_wkt
                )
                source_srid = self._get_srid_from_crs(source_crs)

                target_crs = pyproj.CRS.from_wkt(
                    crs_transform_spec.target_crs_wkt
                )
                target_srid = self._get_srid_from_crs(target_crs)
            else:
                source_srid = self._get_srid_from_crs(self.storage_crs)
                target_srid = source_srid

                # TODO See Issue #1393
                # target_srid = self._get_srid_from_crs(self.default_crs)
                # If issue is not accepted, this block can be merged with
                # the following block.

            LOGGER.debug(f"source_srid: {source_srid}")
            LOGGER.debug(f"target_srid: {target_srid}")

            # Build geometry column call
            #   When a different output CRS is defined, the geometry
            #   geometry column would be transformed.
            if skip_geometry:
                geom = ""

            elif source_srid != target_srid:
                geom = f""", sdo_cs.transform(t1.{self.geom},
                                             :target_srid).get_geojson()
                             AS geometry """

                where_dict["properties"].update(
                    {"target_srid": int(target_srid)}
                )

            else:
                geom = f", t1.{self.geom}.get_geojson() AS geometry "

            orderby = self._get_orderby(sortby) if sortby else ""

            # Create paging and add placeholders for the
            # SQL manipulation class
            paging_bind = {}
            if limit > 0:
                sql_query = f"SELECT #HINTS# {props} \
                              {self._get_extra_columns_expression()} {geom} \
                              FROM {self.table} t1 #JOIN# \
                              {where_dict['clause']} #WHERE# \
                              {orderby} \
                              OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
                paging_bind = {"offset": offset, "limit": limit}
            else:
                sql_query = f"SELECT #HINTS# {props} \
                        {self._get_extra_columns_expression()} {geom} \
                        FROM {self.table} t1 #JOIN# \
                        {where_dict['clause']} #WHERE# \
                        {orderby}"

            # Create dictionary for sql bind variables
            bind_variables = {**where_dict["properties"], **paging_bind}

            # SQL manipulation plugin
            if self.sql_manipulator:
                LOGGER.debug("sql_manipulator: " + self.sql_manipulator)
                manipulation_class = _class_factory(self.sql_manipulator)
                sql_query, bind_variables = manipulation_class.process_query(
                    db,
                    sql_query,
                    bind_variables,
                    self.sql_manipulator_options,
                    offset,
                    limit,
                    resulttype,
                    bbox,
                    datetime_,
                    properties,
                    sortby,
                    skip_geometry,
                    select_properties,
                    crs_transform_spec,
                    q,
                    language,
                    filterq,
                )

            # Clean up placeholders that aren't used by the
            # manipulation class.
            sql_query = sql_query.replace("#HINTS#", "")
            sql_query = sql_query.replace("#JOIN#", "")
            sql_query = sql_query.replace("#WHERE#", "")

            LOGGER.debug(f"SQL Query: {sql_query}")
            LOGGER.debug(f"Bind variables: {bind_variables}")

            try:
                cursor.execute(sql_query, bind_variables)
            except oracledb.Error as err:
                LOGGER.error(f"Error executing sql_query: {sql_query}")
                LOGGER.error(err)
                raise ProviderQueryError()

            # Convert row resultset to dictionary
            columns = [col[0] for col in cursor.description]
            cursor.rowfactory = lambda *args: dict(zip(columns, args))

            row_data = cursor.fetchall()

            # Generate feature JSON
            features = [self._response_feature(rd) for rd in row_data]
            feature_collection = {
                "numberMatched": hits,
                "type": "FeatureCollection",
                "features": features,
            }

            return feature_collection

    def _get_previous(self, cursor, identifier):
        """
        Query previous ID given current ID

        :param identifier: feature id

        :returns: feature id
        """
        sql = f"SELECT {self.id_field} AS id \
                  FROM {self.table} \
                 WHERE ROWNUM = 1 \
                   AND {self.id_field} < :{self.id_field} \
                 ORDER BY {self.id_field} DESC"

        bind_variables = {self.id_field: identifier}

        LOGGER.debug(f"SQL Query: {sql}")
        LOGGER.debug(f"Bind variables: {str(bind_variables)}")

        cursor.execute(sql, bind_variables)

        item = cursor.fetchall()
        id = item[0][0] if item else None

        return id

    def _get_next(self, cursor, identifier):
        """
        Query next ID given current ID

        :param identifier: feature id

        :returns: feature id
        """
        sql = f"SELECT {self.id_field} AS id \
                  FROM {self.table} \
                 WHERE ROWNUM = 1 \
                   AND {self.id_field} > :{self.id_field} \
                 ORDER BY {self.id_field} ASC"

        bind_variables = {self.id_field: identifier}

        LOGGER.debug(f"SQL Query: {sql}")
        LOGGER.debug(f"Bind variables: {str(bind_variables)}")

        cursor.execute(sql, bind_variables)

        item = cursor.fetchall()
        id = item[0][0] if item else None

        return id

    def get(self, identifier, crs_transform_spec=None, **kwargs):
        """
        Query the provider for a specific
        feature id e.g: /collections/ocrl_lakes/items/1

        :param identifier: feature id

        :returns: GeoJSON FeaturesCollection
        """

        with DatabaseConnection(
            self.conn_dic, self.table, properties=self.properties
        ) as db:
            db.conn.outputtypehandler = self._output_type_handler

            cursor = db.conn.cursor()

            crs_dict = {}

            # Get correct SRIDs
            if crs_transform_spec is not None:
                source_crs = pyproj.CRS.from_wkt(
                    crs_transform_spec.source_crs_wkt
                )
                source_srid = self._get_srid_from_crs(source_crs)

                target_crs = pyproj.CRS.from_wkt(
                    crs_transform_spec.target_crs_wkt
                )
                target_srid = self._get_srid_from_crs(target_crs)

            else:
                source_srid = self._get_srid_from_crs(self.storage_crs)
                target_srid = source_srid

                # TODO See Issue #1393
                # target_srid = self._get_srid_from_crs(self.default_crs)
                # If issue is not accepted, this block can be merged with
                # the following block.

            LOGGER.debug(f"source_srid: {source_srid}")
            LOGGER.debug(f"target_srid: {target_srid}")

            # Build geometry column call
            #   When a different output CRS is defined, the geometry
            #   geometry column would be transformed.
            if source_srid != target_srid:
                crs_dict = {"target_srid": target_srid}

                geom_sql = f""", sdo_cs.transform(t1.{self.geom},
                                             :target_srid).get_geojson()
                                    AS geometry """

            else:
                geom_sql = f", t1.{self.geom}.get_geojson() AS geometry "

            columns = ", ".join(db.filtered_fields)
            sql_query = f"SELECT {columns} \
                            {self._get_extra_columns_expression()} \
                            {geom_sql} \
                            FROM {self.table} t1 \
                           WHERE {self.id_field} = :in_id"

            bind_variables = {"in_id": identifier, **crs_dict}

            # SQL manipulation plugin
            if self.sql_manipulator:
                LOGGER.debug("sql_manipulator: " + self.sql_manipulator)
                manipulation_class = _class_factory(self.sql_manipulator)
                sql_query, bind_variables = manipulation_class.process_get(
                    db,
                    sql_query,
                    bind_variables,
                    self.sql_manipulator_options,
                    identifier,
                )

            LOGGER.debug(f"SQL Query: {sql_query}")
            LOGGER.debug(f"Identifier: {identifier}")

            try:
                cursor.execute(sql_query, bind_variables)
            except oracledb.Error as err:
                LOGGER.error(f"Error executing sql_query: {sql_query}")
                LOGGER.error(err)
                raise ProviderQueryError()

            # Convert row resultset to dictionary
            columns = [col[0] for col in cursor.description]
            cursor.rowfactory = lambda *args: dict(zip(columns, args))

            results = cursor.fetchall()

            row_data = None
            if results:
                row_data = results[0]
            feature = self._response_feature(row_data)

            if feature:
                previous_id = self._get_previous(cursor, identifier)
                if previous_id:
                    feature["prev"] = previous_id
                next_id = self._get_next(cursor, identifier)
                if next_id:
                    feature["next"] = self._get_next(cursor, identifier)
                return feature
            else:
                err = f"item identifier {identifier} not found"
                LOGGER.error(err)
                raise ProviderItemNotFoundError(err)

    def _response_feature(self, row_data):
        """
        Assembles GeoJSON output from DB query

        :param row_data: DB row result

        :returns: `dict` of GeoJSON Feature
        """

        if row_data:
            feature = {"type": "Feature"}

            if row_data.get("GEOMETRY"):
                feature["geometry"] = json.loads(row_data["GEOMETRY"])
            else:
                feature["geometry"] = None

            feature["properties"] = {
                key.lower(): value
                for (key, value) in row_data.items()
                if key != "GEOMETRY"
            }
            feature["id"] = feature["properties"].pop(self.id_field)

            return feature
        else:
            return None

    def _response_feature_hits(self, hits):
        """Assembles GeoJSON/Feature number
        e.g: http://localhost:5000/collections/lakes/items?resulttype=hits

        :returns: GeoJSON FeaturesCollection
        """

        feature_collection = {"features": [], "type": "FeatureCollection"}
        feature_collection["numberMatched"] = hits

        return feature_collection

    def create(self, request_data):
        """
        Creates on record with the given data.

        :param request_data: Data of the record as Geojson
        :returns: ID of the created record
        """
        LOGGER.debug(f"Request data: {str(request_data)}")

        with DatabaseConnection(
            self.conn_dic, self.table, properties=self.properties
        ) as db:
            cursor = db.conn.cursor()

            columns = [*request_data.get("properties")]

            # Filter properties to get only columns who are
            # in the column list
            columns = [
                col
                for col in columns
                if col.lower() in db.filtered_fields
            ]

            # Filter function to get only properties who are
            # in the column list
            def filter_binds(pair):
                return pair[0].lower() in db.filtered_fields

            # Filter bind variables
            bind_variables = dict(
                filter(filter_binds, request_data.get("properties").items())
            )

            columns_str = ", ".join([col for col in columns])
            values_str = ", ".join([f":{col}" for col in columns])

            sql_query = f"""
                        INSERT INTO {self.table} (
                            {columns_str},
                            {self.geom}
                        )
                        VALUES (
                            {values_str},
                            sdo_util.from_geojson(:in_geometry, NULL, :srid)
                        )
                        RETURNING {self.id_field} INTO :out_id
                        """

            # Out bind variable for the id of the created row
            out_id = cursor.var(int)

            # Bind variable for the SDO_GEOMETRY type
            # in_geometry = self._get_sdo_from_geojson_geometry(
            #     db.conn, request_data.get("geometry").get("coordinates")[0]
            # )
            in_geometry = request_data.get("geometry")

            bind_variables = {
                **bind_variables,
                "out_id": out_id,
                "in_geometry": json.dumps(in_geometry),
                "srid": self._get_srid_from_crs(self.storage_crs),
            }

            # SQL manipulation plugin
            if self.sql_manipulator:
                LOGGER.debug("sql_manipulator: " + self.sql_manipulator)
                manipulation_class = _class_factory(self.sql_manipulator)
                sql_query, bind_variables = manipulation_class.process_create(
                    db,
                    sql_query,
                    bind_variables,
                    self.sql_manipulator_options,
                    request_data,
                )

            LOGGER.debug(f"SQL Query: {sql_query}")
            LOGGER.debug(f"Bind variables: {bind_variables}")

            try:
                cursor.execute(sql_query, bind_variables)
                db.conn.commit()
            except oracledb.Error as err:
                LOGGER.error(f"Error executing sql_query: {sql_query}")
                LOGGER.error(err)

                db.conn.rollback()

                raise ProviderQueryError()

            identifier = out_id.getvalue()

        return identifier[0]

    def update(self, identifier, request_data):
        """
        Updates the record with the given identifier.

        :param identifier: ID of the record
        :param request_data: Data of the record as Geojson
        :returns: True
        """
        LOGGER.debug(f"Identifier: {identifier}")
        LOGGER.debug(f"Request data: {str(request_data)}")

        with DatabaseConnection(
            self.conn_dic, self.table, properties=self.properties
        ) as db:
            cursor = db.conn.cursor()

            columns = [*request_data.get("properties")]

            # Filter properties to get only columns who are
            # in the column list
            columns = [
                col
                for col in columns
                if col.lower() in db.filtered_fields
            ]

            # Filter function to get only properties who are
            # in the column list
            def filter_binds(pair):
                return pair[0].lower() in db.filtered_fields

            # Filter bind variables
            bind_variables = dict(
                filter(
                    filter_binds,
                    request_data.get("properties").items(),
                )
            )

            set_str = ", ".join([f" {col} = :{col}" for col in columns])

            sql_query = f"""
                        UPDATE {self.table}
                           SET {set_str}
                             , {self.geom} = sdo_util.from_geojson(
                                                 :in_geometry,
                                                 NULL,
                                                 :srid
                                             )
                         WHERE {self.id_field} = :in_id
                        """

            # Bind variable for the SDO_GEOMETRY type
            # in_geometry = self._get_sdo_from_geojson_geometry(
            #     db.conn, request_data.get("geometry").get("coordinates")[0]
            # )
            in_geometry = json.dumps(request_data.get("geometry"))

            bind_variables = {
                **bind_variables,
                "in_id": identifier,
                "in_geometry": in_geometry,
                "srid": self._get_srid_from_crs(self.storage_crs),
            }

            # SQL manipulation plugin
            if self.sql_manipulator:
                LOGGER.debug("sql_manipulator: " + self.sql_manipulator)
                manipulation_class = _class_factory(self.sql_manipulator)
                sql_query, bind_variables = manipulation_class.process_update(
                    db,
                    sql_query,
                    bind_variables,
                    self.sql_manipulator_options,
                    identifier,
                    request_data,
                )

            LOGGER.debug(sql_query)
            LOGGER.debug(bind_variables)

            try:
                cursor.execute(sql_query, bind_variables)
                rowcount = cursor.rowcount
                db.conn.commit()
            except oracledb.Error as err:
                LOGGER.error(f"Error executing sql_query: {sql_query}")
                LOGGER.error(err)

                db.conn.rollback()

                raise ProviderQueryError()

        return rowcount == 1

    def delete(self, identifier):
        """
        Deletes the record with the given identifier.

        :param identifier: ID of the record
        :returns: True
        """

        LOGGER.debug(f"Identifier: {identifier}")

        with DatabaseConnection(
            self.conn_dic, self.table, properties=self.properties
        ) as db:
            cursor = db.conn.cursor()

            sql_query = f"DELETE FROM {self.table} \
                           WHERE {self.id_field} = :in_id"

            bind_variables = {
                "in_id": identifier,
            }

            # SQL manipulation plugin
            if self.sql_manipulator:
                LOGGER.debug("sql_manipulator: " + self.sql_manipulator)
                manipulation_class = _class_factory(self.sql_manipulator)
                sql_query, bind_variables = manipulation_class.process_delete(
                    db,
                    sql_query,
                    bind_variables,
                    self.sql_manipulator_options,
                    identifier,
                )

            LOGGER.debug(sql_query)
            LOGGER.debug(bind_variables)

            try:
                cursor.execute(sql_query, bind_variables)
                rowcount = cursor.rowcount
                db.conn.commit()
            except oracledb.Error as err:
                LOGGER.error(f"Error executing sql_query: {sql_query}")
                LOGGER.error(err)

                db.conn.rollback()

                raise ProviderQueryError()

        return rowcount == 1

    def _get_sdo_from_geojson_geometry(self, conn, geometry, srid=4326):
        """
        Get an filled Python object for Oracle Type SDO_GEOMETRY.

        :param conn: oracledb connection instance
        :param geometry: Ordinate Array from Geojson
        :param srid: SRID defaults to 4326 when not provided
        :return Python object instance:
        """
        gtype = 2003
        elemInfo = [1, 1003, 1]

        # Get Oracle types
        obj_type = conn.gettype("MDSYS.SDO_GEOMETRY")
        element_info_type_obj = conn.gettype("MDSYS.SDO_ELEM_INFO_ARRAY")
        ordinate_type_obj = conn.gettype("MDSYS.SDO_ORDINATE_ARRAY")

        obj = obj_type.newobject()
        obj.SDO_GTYPE = gtype
        obj.SDO_SRID = srid or 4326
        obj.SDO_ELEM_INFO = element_info_type_obj.newobject()
        obj.SDO_ELEM_INFO.extend(elemInfo)
        obj.SDO_ORDINATES = ordinate_type_obj.newobject()
        for coord in geometry:
            obj.SDO_ORDINATES.extend(coord)

        return obj


def _class_factory(
    module_class_string, super_cls: Optional[type] = None, **kwargs
):
    """
    Factory function for class instances.
    Used for dynamic loading of the SQL manipulation class.

    :param module_class_string: full name of the class to create an object of
    :param super_cls: expected super class for validity, None if bypass
    :param kwargs: parameters to pass
    :return instance of the given class:
    """
    module_name, class_name = module_class_string.rsplit(".", 1)
    module = importlib.import_module(module_name)
    LOGGER.debug(f"reading class {class_name} from module {module_name}")
    cls = getattr(module, class_name)
    if super_cls is not None:
        assert issubclass(
            cls, super_cls
        ), f"class {class_name} should inherit from {super_cls.__name__}"
    LOGGER.debug(f"initialising {class_name} with params {kwargs}")
    obj = cls(**kwargs)
    return obj
