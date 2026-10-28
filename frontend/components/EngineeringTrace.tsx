import type { PipelineStage, PipelineTraceEntry } from "@/lib/forge-types";

const STAGE_LABELS: Record<PipelineStage, string> = {
  perception: "Perception",
  model_build: "Model Build",
  topology: "Topology",
  experiment: "Physics Experiment",
};

export function EngineeringTrace({ trace }: { trace: PipelineTraceEntry[] | null }) {
  if (!trace || trace.length === 0) {
    return (
      <div className="flex h-full min-h-[140px] flex-col items-center justify-center gap-2 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-forge-text-dim">
          Awaiting Analysis
        </p>
        <p className="max-w-[240px] text-xs text-forge-text-muted">
          Select a scenario on the left and run the engineering analysis to see each pipeline
          stage execute in order.
        </p>
      </div>
    );
  }

  return (
    <ol className="flex flex-col">
      {trace.map((entry, index) => {
        const isOk = entry.status === "ok";
        const isLast = index === trace.length - 1;
        return (
          <li key={`${entry.stage}-${index}`} className="relative flex gap-2.5 pb-4 last:pb-0">
            {!isLast && (
              <span
                aria-hidden
                className={`absolute left-[9px] top-5 h-full w-px ${
                  isOk ? "bg-forge-border-strong" : "bg-forge-warning/40"
                }`}
              />
            )}
            <span
              aria-hidden
              className={`z-10 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border font-mono text-[10px] font-bold ${
                isOk
                  ? "border-forge-verified bg-forge-verified-dim text-forge-verified"
                  : "border-forge-warning bg-forge-warning-dim text-forge-warning"
              }`}
            >
              {index + 1}
            </span>
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-semibold uppercase tracking-wide text-forge-text">
                  {STAGE_LABELS[entry.stage] ?? entry.stage}
                </span>
                <span
                  className={`font-mono text-[10px] font-bold ${
                    isOk ? "text-forge-verified" : "text-forge-warning"
                  }`}
                >
                  {isOk ? "✓ OK" : "⚠ REFUSED"}
                </span>
              </div>
              <p className="mt-0.5 text-xs leading-snug text-forge-text-muted">{entry.message}</p>
              {entry.stage === "model_build" && (
                <p className="mt-1.5 border-t border-dashed border-forge-border pt-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-forge-text-dim">
                  Evidence Boundary — confirmed observations only
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
