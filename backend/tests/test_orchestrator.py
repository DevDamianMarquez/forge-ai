"""Tests for the bounded Muse <-> FORGE tool-call orchestration loop.

Every test uses FakeMuseClient (tests/fakes.py) -- none of these ever call
the real Meta API.
"""

from __future__ import annotations

import pytest

from app.services.forge_tools import GEAR_TRAIN_EXPERIMENT_TOOL_NAME
from app.services.meta_model import MuseResponse, ToolCall
from app.services.orchestrator import MAX_TOOL_CALLS, MAX_TOOL_ROUNDS, run_forge_analysis
from tests.fakes import FakeMuseClient

VALID_ARGUMENTS = {
    "train": {
        "input_rpm": 1200,
        "connections": [
            {
                "driver": {"id": "driver", "teeth": 20},
                "driven": {"id": "driven", "teeth": 60},
            }
        ],
    },
    "constraints": [
        {"name": "max-output-rpm", "metric": "output_rpm", "operator": "lte", "value": 500}
    ],
}


def _tool_request(arguments: dict) -> MuseResponse:
    return MuseResponse(
        content=None,
        tool_calls=[
            ToolCall(id="call-1", name=GEAR_TRAIN_EXPERIMENT_TOOL_NAME, arguments=arguments)
        ],
    )


def _final_answer(text: str) -> MuseResponse:
    return MuseResponse(content=text, tool_calls=[])


def test_tool_call_produces_canonical_400_rpm_and_final_answer():
    client = FakeMuseClient(
        [
            _tool_request(VALID_ARGUMENTS),
            _final_answer("The output RPM is 400, which satisfies the 500 RPM limit."),
        ]
    )

    result = run_forge_analysis("Verify output speed stays below 500 RPM.", {}, client)

    assert result.status == "answered"
    assert result.answer == "The output RPM is 400, which satisfies the 500 RPM limit."
    assert len(result.experiments) == 1
    assert result.experiments[0].result == pytest.approx(400.0)
    assert result.experiments[0].unit == "rpm"
    assert result.tool_rounds == 1
    assert client.call_count == 2


def test_constraint_pass_is_retained_in_the_result():
    client = FakeMuseClient([_tool_request(VALID_ARGUMENTS), _final_answer("Constraint satisfied.")])

    result = run_forge_analysis("Check the constraint.", {}, client)

    constraint_results = result.experiments[0].constraint_results
    assert len(constraint_results) == 1
    assert constraint_results[0].passed is True
    assert constraint_results[0].actual_value == pytest.approx(400.0)


def test_unknown_tool_request_is_rejected_safely_and_loop_continues():
    client = FakeMuseClient(
        [
            MuseResponse(
                content=None,
                tool_calls=[ToolCall(id="call-1", name="delete_database", arguments={})],
            ),
            _final_answer("I could not verify that with the tools available."),
        ]
    )

    result = run_forge_analysis("Do something unsupported.", {}, client)

    assert result.status == "answered"
    assert result.experiments == []
    assert result.answer == "I could not verify that with the tools available."
    assert len(result.trace) == 1
    assert result.trace[0].status == "error"
    assert result.trace[0].result is None
    assert "delete_database" in result.trace[0].error


def test_invalid_tool_arguments_are_rejected_safely_and_loop_continues():
    bad_arguments = {"train": {"input_rpm": 1200, "connections": []}}
    client = FakeMuseClient(
        [_tool_request(bad_arguments), _final_answer("I need valid gear data to verify that.")]
    )

    result = run_forge_analysis("Verify with bad data.", {}, client)

    assert result.status == "answered"
    assert result.experiments == []
    assert len(result.trace) == 1
    assert result.trace[0].status == "error"
    assert result.trace[0].result is None


def test_final_answer_without_any_tool_call():
    client = FakeMuseClient([_final_answer("No physical calculation is needed for this objective.")])

    result = run_forge_analysis("Just explain the concept.", {}, client)

    assert result.status == "answered"
    assert result.tool_rounds == 0
    assert result.experiments == []
    assert client.call_count == 1


