"""Milestone 7B.1: the bounded autonomous engineering redesign loop.

AI PROPOSES. PHYSICS VERIFIES. FAILURE BECOMES EVIDENCE. AI REPLANS.
PHYSICS VERIFIES AGAIN.

Reuses the existing Muse Spark tool-calling infrastructure
(``app.services.meta_model``) and the existing deterministic physics engine
(``app.physics.experiments.run_gear_train_experiment`` and
``app.physics.constraints.evaluate_constraint``, both unchanged, no
formulas duplicated here). This module adds one new, deliberately narrow
tool (``test_gear_design``) and a new bounded orchestration loop shaped for
autonomous *redesign* -- propose, verify, replan on failure, stop on
deterministic pass -- which is a different shape from Milestone 2A's
open-ended analysis loop (``app.services.orchestrator``), so it is a
sibling loop, not a forced extension of that one.

SCOPE (Milestone 7B.1): Muse may only choose two integers -- the input and
output gear's tooth counts -- for a single, fixed-topology external
two-gear mesh. Input RPM, topology, and the constraint itself are all
fixed trusted context; Muse never invents or changes them.

THE CENTRAL INVARIANT: Muse chooses what to test. Deterministic Python
always computes the physical result. Deterministic constraint code always
decides PASS/FAIL. Muse receives that evidence and may propose another
candidate. Only a deterministic PASS can ever produce a VERIFIED result --
this holds even if Muse's own text claims success.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.models.physics import (
    Constraint,
    ConstraintMetric,
    ConstraintOperator,
    ExperimentResult,
    ExperimentStatus,
    Gear,
    GearConnection,
    GearTrain,
)
from app.physics.experiments import run_gear_train_experiment
from app.services.meta_model import (
    MuseResponse,
    MuseSparkClient,
    build_assistant_tool_call_message,
    build_tool_result_message,
)

MIN_TEETH = 10
MAX_TEETH = 120
"""Sensible demo bounds for Milestone 7B.1's narrow parameter search --
small enough to stay a recognizable gear, large enough that the search is
not trivially constrained to one value. No stronger domain constraint
exists elsewhere in the project yet: ``Gear.teeth`` (app.models.physics)
only requires ``teeth > 0``, and the gear-train physics engine itself has
no upper bound. These are therefore an explicit, deliberate demo choice,
not derived from an existing constraint -- and they are enforced here
independently of whatever Muse claims: Pydantic validates every candidate
against these bounds before any physics runs, so Muse cannot bypass them.
"""

MAX_ATTEMPTS = 3
"""Hard cap on Muse round-trips for one autonomous redesign run.

