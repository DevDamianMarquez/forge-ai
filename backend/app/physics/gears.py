"""Deterministic physics for a single idealized external spur gear mesh.

These functions take plain numbers in and return plain numbers out -- no
Pydantic, no FastAPI, no AI model of any kind. They are the lowest layer
FORGE's future agent will call to get a real physical measurement instead of
letting a model guess one.

PHYSICS SCOPE AND LIMITATIONS (Milestone 1):

This module models ONLY idealized external spur gears, as simple rigid
circles defined solely by tooth count. It intentionally does NOT model or
claim to model:

- efficiency losses, friction, or windage
- material strength or fatigue
- tooth stress or contact (Hertzian) stress
- backlash or manufacturing tolerance
- bearing losses
- thermal effects
- dynamic/impact loading
- helical, planetary, worm, or any non-spur gear geometry
- any safety-critical engineering calculation

FORGE at this stage is a prototype reasoning/verification system, not
professional engineering analysis software. Every number here is exact for
the idealized case and nothing more.
"""

from __future__ import annotations


def compute_gear_ratio(driver_teeth: int, driven_teeth: int) -> float:
    """Return the speed-reduction ratio (driven:driver) of one external mesh.

    A ratio of 3.0 means the driven gear turns 3x slower than the driver gear
    (a 3:1 reduction). ratio = driven_teeth / driver_teeth.
    """
    _validate_teeth(driver_teeth, "driver_teeth")
    _validate_teeth(driven_teeth, "driven_teeth")
    return driven_teeth / driver_teeth


def compute_output_rpm(input_rpm: float, driver_teeth: int, driven_teeth: int) -> float:
    """Return the output RPM of one external mesh.

    output_rpm = input_rpm * driver_teeth / driven_teeth
    """
    _validate_rpm(input_rpm)
    _validate_teeth(driver_teeth, "driver_teeth")
    _validate_teeth(driven_teeth, "driven_teeth")
    return input_rpm * driver_teeth / driven_teeth


def compute_output_direction(input_direction: int, number_of_external_meshes: int) -> int:
    """Return the output rotational direction after N external meshes.

    Every external mesh reverses rotational direction, so the sign flips once
    per mesh: direction = input_direction * (-1) ** number_of_external_meshes.
    """
    if input_direction not in (1, -1):
        raise ValueError(f"input_direction must be 1 or -1, got {input_direction}")
    if number_of_external_meshes < 0:
        raise ValueError(
            f"number_of_external_meshes must be >= 0, got {number_of_external_meshes}"
        )
    return input_direction * (-1) ** number_of_external_meshes


def _validate_teeth(teeth: int, field_name: str) -> None:
    if teeth <= 0:
        raise ValueError(f"{field_name} must be a positive integer, got {teeth}")


def _validate_rpm(rpm: float) -> None:
    if rpm <= 0:
        raise ValueError(f"input_rpm must be positive, got {rpm}")
