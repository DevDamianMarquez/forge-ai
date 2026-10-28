"""A deterministic fixture/mock perception provider.

THIS IS NOT REAL PERCEPTION. Every observation produced here is synthetic,
hand-authored development data, used only to exercise the full
perception -> evidence boundary -> topology -> physics pipeline while real
perception (SAM) is unavailable. Nothing here comes from an image, a vision
model, or any AI call -- every observation's ``source`` is ``DERIVED``,
never ``VISION_MODEL``, so that is unmistakable from the data itself, not
just from comments.

Recognizes only a tiny allowlisted set of fixture ids (``FIXTURE_IDS``) --
never a filesystem path, an image, or arbitrary user input.

A future ``SAMPerceptionProvider`` would implement the same
``PerceptionProvider`` contract (see ``app.perception.providers.base``)
without requiring any change here or downstream.
"""

from __future__ import annotations

from collections.abc import Callable

from app.models.perception import (
    ObservationSource,
    ObservationStatus,
    ObservedValue,
    PerceivedGear,
    PerceivedGearMesh,
    PerceivedShaft,
    PerceptionRequest,
    PerceptionResult,
)

_SOURCE = ObservationSource.DERIVED
_CONFIRMED = ObservationStatus.CONFIRMED


class UnknownFixtureError(ValueError):
    """Raised when a PerceptionRequest names a fixture_id this provider does not know."""


def _value(value, status: ObservationStatus, confidence: float = 1.0) -> ObservedValue:
    return ObservedValue(value=value, source=_SOURCE, confidence=confidence, status=status)


def _shaft(shaft_id: str) -> PerceivedShaft:
    return PerceivedShaft(id=shaft_id, source=_SOURCE, confidence=1.0, status=_CONFIRMED)


def _gear(
    gear_id: str,
    teeth: int,
    shaft_id: str,
    *,
    teeth_status: ObservationStatus = _CONFIRMED,
    teeth_confidence: float = 1.0,
) -> PerceivedGear:
    return PerceivedGear(
        id=gear_id,
        source=_SOURCE,
        confidence=1.0,
        status=_CONFIRMED,
        teeth=_value(teeth, teeth_status, teeth_confidence),
        shaft_id=_value(shaft_id, _CONFIRMED),
    )


def _mesh(gear_a_id: str, gear_b_id: str) -> PerceivedGearMesh:
    return PerceivedGearMesh(
        gear_a_id=gear_a_id, gear_b_id=gear_b_id, source=_SOURCE, confidence=1.0, status=_CONFIRMED
    )


def _simple_gear_pair() -> PerceptionResult:
    """Shaft A: G1 20T -- Shaft B: G2 60T. G1 meshes G2. 1200 RPM in at A, out at B.

    Fully confirmed: exercises the clean success path
    (400 RPM, ratio 3.0, direction reversed).
    """
    return PerceptionResult(
        shafts=[_shaft("shaft-a"), _shaft("shaft-b")],
        gears=[_gear("g1", 20, "shaft-a"), _gear("g2", 60, "shaft-b")],
        meshes=[_mesh("g1", "g2")],
        input_shaft_id=_value("shaft-a", _CONFIRMED),
        input_rpm=_value(1200.0, _CONFIRMED),
        output_shaft_id=_value("shaft-b", _CONFIRMED),
        notes=["fixture:simple_gear_pair -- deterministic synthetic development data, not real perception"],
    )


def _compound_gear_train() -> PerceptionResult:
    """Shaft A: G1 20T -- Shaft B: G2 60T, G3 15T -- Shaft C: G4 45T.

    G1 meshes G2; G3 meshes G4; shaft B rigidly couples G2 and G3. Fully
    confirmed: exercises the compound two-stage success path
    (~133.333333 RPM, ratio 9.0, direction unchanged).
    """
    return PerceptionResult(
        shafts=[_shaft("shaft-a"), _shaft("shaft-b"), _shaft("shaft-c")],
        gears=[
            _gear("g1", 20, "shaft-a"),
            _gear("g2", 60, "shaft-b"),
            _gear("g3", 15, "shaft-b"),
            _gear("g4", 45, "shaft-c"),
        ],
        meshes=[_mesh("g1", "g2"), _mesh("g3", "g4")],
        input_shaft_id=_value("shaft-a", _CONFIRMED),
        input_rpm=_value(1200.0, _CONFIRMED),
        output_shaft_id=_value("shaft-c", _CONFIRMED),
        notes=["fixture:compound_gear_train -- deterministic synthetic development data, not real perception"],
    )


def _uncertain_gear_pair() -> PerceptionResult:
    """Same topology as simple_gear_pair, except G2's tooth count is only
    INFERRED (confidence 0.99) rather than confirmed.

    Demonstrates that high confidence never substitutes for confirmation:
    the evidence boundary must refuse this at the model-build stage, even
    though everything else about the system is fully confirmed.
    """
    return PerceptionResult(
        shafts=[_shaft("shaft-a"), _shaft("shaft-b")],
        gears=[
            _gear("g1", 20, "shaft-a"),
            _gear(
                "g2",
                60,
                "shaft-b",
                teeth_status=ObservationStatus.INFERRED,
                teeth_confidence=0.99,
            ),
        ],
        meshes=[_mesh("g1", "g2")],
        input_shaft_id=_value("shaft-a", _CONFIRMED),
        input_rpm=_value(1200.0, _CONFIRMED),
        output_shaft_id=_value("shaft-b", _CONFIRMED),
        notes=[
            "fixture:uncertain_gear_pair -- deterministic synthetic development data, not real perception",
            "G2 tooth count is intentionally only inferred (confidence 0.99), not confirmed",
        ],
    )


_FIXTURES: dict[str, Callable[[], PerceptionResult]] = {
    "simple_gear_pair": _simple_gear_pair,
    "compound_gear_train": _compound_gear_train,
    "uncertain_gear_pair": _uncertain_gear_pair,
}

FIXTURE_IDS: frozenset[str] = frozenset(_FIXTURES)


class FixturePerceptionProvider:
    """A deterministic, hand-authored mock ``PerceptionProvider``.

    NOT REAL PERCEPTION -- see module docstring. Each call to ``analyze``
    builds brand-new model instances from scratch; nothing is cached or
    shared between calls, so mutating one result can never affect another.
    """

    def analyze(self, request: PerceptionRequest) -> PerceptionResult:
        try:
            factory = _FIXTURES[request.fixture_id]
        except KeyError:
            raise UnknownFixtureError(
                f"unknown fixture_id {request.fixture_id!r}; known fixtures: {sorted(FIXTURE_IDS)}"
            ) from None
        return factory()
