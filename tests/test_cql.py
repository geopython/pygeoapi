""" Functional unit test cases for CQL query filters"""

import os
import json
import pytest
from pycql.ast import (
    CombinationConditionNode, ComparisonPredicateNode,
    BetweenPredicateNode, LikePredicateNode,
    InPredicateNode, NullPredicateNode, TemporalPredicateNode,
    SpatialPredicateNode, BBoxPredicateNode, AttributeExpression,
    LiteralExpression
)
from pycql.values import Time, Geometry
from pygeoapi.cql import CQLHandler
from pygeoapi.filters import combine, compare, between, like,\
    contains, is_null, temporal, spatial, bbox, literal, attribute


def get_test_file_path(filename):
    """helper function to open test file safely"""

    if os.path.isfile(filename):
        return filename
    else:
        return 'tests/{}'.format(filename)


# test file taken for CQL filter testing purpose
path = get_test_file_path('data/ne_110m_lakes.geojson')


def get_ast(cql_filter):
    """helper function to create ast of CQL filter query"""

    cql_ast = CQLHandler.CQLParser(cql_filter).create_ast()
    return cql_ast


@pytest.fixture
def get_collection():
    """get all the feature collection"""

    if os.path.exists(path):
        with open(path) as src:
            data = json.loads(src.read())
    else:
        data = {
            'type': 'FeatureCollection',
            'features': []}
    return data


@pytest.fixture
def get_feature_list(get_collection):
    """get features list from collection"""

    return get_collection['features']


@pytest.fixture
def get_field_list(get_feature_list):
    """get the list of field names in features"""

    field_name = list(get_feature_list[0].keys())
    field_name = field_name + (list(get_feature_list[0]
                                    ['properties'].keys()))
    return field_name


def test_feature_collection(get_collection):
    """
    Assertions for generated feature collection

    :param get_collection: feature collection list
    """

    assert isinstance(get_collection, dict)
    assert 'type' in get_collection
    assert 'features' in get_collection

    assert get_collection['type'] == 'FeatureCollection'
    features = get_collection['features']
    assert isinstance(features, list)

    if features:
        for feature in features:
            assert 'id' in feature
            assert 'properties' in feature


# assertion for COMPARISON predicate node in ast
def test_attribute_eq_literal(get_feature_list, get_field_list):
    """
    Assertions for '=' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('id = 1')
    assert cql_ast == ComparisonPredicateNode(
        AttributeExpression('id'),
        LiteralExpression(1),
        '='
    )
    result = compare_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 1


def test_attribute_lt_literal(get_feature_list, get_field_list):
    """
    Assertions for '<' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('id < 5')
    assert cql_ast == ComparisonPredicateNode(
        AttributeExpression('id'),
        LiteralExpression(5.0),
        '<'
    )
    result = compare_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 5


def test_attribute_lte_literal(get_feature_list, get_field_list):
    """
    Assertions for '<=' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('id <= 5')
    assert cql_ast == ComparisonPredicateNode(
        AttributeExpression('id'),
        LiteralExpression(5.0),
        '<='
    )
    result = compare_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 6


def test_attribute_gt_literal(get_feature_list, get_field_list):
    """
    Assertions for '>' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('id > 5')
    assert cql_ast == ComparisonPredicateNode(
        AttributeExpression('id'),
        LiteralExpression(5.0),
        '>'
    )
    result = compare_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 19


def test_attribute_gte_literal(get_feature_list, get_field_list):
    """
    Assertions for '>=' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('id >= 5')
    assert cql_ast == ComparisonPredicateNode(
        AttributeExpression('id'),
        LiteralExpression(5.0),
        '>='
    )
    result = compare_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 20


def test_attribute_ne_literal(get_feature_list, get_field_list):
    """
    Assertions for '<>' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('id <> 5')
    assert cql_ast == ComparisonPredicateNode(
        AttributeExpression('id'),
        LiteralExpression(5),
        '<>'
    )
    result = compare_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 24


