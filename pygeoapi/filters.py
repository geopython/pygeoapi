"""
For evaluating CQL filter queries from Abstract Syntax Tree
"""

import logging
import re

from pygeoapi.exception import (CQLException,
                                CQLExceptionAttribute,
                                CQLExceptionCombination,
                                CQLExceptionLogicalCombinator,
                                CQLExceptionComparison,
                                CQLExceptionBetween, CQLExceptionNull,
                                CQLExceptionIn, CQLExceptionLike,
                                CQLExceptionComparator,
                                CQLExceptionSpatial, CQLExceptionUnits
                                )
from pygeoapi.util import generate_regex
from shapely.geometry import Point, Polygon
import shapely.wkt

LOGGER = logging.getLogger(__name__)


def combine(sub_filters, combination):
    """
    Combine filters using a logical combinator

    :param sub_filters: the filters to combine
    :param combinator: a string: "AND" / "OR"
    :type sub_filters: tuple of multiple sub-filter result

    :return: the combined filter
    :rtype: filtered dict
    """

    try:
        if combination not in ["AND", "OR"]:
            raise CQLExceptionLogicalCombinator(
                "Invalid combination operator: {}".format(combination)
            )

        mapping_list = []
        intersection = []
        union = []
        for row in sub_filters[0]:
            if row in sub_filters[1]:
                intersection.append(row)
            else:
                union.append(row)

        # perform combination operation
        if combination == "AND":
            mapping_list = intersection
        else:
            mapping_list = union + sub_filters[1]

        return mapping_list

    except IndexError as err:
        LOGGER.error("Invalid index {}".format(err))
        raise CQLExceptionCombination()

    except Exception as err2:
        LOGGER.error("Invalid combination operation: {}".format(err2))
        raise CQLExceptionCombination()


def negate(mapping_list, mapping_choices):
    """ Negate a filter, opposing its meaning.

        :param mapping_list: the filter to negate
        :type mapping_list: list
        :param mapping_choices: a list of feature dict set to lookup
                                potential choices for a certain field
        :type mapping_choices: list
        :return: the negated list
        :rtype: list
    """

    mapping_list = list(
        filter(
            lambda record: record not in mapping_list,
            mapping_choices
        )
    )
    return mapping_list


# Comparison operators dictionary
Comparator = {
    "<": "<",
    "<=": "<=",
    ">": ">",
    ">=": ">=",
    "<>": "!=",
    "=": "=="
}


def compare(lhs, rhs, op, mapping_choices=None):
    """ Compare a filter with an expression using a comparison operation

        :param lhs: the field to compare
        :type lhs: string
        :param rhs: the filter expression
        :type rhs: literal
        :param op: a string denoting the operation. one of ``"<"``, ``"<="``,
                   ``">"``, ``">="``, ``"<>"``, ``"="``
        :type op: str
        :param mapping_choices: a list of feature dict set to lookup
                                potential choices for a certain field
        :type mapping_choices: list
        :return: filtered feature set
        :rtype: list
    """

    try:
        if op not in Comparator:
            raise CQLExceptionComparator("Invalid comparison operator: {}".
                                         format(op))

        comp = Comparator[op]
        mapping_list = []
        if comp:
            # perform comparison operation
            mapping_list = list(
                filter(
                    lambda record, lhs=lhs, comp=comp, rhs=rhs:
                    eval(str(get_field_value(record, lhs)) + comp + str(rhs)),
                    mapping_choices
                )
            )

        return mapping_list

    except Exception as err:
        LOGGER.error("Invalid comparison operation: {}".format(err))
        raise CQLExceptionComparison()


def between(lhs, low, high, not_=False, mapping_choices=None):
    """ Create a filter to match elements that have a value within a certain
        range.

        :param lhs: the field to compare
        :type lhs: string
        :param low: the lower value of the range
        :type low: literal
        :param high: the upper value of the range
        :type high: literal
        :param not_: whether the range shall be inclusive (the default) or
                     exclusive
        :type not_: bool
        :param mapping_choices: a list of feature dict set to lookup
                                potential choices for a certain field
        :type mapping_choices: list
        :return: filtered feature set
        :rtype: list
    """

    try:
        mapping_list = []
        # perform between operation
        mapping_list = list(
            filter(
                lambda record, lhs=lhs, low=low, high=high:
                float(get_field_value(record, lhs)) >= low
                and float(get_field_value(record, lhs)) <= high,
                mapping_choices
            )
        )

        # perform negation operation
        if not_:
            mapping_list = negate(mapping_list, mapping_choices)

        return mapping_list

    except Exception as err:
        LOGGER.error("Invalid 'between' operation: {}".format(err))
        raise CQLExceptionBetween()


