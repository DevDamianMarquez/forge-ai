"use client";

import type { FixtureId } from "@/lib/forge-types";
import { SCENARIOS } from "@/lib/scenarios";

interface ScenarioSelectorProps {
  selected: FixtureId;
  onSelect: (id: FixtureId) => void;
  onRun: () => void;
  isRunning: boolean;
}

export function ScenarioSelector({ selected, onSelect, onRun, isRunning }: ScenarioSelectorProps) {
  return (
    <div className="flex h-full flex-col gap-3">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-forge-text-dim">
          Demo / Synthetic Perception
        </p>
        <p className="mt-0.5 text-[11px] leading-snug text-forge-text-muted">
          Deterministic scenarios used until SAM-backed perception is connected. No image was
          analyzed.
        </p>
      </div>

      <div role="radiogroup" aria-label="Scenario" className="flex flex-col gap-1.5">
        {SCENARIOS.map((scenario) => {
          const isSelected = scenario.id === selected;
          return (
            <button
              key={scenario.id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => onSelect(scenario.id)}
              className={`w-full rounded-md border px-3 py-2 text-left transition-colors ${
                isSelected
                  ? "border-forge-accent bg-forge-panel-raised forge-glow-accent"
                  : "border-forge-border bg-forge-panel hover:border-forge-border-strong"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-forge-text">{scenario.label}</span>
                <span
                  aria-hidden
                  className={`h-2.5 w-2.5 shrink-0 rounded-full border ${
                    isSelected ? "border-forge-accent bg-forge-accent" : "border-forge-border-strong"
                  }`}
                />
              </div>
              <p className="mt-0.5 font-mono text-xs text-forge-accent-strong">
                {scenario.summary}
                <span className="text-forge-text-dim"> · {scenario.inputRpm} RPM in</span>
              </p>
              <p className="mt-0.5 text-[11px] leading-snug text-forge-text-muted">
                {scenario.description}
              </p>
            </button>
          );
        })}
      </div>

      <div className="mt-auto flex flex-col gap-1.5 pt-1">
        <button
          type="button"
          onClick={onRun}
          disabled={isRunning}
          aria-busy={isRunning}
          className="rounded-md border border-forge-accent bg-forge-accent/10 px-4 py-2.5 font-mono text-sm font-semibold uppercase tracking-[0.1em] text-forge-accent-strong transition-colors hover:bg-forge-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isRunning ? "Running Analysis…" : "Run Engineering Analysis"}
        </button>
        <p className="text-center text-[10px] text-forge-text-dim">
          Calls the deterministic FORGE pipeline. The backend is authoritative.
        </p>
      </div>
    </div>
  );
}
