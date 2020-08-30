"""
To form WHERE CLAUSES of CQL filter queries
from Abstract Syntax Tree for PostGres
"""

import logging
from datetime import datetime
from psycopg2.sql import SQL, Identifier, Literal

from pygeoapi.cql_exception import (CQLExceptionAttribute,
                                    CQLExceptionSpatial,
                                    CQLExceptionUnits,
                                    CQLExceptionTemporal
                                    )

LOGGER = logging.getLogger(__name__)


def combine(sub_filters, combination):
    """
    Combine filters using a logical combinator

    :param sub_filters: the filters to combine
    :type sub_filters: tuple of multiple sub-filter result
    :param combination: "AND" / "OR"
    :type combination: str

    :return: sql where clause
    :rtype: str
    """

    where_conditions = []
    for sub_filter in sub_filters:
        where_conditions += sub_filter

    if where_conditions:
        if combination == "AND":
            where_clause = SQL('{}').format(
                SQL(' AND ').join(where_conditions))
        else:
            where_clause = SQL('{}').format(
                SQL(' OR ').join(where_conditions))

    return where_clause


def negate(feature_list, sub_filter):
    """
    Negate a filter, opposing its meaning.

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
    :param sub_filter: the subfilter to negate
    :type sub_filter: list

    :return: sql where clause
    :rtype: str
    """

    where_clause = [SQL(' NOT {}').format(SQL(' AND ').join(sub_filter))]

    return where_clause


Comparisons = {
    "<": SQL('{} < {}'),
    "<=": SQL('{} <= {}'),
    ">": SQL('{} > {}'),
    ">=": SQL('{} >= {}'),
    "<>": SQL('{} <> {}'),
    "=": SQL('{} = {}'),
}


def compare(feature_list, lhs, rhs, op):
    """
    Compare a filter with an expression using a comparison operation

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
    :param lhs: the field to compare
    :type lhs: str
    :param rhs: the filter expression
    :type rhs: literal
    :param op: a string denoting the operation. one of ``"<"``, ``"<="``,
                ``">"``, ``">="``, ``"<>"``, ``"="``
    :type op: str

    :return: sql where clause
    :rtype: str
    """

    where_clause = [Comparisons[op].format(Identifier(lhs), Literal(rhs))]

    return where_clause


def between(feature_list, lhs, low, high, not_=False):
    """
    Create a filter to match elements that have a value within a certain
    range.

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
    :param lhs: the field to compare
    :type lhs: str
    :param low: the lower value of the range
    :type low: literal
    :param high: the upper value of the range
    :type high: literal
    :param not_: whether the range shall be inclusive (the default) or
                    exclusive
    :type not_: bool

    :return: sql where clause
    :rtype: str
    """

    where_clause = [SQL('{} BETWEEN {} AND {}').format(
        Identifier(lhs), Literal(low), Literal(high))]

    if not_:
        where_clause = [SQL('{} NOT BETWEEN {} AND {}').format(
            Identifier(lhs), Literal(low), Literal(high))]

    return where_clause


def like(feature_list, lhs, rhs, case=False, not_=False):
    """
    Create a filter to filter elements according to a string attribute
    using wildcard expressions.

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
    :param lhs: the field to compare
    :type lhs: str
    :param rhs: the wildcard pattern: a string containing any number of '%'
                characters as wildcards.
    :type rhs: str
    :param case: whether the lookup shall be done case sensitively or not
    :type case: bool
    :param not_: whether the range shall be inclusive (the default) or
                    exclusive
    :type not_: bool

    :return: sql where clause
    :rtype: str
    """

    if not case:
        lhs = "UPPER({})".format(lhs)
        rhs = rhs.upper()

    where_clause = [SQL('{} LIKE {}').format(
        Identifier(lhs), Literal(rhs))]

    if not_:
        where_clause = [SQL('{} NOT LIKE {}').format(
            Identifier(lhs), Literal(rhs))]

    return where_clause


def contains(feature_list, lhs, items, not_=False):
    """
    Create a filter to match elements attribute to be in a list of choices.

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
    :param lhs: the field to compare
    :type lhs: str
    :param items: a list of choices
    :type items: list
    :param not_: whether the range shall be inclusive (the default) or
                    exclusive
    :type not_: bool

    :return: sql where clause
    :rtype: str
    """

    where_clause = [SQL('{} IN {}').format(
        Identifier(lhs), Literal(tuple(items)))]

    if not_:
        where_clause = [SQL('{} NOT IN {}').format(
            Identifier(lhs), Literal(tuple(items)))]

    return where_clause


