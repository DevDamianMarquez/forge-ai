"""The one deterministic "tool" that produces a gear-train ExperimentResult.

This is the function the future AI agent layer will call to get a real
physical measurement for a gear train. It never asks a model to produce the
numbers -- it only orchestrates the pure functions in ``app.physics.gears``
and ``app.physics.train``, and packages their output into an auditable
ExperimentResult.
"""

from __future__ import annotations

from app.models.physics import (
    Constraint,
    ConstraintMetric,
    ExperimentResult,
    ExperimentStatus,
    GearTrain,
)
from app.physics.constraints import evaluate_constraint
from app.physics.train import (
    compute_gear_train_output_direction,
    compute_gear_train_output_rpm,
    compute_gear_train_ratio,
)

_TOOL_NAME = "compute_gear_train_output_rpm"


def run_gear_train_experiment(
    train: GearTrain,
    constraints: list[Constraint] | None = None,
) -> ExperimentResult:
    """Run the deterministic gear-train experiment and evaluate any constraints.

    Computes output RPM, overall ratio, and output direction for `train`,
    then evaluates each constraint against the metric it names. GearTrain's
    own validation already rejects invalid teeth/RPM before this is called,
    so the error path below only guards against unforeseen runtime failures
    in the physics functions themselves.
    """
    inputs = train.model_dump()

    try:
        output_rpm = compute_gear_train_output_rpm(train)
        ratio = compute_gear_train_ratio(train)
        direction = compute_gear_train_output_direction(train)
    except ValueError as exc:
        return ExperimentResult(
            tool=_TOOL_NAME,
            inputs=inputs,
            status=ExperimentStatus.ERROR,
            error=str(exc),
        )

    metrics = {
        ConstraintMetric.OUTPUT_RPM.value: output_rpm,
        ConstraintMetric.GEAR_RATIO.value: ratio,
        "output_direction": float(direction),
    }

    constraint_results = [
        evaluate_constraint(constraint, metrics[constraint.metric.value])
        for constraint in (constraints or [])
    ]

    return ExperimentResult(
        tool=_TOOL_NAME,
        inputs=inputs,
        result=output_rpm,
        unit="rpm",
        status=ExperimentStatus.SUCCESS,
        metrics=metrics,
        constraint_results=constraint_results,
    )
