export function Header() {
  return (
    <header className="border-b border-forge-border bg-forge-panel/70">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-0.5 px-6 py-2.5 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-baseline gap-3">
          <h1 className="font-mono text-xl font-bold tracking-[0.08em] text-forge-text">FORGE</h1>
          <span className="text-sm text-forge-text-muted">Autonomous Physical Systems Engineer</span>
        </div>
        <p className="font-mono text-xs uppercase tracking-[0.14em] text-forge-accent-strong">
          AI proposes. Physics verifies.
        </p>
      </div>
    </header>
  );
}
