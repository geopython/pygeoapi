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


class CQLHandler:
    """ CQL Filter Handler """

    def __init__(self, cql_def):
        """
        Initialize object

        :param cql_def: CQL filter definition
        """

        self.cql_expression = cql_def['cql_expression']
        self.feature_set = cql_def['feature_set']

    def cql_filter(self):
        """
        Perform CQL Filter on the feature set

        :returns: list of filtered feature set
        """

        feature_set = self.CQLFilter.cql_filter(self)
        return feature_set

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

        def cql_validation(self):
            """
            Finds the validity of the CQL filter expression
            """

            _ = self.create_ast()

    class CQLEvaluator:
        """ CQL Filter Evaluator """

        def __init__(self, field_mapping, mapping_choices):
            """
            Initialize object

            :param field_mapping: attribute list
            :param mapping_choices: feature set to filter
            """

            self.field_mapping = field_mapping
            self.mapping_choices = mapping_choices

        def to_filter(self, node):
            """
            To translate ECQL Abstract Syntax Tree to query expressions

            :param node: Abstract Syntax Tree nodes

            :returns: list of filtered features
            """
            to_filter = self.to_filter
            # evaluation for Not Condition Predicate Node
            if isinstance(node, NotConditionNode):
                return filters.negate(to_filter(node.sub_node),
                                      self.mapping_choices)

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
                    to_filter(node.lhs),
                    to_filter(node.low),
                    to_filter(node.high),
                    node.not_, self.mapping_choices
                )

            # evaluation for Like Predicate Node
            elif isinstance(node, LikePredicateNode):
                return filters.like(
                    to_filter(node.lhs),
                    to_filter(node.rhs),
                    node.case, node.not_,
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
                    to_filter(node.lhs), node.rhs,
                    node.op, self.mapping_choices
                )

            # evaluation for Spatial Predicate Node
            elif isinstance(node, SpatialPredicateNode):
                return filters.spatial(
                    self.mapping_choices,
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

    class CQLFilter:
        """ CQL Filter Executor """

        def __init__(self):
            """
            Initialize object
            """

            self.CQLParser = self.CQLParser
            self.cql_expression = self.cql_expression
            self.CQLEvaluator = self.CQLEvaluator
            self.feature_set = self.feature_set
            self.CQLFilter = self.CQLFilter

        def cql_filter(self):
            """
            Helper function to perform CQL Filter on the feature set

            :returns: list of filtered feature set
            """

            cql_parser = self.CQLParser(self.cql_expression)
            cql_ast = cql_parser.create_ast()
            field_mapping = list(self.CQLFilter.get_field_mapping(self))

            cql_evaluator = self.CQLEvaluator(field_mapping, self.feature_set)
            feature_set = cql_evaluator.to_filter(cql_ast)

            return feature_set

        def get_field_mapping(self):
            """
            helper function to get a resource's field name

            :param feature_set: ``list`` of features

            :returns: field ``list``
            """

            field_mapping = list(self.feature_set[0].keys())
            field_mapping = field_mapping + (list(self.feature_set[0]
                                                  ['properties'].keys()))

            return field_mapping
