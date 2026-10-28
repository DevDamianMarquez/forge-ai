import type { FixtureId } from "./forge-types.ts";

/**
 * Display metadata for the backend's known fixtures. These are just labels
 * and short copy for the selector UI -- the authoritative shape of each
 * scenario (gears, shafts, meshes, confidence, status) always comes from
 * the backend's PerceptionResult, never from this file.
 *
 * These are DEMO / SYNTHETIC PERCEPTION SCENARIOS: deterministic,
 * hand-authored development fixtures, not output from SAM, a vision
 * model, or any image analysis.
 */
export interface ScenarioOption {
  id: FixtureId;
  label: string;
  summary: string;
  description: string;
  inputRpm: number;
}

export const SCENARIOS: ScenarioOption[] = [
  {
    id: "simple_gear_pair",
    label: "Simple Gear Pair",
    summary: "20T → 60T",
    description: "One external mesh. Every observation is confirmed.",
    inputRpm: 1200,
  },
  {
    id: "compound_gear_train",
    label: "Compound Gear Train",
    summary: "20T → 60T, 15T → 45T",
    description: "Two meshes sharing a rigid middle shaft. Every observation is confirmed.",
    inputRpm: 1200,
  },
  {
    id: "uncertain_gear_pair",
    label: "Uncertain Gear Pair",
    summary: "AI-inferred tooth count",
    description: "A tooth count is only inferred, not confirmed — verification should be blocked.",
    inputRpm: 1200,
  },
];

export function getScenario(id: FixtureId): ScenarioOption {
  const found = SCENARIOS.find((scenario) => scenario.id === id);
  if (!found) {
    throw new Error(`Unknown scenario id: ${id}`);
  }
  return found;
}
