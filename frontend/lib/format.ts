/**
 * Pure presentation formatting of numbers the backend already computed.
 * Nothing here derives a new physical value -- it only formats one.
 */

export function formatRpm(value: number): string {
  return trimTrailingZeros(value.toFixed(6));
}

export function formatRatio(value: number): string {
  return `${trimTrailingZeros(value.toFixed(2))} : 1`;
}

export function formatDirection(value: number): "REVERSED" | "SAME AS INPUT" {
  return value < 0 ? "REVERSED" : "SAME AS INPUT";
}

export function formatConfidencePercent(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

function trimTrailingZeros(formatted: string): string {
  if (!formatted.includes(".")) return formatted;
  return formatted.replace(/0+$/, "").replace(/\.$/, "");
}
