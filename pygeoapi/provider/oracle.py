# =================================================================
#
# Authors: Andreas Kosubek <andreas.kosubek@ama.gv.at>
#
# Copyright (c) 2023 Andreas Kosubek
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

import importlib
import json
import logging
from typing import Optional

import oracledb

from pygeoapi.provider.base import (
    BaseProvider,
    ProviderConnectionError,
    ProviderItemNotFoundError,
    ProviderQueryError,
)

LOGGER = logging.getLogger(__name__)

oracledb.init_oracle_client()


class DatabaseConnection:
    """Database connection class to be used as 'with' statement.
    The class returns a connection object.
    """

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
        self.conn = None

    def __enter__(self):
        try:
            if self.conn_dict.get("init_oracle_client", False):
                oracledb.init_oracle_client()

            # Connect with tnsnames.ora entry and Login with Oracle Wallet
            if self.conn_dict.get("external_auth") == "wallet":
                LOGGER.debug(
                    "Oracle connect with tnsnames.ora entry \
                    and login with Oracle Wallet"
                )

                if "tns_name" not in self.conn_dict:
                    raise Exception(
                        "tns_name must be set for external authentication!"
                    )

                dsn = self.conn_dict["tns_name"]

            # Connect with SERVICE_NAME
            if "service_name" in self.conn_dict:
                LOGGER.debug(
                    f"Oracle connect with service_name: \
                        {self.conn_dict['service_name']}"
                )

                if "host" not in self.conn_dict:
                    raise Exception(
                        "Host must be set for connection with service_name!"
                    )

                dsn = oracledb.makedsn(
                    self.conn_dict["host"],
                    self.conn_dict.get("port", 1521),
                    service_name=self.conn_dict["service_name"],
                )

            # Connect with SID
            elif "sid" in self.conn_dict:
                LOGGER.debug(
                    f"Oracle connect with sid: {self.conn_dict['sid']}"
                )

                if "host" not in self.conn_dict:
                    raise Exception(
                        "Host must be set for connection with sid!"
                    )

                dsn = oracledb.makedsn(
                    self.conn_dict["host"],
                    self.conn_dict.get("port", 1521),
                    sid=self.conn_dict["sid"],
                )

            # Connect with tnsnames.ora entry
            elif "tns_name" in self.conn_dict:
                LOGGER.debug(
                    f"Oracle connect with tns_name: \
                        {self.conn_dict['tns_name']}"
                )
                dsn = self.conn_dict["tns_name"]

            else:
                raise ProviderConnectionError(
                    "One of service_name, sid or tns_name must be specified!"
                )

            LOGGER.debug(f"Oracle DSN string: {dsn}")

            # Connect with tnsnames.ora entry and Login with Oracle Wallet
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
            # When dsn is a TNS name, the environment variable TNS_ADMIN must
            # be set (Path to tnsnames.ora file)
            else:
                self.conn = oracledb.connect(
                    user=self.conn_dict["user"],
                    password=self.conn_dict["password"],
                    dsn=dsn,
                )

        except oracledb.DatabaseError as e:
            LOGGER.error(
                f"Couldn't connect to Oracle using:{str(self.conn_dict)}"
            )
            LOGGER.error(e)
            raise ProviderConnectionError(e)

        # Check if table name has schema inside
        table_parts = self.table.split(".")
        if len(table_parts) == 2:
            schema = table_parts[0]
            table = table_parts[1]
        else:
            schema = self.conn_dict["user"]
            table = self.table

        LOGGER.debug("Schema: " + schema)
        LOGGER.debug("Table: " + table)

        self.cur = self.conn.cursor()
        if self.context == "query":
            # Get table column names and types, excluding geometry
            query_cols = "select column_name, data_type \
                            from all_tab_columns \
                           where table_name = UPPER(:table_name) \
                             and owner = UPPER(:owner) \
                             and data_type != 'SDO_GEOMETRY'"

            self.cur.execute(
                query_cols, {"table_name": table, "owner": schema}
            )
            result = self.cur.fetchall()

            # When self.properties is set, then the result would be filtered
            if self.properties:
                result = [
                    res
                    for res in result
                    if res[0].lower()
                    in [item.lower() for item in self.properties]
                ]

            # Concatenate column names with ', '
            self.columns = ", ".join([item[0].lower() for item in result])

            # Populate dictionary for columns with column type
            for k, v in dict(result).items():
                self.fields[k.lower()] = {"type": v}

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # some logic to commit/rollback
        self.conn.close()


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

        self.table = provider_def["table"]
        self.id_field = provider_def["id_field"]
        self.conn_dic = provider_def["data"]
        self.geom = provider_def["geom_field"]
        self.properties = [item.lower() for item in self.properties]

        self.sql_manipulator = provider_def.get("sql_manipulator")
        self.sql_manipulator_options = provider_def.get(
            "sql_manipulator_options"
        )
        self.mandatory_properties = provider_def.get("mandatory_properties")
        self.source_crs = provider_def.get("source_crs", 4326)
        self.target_crs = provider_def.get("target_crs", 4326)
        self.sdo_mask = provider_def.get("sdo_mask", "anyinteraction")

        LOGGER.debug("Setting Oracle properties:")
        LOGGER.debug(f"Name:{self.name}")
        LOGGER.debug(f"ID_field:{self.id_field}")
        LOGGER.debug(f"Table:{self.table}")
        LOGGER.debug(f"source_crs: {self.source_crs}")
        LOGGER.debug(f"target_crs: {self.target_crs}")
        LOGGER.debug(f"sdo_mask: {self.sdo_mask}")

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
        self, properties, bbox, bbox_crs, sdo_mask="anyinteraction"
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

            sdo_mask = f"mask={sdo_mask}"

            bbox_dict["properties"] = {
                "srid": bbox_crs or 4326,
                "minx": bbox[0],
                "miny": bbox[1],
                "maxx": bbox[2],
                "maxy": bbox[3],
                "sdo_mask": sdo_mask,
            }

            bbox_dict[
                "clause"
            ] = f"sdo_relate({self.geom}, \
                             mdsys.sdo_geometry(2003, \
                                                :srid, \
                                                NULL, \
                                                mdsys.sdo_elem_info_array(\
                                                    1, \
                                                    1003, \
                                                    3\
                                                ), \
                             mdsys.sdo_ordinate_array(:minx, \
                                                      :miny, \
                                                      :maxx, \
                                                      :maxy)), \
                             :sdo_mask) = 'TRUE'"

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

    def query(
        self,
        offset=0,
        limit=10,
        resulttype="results",
        bbox=None,
        datetime_=None,
        properties=[],
        sortby=[],
        select_properties=[],
        skip_geometry=False,
        q=None,
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
                    raise ProviderQueryError(
                        f"Missing mandatory filter property: {mand_col}"
                    )
                else:
                    if mand_col not in property_dict:
                        raise ProviderQueryError(
                            f"Missing mandatory filter property: {mand_col}"
                        )

        if resulttype == "hits":
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
                    bbox_crs=self.source_crs,
                    sdo_mask=self.sdo_mask,
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

            return self._response_feature_hits(hits)

        with DatabaseConnection(
            self.conn_dic, self.table, properties=self.properties
        ) as db:
            db.conn.outputtypehandler = self._output_type_handler

            cursor = db.conn.cursor()

            # Create column list.
            #   Uses columns field that was generated in the Connection class
            #   or the configured columns from the Yaml file.
            props = (
                db.columns
                if select_properties == []
                else ", ".join([p for p in select_properties])
            )

            where_dict = self._get_where_clauses(
                properties=properties,
                bbox=bbox,
                bbox_crs=self.source_crs,
                sdo_mask=self.sdo_mask,
            )

            # Build geometry column call
            #   When a different output CRS is definded, the geometry
            #   geometry column would be transformed.
            if skip_geometry:
                geom = ""
            elif (
                not skip_geometry
                and self.target_crs
                and self.target_crs != self.source_crs
            ):
                geom = f", sdo_cs.transform(t1.{self.geom}, \
                                            :target_srid).get_geojson() \
                            AS geometry "
                where_dict["properties"].update(
                    {"target_srid": int(self.target_crs)}
                )
            else:
                geom = f", t1.{self.geom}.get_geojson() AS geometry "

            orderby = self._get_orderby(sortby) if sortby else ""

            # Create paging and add placeholders for the
            # SQL manipulation class
            paging_bind = {}
            if limit > 0:
                sql_query = f"SELECT #HINTS# {props} {geom} \
                              FROM {self.table} t1 #JOIN# \
                              {where_dict['clause']} #WHERE# \
                              {orderby} \
                              OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
                paging_bind = {"offset": offset, "limit": limit}
            else:
                sql_query = f"SELECT #HINTS# {props} {geom} \
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
                    bbox,
                    self.source_crs,
                    properties,
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

    def get(self, identifier, **kwargs):
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
            if self.target_crs and self.target_crs != self.source_crs:
                geom_sql = f", sdo_cs.transform(t1.{self.geom}, \
                                                :target_srid).get_geojson() \
                                AS geometry "
                crs_dict = {"target_srid": int(self.target_crs)}
            else:
                geom_sql = f", t1.{self.geom}.get_geojson() AS geometry "

            sql_query = f"SELECT {db.columns} {geom_sql} \
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
                if col.lower() in [field.lower() for field in self.fields]
            ]

            # Flter function to get only properties who are
            # in the column list
            def filter_binds(pair):
                return pair[0].lower() in [
                    field.lower() for field in self.fields
                ]

            # Filter bind variables
            bind_variables = dict(
                filter(filter_binds, request_data.get("properties").items())
            )

            columns_str = ", ".join([col for col in columns])
            values_str = ", ".join([f":{col}" for col in columns])

            sql_query = f"INSERT INTO {self.table} (\
                            {columns_str}, \
                            {self.geom}) \
                          VALUES ({values_str}, :in_geometry) \
                          RETURNING {self.id_field} INTO :out_id"

            # Out bind variable for the id of the created row
            out_id = cursor.var(int)

            # Bind variable for the SDO_GEOMETRY type
            in_geometry = self._get_sdo_from_geojson_geometry(
                db.conn, request_data.get("geometry").get("coordinates")[0]
            )

            bind_variables = {
                **bind_variables,
                "out_id": out_id,
                "in_geometry": in_geometry,
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
                if col.lower() in [field.lower() for field in self.fields]
            ]

            # Flter function to get only properties who are
            # in the column list
            def filter_binds(pair):
                return pair[0].lower() in [
                    field.lower() for field in self.fields
                ]

            # Filter bind variables
            bind_variables = dict(
                filter(
                    filter_binds,
                    request_data.get("properties").items(),
                )
            )

            set_str = ", ".join([f" {col} = :{col}" for col in columns])

            sql_query = f"UPDATE {self.table} \
                             SET {set_str} \
                               , {self.geom} = :in_geometry \
                           WHERE {self.id_field} = :in_id"

            # Bind variable for the SDO_GEOMETRY type
            in_geometry = self._get_sdo_from_geojson_geometry(
                db.conn, request_data.get("geometry").get("coordinates")[0]
            )

            bind_variables = {
                **bind_variables,
                "in_id": identifier,
                "in_geometry": in_geometry,
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
