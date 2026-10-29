"use client";

import { useRef } from "react";

import { isSupportedImageType } from "@/lib/real-image-helpers";
import type { RealImagePhase } from "@/lib/real-image-helpers";

export function ImageUpload({
  phase,
  fileName,
  onFileSelected,
  onInvalidType,
  onReset,
}: {
  phase: RealImagePhase;
  fileName: string | null;
  onFileSelected: (file: File) => void;
  onInvalidType: (mimeType: string) => void;
  onReset: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    if (!isSupportedImageType(file.type)) {
      onInvalidType(file.type);
      return;
    }
    onFileSelected(file);
  }

  const isAnalyzing = phase === "analyzing";
  const hasImage = fileName !== null;

  return (
    <div className="flex h-full flex-col gap-3">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-forge-text-dim">
          Upload Mechanism Image
        </p>
        <p className="mt-0.5 text-[11px] leading-snug text-forge-text-muted">
          SAM 3.1 visually detects components. Nothing is assumed verified until you explicitly
          confirm it.
        </p>
      </div>

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={isAnalyzing}
        className="flex flex-1 flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed border-forge-border bg-forge-panel-raised/30 px-3 py-6 text-center transition-colors hover:border-forge-accent/60 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isAnalyzing ? (
          <>
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-forge-accent border-t-transparent" />
            <span className="font-mono text-xs uppercase tracking-[0.12em] text-forge-accent-strong">
              Analyzing Mechanism…
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
              SAM 3.1 Visual Perception
            </span>
          </>
        ) : hasImage ? (
          <>
            <span className="font-mono text-xs text-forge-text">{fileName}</span>
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
              Click to upload a different image
            </span>
          </>
        ) : (
          <>
            <span className="font-mono text-sm uppercase tracking-[0.1em] text-forge-text-muted">
              Click to upload
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-text-dim">
              JPEG or PNG
            </span>
          </>
        )}
      </button>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png"
        className="hidden"
        onChange={(event) => {
          handleFiles(event.target.files);
          event.target.value = "";
        }}
      />

      {hasImage && !isAnalyzing && (
        <button
          type="button"
          onClick={onReset}
          className="rounded-md border border-forge-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-forge-text-dim transition-colors hover:border-forge-border-strong hover:text-forge-text-muted"
        >
          Clear Image
        </button>
      )}
    </div>
  );
}
