import type { PhysicalPipelineResult } from "@/lib/forge-types";
import { formatDirection, formatRatio, formatRpm } from "@/lib/format";
import { hasVerifiedPhysics, isRefusedAtModelBuild } from "@/lib/pipeline-helpers";

export function VerifiedResultPanel({ result }: { result: PhysicalPipelineResult | null }) {
  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center gap-1 py-4 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-forge-text-dim">
          No Result Yet
        </p>
        <p className="text-sm text-forge-text-muted">
          Select a scenario and run the engineering analysis.
        </p>
      </div>
    );
  }

  if (isRefusedAtModelBuild(result) || !hasVerifiedPhysics(result)) {
    return <RefusalResult result={result} />;
  }

  return <SuccessResult result={result} />;
}

function SuccessResult({ result }: { result: PhysicalPipelineResult }) {
  // hasVerifiedPhysics(result) guarantees result.experiment is non-null here.
  const experiment = result.experiment!.experiment;
  const outputRpm = experiment.result ?? 0;
  const ratio = experiment.metrics.gear_ratio ?? 0;
  const direction = experiment.metrics.output_direction ?? 1;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-mono text-lg font-bold uppercase tracking-[0.1em] text-forge-text">
            Verified Result
          </h2>
          <p className="text-sm text-forge-text-muted">Deterministic physics evidence</p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-forge-verified bg-forge-verified-dim px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-wide text-forge-verified forge-glow-verified">
          ✓ Verified by Physics
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Metric label="Output Shaft Speed" value={`${formatRpm(outputRpm)} RPM`} />
        <Metric label="Gear Ratio" value={formatRatio(ratio)} />
        <Metric label="Direction" value={formatDirection(direction)} />
      </div>

      <p className="max-w-2xl text-xs leading-snug text-forge-text-muted">
        This result is based on deterministic mechanical physics, not AI prediction. Every value
        above was produced by FORGE&apos;s Python physics engine from a fully confirmed physical
        model — no language model computed it.
      </p>
    </div>
  );
}

function RefusalResult({ result }: { result: PhysicalPipelineResult }) {
  const issues = result.build_result.issues;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-mono text-lg font-bold uppercase tracking-[0.1em] text-forge-danger">
            Verification Blocked
          </h2>
          <p className="max-w-xl text-sm text-forge-text-muted">
            FORGE refused to generate physical evidence because a required observation was not
            confirmed.
          </p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-forge-warning bg-forge-warning-dim px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-wide text-forge-warning">
          ⚠ No Physics Evidence Generated
        </span>
      </div>

      <div className="rounded-md border border-forge-warning/40 bg-forge-warning-dim/40 px-4 py-2.5">
        <p className="font-mono text-sm font-bold tracking-wide text-forge-warning">
          HIGH CONFIDENCE ≠ VERIFIED
        </p>
        <p className="mt-1 text-xs leading-snug text-forge-text-muted">
          No deterministic physics evidence was generated. Output RPM, gear ratio, and direction
          are intentionally not shown — no verified physical model exists for this run.
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
          Structured Perception Issues ({issues.length})
        </p>
        {issues.map((issue, index) => (
          <div
            key={`${issue.code}-${issue.component_id ?? "system"}-${index}`}
            className="rounded-md border border-forge-border bg-forge-panel-raised/60 px-3 py-1.5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-[10px] uppercase tracking-wide text-forge-warning">
                {issue.code.replace(/_/g, " ")}
              </span>
              {issue.component_id && (
                <span className="font-mono text-[10px] text-forge-text-dim">
                  {issue.component_id}
                  {issue.field ? ` · ${issue.field}` : ""}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs leading-snug text-forge-text-muted">{issue.message}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-forge-border bg-forge-panel-raised/60 px-4 py-2.5">
      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
        {label}
      </p>
      <p className="mt-0.5 font-mono text-2xl font-bold text-forge-text">{value}</p>
    </div>
  );
}
