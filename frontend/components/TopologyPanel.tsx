import type { PhysicalSystemExperimentResult } from "@/lib/forge-types";
import { formatRpm } from "@/lib/format";

export function TopologyPanel({
  experiment,
}: {
  experiment: PhysicalSystemExperimentResult | null;
}) {
  if (!experiment) {
    return (
      <p className="text-xs text-forge-text-dim">
        Topology not compiled — the pipeline stopped before this stage.
      </p>
    );
  }

  const { topology } = experiment;

  return (
    <div className="flex flex-col gap-2">
      <Row
        label="Input Shaft"
        value={`${topology.input_shaft_id.toUpperCase()} — ${formatRpm(topology.gear_train.input_rpm)} RPM`}
      />
      {topology.gear_meshes_used.map((mesh, index) => {
        const connection = topology.gear_train.connections[index];
        return (
          <Row
            key={`${mesh.gear_a_id}-${mesh.gear_b_id}`}
            label={topology.gear_meshes_used.length > 1 ? `Gear Mesh ${index + 1}` : "Gear Mesh"}
            value={
              connection
                ? `${connection.driver.id.toUpperCase()} (${connection.driver.teeth}T) ↔ ${connection.driven.id.toUpperCase()} (${connection.driven.teeth}T)`
                : `${mesh.gear_a_id.toUpperCase()} ↔ ${mesh.gear_b_id.toUpperCase()}`
            }
          />
        );
      })}
      <Row label="Output Shaft" value={topology.output_shaft_id.toUpperCase()} />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
        {label}
      </p>
      <p className="mt-0.5 font-mono text-sm text-forge-text">{value}</p>
    </div>
  );
}