def compare_test(cql_ast, get_feature_list, get_field_list):
    """
    Helper function to perform assertion on 'comparision' operations

    :param cql_ast: ast of cql query filter
    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    lhs = cql_ast.lhs
    rhs = cql_ast.rhs
    op = cql_ast.op
    assert op in [">", "<", "=", ">=", "<=", "<>"]
    assert rhs is not None
    assert lhs is not None
    assert lhs.name in get_field_list

    result = compare(
        get_feature_list, attribute(lhs.name, get_field_list),
        literal(rhs.value), op)
    assert isinstance(result, list)
    if len(result) > 0:
        for feature in result:
            assert isinstance(feature, dict)
            assert feature in get_feature_list
    return result


# assertion for BETWEEN predicate node in ast
def test_attribute_between(get_feature_list, get_field_list):
    """
    Assertions for 'between' operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('id BETWEEN 2 AND 5')
    assert cql_ast == BetweenPredicateNode(
        AttributeExpression('id'),
        LiteralExpression(2),
        LiteralExpression(5),
        False,
    )
    result = between_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 4


def test_attribute_not_between(get_feature_list, get_field_list):
    """
    Assertions for 'not between' operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('id NOT BETWEEN 2 AND 5')
    assert cql_ast == BetweenPredicateNode(
        AttributeExpression('id'),
        LiteralExpression(2),
        LiteralExpression(5),
        True,
    )
    result = between_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 21


def between_test(cql_ast, get_feature_list, get_field_list):
    """
    Helper function to perform assertion on 'between' operations

    :param cql_ast: ast of cql query filter
    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    lhs = cql_ast.lhs
    low = cql_ast.low
    high = cql_ast.high
    assert low is not None
    assert high is not None
    assert lhs is not None
    assert lhs.name in get_field_list

    result = between(
        get_feature_list, attribute(lhs.name, get_field_list),
        literal(low.value), literal(high.value), cql_ast.not_)
    assert isinstance(result, list)
    if len(result) > 0:
        for feature in result:
            assert isinstance(feature, dict)
            assert feature in get_feature_list
    return result


# assertion for LIKE predicate node in ast
def test_string_like(get_feature_list, get_field_list):
    """
    Assertions for 'like' operation with case sensitivity

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('name LIKE "lake%"')
    assert cql_ast == LikePredicateNode(
        AttributeExpression('name'),
        LiteralExpression('lake%'),
        True,
        False,
    )
    result = like_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 0


def test_string_ilike(get_feature_list, get_field_list):
    """
    Assertions for 'like' operations with no case sensitivity

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('name ILIKE "lake%"')
    assert cql_ast == LikePredicateNode(
        AttributeExpression('name'),
        LiteralExpression('lake%'),
        False,
        False,
    )
    result = like_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 14


def test_string_not_like(get_feature_list, get_field_list):
    """
    Assertions for 'not like' operation with case sensitivity

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('name NOT LIKE "lake%"')
    assert cql_ast == LikePredicateNode(
        AttributeExpression('name'),
        LiteralExpression('lake%'),
        True,
        True,
    )
    result = like_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 25


def test_string_not_ilike(get_feature_list, get_field_list):
    """
    Assertions for 'not like' operation with no case sensitivity

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('name NOT ILIKE "lake%"')
    assert cql_ast == LikePredicateNode(
        AttributeExpression('name'),
        LiteralExpression('lake%'),
        False,
        True,
    )
    result = like_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 11


def like_test(cql_ast, get_feature_list, get_field_list):
    """
    Helper function to perform assertion on 'like' operations

    :param cql_ast: ast of cql query filter
    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    lhs = cql_ast.lhs
    rhs = cql_ast.rhs
    assert rhs is not None
    assert lhs is not None
    assert lhs.name in get_field_list

    result = like(
        get_feature_list, attribute(lhs.name, get_field_list),
        literal(rhs.value), cql_ast.case, cql_ast.not_)
    assert isinstance(result, list)
    if len(result) > 0:
        for feature in result:
            assert isinstance(feature, dict)
            assert feature in get_feature_list
    return result


# assertion for IN predicate node in ast
def test_attribute_in_list(get_feature_list, get_field_list):
    """
    Assertions for 'in' operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast("name IN ('Lake Baikal','Lake Huron',"
                      " 'Lake Onega','Lake Victoria')")
    assert cql_ast == InPredicateNode(
        AttributeExpression('name'), [
            LiteralExpression('Lake Baikal'),
            LiteralExpression('Lake Huron'),
            LiteralExpression('Lake Onega'),
            LiteralExpression('Lake Victoria'),
        ],
        False
    )
    result = in_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 4


