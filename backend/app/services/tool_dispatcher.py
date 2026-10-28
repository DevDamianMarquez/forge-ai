"""A tiny, explicit, allowlisted dispatcher for tools Muse Spark may call.

No ``eval()``, no dynamic imports, no arbitrary code execution. Exactly one
physics tool is allowlisted for Milestone 2A. Dispatch always goes through
``run_gear_train_experiment`` -- the same deterministic function the rest of
FORGE (and the HTTP endpoint) uses -- never through anything Muse writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.api.experiments import GearTrainExperimentRequest
from app.models.physics import ExperimentResult
from app.physics.experiments import run_gear_train_experiment
from app.services.forge_tools import GEAR_TRAIN_EXPERIMENT_TOOL_NAME


class UnknownToolError(ValueError):
    """Raised when Muse requests a tool name FORGE does not allowlist."""


class InvalidToolArgumentsError(ValueError):
    """Raised when Muse's tool arguments fail validation against the tool's schema."""


@dataclass(frozen=True)
class ToolExecution:
    """One executed tool call: its name, validated arguments, and real result."""

    tool_name: str
    arguments: dict[str, Any]
    result: ExperimentResult


def dispatch_tool_call(tool_name: str, arguments: dict[str, Any]) -> ToolExecution:
    """Validate and execute one allowlisted FORGE tool call, or raise.

    Only ``GEAR_TRAIN_EXPERIMENT_TOOL_NAME`` is allowlisted. Arguments are
    validated through the exact Pydantic model the HTTP endpoint uses before
    anything is executed; invalid arguments never reach the physics layer.
    """
    if tool_name != GEAR_TRAIN_EXPERIMENT_TOOL_NAME:
        raise UnknownToolError(f"Unknown or disallowed tool: {tool_name!r}")

    try:
        request = GearTrainExperimentRequest.model_validate(arguments)
    except ValidationError as exc:
        raise InvalidToolArgumentsError(str(exc)) from exc

    result = run_gear_train_experiment(request.train, request.constraints)
    return ToolExecution(
        tool_name=tool_name,
        arguments=request.model_dump(mode="json"),
        result=result,
    )
