import { test } from "node:test";
import assert from "node:assert/strict";

import {
  deriveStartingTrain,
  evidenceWasReturnedAfter,
  hasVerifiedRedesign,
  INITIAL_REDESIGN_UI_STATE,
  parseObjectiveMaxOutputRpm,
  redesignTraceTone,
  withObjectiveChanged,
  withRedesignFailed,
  withRedesignStarted,
  withRedesignSucceeded,
  type RedesignUiState,
} from "./autonomous-redesign-helpers.ts";
import type {
  AutonomousRedesignResult,
  ConfirmAndVerifyResult,
  ExperimentResult,
  GearTrain,
  PerceptionResult,
  RedesignTraceEntry,
} from "./forge-types.ts";

function minimalPerception(): PerceptionResult {
  return {
    shafts: [],
    gears: [],
    meshes: [],
    input_shaft_id: null,
    input_rpm: null,
    output_shaft_id: null,
    notes: [],
  };
}

function minimalExperimentResult(overrides: Partial<ExperimentResult> = {}): ExperimentResult {
  return {
    tool: "compute_gear_train_output_rpm",
    inputs: {},
    result: 400,
    unit: "rpm",
    status: "success",
    error: null,
    metrics: { output_rpm: 400, gear_ratio: 3, output_direction: -1 },
    constraint_results: [],
    ...overrides,
  };
}

function gearTrain(connectionsCount: number): GearTrain {
  return {
    input_rpm: 1200,
    input_direction: 1,
    connections: Array.from({ length: connectionsCount }, (_, index) => ({
      driver: { id: `d${index}`, teeth: 20, label: null },
      driven: { id: `n${index}`, teeth: 60, label: null },
    })),
  };
}

function verifiedConfirmResult(connectionsCount: number): ConfirmAndVerifyResult {
  const train = gearTrain(connectionsCount);
  return {
    perception: minimalPerception(),
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
        gear_train: train,
      },
      experiment: minimalExperimentResult(),
    },
  };
}

function unverifiedConfirmResult(): ConfirmAndVerifyResult {
  return {
    perception: minimalPerception(),
    build_result: { physical_system: null, accepted_observations: [], unresolved_observations: [], issues: [] },
    experiment: null,
  };
}

// --- C/D/E/F. deriving starting_train from verified state, never hardcoded -

test("deriveStartingTrain extracts the exact compiled GearTrain from verified state (C/D/E)", () => {
  const confirmResult = verifiedConfirmResult(1);

  const train = deriveStartingTrain(confirmResult);

  assert.notEqual(train, null);
  assert.equal(train!.input_rpm, 1200); // C: input RPM derived, not hardcoded
  assert.equal(train!.connections[0].driver.teeth, 20); // D: input teeth derived
  assert.equal(train!.connections[0].driven.teeth, 60); // E: output teeth derived
  assert.equal(train, confirmResult.experiment!.topology.gear_train); // same object, nothing reconstructed
});

test("deriveStartingTrain returns null before verification", () => {
  assert.equal(deriveStartingTrain(null), null);
  assert.equal(deriveStartingTrain(unverifiedConfirmResult()), null);
});

test("deriveStartingTrain returns null for an unsupported multi-stage topology", () => {
  const confirmResult = verifiedConfirmResult(2);

  assert.equal(deriveStartingTrain(confirmResult), null);
});

// --- H. objective validation ------------------------------------------------

test("parseObjectiveMaxOutputRpm accepts a positive number", () => {
  assert.equal(parseObjectiveMaxOutputRpm("300"), 300);
  assert.equal(parseObjectiveMaxOutputRpm(" 150.5 "), 150.5);
});

test("parseObjectiveMaxOutputRpm rejects non-numeric, zero, negative, and empty input", () => {
  assert.equal(parseObjectiveMaxOutputRpm(""), null);
  assert.equal(parseObjectiveMaxOutputRpm("abc"), null);
  assert.equal(parseObjectiveMaxOutputRpm("0"), null);
  assert.equal(parseObjectiveMaxOutputRpm("-5"), null);
});

// --- N/O/P/Q. VERIFIED gating ------------------------------------------------

function minimalRedesignResult(overrides: Partial<AutonomousRedesignResult> = {}): AutonomousRedesignResult {
  return {
    objective: "output_rpm <= 300.0",
    status: "exhausted",
    attempts: [],
    accepted_design: null,
    final_experiment: null,
    trace: [],
    engineering_explanation: null,
    ...overrides,
  };
}

test("hasVerifiedRedesign is false for null", () => {
  assert.equal(hasVerifiedRedesign(null), false);
});

test("hasVerifiedRedesign is false for EXHAUSTED (N)", () => {
  assert.equal(hasVerifiedRedesign(minimalRedesignResult({ status: "exhausted" })), false);
});

test("hasVerifiedRedesign is false for MODEL_ERROR (O)", () => {
  assert.equal(hasVerifiedRedesign(minimalRedesignResult({ status: "model_error" })), false);
});

test("hasVerifiedRedesign is false when accepted_design is missing even if status is verified (P)", () => {
  const result = minimalRedesignResult({
    status: "verified",
    accepted_design: null,
    final_experiment: minimalExperimentResult(),
  });
  assert.equal(hasVerifiedRedesign(result), false);
});

test("hasVerifiedRedesign is false when final_experiment is missing even if status is verified (Q)", () => {
  const result = minimalRedesignResult({
    status: "verified",
    accepted_design: { input_teeth: 20, output_teeth: 80 },
    final_experiment: null,
  });
  assert.equal(hasVerifiedRedesign(result), false);
});

