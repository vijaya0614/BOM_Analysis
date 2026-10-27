import React, { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import type { BOMComponent, RiskFactors } from '../types';

// ── Risk band types & helpers ────────────────────────────────────────────────
export type RiskBand = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT_DATA';

/** Align with backend risk_engine.band_from_score thresholds. */
export const bandOf = (score: number): RiskBand => {
  const s = score > 1 ? score / 100 : score;
  if (s >= 0.85) return 'CRITICAL';
  if (s >= 0.60) return 'HIGH';
  if (s >= 0.30) return 'MEDIUM';
  return 'LOW';
};

/** Normalize any band string from API/mock into a typed RiskBand. */
export const normalizeBand = (band: unknown, score?: number | null): RiskBand => {
  const raw = String(band ?? '').trim().toUpperCase().replace(/[\s-]+/g, '_');
  if (raw === 'INSUFFICIENT_DATA' || raw === 'UNKNOWN') return 'INSUFFICIENT_DATA';
  if (raw === 'CRITICAL' || raw === 'CRIT') return 'CRITICAL';
  if (raw === 'HIGH' || raw === 'AT_RISK' || raw === 'ATRISK') return 'HIGH';
  if (raw === 'MEDIUM' || raw === 'MED') return 'MEDIUM';
  if (raw === 'LOW' || raw === 'HEALTHY') return 'LOW';
  if (typeof score === 'number') return bandOf(score);
  return 'INSUFFICIENT_DATA';
};

export const bandLabel: Record<RiskBand, string> = {
  CRITICAL: 'Critical',
  HIGH:     'At Risk',
  MEDIUM:   'Medium',
  LOW:      'Healthy',
  INSUFFICIENT_DATA: 'Insufficient data',
};

export const bandColorVar: Record<RiskBand, string> = {
  CRITICAL: 'var(--risk-critical)',
  HIGH:     'var(--risk-high)',
  MEDIUM:   'var(--risk-medium)',
  LOW:      'var(--risk-low)',
  INSUFFICIENT_DATA: 'var(--text-muted)',
};

/** Vivid hex per band — works in both light and dark, safe for SVG fills */
export const bandHexSolid: Record<RiskBand, string> = {
  CRITICAL: '#E76F51',
  HIGH:     '#F4A261',
  MEDIUM:   '#E9C46A',
  LOW:      '#2A9D8F',
  INSUFFICIENT_DATA: '#94867F',
};

/** Solid hex fallbacks for SVG fills (CSS vars can fail inside some SVG contexts). */
export const bandColorSolid: Record<RiskBand, string> = {
  CRITICAL: '#E76F51',
  HIGH:     '#F4A261',
  MEDIUM:   '#E9C46A',
  LOW:      '#2A9D8F',
  INSUFFICIENT_DATA: '#94867F',
};

export const getRiskColorSolid = (score: number): string =>
  bandColorSolid[bandOf(score)];

/** Deterministic sparkline from real part fields / risk factors (never random). */
export const buildSparklineFromPart = (comp: BOMComponent): number[] => {
  if (comp.band === 'INSUFFICIENT_DATA') {
    return [];
  }
  if (comp.sparkline_data && comp.sparkline_data.length >= 2) {
    return comp.sparkline_data;
  }
  const f = comp.risk_factors;
  if (f && [f.lifecycle, f.sourcing, f.lead_time, f.stock, f.criticality, f.composite].every(v => typeof v === 'number')) {
    return [
      (f.lifecycle as number) * 0.55,
      (f.sourcing as number) * 0.6,
      (f.lead_time as number) * 0.7,
      (f.stock as number) * 0.75,
      (f.criticality as number) * 0.85,
      ((f.lifecycle as number) + (f.sourcing as number)) / 2,
      ((f.lead_time as number) + (f.stock as number)) / 2,
      (f.composite as number) * 0.92,
      Math.round((comp.score || 0) * 100),
    ].map(v => Math.max(0, Math.min(100, Math.round(v * 10) / 10)));
  }
  return [];
};

/** Factor breakdown for multi-factor charts — prefers API risk_factors. */
export const buildFactorBreakdown = (comp: BOMComponent): { label: string; value: number; key: keyof RiskFactors | 'exposure' }[] => {
  const f = comp.risk_factors;
  if (!f) return [];
  const rows: { label: string; value: number; key: keyof RiskFactors | 'exposure' }[] = [];
  (['lifecycle', 'sourcing', 'lead_time', 'stock', 'criticality'] as const).forEach((key, index) => {
    const labels = ['Lifecycle', 'Sourcing', 'Lead Time', 'Stock Risk', 'Criticality'];
    const value = f[key];
    if (typeof value === 'number') rows.push({ label: labels[index], value: Math.round(value), key });
  });
  if (typeof comp.exp === 'number') {
    rows.push({ label: 'Exposure', value: Math.round(comp.exp * 100), key: 'exposure' });
  }
  return rows;
};

// ── Animated Sparkline ───────────────────────────────────────────────────────
export interface SparklineProps {
  data: number[];
  color?: string;
  width?: number;
  height?: number;
  strokeWidth?: number;
  area?: boolean;
}

export const Sparkline: React.FC<SparklineProps> = ({
  data,
  color = 'currentColor',
  width = 96,
  height = 28,
  strokeWidth = 1.5,
  area = true,
}) => {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, margin: '-40px' });

  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;

  const pts = data.map((v, i) => [
    (i / (data.length - 1)) * (width - 2) + 1,
    height - 2 - ((v - min) / span) * (height - 4),
  ]);

  const pointsStr = pts.map(p => p.join(',')).join(' ');
  const last = pts[pts.length - 1];
  const areaPath = area
    ? `${pointsStr} ${width - 1},${height - 1} 1,${height - 1}`
    : '';

  return (
    <svg
      ref={ref}
      width={width}
      height={height}
      className="overflow-visible"
    >
      {area && (
        <polygon
          points={areaPath}
          fill={color}
          opacity={0.12}
        />
      )}
      <motion.polyline
        points={pointsStr}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={inView ? { pathLength: 1, opacity: 1 } : {}}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      />
      <motion.circle
        cx={last[0]}
        cy={last[1]}
        r={2}
        fill={color}
        initial={{ scale: 0 }}
        animate={inView ? { scale: 1 } : {}}
        transition={{ delay: 0.7 }}
      />
    </svg>
  );
};

