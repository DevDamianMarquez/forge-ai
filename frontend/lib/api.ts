import type { FixtureId, PhysicalPipelineResult } from "./forge-types.ts";

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
