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

# TODO - implement SQL string composition like psycopg2.sql.SQL
#           (https://www.psycopg.org/docs/sql.html)
#      - Support for parameters crs and bbox-crs (should overwrite
#           source-crs and target-crs configuration)
#      - Use of the correct CRS parameter as URL?! Translation to SRID

import logging
import json
import oracledb
from pygeoapi.provider.base import (
    BaseProvider,
    ProviderConnectionError,
    ProviderQueryError,
    ProviderItemNotFoundError,
)
import importlib

LOGGER = logging.getLogger(__name__)


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

        self.conn_dic = conn_dic
        self.table = table
        self.context = context
        self.columns = (
            None  # Comma sepparated string with column names (for SQL queries)
        )
        self.properties = [item.lower() for item in properties]
        self.fields = {}  # Dict of columns. Key is col name, value is type
        self.conn = None

    def __enter__(self):
        try:
            if (
                "init_oracle_client" in self.conn_dic
                and self.conn_dic["init_oracle_client"] == True
            ):
                oracledb.init_oracle_client()

            # Connect with tnsnames.ora entry and Login with Oracle Wallet
            if (
                "external_auth" in self.conn_dic
                and self.conn_dic["external_auth"] == "wallet"
            ):
                LOGGER.debug(
                    "Oracle connect with tnsnames.ora entry \
                    and login with Oracle Wallet"
                )

                if "tns_name" not in self.conn_dic:
                    raise Exception("tns_name must be set for external authentication!")

                dsn = self.conn_dic["tns_name"]

            # Connect with SERVICE_NAME
            if "service_name" in self.conn_dic:
                LOGGER.debug(
                    "Oracle connect with service_name: " + self.conn_dic["service_name"]
                )

                if "host" not in self.conn_dic:
                    raise Exception(
                        "Host must be set for connection with service_name!"
                    )

                dsn = oracledb.makedsn(
                    self.conn_dic["host"],
                    self.conn_dic["port"] or 1521,
                    service_name=self.conn_dic["service_name"],
                )

            # Connect with SID
            elif "sid" in self.conn_dic:
                LOGGER.debug("Oracle connect with sid: " + self.conn_dic["sid"])

                if "host" not in self.conn_dic:
                    raise Exception("Host must be set for connection with sid!")

                dsn = oracledb.makedsn(
                    self.conn_dic["host"],
                    self.conn_dic["port"] or 1521,
                    sid=self.conn_dic["sid"],
                )

            # Connect with tnsnames.ora entry
            elif "tns_name" in self.conn_dic:
                LOGGER.debug(
                    "Oracle connect with tns_name: " + self.conn_dic["tns_name"]
                )
                dsn = self.conn_dic["tns_name"]

            else:
                raise ProviderConnectionError(
                    "One of service_name, sid or tns_name must be specified!"
                )

            LOGGER.debug("Oracle DSN string: " + dsn)

            # Connect with tnsnames.ora entry and Login with Oracle Wallet
            if (
                "external_auth" in self.conn_dic
                and self.conn_dic["external_auth"] == "wallet"
            ):
                self.conn = oracledb.connect(externalauth=True, dsn=dsn)

            # Connect with tnsnames.ora entry, TNS_ADMIN is set via configuration
            if "tns_admin" in self.conn_dic:
                self.conn = oracledb.connect(
                    user=self.conn_dic["user"],
                    password=self.conn_dic["password"],
                    dsn=dsn,
                    config_dir=self.conn_dic["tns_admin"],
                )

            # Connect with user / password via dsn string
            # When dsn is a TNS name, the environment variable TNS_ADMIN must be set (Path to tnsnames.ora file)
            else:
                self.conn = oracledb.connect(
                    user=self.conn_dic["user"],
                    password=self.conn_dic["password"],
                    dsn=dsn,
                )

        except oracledb.DatabaseError as e:
            LOGGER.error(
                "Couldn't connect to Oracle using:{}".format(str(self.conn_dic))
            )
            LOGGER.error(e)
            raise ProviderConnectionError(e)

        # Check if table name has schema inside
        dot_pos = self.table.find(".")
        if dot_pos > 0:
            schema = self.table[0:dot_pos]
            table = self.table[dot_pos + 1 :]
        else:
            schema = self.conn_dic["user"]
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

            self.cur.execute(query_cols, {"table_name": table, "owner": schema})
            result = self.cur.fetchall()

            # When self.properties is set, then the result would be filtered
            if self.properties:
                result = [
                    res
                    for res in result
                    if res[0].lower() in [item.lower() for item in self.properties]
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
        self.geom = provider_def.get("geom_field", "geom")
        self.properties = [item.lower() for item in self.properties]

        if "sql_manipulator" in provider_def:
            self.sql_manipulator = provider_def["sql_manipulator"]
        else:
            self.sql_manipulator = None
        if "sql_manipulator_options" in provider_def:
            self.sql_manipulator_options = provider_def["sql_manipulator_options"]
        else:
            self.sql_manipulator = None
        if "mandatory_properties" in provider_def:
            self.mandatory_properties = provider_def["mandatory_properties"]
        else:
            self.mandatory_properties = None
        if "source_crs" in provider_def:
            self.source_crs = provider_def["source_crs"]
        else:
            self.source_crs = 4326
        if "target_crs" in provider_def:
            self.target_crs = provider_def["target_crs"]
        else:
            self.target_crs = 4326
        if "sdo_mask" in provider_def:
            self.sdo_mask = provider_def["sdo_mask"]
        else:
            self.sdo_mask = "anyinteraction"

        LOGGER.debug("Setting Oracle properties:")
        LOGGER.debug("Name:{}".format(self.name))
        LOGGER.debug("ID_field:{}".format(self.id_field))
        LOGGER.debug("Table:{}".format(self.table))
        LOGGER.debug("source_crs: {}".format(self.source_crs))
        LOGGER.debug("target_crs: {}".format(self.target_crs))
        LOGGER.debug("sdo_mask: {}".format(self.sdo_mask))

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

    def __get_where_clauses(
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
            property_clauses = [
                "{} = :{}".format(key, key) for key, value in properties
            ]
            where_conditions += property_clauses
            where_dict["properties"] = dict(properties)

        if bbox:
            bbox_dict = {"clause": "", "properties": {}}

            sdo_mask = "mask={}".format(sdo_mask)

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
            ] = "sdo_relate({}, \
                                              mdsys.sdo_geometry(2003, \
                                                                 :srid, \
                                                                 NULL, \
                                                                 mdsys.sdo_elem_info_array(1, 1003, 3), \
                                              mdsys.sdo_ordinate_array(:minx, :miny, :maxx, :maxy)), \
                                              :sdo_mask) = 'TRUE'".format(
                self.geom
            )

            where_conditions.append(bbox_dict["clause"])
            where_dict["properties"].update(bbox_dict["properties"])

        if where_conditions:
            where_dict["clause"] = " WHERE {}".format(" AND ".join(where_conditions))

        LOGGER.debug(where_dict)

        return where_dict

    def __get_orderby(self, sortby):
        """
        Private function: Get ORDER BY clause

        :param sortby: list of dicts (property, order)

        :returns: STA $orderby string
        """
        ret = []
        _map = {"+": "ASC", "-": "DESC"}
        for _ in sortby:
            ret.append(f"{_['property']} {_map[_['order']]}")
        return f"ORDER BY {','.join(ret)}"

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
        e,g: http://localhost:5000/collections/orcl_lakes/items?limit=1&resulttype=results

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

        LOGGER.debug("!!!!!!!!!!!!!!!!!! Query start !!!!!!!!!!!!!!!!!!!!")

        # Check mandatory filter properties
        property_dict = dict(properties)
        if self.mandatory_properties:
            for mand_col in self.mandatory_properties:
                if mand_col == "bbox" and not bbox:
                    raise ProviderQueryError(
                        "Missing mandatory filter property: " + mand_col
                    )
                else:
                    if mand_col not in property_dict:
                        raise ProviderQueryError(
                            "Missing mandatory filter property: " + mand_col
                        )

        if resulttype == "hits":
            with DatabaseConnection(
                self.conn_dic, self.table, properties=self.properties, context="hits"
            ) as db:
                cursor = db.conn.cursor()

                where_dict = self.__get_where_clauses(
                    properties=properties,
                    bbox=bbox,
                    bbox_crs=self.source_crs,
                    sdo_mask=self.sdo_mask,
                )

                # Not dangerous to use self.table as substitution, because of getFields ...
                sql_query = "SELECT COUNT(1) AS hits FROM {} {}".format(
                    self.table, where_dict["clause"]
                )
                try:
                    cursor.execute(sql_query, where_dict["properties"])
                except Exception as err:
                    LOGGER.error(
                        "Error executing sql_query: {}: {}".format(sql_query, err)
                    )
                    raise ProviderQueryError()

                hits = cursor.fetchone()[0]
                LOGGER.debug("hits: " + str(hits))

            return self.__response_feature_hits(hits)

        with DatabaseConnection(
            self.conn_dic, self.table, properties=self.properties
        ) as db:
            # Output type handler for Oracle LOB datatypes
            def output_type_handler(cursor, name, default_type, size, precision, scale):
                if default_type == oracledb.DB_TYPE_CLOB:
                    return cursor.var(oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize)
                if default_type == oracledb.DB_TYPE_BLOB:
                    return cursor.var(
                        oracledb.DB_TYPE_LONG_RAW, arraysize=cursor.arraysize
                    )

            db.conn.outputtypehandler = output_type_handler

            cursor = db.conn.cursor()

            # Create column list.
            #   Uses columns field that was generated in the Connection class
            #   or the configured columns from the Yaml file.
            props = (
                db.columns
                if select_properties == []
                else ", ".join([p for p in select_properties])
            )

            where_dict = self.__get_where_clauses(
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
                geom = ", sdo_cs.transform(t1.{}, :target_srid).get_geojson() AS geometry ".format(
                    self.geom
                )
                where_dict["properties"].update({"target_srid": int(self.target_crs)})
            else:
                geom = ", t1.{}.get_geojson() AS geometry ".format(self.geom)

            orderby = self.__get_orderby(sortby) if sortby else ""

            # Create paging and add placeholders for the
            # SQL manipulation class
            paging_bind = {}
            if limit > 0:
                sql_query = "SELECT #HINTS# {} {} FROM {} t1 #JOIN# {} #WHERE# {} OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY".format(
                    props, geom, self.table, where_dict["clause"], orderby
                )
                paging_bind = {"offset": offset, "limit": limit}
            else:
                sql_query = (
                    "SELECT #HINTS# {} {} FROM {} t1 #JOIN# {} #WHERE# {}".format(
                        props, geom, self.table, where_dict["clause"], orderby
                    )
                )

            # Create dictionary for sql bind variables
            bind_variables = where_dict["properties"] | paging_bind

            # SQL manipulation plugin
            if self.sql_manipulator:
                LOGGER.debug("sql_manipulator: " + self.sql_manipulator)
                manipulation_class = factory(self.sql_manipulator)
                sql_query, bind_variables = manipulation_class.process(
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

            LOGGER.debug("SQL Query: {}".format(sql_query))
            LOGGER.debug("Bind variables: {}".format(bind_variables))

            try:
                cursor.execute(sql_query, bind_variables)
            except Exception as err:
                LOGGER.error("Error executing sql_query: {}".format(sql_query))
                LOGGER.error(err)
                raise ProviderQueryError()

            # Convert row resultset to dictionary
            columns = [col[0] for col in cursor.description]
            cursor.rowfactory = lambda *args: dict(zip(columns, args))

            row_data = cursor.fetchall()

            # Generate feature JSON
            feature_collection = {"type": "FeatureCollection", "features": []}
            for rd in row_data:
                feature = self.__response_feature(rd)

                feature_collection["features"].append(feature)

            return feature_collection

    def get_previous(self, cursor, identifier):
        """
        Query previous ID given current ID

        :param identifier: feature id

        :returns: feature id
        """
        sql = "SELECT {} AS id FROM {} WHERE ROWNUM = 1 AND {} < :{} ORDER BY {} DESC".format(
            self.id_field,
            self.table,
            self.id_field,
            self.id_field,
            self.id_field,
        )

        bind_variables = {self.id_field: identifier}

        LOGGER.debug("SQL Query: {}".format(sql))
        LOGGER.debug("Bind variables: {}".format(str(bind_variables)))

        cursor.execute(sql, bind_variables)

        item = cursor.fetchall()
        id_ = item[0][0] if item else None
        return id_

    def get_next(self, cursor, identifier):
        """
        Query next ID given current ID

        :param identifier: feature id

        :returns: feature id
        """
        sql = "SELECT {} AS id FROM {} WHERE ROWNUM = 1 AND {}>:{} ORDER BY {}".format(
            self.id_field,
            self.table,
            self.id_field,
            self.id_field,
            self.id_field,
        )
        LOGGER.debug("SQL Query: {}".format(sql))
        cursor.execute(sql, {self.id_field: identifier})
        item = cursor.fetchall()
        id_ = item[0][0] if item else None
        return id_

    def get(self, identifier, **kwargs):
        """
        Query the provider for a specific
        feature id e.g: /collections/ocrl_lakes/items/1

        :param identifier: feature id

        :returns: GeoJSON FeaturesCollection
        """

        LOGGER.debug("Get item from Oracle")
        with DatabaseConnection(
            self.conn_dic, self.table, properties=self.properties
        ) as db:
            # Output type handler for Oracle LOB datatypes
            def output_type_handler(cursor, name, default_type, size, precision, scale):
                if default_type == oracledb.DB_TYPE_CLOB:
                    return cursor.var(oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize)
                if default_type == oracledb.DB_TYPE_BLOB:
                    return cursor.var(
                        oracledb.DB_TYPE_LONG_RAW, arraysize=cursor.arraysize
                    )

            db.conn.outputtypehandler = output_type_handler

            cursor = db.conn.cursor()

            crs_dict = {}
            if self.target_crs and self.target_crs != self.source_crs:
                geom_sql = ", sdo_cs.transform(t1.{}, :target_srid).get_geojson() AS geometry ".format(
                    self.geom
                )
                crs_dict = {"target_srid": int(self.target_crs)}
            else:
                geom_sql = ", t1.{}.get_geojson() AS geometry ".format(self.geom)

            sql_query = "SELECT {} {} \
                           FROM {} t1 \
                          WHERE {} = :{}".format(
                db.columns, geom_sql, self.table, self.id_field, self.id_field
            )

            LOGGER.debug("SQL Query: {}".format(sql_query))
            LOGGER.debug("Identifier: {}".format(identifier))

            try:
                cursor.execute(sql_query, {self.id_field: identifier} | crs_dict)
            except Exception as err:
                LOGGER.error("Error executing sql_query: {}".format(sql_query))
                LOGGER.error(err)
                raise ProviderQueryError()

            # Convert row resultset to dictionary
            columns = [col[0] for col in cursor.description]
            cursor.rowfactory = lambda *args: dict(zip(columns, args))

            results = cursor.fetchall()

            row_data = None
            if results:
                row_data = results[0]
            feature = self.__response_feature(row_data)

            if feature:
                previous_id = self.get_previous(cursor, identifier)
                if previous_id:
                    feature["prev"] = previous_id
                next_id = self.get_next(cursor, identifier)
                if next_id:
                    feature["next"] = self.get_next(cursor, identifier)
                return feature
            else:
                err = "item {} not found".format(identifier)
                LOGGER.error(err)
                raise ProviderItemNotFoundError(err)

    def __response_feature(self, row_data):
        """
        Assembles GeoJSON output from DB query

        :param row_data: DB row result

        :returns: `dict` of GeoJSON Feature
        """

        if row_data:
            feature = {"type": "Feature"}

            if row_data["GEOMETRY"]:
                feature["geometry"] = json.loads(row_data["GEOMETRY"])
            feature["properties"] = {
                key.lower(): value
                for (key, value) in row_data.items()
                if key != "GEOMETRY"
            }
            feature["id"] = feature["properties"].pop(self.id_field)

            return feature
        else:
            return None

    def __response_feature_hits(self, hits):
        """Assembles GeoJSON/Feature number
        e.g: http://localhost:5000/collections/lakes/items?resulttype=hits

        :returns: GeoJSON FeaturesCollection
        """

        feature_collection = {"features": [], "type": "FeatureCollection"}
        feature_collection["numberMatched"] = hits

        return feature_collection


def factory(module_class_string, super_cls: type = None, **kwargs):
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
    LOGGER.debug("reading class {} from module {}".format(class_name, module_name))
    cls = getattr(module, class_name)
    if super_cls is not None:
        assert issubclass(cls, super_cls), "class {} should inherit from {}".format(
            class_name, super_cls.__name__
        )
    LOGGER.debug("initialising {} with params {}".format(class_name, kwargs))
    obj = cls(**kwargs)
    return obj