export const getRiskColor = (score: number): string =>
  bandColorVar[bandOf(score)];

// ── Risk badge pill ──────────────────────────────────────────────────────────
export const RiskBadge: React.FC<{ band: RiskBand | string; score?: number }> = ({ band, score }) => {
  const resolved = normalizeBand(band, score !== undefined ? (score > 1 ? score / 100 : score) : undefined);
  const color = score !== undefined ? getRiskColor(score) : bandColorVar[resolved];
  return (
    <motion.span
      whileHover={{ scale: 1.05 }}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-black tracking-wide shrink-0"
      style={{
        color,
        background: `color-mix(in oklab, ${color} 16%, var(--bg-card, white))`,
        border: `1px solid color-mix(in oklab, ${color} 50%, transparent)`,
        boxShadow: `0 0 14px -3px color-mix(in oklab, ${color} 35%, transparent), inset 0 1px 0 rgba(255,255,255,0.08)`,
        letterSpacing: '0.02em',
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full inline-block shrink-0 risk-pulse"
        style={{ backgroundColor: color, color }}
      />
      {bandLabel[resolved]}{score !== undefined && <span className="ml-0.5 opacity-80 font-mono">{score}</span>}
    </motion.span>
  );
};

// ── Stagger variants ─────────────────────────────────────────────────────────
export const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.045 } },
};

export const staggerItem = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] as [number,number,number,number] },
  },
};

// ── Small status dot ─────────────────────────────────────────────────────────
export const RiskDot: React.FC<{ color: string; size?: number; pulse?: boolean }> = ({
  color,
  size = 10,
  pulse = false,
}) => (
  <span className="relative inline-flex shrink-0" style={{ width: size, height: size }}>
    {pulse && (
      <span
        className="absolute inset-0 rounded-full animate-ping opacity-40"
        style={{ backgroundColor: color }}
      />
    )}
    <span
      className="relative rounded-full"
      style={{ width: size, height: size, backgroundColor: color }}
    />
  </span>
);

// ── Section header helper ────────────────────────────────────────────────────
export const SectionHeader: React.FC<{
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  accent?: string;
  right?: React.ReactNode;
}> = ({ title, subtitle, icon, accent = 'var(--accent-gold)', right }) => (
  <div className="flex items-start justify-between gap-3">
    <div className="flex items-center gap-2.5">
      {icon && (
        <span
          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
          style={{
            background: `color-mix(in oklab, ${accent} 12%, var(--bg-card))`,
            color: accent,
            boxShadow: `0 1px 6px -1px color-mix(in oklab, ${accent} 45%, transparent)`,
          }}
        >
          {icon}
        </span>
      )}
      <div>
        <h3 className="text-sm font-bold text-[var(--text-primary)]">{title}</h3>
        {subtitle && <p className="text-xs text-[var(--text-muted)]">{subtitle}</p>}
      </div>
    </div>
    {right}
  </div>
);

// ── Stat stat helper ─────────────────────────────────────────────────────────
export const StatsStat: React.FC<{
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
  icon?: React.ReactNode;
}> = ({ label, value, sub, color = 'var(--text-primary)', icon }) => (
  <motion.div
    whileHover={{ scale: 1.02 }}
    className="glass-card p-4 rounded-2xl flex items-center gap-3 relative overflow-hidden neon-card"
  >
    {/* Subtle colored tint */}
    <div className="absolute inset-0 pointer-events-none rounded-2xl"
      style={{ background: `radial-gradient(ellipse at 0% 50%, color-mix(in oklab, ${color} 8%, transparent), transparent 65%)` }} />
    {icon && (
      <span
        className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 relative z-10"
        style={{
          background: `color-mix(in oklab, ${color} 16%, var(--bg-elevated))`,
          color,
          boxShadow: `0 2px 8px -2px color-mix(in oklab, ${color} 40%, transparent)`,
        }}
      >
        {icon}
      </span>
    )}
    <div className="min-w-0 relative z-10">
      <p className="text-2xl font-black font-mono leading-tight truncate number-glow" style={{ color }}>
        {value}
      </p>
      <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold truncate">
        {label}
      </p>
      {sub && <p className="text-[10px] text-[var(--text-muted)] truncate font-mono">{sub}</p>}
    </div>
  </motion.div>
);
