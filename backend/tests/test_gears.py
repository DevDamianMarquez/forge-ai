"""Tests for the pure, single-mesh physics functions in app.physics.gears."""

from __future__ import annotations

import pytest

from app.physics.gears import (
    compute_gear_ratio,
    compute_output_direction,
    compute_output_rpm,
)


def test_compute_gear_ratio_reduction():
    assert compute_gear_ratio(driver_teeth=20, driven_teeth=60) == pytest.approx(3.0)


def test_compute_gear_ratio_overdrive():
    assert compute_gear_ratio(driver_teeth=60, driven_teeth=20) == pytest.approx(1 / 3)


def test_compute_output_rpm_canonical_example():
    # 1200 RPM into a 20-tooth driver meshed with a 60-tooth driven gear -> 400 RPM
    assert compute_output_rpm(input_rpm=1200, driver_teeth=20, driven_teeth=60) == pytest.approx(
        400.0
    )


def test_compute_output_direction_single_mesh_reverses():
    assert compute_output_direction(input_direction=1, number_of_external_meshes=1) == -1


def test_compute_output_direction_double_mesh_restores():
    assert compute_output_direction(input_direction=1, number_of_external_meshes=2) == 1


def test_compute_output_direction_zero_meshes_unchanged():
    assert compute_output_direction(input_direction=-1, number_of_external_meshes=0) == -1


@pytest.mark.parametrize(
    "driver_teeth,driven_teeth",
    [(0, 10), (-5, 10), (10, 0), (10, -5)],
)
def test_compute_gear_ratio_rejects_invalid_teeth(driver_teeth, driven_teeth):
    with pytest.raises(ValueError):
        compute_gear_ratio(driver_teeth, driven_teeth)


@pytest.mark.parametrize("input_rpm", [0, -100])
def test_compute_output_rpm_rejects_invalid_rpm(input_rpm):
    with pytest.raises(ValueError):
        compute_output_rpm(input_rpm=input_rpm, driver_teeth=20, driven_teeth=60)


def test_compute_output_rpm_rejects_invalid_teeth():
    with pytest.raises(ValueError):
        compute_output_rpm(input_rpm=1200, driver_teeth=0, driven_teeth=60)


def test_compute_output_direction_rejects_invalid_direction():
    with pytest.raises(ValueError):
        compute_output_direction(input_direction=2, number_of_external_meshes=1)


def test_compute_output_direction_rejects_negative_mesh_count():
    with pytest.raises(ValueError):
        compute_output_direction(input_direction=1, number_of_external_meshes=-1)
