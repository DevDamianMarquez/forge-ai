"""The Milestone 2A tool-call loop: Muse Spark <-> FORGE's deterministic physics tool.

Muse may decide an experiment is needed, choose the one allowed tool, supply
arguments, and interpret the result -- but every physical number in the
final result comes from ``app.physics``, never from Muse. This loop is
bounded on two independent axes: ``MAX_TOOL_ROUNDS`` (how many times Muse is
asked for a turn) and ``MAX_TOOL_CALLS`` (how many tool calls may actually
execute in total, regardless of how many rounds or how many calls Muse
packs into a single response). It does not retry, replan, or run
autonomously; it is exactly the loop described in Milestone 2A, nothing more.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from app.models.physics import ExperimentResult
from app.services.forge_tools import gear_train_experiment_tool_schema
from app.services.meta_model import (
    MuseSparkClient,
    build_assistant_tool_call_message,
    build_tool_result_message,
)
from app.services.tool_dispatcher import (
    InvalidToolArgumentsError,
    UnknownToolError,
    dispatch_tool_call,
)

MAX_TOOL_ROUNDS = 2
MAX_TOOL_CALLS = 2
"""Hard upper bound on total tool executions across the whole analysis,
regardless of how Muse groups them into responses or rounds."""

FORGE_SYSTEM_PROMPT = (
    "You are FORGE's reasoning layer for mechanical transmission systems. "
    "For any physical calculation -- output RPM, gear ratio, direction, or a "
    "constraint check -- you must call the provided tool; never estimate or "
    "invent a physical measurement yourself. Treat a tool's result as the "
    "authoritative evidence for the values it returns, and never claim a "
    "value was verified unless a tool actually returned it. If the available "
    "tools cannot verify part of the objective, say so plainly instead of "
    "guessing. Current scope: idealized external spur-gear transmissions only."
)


@dataclass(frozen=True)
class ActionTraceEntry:
    """One observable, attempted tool call -- for a future UI trace.

    Deliberately holds only structured facts: round, tool name, the
    arguments Muse requested, and either a real ExperimentResult (when
    ``status == "success"``) or a structured error message (when
    ``status == "error"``, e.g. unknown tool, invalid arguments, or the
    MAX_TOOL_CALLS limit) -- never Muse's chain-of-thought or any private
    reasoning trace.
    """

    round_number: int
    tool_name: str
    status: Literal["success", "error"]
    arguments: dict[str, Any]
    result: ExperimentResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class ForgeReasoningResult:
    """The orchestration result: Muse's answer kept separate from the real evidence.

    ``experiments`` holds ONLY the ExperimentResults actually produced by a
    successful deterministic physics tool call -- the authoritative
    evidence. An unknown tool, invalid arguments, or a call refused for
    exceeding MAX_TOOL_CALLS never appears here, only in ``trace`` as an
    error entry. ``answer`` is Muse's natural-language interpretation of
    that evidence and must never be treated as a source of physical
    measurements itself.
    """

    answer: str | None
    experiments: list[ExperimentResult]
    tool_rounds: int
    status: str  # "answered" | "tool_round_limit" | "tool_call_limit"
    trace: list[ActionTraceEntry] = field(default_factory=list)


def run_forge_analysis(
    objective: str,
    system_data: dict[str, Any],
    client: MuseSparkClient,
) -> ForgeReasoningResult:
    """Run the bounded Muse <-> FORGE tool-call loop for one objective."""
    tools = [gear_train_experiment_tool_schema()]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": FORGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Objective: {objective}\n\n"
                f"Available system data (JSON): {json.dumps(system_data)}"
            ),
        },
    ]

    experiments: list[ExperimentResult] = []
    trace: list[ActionTraceEntry] = []
    call_limit_exceeded = False

    for round_number in range(1, MAX_TOOL_ROUNDS + 1):
        response = client.send(messages, tools)

        if not response.tool_calls:
            return ForgeReasoningResult(
                answer=response.content,
                experiments=experiments,
                tool_rounds=round_number - 1,
                status="answered",
                trace=trace,
            )

        messages.append(build_assistant_tool_call_message(response))

        for call in response.tool_calls:
            # len(experiments) only ever grows on a successful execution, so
            # this is exactly "how many tool calls have actually run so far"
            # -- a hard, global cap independent of how many rounds or
            # responses Muse spreads its requests across.
            if len(experiments) >= MAX_TOOL_CALLS:
                call_limit_exceeded = True
                error_message = (
                    f"FORGE tool-call limit ({MAX_TOOL_CALLS}) reached for this "
                    "analysis; this request was not executed."
                )
                trace.append(
                    ActionTraceEntry(
                        round_number=round_number,
                        tool_name=call.name,
                        status="error",
                        arguments=call.arguments,
                        error=error_message,
                    )
                )
                messages.append(build_tool_result_message(call.id, {"error": error_message}))
                continue

            try:
                execution = dispatch_tool_call(call.name, call.arguments)
            except (UnknownToolError, InvalidToolArgumentsError) as exc:
                trace.append(
                    ActionTraceEntry(
                        round_number=round_number,
                        tool_name=call.name,
                        status="error",
                        arguments=call.arguments,
                        error=str(exc),
                    )
                )
                messages.append(build_tool_result_message(call.id, {"error": str(exc)}))
                continue

            experiments.append(execution.result)
            trace.append(
                ActionTraceEntry(
                    round_number=round_number,
                    tool_name=execution.tool_name,
                    status="success",
                    arguments=execution.arguments,
                    result=execution.result,
                )
            )
            messages.append(
                build_tool_result_message(call.id, execution.result.model_dump(mode="json"))
            )

    status = "tool_call_limit" if call_limit_exceeded else "tool_round_limit"
    return ForgeReasoningResult(
        answer=None,
        experiments=experiments,
        tool_rounds=MAX_TOOL_ROUNDS,
        status=status,
        trace=trace,
    )
