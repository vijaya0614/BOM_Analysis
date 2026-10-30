import React, { useState, useEffect, useCallback } from 'react';
import type { BOMComponent, ComponentEvidenceAnalysis, IndustryComponentData, SubstituteCandidate } from '../types';
import type { ApprovalMap } from '../App';
import { useHardwareTwin } from '../context/useHardwareTwin';
import { bandColorVar, RiskBadge, getRiskColor } from '../components/primitives';
import type { RiskBand } from '../components/primitives';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Cell, Tooltip, LabelList,
  LineChart, Line, CartesianGrid, AreaChart, Area
} from 'recharts';
import { bandHex, hasNumericScore } from '../utils/riskUtils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, CheckCircle2, AlertTriangle, ShieldAlert, FileText,
  Clock, Package, Activity, Zap, XCircle, ChevronRight, DollarSign,
  ChevronLeft, ChevronRight as ChevronRightIcon, Globe
} from 'lucide-react';
import { SENTINEL_API_BASE, SUBSTITUTE_API_BASE } from '../api';
import { EngineeringObsolescenceCard } from '../components/EngineeringObsolescenceCard';
import { EngineeringMarketRiskCard } from '../components/EngineeringMarketRiskCard';
import { EngineeringMissionProfileCard } from '../components/EngineeringMissionProfileCard';
import { EngineeringToleranceCard } from '../components/EngineeringToleranceCard';
import { EngineeringFmeaCard } from '../components/EngineeringFmeaCard';
import { WhatIfScenarioCard } from '../components/WhatIfScenarioCard';
import { ComponentVendorIntelligenceCard } from '../components/ComponentVendorIntelligenceCard';
import { ComponentResilienceRadarCard } from '../components/ComponentResilienceRadarCard';
import { ComponentLifecycleTimelineCard } from '../components/ComponentLifecycleTimelineCard';
import { getComponentVendorIntelligence } from '../data/vendorCatalog';
import type {
  ObsolescenceForecastData,
  MarketSupplyRiskData,
  MissionProfileData,
  ToleranceAnalysisData,
  FmeaEntry,
  ComponentVendorIntelligence,
} from '../types';

interface ComponentDetailPageProps {
  component: BOMComponent | null;
  approvedSubstitutes: ApprovalMap;
  onApproveSubstitute: (originalPn: string, substitutePn: string) => void;
  onBack: () => void;
  onViewDecision: (component: BOMComponent) => void;
  industryProductId?: string | null;
}

// ── Classification badge ────────────────────────────────────────────────────
const ClassBadge: React.FC<{ cls: string }> = ({ cls }) => {
  const styles: Record<string, { color: string; bg: string; border: string }> = {
    DROP_IN_CANDIDATE: { color: 'var(--risk-low)', bg: 'color-mix(in oklab, var(--risk-low) 12%, var(--bg-card))', border: 'color-mix(in oklab, var(--risk-low) 40%, transparent)' },
    REQUIRES_REDESIGN: { color: 'var(--risk-high)', bg: 'color-mix(in oklab, var(--risk-high) 12%, var(--bg-card))', border: 'color-mix(in oklab, var(--risk-high) 40%, transparent)' },
    INCOMPATIBLE:      { color: 'var(--risk-critical)', bg: 'color-mix(in oklab, var(--risk-critical) 12%, var(--bg-card))', border: 'color-mix(in oklab, var(--risk-critical) 40%, transparent)' },
    INSUFFICIENT_EVIDENCE: { color: 'var(--risk-high)', bg: 'color-mix(in oklab, var(--risk-high) 12%, var(--bg-card))', border: 'color-mix(in oklab, var(--risk-high) 40%, transparent)' },
  };
  const labels: Record<string, string> = {
    DROP_IN_CANDIDATE: 'Drop-in',
    REQUIRES_REDESIGN: 'Redesign',
    INCOMPATIBLE:      'Incompatible',
    INSUFFICIENT_EVIDENCE: 'Evidence incomplete',
  };
  const s = styles[cls] ?? { color: 'var(--text-secondary)', bg: 'var(--bg-elevated)', border: 'var(--border-subtle)' };
  return (
    <span
      className="px-2.5 py-0.5 rounded-full text-[11px] font-bold border"
      style={{ color: s.color, background: s.bg, borderColor: s.border }}
    >
      {labels[cls] ?? cls.replace(/_/g, ' ')}
    </span>
  );
};

const confidenceStyles: Record<string, { color: string; bg: string; border: string }> = {
  HIGH: { color: 'var(--risk-low)', bg: 'color-mix(in oklab, var(--risk-low) 12%, var(--bg-card))', border: 'color-mix(in oklab, var(--risk-low) 35%, transparent)' },
  MEDIUM: { color: 'var(--risk-high)', bg: 'color-mix(in oklab, var(--risk-high) 12%, var(--bg-card))', border: 'color-mix(in oklab, var(--risk-high) 35%, transparent)' },
  LOW: { color: 'var(--accent-blue)', bg: 'color-mix(in oklab, var(--accent-blue) 12%, var(--bg-card))', border: 'color-mix(in oklab, var(--accent-blue) 35%, transparent)' },
  INSUFFICIENT_DATA: { color: 'var(--text-muted)', bg: 'var(--bg-elevated)', border: 'var(--border-subtle)' },
};

const ConfidenceBadge: React.FC<{ value: string }> = ({ value }) => {
  const key = value in confidenceStyles ? value : 'INSUFFICIENT_DATA';
  const s = confidenceStyles[key];
  return (
    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold border" style={{ color: s.color, background: s.bg, borderColor: s.border }}>
      {value}
    </span>
  );
};

const DataLine: React.FC<{ label: string; value: string; suffix?: string }> = ({ label, value, suffix = '' }) => (
  <div className="flex items-start justify-between gap-3 py-2 border-b border-[var(--border-subtle)] last:border-0">
    <span className="text-xs text-[var(--text-muted)] font-mono">{label}</span>
    <span className="text-xs font-semibold text-[var(--text-primary)] text-right">{value}{value !== 'INSUFFICIENT_DATA' ? suffix : ''}</span>
  </div>
);

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value.replace(/[^\d.-]/g, ''));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const syntheticComponentKind = (component: BOMComponent, specsObj: Record<string, unknown> | null): string => {
  const text = `${component.pn} ${component.category ?? ''} ${Object.keys(specsObj ?? {}).join(' ')}`.toLowerCase();
  if (text.includes('cap')) return 'Capacitor';
  if (text.includes('res')) return 'Resistor';
  if (text.includes('mosfet') || text.includes('fet') || text.includes('transistor')) return 'Semiconductor';
  if (text.includes('sensor')) return 'Sensor';
  if (text.includes('buzz')) return 'Buzzer';
  return 'Component';
};

const buildSyntheticAgeingData = (component: BOMComponent, specsObj: Record<string, unknown> | null) => {
  const kind = syntheticComponentKind(component, specsObj);
  const riskBias = component.band === 'CRITICAL' ? 1.45 : component.band === 'HIGH' ? 1.2 : component.band === 'MEDIUM' ? 0.9 : 0.65;
  const baseTolerance = toNumber(specsObj?.tolerance_pct) ?? toNumber(specsObj?.tolerance) ?? (kind === 'Resistor' ? 5 : kind === 'Capacitor' ? 10 : 8);
  const years = [0, 1, 2, 3, 4, 5];
  const driftPerYear = (kind === 'Capacitor' ? 2.3 : kind === 'Resistor' ? 0.65 : kind === 'Sensor' ? 1.1 : kind === 'Buzzer' ? 1.4 : 0.95) * riskBias;
  const scoreVal = component.score ?? 0.5;
  const expVal = component.exp ?? 0.5;
  const marginDrop = (scoreVal * 8 + expVal * 5) * riskBias;
  return years.map((year) => {
    const drift = Number((year * driftPerYear).toFixed(2));
    const condition = Math.max(35, Number((100 - year * (6 + scoreVal * 8) * riskBias).toFixed(1)));
    const margin = Math.max(-20, Number((100 - baseTolerance - year * marginDrop).toFixed(1)));
    return {
      year: `Y${year}`,
      drift,
      condition,
      margin,
      toleranceBand: Number(baseTolerance.toFixed(2)),
    };
  });
};

const buildSyntheticToleranceBars = (component: BOMComponent, specsObj: Record<string, unknown> | null): { label: string; value: number }[] => {
  const nominal = toNumber(specsObj?.resistance_ohms) ?? toNumber(specsObj?.capacitance_uf) ?? toNumber(specsObj?.voltage_rating_v) ?? 100;
  const tolerancePct = toNumber(specsObj?.tolerance_pct) ?? toNumber(specsObj?.tolerance) ?? (component.band === 'CRITICAL' ? 12 : component.band === 'HIGH' ? 8 : 5);
  const ageingAllowance = tolerancePct * (component.band === 'CRITICAL' ? 0.55 : component.band === 'HIGH' ? 0.38 : 0.22);
  return [
    { label: 'Low limit', value: Number((nominal * (1 - tolerancePct / 100)).toFixed(3)) },
    { label: 'Nominal', value: Number(nominal.toFixed(3)) },
    { label: 'High limit', value: Number((nominal * (1 + tolerancePct / 100)).toFixed(3)) },
    { label: 'Aged demo', value: Number((nominal * (1 + ageingAllowance / 100)).toFixed(3)) },
  ];
};

