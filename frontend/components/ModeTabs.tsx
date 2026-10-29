export type WorkflowMode = "real_image" | "demo";

export function ModeTabs({
  mode,
  onChange,
}: {
  mode: WorkflowMode;
  onChange: (mode: WorkflowMode) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Workflow mode"
      className="inline-flex gap-0.5 rounded-md border border-forge-border bg-forge-panel p-0.5"
    >
      <Tab label="Real Image" isSelected={mode === "real_image"} onSelect={() => onChange("real_image")} />
      <Tab label="Demo Scenarios" isSelected={mode === "demo"} onSelect={() => onChange("demo")} />
    </div>
  );
}

function Tab({
  label,
  isSelected,
  onSelect,
}: {
  label: string;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={isSelected}
      onClick={onSelect}
      className={`rounded-[5px] px-3 py-1.5 font-mono text-xs font-semibold uppercase tracking-[0.1em] transition-colors ${
        isSelected
          ? "bg-forge-accent/15 text-forge-accent-strong"
          : "text-forge-text-dim hover:text-forge-text-muted"
      }`}
    >
      {label}
    </button>
  );
}
