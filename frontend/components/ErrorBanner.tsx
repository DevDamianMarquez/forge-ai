export function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-md border border-forge-danger/50 bg-forge-danger-dim/60 px-4 py-3 text-sm text-forge-text"
    >
      <p className="font-mono text-[11px] font-bold uppercase tracking-wide text-forge-danger">
        Request Failed
      </p>
      <p className="mt-1 text-forge-text-muted">{message}</p>
    </div>
  );
}
