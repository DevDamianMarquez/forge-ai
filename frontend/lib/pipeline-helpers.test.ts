import { test } from "node:test";
import assert from "node:assert/strict";

import {
  deriveGearVisualStatus,
  hasVerifiedPhysics,
  isRefusedAtModelBuild,
  resolveFixtureId,
} from "./pipeline-helpers.ts";
import type { PerceivedGear, PhysicalPipelineResult } from "./forge-types.ts";

function minimalGear(overrides: Partial<PerceivedGear> = {}): PerceivedGear {
  return {
    id: "g2",
    label: null,
    source: "derived",
    confidence: 1,
    status: "confirmed",
    teeth: { value: 60, source: "derived", confidence: 1, status: "confirmed" },
    shaft_id: { value: "shaft-b", source: "derived", confidence: 1, status: "confirmed" },
    ...overrides,
  };
}

function minimalResult(overrides: Partial<PhysicalPipelineResult>): PhysicalPipelineResult {
  return {
    status: "completed",
    perception: {
      shafts: [],
      gears: [],
      meshes: [],
      input_shaft_id: { value: "shaft-a", source: "derived", confidence: 1, status: "confirmed" },
      input_rpm: { value: 1200, source: "derived", confidence: 1, status: "confirmed" },
      output_shaft_id: null,
      notes: [],
    },
    build_result: {
      physical_system: null,
      accepted_observations: [],
      unresolved_observations: [],
      issues: [],
    },
    experiment: null,
    trace: [],
    ...overrides,
  };
}

test("hasVerifiedPhysics is false when there is no result at all", () => {
  assert.equal(hasVerifiedPhysics(null), false);
});

test("hasVerifiedPhysics is false when the pipeline refused at model build, even if status looks fine", () => {
  const result = minimalResult({ status: "refused_at_model_build", experiment: null });
  assert.equal(hasVerifiedPhysics(result), false);
});

test("hasVerifiedPhysics is true only when completed AND experiment is present", () => {
  const result = minimalResult({
    status: "completed",
    experiment: {
      topology: {
        input_shaft_id: "shaft-a",
        output_shaft_id: "shaft-b",
        shaft_path: ["shaft-a", "shaft-b"],
        gear_meshes_used: [{ gear_a_id: "g1", gear_b_id: "g2" }],
        gear_train: {
          input_rpm: 1200,
          input_direction: 1,
          connections: [
            {
              driver: { id: "g1", teeth: 20, label: null },
              driven: { id: "g2", teeth: 60, label: null },
            },
          ],
        },
      },
      experiment: {
        tool: "compute_gear_train_output_rpm",
        inputs: {},
        result: 400,
        unit: "rpm",
        status: "success",
        error: null,
        metrics: { output_rpm: 400, gear_ratio: 3, output_direction: -1 },
        constraint_results: [],
      },
    },
  });

  assert.equal(hasVerifiedPhysics(result), true);
});

test("isRefusedAtModelBuild is true exactly when status says so", () => {
  assert.equal(isRefusedAtModelBuild(minimalResult({ status: "refused_at_model_build" })), true);
  assert.equal(isRefusedAtModelBuild(minimalResult({ status: "completed" })), false);
  assert.equal(isRefusedAtModelBuild(null), false);
});

test("resolveFixtureId maps every known scenario id to itself", () => {
  assert.equal(resolveFixtureId("simple_gear_pair"), "simple_gear_pair");
  assert.equal(resolveFixtureId("compound_gear_train"), "compound_gear_train");
  assert.equal(resolveFixtureId("uncertain_gear_pair"), "uncertain_gear_pair");
});

test("deriveGearVisualStatus is confirmed when existence, teeth, and shaft are all confirmed", () => {
  assert.equal(deriveGearVisualStatus(minimalGear()), "confirmed");
});

test("deriveGearVisualStatus is partial when existence is confirmed but teeth is inferred", () => {
  const gear = minimalGear({
    teeth: { value: 60, source: "derived", confidence: 0.99, status: "inferred" },
  });
  assert.equal(deriveGearVisualStatus(gear), "partial");
});

test("deriveGearVisualStatus is partial when existence is confirmed but shaft_id is not", () => {
  const gear = minimalGear({
    shaft_id: { value: "shaft-b", source: "derived", confidence: 0.8, status: "unresolved" },
  });
  assert.equal(deriveGearVisualStatus(gear), "partial");
});

test("deriveGearVisualStatus passes through the gear's own status when existence itself is not confirmed", () => {
  const gear = minimalGear({ status: "rejected" });
  assert.equal(deriveGearVisualStatus(gear), "rejected");
});
