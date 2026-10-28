"""The one FORGE tool Muse Spark is allowed to call, and its schema.

The tool wraps the existing ``run_gear_train_experiment`` deterministic
physics function (Milestone 1) -- no calculation logic is duplicated here.
Its parameters schema is generated directly from ``GearTrainExperimentRequest``,
the same Pydantic model the ``POST /api/v1/experiments/gear-train`` endpoint
already validates against, so there is exactly one schema for this tool's
shape, not two hand-maintained ones.
"""

from __future__ import annotations

from typing import Any

from app.api.experiments import GearTrainExperimentRequest

GEAR_TRAIN_EXPERIMENT_TOOL_NAME = "run_gear_train_experiment"

_TOOL_DESCRIPTION = (
    "Run FORGE's deterministic physics calculation for an idealized external "
    "spur-gear transmission and return the authoritative result. Supports "
    "only: ordered transmission stages (each one external gear mesh), "
    "consecutive stages assumed to be rigidly coupled on a shared shaft, "
    "positive input RPM, and simple numeric constraints on output RPM or "
    "overall gear ratio. This is the only source of real output RPM, gear "
    "ratio, direction, or constraint-pass/fail values -- never estimate "
    "these yourself; always call this tool to get them."
)


def gear_train_experiment_tool_schema() -> dict[str, Any]:
    """The OpenAI/Muse function-tool definition for FORGE's one physics tool."""
    return {
        "type": "function",
        "function": {
            "name": GEAR_TRAIN_EXPERIMENT_TOOL_NAME,
            "description": _TOOL_DESCRIPTION,
            "parameters": GearTrainExperimentRequest.model_json_schema(),
        },
    }
