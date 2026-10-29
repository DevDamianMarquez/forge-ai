import type { RedesignTraceEntry, RedesignTraceStage } from "@/lib/forge-types";
import { redesignTraceTone, type RedesignTraceTone } from "@/lib/autonomous-redesign-helpers";

const STAGE_LABELS: Record<RedesignTraceStage, string> = {
  objective_received: "Objective Received",
  candidate_proposed: "Muse — Candidate Proposed",
  physics_evaluated: "Physics Evaluated",
  constraint_checked: "Constraint Checked",
  evidence_returned: "Evidence Returned to Muse",
  design_verified: "Design Verified",
  attempts_exhausted: "Attempts Exhausted",
  invalid_response: "Invalid Response",
  model_error: "Model Error",
};

const TONE_CLASSES: Record<RedesignTraceTone, { dot: string; text: string; line: string }> = {
  info: {
    dot: "border-forge-accent bg-forge-accent/10 text-forge-accent-strong",
    text: "text-forge-accent-strong",
    line: "bg-forge-border-strong",
  },
  muse: {
    dot: "border-forge-accent bg-forge-accent/10 text-forge-accent-strong",
    text: "text-forge-accent-strong",
    line: "bg-forge-border-strong",
  },
  physics: {
    dot: "border-forge-border-strong bg-forge-panel-raised text-forge-text",
    text: "text-forge-text-muted",
    line: "bg-forge-border-strong",
  },
  verified: {
    dot: "border-forge-verified bg-forge-verified-dim text-forge-verified",
    text: "text-forge-verified",
    line: "bg-forge-border-strong",
  },
  warning: {
    dot: "border-forge-warning bg-forge-warning-dim text-forge-warning",
    text: "text-forge-warning",
    line: "bg-forge-warning/40",
  },
  danger: {
    dot: "border-forge-danger bg-forge-danger-dim text-forge-danger",
    text: "text-forge-danger",
    line: "bg-forge-danger/40",
  },
};

/**
 * Renders the backend's own autonomous-redesign trace faithfully: no stage
 * is inferred or fabricated, and color comes only from each entry's
 * structured stage/status fields (see redesignTraceTone) -- never from
 * parsing message text.
 */
export function AutonomousRedesignTrace({ trace }: { trace: RedesignTraceEntry[] }) {
  if (trace.length === 0) {
    return (
      <div className="flex h-full min-h-[120px] flex-col items-center justify-center gap-2 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-forge-text-dim">
          Awaiting Launch
        </p>
        <p className="max-w-[240px] text-xs text-forge-text-muted">
          Launch autonomous redesign to see each proposal and verification stage execute in
          order.
        </p>
      </div>
    );
  }

  return (
    <ol className="flex flex-col">
      {trace.map((entry, index) => {
        const tone = redesignTraceTone(entry);
        const classes = TONE_CLASSES[tone];
        const isLast = index === trace.length - 1;
        return (
          <li key={`${entry.stage}-${index}`} className="relative flex gap-2.5 pb-4 last:pb-0">
            {!isLast && (
              <span aria-hidden className={`absolute left-[9px] top-5 h-full w-px ${classes.line}`} />
            )}
            <span
              aria-hidden
              className={`z-10 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border font-mono text-[10px] font-bold ${classes.dot}`}
            >
              {index + 1}
            </span>
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-semibold uppercase tracking-wide text-forge-text">
                  {STAGE_LABELS[entry.stage] ?? entry.stage}
                </span>
                {entry.attempt_number !== null && (
                  <span className="font-mono text-[10px] text-forge-text-dim">
                    Attempt {entry.attempt_number}
                  </span>
                )}
                <span className={`font-mono text-[10px] font-bold ${classes.text}`}>
                  {entry.status === "ok" ? "✓ OK" : `⚠ ${entry.status.toUpperCase()}`}
                </span>
              </div>
              <p className="mt-0.5 text-xs leading-snug text-forge-text-muted">{entry.message}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