def test_attribute_not_in_list(get_feature_list, get_field_list):
    """
    Assertions for 'not in' operation with no case sensitivity

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast("name NOT IN ('Lake Baikal','Lake Huron',"
                      "'Lake Onega','Lake Victoria')")
    assert cql_ast == InPredicateNode(
        AttributeExpression('name'), [
            LiteralExpression('Lake Baikal'),
            LiteralExpression('Lake Huron'),
            LiteralExpression('Lake Onega'),
            LiteralExpression('Lake Victoria'),
        ],
        True
    )
    result = in_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 21


def in_test(cql_ast, get_feature_list, get_field_list):
    """
    Helper function to perform assertion on 'in' operations

    :param cql_ast: ast of cql query filter
    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    lhs = cql_ast.lhs
    sub_nodes = cql_ast.sub_nodes
    assert sub_nodes is not None
    assert lhs is not None
    assert lhs.name in get_field_list

    result = contains(
        get_feature_list, attribute(lhs.name, get_field_list),
        [literal(sub_node.value) for sub_node in cql_ast.sub_nodes],
        cql_ast.not_)
    assert isinstance(result, list)
    if len(result) > 0:
        for feature in result:
            assert isinstance(feature, dict)
            assert feature in get_feature_list
    return result


# assertion for IS NULL predicate node in ast
def test_attribute_is_null(get_feature_list, get_field_list):
    """
    Assertions for 'is null' operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('id IS NULL')
    assert cql_ast == NullPredicateNode(
        AttributeExpression('id'), False
    )
    result = null_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 0


def test_attribute_is_not_null(get_feature_list, get_field_list):
    """
    Assertions for 'is not null' operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('id IS NOT NULL')
    assert cql_ast == NullPredicateNode(
        AttributeExpression('id'), True
    )
    result = null_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 25


def null_test(cql_ast, get_feature_list, get_field_list):
    """
    Helper function to perform assertion on 'null' operations

    :param cql_ast: ast of cql query filter
    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    lhs = cql_ast.lhs
    assert lhs is not None
    assert lhs.name in get_field_list
    result = is_null(
        get_feature_list, attribute(lhs.name, get_field_list),
        cql_ast.not_)

    assert isinstance(result, list)
    if len(result) > 0:
        for feature in result:
            assert isinstance(feature, dict)
            assert feature in get_feature_list
    return result


# assertion for COMBINATION node in ast
def test_attribute_and(get_feature_list, get_field_list):
    """
    Assertions for 'and' combination operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('id<5 AND name LIKE "Lake%"')
    assert cql_ast.op in ["AND", "OR"]

    expr1 = ComparisonPredicateNode(AttributeExpression('id'),
                                    LiteralExpression(5), '<')
    expr2 = LikePredicateNode(AttributeExpression('name'),
                              LiteralExpression('Lake%'),
                              True, False)
    result1 = compare_test(expr1, get_feature_list, get_field_list)
    result2 = like_test(expr2, get_feature_list, get_field_list)

    assert isinstance(result1, list)
    for feature in result1:
        assert isinstance(feature, dict)
        assert feature in get_feature_list

    assert isinstance(result2, list)
    for feature in result2:
        assert isinstance(feature, dict)
        assert feature in get_feature_list

    assert cql_ast == CombinationConditionNode(expr1, expr2, 'AND')
    sub_filters = (result1, result2)
    assert isinstance(sub_filters, tuple)
    assert len(sub_filters) == 2

    result = combine(sub_filters, cql_ast.op)
    assert isinstance(result, list)
    if len(result) > 0:
        for feature in result:
            assert isinstance(feature, dict)
            assert feature in get_feature_list

    assert len(result) == 2


