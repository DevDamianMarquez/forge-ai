import type { VisualDetection } from "@/lib/forge-types";
import { boundingBoxToPercentRect, friendlyGearLabel } from "@/lib/real-image-helpers";

/**
 * Renders the uploaded image at its natural aspect ratio with SAM's
 * bounding boxes drawn on top, positioned by percentage so they stay
 * correct at whatever size the browser actually renders the image --
 * see lib/real-image-helpers.ts for the coordinate-conversion rationale.
 *
 * Never renders a SAM mask -- only the plain rectangular box. Every box
 * is labeled OBSERVED, never VERIFIED: a visual detection is evidence of
 * something SAM saw, not a confirmed physical fact.
 */
export function DetectionOverlay({
  previewUrl,
  detections,
}: {
  previewUrl: string;
  detections: VisualDetection[];
}) {
  return (
    <div className="relative w-full overflow-hidden rounded-md border border-forge-border bg-black/40">
      {/* eslint-disable-next-line @next/next/no-img-element -- a locally created object URL, not an optimizable remote asset */}
      <img src={previewUrl} alt="Uploaded mechanism" className="block w-full" />

      {detections.map((detection, index) => {
        const rect = boundingBoxToPercentRect(detection.bounding_box);
        return (
          <div
            key={detection.id}
            className="absolute border-2 border-forge-warning"
            style={{
              left: `${rect.leftPct}%`,
              top: `${rect.topPct}%`,
              width: `${rect.widthPct}%`,
              height: `${rect.heightPct}%`,
            }}
          >
            <span className="absolute -top-[18px] left-0 whitespace-nowrap rounded-sm bg-forge-warning px-1 py-0.5 font-mono text-[10px] font-bold leading-none text-black">
              {friendlyGearLabel(index)} · OBSERVED
            </span>
          </div>
        );
      })}
    </div>
  );
}
