"""Pydantic domain models for FORGE's deterministic physics engine (Milestone 1).

Scope: idealized external spur gear transmissions only. See the module-level
limitations note in ``app.physics.gears`` for exactly what is and isn't modeled.
These models hold data only; all physical calculation lives in ``app.physics``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Gear(BaseModel):
    """A single spur gear."""

    id: str = Field(..., min_length=1, description="Unique identifier for this gear within a train.")
    teeth: int = Field(..., gt=0, description="Number of teeth. Must be a positive integer.")
    label: str | None = Field(default=None, description="Optional human-readable label.")


class GearConnection(BaseModel):
    """One external mesh: a driver gear turning a driven gear.

    Also referred to as a "gear pair" in the architecture docs -- one model
    covers both names since they describe the same thing.
    """

    driver: Gear
    driven: Gear

    @model_validator(mode="after")
    def _driver_and_driven_must_differ(self) -> "GearConnection":
        if self.driver.id == self.driven.id:
            raise ValueError(
                "driver and driven gears must be different gears (a gear cannot mesh with itself)"
            )
        return self


class GearTrain(BaseModel):
    """An ordered sequence of transmission stages driven by one input shaft.

    Each ``GearConnection`` in ``connections`` represents one independent
    external-gear transmission stage -- i.e. one actual gear mesh (driver
    teeth meshing driven teeth). Consecutive stages are assumed to be
    rigidly coupled through a shared shaft: stage *i*'s driven gear and
    stage *i+1*'s driver gear are assumed to be fixed to the same shaft and
    therefore spin at the same RPM in the same direction. That is why the
    computed output RPM of one stage becomes the input RPM of the next
    stage, and why a shared-shaft coupling does not itself reverse
    rotational direction -- only an actual mesh (one per ``GearConnection``)
    does.

    ``connections[0]`` is driven directly by the input shaft at ``input_rpm``.

    This shared-shaft relationship is an *assumption* at Milestone 1: FORGE
    does not model shafts explicitly, and nothing in this schema represents
    or validates that consecutive stages are actually coupled this way. The
    caller is responsible for supplying stages in valid, physically
    consistent power-flow order.
    """

    input_rpm: float = Field(..., gt=0, description="Input shaft speed in RPM. Must be positive.")
    input_direction: Literal[1, -1] = Field(
        default=1, description="Rotational direction of the input shaft: 1 or -1."
    )
    connections: list[GearConnection] = Field(
        ...,
        min_length=1,
        description=(
            "Ordered transmission stages from the input shaft to the output shaft. "
            "Each stage is one external gear mesh; consecutive stages are assumed "
            "to share a rigid shaft (see class docstring), not to mesh with each other."
        ),
    )


class ConstraintMetric(str, Enum):
    """Which computed value a constraint checks."""

    OUTPUT_RPM = "output_rpm"
    GEAR_RATIO = "gear_ratio"


class ConstraintOperator(str, Enum):
    """A deterministic numeric comparison operator."""

    LTE = "lte"
    GTE = "gte"
    LT = "lt"
    GT = "gt"
    EQ = "eq"


class Constraint(BaseModel):
    """A single pass/fail numeric constraint on a computed metric."""

    name: str = Field(..., min_length=1)
    metric: ConstraintMetric
    operator: ConstraintOperator
    value: float


class ConstraintResult(BaseModel):
    """The outcome of evaluating one Constraint against an actual computed value."""

    constraint: Constraint
    actual_value: float
    passed: bool
    message: str


class ExperimentStatus(str, Enum):
    """Whether a deterministic experiment executed successfully."""

    SUCCESS = "success"
    ERROR = "error"


class ExperimentResult(BaseModel):
    """The structured, auditable result of running one deterministic physics tool.

    Identifies which tool ran, its exact inputs, its numeric result (and unit),
    whether it succeeded, and any constraint evaluations -- everything the
    future AI agent layer needs without ever having computed the number itself.
    """

    tool: str
    inputs: dict[str, Any]
    result: float | None = None
    unit: str | None = None
    status: ExperimentStatus
    error: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    constraint_results: list[ConstraintResult] = Field(default_factory=list)