An "attempt" is one full Muse turn, whether or not it actually produced a
usable candidate -- a response with no tool call, multiple tool calls, an
unknown tool, invalid arguments, or a duplicate candidate still consumes
one attempt. This is what actually bounds the loop against a misbehaving
or uncooperative model: bounding only "candidates successfully tested"
would let a model stall the loop forever by never sending a usable
request. No retries happen outside this fixed budget.
"""

TEST_GEAR_DESIGN_TOOL_NAME = "test_gear_design"

AUTONOMOUS_REDESIGN_SYSTEM_PROMPT = (
    "You are FORGE's autonomous redesign layer for a single external "
    "two-gear transmission. You may propose exactly one candidate design "
    f"per turn by calling the '{TEST_GEAR_DESIGN_TOOL_NAME}' tool with two "
    "integers: input_teeth and output_teeth. Input RPM and the "
    "transmission topology are fixed trusted context and cannot be "
    "changed -- you may only choose these two tooth counts. The tool's "
    "result is the only authoritative physical evidence: it reports the "
    "real output RPM, gear ratio, direction, and whether the objective "
    "constraint passed or failed. You must call the tool to test a "
    "candidate; do not estimate the result yourself or just describe what "
    "you would try. If the constraint fails, use the returned evidence to "
    "propose a different candidate on your next turn. Never claim a "
    "design is verified, successful, or satisfies the objective unless "
    "the tool's constraint result says PASS -- your own judgment about "
    "whether a design 'should' work is never sufficient evidence."
)


class UnsupportedRedesignTopologyError(ValueError):
    """Raised when the starting design is not a single external two-gear mesh.

    Milestone 7B.1 deliberately supports only this one topology -- see the
    module docstring's SCOPE section. FORGE never guesses how to extend an
    unsupported starting design; it refuses explicitly.
    """


class GearRedesignCandidate(BaseModel):
    """The only two numbers Muse may choose for Milestone 7B.1.

    Bounds are enforced here via Pydantic, independent of anything Muse
    claims -- a candidate outside [MIN_TEETH, MAX_TEETH] fails validation
    before any physics runs.
    """

    input_teeth: int = Field(..., ge=MIN_TEETH, le=MAX_TEETH)
    output_teeth: int = Field(..., ge=MIN_TEETH, le=MAX_TEETH)


class RedesignAttemptStatus(str, Enum):
    """What happened on one attempt -- always one of these, never a crash."""

    PASSED = "passed"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"


class RedesignAttempt(BaseModel):
    """One attempt's full, structured record.

    ``candidate``/``experiment`` are ``None`` exactly when no valid,
    non-duplicate candidate was actually evaluated by physics this
    attempt (``status`` explains why: no tool call, multiple tool calls,
    an unknown tool, or invalid arguments). A ``DUPLICATE`` attempt has a
    ``candidate`` (the repeated one) but no ``experiment`` -- physics is
    never re-run for a candidate already tested.
    """

    attempt_number: int
    candidate: GearRedesignCandidate | None
    experiment: ExperimentResult | None
    status: RedesignAttemptStatus
    error: str | None = None


class RedesignStatus(str, Enum):
    """The final outcome of one autonomous redesign run."""

    VERIFIED = "verified"
    EXHAUSTED = "exhausted"
    MODEL_ERROR = "model_error"


class RedesignTraceStage(str, Enum):
    """Which stage of the AI-proposes/physics-verifies loop one trace entry describes."""

    OBJECTIVE_RECEIVED = "objective_received"
    CANDIDATE_PROPOSED = "candidate_proposed"
    PHYSICS_EVALUATED = "physics_evaluated"
    CONSTRAINT_CHECKED = "constraint_checked"
    EVIDENCE_RETURNED = "evidence_returned"
    DESIGN_VERIFIED = "design_verified"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"
    INVALID_RESPONSE = "invalid_response"
    MODEL_ERROR = "model_error"


class RedesignTraceEntry(BaseModel):
    """One concise, structured action/evidence event -- never chain-of-thought.

    Holds only a stage, a coarse status, a short human-readable message,
    and which attempt (if any) it belongs to. Muse's own natural-language
    content is never stored here or anywhere else in this module.
    """

    stage: RedesignTraceStage
    status: str  # "ok" | "failed"
    message: str
    attempt_number: int | None = None


class AutonomousRedesignResult(BaseModel):
    """The full outcome of one autonomous redesign run.

    ``accepted_design``/``final_experiment`` are non-``None`` only when
    ``status == VERIFIED``: FORGE never reports an accepted design that
    deterministic physics did not actually pass.
    """

    objective: str
    status: RedesignStatus
    attempts: list[RedesignAttempt] = Field(default_factory=list)
    accepted_design: GearRedesignCandidate | None = None
    final_experiment: ExperimentResult | None = None
    trace: list[RedesignTraceEntry] = Field(default_factory=list)


def _tool_schema() -> dict[str, Any]:
    """The OpenAI/Muse function-tool definition for the one redesign tool."""
    return {
        "type": "function",
        "function": {
            "name": TEST_GEAR_DESIGN_TOOL_NAME,
            "description": (
                "Test one candidate external two-gear transmission design against "
                "the objective constraint. Input RPM and topology are fixed; you "
                "choose only input_teeth and output_teeth. Returns the "
                "deterministic physics result (output RPM, gear ratio, direction) "
                "and whether the objective constraint passed or failed -- this is "
                "the only authoritative evidence, never estimate it yourself."
            ),
            "parameters": GearRedesignCandidate.model_json_schema(),
        },
    }


def _build_constraint(max_output_rpm: float) -> Constraint:
    return Constraint(
        name="max_output_rpm",
        metric=ConstraintMetric.OUTPUT_RPM,
        operator=ConstraintOperator.LTE,
        value=max_output_rpm,
    )


def _evaluate_candidate(
    candidate: GearRedesignCandidate, input_rpm: float, constraint: Constraint
) -> ExperimentResult:
    """Combine the candidate with fixed trusted context and run the unchanged
    deterministic physics engine. No formula lives here."""
    train = GearTrain(
        input_rpm=input_rpm,
        connections=[
            GearConnection(
                driver=Gear(id="input", teeth=candidate.input_teeth),
                driven=Gear(id="output", teeth=candidate.output_teeth),
            )
        ],
    )
    return run_gear_train_experiment(train, [constraint])


def _is_passing(experiment: ExperimentResult) -> bool:
    """Deterministic PASS/FAIL authority: a physics error or an empty/unmet
    constraint list is never treated as a pass, regardless of anything else."""
    return (
        experiment.status == ExperimentStatus.SUCCESS
        and bool(experiment.constraint_results)
        and all(constraint_result.passed for constraint_result in experiment.constraint_results)
    )


def run_autonomous_redesign(
    starting_train: GearTrain,
    objective_max_output_rpm: float,
    client: MuseSparkClient,
) -> AutonomousRedesignResult:
    """Run the bounded Muse <-> FORGE autonomous redesign loop.

    Stops immediately on the first deterministic PASS (no further Muse
    calls), or after ``MAX_ATTEMPTS`` Muse turns without one, or
    immediately if the Muse client itself raises. Never recurses, never
    retries outside the fixed attempt budget.
    """
    if len(starting_train.connections) != 1:
        raise UnsupportedRedesignTopologyError(
            "Milestone 7B.1 only supports a single external two-gear mesh "
            f"(got {len(starting_train.connections)} transmission stage(s))."
        )

    input_rpm = starting_train.input_rpm
    constraint = _build_constraint(objective_max_output_rpm)
    objective_text = f"output_rpm <= {objective_max_output_rpm}"

    starting_connection = starting_train.connections[0]
    baseline = run_gear_train_experiment(starting_train, [constraint])
    baseline_passed = _is_passing(baseline)

    trace: list[RedesignTraceEntry] = [
        RedesignTraceEntry(
            stage=RedesignTraceStage.OBJECTIVE_RECEIVED,
            status="ok",
            message=(
                f"Objective: {objective_text}. Starting design "
                f"{starting_connection.driver.teeth}T -> {starting_connection.driven.teeth}T "
                f"at {input_rpm} RPM produces {baseline.result} RPM "
                f"({'PASS' if baseline_passed else 'FAIL'})."
            ),
        )
    ]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": AUTONOMOUS_REDESIGN_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Objective: {objective_text}\n"
                f"Fixed input RPM: {input_rpm}\n"
                f"Allowed design variables: input_teeth, output_teeth "
                f"(each between {MIN_TEETH} and {MAX_TEETH})\n"
                f"Starting design (fails objective): "
                f"{starting_connection.driver.teeth} teeth -> "
                f"{starting_connection.driven.teeth} teeth, "
                f"output_rpm={baseline.result}\n"
                f"Attempt budget: {MAX_ATTEMPTS}"
            ),
        },
    ]

    tools = [_tool_schema()]
    attempts: list[RedesignAttempt] = []
    tested_candidates: set[tuple[int, int]] = set()

    for attempt_number in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.send(messages, tools)
        except Exception as exc:  # noqa: BLE001 -- any Muse/API failure must become
            # structured evidence and a clean stop, never an unhandled crash. This is
            # the one intentional broad catch in this module, at the single external
            # I/O boundary (the Muse client call) -- nothing else here is caught this
            # broadly.
            trace.append(
                RedesignTraceEntry(
                    stage=RedesignTraceStage.MODEL_ERROR,
                    status="failed",
                    message=f"Muse Spark request failed: {exc}",
                    attempt_number=attempt_number,
                )
            )
            return AutonomousRedesignResult(
                objective=objective_text,
                status=RedesignStatus.MODEL_ERROR,
                attempts=attempts,
                trace=trace,
            )

        attempt = _handle_attempt(
            response=response,
            attempt_number=attempt_number,
            input_rpm=input_rpm,
            constraint=constraint,
            tested_candidates=tested_candidates,
            messages=messages,
            trace=trace,
        )
        attempts.append(attempt)

        if attempt.status == RedesignAttemptStatus.PASSED:
            trace.append(
                RedesignTraceEntry(
                    stage=RedesignTraceStage.DESIGN_VERIFIED,
                    status="ok",
                    message=(
                        f"Verified: {attempt.candidate.input_teeth}T -> "  # type: ignore[union-attr]
                        f"{attempt.candidate.output_teeth}T satisfies {objective_text}."  # type: ignore[union-attr]
                    ),
                    attempt_number=attempt_number,
                )
            )
            return AutonomousRedesignResult(
                objective=objective_text,
                status=RedesignStatus.VERIFIED,
                attempts=attempts,
                accepted_design=attempt.candidate,
                final_experiment=attempt.experiment,
                trace=trace,
            )

    trace.append(
        RedesignTraceEntry(
            stage=RedesignTraceStage.ATTEMPTS_EXHAUSTED,
            status="failed",
            message=f"No candidate satisfied {objective_text} within {MAX_ATTEMPTS} attempt(s).",
        )
    )
    last_experiment = next(
        (candidate_attempt.experiment for candidate_attempt in reversed(attempts) if candidate_attempt.experiment is not None),
        None,
    )
    return AutonomousRedesignResult(
        objective=objective_text,
        status=RedesignStatus.EXHAUSTED,
        attempts=attempts,
        final_experiment=last_experiment,
        trace=trace,
    )


def _handle_attempt(
    *,
    response: MuseResponse,
    attempt_number: int,
    input_rpm: float,
    constraint: Constraint,
    tested_candidates: set[tuple[int, int]],
    messages: list[dict[str, Any]],
    trace: list[RedesignTraceEntry],
) -> RedesignAttempt:
    """Handle exactly one Muse turn: validate its response, run physics if
    (and only if) it proposed exactly one valid, non-duplicate candidate,
    and append both conversation messages and trace entries along the way.
    """
    # Policy: a response with no tool call, or more than one tool call, is
    # rejected as invalid for this attempt rather than executed as a batch
    # or guessed at -- see the module docstring and Milestone 7B.1 report
    # for why (bounded, deterministic, never silently picks one of many).
    if len(response.tool_calls) == 0:
        messages.append({"role": "assistant", "content": response.content})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"No candidate was proposed. Call {TEST_GEAR_DESIGN_TOOL_NAME} "
                    "with input_teeth and output_teeth to test a candidate."
                ),
            }
        )
        error_message = "No tool call was made for this attempt."
        trace.append(
            RedesignTraceEntry(
                stage=RedesignTraceStage.INVALID_RESPONSE,
                status="failed",
                message=error_message,
                attempt_number=attempt_number,
            )
        )
        return RedesignAttempt(
            attempt_number=attempt_number,
            candidate=None,
            experiment=None,
            status=RedesignAttemptStatus.INVALID_RESPONSE,
            error=error_message,
        )

    if len(response.tool_calls) > 1:
        messages.append(build_assistant_tool_call_message(response))
        error_message = (
            "Only one candidate tool call is allowed per attempt; this response "
            f"proposed {len(response.tool_calls)} and none were executed."
        )
        for call in response.tool_calls:
            messages.append(build_tool_result_message(call.id, {"error": error_message}))
        trace.append(
            RedesignTraceEntry(
                stage=RedesignTraceStage.INVALID_RESPONSE,
                status="failed",
                message=error_message,
                attempt_number=attempt_number,
            )
        )
        return RedesignAttempt(
            attempt_number=attempt_number,
            candidate=None,
            experiment=None,
            status=RedesignAttemptStatus.INVALID_RESPONSE,
            error=error_message,
        )

    call = response.tool_calls[0]
    messages.append(build_assistant_tool_call_message(response))

    if call.name != TEST_GEAR_DESIGN_TOOL_NAME:
        error_message = f"Unknown or disallowed tool: {call.name!r}"
        messages.append(build_tool_result_message(call.id, {"error": error_message}))
        trace.append(
            RedesignTraceEntry(
                stage=RedesignTraceStage.INVALID_RESPONSE,
                status="failed",
                message=error_message,
                attempt_number=attempt_number,
            )
        )
        return RedesignAttempt(
            attempt_number=attempt_number,
            candidate=None,
            experiment=None,
            status=RedesignAttemptStatus.UNKNOWN_TOOL,
            error=error_message,
        )

    try:
        candidate = GearRedesignCandidate.model_validate(call.arguments)
    except ValidationError as exc:
        error_message = str(exc)
        messages.append(build_tool_result_message(call.id, {"error": error_message}))
        trace.append(
            RedesignTraceEntry(
                stage=RedesignTraceStage.INVALID_RESPONSE,
                status="failed",
                message=f"Invalid candidate arguments: {error_message}",
                attempt_number=attempt_number,
            )
        )
        return RedesignAttempt(
            attempt_number=attempt_number,
            candidate=None,
            experiment=None,
            status=RedesignAttemptStatus.INVALID_ARGUMENTS,
            error=error_message,
        )

    trace.append(
        RedesignTraceEntry(
            stage=RedesignTraceStage.CANDIDATE_PROPOSED,
            status="ok",
            message=f"Candidate: {candidate.input_teeth}T -> {candidate.output_teeth}T.",
            attempt_number=attempt_number,
        )
    )

    key = (candidate.input_teeth, candidate.output_teeth)
    if key in tested_candidates:
        # Policy: a repeated candidate consumes this attempt (it still counts
        # against MAX_ATTEMPTS) but physics is never re-run for it -- the
        # result would be identical and deterministic, so re-running would
        # only waste budget. Muse gets structured evidence saying so and may
        # propose something new on its next attempt, if any remain.
        error_message = (
            f"Candidate {candidate.input_teeth}T -> {candidate.output_teeth}T was already "
            "tested; physics was not re-run for a repeated candidate."
        )
        messages.append(build_tool_result_message(call.id, {"error": error_message}))
        trace.append(
            RedesignTraceEntry(
                stage=RedesignTraceStage.INVALID_RESPONSE,
                status="failed",
                message=error_message,
                attempt_number=attempt_number,
            )
        )
        return RedesignAttempt(
            attempt_number=attempt_number,
            candidate=candidate,
            experiment=None,
            status=RedesignAttemptStatus.DUPLICATE,
            error=error_message,
        )

    tested_candidates.add(key)
    experiment = _evaluate_candidate(candidate, input_rpm, constraint)
    messages.append(build_tool_result_message(call.id, experiment.model_dump(mode="json")))

    constraint_result = experiment.constraint_results[0] if experiment.constraint_results else None
    rpm_text = f"{experiment.result} RPM" if experiment.result is not None else "no result (physics error)"
    trace.append(
        RedesignTraceEntry(
            stage=RedesignTraceStage.PHYSICS_EVALUATED,
            status="ok" if experiment.status == ExperimentStatus.SUCCESS else "failed",
            message=f"Physics: {rpm_text}.",
            attempt_number=attempt_number,
        )
    )

    passed = _is_passing(experiment)
    trace.append(
        RedesignTraceEntry(
            stage=RedesignTraceStage.CONSTRAINT_CHECKED,
            status="ok" if passed else "failed",
            message=(
                constraint_result.message
                if constraint_result is not None
                else "Constraint could not be evaluated."
            ),
            attempt_number=attempt_number,
        )
    )

    if passed:
        return RedesignAttempt(
            attempt_number=attempt_number,
            candidate=candidate,
            experiment=experiment,
            status=RedesignAttemptStatus.PASSED,
        )

    trace.append(
        RedesignTraceEntry(
            stage=RedesignTraceStage.EVIDENCE_RETURNED,
            status="ok",
            message="Structured physics evidence returned to Muse for replanning.",
            attempt_number=attempt_number,
        )
    )
    return RedesignAttempt(
        attempt_number=attempt_number,
        candidate=candidate,
        experiment=experiment,
        status=RedesignAttemptStatus.FAILED,
    )
