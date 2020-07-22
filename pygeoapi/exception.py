"""
Defining custom exceptions that might be raised due to the
implementation of CQL filter expressions in pygeoapi

"""


class CQLException(Exception):
    """CQL filter generic exception"""
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
    """CQL filter having invalid caomparison operation"""
    pass


class CQLExceptionAttribute(CQLException):
    """CQL filter having invalid attribute exception"""
    pass


class CQLExceptionLiteral(CQLException):
    """CQL filter having invalid literal exception"""
    pass