def is_null(feature_list, lhs, not_=False):
    """
    Create a filter to match elements whose attribute is (not) null

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
    :param lhs: the field to compare
    :type lhs: string
    :param not_: whether the range shall be inclusive (the default) or
                    exclusive
    :type not_: bool

    :return: sql where clause
    :rtype: str
    """

    where_clause = [SQL('{} IS NULL').format(Identifier(lhs))]

    if not_:
        where_clause = [SQL('{} IS NOT NULL').format(Identifier(lhs))]

    return where_clause


def temporal(feature_list, field_list, lhs, time_or_period, op):
    """
    Create a temporal filter for the given temporal attribute.

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
    :param field_list: the dictionary to use as a lookup for field names
    :type field_list: dict
    :type lhs: str
    :param time_or_period: the time instant or time span to use as a filter
    :type time_or_period: :class:`datetime.datetime` or a tuple of two
                            datetimes or a tuple of one datetime and one
                            :class:`datetime.timedelta`
    :param op: the comparison operation. one of ``"BEFORE"``,
                ``"BEFORE OR DURING"``, ``"DURING"``, ``"DURING OR AFTER"``,
                ``"AFTER"``.
    :type op: str

    :return: sql where clause
    :rtype: str
    """

    try:
        where_clause = ""

        # perform before and after operations
        if op in ['BEFORE', 'AFTER']:
            query_date_time = datetime.strptime(
                time_or_period.value, "%Y-%m-%dT%H:%M:%SZ")
            if op == 'BEFORE':
                where_clause = [SQL('{} <= {}').format(
                    Identifier(field_list[lhs]),
                    Literal(query_date_time))]

            elif op == 'AFTER':
                where_clause = [SQL('{} >= {}').format(
                    Identifier(field_list[lhs]),
                    Literal(query_date_time))]

        # perform during operation
        elif 'DURING' in op:
            low, high = time_or_period
            low = datetime.strptime(low.value, "%Y-%m-%dT%H:%M:%SZ")
            high = datetime.strptime(high.value, "%Y-%m-%dT%H:%M:%SZ")

            where_conditions = []
            where_conditions = [SQL('{} >= {}').format(
                Identifier(field_list[lhs]), Literal(low))]
            where_conditions += [SQL('{} <= {}').format(
                Identifier(field_list[lhs]), Literal(high))]

            if where_conditions:
                where_clause = SQL('{}').format(
                    SQL(' AND ').join(where_conditions))

            if 'BEFORE' in op:
                where_clause = [SQL('{} <= {}').format(
                    Identifier(field_list[lhs]),
                    Literal(high))]

            elif 'AFTER' in op:
                where_clause = [SQL('{} >= {}').format(
                    Identifier(field_list[lhs]),
                    Literal(low))]

        return where_clause

    except Exception as err:
        LOGGER.error("Invalid 'temporal' operation: {}".format(err))
        raise CQLExceptionTemporal()


Spatial_Operator = {
    "INTERSECTS": SQL('ST_Intersects'),
    "DISJOINT": SQL('ST_Disjoint'),
    "WITHIN": SQL('ST_Within'),
    "CONTAINS": SQL('ST_Contains'),
    "TOUCHES": SQL('ST_Touches'),
    "CROSSES": SQL('ST_Crosses'),
    "EQUALS": SQL('ST_Equals'),
    "OVERLAPS": SQL('ST_Overlaps'),
    "BEYOND": SQL('ST_DWITHIN'),
    "DWITHIN": SQL('ST_DWITHIN'),
    "RELATE": SQL('ST_Relate')
}


