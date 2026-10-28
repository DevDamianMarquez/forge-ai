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


class Shaft(BaseModel):
    """A rigid shaft. Every gear mounted on the same shaft turns together --
    same RPM, same direction -- which is what lets a compound gear train
    exist (Milestone 1's GearTrain already assumed this; PhysicalSystem
    makes the shaft itself an explicit, separate object instead of an
    assumption baked into stage ordering).
    """

    id: str = Field(..., min_length=1, description="Unique identifier for this shaft.")
    label: str | None = Field(default=None, description="Optional human-readable label.")


class SystemGear(BaseModel):
    """A gear in an explicit PhysicalSystem topology, mounted on one shaft.

    Distinct from ``Gear`` (the low-level unit inside a compiled
    ``GearConnection``/``GearTrain``): a ``SystemGear`` additionally knows
    which shaft it is mounted on, which is exactly the information
    ``app.physics.topology`` needs to determine the transmission path.
    """

    id: str = Field(..., min_length=1, description="Unique identifier for this gear.")
    teeth: int = Field(..., gt=0, description="Number of teeth. Must be a positive integer.")
    shaft_id: str = Field(..., min_length=1, description="The shaft this gear is mounted on.")
    label: str | None = Field(default=None, description="Optional human-readable label.")


class GearMesh(BaseModel):
    """One external mesh between two gears, identified by id.

    Order does not matter: a mesh between "a" and "b" is the same mesh as
    one between "b" and "a" -- PhysicalSystem's validation treats them as
    duplicates of each other, not two different meshes.
    """

    gear_a_id: str = Field(..., min_length=1)
    gear_b_id: str = Field(..., min_length=1)


class PhysicalSystem(BaseModel):
    """An explicit physical topology: shafts, the gears mounted on them, and
    which gears mesh.

    This is the higher-level representation SAM/Muse will eventually
    populate from perception. It carries no physics itself:
    ``app.physics.topology`` compiles it into the existing Milestone 1
    ``GearTrain``, and the existing deterministic physics engine
    (``app.physics.experiments``) produces the actual numbers from that --
    topology code owns topology, the physics engine owns physics.

    Milestone 3A scope: a single, unbranched, acyclic transmission path
    only. Branches, multiple possible paths, disconnected outputs, and
    cycles are rejected by the compiler rather than guessed at (see
    ``app.physics.topology.UnsupportedTopologyError``).
    """

    shafts: list[Shaft] = Field(..., min_length=1)
    gears: list[SystemGear] = Field(..., min_length=1)
    meshes: list[GearMesh] = Field(..., min_length=1)
    input_shaft_id: str = Field(..., min_length=1, description="Where input RPM is applied.")
    input_rpm: float = Field(..., gt=0, description="Input shaft speed in RPM. Must be positive.")
    output_shaft_id: str | None = Field(
        default=None,
        description=(
            "Where the transmission path ends. If omitted, the compiler infers "
            "it, but only if the input shaft is itself one end of an "
            "unambiguous chain -- otherwise it is rejected as ambiguous."
        ),
    )
    constraints: list[Constraint] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_topology_shape(self) -> "PhysicalSystem":
        shaft_ids = [shaft.id for shaft in self.shafts]
        if len(shaft_ids) != len(set(shaft_ids)):
            raise ValueError("shaft ids must be unique")

        gear_ids = [gear.id for gear in self.gears]
        if len(gear_ids) != len(set(gear_ids)):
            raise ValueError("gear ids must be unique")

        shaft_id_set = set(shaft_ids)
        gear_by_id = {gear.id: gear for gear in self.gears}

        for gear in self.gears:
            if gear.shaft_id not in shaft_id_set:
                raise ValueError(f"gear {gear.id!r} references unknown shaft {gear.shaft_id!r}")

        if self.input_shaft_id not in shaft_id_set:
            raise ValueError(f"input_shaft_id {self.input_shaft_id!r} does not exist")

        if self.output_shaft_id is not None and self.output_shaft_id not in shaft_id_set:
            raise ValueError(f"output_shaft_id {self.output_shaft_id!r} does not exist")

        seen_pairs: set[frozenset[str]] = set()
        for mesh in self.meshes:
            if mesh.gear_a_id not in gear_by_id:
                raise ValueError(f"mesh references unknown gear {mesh.gear_a_id!r}")
            if mesh.gear_b_id not in gear_by_id:
                raise ValueError(f"mesh references unknown gear {mesh.gear_b_id!r}")
            if mesh.gear_a_id == mesh.gear_b_id:
                raise ValueError(f"gear {mesh.gear_a_id!r} cannot mesh with itself")

            gear_a = gear_by_id[mesh.gear_a_id]
            gear_b = gear_by_id[mesh.gear_b_id]
            if gear_a.shaft_id == gear_b.shaft_id:
                raise ValueError(
                    f"gears {gear_a.id!r} and {gear_b.id!r} are both on shaft "
                    f"{gear_a.shaft_id!r} and cannot mesh with each other"
                )

            pair = frozenset((mesh.gear_a_id, mesh.gear_b_id))
            if pair in seen_pairs:
                raise ValueError(
                    f"duplicate mesh between {mesh.gear_a_id!r} and {mesh.gear_b_id!r}"
                )
            seen_pairs.add(pair)

        return self


class CompiledTopology(BaseModel):
    """What the topology compiler determined before handing off to the physics engine.

    Small and specific on purpose -- enough to explain which path was
    selected and why, not a general provenance framework.
    """

    input_shaft_id: str
    output_shaft_id: str
    shaft_path: list[str] = Field(
        description="Ordered shaft ids from the input shaft to the output shaft."
    )
    gear_meshes_used: list[GearMesh] = Field(
        description="The actual meshes, in path order, that formed the transmission path."
    )
    gear_train: GearTrain = Field(
        description="The compiled Milestone 1 GearTrain -- its connections are the stages."
    )


class PhysicalSystemExperimentResult(BaseModel):
    """The full result of running an experiment on an explicit PhysicalSystem:
    how its topology was compiled, plus the deterministic ExperimentResult
    produced by the unchanged Milestone 1 physics engine.
    """

    topology: CompiledTopology
    experiment: ExperimentResult
