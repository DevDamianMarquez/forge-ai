import type { ReactNode } from "react";

export function Panel({
  title,
  eyebrow,
  children,
  className = "",
  bodyClassName = "",
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`flex flex-col rounded-lg border border-forge-border bg-forge-panel ${className}`}>
      <header className="border-b border-forge-border px-3.5 py-2">
        {eyebrow && (
          <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-forge-text-dim">
            {eyebrow}
          </p>
        )}
        <h2 className="font-mono text-[13px] font-semibold uppercase tracking-wide text-forge-text">
          {title}
        </h2>
      </header>
      <div className={`flex-1 ${bodyClassName || "p-3"}`}>{children}</div>
    </section>
  );
}
