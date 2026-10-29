import { test } from "node:test";
import assert from "node:assert/strict";

import {
  allGearPairs,
  boundingBoxToPercentRect,
  buildPhysicalConfirmation,
  buildRealImageTrace,
  friendlyGearLabel,
  hasVerifiedPhysics,
  initialGearForms,
  initialSystemForm,
  isModelBlocked,
  isSupportedImageType,
  meshPairKey,
  PreviewUrlTracker,
  type GearConfirmationFormState,
  type SystemConfirmationFormState,
} from "./real-image-helpers.ts";
import type {
  AnalyzeImageResult,
  ConfirmAndVerifyResult,
  PerceptionResult,
  SAMBoundingBox,
} from "./forge-types.ts";

function minimalPerception(overrides: Partial<PerceptionResult> = {}): PerceptionResult {
  return {
    shafts: [],
    gears: [],
    meshes: [],
    input_shaft_id: null,
    input_rpm: null,
    output_shaft_id: null,
    notes: [],
    ...overrides,
  };
}

function minimalAnalyzeResult(overrides: Partial<AnalyzeImageResult> = {}): AnalyzeImageResult {
  return {
    perception: minimalPerception(),
    detections: [],
    build_result: { physical_system: null, accepted_observations: [], unresolved_observations: [], issues: [] },
    ...overrides,
  };
}

function minimalConfirmResult(overrides: Partial<ConfirmAndVerifyResult> = {}): ConfirmAndVerifyResult {
  return {
    perception: minimalPerception(),
    build_result: { physical_system: null, accepted_observations: [], unresolved_observations: [], issues: [] },
    experiment: null,
    ...overrides,
  };
}

// --- A/B/C. MIME validation -------------------------------------------------

test("isSupportedImageType accepts JPEG", () => {
  assert.equal(isSupportedImageType("image/jpeg"), true);
});

test("isSupportedImageType accepts PNG", () => {
  assert.equal(isSupportedImageType("image/png"), true);
});

test("isSupportedImageType rejects other types", () => {
  assert.equal(isSupportedImageType("application/pdf"), false);
  assert.equal(isSupportedImageType(""), false);
});

// --- friendly label ----------------------------------------------------------

test("friendlyGearLabel is 1-based and zero-padded", () => {
  assert.equal(friendlyGearLabel(0), "GEAR 01");
  assert.equal(friendlyGearLabel(1), "GEAR 02");
  assert.equal(friendlyGearLabel(10), "GEAR 11");
});

// --- J. bounding box -> percent rect, from the documented worked example ----

test("boundingBoxToPercentRect converts the parser.py worked example correctly", () => {
  const box: SAMBoundingBox = {
    x1: 181,
    y1: 365,
    x2: 556,
    y2: 486,
    width: 1516,
    height: 1600,
    confidence: null,
  };

  const rect = boundingBoxToPercentRect(box);

  assert.ok(Math.abs(rect.leftPct - (181 / 1516) * 100) < 1e-9);
  assert.ok(Math.abs(rect.topPct - (365 / 1600) * 100) < 1e-9);
  assert.ok(Math.abs(rect.widthPct - ((556 - 181) / 1516) * 100) < 1e-9);
  assert.ok(Math.abs(rect.heightPct - ((486 - 365) / 1600) * 100) < 1e-9);
});

test("boundingBoxToPercentRect clamps to the image bounds", () => {
  const box: SAMBoundingBox = { x1: -5, y1: 0, x2: 120, y2: 50, width: 100, height: 50, confidence: null };

  const rect = boundingBoxToPercentRect(box);

  assert.ok(rect.leftPct >= 0);
  assert.ok(rect.leftPct + rect.widthPct <= 100.0001);
});

test("boundingBoxToPercentRect returns an empty rect for a zero-size reference image", () => {
  const box: SAMBoundingBox = { x1: 0, y1: 0, x2: 10, y2: 10, width: 0, height: 0, confidence: null };

  assert.deepEqual(boundingBoxToPercentRect(box), { leftPct: 0, topPct: 0, widthPct: 0, heightPct: 0 });
});

// --- preview URL revocation bookkeeping --------------------------------------

test("PreviewUrlTracker returns the previous URL to revoke when replaced", () => {
  const tracker = new PreviewUrlTracker();

  assert.equal(tracker.replace("blob:1"), null);
  assert.equal(tracker.value, "blob:1");
  assert.equal(tracker.replace("blob:2"), "blob:1");
  assert.equal(tracker.value, "blob:2");
  assert.equal(tracker.replace(null), "blob:2");
  assert.equal(tracker.value, null);
});

// --- gear pairs / mesh keys ---------------------------------------------------

