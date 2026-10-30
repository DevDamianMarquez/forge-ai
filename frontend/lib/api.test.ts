import { test } from "node:test";
import assert from "node:assert/strict";

import { analyzeImage, confirmAndVerify, ForgeApiError, runAutonomousRedesign } from "./api.ts";
import type {
  AnalyzeImageResult,
  AutonomousRedesignResult,
  ConfirmAndVerifyResult,
  GearTrain,
  PerceptionResult,
  PhysicalConfirmation,
} from "./forge-types.ts";

/**
 * These tests mock the global `fetch` so no real network call -- and
 * certainly no real SAM/Meta call -- is ever made. Node's built-in fetch,
 * FormData, File, and Response globals make this possible without jsdom
 * or any browser.
 */

function withMockedFetch<T>(
  handler: (url: string, init: RequestInit | undefined) => Response,
  run: () => Promise<T>,
): Promise<T> {
  const original = globalThis.fetch;
  globalThis.fetch = (async (url: string | URL, init?: RequestInit) => handler(String(url), init)) as typeof fetch;
  return run().finally(() => {
    globalThis.fetch = original;
  });
}

function minimalAnalyzeResult(): AnalyzeImageResult {
  return {
    perception: { shafts: [], gears: [], meshes: [], input_shaft_id: null, input_rpm: null, output_shaft_id: null, notes: [] },
    detections: [],
    build_result: { physical_system: null, accepted_observations: [], unresolved_observations: [], issues: [] },
  };
}

function minimalConfirmResult(): ConfirmAndVerifyResult {
  return {
    perception: { shafts: [], gears: [], meshes: [], input_shaft_id: null, input_rpm: null, output_shaft_id: null, notes: [] },
    build_result: { physical_system: null, accepted_observations: [], unresolved_observations: [], issues: [] },
    experiment: null,
  };
}

// --- E. analyze request uses multipart/form-data, not base64/JSON ----------

test("analyzeImage sends a multipart/form-data body with the image and prompt fields", async () => {
  let capturedUrl = "";
  let capturedInit: RequestInit | undefined;

  const file = new File(["fake-jpeg-bytes"], "photo.jpg", { type: "image/jpeg" });

  const result = await withMockedFetch(
    (url, init) => {
      capturedUrl = url;
      capturedInit = init;
      return new Response(JSON.stringify(minimalAnalyzeResult()), { status: 200 });
    },
    () => analyzeImage(file, "gear"),
  );

  assert.ok(capturedUrl.endsWith("/api/v1/image-analysis/analyze"));
  assert.ok(capturedInit?.body instanceof FormData);
  const body = capturedInit!.body as FormData;
  assert.equal(body.get("prompt"), "gear");
  const uploaded = body.get("image");
  assert.ok(uploaded instanceof File);
  assert.equal((uploaded as File).type, "image/jpeg");
  // No Content-Type header set manually -- fetch/the browser must set the
  // multipart boundary itself. No base64 anywhere in the request.
  assert.equal(capturedInit?.headers, undefined);
  assert.deepEqual(result, minimalAnalyzeResult());
});

test("analyzeImage throws a ForgeApiError with the structured detail on a non-OK response", async () => {
  const file = new File(["bytes"], "photo.png", { type: "image/png" });

  await assert.rejects(
    () =>
      withMockedFetch(
        () => new Response(JSON.stringify({ detail: "Unsupported image content type" }), { status: 415 }),
        () => analyzeImage(file, "gear"),
      ),
    (error: unknown) => {
      assert.ok(error instanceof ForgeApiError);
      assert.equal(error.status, 415);
      assert.equal(error.message, "Unsupported image content type");
      return true;
    },
  );
});

// --- N. confirm payload round-trips the exact original PerceptionResult ----

test("confirmAndVerify sends perception and confirmation as JSON, unmodified", async () => {
  const perception: PerceptionResult = {
    shafts: [{ id: "shaft-a", label: null, source: "vision_model", confidence: 1, status: "observed" }],
    gears: [],
    meshes: [],
    input_shaft_id: null,
    input_rpm: null,
    output_shaft_id: null,
    notes: ["came from analyze"],
  };
  const confirmation: PhysicalConfirmation = {
    shafts: [{ id: "shaft-a" }],
    gears: [{ id: "g1", confirmed_exists: true, teeth: 20, shaft_id: "shaft-a" }],
    meshes: [],
    input_shaft_id: "shaft-a",
    input_rpm: 1200,
    output_shaft_id: null,
  };

  let capturedInit: RequestInit | undefined;
  await withMockedFetch(
    (_url, init) => {
      capturedInit = init;
      return new Response(JSON.stringify(minimalConfirmResult()), { status: 200 });
    },
    () => confirmAndVerify(perception, confirmation),
  );

  assert.equal(capturedInit?.method, "POST");
  assert.equal((capturedInit?.headers as Record<string, string>)["Content-Type"], "application/json");
  const sentBody = JSON.parse(capturedInit!.body as string);
  assert.deepEqual(sentBody.perception, perception);
  assert.deepEqual(sentBody.confirmation, confirmation);
});

