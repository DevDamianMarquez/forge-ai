"""Tests for deterministic constraint evaluation in app.physics.constraints."""

from __future__ import annotations

import pytest

from app.models.physics import Constraint, ConstraintMetric, ConstraintOperator
from app.physics.constraints import evaluate_constraint


def test_constraint_pass_when_output_rpm_within_bound():
    constraint = Constraint(
        name="max-rpm", metric=ConstraintMetric.OUTPUT_RPM, operator=ConstraintOperator.LTE, value=500
    )
    result = evaluate_constraint(constraint, actual_value=400.0)
    assert result.passed is True
    assert result.actual_value == pytest.approx(400.0)


def test_constraint_fail_when_output_rpm_exceeds_bound():
    constraint = Constraint(
        name="max-rpm", metric=ConstraintMetric.OUTPUT_RPM, operator=ConstraintOperator.LTE, value=300
    )
    result = evaluate_constraint(constraint, actual_value=400.0)
    assert result.passed is False


def test_constraint_gte_pass():
    constraint = Constraint(
        name="min-rpm", metric=ConstraintMetric.OUTPUT_RPM, operator=ConstraintOperator.GTE, value=300
    )
    assert evaluate_constraint(constraint, actual_value=400.0).passed is True


def test_constraint_gte_fail():
    constraint = Constraint(
        name="min-rpm", metric=ConstraintMetric.OUTPUT_RPM, operator=ConstraintOperator.GTE, value=500
    )
    assert evaluate_constraint(constraint, actual_value=400.0).passed is False


def test_constraint_eq_pass_and_fail():
    constraint = Constraint(
        name="exact-rpm", metric=ConstraintMetric.OUTPUT_RPM, operator=ConstraintOperator.EQ, value=400
    )
    assert evaluate_constraint(constraint, actual_value=400.0).passed is True
    assert evaluate_constraint(constraint, actual_value=400.0001).passed is False


def test_constraint_on_gear_ratio_metric():
    constraint = Constraint(
        name="min-reduction",
        metric=ConstraintMetric.GEAR_RATIO,
        operator=ConstraintOperator.GTE,
        value=2.0,
    )
    assert evaluate_constraint(constraint, actual_value=3.0).passed is True
