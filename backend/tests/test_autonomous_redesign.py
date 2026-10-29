"""Tests for Milestone 7B.1's bounded autonomous redesign loop.

Every test uses FakeMuseClient (tests/fakes.py) or a tiny local fake --
none of these ever call the real Meta API. The canonical demo path
(20T->60T fails at 400 RPM, 20T->80T passes at 300 RPM) is exercised here
as the scripted fake-Muse fixture ONLY; production code never hardcodes
either candidate (see app/services/autonomous_redesign.py).
"""

from __future__ import annotations

import pytest

from app.models.physics import ExperimentStatus, Gear, GearConnection, GearTrain
from app.services.autonomous_redesign import (
    MAX_ATTEMPTS,
    MAX_TEETH,
    MIN_TEETH,
    GearRedesignCandidate,
    RedesignAttemptStatus,
    RedesignStatus,
    RedesignTraceStage,
    UnsupportedRedesignTopologyError,
    _is_passing,
    run_autonomous_redesign,
)
from app.services.meta_model import MuseResponse, ToolCall
from tests.fakes import FakeMuseClient

TOOL_NAME = "test_gear_design"

STARTING_TRAIN = GearTrain(
    input_rpm=1200,
    connections=[
        GearConnection(driver=Gear(id="input", teeth=20), driven=Gear(id="output", teeth=60))
    ],
)
OBJECTIVE_MAX_RPM = 300.0


def _candidate_call(input_teeth: int, output_teeth: int, call_id: str = "call-1") -> MuseResponse:
    return MuseResponse(
        content=None,
        tool_calls=[
            ToolCall(
                id=call_id,
                name=TOOL_NAME,
                arguments={"input_teeth": input_teeth, "output_teeth": output_teeth},
            )
        ],
    )


class _RaisingMuseClient:
    """A fake Muse client that always raises -- simulates a Meta API failure."""

    def send(self, messages, tools):  # noqa: ANN001 -- matches MuseSparkClient.send's shape
        raise RuntimeError("simulated Meta API failure")


# --- A. initial design deterministically fails the objective ---------------


def test_initial_design_deterministically_fails_objective():
    client = FakeMuseClient([_candidate_call(20, 60)])
    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert "FAIL" in result.trace[0].message
    assert "400" in result.trace[0].message


# --- B-K. canonical fail -> replan -> pass path -----------------------------


def test_canonical_fail_then_pass_demo_path():
    client = FakeMuseClient([_candidate_call(20, 60), _candidate_call(20, 80)])

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    # B/C/D: first candidate fails, with real recorded evidence
    first = result.attempts[0]
    assert first.status == RedesignAttemptStatus.FAILED
    assert first.candidate == GearRedesignCandidate(input_teeth=20, output_teeth=60)
    assert first.experiment.result == pytest.approx(400.0)
    assert first.experiment.constraint_results[0].passed is False

    # E: failed evidence is supplied into the next Muse interaction
    second_round_messages = client.sent_messages[1]
    tool_result_messages = [m for m in second_round_messages if m.get("role") == "tool"]
    assert any("400" in m["content"] for m in tool_result_messages)

    # F/G/H: second candidate passes, with real recorded evidence
    second = result.attempts[1]
    assert second.status == RedesignAttemptStatus.PASSED
    assert second.candidate == GearRedesignCandidate(input_teeth=20, output_teeth=80)
    assert second.experiment.result == pytest.approx(300.0)
    assert second.experiment.constraint_results[0].passed is True

    # I/J/K: loop stops immediately after PASS
    assert result.status == RedesignStatus.VERIFIED
    assert result.accepted_design == GearRedesignCandidate(input_teeth=20, output_teeth=80)
    assert result.final_experiment.result == pytest.approx(300.0)
    assert len(result.attempts) == 2
    assert client.call_count == 2


# --- L. first candidate passes -> only one attempt --------------------------


def test_first_candidate_passes_takes_only_one_attempt():
    client = FakeMuseClient([_candidate_call(20, 80)])

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert result.status == RedesignStatus.VERIFIED
    assert len(result.attempts) == 1
    assert client.call_count == 1


# --- M/N. all candidates fail -> EXHAUSTED, MAX_ATTEMPTS enforced -----------


def test_all_candidates_failing_exhausts_the_budget():
    # All three stay below the 80T threshold where 1200*20/output_teeth<=300,
    # so every one of them genuinely fails the objective.
    client = FakeMuseClient(
        [_candidate_call(20, 60), _candidate_call(20, 65), _candidate_call(20, 70)]
    )

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert result.status == RedesignStatus.EXHAUSTED
    assert len(result.attempts) == MAX_ATTEMPTS
    assert client.call_count == MAX_ATTEMPTS
    assert result.accepted_design is None
    assert result.trace[-1].stage == RedesignTraceStage.ATTEMPTS_EXHAUSTED


