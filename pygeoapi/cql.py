"""
For implementing CQL filter expressions in pygeoapi.
Acts as an abstract layer between the data providers
and CQL filter.

"""

from pycql import parse
from pycql.ast import (
    NotConditionNode, CombinationConditionNode, ComparisonPredicateNode,
    BetweenPredicateNode, LikePredicateNode, InPredicateNode,
    NullPredicateNode, TemporalPredicateNode, SpatialPredicateNode,
    BBoxPredicateNode, AttributeExpression, LiteralExpression
)
import pygeoapi.filters as filters


class CQLHandler:
    """ CQL Filter Handler """

    def __init__(self, cql_def):
        """
        Initialize object

        :param cql_def: CQL filter definition
        """

        if 'cql_expression' in cql_def.keys():
            self.cql_expression = cql_def['cql_expression']
        if 'feature_list' in cql_def.keys():
            self.feature_list = cql_def['feature_list']

    def cql_filter(self):
        """
        Perform CQL Filter on the feature list

        :returns: list of filtered feature list
        """

        feature_list = self.CQLFilter.cql_filter(self)
        return feature_list

    def cql_validation(self):
        """
        Finds the validity of the CQL filter expression
        """

        _ = self.CQLParser.create_ast(self)

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

        def __init__(self, field_list, feature_list):
            """
            Initialize object

            :param field_list: attribute list
            :param feature_list: feature list to filter
            """

            self.field_list = field_list
            self.feature_list = feature_list

        def to_filter(self, node):
            """
            To translate ECQL Abstract Syntax Tree to query expressions

            :param node: Abstract Syntax Tree nodes

            :returns: list of filtered features
            """
            to_filter = self.to_filter
            # evaluation for Not Condition Predicate Node
            if isinstance(node, NotConditionNode):
                return filters.negate(self.feature_list,
                                      to_filter(node.sub_node)
                                      )

            # evaluation for Combination Condition Predicate Node
            elif isinstance(node, CombinationConditionNode):
                return filters.combine(
                    (to_filter(node.lhs), to_filter(node.rhs)),
                    node.op
                )

            # evaluation for Comparison Predicate Node
            elif isinstance(node, ComparisonPredicateNode):
                return filters.compare(self.feature_list,
                                       to_filter(node.lhs),
                                       to_filter(node.rhs),
                                       node.op
                                       )

            # evaluation for Between Predicate Node
            elif isinstance(node, BetweenPredicateNode):
                return filters.between(self.feature_list,
                                       to_filter(node.lhs),
                                       to_filter(node.low),
                                       to_filter(node.high),
                                       node.not_
                                       )

            # evaluation for Like Predicate Node
            elif isinstance(node, LikePredicateNode):
                return filters.like(self.feature_list,
                                    to_filter(node.lhs),
                                    to_filter(node.rhs),
                                    node.case, node.not_
                                    )

            # evaluation for In Predicate Node
            elif isinstance(node, InPredicateNode):
                return filters.contains(self.feature_list,
                                        to_filter(node.lhs), [
                                            to_filter(sub_node)
                                            for sub_node in node.sub_nodes
                                        ], node.not_
                                        )

            # evaluation for Null Predicate Node
            elif isinstance(node, NullPredicateNode):
                return filters.is_null(self.feature_list,
                                       to_filter(node.lhs),
                                       node.not_
                                       )

            # evaluation for Temporal Predicate Node
            elif isinstance(node, TemporalPredicateNode):
                return filters.temporal(self.feature_list,
                                        to_filter(node.lhs),
                                        node.rhs, node.op
                                        )

            # evaluation for Spatial Predicate Node
            elif isinstance(node, SpatialPredicateNode):
                return filters.spatial(
                    self.feature_list,
                    to_filter(node.lhs), to_filter(node.rhs), node.op,
                    to_filter(node.pattern),
                    to_filter(node.distance),
                    to_filter(node.units)
                )

            # evaluation for BBox Predicate Node
            elif isinstance(node, BBoxPredicateNode):
                return filters.bbox(
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
                return filters.attribute(node.name, self.field_list)

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
            self.CQLFilter = self.CQLFilter

        def cql_filter(self):
            """
            Helper function to perform CQL Filter on the feature list

            :returns: list of filtered feature list
            """

            cql_parser = self.CQLParser(self.cql_expression)
            cql_ast = cql_parser.create_ast()
            field_list = list(self.CQLFilter.get_field_list(self))

            cql_evaluator = self.CQLEvaluator(field_list, self.feature_list)
            feature_list = cql_evaluator.to_filter(cql_ast)

            return feature_list

        def get_field_list(self):
            """
            helper function to get a resource's field name

            :param feature_list: ``list`` of features

            :returns: field ``list``
            """

            field_list = list(self.feature_list[0].keys())
            field_list = field_list + (list(self.feature_list[0]
                                            ['properties'].keys()))

            return field_list