def test_tool_round_limit_bounds_the_loop():
    # Muse keeps requesting the tool forever; the loop must stop after
    # exactly MAX_TOOL_ROUNDS calls to the client, never more, no matter how
    # many scripted responses are available.
    responses = [_tool_request(VALID_ARGUMENTS) for _ in range(MAX_TOOL_ROUNDS + 5)]
    client = FakeMuseClient(responses)

    result = run_forge_analysis("Keep calculating forever.", {}, client)

    assert result.status == "tool_round_limit"
    assert client.call_count == MAX_TOOL_ROUNDS
    assert result.tool_rounds == MAX_TOOL_ROUNDS
    assert len(result.experiments) == MAX_TOOL_ROUNDS


def test_action_trace_holds_only_structured_facts_no_chain_of_thought():
    client = FakeMuseClient([_tool_request(VALID_ARGUMENTS), _final_answer("Done.")])

    result = run_forge_analysis("Verify it.", {}, client)

    assert len(result.trace) == 1
    entry = result.trace[0]
    assert entry.round_number == 1
    assert entry.tool_name == GEAR_TRAIN_EXPERIMENT_TOOL_NAME
    assert entry.status == "success"
    assert entry.result.result == pytest.approx(400.0)
    assert entry.error is None
    assert set(vars(entry).keys()) == {
        "round_number",
        "tool_name",
        "status",
        "arguments",
        "result",
        "error",
    }


def test_three_valid_tool_calls_in_one_response_execute_at_most_max_tool_calls():
    three_calls_in_one_response = MuseResponse(
        content=None,
        tool_calls=[
            ToolCall(id="call-1", name=GEAR_TRAIN_EXPERIMENT_TOOL_NAME, arguments=VALID_ARGUMENTS),
            ToolCall(id="call-2", name=GEAR_TRAIN_EXPERIMENT_TOOL_NAME, arguments=VALID_ARGUMENTS),
            ToolCall(id="call-3", name=GEAR_TRAIN_EXPERIMENT_TOOL_NAME, arguments=VALID_ARGUMENTS),
        ],
    )
    client = FakeMuseClient(
        [three_calls_in_one_response, _final_answer("Two experiments were run; that is the limit.")]
    )

    result = run_forge_analysis("Run as many experiments as you like.", {}, client)

    assert MAX_TOOL_CALLS == 2
    assert len(result.experiments) == MAX_TOOL_CALLS
    assert len(result.trace) == 3
    assert [entry.status for entry in result.trace] == ["success", "success", "error"]
    assert result.trace[2].result is None
    assert "limit" in result.trace[2].error.lower()


def test_tool_calls_distributed_across_rounds_still_execute_at_most_two_total():
    # Round 1: one valid call. Round 2: two more requested -- only one more
    # may run before the global MAX_TOOL_CALLS budget is spent.
    round_one = MuseResponse(
        content=None,
        tool_calls=[ToolCall(id="r1-c1", name=GEAR_TRAIN_EXPERIMENT_TOOL_NAME, arguments=VALID_ARGUMENTS)],
    )
    round_two = MuseResponse(
        content=None,
        tool_calls=[
            ToolCall(id="r2-c1", name=GEAR_TRAIN_EXPERIMENT_TOOL_NAME, arguments=VALID_ARGUMENTS),
            ToolCall(id="r2-c2", name=GEAR_TRAIN_EXPERIMENT_TOOL_NAME, arguments=VALID_ARGUMENTS),
        ],
    )
    client = FakeMuseClient([round_one, round_two])

    result = run_forge_analysis("Keep requesting across rounds.", {}, client)

    assert len(result.experiments) == MAX_TOOL_CALLS
    assert client.call_count == MAX_TOOL_ROUNDS
    assert result.status == "tool_call_limit"
    statuses_by_round = [(entry.round_number, entry.status) for entry in result.trace]
    assert statuses_by_round == [(1, "success"), (2, "success"), (2, "error")]


def test_mixed_valid_and_invalid_calls_retain_only_valid_result_as_evidence():
    mixed_response = MuseResponse(
        content=None,
        tool_calls=[
            ToolCall(id="good", name=GEAR_TRAIN_EXPERIMENT_TOOL_NAME, arguments=VALID_ARGUMENTS),
            ToolCall(id="bad", name="delete_database", arguments={}),
        ],
    )
    client = FakeMuseClient([mixed_response, _final_answer("One result was valid.")])

    result = run_forge_analysis("Mixed request.", {}, client)

    assert len(result.experiments) == 1
    assert result.experiments[0].result == pytest.approx(400.0)
    assert len(result.trace) == 2
    assert result.trace[0].status == "success"
    assert result.trace[1].status == "error"
    assert result.trace[1].result is None
