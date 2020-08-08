"""
For implementing CQL filter expressions in pygeoapi.
Acts as an abstract layer between the data providers
and CQL filter.

"""

from pycql import parse
from pycql.ast import (
    NotConditionNode, CombinationConditionNode, ComparisonPredicateNode,
    BetweenPredicateNode, LikePredicateNode, ArithmeticExpressionNode,
    InPredicateNode, NullPredicateNode, TemporalPredicateNode,
    SpatialPredicateNode, BBoxPredicateNode, AttributeExpression,
    LiteralExpression
)
import pygeoapi.filters as filters


class CQLParser():
    """ CQL Filter Parser """

    def __init__(self, cql_def):
        """
        Initialize object

        :param cql_def: CQL filter definition

        :returns: string expression
        """

        self.cql_expression = cql_def['cql_expression']

    def create_ast(self):
        """
        Create an Abstract Syntax Tree of the CQL filter expression
        by parsing the expression

        :returns: Abstract Syntax Tree
        """

        ast = parse(self.cql_expression)
        return ast

    def cql_validation(self):
        """
        Finds the validity of the CQL filter expression
        """

        _ = self.create_ast()


class CQLFilterEvaluator():
    """ CQL Filter Evaluator """

    def __init__(self, cql_def):
        """
        Initialize object

        :param cql_def: CQL filter definition

        :returns: string expression
        """

        self.field_mapping = cql_def['field_mapping']
        self.mapping_choices = cql_def['mapping_choices']

    def to_filter(self, node):
        """
        To translate ECQL Abstract Syntax Tree to query expressions

        :param node: Abstract Syntax Tree nodes

        :returns: list of filtered features
        """
        to_filter = self.to_filter
        # evaluation for Not Condition Predicate Node
        if isinstance(node, NotConditionNode):
            return filters.negate(to_filter(node.sub_node))

        # evaluation for Combination Condition Predicate Node
        elif isinstance(node, CombinationConditionNode):
            return filters.combine(
                (to_filter(node.lhs), to_filter(node.rhs)), node.op
            )

        # evaluation for Comparison Predicate Node
        elif isinstance(node, ComparisonPredicateNode):
            return filters.compare(
                to_filter(node.lhs), to_filter(node.rhs), node.op,
                self.mapping_choices
            )

        # evaluation for Between Predicate Node
        elif isinstance(node, BetweenPredicateNode):
            return filters.between(
                to_filter(node.lhs), to_filter(node.low), to_filter(node.high),
                node.not_, self.mapping_choices
            )

        # evaluation for Between Predicate Node
        elif isinstance(node, BetweenPredicateNode):
            return filters.between(
                to_filter(node.lhs), to_filter(node.low), to_filter(node.high),
                node.not_
            )

        # evaluation for Like Predicate Node
        elif isinstance(node, LikePredicateNode):
            return filters.like(
                to_filter(node.lhs), to_filter(node.rhs), node.case, node.not_,
                self.mapping_choices

            )

        # evaluation for In Predicate Node
        elif isinstance(node, InPredicateNode):
            return filters.contains(
                to_filter(node.lhs), [
                    to_filter(sub_node) for sub_node in node.sub_nodes
                ], node.not_, self.mapping_choices
            )

        # evaluation for Null Predicate Node
        elif isinstance(node, NullPredicateNode):
            return filters.null(
                to_filter(node.lhs), node.not_, self.mapping_choices
            )

        # evaluation for Temporal Predicate Node
        elif isinstance(node, TemporalPredicateNode):
            return filters.temporal(
                to_filter(node.lhs), node.rhs, node.op
            )

        # evaluation for Spatial Predicate Node
        elif isinstance(node, SpatialPredicateNode):
            return filters.spatial(
                to_filter(node.lhs), to_filter(node.rhs), node.op,
                to_filter(node.pattern),
                to_filter(node.distance),
                to_filter(node.units)
            )

        # evaluation for BBox Predicate Node
        elif isinstance(node, BBoxPredicateNode):
            return filters.bbox(
                to_filter(node.lhs),
                to_filter(node.minx),
                to_filter(node.miny),
                to_filter(node.maxx),
                to_filter(node.maxy),
                to_filter(node.crs)
            )

        # evaluation for Attribute Expression Node
        elif isinstance(node, AttributeExpression):
            return filters.attribute(node.name, self.field_mapping)

        # evaluation for Literal Expression Node
        elif isinstance(node, LiteralExpression):
            return node.value

        # evaluation for Arithmetic Expression Node
        elif isinstance(node, ArithmeticExpressionNode):
            return filters.arithmetic(
                to_filter(node.lhs), to_filter(node.rhs), node.op
            )

        # return the Node
        return node