// ── Score ring ──────────────────────────────────────────────────────────────
const ScoreRing: React.FC<{ value: number | null; label: string; color?: string }> = ({ value, label, color: overrideColor }) => {
  const numeric = typeof value === 'number' && Number.isFinite(value);
  const color = overrideColor || (numeric ? getRiskColor(value) : 'var(--text-muted)');
  const r = 26;
  const circ = 2 * Math.PI * r;
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="64" height="64" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r={r} fill="none" stroke="var(--bg-elevated)" strokeWidth="5" />
        {numeric && (
        <motion.circle
          cx="32" cy="32" r={r} fill="none"
          stroke={color} strokeWidth="5" strokeLinecap="round"
          strokeDasharray={`${(value / 100) * circ} ${circ}`}
          transform="rotate(-90 32 32)"
          initial={{ strokeDasharray: `0 ${circ}` }}
          animate={{ strokeDasharray: `${(value / 100) * circ} ${circ}` }}
          transition={{ duration: 0.9, ease: 'easeOut' }}
          style={{ filter: `drop-shadow(0 1px 6px color-mix(in oklab, ${color} 60%, transparent))` }}
        />
        )}
        <text x="32" y="32" textAnchor="middle" dominantBaseline="central"
          style={{ fontSize: numeric ? '13px' : '7px', fontWeight: 700, fontFamily: 'monospace', fill: 'var(--text-primary)' }}>
          {numeric ? value : 'N/A'}
        </text>
      </svg>
      <span className="text-[10px] text-[var(--text-muted)] font-mono uppercase tracking-wide">{label}</span>
    </div>
  );
};

// ── Check row ────────────────────────────────────────────────────────────────
const CheckRow: React.FC<{ param: string; status: 'MATCHED' | 'MISMATCHED' | 'UNKNOWN'; original: unknown; candidate: unknown }> = ({
  param, status, original, candidate
}) => {
  const icon = status === 'MATCHED' ? <CheckCircle2 className="w-4 h-4" style={{ color: 'var(--risk-low)' }} /> :
               status === 'MISMATCHED' ? <XCircle className="w-4 h-4" style={{ color: 'var(--risk-critical)' }} /> :
               <AlertTriangle className="w-4 h-4" style={{ color: 'var(--risk-high)' }} />;
  return (
    <div className="flex items-center gap-3 py-1.5 border-b border-[var(--border-subtle)] last:border-0 text-xs font-mono">
      {icon}
      <span className="text-[var(--text-secondary)] flex-1 capitalize">{param.replace(/_/g, ' ')}</span>
      <span className="text-[var(--text-muted)]">{String(original ?? '—')}</span>
      <ChevronRight className="w-3 h-3 text-[var(--border-strong)]" />
      <span className="font-bold" style={{ color: status === 'MATCHED' ? 'var(--risk-low)' : status === 'MISMATCHED' ? 'var(--risk-critical)' : 'var(--risk-high)' }}>
        {String(candidate ?? '—')}
      </span>
    </div>
  );
};

// ── Supply Flow Graph (Image 2 representation) ──────────────────────────────
const SupplyFlowGraph: React.FC<{
  factors: { label: string; value: number }[];
  score: number;
  color: string;
}> = ({ factors, score, color }) => {
  const [selectedFactor, setSelectedFactor] = useState<number | null>(null);
  const scoreLabel = score.toFixed(0);

  return (
    <div className="p-5 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-center">
        {/* Left side: 5 interactive node pills matching Image 2 */}
        <div className="lg:col-span-7 space-y-2.5">
          {factors.map((f, i) => {
            const factorBand = f.value >= 70 ? 'CRITICAL' : f.value >= 40 ? 'HIGH' : 'LOW';
            const fColor = bandColorVar[factorBand as RiskBand];
            const isSelected = selectedFactor === i;
            return (
              <motion.div
                key={f.label}
                onClick={() => setSelectedFactor(isSelected ? null : i)}
                whileHover={{ x: 4 }}
                className="flex items-center justify-between px-4 py-3 rounded-xl cursor-pointer transition-all border"
                style={{
                  background: isSelected
                    ? `color-mix(in oklab, ${fColor} 14%, var(--bg-card))`
                    : `color-mix(in oklab, ${fColor} 6%, var(--bg-elevated))`,
                  borderColor: isSelected
                    ? fColor
                    : `color-mix(in oklab, ${fColor} 30%, transparent)`,
                  boxShadow: isSelected
                    ? `0 2px 10px -2px color-mix(in oklab, ${fColor} 35%, transparent)`
                    : 'none',
                }}
              >
                <div className="flex items-center gap-2.5">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: fColor }}
                  />
                  <span className="text-xs font-semibold text-[var(--text-primary)] font-mono">
                    {f.label}
                  </span>
                </div>
                <span
                  className="font-mono font-bold text-xs"
                  style={{ color: fColor }}
                >
                  {f.value}
                </span>
              </motion.div>
            );
          })}
        </div>

        {/* Center-Right: Bezier trace lines & Output Risk Circle */}
        <div className="lg:col-span-5 flex items-center justify-center relative min-h-[220px]">
          <svg className="w-full h-56" viewBox="0 0 200 200">
            {factors.map((f, i) => {
              const sy = 25 + i * 36;
              const ey = 100;
              const d = `M 10 ${sy} C 70 ${sy}, 70 ${ey}, 130 ${ey}`;
              const factorBand = f.value >= 70 ? 'CRITICAL' : f.value >= 40 ? 'HIGH' : 'LOW';
              const fColor = bandColorVar[factorBand as RiskBand];
              const isSelected = selectedFactor === null || selectedFactor === i;
              return (
                <g key={i}>
                  <path
                    d={d}
                    fill="none"
                    stroke={fColor}
                    strokeWidth={isSelected ? '2' : '1'}
                    opacity={isSelected ? 0.7 : 0.15}
                  />
                  <path
                    d={d}
                    fill="none"
                    stroke={fColor}
                    strokeWidth="2"
                    strokeLinecap="round"
                    className="animate-supply-flow"
                    style={{
                      animationDelay: `${i * 0.3}s`,
                      opacity: isSelected ? 1 : 0.2,
                    }}
                  />
                </g>
              );
            })}

            {/* Output Score Circle with RISK OUT label */}
            <circle
              cx="140"
              cy="100"
              r="44"
              fill={`color-mix(in oklab, ${color} 10%, var(--bg-card))` as string}
              stroke={color}
              strokeWidth="2"
              style={{
                filter: `drop-shadow(0 0 14px color-mix(in oklab, ${color} 45%, transparent))`,
              }}
            />
            <circle
              cx="140"
              cy="100"
              r="44"
              fill="none"
              stroke={color}
              strokeWidth="1.5"
              strokeDasharray="6 6"
              className="animate-spin"
              style={{ animationDuration: '20s', opacity: 0.3 }}
            />
            <text
              x="140"
              y="94"
              textAnchor="middle"
              dominantBaseline="central"
              fontSize="24"
              fontWeight="900"
              fontFamily="monospace"
              fill={color}
            >
              {scoreLabel}
            </text>
            <text
              x="140"
              y="115"
              textAnchor="middle"
              dominantBaseline="central"
              fontSize="8"
              fontWeight="700"
              fontFamily="monospace"
              fill="var(--text-muted)"
              letterSpacing="1.5"
            >
              RISK OUT
            </text>
          </svg>
        </div>
      </div>
    </div>
  );
};

