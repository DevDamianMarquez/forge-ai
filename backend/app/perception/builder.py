"""The deterministic boundary: PerceptionResult -> PhysicalSystem, or refusal.

100% deterministic. No Muse, no SAM, no API, no network, no LLM -- this
module only evaluates the ``status`` of structured observations already in
hand and either constructs a ``PhysicalSystem`` or explains why it can't.

The central rule: CONFIRMED values may cross into PhysicalSystem. OBSERVED,
INFERRED, and UNRESOLVED values never do, no matter their confidence --
confidence is metadata, not verification. REJECTED values never do either.
If anything required is not confirmed, no PhysicalSystem is produced; every
reason is reported as a structured PerceptionIssue instead. This module
never mutates the PerceptionResult it is given.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.models.perception import (
    ObservationStatus,
    ObservedValue,
    PerceivedGear,
    PerceivedGearMesh,
    PerceivedShaft,
    PerceptionIssue,
    PerceptionIssueCode,
    PerceptionResult,
    PhysicalSystemBuildResult,
)
from app.models.physics import Constraint, GearMesh, PhysicalSystem, Shaft, SystemGear


def build_physical_system(
    perception: PerceptionResult,
    constraints: list[Constraint] | None = None,
) -> PhysicalSystemBuildResult:
    """Deterministically build a PhysicalSystem from `perception`, or refuse.

    `constraints` are not derived from perception in this milestone -- they
    may be passed through separately, or omitted entirely.
    """
    issues: list[PerceptionIssue] = []
    accepted: list[str] = []
    unresolved: list[str] = []

    shafts: list[Shaft] = []
    for shaft in perception.shafts:
        built = _build_shaft(shaft, issues=issues, accepted=accepted)
        if built is not None:
            shafts.append(built)
    confirmed_shaft_ids = {shaft.id for shaft in shafts}

    gears: list[SystemGear] = []
    for gear in perception.gears:
        built = _build_gear(
            gear, confirmed_shaft_ids=confirmed_shaft_ids, issues=issues, accepted=accepted
        )
        if built is not None:
            gears.append(built)
    confirmed_gear_ids = {gear.id for gear in gears}

    meshes: list[GearMesh] = []
    for mesh in perception.meshes:
        built = _build_mesh(
            mesh, confirmed_gear_ids=confirmed_gear_ids, issues=issues, accepted=accepted
        )
        if built is not None:
            meshes.append(built)

    if not shafts:
        issues.append(_issue(PerceptionIssueCode.MISSING_VALUE, "no confirmed shafts available", field="shafts"))
    if not gears:
        issues.append(_issue(PerceptionIssueCode.MISSING_VALUE, "no confirmed gears available", field="gears"))
    if not meshes:
        issues.append(
            _issue(PerceptionIssueCode.MISSING_VALUE, "no confirmed gear meshes available", field="meshes")
        )

    input_shaft_id = _require_confirmed(
        perception.input_shaft_id, field="input_shaft_id", issues=issues
    )
    if input_shaft_id is not None:
        accepted.append("input_shaft_id")
        if input_shaft_id not in confirmed_shaft_ids:
            issues.append(
                _issue(
                    PerceptionIssueCode.INVALID_REFERENCE,
                    f"input_shaft_id {input_shaft_id!r} is not a confirmed shaft",
                    field="input_shaft_id",
                    status=perception.input_shaft_id.status,
                )
            )

    input_rpm = _require_confirmed(perception.input_rpm, field="input_rpm", issues=issues)
    if input_rpm is not None:
        accepted.append("input_rpm")

    output_shaft_id = _resolve_output_shaft_id(
        perception.output_shaft_id,
        confirmed_shaft_ids=confirmed_shaft_ids,
        issues=issues,
        accepted=accepted,
    )

    if issues:
        return PhysicalSystemBuildResult(
            physical_system=None,
            accepted_observations=accepted,
            unresolved_observations=unresolved,
            issues=issues,
        )

    try:
        physical_system = PhysicalSystem(
            shafts=shafts,
            gears=gears,
            meshes=meshes,
            input_shaft_id=input_shaft_id,
            input_rpm=input_rpm,
            output_shaft_id=output_shaft_id,
            constraints=list(constraints) if constraints else [],
        )
    except (ValidationError, ValueError) as exc:
        issues.append(_issue(PerceptionIssueCode.INVALID_REFERENCE, str(exc)))
        return PhysicalSystemBuildResult(
            physical_system=None,
            accepted_observations=[],
            unresolved_observations=unresolved,
            issues=issues,
        )

    return PhysicalSystemBuildResult(
        physical_system=physical_system,
        accepted_observations=accepted,
        unresolved_observations=unresolved,
        issues=[],
    )


def _issue(
    code: PerceptionIssueCode,
    message: str,
    *,
    component_id: str | None = None,
    field: str | None = None,
    status: ObservationStatus | None = None,
) -> PerceptionIssue:
    return PerceptionIssue(code=code, message=message, component_id=component_id, field=field, status=status)


def _require_confirmed(
    observed: ObservedValue[Any] | None,
    *,
    field: str,
    issues: list[PerceptionIssue],
    component_id: str | None = None,
) -> Any | None:
    """Return observed.value only if status is CONFIRMED; else record an issue."""
    if observed is None:
        issues.append(_issue(PerceptionIssueCode.MISSING_VALUE, f"{field} was not observed", component_id=component_id, field=field))
        return None
    if observed.status == ObservationStatus.REJECTED:
        issues.append(
            _issue(
                PerceptionIssueCode.REJECTED_VALUE,
                f"{field} was rejected",
                component_id=component_id,
                field=field,
                status=observed.status,
            )
        )
        return None
    if observed.status != ObservationStatus.CONFIRMED:
        issues.append(
            _issue(
                PerceptionIssueCode.UNCONFIRMED_VALUE,
                f"{field} is {observed.status.value}, not confirmed",
                component_id=component_id,
                field=field,
                status=observed.status,
            )
        )
        return None
    return observed.value


def _build_shaft(
    shaft: PerceivedShaft, *, issues: list[PerceptionIssue], accepted: list[str]
) -> Shaft | None:
    if shaft.status == ObservationStatus.REJECTED:
        issues.append(
            _issue(
                PerceptionIssueCode.REJECTED_VALUE,
                f"shaft {shaft.id!r} existence was rejected",
                component_id=shaft.id,
                field="existence",
                status=shaft.status,
            )
        )
        return None
    if shaft.status != ObservationStatus.CONFIRMED:
        issues.append(
            _issue(
                PerceptionIssueCode.UNCONFIRMED_VALUE,
                f"shaft {shaft.id!r} existence is {shaft.status.value}, not confirmed",
                component_id=shaft.id,
                field="existence",
                status=shaft.status,
            )
        )
        return None
    accepted.append(f"shaft:{shaft.id}")
    return Shaft(id=shaft.id, label=shaft.label)


def _build_gear(
    gear: PerceivedGear,
    *,
    confirmed_shaft_ids: set[str],
    issues: list[PerceptionIssue],
    accepted: list[str],
) -> SystemGear | None:
    if gear.status == ObservationStatus.REJECTED:
        issues.append(
            _issue(
                PerceptionIssueCode.REJECTED_VALUE,
                f"gear {gear.id!r} existence was rejected",
                component_id=gear.id,
                field="existence",
                status=gear.status,
            )
        )
        return None
    if gear.status != ObservationStatus.CONFIRMED:
        issues.append(
            _issue(
                PerceptionIssueCode.UNCONFIRMED_VALUE,
                f"gear {gear.id!r} existence is {gear.status.value}, not confirmed",
                component_id=gear.id,
                field="existence",
                status=gear.status,
            )
        )
        return None

    teeth = _require_confirmed(gear.teeth, field="teeth", issues=issues, component_id=gear.id)
    shaft_id = _require_confirmed(gear.shaft_id, field="shaft_id", issues=issues, component_id=gear.id)
    if teeth is None or shaft_id is None:
        return None

    if shaft_id not in confirmed_shaft_ids:
        issues.append(
            _issue(
                PerceptionIssueCode.INVALID_REFERENCE,
                f"gear {gear.id!r} references shaft {shaft_id!r}, which is not a confirmed shaft",
                component_id=gear.id,
                field="shaft_id",
                status=gear.shaft_id.status,
            )
        )
        return None

    accepted.append(f"gear:{gear.id}.existence")
    accepted.append(f"gear:{gear.id}.teeth")
    accepted.append(f"gear:{gear.id}.shaft_id")
    return SystemGear(id=gear.id, teeth=teeth, shaft_id=shaft_id, label=gear.label)


def _build_mesh(
    mesh: PerceivedGearMesh,
    *,
    confirmed_gear_ids: set[str],
    issues: list[PerceptionIssue],
    accepted: list[str],
) -> GearMesh | None:
    mesh_id = f"{mesh.gear_a_id}-{mesh.gear_b_id}"
    if mesh.status == ObservationStatus.REJECTED:
        issues.append(
            _issue(
                PerceptionIssueCode.REJECTED_VALUE,
                f"mesh {mesh_id} was rejected",
                component_id=mesh_id,
                field="existence",
                status=mesh.status,
            )
        )
        return None
    if mesh.status != ObservationStatus.CONFIRMED:
        issues.append(
            _issue(
                PerceptionIssueCode.UNCONFIRMED_VALUE,
                f"mesh {mesh_id} is {mesh.status.value}, not confirmed",
                component_id=mesh_id,
                field="existence",
                status=mesh.status,
            )
        )
        return None

    if mesh.gear_a_id not in confirmed_gear_ids or mesh.gear_b_id not in confirmed_gear_ids:
        missing = mesh.gear_a_id if mesh.gear_a_id not in confirmed_gear_ids else mesh.gear_b_id
        issues.append(
            _issue(
                PerceptionIssueCode.INVALID_REFERENCE,
                f"mesh {mesh_id} references gear {missing!r}, which is not a confirmed gear",
                component_id=mesh_id,
                field="gear_reference",
                status=mesh.status,
            )
        )
        return None

    accepted.append(f"mesh:{mesh_id}")
    return GearMesh(gear_a_id=mesh.gear_a_id, gear_b_id=mesh.gear_b_id)


def _resolve_output_shaft_id(
    observed: ObservedValue[str] | None,
    *,
    confirmed_shaft_ids: set[str],
    issues: list[PerceptionIssue],
    accepted: list[str],
) -> str | None:
    """output_shaft_id is optional only when ABSENT entirely: if perception
    proposes no candidate at all, the topology compiler may infer one on its
    own. But once perception explicitly proposes a candidate, that is a
    claim about the world, not nothing -- it must be confirmed like any
    other required field. An unconfirmed or rejected explicit candidate is
    never silently discarded in favor of letting the compiler guess, since
    the compiler's own inference could legitimately land on a different
    shaft than the one perception believed.
    """
    if observed is None:
        return None

    if observed.status == ObservationStatus.REJECTED:
        issues.append(
            _issue(
                PerceptionIssueCode.REJECTED_VALUE,
                "output_shaft_id was rejected",
                field="output_shaft_id",
                status=observed.status,
            )
        )
        return None

    if observed.status != ObservationStatus.CONFIRMED:
        issues.append(
            _issue(
                PerceptionIssueCode.UNCONFIRMED_VALUE,
                f"output_shaft_id is {observed.status.value}, not confirmed; an explicit "
                "but unconfirmed output_shaft_id cannot be silently discarded in favor of "
                "the topology compiler's own inference",
                field="output_shaft_id",
                status=observed.status,
            )
        )
        return None

    if observed.value not in confirmed_shaft_ids:
        issues.append(
            _issue(
                PerceptionIssueCode.INVALID_REFERENCE,
                f"output_shaft_id {observed.value!r} is not a confirmed shaft",
                field="output_shaft_id",
                status=observed.status,
            )
        )
        return None
    accepted.append("output_shaft_id")
    return observed.value
