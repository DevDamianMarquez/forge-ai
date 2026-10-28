"""Deterministic orchestration: PerceptionRequest -> PhysicalPipelineResult.

Coordinates three already-existing layers without reimplementing any of
them: a ``PerceptionProvider`` (perception), ``build_physical_system`` (the
evidence boundary), and ``run_physical_system_experiment`` (topology +
physics). This module owns none of that logic -- it only calls into it, in
order, and records what happened at each stage so a future UI can show the
whole pipeline, not just a final number. No Muse, no Meta, no network, no
physics or topology formulas live here.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models.perception import PerceptionRequest, PerceptionResult, PhysicalSystemBuildResult
from app.models.physics import PhysicalSystemExperimentResult
from app.perception.builder import build_physical_system
from app.perception.providers.base import PerceptionProvider
from app.physics.topology import run_physical_system_experiment


class PipelineStage(str, Enum):
    """The stages of the deterministic perception-to-physics pipeline."""

    PERCEPTION = "perception"
    MODEL_BUILD = "model_build"
    TOPOLOGY = "topology"
    EXPERIMENT = "experiment"


class PipelineTraceEntry(BaseModel):
    """One externally meaningful pipeline action or result.

    Deliberately holds only a stage, a coarse status, and a short
    human-readable message -- never chain-of-thought or hidden reasoning.
    """

    stage: PipelineStage
    status: str  # "ok" | "refused"
    message: str


class PhysicalPipelineResult(BaseModel):
    """The full outcome of running the deterministic pipeline for one request.

    ``experiment`` is populated only when every earlier stage succeeded --
    if the evidence boundary refuses, there is no PhysicalSystem and
    therefore no physics evidence, by construction.
    """

    status: str  # "completed" | "refused_at_model_build"
    perception: PerceptionResult
    build_result: PhysicalSystemBuildResult
    experiment: PhysicalSystemExperimentResult | None = None
    trace: list[PipelineTraceEntry] = Field(default_factory=list)


def run_physical_pipeline(
    provider: PerceptionProvider, request: PerceptionRequest
) -> PhysicalPipelineResult:
    """Run the full deterministic PerceptionRequest -> ExperimentResult pipeline.

    Delegates every piece of domain logic: perception to ``provider``, the
    evidence boundary to ``build_physical_system``, and topology + physics
    to ``run_physical_system_experiment``. This function performs no
    physics, no topology, and no perception validation itself -- it only
    sequences those three calls and records a trace of what happened.
    """
    trace: list[PipelineTraceEntry] = []

    perception = provider.analyze(request)
    trace.append(
        PipelineTraceEntry(
            stage=PipelineStage.PERCEPTION,
            status="ok",
            message=(
                f"Provider produced {len(perception.gears)} gear(s), "
                f"{len(perception.shafts)} shaft(s), {len(perception.meshes)} mesh(es)."
            ),
        )
    )

    build_result = build_physical_system(perception)
    if build_result.physical_system is None:
        trace.append(
            PipelineTraceEntry(
                stage=PipelineStage.MODEL_BUILD,
                status="refused",
                message=(
                    f"Evidence boundary refused: {len(build_result.issues)} unresolved "
                    "issue(s); no PhysicalSystem was built."
                ),
            )
        )
        return PhysicalPipelineResult(
            status="refused_at_model_build",
            perception=perception,
            build_result=build_result,
            experiment=None,
            trace=trace,
        )

    trace.append(
        PipelineTraceEntry(
            stage=PipelineStage.MODEL_BUILD,
            status="ok",
            message="All required observations confirmed; PhysicalSystem built.",
        )
    )

    experiment = run_physical_system_experiment(build_result.physical_system)

    trace.append(
        PipelineTraceEntry(
            stage=PipelineStage.TOPOLOGY,
            status="ok",
            message=(
                f"Compiled {experiment.topology.input_shaft_id} -> "
                f"{experiment.topology.output_shaft_id} using "
                f"{len(experiment.topology.gear_meshes_used)} mesh(es)."
            ),
        )
    )
    trace.append(
        PipelineTraceEntry(
            stage=PipelineStage.EXPERIMENT,
            status="ok",
            message=f"Deterministic result: output_rpm={experiment.experiment.result}.",
        )
    )

    return PhysicalPipelineResult(
        status="completed",
        perception=perception,
        build_result=build_result,
        experiment=experiment,
        trace=trace,
    )