test("hasVerifiedRedesign is true only when status=verified AND both fields are present", () => {
  const result = minimalRedesignResult({
    status: "verified",
    accepted_design: { input_teeth: 20, output_teeth: 80 },
    final_experiment: minimalExperimentResult({ result: 300 }),
  });
  assert.equal(hasVerifiedRedesign(result), true);
});

// --- M. evidence-returned stage only when the backend actually sent it -----

test("evidenceWasReturnedAfter is true only for the matching attempt's real trace entry", () => {
  const trace: RedesignTraceEntry[] = [
    { stage: "objective_received", status: "ok", message: "x", attempt_number: null },
    { stage: "candidate_proposed", status: "ok", message: "x", attempt_number: 1 },
    { stage: "physics_evaluated", status: "ok", message: "x", attempt_number: 1 },
    { stage: "constraint_checked", status: "failed", message: "x", attempt_number: 1 },
    { stage: "evidence_returned", status: "ok", message: "x", attempt_number: 1 },
  ];

  assert.equal(evidenceWasReturnedAfter(trace, 1), true);
  assert.equal(evidenceWasReturnedAfter(trace, 2), false);
});

test("evidenceWasReturnedAfter is false for a passing attempt with no evidence-returned entry", () => {
  const trace: RedesignTraceEntry[] = [
    { stage: "candidate_proposed", status: "ok", message: "x", attempt_number: 1 },
    { stage: "physics_evaluated", status: "ok", message: "x", attempt_number: 1 },
    { stage: "constraint_checked", status: "ok", message: "x", attempt_number: 1 },
    { stage: "design_verified", status: "ok", message: "x", attempt_number: 1 },
  ];

  assert.equal(evidenceWasReturnedAfter(trace, 1), false);
});

// --- trace tone mapping: structured fields only, never message text --------

test("redesignTraceTone uses only stage/status, never message content", () => {
  assert.equal(redesignTraceTone({ stage: "objective_received", status: "ok", message: "", attempt_number: null }), "info");
  assert.equal(redesignTraceTone({ stage: "candidate_proposed", status: "ok", message: "", attempt_number: 1 }), "muse");
  assert.equal(redesignTraceTone({ stage: "physics_evaluated", status: "ok", message: "", attempt_number: 1 }), "physics");
  assert.equal(
    redesignTraceTone({ stage: "constraint_checked", status: "ok", message: "anything", attempt_number: 1 }),
    "verified",
  );
  assert.equal(
    redesignTraceTone({ stage: "constraint_checked", status: "failed", message: "anything", attempt_number: 1 }),
    "warning",
  );
  assert.equal(redesignTraceTone({ stage: "design_verified", status: "ok", message: "", attempt_number: 1 }), "verified");
  assert.equal(redesignTraceTone({ stage: "evidence_returned", status: "ok", message: "", attempt_number: 1 }), "warning");
  assert.equal(redesignTraceTone({ stage: "attempts_exhausted", status: "failed", message: "", attempt_number: null }), "warning");
  assert.equal(redesignTraceTone({ stage: "invalid_response", status: "failed", message: "", attempt_number: 1 }), "warning");
  assert.equal(redesignTraceTone({ stage: "model_error", status: "failed", message: "", attempt_number: 1 }), "danger");
});

test("redesignTraceTone for constraint_checked ignores message text claiming the opposite of status", () => {
  // A backend message could theoretically contain the word "PASS" while
  // status is "failed" (or vice versa) -- tone must follow status only.
  const entry: RedesignTraceEntry = {
    stage: "constraint_checked",
    status: "failed",
    message: "output_rpm lte 300.0: actual=400.0 -> trust only `status`, not this text",
    attempt_number: 1,
  };
  assert.equal(redesignTraceTone(entry), "warning");
});

// --- V/W/X. redesign UI state lifecycle (reset-on-change rules) ------------

test("INITIAL_REDESIGN_UI_STATE starts with no result, no error, not running", () => {
  assert.equal(INITIAL_REDESIGN_UI_STATE.result, null);
  assert.equal(INITIAL_REDESIGN_UI_STATE.apiError, null);
  assert.equal(INITIAL_REDESIGN_UI_STATE.isRunning, false);
});

test("withObjectiveChanged always clears a previous result and error (X)", () => {
  const stateWithResult: RedesignUiState = {
    objectiveInput: "300",
    isRunning: false,
    result: minimalRedesignResult({ status: "verified" }),
    apiError: null,
  };

  const next = withObjectiveChanged(stateWithResult, "250");

  assert.equal(next.objectiveInput, "250");
  assert.equal(next.result, null);
  assert.equal(next.apiError, null);
});

test("withRedesignStarted sets isRunning and clears any previous error", () => {
  const next = withRedesignStarted({ ...INITIAL_REDESIGN_UI_STATE, apiError: "previous error" });
  assert.equal(next.isRunning, true);
  assert.equal(next.apiError, null);
});

test("withRedesignSucceeded stores the result and clears running/error", () => {
  const result = minimalRedesignResult({ status: "verified" });
  const next = withRedesignSucceeded({ ...INITIAL_REDESIGN_UI_STATE, isRunning: true }, result);
  assert.equal(next.result, result);
  assert.equal(next.isRunning, false);
  assert.equal(next.apiError, null);
});

test("withRedesignFailed records the error and clears any stale result (Y: distinct from EXHAUSTED)", () => {
  const stale = minimalRedesignResult({ status: "exhausted" });
  const next = withRedesignFailed({ ...INITIAL_REDESIGN_UI_STATE, isRunning: true, result: stale }, "network down");
  assert.equal(next.apiError, "network down");
  assert.equal(next.isRunning, false);
  assert.equal(next.result, null); // never show a stale EXHAUSTED result under a fresh network error
});
