"""Tests for multi-mesh GearTrain behavior in app.physics.train."""

from __future__ import annotations

import pytest

from app.models.physics import Gear, GearConnection, GearTrain
from app.physics.train import (
    compute_gear_train_output_direction,
    compute_gear_train_output_rpm,
    compute_gear_train_ratio,
)


def _single_stage_train() -> GearTrain:
    driver = Gear(id="driver", teeth=20)
    driven = Gear(id="driven", teeth=60)
    return GearTrain(input_rpm=1200, connections=[GearConnection(driver=driver, driven=driven)])


def test_single_stage_output_rpm_canonical():
    assert compute_gear_train_output_rpm(_single_stage_train()) == pytest.approx(400.0)


def test_single_stage_ratio_is_3_to_1():
    assert compute_gear_train_ratio(_single_stage_train()) == pytest.approx(3.0)


def test_single_stage_reverses_direction():
    assert compute_gear_train_output_direction(_single_stage_train()) == -1


def test_multi_stage_train_chains_stages():
    # Physical topology (a compound two-stage reduction, not a continuous
    # mesh chain):
    #   20T meshes 60T                   -- external mesh #1 (stage 1)
    #   60T shares a rigid shaft with 15T -- same shaft, no mesh, no reversal
    #   15T meshes 45T                   -- external mesh #2 (stage 2)
    #
    # Stage 1: 20 -> 60  (1200 RPM -> 400 RPM), ratio 60/20 = 3
    # Stage 2: 15 -> 45  (400 RPM -> 133.33 RPM), ratio 45/15 = 3
    #
    # total ratio = (60/20) * (45/15) = 9:1
    #
    # There are exactly two external gear meshes (one per stage), so exactly
    # two direction reversals -- the shared shaft between them reverses
    # nothing -- so direction ends up back where it started (+1).
    stage1 = GearConnection(driver=Gear(id="d1", teeth=20), driven=Gear(id="n1", teeth=60))
    stage2 = GearConnection(driver=Gear(id="d2", teeth=15), driven=Gear(id="n2", teeth=45))
    train = GearTrain(input_rpm=1200, connections=[stage1, stage2])

    assert compute_gear_train_output_rpm(train) == pytest.approx(1200 * 20 / 60 * 15 / 45)
    assert compute_gear_train_ratio(train) == pytest.approx(9.0)
    assert compute_gear_train_output_direction(train) == 1


def test_three_stage_train_direction_reverses_odd_number_of_times():
    stages = [
        GearConnection(driver=Gear(id="d1", teeth=10), driven=Gear(id="n1", teeth=20)),
        GearConnection(driver=Gear(id="d2", teeth=10), driven=Gear(id="n2", teeth=20)),
        GearConnection(driver=Gear(id="d3", teeth=10), driven=Gear(id="n3", teeth=20)),
    ]
    train = GearTrain(input_rpm=900, connections=stages)

    assert compute_gear_train_output_direction(train) == -1
    assert compute_gear_train_output_rpm(train) == pytest.approx(900 * 0.5 * 0.5 * 0.5)


def test_input_direction_is_respected():
    train = GearTrain(
        input_rpm=1000,
        input_direction=-1,
        connections=[GearConnection(driver=Gear(id="d", teeth=10), driven=Gear(id="n", teeth=20))],
    )
    assert compute_gear_train_output_direction(train) == 1
