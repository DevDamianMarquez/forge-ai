"""Tests for the deterministic PerceptionResult -> PhysicalSystem boundary.

CENTRAL INVARIANT UNDER TEST: confidence is not verification. Only
ObservationStatus.CONFIRMED values may cross into a PhysicalSystem,
regardless of how high (or low) their confidence is.
"""

from __future__ import annotations

import pytest

from app.models.perception import (
    ObservationSource,
    ObservationStatus,
    ObservedValue,
    PerceivedGear,
    PerceivedGearMesh,
    PerceivedShaft,
    PerceptionIssueCode,
    PerceptionResult,
)
from app.perception.builder import build_physical_system
from app.physics.topology import run_physical_system_experiment


def _obs(value, status, confidence=0.9, source=ObservationSource.VISION_MODEL):
    return ObservedValue(value=value, source=source, confidence=confidence, status=status)


def _confirmed_shaft(shaft_id: str) -> PerceivedShaft:
    return PerceivedShaft(
        id=shaft_id, source=ObservationSource.USER, confidence=1.0, status=ObservationStatus.CONFIRMED
    )


def _confirmed_gear(gear_id: str, teeth_count: int, shaft_id_value: str, **overrides) -> PerceivedGear:
    defaults = dict(
        id=gear_id,
        source=ObservationSource.USER,
        confidence=1.0,
        status=ObservationStatus.CONFIRMED,
        teeth=_obs(teeth_count, ObservationStatus.CONFIRMED),
        shaft_id=_obs(shaft_id_value, ObservationStatus.CONFIRMED),
    )
    defaults.update(overrides)
    return PerceivedGear(**defaults)


def _confirmed_mesh(gear_a_id: str, gear_b_id: str, **overrides) -> PerceivedGearMesh:
    defaults = dict(
        gear_a_id=gear_a_id,
        gear_b_id=gear_b_id,
        source=ObservationSource.USER,
        confidence=1.0,
        status=ObservationStatus.CONFIRMED,
    )
    defaults.update(overrides)
    return PerceivedGearMesh(**defaults)


def _simple_pair_perception(**overrides) -> PerceptionResult:
    defaults = dict(
        shafts=[_confirmed_shaft("shaft-a"), _confirmed_shaft("shaft-b")],
        gears=[
            _confirmed_gear("gear1", 20, "shaft-a"),
            _confirmed_gear("gear2", 60, "shaft-b"),
        ],
        meshes=[_confirmed_mesh("gear1", "gear2")],
        input_shaft_id=_obs("shaft-a", ObservationStatus.CONFIRMED),
        input_rpm=_obs(1200.0, ObservationStatus.CONFIRMED),
    )
    defaults.update(overrides)
    return PerceptionResult(**defaults)


# --- A. Fully confirmed simple system builds and executes to 400 RPM -----


def test_fully_confirmed_system_builds_and_executes_to_400_rpm():
    perception = _simple_pair_perception()

    result = build_physical_system(perception)

    assert result.issues == []
    assert result.physical_system is not None

    experiment = run_physical_system_experiment(result.physical_system)
    assert experiment.experiment.result == pytest.approx(400.0)


# --- B. Inferred tooth count blocks construction --------------------------


def test_inferred_tooth_count_blocks_construction_even_at_high_confidence():
    perception = _simple_pair_perception(
        gears=[
            _confirmed_gear("gear1", 20, "shaft-a", teeth=_obs(20, ObservationStatus.INFERRED, confidence=0.99)),
            _confirmed_gear("gear2", 60, "shaft-b"),
        ]
    )

    result = build_physical_system(perception)

    assert result.physical_system is None
    assert any(issue.code == PerceptionIssueCode.UNCONFIRMED_VALUE for issue in result.issues)


# --- C. Observed (not confirmed) tooth count blocks construction ---------


def test_observed_tooth_count_blocks_construction():
    perception = _simple_pair_perception(
        gears=[
            _confirmed_gear("gear1", 20, "shaft-a", teeth=_obs(20, ObservationStatus.OBSERVED, confidence=0.8)),
            _confirmed_gear("gear2", 60, "shaft-b"),
        ]
    )

    result = build_physical_system(perception)

    assert result.physical_system is None


