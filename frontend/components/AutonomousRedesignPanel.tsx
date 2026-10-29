"use client";

import { Fragment, type ReactNode } from "react";

import type { AutonomousRedesignResult, GearTrain, RedesignAttempt } from "@/lib/forge-types";
import {
  evidenceWasReturnedAfter,
  hasVerifiedRedesign,
  parseObjectiveMaxOutputRpm,
} from "@/lib/autonomous-redesign-helpers";
import { formatDirection, formatRatio, formatRpm } from "@/lib/format";
import { AutonomousRedesignTrace } from "./AutonomousRedesignTrace";

/**
 * Milestone 7B.2: AI proposes, physics verifies. Shown only once a 7A
 * physical system has been verified (gated by the caller, which also
 * derives `startingTrain` from that exact verified state -- never from
 * user-entered text, never hardcoded). Renders only what the backend
 * actually returned: real attempts, the real trace, and the real final
 * status -- never a fabricated replan or a promoted result.
 */
export function AutonomousRedesignPanel({
  startingTrain,
  verifiedOutputRpm,
  objectiveInput,
  onObjectiveChange,
  onLaunch,
  isRunning,
  result,
  apiError,
}: {
  startingTrain: GearTrain | null;
  verifiedOutputRpm: number;
  objectiveInput: string;
  onObjectiveChange: (value: string) => void;
  onLaunch: () => void;
  isRunning: boolean;
  result: AutonomousRedesignResult | null;
  apiError: string | null;
}) {
  if (!startingTrain) {
    return (
      <div className="flex flex-col gap-2 py-2">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-forge-warning">
          Autonomous Redesign Unavailable
        </p>
        <p className="max-w-xl text-xs leading-snug text-forge-text-muted">
          Autonomous redesign currently supports verified simple two-gear transmissions only (a
          single external mesh). This verified physical system has a different topology.
        </p>
      </div>
    );
  }

  const connection = startingTrain.connections[0];
  const objective = parseObjectiveMaxOutputRpm(objectiveInput);
  const canLaunch = objective !== null && !isRunning;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-forge-accent-strong">
          AI Proposes. Physics Verifies.
        </p>
        <p className="mt-0.5 text-[11px] leading-snug text-forge-text-muted">
          Muse Spark proposes a candidate transmission; FORGE&apos;s deterministic physics engine
          is the sole authority on whether it satisfies the objective.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <InfoCard label="Current Verified Design">
          <p className="font-mono text-sm text-forge-text">
            {connection.driver.teeth}T → {connection.driven.teeth}T
          </p>
          <p className="mt-0.5 font-mono text-xs text-forge-text-muted">
            Output: {formatRpm(verifiedOutputRpm)} RPM
          </p>
        </InfoCard>

        <InfoCard label="Engineering Objective">
          <label className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-forge-text-muted">Maximum output speed</span>
            <input
              type="text"
              inputMode="numeric"
              value={objectiveInput}
              onChange={(event) => onObjectiveChange(event.target.value)}
              className="w-20 rounded border border-forge-border bg-forge-panel px-2 py-1 font-mono text-xs text-forge-text focus:border-forge-accent focus:outline-none"
            />
            <span className="text-xs text-forge-text-muted">RPM</span>
          </label>
          {objectiveInput.trim().length > 0 && objective === null && (
            <p className="mt-1 text-[10px] text-forge-danger">Enter a number greater than 0.</p>
          )}
        </InfoCard>
      </div>

      <button
        type="button"
        onClick={onLaunch}
        disabled={!canLaunch}
        aria-busy={isRunning}
        className="rounded-md border border-forge-accent bg-forge-accent/10 px-4 py-2.5 font-mono text-sm font-semibold uppercase tracking-[0.1em] text-forge-accent-strong transition-colors hover:bg-forge-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isRunning ? "Designing…" : "Autonomous Redesign"}
      </button>

      {apiError && (
        <div className="rounded-md border border-forge-danger/50 bg-forge-danger-dim/60 px-3 py-2">
          <p className="font-mono text-[11px] font-bold uppercase tracking-wide text-forge-danger">
            Autonomous Redesign Error
          </p>
          <p className="mt-1 text-xs text-forge-text-muted">{apiError}</p>
        </div>
      )}

      {isRunning && (
        <div className="flex flex-col items-center justify-center gap-1 rounded-md border border-dashed border-forge-accent/40 bg-forge-accent/5 py-6 text-center">
          <span
            aria-hidden
            className="h-5 w-5 animate-spin rounded-full border-2 border-forge-accent border-t-transparent"
          />
          <p className="mt-2 font-mono text-xs uppercase tracking-[0.12em] text-forge-accent-strong">
            Muse Spark Is Designing…
          </p>
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
            Physics Verification Will Follow
          </p>
        </div>
      )}

      {result && !isRunning && (
        <>
          <div className="flex flex-col gap-2.5">
            <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
              Attempts ({result.attempts.length})
            </p>
            {result.attempts.map((attempt) => (
              <Fragment key={attempt.attempt_number}>
                <AttemptCard attempt={attempt} />
                {evidenceWasReturnedAfter(result.trace, attempt.attempt_number) && (
                  <p className="text-center font-mono text-[10px] uppercase tracking-[0.12em] text-forge-warning">
                    ↓ Physics Evidence Returned to Muse
                  </p>
                )}
              </Fragment>
            ))}
          </div>

          <div>
            <p className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
              Autonomous Trace
            </p>
            <AutonomousRedesignTrace trace={result.trace} />
          </div>

          <FinalResult result={result} />
        </>
      )}
    </div>
  );
}