// ── Lifecycle timeline ─────────────────────────────────────────────────────────
const LifecycleTimeline: React.FC<{ status: BOMComponent['lifecycle_status'] }> = ({ status }) => {
  const stages = [
    { id: 'ACTIVE', label: 'Active', desc: 'Fully supported, volume production' },
    { id: 'NRND',   label: 'NRND',  desc: 'Not Recommended for New Designs' },
    { id: 'EOL',    label: 'EOL',   desc: 'End of Life, last-time-buy' },
    { id: 'SINGLE_SOURCE', label: 'Single Source', desc: 'One-supplier dependency' },
  ];
  const currentIdx = stages.findIndex(s => s.id === status);
  const stageColors = ['#2A9D8F', '#F4A261', '#E76F51', '#9C6FE4'];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-0 relative">
        {/* Connecting line */}
        <div
          className="absolute top-3.5 left-4 h-0.5"
          style={{
            right: '1rem',
            background: 'var(--border-subtle)',
          }}
        />
        {stages.map((stage, i) => {
          const isPast = currentIdx >= 0 && i < currentIdx;
          const isCurrent = i === currentIdx;
          const isFuture = !isPast && !isCurrent;
          const c = stageColors[i];
          return (
            <div key={stage.id} className="flex-1 flex flex-col items-center gap-1.5 relative z-10">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: i * 0.12, duration: 0.3, ease: 'backOut' }}
                className="w-7 h-7 rounded-full flex items-center justify-center border-2"
                style={{
                  backgroundColor: isFuture ? 'var(--bg-elevated)' : `color-mix(in oklab, ${c} 15%, var(--bg-card))`,
                  borderColor: isFuture ? 'var(--border-subtle)' : c,
                  boxShadow: isCurrent ? `0 0 0 4px color-mix(in oklab, ${c} 20%, transparent)` : 'none',
                }}
              >
                {isPast && <CheckCircle2 className="w-3.5 h-3.5" style={{ color: c }} />}
                {isCurrent && <div className="w-2 h-2 rounded-full" style={{ backgroundColor: c }} />}
                {isFuture && <div className="w-2 h-2 rounded-full bg-[var(--border-strong)] opacity-40" />}
              </motion.div>
              <span
                className="text-[10px] font-bold font-mono"
                style={{ color: isFuture ? 'var(--text-muted)' : c }}
              >
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>
      {currentIdx >= 0 ? (
        <p className="text-xs text-[var(--text-muted)] text-center">
          Current stage: <strong className="text-[var(--text-primary)]">{stages[currentIdx].label}</strong>
          {' — '}{stages[currentIdx].desc}
        </p>
      ) : status === 'UNCONFIRMED' ? (
        <p className="text-xs text-[var(--text-muted)] text-center">
          UNCONFIRMED — a distributor returned a lifecycle label, but it is not a confirmed Active / NRND / EOL status.
        </p>
      ) : (
        <p className="text-xs text-[var(--text-muted)] text-center">
          INSUFFICIENT_DATA — no measured lifecycle status is available. This timeline does not default to Active.
        </p>
      )}
    </div>
  );
};

// ── Substitutes carousel ──────────────────────────────────────────────────────
const SubstituteCarousel: React.FC<{
  substitutes: SubstituteCandidate[];
  approvedSub: string | undefined;
  onApprove: (sub: SubstituteCandidate) => void;
}> = ({ substitutes, approvedSub, onApprove }) => {
  const [idx, setIdx] = useState(0);
  const [dir, setDir] = useState(1);

  if (substitutes.length === 0) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm text-[var(--text-muted)]">INSUFFICIENT_DATA — no evidence-backed substitute candidates.</p>
      </div>
    );
  }

  const sub = substitutes[idx];
  const canApprove = sub.classification === 'DROP_IN_CANDIDATE' && sub.drop_in_evidence?.status === 'SUPPORTED';
  const isApproved = approvedSub === sub.part_number && canApprove;

  const go = (d: number) => {
    setDir(d);
    setIdx(prev => (prev + d + substitutes.length) % substitutes.length);
  };

  const variants = {
    enter: (d: number) => ({ x: d > 0 ? 80 : -80, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (d: number) => ({ x: d > 0 ? -80 : 80, opacity: 0 }),
  };

  return (
    <div className="space-y-4">
      {/* Navigation + indicator */}
      <div className="flex items-center justify-between">
        <button
          id="sub-carousel-prev"
          onClick={() => go(-1)}
          disabled={substitutes.length <= 1}
          className="p-1.5 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-[var(--text-primary)] disabled:opacity-30 cursor-pointer transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <div className="flex items-center gap-1.5">
          {substitutes.map((_, i) => (
            <button
              key={i}
              onClick={() => { setDir(i > idx ? 1 : -1); setIdx(i); }}
              className="w-2 h-2 rounded-full transition-all cursor-pointer"
              style={{
                background: i === idx ? 'var(--accent-gold)' : 'var(--border-strong)',
                transform: i === idx ? 'scale(1.3)' : 'scale(1)',
              }}
            />
          ))}
        </div>
        <button
          id="sub-carousel-next"
          onClick={() => go(1)}
          disabled={substitutes.length <= 1}
          className="p-1.5 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-muted)] hover:text-[var(--text-primary)] disabled:opacity-30 cursor-pointer transition-colors"
        >
          <ChevronRightIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Slide */}
      <div className="relative overflow-hidden">
        <AnimatePresence custom={dir} mode="wait">
          <motion.div
            key={idx}
            custom={dir}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="p-5 rounded-2xl border-2 space-y-4"
            style={{
              borderColor: isApproved ? '#2A9D8F' : 'var(--border-subtle)',
              background: isApproved
                ? 'color-mix(in oklab, #2A9D8F 6%, var(--bg-card))'
                : 'var(--bg-card)',
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between">
              <span className="px-2 py-0.5 rounded-md bg-blue-500/15 text-blue-600 font-mono font-bold text-[11px]">
                Rank #{sub.rank}
              </span>
              {isApproved
                ? <span className="text-[11px] font-bold text-emerald-600 flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> Approved</span>
                : <ClassBadge cls={sub.classification} />
              }
            </div>

            {/* Part name */}
            <h4 className="font-mono font-bold text-base text-[var(--text-primary)]">{sub.part_number}</h4>

            {/* Score rings */}
            <div className="flex items-center justify-around py-2">
              <ScoreRing value={sub.compatibility_score} label="Compat" color="#2A9D8F" />
              <ScoreRing value={sub.supply_chain_score} label="Supply" color="#3A86EF" />
              <ScoreRing value={sub.confidence_score} label="Conf" color="var(--accent-gold)" />
            </div>

            {/* Explanation */}
            {sub.explanation && (
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed bg-[var(--bg-elevated)] p-3 rounded-xl border border-[var(--border-subtle)]">
                {sub.explanation}
              </p>
            )}

            {sub.drop_in_evidence && (
              <div className="rounded-xl border p-3 space-y-2" style={{ borderColor: sub.drop_in_evidence.status === 'SUPPORTED' ? 'color-mix(in oklab, var(--risk-low) 35%, transparent)' : 'color-mix(in oklab, var(--risk-high) 45%, transparent)', background: 'var(--bg-elevated)' }}>
                <div className="flex items-center justify-between gap-2"><strong className="text-xs">Drop-in evidence</strong><ClassBadge cls={sub.drop_in_evidence.status} /></div>
                {sub.drop_in_evidence.requirements.map(item => <div key={item.parameter} className="text-[10px] text-[var(--text-muted)]"><p><span className="font-mono">{item.parameter}:</span> original {String(item.original.value)} · candidate {String(item.candidate.value)} · {item.status}</p><div className="mt-1 flex flex-wrap gap-x-3">{([['Original source', item.original.source], ['Candidate source', item.candidate.source]] as const).map(([label, source]) => { const url = source?.source_url || source?.url; const title = source?.source_title || source?.source_document || source?.source_id || 'Source unavailable'; return <span key={label}>{label}: {typeof url === 'string' ? <a href={url} target="_blank" rel="noreferrer" className="underline break-all">{String(title)}{source?.source_page ? ` · p. ${source.source_page}` : ''}</a> : String(title)}</span>; })}</div></div>)}
                {sub.drop_in_evidence.unknown_parameters.length > 0 && <p className="text-[10px] text-[var(--risk-high)]">Missing traceable evidence: {sub.drop_in_evidence.unknown_parameters.join(', ')}</p>}
              </div>
            )}

            {/* Checks */}
            {sub.checks && sub.checks.length > 0 && (
              <div className="bg-[var(--bg-elevated)] rounded-xl p-3 border border-[var(--border-subtle)] space-y-0.5 max-h-36 overflow-y-auto">
                {sub.checks.slice(0, 5).map((chk, ci) => (
                  <CheckRow key={ci} param={chk.parameter}
                    status={chk.status} original={chk.original} candidate={chk.candidate} />
                ))}
              </div>
            )}

            {/* Footer */}
            <div className="flex items-center justify-between pt-2 border-t border-[var(--border-subtle)]">
              {sub.lead_time_weeks !== undefined ? (
                <span className="text-[10px] text-[var(--text-muted)] font-mono flex items-center gap-1">
                  <Clock className="w-3 h-3" /> {sub.lead_time_weeks}wk
                  {sub.stock !== undefined && ` · ${sub.stock} units`}
                </span>
              ) : <span />}
              {isApproved ? (
                <span className="px-3 py-1 bg-emerald-100 text-emerald-700 rounded-lg font-semibold text-[11px] flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Approved
                </span>
              ) : canApprove ? (
                <button
                  id={`approve-sub-${sub.rank}`}
                  onClick={() => onApprove(sub)}
                  className="px-3 py-1 bg-emerald-500 text-white rounded-lg font-semibold text-[11px] hover:bg-emerald-600 active:scale-95 transition-all shadow-sm cursor-pointer"
                >
                  Approve
                </button>
              ) : (
                <span className="text-[10px] text-[var(--risk-high)]" title="Approval requires source-backed package, pinout and rating evidence">Evidence incomplete</span>
              )}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Count label */}
      <p className="text-center text-[11px] text-[var(--text-muted)]">
        {idx + 1} of {substitutes.length} substitute candidates
      </p>
    </div>
  );
};

// ── Main ─────────────────────────────────────────────────────────────────────────────
export const ComponentDetailPage: React.FC<ComponentDetailPageProps> = ({
  component, approvedSubstitutes, onApproveSubstitute, onBack, onViewDecision, industryProductId
}) => {
  const { recommendSubstitute, approveSubstitute: twinApprove } = useHardwareTwin();
  const [substitutes, setSubstitutes] = useState<SubstituteCandidate[]>([]);
  const [loadingSubstitutes, setLoadingSubstitutes] = useState<boolean>(false);
  const [componentSpec, setComponentSpec] = useState<Record<string, unknown> | null>(null);
  const [componentAnalysis, setComponentAnalysis] = useState<ComponentEvidenceAnalysis | null>(null);
  const [_industryData, setIndustryData] = useState<IndustryComponentData | null>(null);
  const [substituteSource, setSubstituteSource] = useState<'API' | 'UNAVAILABLE' | 'INSUFFICIENT_DATA'>('API');

  // PS5 Engineering States
  const [obsolescenceData, setObsolescenceData] = useState<ObsolescenceForecastData | null>(null);
  const [marketRiskData, setMarketRiskData] = useState<MarketSupplyRiskData | null>(null);
  const [missionProfileData, setMissionProfileData] = useState<MissionProfileData | null>(null);
  const [toleranceData, setToleranceData] = useState<ToleranceAnalysisData | null>(null);
  const [fmeaEntries, setFmeaEntries] = useState<FmeaEntry[]>([]);
  const [loadingEngineering, setLoadingEngineering] = useState<boolean>(false);
  const [vendorIntelligence, setVendorIntelligence] = useState<ComponentVendorIntelligence | null>(null);

  const fetchData = useCallback(async (comp: BOMComponent) => {
    const lookupId = comp.substitute_lookup_id || comp.component_id || comp.pn;
    const industryRoute = Boolean(industryProductId && comp.ref);
    const initialVendorData = getComponentVendorIntelligence(comp.pn, comp.category);
    setVendorIntelligence(initialVendorData);
    setLoadingSubstitutes(true);
    setLoadingEngineering(true);
    setSubstituteSource('API');
    try {
      const substituteUrl = industryRoute
        ? `${SUBSTITUTE_API_BASE}/industry/${encodeURIComponent(industryProductId || '')}/${encodeURIComponent(comp.ref)}/substitutes`
        : `${SUBSTITUTE_API_BASE}/components/${encodeURIComponent(lookupId)}/substitutes?include_incompatible=true`;
      const [specRes, subRes, analysisRes, industryRes] = await Promise.all([
        industryRoute
          ? Promise.resolve(new Response(JSON.stringify({}), { status: 404 }))
          : fetch(`${SUBSTITUTE_API_BASE}/components/${encodeURIComponent(lookupId)}`),
        fetch(substituteUrl),
        industryRoute
          ? Promise.resolve(new Response(JSON.stringify({}), { status: 404 }))
          : fetch(`${SUBSTITUTE_API_BASE}/evidence/components/${encodeURIComponent(lookupId)}/analysis`),
        fetch(`${SENTINEL_API_BASE}/api/industry/component/${encodeURIComponent(comp.pn)}`)
      ]);
      const specData = await specRes.json();
      const subData = await subRes.json();
      const analysisData = await analysisRes.json();
      const industryPayload = industryRes.ok ? await industryRes.json() : null;

      if (specData.component) setComponentSpec(specData.component);
      if (analysisData) setComponentAnalysis(analysisData);
      if (industryPayload) {
        setIndustryData(industryPayload);
        if (industryPayload.geological && industryPayload.market_saturation) {
          setVendorIntelligence(industryPayload);
        }
      }

      if (subData.candidates?.length > 0) {
        setSubstitutes(subData.candidates);
        setSubstituteSource('API');
      } else if (subRes.ok) {
        setSubstitutes([]);
        setSubstituteSource('INSUFFICIENT_DATA');
      } else {
        setSubstitutes([]);
        setSubstituteSource('UNAVAILABLE');
      }
    } catch {
      setSubstitutes([]);
      setSubstituteSource('UNAVAILABLE');
    } finally {
      setLoadingSubstitutes(false);
    }

    // Fetch PS5 Deep Engineering Analyses
    try {
      const [obsRes, mktRes, misRes, tolRes, fmeaRes] = await Promise.all([
        fetch(`${SUBSTITUTE_API_BASE}/api/obsolescence/forecast`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            part_number: comp.pn,
            category: comp.category || 'generic',
            lifecycle_status: comp.lifecycle_status || 'ACTIVE',
            introduction_year: 2018,
          }),
        }),
        fetch(`${SUBSTITUTE_API_BASE}/api/market/supply-pressure`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            part_number: comp.pn,
            available_stock: comp.stock ?? 18500,
            weekly_demand: 120.0,
            estimated_lead_time_weeks: comp.lead_time_weeks ?? 10.0,
          }),
        }),
        fetch(`${SUBSTITUTE_API_BASE}/api/mission-profile/evaluate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            part_number: comp.pn,
            operating_power_w: 1.25,
            thermal_resistance_c_per_w: 42.0,
            activation_energy_ev: 0.7,
            phases: [
              { name: 'Normal Load', ambient_temp_c: 45.0, annual_hours: 4000, power_dissipation_watts: 1.25 },
              { name: 'Peak Load', ambient_temp_c: 65.0, annual_hours: 1000, power_dissipation_watts: 1.25 },
            ],
          }),
        }),
        fetch(`${SUBSTITUTE_API_BASE}/api/tolerances/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            part_number: comp.pn,
            circuit_type: 'buck_converter',
            vref_volts: 0.8,
            vref_tol_pct: 1.5,
            r_top_ohms: 10000.0,
            r_top_tol_pct: 1.0,
            r_bot_ohms: 2000.0,
            r_bot_tol_pct: 1.0,
            sample_count: 1000,
          }),
        }),
        fetch(`${SUBSTITUTE_API_BASE}/api/fmea/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            part_number: comp.pn,
            category: comp.category || 'generic',
          }),
        }),
      ]);

      if (obsRes.ok) setObsolescenceData(await obsRes.json());
      if (mktRes.ok) setMarketRiskData(await mktRes.json());
      if (misRes.ok) setMissionProfileData(await misRes.json());
      if (tolRes.ok) setToleranceData(await tolRes.json());
      if (fmeaRes.ok) {
        const fData = await fmeaRes.json();
        setFmeaEntries(fData.fmea_entries || []);
      }
    } catch (err) {
      console.warn('Engineering endpoints offline or fallback:', err);
    } finally {
      setLoadingEngineering(false);
    }
  }, [industryProductId]);

  useEffect(() => {
    if (!component) return;
    setSubstitutes([]);
    setComponentSpec(null);
    setComponentAnalysis(null);
    setIndustryData(null);
    setObsolescenceData(null);
    setMarketRiskData(null);
    setMissionProfileData(null);
    setToleranceData(null);
    setFmeaEntries([]);
    setVendorIntelligence(null);
    fetchData(component);
  }, [component, fetchData]);

  const handleApprove = (sub: SubstituteCandidate) => {
    if (!component) return;
    twinApprove();
    onApproveSubstitute(component.pn, sub.part_number);
    recommendSubstitute(sub.part_number);
  };

  if (!component) {
    return (
      <div className="p-8 text-center glass-panel rounded-2xl">
        <p className="text-sm text-[var(--text-muted)]">No component selected.</p>
        <button onClick={onBack} className="mt-4 px-4 py-2 bg-[var(--accent-gold)] text-white rounded-xl text-xs font-semibold cursor-pointer">
          Back
        </button>
      </div>
    );
  }

  const band = component.band as RiskBand;
  const color = bandColorVar[band];
  const approvedSub = approvedSubstitutes[component.pn];
  const isApproved = !!approvedSub;
  const insufficientEvidence = band === 'INSUFFICIENT_DATA' || !hasNumericScore(component.score);

  const radarData = insufficientEvidence ? [] : [
    { factor: 'EOL Risk',      value: component.band === 'CRITICAL' ? 90 : component.band === 'HIGH' ? 65 : 25 },
    { factor: 'Single Source', value: component.reasons.some(r => r.toLowerCase().includes('single')) ? 88 : 20 },
    { factor: 'Lead Time',     value: Math.round((component.exp ?? 0.5) * 100) },
    { factor: 'Price Vol',     value: Math.round((component.score ?? 0.5) * 80) },
    { factor: 'Exposure',      value: Math.round((component.exp ?? 0.5) * 100) },
  ];

  const flowFactors = insufficientEvidence ? [] : [
    { label: 'Lifecycle stage', value: component.band === 'CRITICAL' ? 95 : component.band === 'HIGH' ? 70 : 30 },
    { label: 'Sourcing',        value: Math.round((component.score ?? 0.5) * 100) },
    { label: 'Availability',    value: Math.round((component.exp ?? 0.5) * 100) },
    { label: 'Price volatility',value: Math.round((component.score ?? 0.5) * 82) },
    { label: 'Vendor conc.',    value: Math.round(component.conf * 55) },
  ];

  const spec = componentSpec as Record<string, unknown> | null;
  const specsObj = spec?.specs as Record<string, unknown> | null;
  const intelligence = componentAnalysis?.data;
  const evidenceProfile = intelligence?.profile;
  const allProfileFields = evidenceProfile?.electrical_profile ?? [];
  const toleranceFields = evidenceProfile?.tolerance_profile ?? allProfileFields.filter((field) => field.field.toLowerCase().includes('tolerance'));
  const profileFields = evidenceProfile?.operating_profile ?? allProfileFields.filter((field) => !field.field.toLowerCase().includes('tolerance'));
  const specificFields = evidenceProfile?.component_specific_parameters ?? [];
  const evidenceRows = intelligence?.evidence ?? [];
  const reliability = intelligence?.reliability;
  const syntheticKind = syntheticComponentKind(component, specsObj);
  const syntheticAgeingData = buildSyntheticAgeingData(component, specsObj);
  const syntheticToleranceBars = buildSyntheticToleranceBars(component, specsObj);
  const hasExactToleranceEvidence = toleranceFields.some((field) => field.value !== 'INSUFFICIENT_DATA');

  return (
    <div className="space-y-5 pb-12">

      {/* ── Back nav + band badge ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <button onClick={onBack}
          className="flex items-center gap-2 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] glass-card px-3 py-1.5 rounded-xl border border-[var(--border-subtle)] cursor-pointer transition-all">
          <ArrowLeft className="w-4 h-4" /> Back to Components
        </button>
        <button onClick={() => onViewDecision(component)}
          className="px-4 py-2 rounded-xl text-xs font-bold text-white flex items-center gap-2 shadow-sm cursor-pointer"
          style={{ background: 'var(--gradient-brand)' }}>
          <ChevronRight className="w-4 h-4" /> View Decision
        </button>
        <div className="flex items-center gap-2">
          {isApproved && (
            <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700 border border-emerald-300 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" /> Approved → {approvedSub}
            </span>
          )}
          <RiskBadge band={band} score={hasNumericScore(component.score) ? Math.round(component.score * 100) : undefined} />
        </div>
      </div>

      {/* ── Sticky Engineering Section Navigation Strip ── */}
      <div className="sticky top-2 z-30 p-2 rounded-2xl glass-card border border-[var(--border-subtle)] flex items-center gap-1.5 overflow-x-auto text-xs font-semibold backdrop-blur-md shadow-md">
        <a href="#sec-overview" className="px-3 py-1.5 rounded-xl hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all whitespace-nowrap">
          Overview
        </a>
        <a href="#sec-vendor" className="px-3 py-1.5 rounded-xl hover:bg-[var(--bg-elevated)] text-[var(--accent-gold)] font-bold transition-all whitespace-nowrap flex items-center gap-1">
          <Globe className="w-3 h-3 text-[var(--accent-gold)]" /> Vendor & Geology
        </a>
        <a href="#sec-resilience" className="px-3 py-1.5 rounded-xl hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all whitespace-nowrap">
          Resilience Radar
        </a>
        <a href="#sec-lifecycle" className="px-3 py-1.5 rounded-xl hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all whitespace-nowrap">
          Lifecycle & EOL
        </a>
        <a href="#sec-obsolescence" className="px-3 py-1.5 rounded-xl hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all whitespace-nowrap">
          Obsolescence (Weibull)
        </a>
        <a href="#sec-market" className="px-3 py-1.5 rounded-xl hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all whitespace-nowrap">
          Market & SPI Risk
        </a>
        <a href="#sec-mission" className="px-3 py-1.5 rounded-xl hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all whitespace-nowrap">
          Mission Profile & Thermal
        </a>
        <a href="#sec-tolerance" className="px-3 py-1.5 rounded-xl hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all whitespace-nowrap">
          Tolerance (WCCA / Monte Carlo)
        </a>
        <a href="#sec-fmea" className="px-3 py-1.5 rounded-xl hover:bg-[var(--bg-elevated)] text-rose-400 font-bold transition-all whitespace-nowrap flex items-center gap-1">
          <ShieldAlert className="w-3 h-3 text-rose-400" /> FMEA & Action Priority
        </a>
        <a href="#sec-whatif" className="px-3 py-1.5 rounded-xl hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all whitespace-nowrap">
          What-If Sandbox
        </a>
      </div>

      {/* ── Hero banner ────────────────────────────────────────────────────────── */}
      <div id="sec-overview" className="glass-card p-6 rounded-2xl">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          <div className="space-y-1.5">
            <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest">Manufacturer Part</span>
            <h2 className="text-2xl font-extrabold text-[var(--text-primary)] font-mono">{component.pn}</h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-secondary)] font-mono">
              <span className="flex items-center gap-1"><Package className="w-3.5 h-3.5" /> Ref: <strong>{component.ref}</strong></span>
              <span className="flex items-center gap-1"><Zap className="w-3.5 h-3.5" /> Qty: <strong>{component.qty}</strong></span>
              {spec?.category ? <span className="flex items-center gap-1"><Activity className="w-3.5 h-3.5" /> {String(spec.category)}</span> : null}
              {spec?.manufacturer ? <span>{String(spec.manufacturer)}</span> : null}
            </div>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {component.reasons.map((r, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded-full text-[10px] font-semibold flex items-center gap-1"
                  style={{
                    color,
                    background: `color-mix(in oklab, ${color} 10%, var(--bg-card))`,
                    border: `1px solid color-mix(in oklab, ${color} 30%, transparent)`,
                  }}
                >
                  <AlertTriangle className="w-2.5 h-2.5" />{r}
                </span>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-5">
            <ScoreRing value={hasNumericScore(component.score) ? Math.round(component.score * 100) : null} label="Risk" color={color} />
            <ScoreRing value={hasNumericScore(component.exp) ? Math.round(component.exp * 100) : null} label="Exposure" color="var(--accent-amber)" />
            <ScoreRing value={insufficientEvidence || !hasNumericScore(component.conf) ? null : Math.round(component.conf * 100)} label="Confidence" color="var(--accent-emerald)" />
          </div>
        </div>

        {/* Quick Procurement Highlights from Verified Vendor Intelligence */}
        {vendorIntelligence && (
          <div className="mt-4 pt-4 border-t border-[var(--border-subtle)] grid grid-cols-2 lg:grid-cols-4 gap-2">
            <div className="px-3 py-1.5 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] text-xs font-mono">
              <span className="text-[var(--text-muted)]">Global Stock: </span>
              <span className="font-bold text-emerald-400">
                {vendorIntelligence.market_saturation.distributors.reduce((acc, curr) => acc + curr.stock, 0).toLocaleString()} units
              </span>
            </div>
            <div className="px-3 py-1.5 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] text-xs font-mono flex items-center gap-1">
              <Clock className="w-3 h-3 text-[var(--accent-gold)]" />
              <span className="text-[var(--text-muted)]">Lead: </span>
              <span className="font-bold text-[var(--text-primary)]">
                {vendorIntelligence.market_saturation.distributors[0]?.lead_time_weeks ?? 8} weeks
              </span>
            </div>
            <div className="px-3 py-1.5 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] text-xs font-mono flex items-center gap-1">
              <DollarSign className="w-3 h-3 text-emerald-400" />
              <span className="text-[var(--text-muted)]">Price: </span>
              <span className="font-bold text-[var(--text-primary)]">
                ${vendorIntelligence.market_saturation.distributors[0]?.unit_price.toFixed(2)} USD
              </span>
            </div>
            <div className="px-3 py-1.5 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] text-xs font-mono">
              <span className="text-[var(--text-muted)]">Fab: </span>
              <span className="font-bold text-[var(--text-primary)]">
                {vendorIntelligence.geological.primary_fab_country} ({vendorIntelligence.geological.primary_fab_name})
              </span>
            </div>
          </div>
        )}

        {specsObj && (
          <div className="mt-4 pt-4 border-t border-[var(--border-subtle)] flex flex-wrap gap-2">
            {Object.entries(specsObj).map(([k, v]) => (
              <div key={k} className="px-3 py-1.5 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] text-xs font-mono">
                <span className="text-[var(--text-muted)] capitalize">{k.replace(/_/g, ' ')}: </span>
                <span className="font-bold text-[var(--text-primary)]">{String(v)}</span>
              </div>
            ))}
            {spec?.stock !== undefined && (
              <div className="px-3 py-1.5 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] text-xs font-mono">
                <span className="text-[var(--text-muted)]">Stock: </span>
                <span className="font-bold text-[var(--text-primary)]">{String(spec.stock)} units</span>
              </div>
            )}
            {spec?.lead_time_weeks !== undefined && (
              <div className="px-3 py-1.5 rounded-xl border text-xs font-mono flex items-center gap-1"
                style={{
                  background: `color-mix(in oklab, var(--risk-high) 8%, var(--bg-card))`,
                  borderColor: `color-mix(in oklab, var(--risk-high) 30%, transparent)`,
                }}
              >
                <Clock className="w-3 h-3" style={{ color: 'var(--risk-high)' }} />
                <span style={{ color: 'var(--risk-high)' }} className="font-bold">{String(spec.lead_time_weeks)}wk lead time</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Visual Vendor Intelligence, Geological Availability & Market Saturation ── */}
      {vendorIntelligence && (
        <>
          <div id="sec-vendor">
            <ComponentVendorIntelligenceCard intelligence={vendorIntelligence} />
          </div>

          <div id="sec-resilience">
            <ComponentResilienceRadarCard resilience={vendorIntelligence.resilience} partNumber={component.pn} />
          </div>

          <div id="sec-lifecycle">
            <ComponentLifecycleTimelineCard lifecycle={vendorIntelligence.lifecycle} partNumber={component.pn} />
          </div>
        </>
      )}

      {/* Normalized Technical Specs & Datasheet References */}
      {vendorIntelligence && (vendorIntelligence.normalized_specs.length > 0 || vendorIntelligence.document_links.length > 0) && (
        <div className="glass-card p-6 rounded-2xl space-y-3">
          <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest">
            Datasheet & Manufacturing Specifications
          </span>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="p-3 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)]">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Normalized Technical Parameters</p>
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {vendorIntelligence.normalized_specs.map((item, index) => (
                  <DataLine key={`${item.parameter_name}-${index}`} label={item.parameter_name} value={item.nominal_value} />
                ))}
              </div>
            </div>
            <div className="p-3 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)]">
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Compliance & Datasheet Documents</p>
              <div className="space-y-2">
                {vendorIntelligence.document_links.map((item, index) => (
                  <a
                    key={`${item.url}-${index}`}
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="block text-xs text-[var(--accent-blue)] hover:underline truncate"
                  >
                    📄 {item.title}
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Supply Flow Graph ──────────────────────────────────────────────────── */}
      <div className="glass-card p-6 rounded-2xl space-y-4">
        <div>
          <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest">Risk Decomposition</span>
          <h3 className="text-sm font-bold text-[var(--text-primary)]">How the score composes</h3>
          <p className="text-xs text-[var(--text-muted)]">Tap a node to see what fed it. Current flows left to right into the final risk output.</p>
        </div>
        {flowFactors.length > 0 ? (
        <SupplyFlowGraph
          factors={flowFactors}
          score={Math.round((component.score ?? 0.5) * 100)}
          color={color}
        />
        ) : (
          <p className="text-xs text-[var(--text-muted)]">INSUFFICIENT_DATA — no measured risk-factor contributions to decompose.</p>
        )}
      </div>

﻿      {/* ── Multi-Factor Bar Chart + AI Rationale */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="glass-card p-6 rounded-2xl space-y-3">
          <div>
            <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest">Factor Analysis</span>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">Multi-Factor Risk Breakdown</h3>
            <p className="text-xs text-[var(--text-muted)]">Horizontal bars — higher value = greater risk</p>
          </div>
          {radarData.length > 0 ? (
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={radarData} layout="vertical" margin={{ top: 4, right: 44, left: 0, bottom: 4 }}>
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 9, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="factor" width={90} tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: 'var(--bg-elevated)', opacity: 0.5 }}
                  contentStyle={{ background: 'var(--bg-surface-solid)', border: '1px solid var(--border-subtle)', borderRadius: '10px', fontSize: '11px' }}
                  formatter={(v) => [`${Number(v)}/100`, 'Risk']}
                />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={22}>
                  {radarData.map((entry, i) => {
                    const bc = entry.value >= 70 ? bandHex('CRITICAL') : entry.value >= 40 ? bandHex('HIGH') : entry.value >= 20 ? bandHex('MEDIUM') : bandHex('LOW');
                    return <Cell key={i} fill={bc} fillOpacity={0.88} />;
                  })}
                  <LabelList dataKey="value" position="right"
                    style={{ fontSize: 10, fontWeight: 700, fontFamily: 'monospace', fill: 'var(--text-primary)' }}
                    formatter={(v: any) => `${v}`}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          ) : (
            <p className="text-xs text-[var(--text-muted)]">INSUFFICIENT_DATA — factor bars are not drawn from missing vendor or lifecycle evidence.</p>
          )}
        </div>

        <div className="glass-card p-6 rounded-2xl flex flex-col gap-3 relative overflow-hidden"
          style={{
            background: `linear-gradient(135deg, color-mix(in oklab, ${color} 8%, var(--bg-card)) 0%, var(--bg-card) 55%)`,
            borderLeft: `3px solid ${color}`,
          }}
        >
          <div className="absolute top-0 right-0 w-40 h-40 rounded-full pointer-events-none"
            style={{ background: `radial-gradient(circle, color-mix(in oklab, ${color} 12%, transparent) 0%, transparent 70%)` }} />
          <div className="relative z-10 flex items-center gap-2">
            <span className="w-9 h-9 rounded-xl flex items-center justify-center text-lg shrink-0"
              style={{ background: `color-mix(in oklab, ${color} 18%, var(--bg-elevated))` }}>🤖</span>
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest" style={{ color }}>AI Risk Rationale</span>
              <h3 className="text-sm font-bold text-[var(--text-primary)]">Automated Analysis</h3>
            </div>
          </div>
          <div className="relative z-10 grid grid-cols-3 gap-2">
            {[
              { label: 'Risk Score', val: hasNumericScore(component.score) ? `${(component.score * 100).toFixed(0)}` : 'INSUFFICIENT_DATA', col: color, icon: '⚠️' },
              { label: 'Exposure', val: hasNumericScore(component.exp) ? `${(component.exp * 100).toFixed(0)}%` : 'INSUFFICIENT_DATA', col: '#F4A261', icon: '📡' },
              { label: 'Confidence', val: insufficientEvidence || !hasNumericScore(component.conf) ? 'INSUFFICIENT_DATA' : `${(component.conf * 100).toFixed(0)}%`, col: '#2A9D8F', icon: '✅' },
            ].map(({ label, val, col, icon }) => (
              <div key={label} className="text-center p-2.5 rounded-xl border"
                style={{ background: `color-mix(in oklab, ${col} 10%, var(--bg-elevated))`, borderColor: `color-mix(in oklab, ${col} 30%, transparent)` }}>
                <div className="text-base mb-0.5">{icon}</div>
                <p className="text-sm font-extrabold font-mono" style={{ color: col }}>{val}</p>
                <p className="text-[9px] text-[var(--text-muted)] font-mono uppercase">{label}</p>
              </div>
            ))}
          </div>
          <div className="relative z-10 space-y-1.5 flex-1">
            <p className="text-[10px] font-mono text-[var(--text-muted)] uppercase tracking-wider">Risk Triggers</p>
            {component.reasons.map((r, i) => (
              <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.07 }}
                className="flex items-start gap-2 px-3 py-2 rounded-lg border text-xs"
                style={{
                  background: `color-mix(in oklab, ${color} 7%, var(--bg-elevated))`,
                  borderColor: `color-mix(in oklab, ${color} 22%, transparent)`,
                  color: 'var(--text-secondary)',
                }}
              >
                <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" style={{ color }} />
                <span>{r}</span>
              </motion.div>
            ))}
          </div>
          <div className="relative z-10 pt-2 border-t border-[var(--border-subtle)] flex items-center justify-between text-[10px] text-[var(--text-muted)] font-mono">
            <span>Rule Engine v2.4</span>
            <span className="text-emerald-500 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> 100% Verified</span>
          </div>
        </div>
      </div>
      {/* ── Lifecycle timeline ─────────────────────────────────────────────────── */}
      <div className="glass-card p-6 rounded-2xl space-y-4">
        <div>
          <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest">Component Lifecycle</span>
          <h3 className="text-sm font-bold text-[var(--text-primary)]">Lifecycle</h3>
        </div>
        <LifecycleTimeline status={component.lifecycle_status} />
      </div>

      {/* ── Substitutes carousel ───────────────────────────────────────────────── */}
      <div className="glass-card p-6 rounded-2xl space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest font-semibold">Substitute Intelligence</span>
            <h3 className="text-base font-bold text-[var(--text-primary)]">Ranked Substitute Candidates</h3>
          </div>
          <div className="flex items-center gap-2">
            {substituteSource === 'UNAVAILABLE' && (
              <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full border" style={{ color: 'var(--risk-high)', background: 'color-mix(in oklab, var(--risk-high) 10%, var(--bg-card))', borderColor: 'color-mix(in oklab, var(--risk-high) 30%, transparent)' }}>
                SUBSTITUTE API UNAVAILABLE
              </span>
            )}
            {substituteSource === 'INSUFFICIENT_DATA' && (
              <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full border" style={{ color: 'var(--text-muted)', background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)' }}>
                INSUFFICIENT_DATA
              </span>
            )}
            {isApproved && (
              <span className="text-xs font-mono text-emerald-600 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {approvedSub} approved
              </span>
            )}
          </div>
        </div>

        {loadingSubstitutes ? (
          <div className="py-10 text-center text-xs text-[var(--text-muted)]">
            <div className="animate-spin w-5 h-5 border-2 border-[var(--accent-gold)] border-t-transparent rounded-full mx-auto mb-2" />
            Loading from catalog…
          </div>
        ) : substitutes.length > 0 ? (
          <SubstituteCarousel
            substitutes={substitutes}
            approvedSub={approvedSub}
            onApprove={handleApprove}
          />
        ) : (
          <p className="py-8 text-center text-sm text-[var(--text-muted)]">
            {substituteSource === 'UNAVAILABLE'
              ? 'UNAVAILABLE — the substitute service could not be reached.'
              : 'INSUFFICIENT_DATA — no evidence-backed substitute candidates for this component.'}
          </p>
        )}
      </div>

      {/* ── PS5 Engineering Modules (Parts 5, 6, 8, 9, 11, 14) ────────────────────── */}
      <div id="sec-obsolescence">
        <EngineeringObsolescenceCard data={obsolescenceData} loading={loadingEngineering} />
      </div>
      <div id="sec-market">
        <EngineeringMarketRiskCard data={marketRiskData} loading={loadingEngineering} />
      </div>
      <div id="sec-mission">
        <EngineeringMissionProfileCard data={missionProfileData} loading={loadingEngineering} />
      </div>
      <div id="sec-tolerance">
        <EngineeringToleranceCard data={toleranceData} loading={loadingEngineering} />
      </div>
      <div id="sec-fmea">
        <EngineeringFmeaCard entries={fmeaEntries} loading={loadingEngineering} />
      </div>
      <div id="sec-whatif">
        <WhatIfScenarioCard partNumber={component.pn} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className="glass-card p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest">Component Profile</span>
              <h3 className="text-sm font-bold text-[var(--text-primary)]">Evidence-Backed Identity & Operating Limits</h3>
            </div>
            <ConfidenceBadge value={componentAnalysis?.confidence ?? 'INSUFFICIENT_DATA'} />
          </div>
          {evidenceProfile ? (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-1.5">
                <DataLine label="MPN" value={evidenceProfile.identity.mpn} />
                <DataLine label="Manufacturer" value={evidenceProfile.identity.manufacturer} />
                <DataLine label="Component type" value={evidenceProfile.identity.component_type} />
                <DataLine label="Description" value={evidenceProfile.identity.description} />
                <DataLine label="Package" value={evidenceProfile.identity.package} />
              </div>
              <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
                <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Operating Limits</p>
                {profileFields.map((field) => (
                  <DataLine key={field.field} label={field.label} value={field.value} suffix={field.unit ? ` ${field.unit}` : ''} />
                ))}
              </div>
              <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Tolerance</p>
                  <ConfidenceBadge value={toleranceFields[0]?.confidence ?? 'INSUFFICIENT_DATA'} />
                </div>
                {toleranceFields.length > 0 ? toleranceFields.map((field) => (
                  <div key={field.field}>
                    <DataLine label={field.label} value={field.value} suffix={field.unit ? ` ${field.unit}` : ''} />
                    <DataLine label="Source document" value={field.source_document} />
                    <DataLine label="Source page" value={field.source_page} />
                  </div>
                )) : <p className="text-xs text-[var(--text-muted)]">INSUFFICIENT_DATA</p>}
              </div>
              <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
                <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Component-Specific Parameters</p>
                {specificFields.length > 0 ? specificFields.map((field) => (
                  <DataLine key={field.field} label={field.label} value={field.value} suffix={field.unit ? ` ${field.unit}` : ''} />
                )) : <p className="text-xs text-[var(--text-muted)]">INSUFFICIENT_DATA</p>}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-1.5">
                <DataLine label="MPN" value={component.pn} />
                <DataLine label="Reference Designator" value={component.ref} />
                <DataLine label="Quantity" value={String(component.qty)} />
                <DataLine label="Category" value={component.category ?? 'Unclassified SMD / SMT'} />
                <DataLine label="Package / Case" value={spec?.package ? String(spec.package) : spec?.footprint ? String(spec.footprint) : 'Standard SMD footprint'} />
                {spec?.voltage_rating_v ? <DataLine label="Rated Voltage" value={String(spec.voltage_rating_v)} suffix=" V" /> : null}
                {spec?.resistance_ohms ? <DataLine label="Nominal Resistance" value={String(spec.resistance_ohms)} suffix=" Ω" /> : null}
                {spec?.capacitance_uf ? <DataLine label="Nominal Capacitance" value={String(spec.capacitance_uf)} suffix=" µF" /> : null}
                {spec?.tolerance ? <DataLine label="Catalog Tolerance" value={String(spec.tolerance)} suffix="%" /> : null}
              </div>
              <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-2">
                <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Engineering Derating Baseline (IPC-9592B / MIL-HDBK-338B)</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)]">
                    <span className="text-[10px] text-[var(--text-muted)] block">Voltage Derating Rule</span>
                    <span className="font-mono font-bold text-emerald-400">≤ 80% V_max</span>
                    <p className="text-[10px] text-[var(--text-muted)] mt-1">Prevents dielectric puncture</p>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)]">
                    <span className="text-[10px] text-[var(--text-muted)] block">Thermal Junction Margin</span>
                    <span className="font-mono font-bold text-emerald-400">≥ 25°C headroom</span>
                    <p className="text-[10px] text-[var(--text-muted)] mt-1">Arrhenius life factor</p>
                  </div>
                </div>
                <div className="p-2.5 rounded-lg bg-[var(--bg-card)] border border-amber-500/20 text-[11px] text-[var(--text-secondary)] flex items-start gap-2">
                  <FileText className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-[var(--text-primary)]">Datasheet Ingestion Checklist:</span>
                    <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                      To lock Level-5 Evidence confidence, link the manufacturer PDF datasheet or provide live Mouser/DigiKey API credentials in Settings.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="glass-card p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest">Evidence</span>
              <h3 className="text-sm font-bold text-[var(--text-primary)]">Parameter Support & Source Traceability</h3>
            </div>
            <span className="text-[11px] font-mono text-[var(--text-muted)]">{evidenceRows.length} sources</span>
          </div>
          {evidenceRows.length > 0 ? (
            <div className="space-y-3 max-h-[34rem] overflow-y-auto pr-1">
              {evidenceRows.map((row) => (
                <div key={row.source_id} className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-bold text-[var(--text-primary)]">{row.parameter_supported}</p>
                    <ConfidenceBadge value={row.confidence} />
                  </div>
                  <p className="text-xs text-[var(--text-secondary)]">{row.evidence_summary}</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                    <div className="text-[var(--text-muted)]">Source title: <span className="text-[var(--text-primary)]">{row.source_title}</span></div>
                    <div className="text-[var(--text-muted)]">Source type: <span className="text-[var(--text-primary)]">{row.source_type}</span></div>
                    <div className="text-[var(--text-muted)]">Manufacturer: <span className="text-[var(--text-primary)]">{row.manufacturer}</span></div>
                    <div className="text-[var(--text-muted)]">Page: <span className="text-[var(--text-primary)]">{row.source_page}</span></div>
                  </div>
                  <a href={row.source_url} target="_blank" rel="noreferrer" className="text-xs font-mono text-[var(--accent-blue)] break-all">
                    View Evidence: {row.source_url}
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-amber-400">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>Datasheet Extraction Repository Standby</span>
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                PS5 enforces strict engineering evidence provenance: parameter assertions (derating, MTBF, failure rates) are only marked 100% verified when grounded in a manufacturer datasheet, qualification test report (AEC-Q100 / AEC-Q200), or verified distributor spec sheet.
              </p>
              <div className="p-3 rounded-lg bg-[var(--bg-card)] text-xs font-mono text-[var(--text-muted)] space-y-1.5 border border-[var(--border-subtle)]">
                <div className="text-[11px] font-bold text-[var(--text-primary)] font-sans">Vendor & Spec Requirements for Level-5 Evidence:</div>
                <div className="text-[11px]">• <strong>Distributor Snapshots:</strong> Stock, Lead Time (weeks), Minimum Order Quantity (MOQ), Price Tiers</div>
                <div className="text-[11px]">• <strong>Electrical Limits:</strong> V_breakdown, I_continuous, R_theta_JC (°C/W), Max Junction Temp Tj</div>
                <div className="text-[11px]">• <strong>Reliability Standards:</strong> JEDEC JESD47, MIL-STD-883, FIT rate at 55°C</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {hasExactToleranceEvidence ? (
        <div className="glass-card p-6 rounded-2xl space-y-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest">Synthetic Risk Modelling</span>
              <h3 className="text-sm font-bold text-[var(--text-primary)]">Tolerance Levels & Ageing Analysis</h3>
            </div>
            <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full border text-[var(--risk-high)] bg-[color-mix(in_oklab,var(--risk-high)_10%,var(--bg-card))] border-[color-mix(in_oklab,var(--risk-high)_30%,transparent)]">
              SYNTHETIC DEMO DATA
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Generated from the selected BOM risk band, exposure, confidence, and available catalog specs for {syntheticKind}. This is for ageing visualization and prioritization only, not manufacturer evidence.
          </p>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-3">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Tolerance Window</p>
                <p className="text-xs text-[var(--text-secondary)]">Nominal vs low/high tolerance limits and an aged demo point.</p>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={syntheticToleranceBars} margin={{ top: 12, right: 12, left: 0, bottom: 4 }}>
                    <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
                    <Tooltip cursor={{ fill: 'var(--bg-card)', opacity: 0.45 }} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 12 }} />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                      {syntheticToleranceBars.map((entry) => (
                        <Cell key={entry.label} fill={entry.label === 'Aged demo' ? color : 'var(--accent-blue)'} />
                      ))}
                      <LabelList dataKey="value" position="top" style={{ fill: 'var(--text-secondary)', fontSize: 10, fontFamily: 'monospace' }} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-3">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Ageing Drift Scenario</p>
                <p className="text-xs text-[var(--text-secondary)]">Synthetic condition and operating-margin trend for risky component review.</p>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={syntheticAgeingData} margin={{ top: 12, right: 16, left: 0, bottom: 4 }}>
                    <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
                    <XAxis dataKey="year" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 12 }} />
                    <Line type="monotone" dataKey="condition" name="Condition %" stroke="var(--risk-low)" strokeWidth={2.5} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="margin" name="Margin %" stroke={color} strokeWidth={2.5} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">Ageing Degradation Envelope</p>
              <p className="text-xs text-[var(--text-secondary)]">Synthetic drift grows over time while the tolerance band stays visible as a review boundary.</p>
            </div>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={syntheticAgeingData} margin={{ top: 12, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
                  <XAxis dataKey="year" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 12 }} />
                  <Area type="monotone" dataKey="drift" name="Synthetic drift %" stroke={color} fill={color} fillOpacity={0.18} strokeWidth={2.5} />
                  <Line type="monotone" dataKey="toleranceBand" name="Tolerance band %" stroke="var(--accent-blue)" strokeDasharray="5 5" strokeWidth={2} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : (
        <div className="glass-card p-6 rounded-2xl space-y-4 border border-[var(--border-subtle)]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest font-semibold">Tolerance & Degradation Verification</span>
              <h3 className="text-sm font-bold text-[var(--text-primary)]">Worst-Case Circuit Analysis (WCCA) & Physics-of-Failure</h3>
            </div>
            <a
              href="#sec-tolerance"
              className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-[var(--bg-elevated)] hover:bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--accent-blue)] self-start sm:self-auto transition-all"
            >
              View Monte Carlo Model ↑
            </a>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Exact empirical laboratory ageing curves require manufacturer qualification test records (e.g. HTOL 1,000h @ 125°C). In the meantime, full parametric Monte Carlo simulation and RSS tolerance distributions for <strong>{component.pn}</strong> are calculated and displayed in the <strong>Tolerance & Ageing Card</strong> above.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
            <div className="p-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
              <span className="text-[10px] text-[var(--text-muted)] block font-mono">WCCA Worst-Case</span>
              <span className="text-xs font-bold text-[var(--text-primary)] font-mono">Algebraic Linear Sum</span>
              <p className="text-[10px] text-[var(--text-muted)] mt-1">Extreme envelope limits</p>
            </div>
            <div className="p-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
              <span className="text-[10px] text-[var(--text-muted)] block font-mono">RSS Statistical</span>
              <span className="text-xs font-bold text-emerald-400 font-mono">3-Sigma Gaussian Stack</span>
              <p className="text-[10px] text-[var(--text-muted)] mt-1">Realistic 99.73% boundary</p>
            </div>
            <div className="p-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
              <span className="text-[10px] text-[var(--text-muted)] block font-mono">Monte Carlo Iterations</span>
              <span className="text-xs font-bold text-[var(--accent-blue)] font-mono">1,000 Runs</span>
              <p className="text-[10px] text-[var(--text-muted)] mt-1">Parameter distribution curve</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Engineering Standards & Reliability Traceability ── */}
      <div className="glass-card p-6 rounded-2xl space-y-4 border border-[var(--border-subtle)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest font-semibold">Reliability Architecture</span>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">Engineering Calculation Engines & Evidence Traceability</h3>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
            All 5 Mathematical Engines Active
          </span>
        </div>

        <p className="text-xs text-[var(--text-secondary)]">
          PS5 replaces static assumptions with physics-of-failure equations and empirical industry standards. The active status of the mathematical engines for <strong>{component.pn}</strong> is verified below:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          <div className="p-3.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-[var(--text-primary)]">Arrhenius Thermal Model</span>
              <span className="text-[10px] font-mono text-emerald-400">MIL-HDBK-217F</span>
            </div>
            <p className="text-[11px] text-[var(--text-secondary)]">
              Calculates thermal acceleration factor AF = exp[(Ea/k)(1/T_use - 1/T_stress)]. Active in Mission Profile card.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-[var(--text-primary)]">Weibull 2-Parameter Forecasting</span>
              <span className="text-[10px] font-mono text-emerald-400">IEEE 1413</span>
            </div>
            <p className="text-[11px] text-[var(--text-secondary)]">
              Computes cumulative survival probability F(t) = 1 - exp(-(t/η)^β). Active in Obsolescence card.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-[var(--text-primary)]">AIAG-VDA FMEA Action Priority</span>
              <span className="text-[10px] font-mono text-emerald-400">IEC 60812</span>
            </div>
            <p className="text-[11px] text-[var(--text-secondary)]">
              Multi-dimensional matrix evaluating Severity, Occurrence, and Detection for failure mechanisms. Active in FMEA card.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-[var(--text-primary)]">SPI & HHI Market Concentration</span>
              <span className="text-[10px] font-mono text-emerald-400">Herfindahl Metric</span>
            </div>
            <p className="text-[11px] text-[var(--text-secondary)]">
              Evaluates multi-distributor inventory dispersion, lead-time volatility, and pipeline health. Active in Market Risk card.
            </p>
          </div>
        </div>

        {reliability?.data?.length ? (
          <div className="mt-4 pt-4 border-t border-[var(--border-subtle)] space-y-3">
            <h4 className="text-xs font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider">Manufacturer Qualification Test Records</h4>
            <div className="space-y-2">
              {reliability.data.map((row, index) => (
                <div key={`${row.source_document}-${index}`} className="p-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-xs">
                  <div className="flex justify-between font-bold text-[var(--text-primary)]">
                    <span>{row.reliability_metric_type} ({row.qualification_standard})</span>
                    <span className="font-mono text-emerald-400">{row.fit} FIT</span>
                  </div>
                  <p className="text-[11px] text-[var(--text-secondary)] mt-1">
                    MTBF: {row.mtbf} · Sample: {row.sample_size} · Failures: {row.failures} · Test: {row.reliability_test_type} ({row.test_temperature})
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      {substitutes.length > 0 && (
        <div className="glass-card p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest">Recommendation</span>
              <h3 className="text-sm font-bold text-[var(--text-primary)]">Reliability Outlook & Engineering Action</h3>
            </div>
            <ConfidenceBadge value={substitutes[0].final_engineering_recommendation?.confidence ?? substitutes[0].reliability_outlook?.confidence ?? 'INSUFFICIENT_DATA'} />
          </div>
          <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-3">
            <p className="text-sm font-bold text-[var(--text-primary)]">
              Reliability Outlook: {substitutes[0].reliability_outlook?.outcome ?? 'INSUFFICIENT_DATA'}
            </p>
            <p className="text-xs text-[var(--text-secondary)]">{substitutes[0].reliability_outlook?.reason ?? 'No evidence-backed reliability comparison available.'}</p>
            <p className="text-sm font-bold text-[var(--text-primary)]">
              Final Recommendation: {substitutes[0].final_engineering_recommendation?.recommendation ?? 'INSUFFICIENT DATA'}
            </p>
            <p className="text-xs text-[var(--text-secondary)]">{substitutes[0].final_engineering_recommendation?.reason ?? 'No integrated engineering recommendation available.'}</p>
            {substitutes[0].reliability_outlook?.evidence?.length ? (
              <div className="space-y-2 pt-2 border-t border-[var(--border-subtle)]">
                {substitutes[0].reliability_outlook?.evidence.map((item, index) => (
                  <div key={`${item.factor}-${index}`} className="text-xs text-[var(--text-secondary)]">
                    <strong className="text-[var(--text-primary)]">{item.factor}:</strong> original `{item.original}` vs candidate `{item.candidate}`. {item.reason}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
};

