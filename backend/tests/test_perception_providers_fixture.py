"""Tests for the deterministic fixture perception provider.

NOT real perception -- this proves the fixture provider's own behavior
(allowlist, labeling, determinism, fresh instances), independent of the
pipeline that consumes it.
"""

from __future__ import annotations

import pytest

from app.models.perception import ObservationSource, ObservationStatus, PerceptionRequest
from app.perception.providers.fixture import (
    FIXTURE_IDS,
    FixturePerceptionProvider,
    UnknownFixtureError,
)


def test_known_fixture_ids_are_exactly_the_documented_fixtures():
    assert FIXTURE_IDS == {"simple_gear_pair", "compound_gear_train", "uncertain_gear_pair"}


def test_simple_gear_pair_fixture_shape_and_labeling():
    provider = FixturePerceptionProvider()
    result = provider.analyze(PerceptionRequest(fixture_id="simple_gear_pair"))

    assert {s.id for s in result.shafts} == {"shaft-a", "shaft-b"}
    assert {g.id for g in result.gears} == {"g1", "g2"}
    assert all(gear.status == ObservationStatus.CONFIRMED for gear in result.gears)
    assert all(gear.teeth.status == ObservationStatus.CONFIRMED for gear in result.gears)

    # Never labeled as real vision perception -- always DERIVED.
    assert all(gear.source == ObservationSource.DERIVED for gear in result.gears)
    assert all(gear.teeth.source == ObservationSource.DERIVED for gear in result.gears)
    assert all(gear.source != ObservationSource.VISION_MODEL for gear in result.gears)
    assert any("not real perception" in note for note in result.notes)


def test_compound_gear_train_fixture_shape():
    provider = FixturePerceptionProvider()
    result = provider.analyze(PerceptionRequest(fixture_id="compound_gear_train"))

    assert {s.id for s in result.shafts} == {"shaft-a", "shaft-b", "shaft-c"}
    assert {g.id for g in result.gears} == {"g1", "g2", "g3", "g4"}
    assert len(result.meshes) == 2
    assert all(gear.source == ObservationSource.DERIVED for gear in result.gears)


def test_uncertain_gear_pair_fixture_has_exactly_one_unconfirmed_field():
    provider = FixturePerceptionProvider()
    result = provider.analyze(PerceptionRequest(fixture_id="uncertain_gear_pair"))

    g1 = next(gear for gear in result.gears if gear.id == "g1")
    g2 = next(gear for gear in result.gears if gear.id == "g2")

    assert g1.teeth.status == ObservationStatus.CONFIRMED
    assert g2.status == ObservationStatus.CONFIRMED  # the gear's existence itself is fine
    assert g2.shaft_id.status == ObservationStatus.CONFIRMED  # only teeth is uncertain
    assert g2.teeth.status == ObservationStatus.INFERRED
    assert g2.teeth.confidence == pytest.approx(0.99)


def test_unknown_fixture_id_is_rejected():
    provider = FixturePerceptionProvider()

    with pytest.raises(UnknownFixtureError):
        provider.analyze(PerceptionRequest(fixture_id="not_a_real_fixture"))


def test_provider_returns_fresh_instances_not_shared_mutable_state():
    provider = FixturePerceptionProvider()

    first = provider.analyze(PerceptionRequest(fixture_id="simple_gear_pair"))
    second = provider.analyze(PerceptionRequest(fixture_id="simple_gear_pair"))

    assert first is not second
    assert first.gears[0] is not second.gears[0]

    first.notes.append("mutated by a caller")
    assert "mutated by a caller" not in second.notes
