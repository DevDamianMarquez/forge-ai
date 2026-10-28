"""The perception provider contract future SAM integration will implement.

Kept intentionally tiny: one method, one input, one output. A future
``SAMPerceptionProvider`` implements this exact ``analyze`` signature with
zero changes required anywhere else -- not in the evidence boundary
(``app.perception.builder``), ``PhysicalSystem``, the topology compiler, the
physics engine, or the pipeline service (``app.services.physical_pipeline``).
This is deliberately not a general computer-vision framework; it is just
enough shape for FORGE's orchestration layer to depend on an interface
instead of a concrete provider.
"""

from __future__ import annotations

from typing import Protocol

from app.models.perception import PerceptionRequest, PerceptionResult


class PerceptionProvider(Protocol):
    """Anything that can turn a PerceptionRequest into a PerceptionResult."""

    def analyze(self, request: PerceptionRequest) -> PerceptionResult: ...