test("confirmAndVerify throws ForgeApiError on refusal responses (e.g. unknown gear id)", async () => {
  await assert.rejects(
    () =>
      withMockedFetch(
        () => new Response(JSON.stringify({ detail: "confirmation references gear id 'bad'" }), { status: 422 }),
        () =>
          confirmAndVerify(
            { shafts: [], gears: [], meshes: [], input_shaft_id: null, input_rpm: null, output_shaft_id: null, notes: [] },
            { shafts: [], gears: [{ id: "bad", confirmed_exists: true }], meshes: [] },
          ),
      ),
    (error: unknown) => {
      assert.ok(error instanceof ForgeApiError);
      assert.equal(error.status, 422);
      return true;
    },
  );
});

// --- G. autonomous-redesign request sends the exact starting_train/objective

function minimalRedesignResult(): AutonomousRedesignResult {
  return {
    objective: "output_rpm <= 300.0",
    status: "exhausted",
    attempts: [],
    accepted_design: null,
    final_experiment: null,
    trace: [],
    engineering_explanation: null,
  };
}

test("runAutonomousRedesign sends starting_train and objective_max_output_rpm as JSON", async () => {
  const startingTrain: GearTrain = {
    input_rpm: 1200,
    input_direction: 1,
    connections: [
      { driver: { id: "input", teeth: 20, label: null }, driven: { id: "output", teeth: 60, label: null } },
    ],
  };

  let capturedUrl = "";
  let capturedInit: RequestInit | undefined;
  await withMockedFetch(
    (url, init) => {
      capturedUrl = url;
      capturedInit = init;
      return new Response(JSON.stringify(minimalRedesignResult()), { status: 200 });
    },
    () => runAutonomousRedesign(startingTrain, 300),
  );

  assert.ok(capturedUrl.endsWith("/api/v1/forge/autonomous-redesign"));
  assert.equal(capturedInit?.method, "POST");
  assert.equal((capturedInit?.headers as Record<string, string>)["Content-Type"], "application/json");
  const sentBody = JSON.parse(capturedInit!.body as string);
  assert.deepEqual(sentBody.starting_train, startingTrain);
  assert.equal(sentBody.objective_max_output_rpm, 300);
  // No physics/PASS-FAIL computed client-side -- the request carries only
  // the trusted starting design and the objective, nothing derived.
  assert.deepEqual(Object.keys(sentBody).sort(), ["objective_max_output_rpm", "starting_train"]);
});

test("runAutonomousRedesign returns the exact backend response unmodified", async () => {
  const backendResult: AutonomousRedesignResult = {
    objective: "output_rpm <= 300.0",
    status: "verified",
    attempts: [
      {
        attempt_number: 1,
        candidate: { input_teeth: 20, output_teeth: 80 },
        experiment: {
          tool: "compute_gear_train_output_rpm",
          inputs: {},
          result: 300,
          unit: "rpm",
          status: "success",
          error: null,
          metrics: { output_rpm: 300, gear_ratio: 4, output_direction: -1 },
          constraint_results: [],
        },
        status: "passed",
        error: null,
      },
    ],
    accepted_design: { input_teeth: 20, output_teeth: 80 },
    final_experiment: null,
    trace: [],
    engineering_explanation: "Final design satisfies the objective.",
  };

  const result = await withMockedFetch(
    () => new Response(JSON.stringify(backendResult), { status: 200 }),
    () =>
      runAutonomousRedesign(
        { input_rpm: 1200, input_direction: 1, connections: [] },
        300,
      ),
  );

  assert.deepEqual(result, backendResult);
});

test("runAutonomousRedesign throws ForgeApiError on an unsupported-topology refusal", async () => {
  await assert.rejects(
    () =>
      withMockedFetch(
        () =>
          new Response(
            JSON.stringify({ detail: "Milestone 7B.1 only supports a single external two-gear mesh" }),
            { status: 422 },
          ),
        () =>
          runAutonomousRedesign(
            { input_rpm: 1200, input_direction: 1, connections: [] },
            300,
          ),
      ),
    (error: unknown) => {
      assert.ok(error instanceof ForgeApiError);
      assert.equal(error.status, 422);
      return true;
    },
  );
});