def spatial(feature_list, field_list, lhs, rhs, op,
            pattern=None, distance=None, units=None):
    """
    Create a spatial filter for the given spatial attribute

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
    :param field_list: the dictionary to use as a lookup for field names
    :type field_list: dict
    :param lhs: the field to compare
    :type lhs: str
    :param rhs: spatial expression
    :type rhs: geometry
    :param op: the comparison operation. one of ``"INTERSECTS"``,
                ``"DISJOINT"``, `"CONTAINS"``, ``"WITHIN"``,
                ``"TOUCHES"``, ``"CROSSES"``, ``"OVERLAPS"``,
                ``"EQUALS"``, ``"RELATE"``, ``"DWITHIN"``, ``"BEYOND"``
    :type op: str
    :param pattern: the spatial relation pattern
    :type pattern: str
    :param distance: the distance value for distance based lookups:
                        ``"DWITHIN"`` and ``"BEYOND"``
    :type distance: float
    :param units: the units the distance is expressed in
    :type units: str

    :return: sql where clause
    :rtype: str
    """

    try:
        if lhs != "geometry":
            raise CQLExceptionSpatial("Invalid field name: {}".format(lhs))

        rhs = str(rhs.value)

        if op in ['DWITHIN', 'BEYOND']:
            if units is None or units not in ['meters', 'kilometers']:
                raise CQLExceptionUnits(
                    "Invalid distance units: {}".format(units)
                )
            if units == 'kilometers':
                distance = distance * 1000

            where_condition = [
                SQL('{relation}({geometry},'
                    'ST_GeomFromText({parameter},{srid}), '
                    '{distance})').format(
                    relation=Spatial_Operator[op],
                    geometry=Identifier(field_list[lhs]),
                    parameter=Literal(rhs), srid=Literal(4326),
                    distance=Literal(distance))
            ]

            if op == "BEYOND":
                where_clause = [
                    SQL(' NOT {}').format(SQL(' AND ').join(
                        where_condition))]
            else:
                where_clause = where_condition

        elif op == "RELATE":
            where_clause = [
                SQL('{relation}({geometry},'
                    'ST_GeomFromText({parameter},{srid}), '
                    '{pattern})').format(
                    relation=Spatial_Operator[op],
                    geometry=Identifier(field_list[lhs]),
                    parameter=Literal(rhs), srid=Literal(4326),
                    distance=Literal(distance),
                    pattern=Literal(pattern))]

        else:
            where_clause = [
                SQL('{relation}({geometry},'
                    'ST_GeomFromText({parameter},{srid}))').format(
                    relation=Spatial_Operator[op],
                    geometry=Identifier(field_list[lhs]),
                    parameter=Literal(rhs), srid=Literal(4326))
            ]

        return where_clause

    except KeyError:
        LOGGER.error("Invalid operator : {}".format(op))
        raise CQLExceptionSpatial()

    except Exception as err:
        LOGGER.error("Invalid 'spatial' operation: {}".format(err))
        raise CQLExceptionSpatial()


def bbox(feature_list, field_list, lhs, minx, miny, maxx, maxy,
         crs=None, bboverlaps=True):
    """
    Create a bounding box filter for the given spatial attribute.

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
    :param field_list: the dictionary to use as a lookup for field names
    :type field_list: dict
    :param lhs: the field to compare
    :type lhs: str
    :param minx: the lower x part of the bbox
    :type minx: float
    :param miny: the lower y part of the bbox
    :type miny: float
    :param maxx: the upper x part of the bbox
    :type maxx: float
    :param maxy: the upper y part of the bbox
    :type maxy: float
    :param crs: the CRS the bbox is expressed in
    :type crs: str

    :return: sql where clause
    :rtype: str
    """

    bbox_coord = [Literal(minx), Literal(miny), Literal(maxx), Literal(maxy)]
    where_conditions = []
    bbox_clause = SQL('{} && ST_MakeEnvelope({})').format(
        Identifier(field_list[lhs]), SQL(', ').join(bbox_coord))
    where_conditions.append(bbox_clause)

    if where_conditions:
        where_clause = SQL('{}').format(
            SQL(' AND ').join(where_conditions))

    return where_clause


def attribute(name, field_name):
    """
    Create an attribute lookup expression using a field mapping dictionary.

    :param name: the field filter name
    :type name: str
    :param field_name: the dictionary to use as a lookup for field names
    :type field_name: dict

    :return: field name
    :rtype: str
    """

    try:
        if name.lower() in field_name.keys():
            field = name
            return str(field)
        else:
            raise CQLExceptionAttribute(
                "Invalid field value: {}".format(name)
            )

    except Exception as err:
        LOGGER.error(err)
        raise CQLExceptionAttribute()
