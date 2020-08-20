"""
For evaluating CQL filter queries from Abstract Syntax Tree
"""

import logging
import re
from datetime import datetime
from shapely.geometry import Point, Polygon, box
import shapely.wkt

from pygeoapi.exception import (CQLException,
                                CQLExceptionAttribute,
                                CQLExceptionCombination,
                                CQLExceptionLogicalCombinator,
                                CQLExceptionComparison,
                                CQLExceptionBetween, CQLExceptionNull,
                                CQLExceptionIn, CQLExceptionLike,
                                CQLExceptionComparator,
                                CQLExceptionSpatial,
                                CQLExceptionSpatialOperator,
                                CQLExceptionUnits,
                                CQLExceptionPattern, CQLExceptionTemporal,
                                CQLExceptionTemporalOperator,
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

    :return: a combined expression result
    :rtype: list
    """

    try:
        if combination not in ["AND", "OR"]:
            raise CQLExceptionLogicalCombinator(
                "Invalid combination operator: {}".format(combination)
            )

        filtered_feature_list = []
        intersection = []
        union = []
        for row in sub_filters[0]:
            intersection.append(row) if row in sub_filters[1] \
                else union.append(row)

        # perform combination operation
        filtered_feature_list = intersection if combination == "AND" \
            else union + sub_filters[1]

        return filtered_feature_list

    except IndexError as err:
        LOGGER.error("Invalid index {}".format(err))
        raise CQLExceptionCombination()

    except Exception as err2:
        LOGGER.error("Invalid combination operation: {}".format(err2))
        raise CQLExceptionCombination()


def negate(feature_list, filtered_feature_list):
    """
    Negate a filter, opposing its meaning.

    :param filtered_feature_list: the filter to negate
    :type filtered_feature_list: list
    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list

    :return: the negated list
    :rtype: list
    """

    filtered_feature_list = list(
        filter(
            lambda record: record not in filtered_feature_list,
            feature_list
        )
    )
    return filtered_feature_list


# Comparison operation dictionary
Comparisons = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<>": lambda a, b: a != b,
    "=": lambda a, b: a == b,
}


def compare(feature_list, lhs, rhs, op):
    """
    Compare a filter with an expression using a comparison operation

    :param lhs: the field to compare
    :type lhs: str
    :param rhs: the filter expression
    :type rhs: literal
    :param op: a string denoting the operation. one of ``"<"``, ``"<="``,
                ``">"``, ``">="``, ``"<>"``, ``"="``
    :type op: str
    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list

    :return: a comparison expression result
    :rtype: list
    """

    try:
        if op not in Comparisons.keys():
            raise CQLExceptionComparator("Invalid comparison operator: {}".
                                         format(op))

        filtered_feature_list = []

        # perform comparison operation
        filtered_feature_list = list(
            filter(
                lambda record, lhs=lhs, rhs=rhs:
                (Comparisons[op])(float(get_field_value(record, lhs)),
                                  float(rhs)
                                  ),
                feature_list
            )
        )

        return filtered_feature_list

    except Exception as err:
        LOGGER.error("Invalid comparison operation: {}".format(err))
        raise CQLExceptionComparison()


def between(feature_list, lhs, low, high, not_=False):
    """
    Create a filter to match elements that have a value within a certain
    range.

    :param lhs: the field to compare
    :type lhs: str
    :param low: the lower value of the range
    :type low: literal
    :param high: the upper value of the range
    :type high: literal
    :param not_: whether the range shall be inclusive (the default) or
                    exclusive
    :type not_: bool
    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list

    :return: a comparison expression result
    :rtype: list
    """

    try:
        filtered_feature_list = []

        # perform between operation
        filtered_feature_list = list(
            filter(
                lambda record, lhs=lhs, low=low, high=high:
                float(get_field_value(record, lhs)) >= low
                and float(get_field_value(record, lhs)) <= high,
                feature_list
            )
        )

        # perform negation operation
        if not_:
            filtered_feature_list = negate(feature_list, filtered_feature_list)

        return filtered_feature_list

    except Exception as err:
        LOGGER.error("Invalid 'between' operation: {}".format(err))
        raise CQLExceptionBetween()


def like(feature_list, lhs, rhs, case=False, not_=False):
    """
    Create a filter to filter elements according to a string attribute
    using wildcard expressions.

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
    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list

    :return: a comparison expression result
    :rtype: list
    """

    try:
        filtered_feature_list = []

        regex = generate_regex(rhs, case)
        matcher = re.compile(regex)

        # perform like operation with case sensitivity
        filtered_feature_list = list(
            filter(
                lambda record, matcher=matcher:
                matcher.search(get_field_value(record, lhs))
                if case
                else matcher.search(get_field_value(record, lhs).lower()),
                feature_list
            )
        )

        # perform negation operation
        if not_:
            filtered_feature_list = negate(feature_list, filtered_feature_list)

        return filtered_feature_list

    except Exception as err:
        LOGGER.error("Invalid 'like' operation: {}".format(err))
        raise CQLExceptionLike()


def generate_regex(query_string, case):
    """
    Helper function to get regex expression of string

    :param query_string: query string
    :type query_string: str
    :param case: for regex to be case sensitive
    :type case: bool

    :returns: regex str
    :rtype: str
    """

    regex = None

    if query_string.startswith('%') and query_string.endswith('%'):
        regex = query_string[1:len(query_string) - 1]
    elif query_string.startswith('%'):
        regex = query_string[1:len(query_string)] + '$'
    elif query_string.endswith('%'):
        regex = '^' + query_string[0:len(query_string) - 1]
    elif '%' in query_string:
        pos = query_string.index('%')
        regex = '^' + query_string[:pos] + '(.*?)' + \
                query_string[pos + 1:] + '$'
    elif query_string:
        regex = '^' + query_string + '$'

    # check for case sensitivity
    if not case:
        return regex.lower()

    return regex


def contains(feature_list, lhs, items, not_=False):
    """
    Create a filter to match elements attribute to be in a list of choices.

    :param lhs: the field to compare
    :type lhs: str
    :param items: a list of choices
    :type items: list
    :param not_: whether the range shall be inclusive (the default) or
                    exclusive
    :type not_: bool
    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list

    :return: a comparison expression result
    :rtype: list
    """

    try:
        filtered_feature_list = []

        # perform contains operation
        filtered_feature_list = list(
            filter(
                lambda record, lhs=lhs, items=items:
                get_field_value(record, lhs) in items,
                feature_list
            )
        )

        # perform negation operation
        if not_:
            filtered_feature_list = negate(feature_list, filtered_feature_list)

        return filtered_feature_list

    except Exception as err:
        LOGGER.error("Invalid 'in' operation: {}".format(err))
        raise CQLExceptionIn()


def is_null(feature_list, lhs, not_=False):
    """
    Create a filter to match elements whose attribute is (not) null

    :param lhs: the field to compare
    :type lhs: string
    :param not_: whether the range shall be inclusive (the default) or
                    exclusive
    :type not_: bool
    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list

    :return: a comparison expression result
    :rtype: list
    """

    try:
        filtered_feature_list = []

        # perform null checking
        filtered_feature_list = list(
            filter(
                lambda record, lhs=lhs:
                ((get_field_value(record, lhs) is not None
                  and get_field_value(record, lhs) == 'null')
                 or get_field_value(record, lhs) is None),
                feature_list
            )
        )

        # perform negation operation
        if not_:
            filtered_feature_list = negate(feature_list, filtered_feature_list)

        return filtered_feature_list

    except Exception as err:
        LOGGER.error("Invalid 'null' operation: {}".format(err))
        raise CQLExceptionNull()


def get_field_value(record, lhs):
    """
    Helper function to get matching field's value from for all the features

    :param record: a feature meta-data
    :type record: dict
    :param lhs: the field name
    :type lhs: str

    :return: field value
    :rtype: literal
    """

    try:
        field_value = None
        if lhs in record.keys():
            field_value = record[lhs]
        elif lhs in record['properties'].keys():
            field_value = record['properties'][lhs]
        else:
            raise CQLException()
        return field_value

    except KeyError:
        LOGGER.error("Invalid field name: {}".format(lhs))
        raise CQLException()


def temporal(feature_list, lhs, time_or_period, op):
    """
    Create a temporal filter for the given temporal attribute.

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
    :param feature_list: a list of feature dict set to lookup
                            potential choices for a certain field
    :type feature_list: list

    :return: a comparison expression result
    :rtype: list
    """

    try:
        filtered_feature_list = []

        # perform temporal comparison
        filtered_feature_list = list(
            filter(
                lambda record, op=op, lhs=lhs, time_or_period=time_or_period:
                temporal_filter(record['properties'][lhs], time_or_period, op),
                feature_list
            )
        )
        return filtered_feature_list

    except KeyError:
        LOGGER.error("Invalid field name: {}".format(lhs))
        raise CQLExceptionTemporal()

    except Exception as err:
        LOGGER.error("Invalid 'temporal' operation: {}".format(err))
        raise CQLExceptionTemporal()


def temporal_filter(record_date_time, time_or_period, op):
    """
    Helper function to perform spatial filters on feature set

    :param record_date_time: datetime field value of a feature
    :type record_date_time: :class:`datetime.datetime`
    :param time_or_period: the time instant or time span to use as a filter
    :type time_or_period: :class:`datetime.datetime` or a tuple of two
                            datetimes or a tuple of one datetime and one
                            :class:`datetime.timedelta`
    :param op: the comparison operation
    :type op: str

    :return: a comparison expression result
    :rtype: bool
    """

    d = datetime.strptime(record_date_time, "%Y-%m-%dT%H:%M:%SZ")
    result = None

    # perform before and after operations
    if op in ['BEFORE', 'AFTER']:
        query_date_time = datetime.strptime(
            time_or_period.value, "%Y-%m-%dT%H:%M:%SZ")
        if op == 'BEFORE':
            return d <= query_date_time
        elif op == 'AFTER':
            return d >= query_date_time

    # perform during operation
    elif 'DURING' in op:
        low, high = time_or_period
        low = datetime.strptime(low.value, "%Y-%m-%dT%H:%M:%SZ")
        high = datetime.strptime(high.value, "%Y-%m-%dT%H:%M:%SZ")
        result = d >= low and d <= high
        if 'BEFORE' in op:
            result = d <= low or result
        if 'AFTER' in op:
            result = d >= high or result
        return result

    else:
        raise CQLExceptionTemporalOperator(
            "Invalid temporal operator: {}".format(op))


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

    :return: a comparison expression result
    :rtype: list
    """

    try:
        rhs = shapely.wkt.loads(rhs.value)
        filtered_feature_list = []

        # perform spatial comparison
        filtered_feature_list = list(
            filter(
                lambda record, op=op, lhs=lhs, rhs=rhs:
                spatial_filter(record[lhs]['coordinates'],
                               op, rhs, pattern,
                               distance, units),
                feature_list
            )
        )
        return filtered_feature_list

    except KeyError:
        LOGGER.error("Invalid field name: {}".format(lhs))
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

    :return: a comparison expression result
    :rtype: list
    """

    try:
        filtered_feature_list = []

        bbox = box(minx, miny, maxx, maxy)

        # perform bbox intersection
        filtered_feature_list = list(
            filter(
                lambda record, lhs=lhs:
                spatial_filter(record[lhs]['coordinates'],
                               'INTERSECTS', bbox),
                feature_list
            )
        )
        return filtered_feature_list

    except KeyError:
        LOGGER.error("Invalid field name: {}".format(lhs))
        raise CQLExceptionBBox()

    except Exception as err:
        LOGGER.error("Invalid 'spatial' operation: {}".format(err))
        raise CQLExceptionBBox()


def spatial_filter(coords, op, rhs, pattern=None, distance=None, units=None):
    """
    Helper function to perform spatial filters on feature set

    :param coords: list of coordinates
    :type coords: list
    :param rhs: spatial expression
    :type rhs: geomtry
    :param op: the comparison operation
    :type op: str
    :param pattern: the spatial relation pattern
    :type pattern: str
    :param distance: the distance value
    :type distance: float
    :param units: the units the distance is expressed in
    :type units: str

    :return: a comparison expression result
    :rtype: bool
    """

    # check for object geometry
    shape = Point(coords) if len(coords) == 2 else Polygon(coords[0])

    # return spatial comparison result
    if op == 'RELATE':
        if pattern is None:
            raise CQLExceptionPattern("Invalid relate pattern")
        return shape.relate_pattern(rhs, pattern)

    elif op in ['DWITHIN', 'BEYOND']:
        if units is None or units not in ['meters', 'kilometers']:
            raise CQLExceptionUnits("Invalid distance units: {}".format(units))
        if units == 'meters':
            distance = distance / 1000

        if op == 'DWITHIN':
            return shape.distance(rhs) <= distance
        else:
            return shape.distance(rhs) > distance

    elif op in ['INTERSECTS', 'DISJOINT', 'CONTAINS', 'WITHIN',
                'TOUCHES', 'CROSSES', 'OVERLAPS', 'EQUALS']:
        return getattr(shape, op.lower())(rhs)

    else:
        raise CQLExceptionSpatialOperator(
            "Invalid spatial operator: {}".format(op))


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
        if name in field_name:
            field = name
            return field
        else:
            raise CQLExceptionAttribute("Invalid field value: {}".format(name))

    except Exception as err:
        LOGGER.error(err)
        raise CQLExceptionAttribute()


def literal(value):
    """
    Returns the literal value of the node

    :param value: data value
    :type value: str, int, float

    :return: data value
    :rtype: str, int, float
    """

    return value
