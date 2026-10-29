/**
 * Pure, backend-data-only logic for the real-image engineering flow
 * (Milestone 7A.2). Nothing here computes a physical value -- gear ratio,
 * output RPM, and direction always come from the backend's
 * ConfirmAndVerifyResult. Everything here is either (a) presentation-only
 * derivation (a friendly "GEAR 01" label, a percentage box rect) or (b) a
 * pure reshaping of user form input into the exact backend confirmation
 * contract (app.services.image_analysis.PhysicalConfirmation).
 */

import type {
  AnalyzeImageResult,
  ConfirmAndVerifyResult,
  GearConfirmation,
  MeshConfirmation,
  PhysicalConfirmation,
  SAMBoundingBox,
  ShaftConfirmation,
} from "./forge-types.ts";

/**
 * The real-image workflow's own UI phase -- presentation-only state, never
 * a backend value. A network/API error is tracked separately (see the
 * page component) so it is always visually distinct from an evidence
 * refusal ("incomplete"), per the product requirement that the two must
 * never look the same.
 */
export type RealImagePhase =
  | "idle"
  | "analyzing"
  | "observed"
  | "verifying"
  | "verified"
  | "incomplete";

/** Mirrors backend/app/sam/client.py's SUPPORTED_IMAGE_MIME_TYPES exactly. */
export const SUPPORTED_IMAGE_MIME_TYPES: ReadonlySet<string> = new Set([
  "image/jpeg",
  "image/png",
]);

export function isSupportedImageType(mimeType: string): boolean {
  return SUPPORTED_IMAGE_MIME_TYPES.has(mimeType);
}

/** A friendly, presentation-only label -- never sent to the backend, never
 * confused with the stable detection/gear id used in API payloads. */
export function friendlyGearLabel(index: number): string {
  return `GEAR ${String(index + 1).padStart(2, "0")}`;
}

export interface PercentRect {
  leftPct: number;
  topPct: number;
  widthPct: number;
  heightPct: number;
}

/**
 * Converts one SAMBoundingBox into a percentage-based rect suitable for
 * absolutely positioning an overlay <div> inside a container that exactly
 * wraps the displayed <img> (so the container's own width/height equal
 * the rendered image's width/height, whatever size that turns out to be).
 *
 * COORDINATE SEMANTICS -- see the SAMBoundingBox doc comment in
 * forge-types.ts: ``width``/``height`` are the full source image's pixel
 * dimensions (not the box's own size), and x1/y1/x2/y2 are absolute pixel
 * coordinates within that image. Dividing by width/height therefore
 * yields the box's position/size as a fraction of the whole image,
 * which is exactly what's needed for percentage-based CSS positioning --
 * no separate knowledge of the rendered <img> element's pixel size is
 * required.
 */
export function boundingBoxToPercentRect(box: SAMBoundingBox): PercentRect {
  if (box.width <= 0 || box.height <= 0) {
    return { leftPct: 0, topPct: 0, widthPct: 0, heightPct: 0 };
  }

  const clamp = (value: number) => Math.min(100, Math.max(0, value));

  const leftPct = clamp((box.x1 / box.width) * 100);
  const topPct = clamp((box.y1 / box.height) * 100);
  const rightPct = clamp((box.x2 / box.width) * 100);
  const bottomPct = clamp((box.y2 / box.height) * 100);

  return {
    leftPct,
    topPct,
    widthPct: Math.max(0, rightPct - leftPct),
    heightPct: Math.max(0, bottomPct - topPct),
  };
}

/**
 * Tracks the single "currently live" object URL for the uploaded-image
 * preview, so the caller always revokes exactly the one it replaces (or
 * the one left over on unmount) and never anything else. Pure bookkeeping
 * -- it does not call URL.createObjectURL/revokeObjectURL itself, so it
 * can be unit-tested without a browser.
 */
export class PreviewUrlTracker {
  private current: string | null = null;

  /** Returns the URL that must now be revoked (if any), and records `next`. */
  replace(next: string | null): string | null {
    const toRevoke = this.current;
    this.current = next;
    return toRevoke;
  }

  get value(): string | null {
    return this.current;
  }
}

export interface GearConfirmationFormState {
  /** The stable VisualDetection/PerceivedGear id this row confirms. */
  id: string;
  confirmedExists: boolean;
  /** Raw text input; parsed on submit. Empty string means "not supplied". */
  teeth: string;
  shaftId: string;
}

export interface SystemConfirmationFormState {
  /** Keyed by `${gearAId}|${gearBId}`; true means the user checked this mesh. */
  meshPairs: Record<string, boolean>;
  inputShaftId: string;
  inputRpm: string;
  outputShaftId: string;
}

export function initialGearForms(detectionIds: string[]): GearConfirmationFormState[] {
  return detectionIds.map((id) => ({ id, confirmedExists: false, teeth: "", shaftId: "" }));
}

export function initialSystemForm(): SystemConfirmationFormState {
  return { meshPairs: {}, inputShaftId: "", inputRpm: "", outputShaftId: "" };
}

export function meshPairKey(gearAId: string, gearBId: string): string {
  return `${gearAId}|${gearBId}`;
}

/** Every unordered pair of detected gears, in a stable order -- for a
 * two-gear detection this is exactly one pair. */
