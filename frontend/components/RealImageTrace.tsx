import type { TraceEvent } from "@/lib/real-image-helpers";

/**
 * Visually mirrors EngineeringTrace's styling for the demo-scenario flow,
 * but consumes the real-image flow's own derived TraceEvent list (built by
 * lib/real-image-helpers.ts's buildRealImageTrace -- never chain-of-thought,
 * never a fabricated future stage).
 */
export function RealImageTrace({ events }: { events: TraceEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="flex h-full min-h-[140px] flex-col items-center justify-center gap-2 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-forge-text-dim">
          Awaiting Image
        </p>
        <p className="max-w-[240px] text-xs text-forge-text-muted">
          Upload a mechanism image to see each stage of the real engineering flow execute in
          order.
        </p>
      </div>
    );
  }

  return (
    <ol className="flex flex-col">
      {events.map((event, index) => {
        const isOk = event.status === "ok";
        const isLast = index === events.length - 1;
        return (
          <li key={`${event.label}-${index}`} className="relative flex gap-2.5 pb-4 last:pb-0">
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
                  {event.label}
                </span>
                <span
                  className={`font-mono text-[10px] font-bold ${
                    isOk ? "text-forge-verified" : "text-forge-warning"
                  }`}
                >
                  {isOk ? "✓ OK" : "⚠ REFUSED"}
                </span>
              </div>
              <p className="mt-0.5 text-xs leading-snug text-forge-text-muted">{event.message}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
