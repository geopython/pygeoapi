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


class CQLExceptionComparisonOperator(CQLException):
    """CQL filter having invalid comparison operator exception"""
    pass


class CQLExceptionAttribute(CQLException):
    """CQL filter having invalid attribute exception"""
    pass


class CQLExceptionLiteral(CQLException):
    """CQL filter having invalid literal exception"""
    pass
