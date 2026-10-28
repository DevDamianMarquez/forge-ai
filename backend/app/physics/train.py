"""Deterministic physics for a multi-stage GearTrain.

Chains the single-mesh functions in ``app.physics.gears`` across every
transmission stage in a train, in order. See ``app.physics.gears`` for the
physics scope and limitations that apply here too, and see ``GearTrain`` in
``app.models.physics`` for the shared-shaft assumption this module relies on.
"""

from __future__ import annotations

from app.models.physics import GearTrain
from app.physics.gears import compute_gear_ratio, compute_output_direction, compute_output_rpm


def compute_gear_train_output_rpm(train: GearTrain) -> float:
    """Chain compute_output_rpm across every transmission stage, in order.

    Each stage's computed output RPM becomes the next stage's input RPM.
    This is only physically correct under GearTrain's shared-shaft
    assumption: a stage's driven gear and the next stage's driver gear are
    assumed to be rigidly fixed to the same shaft, so they turn at the same
    RPM -- there is no mesh, and therefore no RPM change, between them.
    """
    rpm = train.input_rpm
    for connection in train.connections:
        rpm = compute_output_rpm(rpm, connection.driver.teeth, connection.driven.teeth)
    return rpm


def compute_gear_train_ratio(train: GearTrain) -> float:
    """Return the overall speed-reduction ratio: the product of each stage's ratio.

    e.g. a 20T->60T stage (ratio 3) followed by a shared-shaft 15T->45T stage
    (ratio 3) gives an overall ratio of 3 * 3 = 9 (a 9:1 reduction).
    """
    ratio = 1.0
    for connection in train.connections:
        ratio *= compute_gear_ratio(connection.driver.teeth, connection.driven.teeth)
    return ratio


def compute_gear_train_output_direction(train: GearTrain) -> int:
    """Return the output direction after every stage's mesh has reversed it once.

    Each ``GearConnection`` is exactly one external mesh, so it contributes
    exactly one direction reversal. The shared-shaft coupling *between*
    stages is not a mesh and does not reverse direction on its own -- so the
    total number of reversals equals the number of stages (connections),
    not twice that number.
    """
    return compute_output_direction(train.input_direction, len(train.connections))