# --- D. Confirmed value with LOW confidence is still accepted ------------


def test_confirmed_value_with_low_confidence_is_accepted():
    perception = _simple_pair_perception(
        gears=[
            _confirmed_gear("gear1", 20, "shaft-a", teeth=_obs(20, ObservationStatus.CONFIRMED, confidence=0.60)),
            _confirmed_gear("gear2", 60, "shaft-b"),
        ]
    )

    result = build_physical_system(perception)

    assert result.issues == []
    assert result.physical_system is not None


# --- E. Rejected observation blocks construction -------------------------


def test_rejected_tooth_count_blocks_construction():
    perception = _simple_pair_perception(
        gears=[
            _confirmed_gear("gear1", 20, "shaft-a", teeth=_obs(20, ObservationStatus.REJECTED, confidence=0.3)),
            _confirmed_gear("gear2", 60, "shaft-b"),
        ]
    )

    result = build_physical_system(perception)

    assert result.physical_system is None
    assert any(issue.code == PerceptionIssueCode.REJECTED_VALUE for issue in result.issues)


# --- F. Unresolved shaft assignment blocks construction -------------------


def test_unresolved_shaft_assignment_blocks_construction():
    perception = _simple_pair_perception(
        gears=[
            _confirmed_gear(
                "gear1", 20, "shaft-a", shaft_id=_obs("shaft-a", ObservationStatus.UNRESOLVED, confidence=0.5)
            ),
            _confirmed_gear("gear2", 60, "shaft-b"),
        ]
    )

    result = build_physical_system(perception)

    assert result.physical_system is None
    assert any(issue.field == "shaft_id" for issue in result.issues)


# --- G. Unconfirmed gear mesh blocks construction -------------------------


def test_unconfirmed_mesh_blocks_construction():
    perception = _simple_pair_perception(
        meshes=[_confirmed_mesh("gear1", "gear2", status=ObservationStatus.INFERRED, confidence=0.95)]
    )

    result = build_physical_system(perception)

    assert result.physical_system is None
    assert any(issue.code == PerceptionIssueCode.UNCONFIRMED_VALUE for issue in result.issues)


# --- H. Missing required value blocks construction ------------------------


def test_no_confirmed_gears_at_all_blocks_construction():
    perception = _simple_pair_perception(gears=[])

    result = build_physical_system(perception)

    assert result.physical_system is None
    assert any(issue.code == PerceptionIssueCode.MISSING_VALUE and issue.field == "gears" for issue in result.issues)


# --- I. Invalid gear->shaft reference: structured issue, never a crash ---


def test_gear_referencing_unconfirmed_shaft_produces_structured_issue_not_a_crash():
    perception = _simple_pair_perception(
        shafts=[_confirmed_shaft("shaft-a")],  # shaft-b never confirmed
    )

    result = build_physical_system(perception)

    assert result.physical_system is None
    assert any(issue.code == PerceptionIssueCode.INVALID_REFERENCE for issue in result.issues)


def test_gear_referencing_shaft_not_in_perception_at_all_produces_structured_issue():
    perception = _simple_pair_perception(
        gears=[
            _confirmed_gear("gear1", 20, "shaft-a"),
            _confirmed_gear("gear2", 60, "shaft-ghost"),
        ]
    )

    result = build_physical_system(perception)

    assert result.physical_system is None
    assert any(issue.code == PerceptionIssueCode.INVALID_REFERENCE for issue in result.issues)


# --- J. Output shaft omitted, otherwise valid: compiler infers it --------


def test_output_shaft_omitted_is_inferred_by_the_topology_compiler():
    perception = _simple_pair_perception()  # no output_shaft_id at all
    assert perception.output_shaft_id is None

    result = build_physical_system(perception)

    assert result.issues == []
    assert result.physical_system is not None
    assert result.physical_system.output_shaft_id is None  # left to the compiler

    experiment = run_physical_system_experiment(result.physical_system)
    assert experiment.topology.output_shaft_id == "shaft-b"
    assert experiment.experiment.result == pytest.approx(400.0)