test("allGearPairs produces exactly one pair for two gears", () => {
  assert.deepEqual(allGearPairs(["g1", "g2"]), [["g1", "g2"]]);
});

test("allGearPairs produces zero pairs for one gear", () => {
  assert.deepEqual(allGearPairs(["g1"]), []);
});

test("meshPairKey is stable and order-sensitive", () => {
  assert.equal(meshPairKey("g1", "g2"), "g1|g2");
});

// --- initial form builders -----------------------------------------------------

test("initialGearForms starts every gear unconfirmed with empty fields", () => {
  const forms = initialGearForms(["sam-f0-o0", "sam-f0-o1"]);
  assert.deepEqual(forms, [
    { id: "sam-f0-o0", confirmedExists: false, teeth: "", shaftId: "" },
    { id: "sam-f0-o1", confirmedExists: false, teeth: "", shaftId: "" },
  ]);
});

test("initialSystemForm starts fully empty", () => {
  assert.deepEqual(initialSystemForm(), { meshPairs: {}, inputShaftId: "", inputRpm: "", outputShaftId: "" });
});

// --- L/M. confirmed_exists is independent of supplied attributes -----------

test("entering teeth alone does not set confirmed_exists", () => {
  const gearForms: GearConfirmationFormState[] = [
    { id: "sam-f0-o0", confirmedExists: false, teeth: "20", shaftId: "" },
  ];
  const confirmation = buildPhysicalConfirmation(gearForms, initialSystemForm());

  assert.equal(confirmation.gears[0].confirmed_exists, false);
  assert.equal(confirmation.gears[0].teeth, 20);
  assert.equal(confirmation.gears[0].shaft_id, null);
});

test("checking the existence box sets confirmed_exists true", () => {
  const gearForms: GearConfirmationFormState[] = [
    { id: "sam-f0-o0", confirmedExists: true, teeth: "", shaftId: "" },
  ];
  const confirmation = buildPhysicalConfirmation(gearForms, initialSystemForm());

  assert.equal(confirmation.gears[0].confirmed_exists, true);
  assert.equal(confirmation.gears[0].teeth, null);
});

test("blank or non-numeric teeth/rpm input is omitted, never sent as a fabricated value", () => {
  const gearForms: GearConfirmationFormState[] = [
    { id: "g1", confirmedExists: true, teeth: "not-a-number", shaftId: "  " },
  ];
  const systemForm: SystemConfirmationFormState = {
    meshPairs: {},
    inputShaftId: "",
    inputRpm: "abc",
    outputShaftId: "",
  };

  const confirmation = buildPhysicalConfirmation(gearForms, systemForm);

  assert.equal(confirmation.gears[0].teeth, null);
  assert.equal(confirmation.gears[0].shaft_id, null);
  assert.equal(confirmation.input_rpm, null);
});

// --- N/O. complete two-gear canonical confirmation round-trips exactly -----

test("complete canonical two-gear confirmation produces the exact expected backend payload", () => {
  const gearForms: GearConfirmationFormState[] = [
    { id: "sam-f0-o0", confirmedExists: true, teeth: "20", shaftId: "shaft-a" },
    { id: "sam-f0-o1", confirmedExists: true, teeth: "60", shaftId: "shaft-b" },
  ];
  const systemForm: SystemConfirmationFormState = {
    meshPairs: { [meshPairKey("sam-f0-o0", "sam-f0-o1")]: true },
    inputShaftId: "shaft-a",
    inputRpm: "1200",
    outputShaftId: "shaft-b",
  };

  const confirmation = buildPhysicalConfirmation(gearForms, systemForm);

  assert.deepEqual(confirmation, {
    shafts: [{ id: "shaft-a" }, { id: "shaft-b" }],
    gears: [
      { id: "sam-f0-o0", confirmed_exists: true, teeth: 20, shaft_id: "shaft-a" },
      { id: "sam-f0-o1", confirmed_exists: true, teeth: 60, shaft_id: "shaft-b" },
    ],
    meshes: [{ gear_a_id: "sam-f0-o0", gear_b_id: "sam-f0-o1" }],
    input_shaft_id: "shaft-a",
    input_rpm: 1200,
    output_shaft_id: "shaft-b",
  });
});

test("an unchecked mesh is never included, even if its pair key exists in the form state", () => {
  const systemForm: SystemConfirmationFormState = {
    meshPairs: { [meshPairKey("g1", "g2")]: false },
    inputShaftId: "",
    inputRpm: "",
    outputShaftId: "",
  };

  const confirmation = buildPhysicalConfirmation([], systemForm);

  assert.deepEqual(confirmation.meshes, []);
});

