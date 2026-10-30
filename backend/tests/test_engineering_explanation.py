"""Tests for Milestone 8C's ``engineering_explanation`` field.

Proves it is pure, deterministic formatting over a run's own already-
computed structured evidence -- never a new reasoning step, never a new
Muse/SAM/Meta call, and never able to imply VERIFIED/success for a run that
did not actually pass deterministic physics. None of these tests call the
real Meta API; they use the same ``FakeMuseClient`` as the rest of the
Milestone 7B.1 suite.
"""

from __future__ import annotations

import inspect

import pytest

from app.models.physics import Gear, GearConnection, GearTrain
from app.physics.experiments import run_gear_train_experiment
from app.services.autonomous_redesign import (
    GearRedesignCandidate,
    RedesignStatus,
    _build_engineering_explanation,
    run_autonomous_redesign,
)
from app.services.meta_model import MuseResponse, ToolCall
from tests.fakes import FakeMuseClient

TOOL_NAME = "test_gear_design"

CANONICAL_STARTING_TRAIN = GearTrain(
    input_rpm=1200,
    connections=[
        GearConnection(driver=Gear(id="input", teeth=20), driven=Gear(id="output", teeth=60))
    ],
)
CANONICAL_OBJECTIVE = 300.0


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


class _RaisingClient:
    """Simulates a Meta API failure -- never calls the real API."""

    def send(self, messages, tools):  # noqa: ANN001 -- matches MuseSparkClient.send's shape
        raise RuntimeError("simulated Meta API failure")


# --- 2. canonical real example -----------------------------------------------


def test_canonical_example_explanation_matches_the_known_real_values():
    client = FakeMuseClient([_candidate_call(20, 60), _candidate_call(20, 90)])

    result = run_autonomous_redesign(CANONICAL_STARTING_TRAIN, CANONICAL_OBJECTIVE, client)

    assert result.status == RedesignStatus.VERIFIED
    assert result.final_experiment.result == pytest.approx(266.666667, rel=1e-6)
    assert result.final_experiment.metrics["gear_ratio"] == pytest.approx(4.5)
    assert result.final_experiment.metrics["output_direction"] == -1.0

    explanation = result.engineering_explanation
    assert explanation is not None
    assert "20T -> 60T" in explanation
    assert "400" in explanation
    assert "300" in explanation
    assert "20T -> 90T" in explanation
    assert "4.5:1" in explanation
    assert "1200" in explanation
    assert "266.67" in explanation
    assert "reversed" in explanation.lower()
    assert "deterministic physics" in explanation.lower()


# --- 1. uses actual workflow values, not hardcoded canonical ones -----------


def test_explanation_uses_actual_workflow_values_not_hardcoded_canonical_ones():
    starting_train = GearTrain(
        input_rpm=900,
        connections=[
            GearConnection(driver=Gear(id="input", teeth=15), driven=Gear(id="output", teeth=30))
        ],
    )
    client = FakeMuseClient([_candidate_call(15, 60)])

    result = run_autonomous_redesign(starting_train, 250.0, client)

    assert result.status == RedesignStatus.VERIFIED
    explanation = result.engineering_explanation
    assert explanation is not None
    # None of the canonical demo's own numbers leak into this unrelated run.
    assert "20T -> 60T" not in explanation
    assert "20T -> 90T" not in explanation
    assert "266.67" not in explanation
    assert "1200" not in explanation
    # Its own real values are present instead.
    assert "15T -> 30T" in explanation
    assert "15T -> 60T" in explanation
    assert "900" in explanation


# --- 3. a different valid design produces a different explanation ----------


def test_a_different_valid_design_produces_a_different_explanation():
    client_a = FakeMuseClient([_candidate_call(20, 90)])
    client_b = FakeMuseClient([_candidate_call(20, 100)])

    result_a = run_autonomous_redesign(CANONICAL_STARTING_TRAIN, CANONICAL_OBJECTIVE, client_a)
    result_b = run_autonomous_redesign(CANONICAL_STARTING_TRAIN, CANONICAL_OBJECTIVE, client_b)

    assert result_a.engineering_explanation != result_b.engineering_explanation
    assert "20T -> 90T" in result_a.engineering_explanation
    assert "20T -> 100T" in result_b.engineering_explanation