# output_shaft_id semantics: ABSENT is delegable to the topology compiler,
# but an explicit PRESENT candidate is a claim that must itself be
# confirmed -- it must never be silently discarded in favor of letting the
# compiler infer a potentially different shaft.


def test_confirmed_output_shaft_id_is_accepted_and_transferred():
    perception = _simple_pair_perception(
        output_shaft_id=_obs("shaft-b", ObservationStatus.CONFIRMED, confidence=0.95)
    )

    result = build_physical_system(perception)

    assert result.issues == []
    assert result.physical_system is not None
    assert result.physical_system.output_shaft_id == "shaft-b"


@pytest.mark.parametrize(
    "status",
    [ObservationStatus.INFERRED, ObservationStatus.OBSERVED, ObservationStatus.UNRESOLVED],
)
def test_explicit_unconfirmed_output_shaft_id_blocks_construction(status):
    perception = _simple_pair_perception(output_shaft_id=_obs("shaft-b", status, confidence=1.0))

    result = build_physical_system(perception)

    assert result.physical_system is None
    assert any(
        issue.code == PerceptionIssueCode.UNCONFIRMED_VALUE and issue.field == "output_shaft_id"
        for issue in result.issues
    )


def test_rejected_output_shaft_id_blocks_construction():
    perception = _simple_pair_perception(
        output_shaft_id=_obs("shaft-b", ObservationStatus.REJECTED, confidence=0.3)
    )

    result = build_physical_system(perception)

    assert result.physical_system is None
    assert any(
        issue.code == PerceptionIssueCode.REJECTED_VALUE and issue.field == "output_shaft_id"
        for issue in result.issues
    )


def test_confirmed_output_shaft_id_referencing_unconfirmed_shaft_blocks_construction():
    perception = _simple_pair_perception(
        shafts=[_confirmed_shaft("shaft-a")],  # shaft-b never confirmed
        output_shaft_id=_obs("shaft-b", ObservationStatus.CONFIRMED, confidence=1.0),
    )

    result = build_physical_system(perception)

    assert result.physical_system is None
    assert any(
        issue.code == PerceptionIssueCode.INVALID_REFERENCE and issue.field == "output_shaft_id"
        for issue in result.issues
    )


def test_output_shaft_id_confidence_does_not_override_unconfirmed_status():
    # output_shaft_id "shaft-b", confidence=1.0, status=inferred MUST FAIL --
    # confidence never overrides status, even for this specific field.
    perception = _simple_pair_perception(
        output_shaft_id=_obs("shaft-b", ObservationStatus.INFERRED, confidence=1.0)
    )

    result = build_physical_system(perception)

    assert result.physical_system is None


# --- K. Builder never mutates the original PerceptionResult ---------------


def test_builder_never_mutates_the_input_perception_result():
    perception = _simple_pair_perception()
    before = perception.model_dump(mode="json")

    build_physical_system(perception)

    after = perception.model_dump(mode="json")
    assert before == after


# --- Section 12: the explicit confidence-is-not-verification test --------


def test_confidence_is_not_verification():
    """Perceived tooth count value=20, confidence=1.0, status=inferred MUST
    FAIL. value=20, confidence=0.51, status=confirmed MUST SUCCEED. Status
    decides the boundary; confidence is only metadata.
    """
    high_confidence_but_inferred = _simple_pair_perception(
        gears=[
            _confirmed_gear(
                "gear1", 20, "shaft-a", teeth=_obs(20, ObservationStatus.INFERRED, confidence=1.0)
            ),
            _confirmed_gear("gear2", 60, "shaft-b"),
        ]
    )
    low_confidence_but_confirmed = _simple_pair_perception(
        gears=[
            _confirmed_gear(
                "gear1", 20, "shaft-a", teeth=_obs(20, ObservationStatus.CONFIRMED, confidence=0.51)
            ),
            _confirmed_gear("gear2", 60, "shaft-b"),
        ]
    )

    inferred_result = build_physical_system(high_confidence_but_inferred)
    confirmed_result = build_physical_system(low_confidence_but_confirmed)

    assert inferred_result.physical_system is None, "confidence=1.0 + inferred must NOT be accepted"
    assert confirmed_result.physical_system is not None, "confidence=0.51 + confirmed MUST be accepted"