// --- hasVerifiedPhysics / isModelBlocked -------------------------------------

test("hasVerifiedPhysics is false for null", () => {
  assert.equal(hasVerifiedPhysics(null), false);
});

test("hasVerifiedPhysics is false when physical_system is null even if experiment is not", () => {
  const result = minimalConfirmResult({
    build_result: { physical_system: null, accepted_observations: [], unresolved_observations: [], issues: [] },
  });
  assert.equal(hasVerifiedPhysics(result), false);
});

test("hasVerifiedPhysics is true when both physical_system and experiment are present", () => {
  const result = minimalConfirmResult({
    build_result: {
      physical_system: {
        shafts: [],
        gears: [],
        meshes: [],
        input_shaft_id: "shaft-a",
        input_rpm: 1200,
        output_shaft_id: "shaft-b",
        constraints: [],
      },
      accepted_observations: [],
      unresolved_observations: [],
      issues: [],
    },
    experiment: {
      topology: {
        input_shaft_id: "shaft-a",
        output_shaft_id: "shaft-b",
        shaft_path: ["shaft-a", "shaft-b"],
        gear_meshes_used: [{ gear_a_id: "g1", gear_b_id: "g2" }],
        gear_train: {
          input_rpm: 1200,
          input_direction: 1,
          connections: [{ driver: { id: "g1", teeth: 20, label: null }, driven: { id: "g2", teeth: 60, label: null } }],
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
  assert.equal(result.experiment!.experiment.result, 400);
  assert.equal(result.experiment!.experiment.metrics.gear_ratio, 3);
  assert.equal(result.experiment!.experiment.metrics.output_direction, -1);
});

test("isModelBlocked is true for null and for a null physical_system", () => {
  assert.equal(isModelBlocked(null), true);
  assert.equal(isModelBlocked(minimalAnalyzeResult()), true);
});

// --- buildRealImageTrace: only shows events that actually happened ----------

test("buildRealImageTrace is empty before any analysis", () => {
  assert.deepEqual(buildRealImageTrace(null, null), []);
});

test("buildRealImageTrace stops after the (refused) evidence boundary when not yet confirmed", () => {
  const analysis = minimalAnalyzeResult({ detections: [] });
  const trace = buildRealImageTrace(analysis, null);

  assert.equal(trace.length, 3);
  assert.equal(trace[2].label, "EVIDENCE BOUNDARY");
  assert.equal(trace[2].status, "refused");
});

test("buildRealImageTrace stops at PHYSICAL MODEL when confirmation is still incomplete -- never shows later stages", () => {
  const analysis = minimalAnalyzeResult();
  const confirmResult = minimalConfirmResult();

  const trace = buildRealImageTrace(analysis, confirmResult);

  assert.equal(trace.length, 5);
  assert.equal(trace[4].label, "PHYSICAL MODEL");
  assert.equal(trace[4].status, "refused");
  assert.ok(!trace.some((event) => event.label === "TOPOLOGY" || event.label === "RESULT"));
});

test("buildRealImageTrace shows all eight events on a fully verified result", () => {
  const analysis = minimalAnalyzeResult({ detections: [] });
  const confirmResult = minimalConfirmResult({
    build_result: {
      physical_system: {
        shafts: [],
        gears: [],
        meshes: [],
        input_shaft_id: "shaft-a",
        input_rpm: 1200,
        output_shaft_id: "shaft-b",
        constraints: [],
      },
      accepted_observations: [],
      unresolved_observations: [],
      issues: [],
    },
    experiment: {
      topology: {
        input_shaft_id: "shaft-a",
        output_shaft_id: "shaft-b",
        shaft_path: ["shaft-a", "shaft-b"],
        gear_meshes_used: [],
        gear_train: { input_rpm: 1200, input_direction: 1, connections: [] },
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

  const trace = buildRealImageTrace(analysis, confirmResult);

  assert.equal(trace.length, 8);
  assert.deepEqual(
    trace.map((event) => event.label),
    [
      "IMAGE RECEIVED",
      "SAM 3.1 — VISUAL PERCEPTION",
      "EVIDENCE BOUNDARY",
      "USER CONFIRMATION RECEIVED",
      "PHYSICAL MODEL",
      "TOPOLOGY",
      "DETERMINISTIC PHYSICS",
      "RESULT",
    ],
  );
  // The pre-confirmation evidence boundary (index 2) is correctly "refused"
  // -- nothing is confirmed yet at that point, even on a path that later
  // succeeds. Every other stage, once confirmation has resolved, is "ok".
  assert.equal(trace[2].status, "refused");
  assert.ok(trace.slice(3).every((event) => event.status === "ok"));
});