def test_max_attempts_is_three():
    assert MAX_ATTEMPTS == 3


def test_loop_never_calls_muse_more_than_max_attempts_even_with_more_scripted_responses():
    responses = [_candidate_call(20, 60 + i) for i in range(MAX_ATTEMPTS + 5)]
    client = FakeMuseClient(responses)

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert client.call_count == MAX_ATTEMPTS
    assert result.status in (RedesignStatus.EXHAUSTED, RedesignStatus.VERIFIED)


# --- O/P. duplicate candidate policy ----------------------------------------


def test_duplicate_candidate_is_not_re_executed():
    client = FakeMuseClient(
        [_candidate_call(20, 60), _candidate_call(20, 60), _candidate_call(20, 80)]
    )

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    duplicate_attempt = result.attempts[1]
    assert duplicate_attempt.status == RedesignAttemptStatus.DUPLICATE
    assert duplicate_attempt.candidate == GearRedesignCandidate(input_teeth=20, output_teeth=60)
    assert duplicate_attempt.experiment is None  # physics never re-run
    assert "already tested" in duplicate_attempt.error

    # The duplicate still consumed an attempt (deterministic policy), so the
    # passing candidate only arrives on the third call.
    assert client.call_count == 3
    assert result.status == RedesignStatus.VERIFIED


def test_duplicate_candidate_policy_is_deterministic_and_bounded_even_if_repeated_forever():
    client = FakeMuseClient([_candidate_call(20, 60)] * (MAX_ATTEMPTS + 10))

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert client.call_count == MAX_ATTEMPTS
    assert result.status == RedesignStatus.EXHAUSTED
    assert result.attempts[0].status == RedesignAttemptStatus.FAILED
    assert all(a.status == RedesignAttemptStatus.DUPLICATE for a in result.attempts[1:])


# --- Q/R. bounds and malformed arguments ------------------------------------


def test_out_of_range_teeth_is_rejected_without_crashing():
    client = FakeMuseClient([_candidate_call(MIN_TEETH - 1, 60), _candidate_call(20, 80)])

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert result.attempts[0].status == RedesignAttemptStatus.INVALID_ARGUMENTS
    assert result.attempts[0].candidate is None
    assert result.attempts[0].experiment is None
    assert result.status == RedesignStatus.VERIFIED  # loop recovered on the next attempt


def test_teeth_above_max_is_rejected():
    client = FakeMuseClient([_candidate_call(20, MAX_TEETH + 1)])

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert result.attempts[0].status == RedesignAttemptStatus.INVALID_ARGUMENTS


def test_malformed_tool_arguments_are_rejected_without_crashing():
    bad_response = MuseResponse(
        content=None,
        tool_calls=[
            ToolCall(id="call-1", name=TOOL_NAME, arguments={"input_teeth": "twenty", "output_teeth": 60})
        ],
    )
    client = FakeMuseClient([bad_response, _candidate_call(20, 80)])

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert result.attempts[0].status == RedesignAttemptStatus.INVALID_ARGUMENTS
    assert result.status == RedesignStatus.VERIFIED


def test_missing_required_argument_is_rejected():
    bad_response = MuseResponse(
        content=None,
        tool_calls=[ToolCall(id="call-1", name=TOOL_NAME, arguments={"input_teeth": 20})],
    )
    client = FakeMuseClient([bad_response])

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert result.attempts[0].status == RedesignAttemptStatus.INVALID_ARGUMENTS


# --- S. no tool call handled -------------------------------------------------


def test_no_tool_call_is_handled_without_crashing():
    client = FakeMuseClient(
        [MuseResponse(content="I think 80 teeth would work.", tool_calls=[]), _candidate_call(20, 80)]
    )

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert result.attempts[0].status == RedesignAttemptStatus.INVALID_RESPONSE
    assert result.attempts[0].candidate is None
    assert result.status == RedesignStatus.VERIFIED


# --- T. multiple tool calls handled deterministically -----------------------


def test_multiple_tool_calls_in_one_attempt_are_rejected_as_invalid_not_executed():
    multi_call_response = MuseResponse(
        content=None,
        tool_calls=[
            ToolCall(id="call-1", name=TOOL_NAME, arguments={"input_teeth": 20, "output_teeth": 70}),
            ToolCall(id="call-2", name=TOOL_NAME, arguments={"input_teeth": 20, "output_teeth": 80}),
        ],
    )
    client = FakeMuseClient([multi_call_response, _candidate_call(20, 80)])

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert result.attempts[0].status == RedesignAttemptStatus.INVALID_RESPONSE
    assert result.attempts[0].candidate is None
    assert result.attempts[0].experiment is None
    assert "2" in result.attempts[0].error
    # Neither candidate from the rejected multi-call response was ever tested.
    assert result.status == RedesignStatus.VERIFIED
    assert len(result.attempts) == 2


