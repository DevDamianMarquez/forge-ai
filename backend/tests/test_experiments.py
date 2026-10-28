"""Tests for the end-to-end deterministic experiment orchestrator."""

from __future__ import annotations

import pytest

from app.models.physics import (
    Constraint,
    ConstraintMetric,
    ConstraintOperator,
    ExperimentStatus,
    Gear,
    GearConnection,
    GearTrain,
)
from app.physics.experiments import run_gear_train_experiment


def _canonical_train() -> GearTrain:
    driver = Gear(id="driver", teeth=20, label="input gear")
    driven = Gear(id="driven", teeth=60, label="output gear")
    return GearTrain(input_rpm=1200, connections=[GearConnection(driver=driver, driven=driven)])


def test_canonical_experiment_output_rpm_and_ratio():
    result = run_gear_train_experiment(_canonical_train())

    assert result.status == ExperimentStatus.SUCCESS
    assert result.result == pytest.approx(400.0)
    assert result.unit == "rpm"
    assert result.metrics["gear_ratio"] == pytest.approx(3.0)
    assert result.tool == "compute_gear_train_output_rpm"
    assert result.inputs["input_rpm"] == 1200
    assert result.error is None


def test_experiment_constraint_pass():
    constraint = Constraint(
        name="max-output-rpm",
        metric=ConstraintMetric.OUTPUT_RPM,
        operator=ConstraintOperator.LTE,
        value=500,
    )
    result = run_gear_train_experiment(_canonical_train(), constraints=[constraint])

    assert len(result.constraint_results) == 1
    assert result.constraint_results[0].passed is True
    assert result.constraint_results[0].actual_value == pytest.approx(400.0)


def test_experiment_constraint_fail():
    constraint = Constraint(
        name="max-output-rpm",
        metric=ConstraintMetric.OUTPUT_RPM,
        operator=ConstraintOperator.LTE,
        value=300,
    )
    result = run_gear_train_experiment(_canonical_train(), constraints=[constraint])

    assert result.constraint_results[0].passed is False


def test_experiment_multi_stage_train():
    stage1 = GearConnection(driver=Gear(id="d1", teeth=20), driven=Gear(id="n1", teeth=60))
    stage2 = GearConnection(driver=Gear(id="d2", teeth=15), driven=Gear(id="n2", teeth=45))
    train = GearTrain(input_rpm=1200, connections=[stage1, stage2])

    result = run_gear_train_experiment(train)

    assert result.status == ExperimentStatus.SUCCESS
    assert result.result == pytest.approx(1200 * 20 / 60 * 15 / 45)
    assert result.metrics["gear_ratio"] == pytest.approx(9.0)


def test_experiment_reports_error_status_for_invalid_runtime_state():
    # GearTrain's own validation prevents this through normal construction;
    # model_construct bypasses it here only to exercise
    # run_gear_train_experiment's defensive error-reporting path.
    bad_driver = Gear.model_construct(id="d", teeth=0)
    good_driven = Gear(id="n", teeth=60)
    connection = GearConnection.model_construct(driver=bad_driver, driven=good_driven)
    train = GearTrain.model_construct(input_rpm=1200, input_direction=1, connections=[connection])

    result = run_gear_train_experiment(train)

    assert result.status == ExperimentStatus.ERROR
    assert result.error is not None
    assert result.result is None
