"""Deterministic constraint evaluation.

Compares an already-computed numeric value against a Constraint's numeric
target using plain operator comparison. No model inference or natural-
language interpretation is involved anywhere in this module.
"""

from __future__ import annotations

import operator as _operator
from typing import Callable

from app.models.physics import Constraint, ConstraintOperator, ConstraintResult

_COMPARATORS: dict[ConstraintOperator, Callable[[float, float], bool]] = {
    ConstraintOperator.LTE: _operator.le,
    ConstraintOperator.GTE: _operator.ge,
    ConstraintOperator.LT: _operator.lt,
    ConstraintOperator.GT: _operator.gt,
    ConstraintOperator.EQ: _operator.eq,
}


def evaluate_constraint(constraint: Constraint, actual_value: float) -> ConstraintResult:
    """Deterministically compare actual_value against the constraint's numeric target."""
    comparator = _COMPARATORS[constraint.operator]
    passed = comparator(actual_value, constraint.value)
    message = (
        f"{constraint.metric.value} {constraint.operator.value} {constraint.value}: "
        f"actual={actual_value} -> {'PASS' if passed else 'FAIL'}"
    )
    return ConstraintResult(
        constraint=constraint,
        actual_value=actual_value,
        passed=passed,
        message=message,
    )