# --- U. unknown tool rejected -------------------------------------------------


def test_unknown_tool_is_rejected():
    client = FakeMuseClient(
        [
            MuseResponse(content=None, tool_calls=[ToolCall(id="call-1", name="delete_database", arguments={})]),
            _candidate_call(20, 80),
        ]
    )

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert result.attempts[0].status == RedesignAttemptStatus.UNKNOWN_TOOL
    assert "delete_database" in result.attempts[0].error
    assert result.status == RedesignStatus.VERIFIED


# --- V. Muse API failure handled ---------------------------------------------


def test_muse_api_failure_produces_model_error_without_crashing():
    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, _RaisingMuseClient())

    assert result.status == RedesignStatus.MODEL_ERROR
    assert result.accepted_design is None
    assert result.trace[-1].stage == RedesignTraceStage.MODEL_ERROR


# --- W/X. physics error / Muse's own claim never produces VERIFIED ---------


def test_is_passing_rejects_an_experiment_with_error_status():
    from app.models.physics import ExperimentResult

    broken = ExperimentResult(
        tool="compute_gear_train_output_rpm",
        inputs={},
        status=ExperimentStatus.ERROR,
        error="something went wrong",
    )
    assert _is_passing(broken) is False


def test_is_passing_rejects_success_with_no_constraint_results():
    from app.models.physics import ExperimentResult

    no_constraints = ExperimentResult(
        tool="compute_gear_train_output_rpm",
        inputs={},
        result=300.0,
        unit="rpm",
        status=ExperimentStatus.SUCCESS,
        constraint_results=[],
    )
    assert _is_passing(no_constraints) is False


def test_muse_claiming_success_in_text_never_overrides_a_failing_constraint():
    confident_but_wrong = MuseResponse(
        content="This design definitely satisfies the objective.",
        tool_calls=[
            ToolCall(id="call-1", name=TOOL_NAME, arguments={"input_teeth": 20, "output_teeth": 60})
        ],
    )
    client = FakeMuseClient([confident_but_wrong])

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert result.status != RedesignStatus.VERIFIED
    assert result.attempts[0].status == RedesignAttemptStatus.FAILED


# --- Y. trace contains failure/replan/success stages -------------------------


def test_trace_contains_every_expected_stage_in_order_for_the_canonical_path():
    client = FakeMuseClient([_candidate_call(20, 60), _candidate_call(20, 80)])

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    stages = [entry.stage for entry in result.trace]
    assert stages == [
        RedesignTraceStage.OBJECTIVE_RECEIVED,
        RedesignTraceStage.CANDIDATE_PROPOSED,
        RedesignTraceStage.PHYSICS_EVALUATED,
        RedesignTraceStage.CONSTRAINT_CHECKED,
        RedesignTraceStage.EVIDENCE_RETURNED,
        RedesignTraceStage.CANDIDATE_PROPOSED,
        RedesignTraceStage.PHYSICS_EVALUATED,
        RedesignTraceStage.CONSTRAINT_CHECKED,
        RedesignTraceStage.DESIGN_VERIFIED,
    ]
    assert len(stages) == 9  # matches the mission's canonical 01-09 trace


def test_trace_never_shows_a_later_stage_if_the_model_build_never_passed():
    client = FakeMuseClient([_candidate_call(20, 60), _candidate_call(20, 65), _candidate_call(20, 70)])

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    assert RedesignTraceStage.DESIGN_VERIFIED not in [e.stage for e in result.trace]


# --- Z. trace contains no raw chain-of-thought/model reasoning -------------


def test_trace_never_contains_muses_raw_text_content():
    secret_reasoning = (
        "SECRET REASONING: I believe 80 teeth will work because of my internal chain of thought."
    )
    client = FakeMuseClient(
        [
            MuseResponse(
                content=secret_reasoning,
                tool_calls=[
                    ToolCall(id="call-1", name=TOOL_NAME, arguments={"input_teeth": 20, "output_teeth": 80})
                ],
            )
        ]
    )

    result = run_autonomous_redesign(STARTING_TRAIN, OBJECTIVE_MAX_RPM, client)

    for entry in result.trace:
        assert secret_reasoning not in entry.message
    assert "SECRET REASONING" not in result.model_dump_json()


# --- Topology guard -----------------------------------------------------------


def test_multi_stage_starting_train_is_rejected():
    multi_stage = GearTrain(
        input_rpm=1200,
        connections=[
            GearConnection(driver=Gear(id="g1", teeth=20), driven=Gear(id="g2", teeth=60)),
            GearConnection(driver=Gear(id="g3", teeth=15), driven=Gear(id="g4", teeth=45)),
        ],
    )
    client = FakeMuseClient([])

    with pytest.raises(UnsupportedRedesignTopologyError):
        run_autonomous_redesign(multi_stage, OBJECTIVE_MAX_RPM, client)
