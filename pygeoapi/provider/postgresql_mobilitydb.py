import json
import datetime
import psycopg2
from functools import partial
from dateutil.parser import parse as dateparse
import pytz
from pymeos import (Temporal, TFloatSeq, TFloatSeqSet, pymeos_initialize)
from pygeoapi.util import format_datetime
from pymeos_cffi import (tfloat_from_mfjson, ttext_from_mfjson,
                         tgeompoint_from_mfjson)
# from mobilitydb.psycopg import register


class PostgresMobilityDB:
    # host = '127.0.0.1'
    # port = 5432
    # db = 'mobilitydb'
    # user = 'docker'
    # password = 'docker'
    # connection = None

    host = '172.20.241.18'
    port = 5432
    db = 'mobility'
    user = 'postgres'
    password = 'postgres'
    connection = None

    def __init__(self, datasource=None):
        """
        PostgresMobilityDB Class constructor

        :param datasource: datasource definition (default None)
            host - database host address
            port - connection port number
            db - table name
            user - user name used to authenticate
            password - password used to authenticate
        """

        self.connection = None
        if datasource is not None:
            self.host = datasource['host']
            self.port = int(datasource['port'])
            self.db = datasource['dbname']
            self.user = datasource['user']
            self.password = datasource['password']

    def connect(self):
        """
        Connection of database
        """

        # Set the connection parameters to PostgreSQL
        self.connection = psycopg2.connect(host=self.host,
                                           database=self.db,
                                           user=self.user,
                                           password=self.password,
                                           port=self.port)
        self.connection.autocommit = True
        # Register MobilityDB data types (old library 'python-mobilitydb')
        # register(self.connection)

    def disconnect(self):
        """
        Close the connection
        """

        if self.connection:
            self.connection.close()

    def get_collections_list(self):
        """
        Query moving features collection list
        GET /collections

        :returns: JSON FeatureCollection
        """
        with self.connection.cursor() as cur:
            select_query = "SELECT collection_id FROM collection"
            cur.execute(select_query)
            result = cur.fetchall()
        return result

    def get_collections(self):
        """
        Query moving features collections

        :returns: JSON FeatureCollections
        """
        with self.connection.cursor() as cur:
            select_query = """select collection.collection_id,
            collection.collection_property, extentLifespan,
            extentTGeometry from (select collection.collection_id,
            collection.collection_property,
            extent(mfeature.lifespan) as extentLifespan,
            extent(tgeometry.tgeometry_property) as extentTGeometry
            from collection
            left outer join mfeature
            on collection.collection_id = mfeature.collection_id
            left outer join tgeometry
            on mfeature.collection_id = tgeometry.collection_id
            and mfeature.mfeature_id = tgeometry.mfeature_id
            group by collection.collection_id, collection.collection_property)
            collection """

            cur.execute(select_query)
            result = cur.fetchall()
        return result

    def get_collection(self, collection_id):
        """
        Query specific moving features collection
        GET /collections/{collectionId}

        :param collection_id: local identifier of a collection

        :returns: JSON FeatureCollection
        """
        with self.connection.cursor() as cur:
            select_query = ("""select collection.collection_id,
                collection.collection_property, extentLifespan,
                extentTGeometry from (select collection.collection_id,
                collection.collection_property,
                extent(mfeature.lifespan) as extentLifespan,
                extent(tgeometry.tgeometry_property) as extentTGeometry
                from collection
                left outer join mfeature
                on collection.collection_id = mfeature.collection_id
                left outer join tgeometry
                on mfeature.collection_id = tgeometry.collection_id
                and mfeature.mfeature_id = tgeometry.mfeature_id
                where collection.collection_id ='{0}'
                group by collection.collection_id,
                collection.collection_property)
                collection """
                            .format(collection_id))

            cur.execute(select_query)
            result = cur.fetchall()
        return result

    def get_features_list(self):
        """
        Query all moving features

        :returns: JSON MovingFeatures
        """

        with self.connection.cursor() as cur:
            select_query = "SELECT collection_id, mfeature_id FROM mfeature"
            cur.execute(select_query)
            result = cur.fetchall()
        return result

    def get_features(
            self, collection_id, bbox='', datetime='', limit=10, offset=0,
            sub_trajectory=False):
        """
        Retrieve the moving feature collection to access
        the static information of the moving feature
        /collections/{collectionId}/items

        :param collection_id: local identifier of a collection
        :param bbox: bounding box [lowleft1,lowleft2,min(optional),
                                   upright1,upright2,max(optional)]
        :param datetime: either a date-time or an interval(datestamp or extent)
        :param limit: number of items (default 10) [optional]
        :param offset: starting record to return (default 0)
        :param sub_trajectory: If specified true, This operation returns only a
                              subsequence of temporal geometry within a time
                              interval contained in the
                              datetime parameter (default False)[optional]

        :returns: JSON MovingFeatures
        """

        with self.connection.cursor() as cur:
            bbox_restriction = ""
            if bbox != '' and bbox is not None:
                s_bbox = ','.join(str(x) for x in bbox)
                if len(bbox) == 4:
                    bbox_restriction = " and box2d(stboxx(" + \
                        s_bbox + ")) &&& box2d(extentTGeometry) "
                elif len(bbox) == 6:
                    bbox_restriction = " and box3d(stboxz(" + \
                        s_bbox + ")) &&& box3d(extentTGeometry) "

            datetime_restriction = ""
            if datetime != '' and datetime is not None:
                if sub_trajectory is False or sub_trajectory == "false":
                    datetime_restriction = (
                        """ and((lifespan && tstzspan('[{0}]'))
                        or (extentTPropertiesValueFloat::tstzspan &&
                        tstzspan('[{0}]')) or
                        (extentTPropertiesValueText::tstzspan &&
                        tstzspan('[{0}]')) or
                        (extentTGeometry::tstzspan && tstzspan('[{0}]')))"""
                        .format(datetime))
            limit_restriction = " LIMIT " + \
                str(limit) + " OFFSET " + str(offset)

            # sub_trajectory is false
            select_query = (
                """select mfeature.collection_id, mfeature.mfeature_id,
                st_asgeojson(mfeature.mf_geometry) as mf_geometry,
                mfeature.mf_property, mfeature.lifespan, extentTGeometry,
                extentTPropertiesValueFloat, extentTPropertiesValueText
                from (select mfeature.collection_id, mfeature.mfeature_id,
                mfeature.mf_geometry, mfeature.mf_property, mfeature.lifespan,
                extent(tgeometry.tgeometry_property) as extentTGeometry
                from mfeature left outer join tgeometry
                on mfeature.collection_id = tgeometry.collection_id
                and mfeature.mfeature_id = tgeometry.mfeature_id
                where mfeature.collection_id ='{0}'
                group by mfeature.collection_id, mfeature.mfeature_id,
                mfeature.mf_geometry, mfeature.mf_property, mfeature.lifespan)
                mfeature left outer join
                (select mfeature.collection_id, mfeature.mfeature_id,
                extent(tvalue.pvalue_float)
                as extentTPropertiesValueFloat,
                extent(tvalue.pvalue_text) as extentTPropertiesValueText
                from mfeature left outer join tvalue
                on mfeature.collection_id = tvalue.collection_id
                and mfeature.mfeature_id = tvalue.mfeature_id
                where mfeature.collection_id ='{0}'
                group by mfeature.collection_id, mfeature.mfeature_id)
                tvalue ON
                mfeature.collection_id = tvalue.collection_id
                and mfeature.mfeature_id = tvalue.mfeature_id
                where 1=1 {1} {2}""" .format(
                    collection_id, bbox_restriction, datetime_restriction))

            cur.execute(select_query)
            result = cur.fetchall()
            number_matched = len(result)

            select_query += limit_restriction
            cur.execute(select_query)
            result = cur.fetchall()
            number_returned = len(result)

            if sub_trajectory or sub_trajectory == "true":
                sub_trajectory_field = ("""atTime(tgeometry.tgeometry_property,
                                    tstzspan('[{0}]'))"""
                                        .format(datetime))
                # sub_trajectory is true
                select_geometry_query = (
                    """select mfeature.collection_id,
                mfeature.mfeature_id, mfeature.mf_geometry,
                mfeature.mf_property, mfeature.lifespan,
                extentTGeometry, tgeometry.tgeometry_id,
                tgeometry_property from (select mfeature.collection_id,
                mfeature.mfeature_id, st_asgeojson(mfeature.mf_geometry)
                as mf_geometry, mfeature.mf_property, mfeature.lifespan,
                extentTGeometry from (select mfeature.collection_id,
                mfeature.mfeature_id, mfeature.mf_geometry,
                mfeature.mf_property, mfeature.lifespan,
                extent(tgeometry.tgeometry_property)
                as extentTGeometry from mfeature left outer join tgeometry
                on mfeature.collection_id = tgeometry.collection_id
                and mfeature.mfeature_id = tgeometry.mfeature_id
                where mfeature.collection_id ='{0}'
                group by mfeature.collection_id, mfeature.mfeature_id,
                mfeature.mf_geometry, mfeature.mf_property, mfeature.lifespan)
                mfeature where 1=1 {1} {2}) mfeature
                left outer join (select tgeometry.collection_id,
                tgeometry.mfeature_id, tgeometry.tgeometry_id, {3}
                as tgeometry_property from tgeometry
                where tgeometry.collection_id ='{0}' and {3} is not null)
                tgeometry ON mfeature.collection_id = tgeometry.collection_id
                and mfeature.mfeature_id = tgeometry.mfeature_id where 1=1 """.
                    format(
                        collection_id, bbox_restriction,
                        limit_restriction,
                        sub_trajectory_field))

                cur.execute(select_geometry_query)
                result = cur.fetchall()

        return result, number_matched, number_returned

    def get_feature(self, collection_id, mfeature_id):
        """
        Access the static data of the moving feature

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature

        :returns: JSON MovingFeature
        """
        with self.connection.cursor() as cur:
            cur = self.connection.cursor()
            select_query = (
                """select mfeature.collection_id, mfeature.mfeature_id,
                st_asgeojson(mfeature.mf_geometry) as mf_geometry,
                mfeature.mf_property, mfeature.lifespan, extentTGeometry
                from (select mfeature.collection_id, mfeature.mfeature_id,
                mfeature.mf_geometry, mfeature.mf_property, mfeature.lifespan,
                extent(tgeometry.tgeometry_property) as extentTGeometry
                from mfeature left outer join tgeometry
                on mfeature.collection_id = tgeometry.collection_id
                and mfeature.mfeature_id = tgeometry.mfeature_id
                where mfeature.collection_id ='{0}'
                AND mfeature.mfeature_id='{1}'
                group by mfeature.collection_id, mfeature.mfeature_id,
                mfeature.mf_geometry, mfeature.mf_property,
                mfeature.lifespan) mfeature """ .format(
                    collection_id, mfeature_id))
            cur.execute(select_query)
            result = cur.fetchall()
        return result

    def get_temporalgeometries(
            self, collection_id, mfeature_id, bbox='', leaf='', datetime='',
            limit=10, offset=0, sub_trajectory=False):
        """
        Retrieve only the movement data of a moving feature

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature
        :param bbox: bounding box [lowleft1,lowleft2,min(optional),
                                   upright1,upright2,max(optional)]
        :param leaf: only features that have a temporal geometry and
                     property that intersects the given
                     date-time are selected [optional]
        :param datetime: either a date-time or an interval(datestamp or extent)
        :param limit: number of items (default 10) [optional]
        :param offset: starting record to return (default 0)
        :param sub_trajectory: If specified true, This operation returns only a
                              subsequence of temporal geometry within a time
                              interval contained in the
                              datetime parameter (default False) [optional]

        :returns: JSON TemporalGeometry
        """
        with self.connection.cursor() as cur:
            tgeometry_property = 'null'

            bbox_restriction = ""
            if bbox != '' and bbox is not None:
                s_bbox = ','.join(str(x) for x in bbox)
                if len(bbox) == 4:
                    bbox_restriction = " and box2d(stboxx(" + s_bbox + \
                        ")) &&& box2d(stbox(tgeometry_property))"
                elif len(bbox) == 6:
                    bbox_restriction = " and box3d(stboxz(" + s_bbox + \
                        ")) &&& box3d(stbox(tgeometry_property))"

            datetime_restriction = ""
            if datetime != '' and datetime is not None:
                datetime_restriction = (""" and atTime(tgeometry_property,
                    tstzspan('[{0}]')) is not null """
                                        .format(datetime))

            if leaf != '' and leaf is not None:
                tgeometry_property = ("""atTime(tgeometry_property,
                    tstzset('{0}'))""".format('{' + leaf + '}'))
            elif sub_trajectory or sub_trajectory == "true":
                tgeometry_property = ("""atTime(tgeometry_property,
                    tstzspan('[{0}]'))""".format(datetime))

            select_query = (
                """SELECT collection_id, mfeature_id, tgeometry_id,
                    tgeometry_property, {0}
                    FROM tgeometry WHERE collection_id ='{1}'
                    AND mfeature_id='{2}' {3} {4}"""
                .format(tgeometry_property, collection_id,
                        mfeature_id, bbox_restriction,
                        datetime_restriction))

            cur.execute(select_query)
            result = cur.fetchall()
            number_matched = len(result)

            select_query += " LIMIT " + str(limit) + " OFFSET " + str(offset)
            cur.execute(select_query)
            result = cur.fetchall()
            number_returned = len(result)

        return result, number_matched, number_returned

    def get_tProperties_name_list(self):
        """
        Query all tProperties name list

        :returns: MF-JSON tProperties
        """
        with self.connection.cursor() as cur:
            select_query = """SELECT collection_id, mfeature_id,
                    tproperties_name FROM tproperties"""
            cur.execute(select_query)
            result = cur.fetchall()
        return result

    def get_temporalproperties(
            self, collection_id, mfeature_id, datetime='', limit=10,
            offset=0, sub_temporal_value=False):
        """
        Retrieve the static information of the temporal property data
        that included a single moving feature

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature
        :param datetime: either a date-time or an interval(datestamp or extent)
        :param limit: number of items (default 10) [optional]
        :param offset: starting record to return (default 0)
        :param sub_temporal_value: only features with a temporal property
                                 intersecting the given time interval
                                 will return (default False) [optional]

        :returns: MF-JSON TemporalProperties or temporalProperty
        """
        with self.connection.cursor() as cur:
            datetime_restriction = ''
            if datetime != '' and datetime is not None:
                if sub_temporal_value is False \
                        or sub_temporal_value == "false":
                    datetime_restriction = (""" and (atTime(pvalue_float,
                    tstzspan('[{0}]')) is not null
                    or atTime(pvalue_text, tstzspan('[{0}]')) is not null)"""
                                            .format(datetime))

            limit_restriction = " LIMIT " + \
                str(limit) + " OFFSET " + str(offset)
            select_query = ("""select distinct on (tproperties.collection_id,
            tproperties.mfeature_id, tproperties.tproperties_name)
            tproperties.collection_id, tproperties.mfeature_id,
            tproperties.tproperties_name, tproperties.tproperty
            from tproperties left outer join tvalue
            on tproperties.collection_id = tvalue.collection_id
            and tproperties.mfeature_id = tvalue.mfeature_id
            and tproperties.tproperties_name = tvalue.tproperties_name
            WHERE tproperties.collection_id ='{0}'
            AND tproperties.mfeature_id='{1}' {2}""". format(
                collection_id, mfeature_id, datetime_restriction))

            cur.execute(select_query)
            result = cur.fetchall()
            number_matched = len(result)

            select_query += limit_restriction
            cur.execute(select_query)
            result = cur.fetchall()
            number_returned = len(result)

            if sub_temporal_value or sub_temporal_value == "true":
                subTemporalValue_float_field = (
                    """atTime(tvalue.pvalue_float,
                    tstzspan('[{0}]'))""" .format(datetime))
                subTemporalValue_text_field = (
                    """atTime(tvalue.pvalue_text,
                    tstzspan('[{0}]'))""" .format(datetime))

                select_temporalvalue_query = (
                    """select tproperties.collection_id,
        tproperties.mfeature_id, tproperties.tproperties_name,
        tproperties.tproperty, datetime_group, pvalue_float, pvalue_text
        from (select distinct on (tproperties.collection_id,
        tproperties.mfeature_id, tproperties.tproperties_name)
        tproperties.collection_id, tproperties.mfeature_id,
        tproperties.tproperties_name, tproperties.tproperty
        from tproperties left outer join tvalue
        on tproperties.collection_id = tvalue.collection_id
        and tproperties.mfeature_id = tvalue.mfeature_id
        and tproperties.tproperties_name = tvalue.tproperties_name
        where tproperties.collection_id ='{0}'
        AND tproperties.mfeature_id='{1}' {2} {3}) tproperties
        left outer join (select tvalue.collection_id,
        tvalue.mfeature_id, tvalue.tproperties_name,
        tvalue.datetime_group, {4} as pvalue_float,
        {5} as pvalue_text from tvalue
        where tvalue.collection_id ='{0}'
        AND tvalue.mfeature_id='{1}' and ({4} is not null
        or {5} is not null)) tvalue
        on tproperties.collection_id = tvalue.collection_id
        and tproperties.mfeature_id = tvalue.mfeature_id
        and tproperties.tproperties_name = tvalue.tproperties_name
        where 1=1 order by datetime_group""".
                    format(
                        collection_id, mfeature_id,
                        datetime_restriction,
                        limit_restriction,
                        subTemporalValue_float_field,
                        subTemporalValue_text_field))

                cur.execute(select_temporalvalue_query)
                result = cur.fetchall()

        return result, number_matched, number_returned

    def get_temporalproperties_value(
            self, collection_id, mfeature_id, tProperty_name, datetime='',
            leaf='', sub_temporal_value=False):
        """
        Retrieve temporal values with a specified name
        {tPropertyName} of temporal property.

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature
        :param tProperty_name: local identifier of a temporal property
        :param datetime: either a date-time or an interval(datestamp or extent)
        :param leaf: only features that have a temporal geometry and
                     property that intersects the given
                     date-time are selected [optional]

        :param sub_temporal_value: only features with a temporal property
                                 intersecting the given time interval
                                 will return (default False) [optional]

        :returns: JSON TemporalPropertyValue
        """
        with self.connection.cursor() as cur:
            datetime_restriction = ""
            if datetime != '' and datetime is not None:
                datetime_restriction = (
                    """ and (atTime(tvalue.pvalue_float,
                tstzspan('[{0}]')) is not null
                or atTime(tvalue.pvalue_text,
                tstzspan('[{0}]')) is not null) """ .format(datetime))
            float_field = 'pvalue_float'
            text_field = 'pvalue_text'
            if leaf != '' and leaf is not None:
                float_field = "atTime(tvalue.pvalue_float, \
                    tstzset('{" + leaf + "}'))"
                text_field = "atTime(tvalue.pvalue_text, \
                    tstzset('{" + leaf + "}'))"
            elif sub_temporal_value or sub_temporal_value == "true":
                float_field = "atTime(tvalue.pvalue_float, \
                    tstzspan('[" + datetime + "]'))"
                text_field = "atTime(tvalue.pvalue_text, \
                    tstzspan('[" + datetime + "]'))"

            select_query = (
                """select tproperties.collection_id, tproperties.mfeature_id,
        tproperties.tproperties_name, tproperties.tproperty,
        datetime_group, pvalue_float, pvalue_text
        from (select tproperties.collection_id, tproperties.mfeature_id,
        tproperties.tproperties_name, tproperties.tproperty
        from tproperties where tproperties.collection_id ='{0}'
        AND tproperties.mfeature_id='{1}'
        AND tproperties.tproperties_name='{2}') tproperties
        left outer join (select tproperties.collection_id,
        tproperties.mfeature_id, tproperties.tproperties_name,
        tvalue.datetime_group, {3} as pvalue_float, {4} as pvalue_text
        from tproperties left outer join tvalue
        on tproperties.collection_id = tvalue.collection_id
        and tproperties.mfeature_id = tvalue.mfeature_id
        and tproperties.tproperties_name = tvalue.tproperties_name
        where tproperties.collection_id ='{0}'
        AND tproperties.mfeature_id='{1}'
        AND tproperties.tproperties_name='{2}' {5}) tvalue
        on tproperties.collection_id = tvalue.collection_id
        and tproperties.mfeature_id = tvalue.mfeature_id
        and tproperties.tproperties_name = tvalue.tproperties_name
        where 1=1 order by datetime_group"""
                .format(collection_id, mfeature_id, tProperty_name,
                        float_field, text_field, datetime_restriction))
            cur.execute(select_query)
            result = cur.fetchall()
        return result

    def post_collection(self, collection_property):
        """
        Register metadata about a collection of moving features

        :param collection_property: metadata about a collection
            title - human readable title of the collection
            updateFrequency - a time interval of sampling location
            description - any description
            itemType - indicator about the type of the items in the
                       moving features collection (default "movingfeature")

        :returns: Collection ID
        """
        with self.connection.cursor() as cur:
            cur.execute(
                "INSERT INTO collection(collection_property) \
                VALUES ('{0}') RETURNING collection_id".
                format(json.dumps(collection_property)))

            collection_id = cur.fetchone()[0]
        return collection_id

    def post_movingfeature(self, collection_id, movingfeature):
        """
        Insert a set of moving features or a moving feature into a collection

        :param collection_id: local identifier of a collection
        :param movingfeature: MovingFeature object or
                              MovingFeatureCollection object

        :returns: MovingFeature ID
        """
        with self.connection.cursor() as cur:
            g_movingfeature = dict(movingfeature)
            lifespan = g_movingfeature.pop("time", None)
            if lifespan is not None:
                lifespan = "'[" + self.validate_lifespan(lifespan) + "]'"
            else:
                lifespan = "NULL"
            temporal_geometries = g_movingfeature.pop("temporalGeometry", None)
            temporal_properties = g_movingfeature.pop(
                "temporalProperties", None)

            if 'geometry' in g_movingfeature:
                geometry = g_movingfeature.pop("geometry", None)
                cur.execute(
                    """INSERT INTO mfeature(collection_id, mf_geometry,
                    mf_property, lifespan) VALUES ('{0}',
                    ST_GeomFromGeoJSON('{1}'), '{2}', {3})
                    RETURNING mfeature_id"""
                    .format(collection_id, json.dumps(geometry),
                            json.dumps(g_movingfeature), lifespan))
            else:
                cur.execute(
                    """INSERT INTO mfeature(collection_id,
                    mf_property, lifespan)
                    VALUES ('{0}', '{1}', {2}) RETURNING mfeature_id"""
                    .format(
                        collection_id, json.dumps(g_movingfeature), lifespan))
            mfeature_id = cur.fetchone()[0]

            if temporal_geometries is not None:
                temporal_geometries = [temporal_geometries] if not isinstance(
                    temporal_geometries, list) else temporal_geometries
                for temporal_geometry in temporal_geometries:
                    self.post_temporalgeometry(
                        collection_id, mfeature_id, temporal_geometry)

            if temporal_properties is not None:
                temporal_properties = [temporal_properties] if not isinstance(
                    temporal_properties, list) else temporal_properties
                for temporal_property in temporal_properties:
                    self.post_temporalproperties(
                        collection_id, mfeature_id, temporal_property)

        return mfeature_id

    def post_temporalgeometry(
            self, collection_id, mfeature_id, temporal_geometry):
        """
        Add movement data into the moving feature

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature
        :param temporal_geometry: TemporalPrimitiveGeometry object
                                 in the OGC MF-JSON
        :returns: TemporalGeometry ID
        """

        with self.connection.cursor() as cur:
            # pymeos of python
            pymeos_initialize()
            temporal_geometry = self.convert_temporalgeometry_to_new_version(
                temporal_geometry)
            value = Temporal._factory(
                tgeompoint_from_mfjson(json.dumps(temporal_geometry)))
            cur.execute(
                """INSERT INTO tgeometry(collection_id, mfeature_id,
                tgeometry_property, tgeog_property)
                VALUES ('{0}', '{1}', '{2}', '{3}') RETURNING tgeometry_id"""
                .format(collection_id, mfeature_id, str(value), str(value)))

            tgeometry_id = cur.fetchone()[0]

        return tgeometry_id

    def post_temporalproperties(
            self, collection_id, mfeature_id, temporal_property):
        """
        Add temporal property data into a moving feature

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature
        :param temporalProperty: TemporalProperties object in the OGC MF-JSON

        :returns: TemporalProperty Name
        """
        g_temporal_property = dict(temporal_property)
        datetimes = []
        if 'datetimes' in g_temporal_property:
            datetimes = g_temporal_property.pop("datetimes", None)

        tproperties_name_list = []
        for tproperties_name in g_temporal_property:
            with self.connection.cursor() as cur:
                temporal_value_data = {}
                if 'values' in g_temporal_property[tproperties_name] \
                    and 'interpolation' in g_temporal_property[
                        tproperties_name]:
                    values = g_temporal_property[tproperties_name].pop(
                        "values", None)
                    interpolation = g_temporal_property[tproperties_name].pop(
                        "interpolation", None)

                    temporal_value_data['datetimes'] = datetimes
                    temporal_value_data['values'] = values
                    temporal_value_data['interpolation'] = interpolation

                insert_query = (
                    """INSERT INTO tproperties(collection_id, mfeature_id,
                        tproperties_name, tproperty)
                        VALUES ('{0}', '{1}', '{2}', '{3}')
                        ON CONFLICT (collection_id, mfeature_id,
                        tproperties_name)
                        DO UPDATE SET tproperty = EXCLUDED.tproperty"""
                    .format(collection_id, mfeature_id,
                            tproperties_name, json.dumps(
                                g_temporal_property[tproperties_name])))
                cur.execute(insert_query)

                if temporal_value_data:
                    self.post_temporalvalue(
                        collection_id, mfeature_id, tproperties_name,
                        temporal_value_data)

            tproperties_name_list.append(tproperties_name)

        # TODO replace g_temporal_property
        return tproperties_name_list

    def post_temporalvalue(
            self, collection_id, mfeature_id, tproperties_name,
            temporal_value_data):
        """
        Add more temporal values data into a temporal property

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature
        :param tproperties_name: local identifier of a temporal property
        :param temporal_value_data: temporal primitive value
            datetimes - array of strings <date-time>
            values - number or string or boolean
            interpolation - Enum: "Discrete" "Step" "Linear" "Regression"

        :returns: Temporal Primitive Value
        """
        with self.connection.cursor() as cur:

            datetimes = temporal_value_data['datetimes']
            values = temporal_value_data['values']
            interpolation = temporal_value_data['interpolation']
            temporal_value = self.create_temporalproperty_value(
                datetimes, values, interpolation)

            datetime_group = self.get_temporalvalue_group(
                collection_id, mfeature_id, datetimes)
            dataType = temporal_value["type"]
            pvalue_column = ""
            value = None

            pymeos_initialize()
            if dataType == 'MovingFloat':
                pvalue_column = "pValue_float"
                value = Temporal._factory(
                    tfloat_from_mfjson(json.dumps(temporal_value)))
            else:
                pvalue_column = "pValue_text"
                value = Temporal._factory(
                    ttext_from_mfjson(json.dumps(temporal_value)))

            insert_querry = (
                """INSERT INTO tvalue(collection_id, mfeature_id,
                tproperties_name, datetime_group, {0})
                VALUES ('{1}', '{2}', '{3}', {4}, '{5}')
                 RETURNING tvalue_id"""
                .format(
                    pvalue_column, collection_id, mfeature_id,
                    tproperties_name, datetime_group, str(value)))

            cur.execute(insert_querry)
            tvalue_id = cur.fetchone()[0]

        return tvalue_id

    def put_collection(self, collection_id, collection_property):
        """
        Replace metadata about the collection

        :param collection_id: local identifier of a collection
        :param collection_property: metadata about a collection
            title - human readable title of the collection
            updateFrequency - a time interval of sampling location
            description - any description
            itemType - indicator about the type of the items in the
                       moving features collection (default "movingfeature")
        """
        with self.connection.cursor() as cur:
            cur.execute(
                "UPDATE collection set collection_property = '{0}' \
                        WHERE collection_id = '{1}'" .format(
                    json.dumps(collection_property), collection_id))

    def delete_collection(self, restriction):
        """
        Delete records associated with a collection id

        :param restriction: moving feature collection id
        """

        with self.connection.cursor() as cur:
            cur.execute(
                "DELETE FROM tvalue WHERE 1=1 {0}".format(restriction))
            cur.execute(
                "DELETE FROM tproperties WHERE 1=1 {0}".format(restriction))
            cur.execute(
                "DELETE FROM tgeometry WHERE 1=1 {0}".format(restriction))
            cur.execute(
                "DELETE FROM mfeature WHERE 1=1 {0}".format(restriction))
            cur.execute(
                "DELETE FROM collection WHERE 1=1 {0}".format(restriction))

    def delete_movingfeature(self, restriction):
        """
        Delete records associated with a moving feature id

        :param restriction: moving feature id
        """
        with self.connection.cursor() as cur:
            cur.execute(
                "DELETE FROM tvalue WHERE 1=1 {0}".format(restriction))
            cur.execute(
                "DELETE FROM tproperties WHERE 1=1 {0}".format(restriction))
            cur.execute(
                "DELETE FROM tgeometry WHERE 1=1 {0}".format(restriction))
            cur.execute(
                "DELETE FROM mfeature WHERE 1=1 {0}".format(restriction))

    def delete_temporalgeometry(self, restriction):
        """
        Delete the temporal geometry record with the given restriction.

        :param restriction: temporal geometry id
        """
        with self.connection.cursor() as cur:
            cur.execute(
                "DELETE FROM tgeometry WHERE 1=1 {0}".format(restriction))

    def delete_temporalproperties(self, restriction):
        """
        Delete the temporal properties record with the given restriction.

        :param restriction: temporal properties id
        """

        with self.connection.cursor() as cur:
            cur.execute(
                "DELETE FROM tvalue WHERE 1=1 {0}".format(restriction))
            cur.execute(
                "DELETE FROM tproperties WHERE 1=1 {0}".format(restriction))

    def delete_temporalvalue(self, restriction):
        """
        Delete the temporal value record with the given restriction.

        :param restriction: temporal value id
        """

        with self.connection.cursor() as cur:
            cur.execute(
                "DELETE FROM tvalue WHERE 1=1 {0}".format(restriction))

    def convert_temporalgeometry_to_new_version(self, temporal_geometry):
        """
        Convert temporal geometory to new version

        :param temporal_geometry: MF-JSON TemporalPrimitiveGeometry (object) or
                                 MF-JSON TemporalComplexGeometry

        :returns: temporalGeometry object
        """

        if 'datetimes' in temporal_geometry:
            datetimes = temporal_geometry['datetimes']
            for i in range(len(datetimes)):
                datetimes[i] = datetimes[i].replace('Z', '')
            temporal_geometry['datetimes'] = datetimes

        if 'lower_inc' not in temporal_geometry:
            temporal_geometry['lower_inc'] = True
        if 'upper_inc' not in temporal_geometry:
            temporal_geometry['upper_inc'] = True
        return temporal_geometry

    def convert_temporalgeometry_to_old_version(self, temporal_geometry):
        """
        Convert temporal geometory to old version

        :param temporal_geometry: MF-JSON TemporalPrimitiveGeometry (object) or
                                 MF-JSON TemporalComplexGeometry

        :returns: temporalGeometry object
        """

        if 'datetimes' in temporal_geometry:
            datetimes = temporal_geometry['datetimes']
            for i in range(len(datetimes)):
                datetimes[i] = datetimes[i].split('+')[0] + 'Z'
            temporal_geometry['datetimes'] = datetimes

        if 'lower_inc' in temporal_geometry:
            del temporal_geometry['lower_inc']
        if 'upper_inc' in temporal_geometry:
            del temporal_geometry['upper_inc']

        return temporal_geometry

    def create_temporalproperty_value(self, datetimes, values, interpolation):
        """
        Create temporal property value

        :param datetimes: array of strings <date-time>
        :param values: number or string or boolean
        :param interpolation: Enum: "Discrete" "Step" "Linear" "Regression"

        :returns: temporalValue object
        """

        for i in range(len(datetimes)):
            if isinstance(datetimes[i], int):
                datetimes[i] = datetime.datetime.fromtimestamp(
                    datetimes[i] / 1e3).strftime("%Y/%m/%dT%H:%M:%S.%f")
            else:
                datetimes[i] = datetimes[i].replace('Z', '')

        if all(
            [isinstance(item, int) or isinstance(item, float)
             for item in values]):
            dataType = 'MovingFloat'
        else:
            dataType = 'MovingText'
        temporal_value = {
            "type": dataType,
            "lower_inc": True,
            "upper_inc": True,
            'datetimes': datetimes,
            'values': values,
            'interpolation': interpolation
        }
        return temporal_value

    def convert_temporalproperty_value_to_base_version(
            self, temporal_property_value):
        """
        Convert temporal property value to base version

        :param temporal_property_value: database type(tText,tFloat)
                                        temporalPropertyValue object

        :returns: JSON temporalPropertyValue
        """

        if 'type' in temporal_property_value:
            del temporal_property_value['type']

        if 'datetimes' in temporal_property_value:
            datetimes = temporal_property_value['datetimes']
            for i in range(len(datetimes)):
                datetimes[i] = datetimes[i].split('+')[0] + 'Z'
            temporal_property_value['datetimes'] = datetimes

        if 'lower_inc' in temporal_property_value:
            del temporal_property_value['lower_inc']
        if 'upper_inc' in temporal_property_value:
            del temporal_property_value['upper_inc']
        return temporal_property_value

    def validate_lifespan(self, datetime_=None) -> str:
        """
        Validate datetime lifespan

        :param datetime_: either a date-time or an interval. (default None)

        :returns: start and end datetype string
        """

        datetime_for_return = ''
        if datetime_ is not None and datetime_ != []:
            dateparse_begin = partial(dateparse, default=datetime.datetime.min)
            dateparse_end = partial(dateparse, default=datetime.datetime.max)

            datetime_begin = datetime_[0]
            datetime_end = datetime_[-1]
            datetime_begin = dateparse_begin(datetime_begin)
            if datetime_begin.tzinfo is None:
                datetime_begin = datetime_begin.replace(
                    tzinfo=pytz.UTC)

            datetime_end = dateparse_end(datetime_end)
            if datetime_end.tzinfo is None:
                datetime_end = datetime_end.replace(tzinfo=pytz.UTC)

            datetime_invalid = any([
                (datetime_begin > datetime_end)
            ])

            if not datetime_invalid:
                datetime_for_return = datetime_begin.strftime(
                    '%Y-%m-%d %H:%M:%S.%f') + ',' + \
                    datetime_end.strftime('%Y-%m-%d %H:%M:%S.%f')
        return datetime_for_return

    def check_temporalproperty_can_post(
            self, collection_id, mfeature_id, temporal_properties,
            tproperties_name=None):
        """
        Check temporalProperties object can be POSTed

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature
        :param temporal_properties: temporalProperties object
        :param tproperties_name: temporal property name (default None)

        :returns: True or False
        """

        with self.connection.cursor() as cur:
            for temporal_property in temporal_properties:
                g_temporal_property = dict(temporal_property)
                if 'datetimes' in g_temporal_property:
                    datetimes = g_temporal_property["datetimes"]
                    for i in range(len(datetimes)):
                        if isinstance(datetimes[i], int):
                            datetimes[i] = datetime.datetime.fromtimestamp(
                                datetimes[i] / 1e3)\
                                .strftime("%Y/%m/%dT%H:%M:%S.%f")
                        else:
                            datetimes[i] = datetimes[i].replace('Z', '')

                    tproperties_name_list = []
                    if tproperties_name is not None:
                        tproperties_name_list = [tproperties_name]
                    else:
                        for tproperties_name in g_temporal_property:
                            tproperties_name_list.append(tproperties_name)

                    select_query = (
                        """select collection_id, mfeature_id, tproperties_name,
                    count(datetime_group) as intersect_count
                    from tvalue where collection_id ='{0}'
                    and mfeature_id='{1}' and tproperties_name in ({2})
                    and ((pvalue_float::tstzspan && tstzset('{3}')::tstzspan)
                    or (pvalue_text::tstzspan && tstzset('{3}')::tstzspan))
                    group by collection_id, mfeature_id, tproperties_name"""
                        .format(collection_id, mfeature_id,
                                "'" + "', '".join(tproperties_name_list) + "'",
                                "{" + ", ".join(datetimes) + "}"))
                    cur.execute(select_query)
                    rows = cur.fetchall()

                    for row in rows:
                        if int(row[3]) > 0:
                            return False
        return True

    def get_temporalvalue_group(
            self, collection_id, mfeature_id, datetimes):
        """
        Get temporal properties group

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature
        :param datetimes: array of strings <date-time>

        :returns: ID of the group that summarizes same datetime in tproperty
        """

        with self.connection.cursor() as cur:
            for i in range(len(datetimes)):
                if isinstance(datetimes[i], int):
                    datetimes[i] = datetime.datetime.fromtimestamp(
                        datetimes[i] / 1e3).strftime("%Y/%m/%dT%H:%M:%S.%f")
                else:
                    datetimes[i] = datetimes[i].replace('Z', '')

            select_query = (
                """select temp1.collection_id, temp1.mfeature_id,
                COALESCE(temp2.datetime_group, temp3.max_datetime_group)
                from (select collection_id, mfeature_id from tvalue
                where collection_id ='{0}' and mfeature_id='{1}') temp1
                left outer join (select collection_id, mfeature_id,
                datetime_group from tvalue
                where collection_id ='{0}' and mfeature_id='{1}'
                and (set(timestamps(pvalue_float)) = tstzset('{2}')
                or set(timestamps(pvalue_text)) = tstzset('{2}'))) temp2
                on temp1.collection_id = temp2.collection_id
                and temp1.mfeature_id = temp2.mfeature_id
                left outer join (select collection_id, mfeature_id,
                COALESCE(max(datetime_group), 0) + 1 as max_datetime_group
                from tvalue where collection_id ='{0}'
                and mfeature_id='{1}'
                group by collection_id, mfeature_id ) temp3
                on temp1.collection_id = temp3.collection_id
                and temp1.mfeature_id = temp3.mfeature_id """
                .format(collection_id, mfeature_id,
                        "{" + ", ".join(datetimes) + "}"))
            print(select_query)
            cur.execute(select_query)
            result = cur.fetchall()
        if len(result) > 0:
            return result[0][2]
        return 1

    def get_velocity(
            self, collection_id, mfeature_id, tgeometry_id, datetime=None):
        """
        Get temporal property of velocity

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature
        :param tgeometry_id: local identifier of a geometry
        :param datetime: array of strings <date-time> (default None)

        :returns: TemporalProperty of velocity
        """

        form = "MTS"
        name = "velocity"

        with self.connection.cursor() as cur:
            if datetime is None:
                select_query = f"""SELECT speed(tgeog_property) AS speed
                FROM tgeometry
                WHERE collection_id = '{collection_id}'
                and mfeature_id = '{mfeature_id}'
                and tgeometry_id = '{tgeometry_id}'"""
            else:
                select_query = \
                    f"""SELECT valueAtTimestamp(speed(tgeog_property),
                '{datetime}') AS speed, interp(speed(tgeog_property))
                AS interp
                FROM tgeometry
                WHERE collection_id = '{collection_id}'
                and mfeature_id = '{mfeature_id}'
                and tgeometry_id = '{tgeometry_id}'"""
            cur.execute(select_query)
            result = cur.fetchall()

        return self.to_tproperties(result, name, form, datetime)

    def get_distance(
            self, collection_id, mfeature_id, tgeometry_id, datetime=None):
        """
        Get temporal property of distance

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature
        :param tgeometry_id: local identifier of a geometry
        :param datetime: array of strings <date-time> (default None)

        :returns: TemporalProperty of distance
        """

        form = "MTR"
        name = "distance"
        with self.connection.cursor() as cur:
            if datetime is None:
                select_query = f"""SELECT cumulativeLength(tgeog_property)
                AS distance FROM tgeometry
                WHERE collection_id = '{collection_id}'
                and mfeature_id = '{mfeature_id}'
                and tgeometry_id = '{tgeometry_id}'"""
            else:
                select_query = f"""SELECT
                valueAtTimestamp(cumulativeLength(tgeog_property),
                                '{datetime}') AS distance,
                interp(cumulativeLength(tgeog_property)) AS interp
                FROM tgeometry
                WHERE collection_id = '{collection_id}'
                and mfeature_id = '{mfeature_id}'
                and tgeometry_id = '{tgeometry_id}'"""
            cur.execute(select_query)
            result = cur.fetchall()

        return self.to_tproperties(result, name, form, datetime)

    def get_acceleration(
            self, collection_id, mfeature_id, tgeometry_id, datetime=None):
        """
       Get temporal property of acceleration

        :param collection_id: local identifier of a collection
        :param mfeature_id: local identifier of a moving feature
        :param tgeometry_id: local identifier of a geometry
        :param datetime: array of strings <date-time> (default None)

        :returns: TemporalProperty of acceleration
        """

        tProperty = {
            "name": "acceleration",
            "type": "TReal",
            "form": "MTS",
            "valueSequence": []
        }
        with self.connection.cursor() as cur:
            select_query = f"""SELECT speed(tgeog_property) AS speed
            FROM tgeometry WHERE collection_id = '{collection_id}'
            and mfeature_id = '{mfeature_id}'
            and tgeometry_id = '{tgeometry_id}'"""
            cur.execute(select_query)
            result = cur.fetchall()

        pymeos_initialize()
        for each_row in result:
            each_row_converted = TFloatSeqSet(each_row[0])
            interpolation = each_row_converted.interpolation().to_string()

            each_time = [
                each_val.time().start_timestamp().strftime(
                    '%Y-%m-%dT%H:%M:%S.%fZ')
                for each_val in each_row_converted.instants()]
            if interpolation == "Step":
                each_values = [0 for each_val in each_row_converted.instants()]
            else:
                each_values = [each_val.value()
                               for each_val in each_row_converted.instants()]

            value_sequence = self.calculate_acceleration(
                each_values, each_time, datetime)
            if value_sequence.get("values"):
                if datetime is not None:
                    value_sequence["interpolation"] = "Discrete"
                elif interpolation == "Linear":
                    value_sequence["interpolation"] = "Step"
                else:
                    value_sequence["interpolation"] = interpolation
            tProperty["valueSequence"].append(value_sequence)
        return tProperty

    def to_tproperties(self, results, name, form, datetime):
        """
        Convert Temoral properties object

        :param results: temporal property object of query
        :param name: temporal property name
        :param form: a unit of measurement
        :param datetime: array of strings <date-time>

        :returns: TemporalProperty object
        """
        tProperty = {
            "name": name,
            "type": "TReal",
            "form": form,
            "valueSequence": []
        }
        pymeos_initialize()
        for each_row in results:
            if datetime is None:
                each_row_converted = None
                if name == "velocity":
                    each_row_converted = TFloatSeqSet(each_row[0])
                else:
                    each_row_converted = TFloatSeq(each_row[0])
                each_values = [each_val.value()
                               for each_val in each_row_converted.instants()]
                each_time = [
                    each_val.time().start_timestamp().strftime(
                        '%Y-%m-%dT%H:%M:%S.%fZ')
                    for each_val in each_row_converted.instants()]
                interpolation = each_row_converted.interpolation().to_string()
                value_sequence = {
                    "datetimes": each_time,
                    "values": each_values,
                    "interpolation": interpolation
                }
            else:
                value_sequence = {
                    "datetimes": [format_datetime(datetime)],
                    "values": [each_row[0]],
                    "interpolation": "Discrete"
                }
            tProperty["valueSequence"].append(value_sequence)
        return tProperty

    def calculate_acceleration(self, velocities, times, chk_dtime):
        """
        Calculate acceleration

        :param velocities: interpolation value list
        :param times: interpolation datetime list
        :param chk_dtime: array of strings <date-time>

        :returns: valueSequence object
        """

        value_sequence = {}
        time_format = '%Y-%m-%d %H:%M:%S.%f'
        time_format2 = '%Y-%m-%dT%H:%M:%S.%fZ'
        if chk_dtime is not None:
            chk_time = datetime.datetime.strptime(chk_dtime, time_format)

            for i in range(1, len(velocities)):
                time1 = datetime.datetime.strptime(times[i - 1], time_format2)
                time2 = datetime.datetime.strptime(times[i], time_format2)
                if chk_time <= time2 and chk_time >= time1:
                    delta_v = velocities[i] - velocities[i - 1]
                    delta_t = (time2 - time1).total_seconds()
                    acceleration = delta_v / delta_t
                    value_sequence["values"] = [acceleration]
                    value_sequence["datetimes"] = [format_datetime(chk_dtime)]
                    break
        else:
            value_sequence["values"] = []
            value_sequence["datetimes"] = []
            for i in range(1, len(velocities)):
                delta_v = velocities[i] - velocities[i - 1]
                time1 = datetime.datetime.strptime(times[i - 1], time_format2)
                time2 = datetime.datetime.strptime(times[i], time_format2)
                delta_t = (time2 - time1).total_seconds()
                acceleration = delta_v / delta_t
                value_sequence["values"].append(acceleration)
                value_sequence["datetimes"].append(times[i])

        return value_sequence
