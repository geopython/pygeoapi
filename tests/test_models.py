# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2024 Francesco Bartoli
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.pytest_plugin import register_fixture

from pygeoapi.models.provider.base import GeospatialDataType
from pygeoapi.models.cql import (CQLModel, ComparisonPredicate,
                                 ScalarExpression, SpatialPredicate,
                                 TemporalPredicate, AndExpression,
                                 Between, EqExpression, ScalarOperands,
                                 IntersectsExpression, SpatialOperands)


@register_fixture
class CQLModelFactory(ModelFactory[CQLModel]):
    ...


@register_fixture
class GeospatialDataTypeFactory(ModelFactory[GeospatialDataType]):
    ...


@register_fixture
class BetweenModelFactory(ModelFactory[Between]):
    ...


@register_fixture
class EqExpressionModelFactory(ModelFactory[EqExpression]):
    ...


@register_fixture
class IntersectsExpressionModelFactory(ModelFactory[IntersectsExpression]):
    ...


def test_cql_model(cql_model_factory: CQLModelFactory) -> None:
    cql_model_instance = cql_model_factory.build()
    assert isinstance(cql_model_instance, CQLModel)
    assert cql_model_instance.dict()
    assert type(cql_model_instance.__root__) in [
        ComparisonPredicate, SpatialPredicate, TemporalPredicate, AndExpression
    ]


def test_provider_base_geospatial_data_type(
        geospatial_data_type_factory: GeospatialDataTypeFactory) -> None:
    gdt_instance = geospatial_data_type_factory.build()
    assert gdt_instance.dict()
    assert isinstance(gdt_instance, GeospatialDataType)


def test_between_model(between_model_factory: BetweenModelFactory) -> None:
    between_model_instance = between_model_factory.build()
    assert isinstance(between_model_instance, Between)
    assert between_model_instance.dict()
    assert type(between_model_instance.lower) is ScalarExpression
    assert type(between_model_instance.upper) is ScalarExpression


def test_eq_expression_model(
        eq_expression_model_factory: EqExpressionModelFactory) -> None:
    eqexpr_model_instance = eq_expression_model_factory.build()
    assert isinstance(eqexpr_model_instance, EqExpression)
    assert eqexpr_model_instance.dict()
    assert type(eqexpr_model_instance.eq) is ScalarOperands


def test_intersects_expression_model(
        intersects_expression_model_factory: IntersectsExpressionModelFactory) -> None:  # noqa
    intersectsexpr_model_instance = intersects_expression_model_factory.build()
    assert isinstance(intersectsexpr_model_instance, IntersectsExpression)
    assert intersectsexpr_model_instance.dict()
    assert type(intersectsexpr_model_instance.intersects) is SpatialOperands
