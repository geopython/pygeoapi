"""
For evaluating CQL filter queries from Abstract Syntax Tree
"""

import logging
from datetime import datetime

from pygeoapi.cql_exception import (CQLExceptionAttribute,
                                    CQLExceptionCombination,
                                    CQLExceptionSpatial,
                                    CQLExceptionUnits,
                                    CQLExceptionTemporal,
                                    CQLExceptionBBox
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

    try:
        where_clause = "{} {} {}".format(sub_filters[0],
                                         combination,
                                         sub_filters[1])
        return where_clause

    except IndexError as err:
        LOGGER.error("Invalid index {}".format(err))
        raise CQLExceptionCombination()


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

    where_clause = "NOT {}".format(sub_filter)
    return where_clause


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

    if isinstance(rhs, str):
        rhs = "'{}'".format(rhs)

    where_clause = "{}{}{}".format(lhs, op, rhs)
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

    where_clause = "{} BETWEEN {} AND {}".format(lhs, low, high)

    # where clause for negation operation
    if not_:
        where_clause = "{} NOT BETWEEN {} AND {}".format(lhs, low, high)

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

    where_clause = "{} LIKE '{}'".format(lhs, rhs)

    # where clause for negation operation
    if not_:
        where_clause = "{} NOT LIKE '{}'".format(lhs, rhs)
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

    where_clause = "{} IN {}".format(lhs, tuple(items))

    # where clause for negation operation
    if not_:
        where_clause = "{} NOT IN {}".format(lhs, tuple(items))

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

    where_clause = "{} IS NULL".format(lhs)
    if not_:
        where_clause = "{} IS NOT NULL".format(lhs)

    return where_clause


def temporal(feature_list, lhs, time_or_period, op):
    """
    Create a temporal filter for the given temporal attribute.

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
    :param lhs: the field to compare
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
        if lhs != "datetime":
            raise CQLExceptionTemporal("Invalid field name: {}".format(lhs))
        where_clause = ""

        # perform before and after operations
        if op in ['BEFORE', 'AFTER']:
            query_date_time = datetime.strptime(
                time_or_period.value, "%Y-%m-%dT%H:%M:%SZ")
            if op == 'BEFORE':
                where_clause =\
                    "{date}<={parameter}".format(date=lhs,
                                                 parameter=query_date_time)

            elif op == 'AFTER':
                where_clause =\
                    "{date}>={parameter}".format(date=lhs,
                                                 parameter=query_date_time)

        # perform during operation
        elif 'DURING' in op:
            low, high = time_or_period
            low = datetime.strptime(low.value, "%Y-%m-%dT%H:%M:%SZ")
            high = datetime.strptime(high.value, "%Y-%m-%dT%H:%M:%SZ")
            where_clause =\
                "{date}>={low} AND {date}<={high}".format(date=lhs,
                                                          low=low,
                                                          high=high)
            if 'BEFORE' in op:
                where_clause =\
                    "{date}<={high}".format(date=lhs,
                                            high=high)
            elif 'AFTER' in op:
                where_clause =\
                    "{date}>={low}".format(date=lhs,
                                           low=low)
        return where_clause

    except Exception as err:
        LOGGER.error("Invalid 'temporal' operation: {}".format(err))
        raise CQLExceptionTemporal()


Spatial_Operator = {
    "INTERSECTS": "ST_Intersects",
    "DISJOINT": "ST_Disjoint",
    "WITHIN": "ST_Within",
    "CONTAINS": "ST_Contains",
    "TOUCHES": "ST_Touches",
    "CROSSES": "ST_Crosses",
    "EQUALS": "ST_Equals",
    "OVERLAPS": "ST_Overlaps",
    "BEYOND": "ST_Distance",
    "DWITHIN": "ST_Distance",
    "RELATE": "ST_Relate"
}


def spatial(feature_list, lhs, rhs, op,
            pattern=None, distance=None, units=None):
    """
    Create a spatial filter for the given spatial attribute.

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
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
            if units == 'meters':
                distance = distance / 1000

            if op == "BEYOND":
                where_clause =\
                    "{relation}({geometry},ST_GeomFromText('{parameter}'))" \
                    ">={distance}".format(relation=Spatial_Operator[op],
                                          geometry="{}",
                                          parameter=rhs,
                                          distance=distance)
            else:
                where_clause =\
                    "{relation}({geometry},ST_GeomFromText('{parameter}'))" \
                    "<={distance}".format(relation=Spatial_Operator[op],
                                          geometry="{}",
                                          parameter=rhs,
                                          distance=distance)

        elif op == "RELATE":
            where_clause =\
                "{relation}({geometry},ST_GeomFromText('{parameter}')," \
                "'{pattern}')".format(relation=Spatial_Operator[op],
                                      geometry="{}",
                                      parameter=rhs,
                                      pattern=pattern)
        else:
            where_clause =\
                "{relation}({geometry},ST_GeomFromText('{parameter}')" \
                ")".format(relation=Spatial_Operator[op],
                           geometry="{}",
                           parameter=rhs)

        return where_clause

    except KeyError:
        LOGGER.error("Invalid operator : {}".format(op))
        raise CQLExceptionSpatial()

    except Exception as err:
        LOGGER.error("Invalid 'spatial' operation: {}".format(err))
        raise CQLExceptionSpatial()


def bbox(feature_list, lhs, minx, miny, maxx, maxy,
         crs=None, bboverlaps=True):
    """
    Create a bounding box filter for the given spatial attribute.

    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list
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

    try:
        if lhs != "geometry":
            raise CQLExceptionBBox(
                "Invalid field name: {}".format(lhs)
            )

        bbox = 'Polygon(({minx} {miny}, {maxx} {miny}, ' \
               '{maxx} {maxy}, {minx} {maxy}, ' \
               '{minx} {miny}))'.format(minx=minx,
                                        miny=miny,
                                        maxx=maxx,
                                        maxy=maxy)

        where_clause = "ST_Intersects({geometry},ST_ENVELOPE('{bbox}')" \
                       ")".format(geometry="{}", bbox=bbox)
        return where_clause

    except Exception as err:
        LOGGER.error("Invalid 'spatial' operation: {}".format(err))
        raise CQLExceptionBBox()


def attribute(name, field_name=None):
    """
    Create an attribute lookup expression using a field mapping dictionary.

    :param name: the field filter name
    :type name: str
    :param field_name: the dictionary to use as a lookup.
    :type field_name: list of feature dict set

    :return: field name
    :rtype: str
    """

    try:
        if name.lower() in field_name:
            field = name
            return str(field)
        else:
            raise CQLExceptionAttribute(
                "Invalid field value: {}".format(name)
            )

    except Exception as err:
        LOGGER.error(err)
        raise CQLExceptionAttribute()
