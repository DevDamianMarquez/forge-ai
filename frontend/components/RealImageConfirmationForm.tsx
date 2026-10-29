"use client";

import type { PerceptionIssue, VisualDetection } from "@/lib/forge-types";
import { formatConfidencePercent } from "@/lib/format";
import {
  allGearPairs,
  friendlyGearLabel,
  meshPairKey,
  type GearConfirmationFormState,
  type SystemConfirmationFormState,
} from "@/lib/real-image-helpers";

export function RealImageConfirmationForm({
  detections,
  issues,
  gearForms,
  onGearFormChange,
  systemForm,
  onSystemFormChange,
  onVerify,
  isVerifying,
}: {
  detections: VisualDetection[];
  issues: PerceptionIssue[];
  gearForms: GearConfirmationFormState[];
  onGearFormChange: (id: string, patch: Partial<GearConfirmationFormState>) => void;
  systemForm: SystemConfirmationFormState;
  onSystemFormChange: (patch: Partial<SystemConfirmationFormState>) => void;
  onVerify: () => void;
  isVerifying: boolean;
}) {
  const gearIds = detections.map((detection) => detection.id);
  const pairs = allGearPairs(gearIds);

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-md border border-forge-warning/40 bg-forge-warning-dim/30 px-3 py-2">
        <p className="font-mono text-[11px] font-bold uppercase tracking-wide text-forge-warning">
          Physical Properties Required
        </p>
        <p className="mt-1 text-[11px] leading-snug text-forge-text-muted">
          Visual components detected. Physical properties require explicit confirmation before
          FORGE can run engineering calculations.
        </p>
      </div>

      {issues.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
            Missing Information ({issues.length})
          </p>
          {issues.map((issue, index) => (
            <div
              key={`${issue.code}-${issue.component_id ?? "system"}-${index}`}
              className="rounded border border-forge-border bg-forge-panel-raised/50 px-2 py-1"
            >
              <p className="text-[11px] leading-snug text-forge-text-muted">{issue.message}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-2.5">
        {detections.map((detection, index) => {
          const form = gearForms.find((candidate) => candidate.id === detection.id);
          if (!form) return null;
          return (
            <GearRow
              key={detection.id}
              index={index}
              detection={detection}
              form={form}
              onChange={(patch) => onGearFormChange(detection.id, patch)}
            />
          );
        })}
      </div>

      {pairs.length > 0 && (
        <div>
          <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
            Gear Mesh
          </p>
          <div className="flex flex-col gap-1">
            {pairs.map(([aId, bId]) => {
              const aIndex = gearIds.indexOf(aId);
              const bIndex = gearIds.indexOf(bId);
              const key = meshPairKey(aId, bId);
              const checked = systemForm.meshPairs[key] ?? false;
              return (
                <label key={key} className="flex items-center gap-2 text-xs text-forge-text">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(event) =>
                      onSystemFormChange({
                        meshPairs: { ...systemForm.meshPairs, [key]: event.target.checked },
                      })
                    }
                    className="h-3.5 w-3.5 accent-forge-accent"
                  />
                  {friendlyGearLabel(aIndex)} meshes with {friendlyGearLabel(bIndex)}
                </label>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <Field
          label="Input Shaft"
          value={systemForm.inputShaftId}
          placeholder="shaft-a"
          onChange={(value) => onSystemFormChange({ inputShaftId: value })}
        />
        <Field
          label="Input RPM"
          value={systemForm.inputRpm}
          placeholder="1200"
          onChange={(value) => onSystemFormChange({ inputRpm: value })}
        />
        <Field
          label="Output Shaft (optional)"
          value={systemForm.outputShaftId}
          placeholder="shaft-b"
          onChange={(value) => onSystemFormChange({ outputShaftId: value })}
        />
      </div>

      <button
        type="button"
        onClick={onVerify}
        disabled={isVerifying}
        aria-busy={isVerifying}
        className="rounded-md border border-forge-accent bg-forge-accent/10 px-4 py-2.5 font-mono text-sm font-semibold uppercase tracking-[0.1em] text-forge-accent-strong transition-colors hover:bg-forge-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isVerifying ? "Verifying…" : "Verify Physical System"}
      </button>
    </div>
  );
}

function GearRow({
  index,
  detection,
  form,
  onChange,
}: {
  index: number;
  detection: VisualDetection;
  form: GearConfirmationFormState;
  onChange: (patch: Partial<GearConfirmationFormState>) => void;
}) {
  return (
    <div className="rounded-md border border-forge-border bg-forge-panel-raised/50 px-2.5 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-forge-text">{friendlyGearLabel(index)}</span>
        <span className="font-mono text-[10px] uppercase tracking-wide text-forge-warning">
          Observed
          {detection.confidence !== null && (
            <span className="text-forge-text-dim"> · {formatConfidencePercent(detection.confidence)}</span>
          )}
        </span>
      </div>
      <p className="mt-0.5 font-mono text-[10px] text-forge-text-dim">{detection.id}</p>

      <label className="mt-1.5 flex items-center gap-2 text-xs text-forge-text">
        <input
          type="checkbox"
          checked={form.confirmedExists}
          onChange={(event) => onChange({ confirmedExists: event.target.checked })}
          className="h-3.5 w-3.5 accent-forge-accent"
        />
        Confirm this component is a gear
      </label>

      <div className="mt-1.5 grid grid-cols-2 gap-2">
        <Field label="Teeth" value={form.teeth} placeholder="20" onChange={(value) => onChange({ teeth: value })} />
        <Field
          label="Shaft"
          value={form.shaftId}
          placeholder="shaft-a"
          onChange={(value) => onChange({ shaftId: value })}
        />
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-0.5">
      <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-forge-text-dim">{label}</span>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="rounded border border-forge-border bg-forge-panel px-2 py-1 font-mono text-xs text-forge-text placeholder:text-forge-text-dim focus:border-forge-accent focus:outline-none"
      />
    </label>
  );
}
