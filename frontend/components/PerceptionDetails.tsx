import type { ObservationStatus, PerceptionResult } from "@/lib/forge-types";
import { formatConfidencePercent } from "@/lib/format";
import { deriveGearVisualStatus } from "@/lib/pipeline-helpers";
import { StatusBadge } from "./StatusBadge";

export function PerceptionDetails({ perception }: { perception: PerceptionResult }) {
  return (
    <div className="flex flex-col gap-2">
      {(perception.shafts.length > 0 || perception.meshes.length > 0) && (
        <div className="grid grid-cols-2 gap-1.5">
          {perception.shafts.map((shaft) => (
            <ObservationChip
              key={shaft.id}
              title={`Shaft ${shaft.id.replace("shaft-", "").toUpperCase()}`}
              status={shaft.status}
              confidence={shaft.confidence}
            />
          ))}
          {perception.meshes.map((mesh) => (
            <ObservationChip
              key={`${mesh.gear_a_id}-${mesh.gear_b_id}`}
              title={`${mesh.gear_a_id.toUpperCase()} ↔ ${mesh.gear_b_id.toUpperCase()}`}
              status={mesh.status}
              confidence={mesh.confidence}
            />
          ))}
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        {perception.gears.map((gear) => {
          const visualStatus = deriveGearVisualStatus(gear);
          const hasUncertainField =
            gear.teeth.status !== "confirmed" || gear.shaft_id.status !== "confirmed";
          return (
            <div
              key={gear.id}
              className="rounded-md border border-forge-border bg-forge-panel-raised/50 px-2.5 py-1.5"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-forge-text">
                  Gear {gear.id.toUpperCase()}
                </span>
                <StatusBadge status={visualStatus} />
              </div>
              <p className="mt-1 font-mono text-[11px] text-forge-text-muted">
                {gear.teeth.value} teeth · mounted on {gear.shaft_id.value}
              </p>
              {hasUncertainField && (
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {gear.teeth.status !== "confirmed" && (
                    <UncertainFieldTag
                      label="teeth"
                      status={gear.teeth.status}
                      confidence={gear.teeth.confidence}
                    />
                  )}
                  {gear.shaft_id.status !== "confirmed" && (
                    <UncertainFieldTag
                      label="shaft"
                      status={gear.shaft_id.status}
                      confidence={gear.shaft_id.confidence}
                    />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ObservationChip({
  title,
  status,
  confidence,
}: {
  title: string;
  status: ObservationStatus;
  confidence: number;
}) {
  return (
    <div className="flex items-center justify-between gap-1 rounded border border-forge-border bg-forge-panel-raised/50 px-2 py-1">
      <span className="truncate text-[11px] text-forge-text">{title}</span>
      <div className="flex shrink-0 items-center gap-1.5">
        <span className="font-mono text-[9px] text-forge-text-dim">
          {formatConfidencePercent(confidence)}
        </span>
        <StatusBadge status={status} />
      </div>
    </div>
  );
}

function UncertainFieldTag({
  label,
  status,
  confidence,
}: {
  label: string;
  status: ObservationStatus;
  confidence: number;
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-forge-warning/40 bg-forge-warning-dim px-1.5 py-0.5 font-mono text-[10px] text-forge-warning">
      {label.toUpperCase()}: {status.toUpperCase()} · {formatConfidencePercent(confidence)}{" "}
      confidence
    </span>
  );
}