def like(lhs, rhs, case=False, not_=False, mapping_choices=None):
    """ Create a filter to filter elements according to a string attribute using
        wildcard expressions.

        :param lhs: the field to compare
        :type lhs: string
        :param rhs: the wildcard pattern: a string containing any number of '%'
                    characters as wildcards.
        :type rhs: str
        :param case: whether the lookup shall be done case sensitively or not
        :type case: bool
        :param not_: whether the range shall be inclusive (the default) or
                     exclusive
        :type not_: bool
        :param mapping_choices: a list of feature dict set to lookup
                                potential choices for a certain field
        :type mapping_choices: list
        :return: filtered feature set
        :rtype: list
    """

    try:
        mapping_list = []
        regex = generate_regex(rhs)
        matcher = re.compile(regex)

        # perform like operation
        mapping_list = list(
            filter(
                lambda record, matcher=matcher:
                matcher.search(get_field_value(record, lhs)),
                mapping_choices
            )
        )

        # perform negation operation
        if not_:
            mapping_list = negate(mapping_list, mapping_choices)

        return mapping_list

    except Exception as err:
        LOGGER.error("Invalid 'like' operation: {}".format(err))
        raise CQLExceptionLike()


def contains(lhs, items, not_=False, mapping_choices=None):
    """ Create a filter to match elements attribute to be in a list of choices.

        :param lhs: the field to compare
        :type lhs: string
        :param items: a list of choices
        :type items: list
        :param not_: whether the range shall be inclusive (the default) or
                     exclusive
        :type not_: bool
        :param mapping_choices: a list of feature dict set to lookup
                                potential choices for a certain field
        :type mapping_choices: list
        :return: filtered feature set
        :rtype: list
    """

    try:
        mapping_list = []

        # perform contains operation
        mapping_list = list(
            filter(
                lambda record, lhs=lhs, items=items:
                get_field_value(record, lhs) in items,
                mapping_choices
            )
        )

        # perform negation operation
        if not_:
            mapping_list = negate(mapping_list, mapping_choices)

        return mapping_list

    except Exception as err:
        LOGGER.error("Invalid 'in' operation: {}".format(err))
        raise CQLExceptionIn()


def null(lhs, not_=False, mapping_choices=None):
    """ Create a filter to match elements whose attribute is (not) null

        :param lhs: the field to compare
        :type lhs: string
        :param not_: whether the range shall be inclusive (the default) or
                     exclusive
        :type not_: bool
        :param mapping_choices: a list of feature dict set to lookup
                                potential choices for a certain field
        :type mapping_choices: list
        :return: filtered feature set
        :rtype: list
    """

    try:
        mapping_list = []

        # perform null checking
        mapping_list = list(
            filter(
                lambda record, lhs=lhs:
                ((get_field_value(record, lhs) is not None
                  and get_field_value(record, lhs) == 'null')
                 or get_field_value(record, lhs) is None),
                mapping_choices
            )
        )

        # perform negation operation
        if not_:
            mapping_list = negate(mapping_list, mapping_choices)

        return mapping_list

    except Exception as err:
        LOGGER.error("Invalid 'null' operation: {}".format(err))
        raise CQLExceptionNull()


