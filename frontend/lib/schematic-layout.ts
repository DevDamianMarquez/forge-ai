import type { PhysicalSystem } from "./forge-types.ts";

/**
 * Derives 2D schematic layout positions from backend data only (shaft list,
 * gear list with shaft_id, mesh list, and optionally the compiled
 * shaft_path for left-to-right ordering). No fixture-specific hardcoding --
 * this generically handles any number of shafts, any number of gears per
 * shaft, and any number of meshes, which is all that's needed for FORGE's
 * currently supported idealized-spur-gear systems. Not a general CAD
 * renderer.
 */

export interface SchematicShaft {
  id: string;
  /** Normalized horizontal position, 0 (leftmost) to 1 (rightmost). */
  x: number;
  gearIds: string[];
}

export interface SchematicGear {
  id: string;
  teeth: number;
  shaftId: string;
  label: string | null;
}

export interface SchematicMesh {
  gearAId: string;
  gearBId: string;
}

export interface SchematicLayout {
  shafts: SchematicShaft[];
  gears: Record<string, SchematicGear>;
  meshes: SchematicMesh[];
}

export function buildSchematicLayout(
  system: PhysicalSystem,
  shaftOrder?: string[],
): SchematicLayout {
  const knownShaftIds = new Set(system.shafts.map((shaft) => shaft.id));
  const orderedShaftIds =
    shaftOrder && shaftOrder.length > 0
      ? shaftOrder.filter((id) => knownShaftIds.has(id))
      : system.shafts.map((shaft) => shaft.id);

  const gearIdsByShaft = new Map<string, string[]>();
  for (const shaftId of orderedShaftIds) gearIdsByShaft.set(shaftId, []);
  for (const gear of system.gears) {
    const list = gearIdsByShaft.get(gear.shaft_id);
    if (list) {
      list.push(gear.id);
    } else {
      gearIdsByShaft.set(gear.shaft_id, [gear.id]);
    }
  }

  const shaftCount = orderedShaftIds.length;
  const shafts: SchematicShaft[] = orderedShaftIds.map((id, index) => ({
    id,
    x: shaftCount <= 1 ? 0.5 : index / (shaftCount - 1),
    gearIds: gearIdsByShaft.get(id) ?? [],
  }));

  const gears: Record<string, SchematicGear> = {};
  for (const gear of system.gears) {
    gears[gear.id] = {
      id: gear.id,
      teeth: gear.teeth,
      shaftId: gear.shaft_id,
      label: gear.label,
    };
  }

  const meshes: SchematicMesh[] = system.meshes.map((mesh) => ({
    gearAId: mesh.gear_a_id,
    gearBId: mesh.gear_b_id,
  }));

  return { shafts, gears, meshes };
}

/** A gear's relative radius for display, clamped so very large tooth counts stay on-canvas. */
export function gearDisplayRadius(teeth: number): number {
  const base = Math.sqrt(teeth) * 5.6;
  return Math.min(Math.max(base, 26), 62);
}
