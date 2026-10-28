import type { PhysicalPipelineResult } from "@/lib/forge-types";
import { GearSchematic } from "./GearSchematic";
import { PerceptionDetails } from "./PerceptionDetails";
import { TopologyPanel } from "./TopologyPanel";

export function PhysicalModelColumn({ result }: { result: PhysicalPipelineResult | null }) {
  if (!result) {
    return (
      <div className="flex h-full min-h-[180px] flex-col items-center justify-center gap-2 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-forge-text-dim">
          No Model Yet
        </p>
        <p className="max-w-[220px] text-xs text-forge-text-muted">
          The physical model, topology, and schematic appear here once FORGE runs an analysis.
        </p>
      </div>
    );
  }

  const physicalSystem = result.build_result.physical_system;

  return (
    <div className="flex flex-col gap-2.5">
      {physicalSystem ? (
        <div className="rounded-md border border-forge-border bg-forge-panel-raised/40 p-2">
          <GearSchematic
            system={physicalSystem}
            shaftOrder={result.experiment?.topology.shaft_path}
          />
        </div>
      ) : (
        <div className="rounded-md border border-dashed border-forge-warning/40 bg-forge-warning-dim/30 p-3 text-xs text-forge-text-muted">
          No physical model was built — the evidence boundary refused one or more
          observations below.
        </div>
      )}

      <div>
        <p className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
          Perceived Components
        </p>
        <PerceptionDetails perception={result.perception} />
      </div>

      <div>
        <p className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
          Topology
        </p>
        <TopologyPanel experiment={result.experiment} />
      </div>
    </div>
  );
}