# assertion for TEMPORAL predicate node in ast
def test_attribute_before(get_feature_list, get_field_list):
    """
    Assertions for 'before' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('datetime BEFORE 2000-01-01T00:00:01Z')
    assert cql_ast == TemporalPredicateNode(
        AttributeExpression('datetime'),
        Time('2000-01-01T00:00:01Z'),
        'BEFORE'
    )


def test_attribute_before_or_during_dt_dt(get_feature_list, get_field_list):
    """
    Assertions for 'before or during' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('datetime BEFORE OR DURING '
                      '2000-01-01T00:00:00Z / 2003-01-01T00:00:01Z')
    assert cql_ast == TemporalPredicateNode(
        AttributeExpression('datetime'),
        (Time('2000-01-01T00:00:00Z'), Time('2003-01-01T00:00:01Z')),
        'BEFORE OR DURING'
    )


def test_attribute_after(get_feature_list, get_field_list):
    """
    Assertions for 'after' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('datetime AFTER 2000-01-01T00:00:01Z')
    assert cql_ast == TemporalPredicateNode(
        AttributeExpression('datetime'),
        Time('2000-01-01T00:00:01Z'),
        'AFTER')


# the test data has no datetime field to perform this unit test
def temporal_test(cql_ast, get_feature_list, get_field_list):
    """
    Helper function to perform assertion on 'temporal' operations

    :param cql_ast: ast of cql query filter
    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    lhs = cql_ast.lhs
    rhs = cql_ast.rhs
    op = cql_ast.op
    assert op in ["BEFORE", "BEFORE OR DURING", "DURING",
                  "DURING OR AFTER", "AFTER"]
    assert rhs is not None
    assert lhs is not None
    assert lhs.name in get_field_list

    result = temporal(
        get_feature_list, attribute(lhs.name, get_field_list),
        literal(rhs.value), op)
    assert isinstance(result, list)
    if len(result) > 0:
        for feature in result:
            assert isinstance(feature, dict)
            assert feature in get_feature_list
    return result


# assertion for SPATIAL predicate node in ast
def test_geometry_intersects(get_feature_list, get_field_list):
    """
    Assertions for 'intersect' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('INTERSECTS(geometry,POINT(-75 45))')
    assert cql_ast == SpatialPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(Geometry('POINT(-75 45)')),
        'INTERSECTS')
    result = spatial_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 0


def test_geometry_disjoint(get_feature_list, get_field_list):
    """
    Assertions for 'disjoint' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('DISJOINT(geometry,POINT(-75 45))')
    assert cql_ast == SpatialPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(Geometry('POINT(-75 45)')),
        'DISJOINT')
    result = spatial_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 25


def test_geometry_contains(get_feature_list, get_field_list):
    """
    Assertions for 'contains' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('CONTAINS(geometry,POINT(-75 45))')
    assert cql_ast == SpatialPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(Geometry('POINT(-75 45)')),
        'CONTAINS')
    result = spatial_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 0


def test_geometry_within(get_feature_list, get_field_list):
    """
    Assertions for 'within' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('WITHIN(geometry,POINT(-75 45))')
    assert cql_ast == SpatialPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(Geometry('POINT(-75 45)')),
        'WITHIN')
    result = spatial_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 0


def test_geometry_touches(get_feature_list, get_field_list):
    """
    Assertions for 'touches' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('TOUCHES(geometry,POINT(-75 45))')
    assert cql_ast == SpatialPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(Geometry('POINT(-75 45)')),
        'TOUCHES')
    result = spatial_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 0


def test_geometry_crosses(get_feature_list, get_field_list):
    """
    Assertions for 'crosses' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('CROSSES(geometry,POINT(-75 45))')
    assert cql_ast == SpatialPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(Geometry('POINT(-75 45)')),
        'CROSSES')
    result = spatial_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 0


