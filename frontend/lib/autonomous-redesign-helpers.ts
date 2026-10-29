/**
 * Pure, backend-data-only logic for Milestone 7B.2's autonomous redesign
 * UI. Nothing here computes a physical value or a PASS/FAIL decision --
 * output RPM, gear ratio, direction, and constraint status always come
 * from the backend's AutonomousRedesignResult. Everything here is either
 * (a) deriving the trusted starting_train from the already-verified 7A
 * physical state (never reconstructed from user-entered text, never
 * hardcoded), (b) validating the objective input field, or (c) pure state
 * transitions for the redesign UI's own lifecycle (reset-on-change rules).
 */

import type {
  AutonomousRedesignResult,
  ConfirmAndVerifyResult,
  GearTrain,
  RedesignTraceEntry,
} from "./forge-types.ts";
import { hasVerifiedPhysics } from "./real-image-helpers.ts";

/**
 * Extracts the single-mesh GearTrain the verified physical system already
 * compiled to (the backend's own CompiledTopology.gear_train from the 7A
 * confirm/verify step), for use as autonomous-redesign's trusted
 * starting_train. Never reconstructed from confirmation form text, and
 * never hardcoded -- always the backend's own already-computed topology.
 *
 * Returns null when there is no verified physics yet, OR when the
 * verified system is not a single external two-gear mesh (the only
 * topology Milestone 7B.1's backend supports) -- callers must hide or
 * clearly explain this case, never guess or fall back to something else.
 */
export function deriveStartingTrain(confirmResult: ConfirmAndVerifyResult | null): GearTrain | null {
  if (!hasVerifiedPhysics(confirmResult)) return null;
  const gearTrain = confirmResult!.experiment!.topology.gear_train;
  return gearTrain.connections.length === 1 ? gearTrain : null;
}

/** Parses the objective text field: must be a finite number > 0. */
export function parseObjectiveMaxOutputRpm(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed.length === 0) return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

/**
 * True only when the backend's own top-level status is VERIFIED and it
 * actually attached both an accepted design and a final experiment.
 * Every condition is checked independently -- this mirrors the backend's
 * own invariant that VERIFIED is never set without both, and the frontend
 * never promotes a result on its own judgment.
 */
export function hasVerifiedRedesign(result: AutonomousRedesignResult | null): boolean {
  return (
    result !== null &&
    result.status === "verified" &&
    result.accepted_design !== null &&
    result.final_experiment !== null
  );
}

/**
 * True when the backend's trace actually recorded evidence being
 * returned to Muse after this specific attempt -- never inferred from
 * "the previous attempt failed, so evidence must have been returned";
 * always read from the real trace entries the backend sent.
 */
export function evidenceWasReturnedAfter(trace: RedesignTraceEntry[], attemptNumber: number): boolean {
  return trace.some(
    (entry) => entry.stage === "evidence_returned" && entry.attempt_number === attemptNumber,
  );
}

export type RedesignTraceTone = "info" | "muse" | "physics" | "verified" | "warning" | "danger";

/**
 * Maps one trace entry to a visual tone using only its structured
 * stage/status fields -- never parsing the entry's message text. A
 * CONSTRAINT_CHECKED entry's color depends on the backend's own `status`
 * field ("ok"/"failed"), not on any client-side re-evaluation of PASS/FAIL.
 */
export function redesignTraceTone(entry: RedesignTraceEntry): RedesignTraceTone {
  switch (entry.stage) {
    case "objective_received":
      return "info";
    case "candidate_proposed":
      return "muse";
    case "physics_evaluated":
      return "physics";
    case "constraint_checked":
      return entry.status === "ok" ? "verified" : "warning";
    case "design_verified":
      return "verified";
    case "evidence_returned":
      return "warning";
    case "attempts_exhausted":
      return "warning";
    case "invalid_response":
      return "warning";
    case "model_error":
      return "danger";
    default:
      return "info";
  }
}

/** The autonomous-redesign panel's own UI state -- presentation-only,
 * never a backend value. Kept separate from the real-image workflow state
 * so a redesign run belongs unambiguously to one verified physical system
 * and one objective; every trigger that invalidates either resets this. */
export interface RedesignUiState {
  objectiveInput: string;
  isRunning: boolean;
  result: AutonomousRedesignResult | null;
  apiError: string | null;
}

/** Matches the mission's own example UI ("[ 300 ] RPM") -- a sensible,
 * fully user-editable starting suggestion, never a value silently sent
 * without the user's own (unchanged, but explicit) input. */
export const INITIAL_REDESIGN_UI_STATE: RedesignUiState = {
  objectiveInput: "300",
  isRunning: false,
  result: null,
  apiError: null,
};

/** Changing the objective always discards any previous redesign result/
 * error -- a result is only ever meaningful for the exact objective it was
 * computed against, never silently reattributed to a new one. */
export function withObjectiveChanged(state: RedesignUiState, objectiveInput: string): RedesignUiState {
  return { ...state, objectiveInput, result: null, apiError: null };
}

export function withRedesignStarted(state: RedesignUiState): RedesignUiState {
  return { ...state, isRunning: true, apiError: null };
}

export function withRedesignSucceeded(
  state: RedesignUiState,
  result: AutonomousRedesignResult,
): RedesignUiState {
  return { ...state, isRunning: false, result, apiError: null };
}

/** A network/API failure also clears any previous (now stale) result --
 * otherwise an old EXHAUSTED result could render at the same time as the
 * new error banner, which would blur the required visual distinction
 * between "a run actually exhausted" and "the request itself failed". */
export function withRedesignFailed(state: RedesignUiState, apiError: string): RedesignUiState {
  return { ...state, isRunning: false, apiError, result: null };
}