export function allGearPairs(gearIds: string[]): Array<[string, string]> {
  const pairs: Array<[string, string]> = [];
  for (let i = 0; i < gearIds.length; i += 1) {
    for (let j = i + 1; j < gearIds.length; j += 1) {
      pairs.push([gearIds[i], gearIds[j]]);
    }
  }
  return pairs;
}

function parsePositiveInt(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed.length === 0) return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value) || !Number.isInteger(value) || value <= 0) return null;
  return value;
}

function parsePositiveNumber(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed.length === 0) return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

function nonEmpty(raw: string): string | null {
  const trimmed = raw.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/**
 * Builds the exact PhysicalConfirmation payload the backend expects, from
 * the user's form state. This is a pure reshaping, not a confirmation
 * decision: a gear's existence is confirmed if and only if
 * `form.confirmedExists` is true, independent of whether `teeth`/`shaftId`
 * were also typed in -- matching the backend's GearConfirmation contract
 * exactly (entering a tooth count alone must never imply existence).
 *
 * Shafts are confirmed implicitly by use (matching ShaftConfirmation's
 * approved presence-implies-existence semantics): every shaft id the user
 * actually typed into a gear row or the system's input/output fields
 * becomes one ShaftConfirmation entry.
 */
export function buildPhysicalConfirmation(
  gearForms: GearConfirmationFormState[],
  systemForm: SystemConfirmationFormState,
): PhysicalConfirmation {
  const gears: GearConfirmation[] = gearForms.map((form) => ({
    id: form.id,
    confirmed_exists: form.confirmedExists,
    teeth: parsePositiveInt(form.teeth),
    shaft_id: nonEmpty(form.shaftId),
  }));

  const inputShaftId = nonEmpty(systemForm.inputShaftId);
  const outputShaftId = nonEmpty(systemForm.outputShaftId);

  const shaftIds = new Set<string>();
  for (const gear of gears) {
    if (gear.shaft_id) shaftIds.add(gear.shaft_id);
  }
  if (inputShaftId) shaftIds.add(inputShaftId);
  if (outputShaftId) shaftIds.add(outputShaftId);

  const shafts: ShaftConfirmation[] = Array.from(shaftIds).map((id) => ({ id }));

  const meshes: MeshConfirmation[] = Object.entries(systemForm.meshPairs)
    .filter(([, checked]) => checked)
    .map(([key]) => {
      const [gearAId, gearBId] = key.split("|");
      return { gear_a_id: gearAId, gear_b_id: gearBId };
    });

  return {
    shafts,
    gears,
    meshes,
    input_shaft_id: inputShaftId,
    input_rpm: parsePositiveNumber(systemForm.inputRpm),
    output_shaft_id: outputShaftId,
  };
}

/** True only when the backend produced real deterministic physics evidence
 * for this confirmation attempt. Gates every rendered RPM/ratio/direction. */
export function hasVerifiedPhysics(result: ConfirmAndVerifyResult | null): boolean {
  return result !== null && result.build_result.physical_system !== null && result.experiment !== null;
}

/** True whenever the evidence boundary has not (yet, or still not) built a
 * PhysicalSystem -- works for both the pre-confirmation analyze result and
 * a post-confirmation refusal. */
export function isModelBlocked(result: { build_result: { physical_system: unknown } } | null): boolean {
  return result === null || result.build_result.physical_system === null;
}

export type TraceEventStatus = "ok" | "refused";

export interface TraceEvent {
  label: string;
  status: TraceEventStatus;
  message: string;
}

/**
 * Derives the real-image action/evidence trace purely from what actually
 * happened -- never chain-of-thought, never a fabricated future stage. If
 * the model build is refused (at analyze time or after confirmation), no
 * later "successful" stage (topology/physics/result) is ever appended.
 */
export function buildRealImageTrace(
  analysis: AnalyzeImageResult | null,
  confirmResult: ConfirmAndVerifyResult | null,
): TraceEvent[] {
  if (!analysis) return [];

  const events: TraceEvent[] = [
    {
      label: "IMAGE RECEIVED",
      status: "ok",
      message: "Uploaded image sent to SAM 3.1 for visual analysis.",
    },
    {
      label: "SAM 3.1 — VISUAL PERCEPTION",
      status: "ok",
      message: `${analysis.detections.length} component(s) observed.`,
    },
  ];

  const initiallyBlocked = isModelBlocked(analysis);
  events.push({
    label: "EVIDENCE BOUNDARY",
    status: initiallyBlocked ? "refused" : "ok",
    message: initiallyBlocked
      ? `Model blocked — ${analysis.build_result.issues.length} physical fact(s) unresolved.`
      : "All required facts already confirmed.",
  });

  if (!confirmResult) return events;

  events.push({
    label: "USER CONFIRMATION RECEIVED",
    status: "ok",
    message: "Explicit physical confirmation submitted to the backend.",
  });

  const built = !isModelBlocked(confirmResult);
  events.push({
    label: "PHYSICAL MODEL",
    status: built ? "ok" : "refused",
    message: built
      ? "Built from confirmed evidence."
      : `Still blocked — ${confirmResult.build_result.issues.length} issue(s) remain.`,
  });
  if (!built) return events;

  events.push({
    label: "TOPOLOGY",
    status: "ok",
    message: "Transmission path compiled from the confirmed model.",
  });
  events.push({
    label: "DETERMINISTIC PHYSICS",
    status: "ok",
    message: "Executed by FORGE's Python physics engine.",
  });
  events.push({
    label: "RESULT",
    status: "ok",
    message: "Verified by physics.",
  });

  return events;
}