# --- 4. never alters the structured numeric evidence -------------------------


def test_explanation_never_alters_the_structured_numeric_evidence():
    client = FakeMuseClient([_candidate_call(20, 60), _candidate_call(20, 90)])

    result = run_autonomous_redesign(CANONICAL_STARTING_TRAIN, CANONICAL_OBJECTIVE, client)

    assert result.final_experiment.result == pytest.approx(1200 * 20 / 90)
    assert result.accepted_design == GearRedesignCandidate(input_teeth=20, output_teeth=90)
    assert result.final_experiment.constraint_results[0].passed is True
    # engineering_explanation is a separate, additional field -- its presence
    # cannot have replaced or mutated any of the structured fields above.
    assert isinstance(result.engineering_explanation, str)


# --- 5. the explanation does not determine VERIFIED status -------------------


def test_explanation_does_not_determine_verified_status():
    """``_build_engineering_explanation`` takes ``status`` as a plain input
    and never computes it. Even when told the run is VERIFIED, it refuses
    to fabricate success prose when no accepted design/final experiment
    evidence actually exists -- it has no authority to assert VERIFIED on
    its own; it can only restate evidence that already exists."""
    starting_connection = CANONICAL_STARTING_TRAIN.connections[0]
    baseline = run_gear_train_experiment(CANONICAL_STARTING_TRAIN, [])

    explanation = _build_engineering_explanation(
        status=RedesignStatus.VERIFIED,
        objective_max_output_rpm=CANONICAL_OBJECTIVE,
        input_rpm=1200,
        starting_connection=starting_connection,
        baseline=baseline,
        attempts=[],
        accepted_design=None,
        final_experiment=None,
    )

    assert explanation is None


# --- 6. failed/exhausted workflows never imply successful verification -----


def test_exhausted_workflow_never_implies_successful_verification():
    client = FakeMuseClient(
        [_candidate_call(20, 60), _candidate_call(20, 65), _candidate_call(20, 70)]
    )

    result = run_autonomous_redesign(CANONICAL_STARTING_TRAIN, CANONICAL_OBJECTIVE, client)

    assert result.status == RedesignStatus.EXHAUSTED
    explanation = result.engineering_explanation
    assert explanation is not None
    assert "satisfies the engineering objective" not in explanation
    assert "No design was verified" in explanation
    assert "VERIFIED" not in explanation


def test_model_error_workflow_has_no_fabricated_explanation():
    result = run_autonomous_redesign(CANONICAL_STARTING_TRAIN, CANONICAL_OBJECTIVE, _RaisingClient())

    assert result.status == RedesignStatus.MODEL_ERROR
    assert result.engineering_explanation is None


# --- 7. no Muse/SAM/Meta client is called to generate the explanation -------


def test_building_the_explanation_requires_no_client_and_makes_no_network_call():
    """``_build_engineering_explanation``'s signature has no Muse/SAM/HTTP
    client parameter at all -- it is pure formatting over data already
    computed by the time it runs, never a new call to Meta."""
    signature = inspect.signature(_build_engineering_explanation)
    assert "client" not in signature.parameters


# --- 8. existing autonomous redesign behavior remains unchanged -------------


def test_existing_autonomous_redesign_behavior_is_unchanged_by_the_new_field():
    """The exact same canonical fail-then-pass path already covered in
    test_autonomous_redesign.py still produces identical attempts/status/
    accepted_design/final_experiment -- engineering_explanation is purely
    additive, never a replacement for any existing field."""
    client = FakeMuseClient([_candidate_call(20, 60), _candidate_call(20, 80)])

    result = run_autonomous_redesign(CANONICAL_STARTING_TRAIN, CANONICAL_OBJECTIVE, client)

    assert result.status == RedesignStatus.VERIFIED
    assert result.accepted_design == GearRedesignCandidate(input_teeth=20, output_teeth=80)
    assert result.final_experiment.result == pytest.approx(300.0)
    assert len(result.attempts) == 2
    assert client.call_count == 2
