"""Deterministic compiler: explicit PhysicalSystem topology -> existing GearTrain.

This module owns topology only. It never computes a gear ratio, an RPM, or
a direction itself -- every formula still lives in ``app.physics.gears`` and
``app.physics.train``, used unchanged through
``app.physics.experiments.run_gear_train_experiment``. Given an explicit
``PhysicalSystem`` (shafts, gears, meshes), it determines the single
transmission path from the input shaft to the output shaft (given or
inferred) using only shaft/gear/mesh id relationships -- never the order
shafts, gears, or meshes happen to appear in the input -- and builds the
``GearConnection`` stages for that path.

Milestone 3A scope: only a single, unbranched, acyclic transmission path is
supported. Branches, multiple possible paths, disconnected outputs, and
cycles are all rejected explicitly with ``UnsupportedTopologyError`` rather
than guessed at.
"""

from __future__ import annotations

from collections import defaultdict

from app.models.physics import (
    CompiledTopology,
    Gear,
    GearConnection,
    GearMesh,
    GearTrain,
    PhysicalSystem,
    PhysicalSystemExperimentResult,
    SystemGear,
)
from app.physics.experiments import run_gear_train_experiment

_Edge = tuple[str, SystemGear, SystemGear]  # (neighbor_shaft_id, gear_on_this_shaft, gear_on_neighbor)


class UnsupportedTopologyError(ValueError):
    """Raised when a PhysicalSystem's topology is branched, cyclic,
    disconnected, or otherwise does not reduce to one unambiguous
    transmission path from the input shaft to the output shaft.

    FORGE never guesses a path in these cases -- it rejects explicitly.
    """


def compile_topology(system: PhysicalSystem) -> CompiledTopology:
    """Determine the one transmission path from input to output and build its GearTrain."""
    gear_by_id = {gear.id: gear for gear in system.gears}

    # Exactly one GearMesh may connect any given unordered shaft pair. Two
    # distinct meshes between the same two shafts (e.g. A1<->B1 AND A2<->B2)
    # look identical at the shaft-graph level but are two different candidate
    # transmission stages -- FORGE never guesses which one carries power, so
    # this is checked explicitly, before any traversal, regardless of mesh
    # order or whether BFS would even reach this shaft pair.
    adjacency: dict[str, list[_Edge]] = defaultdict(list)
    shaft_pair_mesh: dict[frozenset[str], GearMesh] = {}
    for mesh in system.meshes:
        gear_a = gear_by_id[mesh.gear_a_id]
        gear_b = gear_by_id[mesh.gear_b_id]

        shaft_pair = frozenset((gear_a.shaft_id, gear_b.shaft_id))
        existing_mesh = shaft_pair_mesh.get(shaft_pair)
        if existing_mesh is not None:
            raise UnsupportedTopologyError(
                f"shafts {gear_a.shaft_id!r} and {gear_b.shaft_id!r} are connected "
                f"by more than one distinct gear mesh "
                f"({existing_mesh.gear_a_id!r}<->{existing_mesh.gear_b_id!r} and "
                f"{mesh.gear_a_id!r}<->{mesh.gear_b_id!r}); ambiguous/redundant "
                "parallel gear meshes between the same shaft pair are not "
                "supported -- which mesh carries power cannot be inferred"
            )
        shaft_pair_mesh[shaft_pair] = mesh

        adjacency[gear_a.shaft_id].append((gear_b.shaft_id, gear_a, gear_b))
        adjacency[gear_b.shaft_id].append((gear_a.shaft_id, gear_b, gear_a))

    parent: dict[str, _Edge] = {}
    visited = {system.input_shaft_id}
    queue = [system.input_shaft_id]

    while queue:
        current = queue.pop(0)
        neighbors = adjacency.get(current, [])
        if len(neighbors) > 2:
            raise UnsupportedTopologyError(
                f"shaft {current!r} meshes with more than two other shafts; "
                "branched topologies are not supported in Milestone 3A"
            )

        arrived_from_shaft_id = parent[current][0] if current in parent else None
        for neighbor_shaft_id, gear_on_current, gear_on_neighbor in neighbors:
            if neighbor_shaft_id == arrived_from_shaft_id:
                continue  # the edge we arrived on -- not a revisit
            if neighbor_shaft_id in visited:
                raise UnsupportedTopologyError(
                    f"shaft {neighbor_shaft_id!r} is reachable by more than one "
                    "path from the input shaft; cyclic topologies are not "
                    "supported in Milestone 3A"
                )
            visited.add(neighbor_shaft_id)
            parent[neighbor_shaft_id] = (current, gear_on_current, gear_on_neighbor)
            queue.append(neighbor_shaft_id)

    output_shaft_id = system.output_shaft_id
    if output_shaft_id is None:
        endpoints = [shaft_id for shaft_id in visited if len(adjacency.get(shaft_id, [])) <= 1]
        if system.input_shaft_id not in endpoints:
            raise UnsupportedTopologyError(
                f"input shaft {system.input_shaft_id!r} is not an end of the "
                "transmission chain, and no output_shaft_id was given, so the "
                "direction of power flow is ambiguous"
            )
        other_endpoints = [shaft_id for shaft_id in endpoints if shaft_id != system.input_shaft_id]
        if len(other_endpoints) != 1:
            raise UnsupportedTopologyError(
                "could not determine a unique output shaft; specify output_shaft_id"
            )
        output_shaft_id = other_endpoints[0]
    elif output_shaft_id == system.input_shaft_id:
        raise UnsupportedTopologyError("output_shaft_id must differ from input_shaft_id")
    elif output_shaft_id not in visited:
        raise UnsupportedTopologyError(
            f"output shaft {output_shaft_id!r} is not reachable from input shaft "
            f"{system.input_shaft_id!r}"
        )

    shaft_path = [output_shaft_id]
    meshes_used: list[GearMesh] = []
    connections: list[GearConnection] = []
    current = output_shaft_id
    while current != system.input_shaft_id:
        previous_shaft_id, gear_on_previous, gear_on_current = parent[current]
        shaft_path.append(previous_shaft_id)
        meshes_used.append(GearMesh(gear_a_id=gear_on_previous.id, gear_b_id=gear_on_current.id))
        connections.append(
            GearConnection(
                driver=Gear(
                    id=gear_on_previous.id,
                    teeth=gear_on_previous.teeth,
                    label=gear_on_previous.label,
                ),
                driven=Gear(
                    id=gear_on_current.id,
                    teeth=gear_on_current.teeth,
                    label=gear_on_current.label,
                ),
            )
        )
        current = previous_shaft_id

    shaft_path.reverse()
    meshes_used.reverse()
    connections.reverse()

    gear_train = GearTrain(input_rpm=system.input_rpm, connections=connections)

    return CompiledTopology(
        input_shaft_id=system.input_shaft_id,
        output_shaft_id=output_shaft_id,
        shaft_path=shaft_path,
        gear_meshes_used=meshes_used,
        gear_train=gear_train,
    )


def run_physical_system_experiment(system: PhysicalSystem) -> PhysicalSystemExperimentResult:
    """Compile `system`'s topology, then run the existing deterministic physics engine.

    Every numeric result comes from
    ``app.physics.experiments.run_gear_train_experiment`` (Milestone 1),
    unchanged -- this function only ever decides *which* gears form the
    transmission path, never *what number* that path produces.
    """
    topology = compile_topology(system)
    experiment = run_gear_train_experiment(topology.gear_train, system.constraints)
    return PhysicalSystemExperimentResult(topology=topology, experiment=experiment)