function AttemptCard({ attempt }: { attempt: RedesignAttempt }) {
  const label = `Attempt ${String(attempt.attempt_number).padStart(2, "0")}`;

  if (!attempt.experiment) {
    // No physics ran this attempt: no tool call, multiple tool calls, an
    // unknown tool, invalid arguments, or a duplicate candidate.
    return (
      <div className="rounded-md border border-forge-border bg-forge-panel-raised/50 px-3 py-2">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-xs font-semibold text-forge-text">{label}</span>
          <StatusChip status={attempt.status} />
        </div>
        {attempt.candidate && (
          <p className="mt-1 font-mono text-xs text-forge-text-muted">
            Candidate: {attempt.candidate.input_teeth}T → {attempt.candidate.output_teeth}T
          </p>
        )}
        {attempt.error && (
          <p className="mt-1 text-xs leading-snug text-forge-text-muted">{attempt.error}</p>
        )}
      </div>
    );
  }

  const outputRpm = attempt.experiment.result;
  const ratio = attempt.experiment.metrics.gear_ratio;
  const direction = attempt.experiment.metrics.output_direction;

  return (
    <div className="rounded-md border border-forge-border bg-forge-panel-raised/50 px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs font-semibold text-forge-text">{label}</span>
        <StatusChip status={attempt.status} />
      </div>

      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-forge-accent-strong">
            Muse Spark — Candidate
          </p>
          <p className="font-mono text-sm text-forge-text">
            {attempt.candidate?.input_teeth}T → {attempt.candidate?.output_teeth}T
          </p>
        </div>
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-forge-text-dim">
            Deterministic Physics
          </p>
          <p className="font-mono text-sm text-forge-text">
            {outputRpm !== null ? `${formatRpm(outputRpm)} RPM` : "—"}
            {ratio !== undefined && <> · {formatRatio(ratio)}</>}
            {direction !== undefined && <> · {formatDirection(direction)}</>}
          </p>
        </div>
      </div>
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const isPass = status === "passed";
  const className = isPass
    ? "border-forge-verified bg-forge-verified-dim text-forge-verified"
    : "border-forge-warning bg-forge-warning-dim text-forge-warning";
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide ${className}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

function FinalResult({ result }: { result: AutonomousRedesignResult }) {
  if (hasVerifiedRedesign(result)) {
    // hasVerifiedRedesign guarantees both are non-null here.
    const experiment = result.final_experiment!;
    const design = result.accepted_design!;
    return (
      <div className="rounded-md border border-forge-verified bg-forge-verified-dim/40 px-4 py-3 forge-glow-verified">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-mono text-sm font-bold uppercase tracking-[0.08em] text-forge-text">
            Final Design
          </p>
          <span className="inline-flex items-center gap-2 rounded-full border border-forge-verified bg-forge-verified-dim px-3 py-1 font-mono text-xs font-bold uppercase tracking-wide text-forge-verified">
            ✓ Verified by Physics
          </span>
        </div>
        <p className="mt-1.5 font-mono text-lg text-forge-text">
          {design.input_teeth}T → {design.output_teeth}T
        </p>
        <div className="mt-2 grid grid-cols-3 gap-2">
          <Metric label="Output RPM" value={formatRpm(experiment.result ?? 0)} />
          <Metric label="Ratio" value={formatRatio(experiment.metrics.gear_ratio ?? 0)} />
          <Metric label="Direction" value={formatDirection(experiment.metrics.output_direction ?? 1)} />
        </div>
      </div>
    );
  }

  if (result.status === "exhausted") {
    return (
      <div className="rounded-md border border-forge-warning/50 bg-forge-warning-dim/40 px-4 py-3">
        <p className="font-mono text-sm font-bold uppercase tracking-[0.08em] text-forge-warning">
          No Verified Design Found
        </p>
        <p className="mt-1 text-xs leading-snug text-forge-text-muted">
          FORGE exhausted its attempt budget without a candidate satisfying the objective.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-forge-danger/50 bg-forge-danger-dim/60 px-4 py-3">
      <p className="font-mono text-sm font-bold uppercase tracking-[0.08em] text-forge-danger">
        Autonomous Redesign Error
      </p>
      <p className="mt-1 text-xs leading-snug text-forge-text-muted">
        Muse Spark could not complete this redesign run.
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-forge-border bg-forge-panel-raised/60 px-2 py-1.5">
      <p className="font-mono text-[9px] uppercase tracking-[0.1em] text-forge-text-dim">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-bold text-forge-text">{value}</p>
    </div>
  );
}

function InfoCard({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-md border border-forge-border bg-forge-panel-raised/50 px-3 py-2">
      <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-forge-text-dim">{label}</p>
      <div className="mt-1">{children}</div>
    </div>
  );
}
