import type {
  FixtureId,
  ObservationStatus,
  PerceivedGear,
  PhysicalPipelineResult,
} from "./forge-types.ts";
import { SCENARIOS } from "./scenarios.ts";

/**
 * "partial" is a presentation-only addition, never a backend value: it
 * means a component's own existence is confirmed, but at least one of its
 * required observations is not. Backend ObservationStatus is unchanged.
 */
export type DisplayStatus = ObservationStatus | "partial";

/**
 * True only when the backend produced real deterministic physics evidence.
 * The UI must gate every rendered RPM/ratio/direction value behind this --
 * never behind a loading flag or an optimistic guess.
 */
export function hasVerifiedPhysics(result: PhysicalPipelineResult | null): boolean {
  return result !== null && result.status === "completed" && result.experiment !== null;
}

/** True when the evidence boundary refused to build a PhysicalSystem at all. */
export function isRefusedAtModelBuild(result: PhysicalPipelineResult | null): boolean {
  return result !== null && result.status === "refused_at_model_build";
}

/** Maps a scenario selector id to the exact backend fixture_id it represents. */
export function resolveFixtureId(scenarioId: FixtureId): FixtureId {
  const match = SCENARIOS.find((scenario) => scenario.id === scenarioId);
  if (!match) {
    throw new Error(`Unknown scenario id: ${scenarioId}`);
  }
  return match.id;
}

/**
 * How a gear should be visually badged. A gear whose own existence is
 * confirmed but whose tooth count or shaft assignment is not must never be
 * badged identically to a fully confirmed gear -- that would visually
 * contradict why the evidence boundary refuses it. This derives a display
 * label only; it never changes which backend status values exist or what
 * the evidence boundary accepts.
 */
export function deriveGearVisualStatus(gear: PerceivedGear): DisplayStatus {
  if (gear.status !== "confirmed") return gear.status;
  if (gear.teeth.status !== "confirmed" || gear.shaft_id.status !== "confirmed") {
    return "partial";
  }
  return "confirmed";
}
