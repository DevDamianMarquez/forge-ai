import type { DisplayStatus } from "@/lib/pipeline-helpers";

const STATUS_STYLES: Record<DisplayStatus, { label: string; className: string }> = {
  confirmed: {
    label: "CONFIRMED",
    className: "bg-forge-verified-dim text-forge-verified border-forge-verified/40",
  },
  partial: {
    label: "PARTIAL",
    className: "bg-forge-warning-dim text-forge-warning border-forge-warning/40",
  },
  inferred: {
    label: "INFERRED",
    className: "bg-forge-warning-dim text-forge-warning border-forge-warning/40",
  },
  observed: {
    label: "OBSERVED",
    className: "bg-forge-warning-dim text-forge-warning border-forge-warning/40",
  },
  unresolved: {
    label: "UNRESOLVED",
    className: "bg-forge-warning-dim text-forge-warning border-forge-warning/40",
  },
  rejected: {
    label: "REJECTED",
    className: "bg-forge-danger-dim text-forge-danger border-forge-danger/40",
  },
};

/** Status is always shown as readable text, never color alone (accessibility). */
export function StatusBadge({ status }: { status: DisplayStatus }) {
  const style = STATUS_STYLES[status];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-wide ${style.className}`}
    >
      {style.label}
    </span>
  );
}
