import type { BOMComponent } from '../types';
import type { RiskBand } from '../components/primitives';

export function hasNumericScore(score: unknown): score is number {
  return typeof score === 'number' && Number.isFinite(score);
}

/** Display a 0–100 score, or INSUFFICIENT_DATA when the engine did not score the part. */
export function scoreDisplay(score: unknown, band?: string | null): string {
  if (String(band || '').toUpperCase() === 'INSUFFICIENT_DATA' || !hasNumericScore(score)) {
    return 'INSUFFICIENT_DATA';
  }
  return String(Math.round(score > 1 ? score : score * 100));
}

/** Deterministic 9-point sparkline from real component fields — never random. */
export function buildPerformanceCurve(comp: BOMComponent): number[] {
  if (comp.band === 'INSUFFICIENT_DATA' || !hasNumericScore(comp.score)) {
    return [];
  }
  // Use provided sparkline_data if valid
  if (comp.sparkline_data && comp.sparkline_data.length >= 2) {
    return comp.sparkline_data;
  }
  // Derive from real fields only when lifecycle is a measured stage.
  const life =
    comp.lifecycle_status === 'EOL' ? 95 :
    comp.lifecycle_status === 'NRND' ? 65 :
    comp.lifecycle_status === 'SINGLE_SOURCE' ? 72 :
    comp.lifecycle_status === 'ACTIVE' ? 18 :
    null;
  if (life == null) {
    return [];
  }
  const lead = comp.lead_time_weeks != null
    ? Math.min(100, (comp.lead_time_weeks / 26) * 100)
    : Math.round(comp.exp * 100);
  const stock = comp.stock_level != null
    ? Math.max(0, 100 - Math.min(100, (comp.stock_level / 1000) * 100))
    : Math.round(comp.score * 70);
  const single = comp.reasons.some(r => /single/i.test(r)) ? 85 : 22;
  const score = Math.round(comp.score * 100);
  return [
    Math.round(life * 0.5),
    Math.round(single * 0.55),
    Math.round(lead * 0.65),
    Math.round(stock * 0.7),
    Math.round((life + single) / 2),
    Math.round((lead + stock) / 2),
    Math.round(score * 0.88),
    Math.round(score * 0.94),
    score,
  ].map(v => Math.max(0, Math.min(100, v)));
}

/** Hex stroke color for sparklines/bubbles given a RiskBand. */
/** Vivid hex palette — renders well in both light and dark themes */
export const BAND_HEX: Record<RiskBand, string> = {
  CRITICAL: '#E76F51',
  HIGH:     '#F4A261',
  MEDIUM:   '#E9C46A',
  LOW:      '#2A9D8F',
  INSUFFICIENT_DATA: '#94867F',
};

export function bandHex(band: RiskBand): string {
  return BAND_HEX[band] ?? '#94867F';
}

/** Score-based hex color (same thresholds as bandOf). */
export function scoreHex(score: number): string {
  const s = score > 1 ? score / 100 : score;
  if (s >= 0.70) return BAND_HEX.CRITICAL;
  if (s >= 0.40) return BAND_HEX.HIGH;
  if (s >= 0.20) return BAND_HEX.MEDIUM;
  return BAND_HEX.LOW;
}
