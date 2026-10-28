import type { PhysicalSystem } from "@/lib/forge-types";
import { buildSchematicLayout, gearDisplayRadius } from "@/lib/schematic-layout";

const WIDTH = 720;
const HEIGHT = 250;
const SHAFT_TOP = 46;
const SHAFT_BOTTOM = 190;
const GEAR_Y = 118;
const PADDING_X = 92;
const TEETH_TICK_COUNT = 14;

/**
 * A clean 2D engineering schematic for FORGE's currently supported
 * idealized spur-gear systems. Driven entirely by backend PhysicalSystem
 * data (shafts, gears, meshes) plus the optional compiled shaft order --
 * not a general CAD renderer, just enough to visualize our fixtures.
 */
export function GearSchematic({
  system,
  shaftOrder,
}: {
  system: PhysicalSystem;
  shaftOrder?: string[];
}) {
  const layout = buildSchematicLayout(system, shaftOrder);
  const usableWidth = WIDTH - PADDING_X * 2;

  const shaftX = new Map<string, number>();
  for (const shaft of layout.shafts) {
    shaftX.set(shaft.id, PADDING_X + shaft.x * usableWidth);
  }

  const gearPosition = new Map<string, { x: number; radius: number }>();
  for (const shaft of layout.shafts) {
    const baseX = shaftX.get(shaft.id) ?? WIDTH / 2;
    if (shaft.gearIds.length <= 1) {
      const gearId = shaft.gearIds[0];
      if (gearId) {
        const gear = layout.gears[gearId];
        gearPosition.set(gear.id, { x: baseX, radius: gearDisplayRadius(gear.teeth) });
      }
      continue;
    }

    const radii = shaft.gearIds.map((id) => gearDisplayRadius(layout.gears[id].teeth));
    const gap = 20;
    const totalWidth = radii.reduce((sum, r) => sum + r * 2, 0) + gap * (radii.length - 1);
    let cursor = baseX - totalWidth / 2;
    shaft.gearIds.forEach((id, index) => {
      const radius = radii[index];
      const centerX = cursor + radius;
      gearPosition.set(id, { x: centerX, radius });
      cursor += radius * 2 + gap;
    });
  }

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="w-full"
      role="img"
      aria-label="Gear train schematic showing shafts, gears, and meshes"
    >
      {layout.shafts.map((shaft) => {
        const x = shaftX.get(shaft.id) ?? 0;
        return (
          <g key={shaft.id}>
            <line
              x1={x}
              y1={SHAFT_TOP}
              x2={x}
              y2={SHAFT_BOTTOM}
              stroke="var(--forge-border-strong)"
              strokeWidth={4}
              strokeLinecap="round"
            />
            <text
              x={x}
              y={SHAFT_BOTTOM + 24}
              textAnchor="middle"
              fontFamily="var(--forge-mono)"
              fontSize={13}
              letterSpacing="0.05em"
              fill="var(--forge-text-dim)"
            >
              {shaft.id.replace("-", " ").toUpperCase()}
            </text>
          </g>
        );
      })}

      {layout.shafts
        .filter((shaft) => shaft.gearIds.length > 1)
        .flatMap((shaft) =>
          shaft.gearIds.slice(0, -1).map((gearId, index) => {
            const nextId = shaft.gearIds[index + 1];
            const a = gearPosition.get(gearId);
            const b = gearPosition.get(nextId);
            if (!a || !b) return null;
            return (
              <line
                key={`${gearId}-${nextId}-coupler`}
                x1={a.x + a.radius}
                y1={GEAR_Y}
                x2={b.x - b.radius}
                y2={GEAR_Y}
                stroke="var(--forge-border-strong)"
                strokeWidth={9}
                strokeLinecap="round"
              />
            );
          }),
        )}

      {layout.meshes.map((mesh) => {
        const a = gearPosition.get(mesh.gearAId);
        const b = gearPosition.get(mesh.gearBId);
        if (!a || !b) return null;
        const direction = b.x >= a.x ? 1 : -1;
        return (
          <line
            key={`${mesh.gearAId}-${mesh.gearBId}-mesh`}
            x1={a.x + direction * a.radius}
            y1={GEAR_Y}
            x2={b.x - direction * b.radius}
            y2={GEAR_Y}
            stroke="var(--forge-accent)"
            strokeWidth={4}
            strokeDasharray="2 5"
            strokeLinecap="round"
          />
        );
      })}

      {Object.values(layout.gears).map((gear) => {
        const position = gearPosition.get(gear.id);
        if (!position) return null;
        return (
          <g key={gear.id}>
            {Array.from({ length: TEETH_TICK_COUNT }).map((_, tickIndex) => {
              const angle = (tickIndex / TEETH_TICK_COUNT) * Math.PI * 2;
              const inner = position.radius;
              const outer = position.radius + 7;
              return (
                <line
                  key={tickIndex}
                  x1={position.x + Math.cos(angle) * inner}
                  y1={GEAR_Y + Math.sin(angle) * inner}
                  x2={position.x + Math.cos(angle) * outer}
                  y2={GEAR_Y + Math.sin(angle) * outer}
                  stroke="var(--forge-accent)"
                  strokeWidth={3}
                  strokeLinecap="round"
                />
              );
            })}
            <circle
              cx={position.x}
              cy={GEAR_Y}
              r={position.radius}
              fill="var(--forge-panel-raised)"
              stroke="var(--forge-accent)"
              strokeWidth={2.5}
            />
            <circle
              cx={position.x}
              cy={GEAR_Y}
              r={Math.max(position.radius * 0.28, 7)}
              fill="none"
              stroke="var(--forge-border-strong)"
              strokeWidth={2}
            />
            <circle cx={position.x} cy={GEAR_Y} r={3} fill="var(--forge-accent)" />
            <text
              x={position.x}
              y={GEAR_Y - position.radius - 16}
              textAnchor="middle"
              fontFamily="var(--forge-mono)"
              fontSize={13}
              fontWeight={700}
              fill="var(--forge-text-muted)"
            >
              {gear.id.toUpperCase()}
            </text>
            <text
              x={position.x}
              y={GEAR_Y + 5}
              textAnchor="middle"
              fontFamily="var(--forge-mono)"
              fontSize={14}
              fontWeight={700}
              fill="var(--forge-text)"
            >
              {gear.teeth}T
            </text>
          </g>
        );
      })}
    </svg>
  );
}
