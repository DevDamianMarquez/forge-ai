"""Tests for the deterministic perception-to-physics pipeline orchestrator.

Proves the pipeline is pure orchestration: it delegates perception to the
provider, the evidence boundary to build_physical_system, and physics to
run_physical_system_experiment -- never reimplementing any of them.
"""

from __future__ import annotations

import pytest

from app.models.perception import PerceptionRequest
from app.perception.providers.fixture import FixturePerceptionProvider
from app.services.physical_pipeline import PipelineStage, run_physical_pipeline


def _provider() -> FixturePerceptionProvider:
    return FixturePerceptionProvider()


# --- A. simple_gear_pair end-to-end ---------------------------------------


def test_simple_gear_pair_pipeline_produces_400_rpm():
    result = run_physical_pipeline(_provider(), PerceptionRequest(fixture_id="simple_gear_pair"))

    assert result.status == "completed"
    assert result.experiment is not None
    assert result.experiment.experiment.result == pytest.approx(400.0)
    assert result.experiment.experiment.metrics["gear_ratio"] == pytest.approx(3.0)
    assert result.experiment.experiment.metrics["output_direction"] == pytest.approx(-1.0)


# --- B. compound_gear_train end-to-end ------------------------------------


def test_compound_gear_train_pipeline_produces_9_to_1_reduction():
    result = run_physical_pipeline(_provider(), PerceptionRequest(fixture_id="compound_gear_train"))

    assert result.status == "completed"
    assert result.experiment.experiment.result == pytest.approx(1200 * 20 / 60 * 15 / 45)
    assert result.experiment.experiment.metrics["gear_ratio"] == pytest.approx(9.0)
    assert result.experiment.experiment.metrics["output_direction"] == pytest.approx(1.0)


# --- C. uncertain_gear_pair stops at MODEL_BUILD, no experiment ----------


def test_uncertain_gear_pair_pipeline_stops_at_model_build():
    result = run_physical_pipeline(_provider(), PerceptionRequest(fixture_id="uncertain_gear_pair"))

    assert result.status == "refused_at_model_build"
    assert result.experiment is None
    assert result.build_result.physical_system is None
    assert any(issue.component_id == "g2" for issue in result.build_result.issues)


# --- D. confidence=0.99 does not cause confirmation -----------------------


def test_uncertain_gear_pair_high_confidence_does_not_cause_confirmation():
    result = run_physical_pipeline(_provider(), PerceptionRequest(fixture_id="uncertain_gear_pair"))

    # The fixture's uncertain field has confidence=0.99 -- still refused.
    assert result.status == "refused_at_model_build"
    assert result.experiment is None


# --- E. trace stage order on success --------------------------------------


def test_success_trace_has_all_four_stages_in_order():
    result = run_physical_pipeline(_provider(), PerceptionRequest(fixture_id="simple_gear_pair"))

    assert [entry.stage for entry in result.trace] == [
        PipelineStage.PERCEPTION,
        PipelineStage.MODEL_BUILD,
        PipelineStage.TOPOLOGY,
        PipelineStage.EXPERIMENT,
    ]
    assert all(entry.status == "ok" for entry in result.trace)


# --- F. failure trace stops before TOPOLOGY/EXPERIMENT --------------------


def test_failure_trace_stops_at_model_build():
    result = run_physical_pipeline(_provider(), PerceptionRequest(fixture_id="uncertain_gear_pair"))

    stages = [entry.stage for entry in result.trace]
    assert stages == [PipelineStage.PERCEPTION, PipelineStage.MODEL_BUILD]
    assert result.trace[-1].status == "refused"


# --- Section 12: the pipeline is orchestration, not reimplementation -----


class _RecordingProvider:
    """A fake provider proving the pipeline calls .analyze() -- and only that."""

    def __init__(self, result):
        self._result = result
        self.calls = 0

    def analyze(self, request):
        self.calls += 1
        return self._result


def test_pipeline_delegates_perception_to_the_provider_verbatim():
    expected_perception = _provider().analyze(PerceptionRequest(fixture_id="simple_gear_pair"))
    recorder = _RecordingProvider(expected_perception)

    result = run_physical_pipeline(recorder, PerceptionRequest(fixture_id="simple_gear_pair"))

    assert recorder.calls == 1
    assert result.perception == expected_perception


def test_pipeline_delegates_evidence_boundary_to_build_physical_system(monkeypatch):
    import app.services.physical_pipeline as pipeline_module

    calls = []
    original = pipeline_module.build_physical_system

    def spy(perception, *args, **kwargs):
        calls.append(perception)
        return original(perception, *args, **kwargs)

    monkeypatch.setattr(pipeline_module, "build_physical_system", spy)

    run_physical_pipeline(_provider(), PerceptionRequest(fixture_id="simple_gear_pair"))

    assert len(calls) == 1


def test_pipeline_delegates_physics_to_run_physical_system_experiment(monkeypatch):
    import app.services.physical_pipeline as pipeline_module

    calls = []
    original = pipeline_module.run_physical_system_experiment

    def spy(system, *args, **kwargs):
        calls.append(system)
        return original(system, *args, **kwargs)

    monkeypatch.setattr(pipeline_module, "run_physical_system_experiment", spy)

    run_physical_pipeline(_provider(), PerceptionRequest(fixture_id="simple_gear_pair"))

    assert len(calls) == 1


def test_pipeline_never_calls_physics_when_boundary_refuses(monkeypatch):
    import app.services.physical_pipeline as pipeline_module

    calls = []
    original = pipeline_module.run_physical_system_experiment

    def spy(system, *args, **kwargs):
        calls.append(system)
        return original(system, *args, **kwargs)

    monkeypatch.setattr(pipeline_module, "run_physical_system_experiment", spy)

    run_physical_pipeline(_provider(), PerceptionRequest(fixture_id="uncertain_gear_pair"))

    assert len(calls) == 0