def test_geometry_overlaps(get_feature_list, get_field_list):
    """
    Assertions for 'overlaps' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('OVERLAPS(geometry,POINT(-75 45))')
    assert cql_ast == SpatialPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(Geometry('POINT(-75 45)')),
        'OVERLAPS')
    result = spatial_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 0


def test_geometry_equals(get_feature_list, get_field_list):
    """
    Assertions for 'equals' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('EQUALS(geometry,POINT(-75 45))')
    assert cql_ast == SpatialPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(Geometry('POINT(-75 45)')),
        'EQUALS')
    result = spatial_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 0


def test_geometry_relate(get_feature_list, get_field_list):
    """
    Assertions for 'relate' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """
    cql_ast = get_ast('RELATE(geometry,POINT(-85 75), "T*****FF*")')
    assert cql_ast == SpatialPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(Geometry('POINT(-85 75)')), 'RELATE',
        'T*****FF*')
    result = spatial_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 0


def test_geometry_dwithin(get_feature_list, get_field_list):
    """
    Assertions for 'dwithin' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('DWITHIN(geometry,POINT(-85 75),10,kilometers)')
    spatial_node = SpatialPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(Geometry('POINT(-85 75)')),
        'DWITHIN', None, LiteralExpression(10.0),
        'kilometers')
    assert cql_ast == spatial_node
    result = spatial_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 0


def test_geometry_beyond(get_feature_list, get_field_list):
    """
    Assertions for 'beyond' comparison operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('BEYOND(geometry,POINT(-85 75),10,meters)')
    spatial_node = SpatialPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(Geometry('POINT(-85 75)')),
        'BEYOND', None, LiteralExpression(10.0), 'meters')
    assert cql_ast == spatial_node
    result = spatial_test(cql_ast, get_feature_list, get_field_list)
    assert len(result) == 25


def spatial_test(cql_ast, get_feature_list, get_field_list):
    """
    Helper function to perform assertion on 'spatial' operation

    :param cql_ast: ast of cql query filter
    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    lhs = cql_ast.lhs
    rhs = cql_ast.rhs
    op = cql_ast.op
    assert op in ["INTERSECTS", "DISJOINT", "CONTAINS", "WITHIN",
                  "TOUCHES", "CROSSES", "OVERLAPS", "EQUALS", "RELATE",
                  "DWITHIN", "BEYOND"]
    assert rhs is not None
    assert lhs is not None
    assert lhs.name in get_field_list
    distance = None
    if cql_ast.distance:
        distance = cql_ast.distance.value

    result = spatial(get_feature_list,
                     attribute(lhs.name, get_field_list),
                     literal(rhs.value), op,
                     pattern=cql_ast.pattern,
                     distance=distance,
                     units=cql_ast.units)
    assert isinstance(result, list)
    if len(result) > 0:
        for feature in result:
            assert isinstance(feature, dict)
            assert feature in get_feature_list
    return result


# BBox prediacte
def test_bbox_simple(get_feature_list, get_field_list):
    """
    Assertions for 'bbox' intersection operation

    :param get_feature_list: feature collection list
    :param get_field_list: feature field names
    """

    cql_ast = get_ast('BBOX(geometry, -90, 40, -60, 45)')
    assert cql_ast == BBoxPredicateNode(
        AttributeExpression('geometry'),
        LiteralExpression(-90),
        LiteralExpression(40),
        LiteralExpression(-60),
        LiteralExpression(45),
    )
    lhs = cql_ast.lhs
    minx = cql_ast.minx
    miny = cql_ast.miny
    maxx = cql_ast.maxx
    maxy = cql_ast.maxy
    assert lhs is not None
    assert minx is not None
    assert miny is not None
    assert maxx is not None
    assert maxy is not None
    assert lhs.name in get_field_list

    result = bbox(get_feature_list,
                  attribute(lhs.name, get_field_list),
                  literal(minx.value), literal(miny.value),
                  literal(maxx.value), literal(maxy.value))
    assert isinstance(result, list)
    if len(result) > 0:
        for feature in result:
            assert isinstance(feature, dict)
            assert feature in get_feature_list
    assert len(result) == 4
