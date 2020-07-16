from pycql.ast import (
    NotConditionNode, CombinationConditionNode, ComparisonPredicateNode,
    BetweenPredicateNode, LikePredicateNode, ArithmeticExpressionNode,
    InPredicateNode, NullPredicateNode, TemporalPredicateNode,
    SpatialPredicateNode, BBoxPredicateNode, AttributeExpression,
    LiteralExpression
)
import pygeoapi.filters as filters


class FilterEvaluator(object):
    def __init__(self, field_mapping=None, mapping_choices=None):
        self.field_mapping = field_mapping
        self.mapping_choices = mapping_choices

    # recursive call for filter evaluation
    def to_filter(self, node):
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
                self.mapping_choices, self.field_mapping
            )

        # evaluation for Between Predicate Node
        elif isinstance(node, BetweenPredicateNode):
            return filters.between(
                to_filter(node.lhs), to_filter(node.low), to_filter(node.high),
                node.not_
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
                to_filter(node.lhs), node.not_
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


def to_filter(ast, field_mapping=None, mapping_choices=None):
    """ Helper function to translate ECQL AST to Django Query expressions.

        :param ast: the abstract syntax tree
        :param field_mapping: a dict mapping from the filter name
        :param mapping_choices: a dict mapping field lookups to choices.
        :type ast: :class:`Node`
        :returns: a query dict
        :rtype: dict
    """
    return FilterEvaluator(field_mapping, mapping_choices).to_filter(ast)
