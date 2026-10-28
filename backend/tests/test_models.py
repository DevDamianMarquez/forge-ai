"""Tests for strict Pydantic validation on the physics domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.physics import (
    Constraint,
    ConstraintMetric,
    ConstraintOperator,
    Gear,
    GearConnection,
    GearTrain,
)


def test_gear_rejects_zero_teeth():
    with pytest.raises(ValidationError):
        Gear(id="g1", teeth=0)


def test_gear_rejects_negative_teeth():
    with pytest.raises(ValidationError):
        Gear(id="g1", teeth=-5)


def test_gear_accepts_optional_label():
    gear = Gear(id="g1", teeth=20, label="input gear")
    assert gear.label == "input gear"


def test_gear_label_defaults_to_none():
    gear = Gear(id="g1", teeth=20)
    assert gear.label is None


def test_gear_train_rejects_zero_rpm():
    driver = Gear(id="driver", teeth=20)
    driven = Gear(id="driven", teeth=60)
    with pytest.raises(ValidationError):
        GearTrain(input_rpm=0, connections=[GearConnection(driver=driver, driven=driven)])


def test_gear_train_rejects_negative_rpm():
    driver = Gear(id="driver", teeth=20)
    driven = Gear(id="driven", teeth=60)
    with pytest.raises(ValidationError):
        GearTrain(input_rpm=-100, connections=[GearConnection(driver=driver, driven=driven)])


def test_gear_train_rejects_empty_connections():
    with pytest.raises(ValidationError):
        GearTrain(input_rpm=1200, connections=[])


def test_gear_connection_rejects_self_mesh():
    gear = Gear(id="same", teeth=20)
    with pytest.raises(ValidationError):
        GearConnection(driver=gear, driven=gear)


def test_constraint_requires_value():
    with pytest.raises(ValidationError):
        Constraint(
            name="max-output-rpm",
            metric=ConstraintMetric.OUTPUT_RPM,
            operator=ConstraintOperator.LTE,
        )


def test_constraint_rejects_unknown_metric():
    with pytest.raises(ValidationError):
        Constraint(name="bad", metric="torque", operator=ConstraintOperator.LTE, value=100)


def test_constraint_rejects_unknown_operator():
    with pytest.raises(ValidationError):
        Constraint(
            name="bad", metric=ConstraintMetric.OUTPUT_RPM, operator="approximately", value=100
        )
