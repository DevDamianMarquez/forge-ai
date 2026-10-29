import type {
  AnalyzeImageResult,
  AutonomousRedesignResult,
  ConfirmAndVerifyResult,
  FixtureId,
  GearTrain,
  PerceptionResult,
  PhysicalConfirmation,
  PhysicalPipelineResult,
} from "./forge-types.ts";

const DEFAULT_API_URL = "http://localhost:8000";

/** The FORGE backend's base URL. Configurable via NEXT_PUBLIC_FORGE_API_URL; see .env.example. */
export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_FORGE_API_URL?.trim();
  return configured && configured.length > 0 ? configured : DEFAULT_API_URL;
}

/** A clean, structured error from the FORGE API -- never a raw thrown string. */
export class ForgeApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(ForgeApiError.describe(status, detail));
    this.name = "ForgeApiError";
    this.status = status;
    this.detail = detail;
  }

  private static describe(status: number, detail: unknown): string {
    if (typeof detail === "string" && detail.length > 0) return detail;
    return `FORGE API request failed (HTTP ${status}).`;
  }
}

/**
 * Run the deterministic perception-to-physics pipeline for one fixture.
 *
 * This is the ONLY network call the frontend makes. The backend is the
 * sole source of every physics/perception value rendered afterward --
 * nothing here computes or guesses a result.
 */
export async function runFixturePipeline(
  fixtureId: FixtureId,
  signal?: AbortSignal,
): Promise<PhysicalPipelineResult> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/pipeline/run-fixture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fixture_id: fixtureId }),
    signal,
  });

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    throw new ForgeApiError(response.status, detail);
  }

  return body as PhysicalPipelineResult;
}

/**
 * Upload a real mechanism image to SAM 3.1 and get back its visual
 * detections plus whatever the evidence boundary says is still missing.
 *
 * Sends multipart/form-data -- never base64 -- so the browser sets the
 * Content-Type (with boundary) itself; this function must never set that
 * header manually. This never computes or guesses a physical value: every
 * field on the returned AnalyzeImageResult comes directly from the
 * backend.
 */
export async function analyzeImage(
  image: File,
  prompt: string,
  signal?: AbortSignal,
): Promise<AnalyzeImageResult> {
  const formData = new FormData();
  formData.append("image", image);
  formData.append("prompt", prompt);

  const response = await fetch(`${getApiBaseUrl()}/api/v1/image-analysis/analyze`, {
    method: "POST",
    body: formData,
    signal,
  });

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    throw new ForgeApiError(response.status, detail);
  }

  return body as AnalyzeImageResult;
}

/**
 * Submit explicit USER confirmation (plus the exact PerceptionResult it
 * applies to, round-tripped from analyzeImage) and get back the evidence
 * boundary's decision -- and, only if it succeeded, the backend's
 * deterministic physics result. This function performs no physics and no
 * physical inference itself; it only moves the request/response.
 */
export async function confirmAndVerify(
  perception: PerceptionResult,
  confirmation: PhysicalConfirmation,
  signal?: AbortSignal,
): Promise<ConfirmAndVerifyResult> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/image-analysis/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ perception, confirmation }),
    signal,
  });

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    throw new ForgeApiError(response.status, detail);
  }

  return body as ConfirmAndVerifyResult;
}

/**
 * Launch the bounded autonomous engineering redesign loop: Muse Spark
 * proposes candidate (input_teeth, output_teeth) pairs for a fixed-topology
 * two-gear transmission, and FORGE's deterministic physics/constraint
 * engine is the sole authority on PASS/FAIL. This function performs no
 * physics, no constraint evaluation, and no redesign logic itself -- it
 * only sends the trusted starting design (derived from the already-
 * verified 7A physical state, never hardcoded) and the objective, and
 * returns exactly what the backend computed.
 */
export async function runAutonomousRedesign(
  startingTrain: GearTrain,
  objectiveMaxOutputRpm: number,
  signal?: AbortSignal,
): Promise<AutonomousRedesignResult> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/forge/autonomous-redesign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      starting_train: startingTrain,
      objective_max_output_rpm: objectiveMaxOutputRpm,
    }),
    signal,
  });

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    throw new ForgeApiError(response.status, detail);
  }

  return body as AutonomousRedesignResult;
}
