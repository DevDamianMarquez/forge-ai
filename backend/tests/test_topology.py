"""Tests for the explicit PhysicalSystem topology model and its compiler.

Covers PhysicalSystem's own validation (unique ids, references, self-mesh,
same-shaft mesh, duplicate mesh) and app.physics.topology's graph-based
compilation into the existing Milestone 1 GearTrain -- including rejection
of branches, cycles, disconnected outputs, and ambiguous paths.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.physics import (
    Constraint,
    ConstraintMetric,
    ConstraintOperator,
    ExperimentStatus,
    GearMesh,
    PhysicalSystem,
    Shaft,
    SystemGear,
)
from app.physics.topology import UnsupportedTopologyError, compile_topology, run_physical_system_experiment


def _simple_pair_system(**overrides) -> PhysicalSystem:
    defaults = dict(
        shafts=[Shaft(id="shaft-a"), Shaft(id="shaft-b")],
        gears=[
            SystemGear(id="gear1", teeth=20, shaft_id="shaft-a"),
            SystemGear(id="gear2", teeth=60, shaft_id="shaft-b"),
        ],
        meshes=[GearMesh(gear_a_id="gear1", gear_b_id="gear2")],
        input_shaft_id="shaft-a",
        input_rpm=1200,
    )
    defaults.update(overrides)
    return PhysicalSystem(**defaults)


def _compound_train_system(**overrides) -> PhysicalSystem:
    # Shaft A: Gear1 20T
    # Shaft B: Gear2 60T, Gear3 15T (same shaft -- rigidly coupled)
    # Shaft C: Gear4 45T
    # Meshes: Gear1-Gear2, Gear3-Gear4
    defaults = dict(
        shafts=[Shaft(id="shaft-a"), Shaft(id="shaft-b"), Shaft(id="shaft-c")],
        gears=[
            SystemGear(id="gear1", teeth=20, shaft_id="shaft-a"),
            SystemGear(id="gear2", teeth=60, shaft_id="shaft-b"),
            SystemGear(id="gear3", teeth=15, shaft_id="shaft-b"),
            SystemGear(id="gear4", teeth=45, shaft_id="shaft-c"),
        ],
        meshes=[
            GearMesh(gear_a_id="gear1", gear_b_id="gear2"),
            GearMesh(gear_a_id="gear3", gear_b_id="gear4"),
        ],
        input_shaft_id="shaft-a",
        input_rpm=1200,
    )
    defaults.update(overrides)
    return PhysicalSystem(**defaults)


# --- A. Simple pair -----------------------------------------------------


def test_simple_pair_compiles_to_canonical_400_rpm():
    system = _simple_pair_system()

    topology = compile_topology(system)

    assert topology.input_shaft_id == "shaft-a"
    assert topology.output_shaft_id == "shaft-b"
    assert topology.shaft_path == ["shaft-a", "shaft-b"]
    assert len(topology.gear_train.connections) == 1
    assert topology.gear_train.connections[0].driver.teeth == 20
    assert topology.gear_train.connections[0].driven.teeth == 60


def test_simple_pair_experiment_result_is_400_rpm_ratio_3_direction_reversed():
    system = _simple_pair_system()

    result = run_physical_system_experiment(system)

    assert result.experiment.status == ExperimentStatus.SUCCESS
    assert result.experiment.result == pytest.approx(400.0)
    assert result.experiment.metrics["gear_ratio"] == pytest.approx(3.0)
    assert result.experiment.metrics["output_direction"] == pytest.approx(-1.0)


# --- B. Compound train ---------------------------------------------------


def test_compound_train_compiles_to_two_stages():
    system = _compound_train_system()

    topology = compile_topology(system)

    assert topology.shaft_path == ["shaft-a", "shaft-b", "shaft-c"]
    assert topology.output_shaft_id == "shaft-c"
    assert len(topology.gear_meshes_used) == 2
    assert len(topology.gear_train.connections) == 2


def test_compound_train_experiment_result_matches_9_to_1_reduction():
    system = _compound_train_system()

    result = run_physical_system_experiment(system)

    assert result.experiment.status == ExperimentStatus.SUCCESS
    assert result.experiment.result == pytest.approx(1200 * 20 / 60 * 15 / 45)
    assert result.experiment.metrics["gear_ratio"] == pytest.approx(9.0)
    # Two actual gear meshes -> two reversals -> direction unchanged.
    assert result.experiment.metrics["output_direction"] == pytest.approx(1.0)


# --- C. Same-shaft behavior: no synthesized third stage ------------------


def test_same_shaft_gears_produce_no_extra_stage_or_reversal():
    system = _compound_train_system()

    topology = compile_topology(system)

    # Exactly the two real meshes -- nothing synthesized between gear2 (60T)
    # and gear3 (15T) just because they share shaft-b.
    assert len(topology.gear_train.connections) == 2
    mesh_gear_ids = {frozenset((m.gear_a_id, m.gear_b_id)) for m in topology.gear_meshes_used}
    assert frozenset(("gear2", "gear3")) not in mesh_gear_ids


# --- D-G. PhysicalSystem's own validation ---------------------------------


def test_gear_referencing_nonexistent_shaft_is_rejected():
    with pytest.raises(ValidationError):
        _simple_pair_system(
            gears=[
                SystemGear(id="gear1", teeth=20, shaft_id="shaft-a"),
                SystemGear(id="gear2", teeth=60, shaft_id="no-such-shaft"),
            ]
        )


def test_mesh_referencing_nonexistent_gear_is_rejected():
    with pytest.raises(ValidationError):
        _simple_pair_system(meshes=[GearMesh(gear_a_id="gear1", gear_b_id="ghost-gear")])


def test_same_shaft_gears_attempting_to_mesh_are_rejected():
    with pytest.raises(ValidationError):
        PhysicalSystem(
            shafts=[Shaft(id="shaft-a")],
            gears=[
                SystemGear(id="gear1", teeth=20, shaft_id="shaft-a"),
                SystemGear(id="gear2", teeth=60, shaft_id="shaft-a"),
            ],
            meshes=[GearMesh(gear_a_id="gear1", gear_b_id="gear2")],
            input_shaft_id="shaft-a",
            input_rpm=1200,
        )


def test_gear_cannot_mesh_with_itself():
    with pytest.raises(ValidationError):
        _simple_pair_system(meshes=[GearMesh(gear_a_id="gear1", gear_b_id="gear1")])


def test_duplicate_mesh_a_b_is_rejected():
    with pytest.raises(ValidationError):
        _simple_pair_system(
            meshes=[
                GearMesh(gear_a_id="gear1", gear_b_id="gear2"),
                GearMesh(gear_a_id="gear1", gear_b_id="gear2"),
            ]
        )


def test_duplicate_mesh_b_a_reversed_is_also_rejected():
    with pytest.raises(ValidationError):
        _simple_pair_system(
            meshes=[
                GearMesh(gear_a_id="gear1", gear_b_id="gear2"),
                GearMesh(gear_a_id="gear2", gear_b_id="gear1"),
            ]
        )


def test_duplicate_shaft_ids_are_rejected():
    with pytest.raises(ValidationError):
        _simple_pair_system(shafts=[Shaft(id="shaft-a"), Shaft(id="shaft-a")])


def test_duplicate_gear_ids_are_rejected():
    with pytest.raises(ValidationError):
        _simple_pair_system(
            gears=[
                SystemGear(id="gear1", teeth=20, shaft_id="shaft-a"),
                SystemGear(id="gear1", teeth=60, shaft_id="shaft-b"),
            ]
        )


def test_unknown_input_shaft_id_is_rejected():
    with pytest.raises(ValidationError):
        _simple_pair_system(input_shaft_id="no-such-shaft")


def test_unknown_output_shaft_id_is_rejected_at_the_model_level():
    with pytest.raises(ValidationError):
        _simple_pair_system(output_shaft_id="no-such-shaft")


def test_non_positive_teeth_is_rejected():
    with pytest.raises(ValidationError):
        _simple_pair_system(
            gears=[
                SystemGear(id="gear1", teeth=0, shaft_id="shaft-a"),
                SystemGear(id="gear2", teeth=60, shaft_id="shaft-b"),
            ]
        )


def test_non_positive_input_rpm_is_rejected():
    with pytest.raises(ValidationError):
        _simple_pair_system(input_rpm=0)


# --- H. Disconnected output shaft (exists, but unreachable) --------------


def test_disconnected_output_shaft_is_rejected_by_the_compiler():
    system = _simple_pair_system(
        shafts=[Shaft(id="shaft-a"), Shaft(id="shaft-b"), Shaft(id="shaft-isolated")],
        output_shaft_id="shaft-isolated",
    )

    with pytest.raises(UnsupportedTopologyError):
        compile_topology(system)


# --- I. Branched topology -------------------------------------------------


def test_branched_topology_is_rejected():
    # Shaft B has three gears, each meshing a different other shaft: a
    # genuine branch, not a simple chain.
    system = PhysicalSystem(
        shafts=[Shaft(id="a"), Shaft(id="b"), Shaft(id="c"), Shaft(id="d")],
        gears=[
            SystemGear(id="g1", teeth=20, shaft_id="a"),
            SystemGear(id="g2", teeth=20, shaft_id="b"),
            SystemGear(id="g3", teeth=20, shaft_id="b"),
            SystemGear(id="g4", teeth=20, shaft_id="c"),
            SystemGear(id="g5", teeth=20, shaft_id="b"),
            SystemGear(id="g6", teeth=20, shaft_id="d"),
        ],
        meshes=[
            GearMesh(gear_a_id="g1", gear_b_id="g2"),
            GearMesh(gear_a_id="g3", gear_b_id="g4"),
            GearMesh(gear_a_id="g5", gear_b_id="g6"),
        ],
        input_shaft_id="a",
        input_rpm=1000,
    )

    with pytest.raises(UnsupportedTopologyError):
        compile_topology(system)


# --- J. Multiple possible paths (input is a middle shaft) ----------------


def test_ambiguous_direction_when_input_is_a_middle_shaft_and_no_output_given():
    # a - b - c, input at the middle shaft b, no output_shaft_id: power could
    # flow toward a or toward c -- ambiguous.
    system = PhysicalSystem(
        shafts=[Shaft(id="a"), Shaft(id="b"), Shaft(id="c")],
        gears=[
            SystemGear(id="g1", teeth=20, shaft_id="a"),
            SystemGear(id="g2", teeth=40, shaft_id="b"),
            SystemGear(id="g3", teeth=10, shaft_id="b"),
            SystemGear(id="g4", teeth=30, shaft_id="c"),
        ],
        meshes=[
            GearMesh(gear_a_id="g1", gear_b_id="g2"),
            GearMesh(gear_a_id="g3", gear_b_id="g4"),
        ],
        input_shaft_id="b",
        input_rpm=1000,
    )

    with pytest.raises(UnsupportedTopologyError):
        compile_topology(system)


def test_middle_shaft_input_is_fine_when_output_is_explicit():
    # Same shape as above, but output_shaft_id disambiguates the direction,
    # so it is no longer ambiguous.
    system = PhysicalSystem(
        shafts=[Shaft(id="a"), Shaft(id="b"), Shaft(id="c")],
        gears=[
            SystemGear(id="g1", teeth=20, shaft_id="a"),
            SystemGear(id="g2", teeth=40, shaft_id="b"),
            SystemGear(id="g3", teeth=10, shaft_id="b"),
            SystemGear(id="g4", teeth=30, shaft_id="c"),
        ],
        meshes=[
            GearMesh(gear_a_id="g1", gear_b_id="g2"),
            GearMesh(gear_a_id="g3", gear_b_id="g4"),
        ],
        input_shaft_id="b",
        input_rpm=1000,
        output_shaft_id="c",
    )

    topology = compile_topology(system)

    assert topology.shaft_path == ["b", "c"]
    assert len(topology.gear_train.connections) == 1


# --- K. Cycle --------------------------------------------------------------


def test_cycle_is_rejected():
    # a - b - c - a: a closed loop.
    system = PhysicalSystem(
        shafts=[Shaft(id="a"), Shaft(id="b"), Shaft(id="c")],
        gears=[
            SystemGear(id="g1", teeth=20, shaft_id="a"),
            SystemGear(id="g2", teeth=20, shaft_id="b"),
            SystemGear(id="g3", teeth=20, shaft_id="b"),
            SystemGear(id="g4", teeth=20, shaft_id="c"),
            SystemGear(id="g5", teeth=20, shaft_id="c"),
            SystemGear(id="g6", teeth=20, shaft_id="a"),
        ],
        meshes=[
            GearMesh(gear_a_id="g1", gear_b_id="g2"),
            GearMesh(gear_a_id="g3", gear_b_id="g4"),
            GearMesh(gear_a_id="g5", gear_b_id="g6"),
        ],
        input_shaft_id="a",
        input_rpm=1000,
    )

    with pytest.raises(UnsupportedTopologyError):
        compile_topology(system)


# --- Constraints pass through to the underlying experiment ---------------


def test_constraint_on_physical_system_is_evaluated_and_passes():
    system = _simple_pair_system(
        constraints=[
            Constraint(
                name="max-output-rpm",
                metric=ConstraintMetric.OUTPUT_RPM,
                operator=ConstraintOperator.LTE,
                value=500,
            )
        ]
    )

    result = run_physical_system_experiment(system)

    assert result.experiment.constraint_results[0].passed is True


# --- Part 9: must use graph relationships, never list order --------------


def test_shuffled_order_does_not_change_the_compiled_path():
    # Same compound train as test B, but every list is deliberately
    # supplied out of physical order: output shaft listed first, meshes in
    # reverse, gears scrambled.
    system = PhysicalSystem(
        shafts=[Shaft(id="shaft-c"), Shaft(id="shaft-a"), Shaft(id="shaft-b")],
        gears=[
            SystemGear(id="gear4", teeth=45, shaft_id="shaft-c"),
            SystemGear(id="gear3", teeth=15, shaft_id="shaft-b"),
            SystemGear(id="gear1", teeth=20, shaft_id="shaft-a"),
            SystemGear(id="gear2", teeth=60, shaft_id="shaft-b"),
        ],
        meshes=[
            GearMesh(gear_a_id="gear4", gear_b_id="gear3"),
            GearMesh(gear_a_id="gear2", gear_b_id="gear1"),
        ],
        input_shaft_id="shaft-a",
        input_rpm=1200,
    )

    result = run_physical_system_experiment(system)

    assert result.topology.shaft_path == ["shaft-a", "shaft-b", "shaft-c"]
    assert result.experiment.result == pytest.approx(1200 * 20 / 60 * 15 / 45)
    assert result.experiment.metrics["gear_ratio"] == pytest.approx(9.0)


# --- Parallel/ambiguous meshes between the same shaft pair ---------------
#
# Shaft A: GearA1 20T, GearA2 30T
# Shaft B: GearB1 60T, GearB2 90T
# Meshes: A1<->B1, A2<->B2
#
# At the shaft-graph level this looks like just A<->B, but there are two
# distinct physical gear meshes that could define the stage. FORGE must
# reject this outright, never pick one.


def _parallel_mesh_system(mesh_order: list[tuple[str, str]]) -> PhysicalSystem:
    return PhysicalSystem(
        shafts=[Shaft(id="shaft-a"), Shaft(id="shaft-b")],
        gears=[
            SystemGear(id="gear-a1", teeth=20, shaft_id="shaft-a"),
            SystemGear(id="gear-a2", teeth=30, shaft_id="shaft-a"),
            SystemGear(id="gear-b1", teeth=60, shaft_id="shaft-b"),
            SystemGear(id="gear-b2", teeth=90, shaft_id="shaft-b"),
        ],
        meshes=[GearMesh(gear_a_id=a, gear_b_id=b) for a, b in mesh_order],
        input_shaft_id="shaft-a",
        input_rpm=1200,
    )


def test_two_distinct_meshes_between_same_shaft_pair_are_rejected():
    system = _parallel_mesh_system([("gear-a1", "gear-b1"), ("gear-a2", "gear-b2")])

    with pytest.raises(UnsupportedTopologyError):
        compile_topology(system)


def test_reversed_mesh_order_produces_the_same_rejection():
    system = _parallel_mesh_system([("gear-a2", "gear-b2"), ("gear-a1", "gear-b1")])

    with pytest.raises(UnsupportedTopologyError):
        compile_topology(system)


def test_parallel_mesh_rejection_is_exactly_unsupported_topology_error():
    system = _parallel_mesh_system([("gear-a1", "gear-b1"), ("gear-a2", "gear-b2")])

    with pytest.raises(UnsupportedTopologyError) as exc_info:
        compile_topology(system)

    assert isinstance(exc_info.value, UnsupportedTopologyError)


def test_parallel_mesh_error_message_names_the_shafts_and_ambiguity():
    system = _parallel_mesh_system([("gear-a1", "gear-b1"), ("gear-a2", "gear-b2")])

    with pytest.raises(UnsupportedTopologyError) as exc_info:
        compile_topology(system)

    message = str(exc_info.value).lower()
    assert "shaft-a" in message
    assert "shaft-b" in message
    assert "parallel" in message or "ambiguous" in message or "redundant" in message


def test_single_mesh_between_a_shaft_pair_still_compiles_normally():
    # Regression check: only one of the two candidate meshes present --
    # this must still work exactly as a normal pair.
    system = _parallel_mesh_system([("gear-a1", "gear-b1")])

    topology = compile_topology(system)

    assert topology.shaft_path == ["shaft-a", "shaft-b"]
    assert len(topology.gear_train.connections) == 1
    assert topology.gear_train.connections[0].driver.teeth == 20
    assert topology.gear_train.connections[0].driven.teeth == 60


def test_canonical_compound_train_still_correct_after_parallel_mesh_fix():
    system = _compound_train_system()

    result = run_physical_system_experiment(system)

    assert result.experiment.status == ExperimentStatus.SUCCESS
    assert result.experiment.result == pytest.approx(133.333333, rel=1e-6)
    assert result.experiment.metrics["gear_ratio"] == pytest.approx(9.0)
    assert result.experiment.metrics["output_direction"] == pytest.approx(1.0)
