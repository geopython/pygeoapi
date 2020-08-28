"""
For implementing CQL filter expressions in pygeoapi.
Acts as an abstract layer between the data providers
and CQL filter.

"""

import logging
from pycql import parse
from pycql.ast import (
    NotConditionNode, CombinationConditionNode, ComparisonPredicateNode,
    BetweenPredicateNode, LikePredicateNode, InPredicateNode,
    NullPredicateNode, TemporalPredicateNode, SpatialPredicateNode,
    BBoxPredicateNode, AttributeExpression, LiteralExpression
)
from pygeoapi.cql_exception import CQLException
import pygeoapi.cql_filters as cql_filters
import pygeoapi.cql_where_clauses as cql_where_clauses

LOGGER = logging.getLogger(__name__)


class CQLHandler:
    """ CQL Filter Handler """

    def __init__(self, cql_def):
        """
        Initialize object

        :param cql_def: CQL filter definition
        """

        self.cql_expression = cql_def.get('cql_expression', None)
        self.feature_list = cql_def.get('feature_list', None)
        self.field_list = cql_def.get('field_list', None)

    def cql_filter(self):
        """
        Perform CQL Filter on the feature list

        :returns: list of filtered feature list
        """

        feature_list = self.CQLFilter.get_cql_filtered_list(self)
        return feature_list

    def cql_where_clause(self):
        """
        Perform CQL Filter on the feature list

        :returns: list of filtered feature list
        """

        where_clause = self.CQLFilter.get_cql_where_clause(self)
        return where_clause

    def cql_validation(self):
        """
        Finds the validity of the CQL filter expression
        """

        cql_ast = self.CQLParser.create_ast(self)
        if cql_ast is None:
            raise CQLException()

    class CQLParser:
        """ CQL Filter Parser """

        def __init__(self, cql_expression):
            """
            Initialize object

            :param cql_expression: CQL filter expression
            """

            self.cql_expression = cql_expression

        def create_ast(self):
            """
            Create an Abstract Syntax Tree of the CQL filter expression
            by parsing the expression

            :returns: Abstract Syntax Tree
            """

            cql_ast = parse(self.cql_expression)
            return cql_ast

    class CQLEvaluator:
        """ CQL Filter Evaluator """

        def __init__(self, field_list, feature_list, provider):
            """
            Initialize object

            :param field_list: attribute list
            :param feature_list: feature list to filter
            """

            self.field_list = field_list
            self.feature_list = feature_list
            self.provider = provider
            self.method = cql_where_clauses\
                if self.provider in ['SQLite', 'PostGreSQL']\
                else cql_filters

        def to_filter(self, node):
            """
            To translate ECQL Abstract Syntax Tree to query expressions

            :param node: Abstract Syntax Tree nodes

            :returns: list of filtered features
            """
            to_filter = self.to_filter
            # evaluation for Not Condition Predicate Node
            if isinstance(node, NotConditionNode):
                return self.method.negate(
                    self.feature_list,
                    to_filter(node.sub_node)
                )

            # evaluation for Combination Condition Predicate Node
            elif isinstance(node, CombinationConditionNode):
                return self.method.combine(
                    (to_filter(node.lhs), to_filter(node.rhs)),
                    node.op
                )

            # evaluation for Comparison Predicate Node
            elif isinstance(node, ComparisonPredicateNode):
                return self.method.compare(
                    self.feature_list,
                    to_filter(node.lhs),
                    to_filter(node.rhs),
                    node.op
                )

            # evaluation for Between Predicate Node
            elif isinstance(node, BetweenPredicateNode):
                return self.method.between(
                    self.feature_list,
                    to_filter(node.lhs),
                    to_filter(node.low),
                    to_filter(node.high),
                    node.not_
                )

            # evaluation for Like Predicate Node
            elif isinstance(node, LikePredicateNode):
                return self.method.like(
                    self.feature_list,
                    to_filter(node.lhs),
                    to_filter(node.rhs),
                    node.case, node.not_
                )

            # evaluation for In Predicate Node
            elif isinstance(node, InPredicateNode):
                return self.method.contains(
                    self.feature_list,
                    to_filter(node.lhs),
                    [to_filter(sub_node)
                     for sub_node in node.sub_nodes],
                    node.not_
                )

            # evaluation for Null Predicate Node
            elif isinstance(node, NullPredicateNode):
                return self.method.is_null(
                    self.feature_list,
                    to_filter(node.lhs),
                    node.not_
                )

            # evaluation for Temporal Predicate Node
            elif isinstance(node, TemporalPredicateNode):
                return self.method.temporal(
                    self.feature_list,
                    to_filter(node.lhs),
                    node.rhs,
                    node.op
                )

            # evaluation for Spatial Predicate Node
            elif isinstance(node, SpatialPredicateNode):
                return self.method.spatial(
                    self.feature_list,
                    to_filter(node.lhs),
                    to_filter(node.rhs),
                    node.op,
                    to_filter(node.pattern),
                    to_filter(node.distance),
                    to_filter(node.units)
                )

            # evaluation for BBox Predicate Node
            elif isinstance(node, BBoxPredicateNode):
                return self.method.bbox(
                    self.feature_list,
                    to_filter(node.lhs),
                    to_filter(node.minx),
                    to_filter(node.miny),
                    to_filter(node.maxx),
                    to_filter(node.maxy),
                    to_filter(node.crs),
                )

            # evaluation for Attribute Expression Node
            elif isinstance(node, AttributeExpression):
                return self.method.attribute(node.name, self.field_list)

            # evaluation for Literal Expression Node
            elif isinstance(node, LiteralExpression):
                return node.value

            # return the Node
            return node

    class CQLFilter:
        """ CQL Filter Executor """

        def __init__(self):
            """
            Initialize object
            """

            self.CQLParser = self.CQLParser
            self.cql_expression = self.cql_expression
            self.CQLEvaluator = self.CQLEvaluator
            self.feature_list = self.feature_list
            self.field_list = self.field_list
            self.CQLFilter = self.CQLFilter

        def get_field_list(self):
            """
            helper function to get a resource's field name

            :param feature_list: ``list`` of features

            :returns: field ``list``
            """
            if self.field_list:
                return [x.lower() for x in self.field_list]
            field_list = list(self.feature_list[0].keys())
            field_list = field_list + (list(self.feature_list[0]
                                            ['properties'].keys()))
            return field_list

        def get_cql_evaluation(self, provider):
            """
            Helper function to evaluate CQL Filter depending on provider

            :returns: evaluated result
            """

            try:
                cql_parser = self.CQLParser(self.cql_expression)
                cql_ast = cql_parser.create_ast()
                if cql_ast is None:
                    raise CQLException()

                field_list = list(self.CQLFilter.get_field_list(self))
                cql_evaluator = self.CQLEvaluator(field_list,
                                                  self.feature_list,
                                                  provider)
                result = cql_evaluator.to_filter(cql_ast)
                return result

            except Exception as err:
                LOGGER.error(err)
                raise CQLException(err)

        def get_cql_filtered_list(self):
            """
            Helper function to perform CQL Filter on the feature list

            :returns: list of filtered feature list
            """
            filtered_feature_list = self.CQLFilter.\
                get_cql_evaluation(self, ['CSV', 'GeoJSON'])
            return filtered_feature_list

        def get_cql_where_clause(self):
            """
            Helper function to get where clause for provider

            :returns: string where clause
            """

            cql_where_clause = self.CQLFilter.\
                get_cql_evaluation(self, 'SQLite')
            return cql_where_clause