def get_field_value(record, lhs):
    """ Helper function to get matching field's value from for all the features

        :param lhs: the field name
        :type lhs: string
        :param record: a feature meta-data
        :type record: dict
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


def temporal(lhs, time_or_period, op):  # TODO!!
    """ Create a temporal filter for the given temporal attribute.

        :param lhs: the field to compare
        :type lhs:
        :param time_or_period: the time instant or time span to use as a filter
        :type time_or_period: :class:`datetime.datetime` or a tuple of two
                              datetimes or a tuple of one datetime and one
                              :class:`datetime.timedelta`
        :param op: the comparison operation. one of ``"BEFORE"``,
                   ``"BEFORE OR DURING"``, ``"DURING"``, ``"DURING OR AFTER"``,
                   ``"AFTER"``.
        :type op: str
        :return: a comparison expression result
        :rtype:
    """
    pass


def spatial(mapping_choices, lhs, rhs, op,
            pattern=None, distance=None, units=None):
    """ Create a spatial filter for the given spatial attribute.

        :param lhs: the field to compare
        :type lhs:
        :param rhs: spatial expression
        :type rhs:
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
        :rtype:
    """

    try:
        rhs = shapely.wkt.loads(rhs.value)

        if units and units not in ['meters', 'kilometers']:
            raise CQLExceptionUnits()
        if units == "meters":
            distance = distance / 1000

        # perform spatial comparison
        mapping_list = list(
            filter(
                lambda record, op=op, lhs=lhs, rhs=rhs:
                spatial_filter(record[lhs]['coordinates'],
                               op.lower(), rhs, pattern,
                               distance, units),
                mapping_choices
            )
        )
        return mapping_list

    except CQLExceptionUnits:
        LOGGER.error("Invalid distance unit: {}".format(units))
        raise CQLExceptionSpatial()

    except KeyError:
        LOGGER.error("Invalid field name: {}".format(lhs))
        raise CQLExceptionSpatial()

    except Exception as err:
        LOGGER.error("Invalid 'spatial' operation: {}".format(err))
        raise CQLExceptionSpatial()


def spatial_filter(coords, op, rhs, pattern, distance, units):
    """ Helper function to perform spatial filters on feature set

        :param coords: list of coordinates
        :type coords: list
        :param rhs: spatial expression
        :type rhs:
        :param op: the comparison operation
        :type op: str
        :param pattern: the spatial relation pattern
        :type pattern: str
        :param distance: the distance value
        :type distance: float
        :param units: the units the distance is expressed in
        :type units: str
        :return: a comparison expression result
        :rtype: boolean
    """

    try:
        # check for point objects
        if len(coords) == 2:
            shape = Point(coords)
        # check for polygon objects
        else:
            shape = Polygon(coords[0])

        # return spatial comparison result
        if op == 'relate':
            return shape.relate_pattern(rhs, pattern)
        elif op == 'dwithin':
            return shape.distance(rhs) <= distance
        elif op == 'beyond':
            return shape.distance(rhs) > distance

        return getattr(shape, op)(rhs)

    except Exception as err:
        LOGGER.error(err)
        raise CQLException()


def bbox(lhs, minx, miny, maxx, maxy, crs=None, bboverlaps=True):  # TODO!!
    """ Create a bounding box filter for the given spatial attribute.

        :param lhs: the field to compare
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
        :type lhs:
        :return: a comparison expression result
        :rtype:
    """
    pass


def attribute(name, field_mapping=None):
    """
    Create an attribute lookup expression using a field mapping dictionary.

    :param name: the field filter name
    :type name: str
    :param field_mapping: the dictionary to use as a lookup.
    :type mapping_choices: list of feature dict set

    :return: field name
    :rtype: `string`
    """

    try:
        if name in field_mapping:
            field = name
            return field
        else:
            raise CQLExceptionAttribute("Invalid field value: {}".format(name))

    except CQLExceptionAttribute as err:
        LOGGER.error(err)
        raise CQLExceptionAttribute()


def literal(value):
    """
    Returns the literal value of the node

    :param value: data value
    :type name: str, int, float

    :return: data value
    :rtype: str, int, float
    """

    return value


# OP_TO_FUNC = {
#     "+": add,
#     "-": sub,
#     "*": mul,
#     "/": truediv
# }


def arithmetic(lhs, rhs, op):  # TODO!!
    """ Create an arithmetic filter

        :param lhs: left hand side of the arithmetic expression.
                    either a scalar or a field lookup or another
                    type of expression
        :param rhs: same as `lhs`
        :param op: the arithmetic operation. one of
                    ``"+"``, ``"-"``, ``"*"``, ``"/"``
        :rtype:
    """
    pass
