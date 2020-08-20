"""
Defining custom exceptions that might be raised due to the
implementation of CQL filter expressions in pygeoapi

"""


class CQLException(Exception):
    """CQL filter generic exception"""
    pass


class CQLExceptionFilterLang(Exception):
    """CQL filter lang exception"""
    pass


class CQLExceptionEmptyList(CQLException):
    """CQL filter encounters empty feature list exception"""
    pass


class CQLExceptionSubFilters(CQLException):
    """CQL sub-filter exception"""
    pass


class CQLExceptionLogicalCombinator(CQLException):
    """CQL filter having invalid logical combinator exception"""
    pass


class CQLExceptionCombination(CQLException):
    """CQL filter having invalid combination operation"""
    pass


class CQLExceptionComparator(CQLException):
    """CQL filter having invalid comparison operator exception"""
    pass


class CQLExceptionComparison(CQLException):
    """CQL filter having invalid comparison operation"""
    pass


class CQLExceptionBetween(CQLException):
    """CQL filter having invalid between operation"""
    pass


class CQLExceptionNull(CQLException):
    """CQL filter having invalid null operation"""
    pass


class CQLExceptionIn(CQLException):
    """CQL filter having invalid IN operation"""
    pass


class CQLExceptionLike(CQLException):
    """CQL filter having invalid LIKE operation"""
    pass


class CQLExceptionSpatial(CQLException):
    """CQL filter having invalid SPATIAL operation"""
    pass


class CQLExceptionSpatialOperator(CQLException):
    """CQL filter having invalid spatial operator"""
    pass


class CQLExceptionBBox(CQLException):
    """CQL filter having invalid bbox operation"""
    pass


class CQLExceptionUnits(CQLException):
    """CQL filter having invalid distance units"""
    pass


class CQLExceptionPattern(CQLException):
    """CQL filter having invalid relate pattern"""
    pass


class CQLExceptionTemporal(CQLException):
    """CQL filter having invalid TEMPORAL operation"""
    pass


class CQLExceptionTemporalOperator(CQLException):
    """CQL filter having invalid temporal operator"""
    pass


class CQLExceptionAttribute(CQLException):
    """CQL filter having invalid attribute exception"""
    pass


class CQLExceptionLiteral(CQLException):
    """CQL filter having invalid literal exception"""
    pass
