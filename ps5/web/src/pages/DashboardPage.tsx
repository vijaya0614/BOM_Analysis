import React, { useState } from 'react';
import type { RiskReportDashboard, BOMComponent } from '../types';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip
} from 'recharts';
import {
  ShieldAlert, AlertTriangle, CheckCircle2, Cpu, ArrowUpRight,
  Flame, TrendingUp, Activity, ArrowRight, Layers, Package, Radar,
  Power, Waves, Boxes, Zap
} from 'lucide-react';
import { motion } from 'framer-motion';
import { Sparkline, RiskBadge, bandColorVar, StatsStat } from '../components/primitives';
import type { RiskBand } from '../components/primitives';
import { buildPerformanceCurve, bandHex, scoreHex, hasNumericScore } from '../utils/riskUtils';
import { ProductRiskSummaryCard } from '../components/ProductRiskSummaryCard';
import { ComponentVisualExposureMap } from '../components/ComponentVisualExposureMap';

const CATEGORY_ICONS: Record<string, React.FC<{ className?: string }>> = {
  'Microcontroller': Cpu,
  'Power Management': Power,
  'Sensor': Radar,
  'Passive': Layers,
  'Transistor': Waves,
  'Interface': Layers,
};

interface DashboardPageProps {
  report: RiskReportDashboard | null;
  bandFilter?: RiskBand | 'ALL';
  onBandFilterChange?: (band: RiskBand | 'ALL') => void;
  onSelectComponent: (comp: BOMComponent) => void;
  onNavigateToUpload: () => void;
  onNavigateToComponents?: () => void;
}

// ── AI Risk Summary Panel ───────────────────────────────────────────────────
const AISummaryPanel: React.FC<{ report: RiskReportDashboard }> = ({ report }) => {
  const parts = report.parts || [];
  const topRisk = [...parts].filter(p => hasNumericScore(p.score)).sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 3);
  const criticalPart = parts.find(p => p.band === 'CRITICAL');
  const insufficient = String(report.overall || '').toUpperCase() === 'INSUFFICIENT_DATA' || !hasNumericScore(report.avg_score);
  const healthScore = insufficient || report.avg_score == null ? null : Math.max(0, Math.min(100, Math.round((1 - report.avg_score) * 100)));
  const urgencyColor = healthScore == null ? '#94867F' : healthScore < 40 ? '#E76F51' : healthScore < 60 ? '#F4A261' : '#2A9D8F';

  const insights = insufficient
    ? [
        { icon: '⚪', text: 'Risk bands are INSUFFICIENT_DATA — no measured lifecycle, stock, lead-time, or second-source evidence', color: '#94867F' },
        { icon: '📊', text: 'BOM completeness INSUFFICIENT_DATA — vendor and lifecycle tables are empty for this industry session', color: '#E9C46A' },
        { icon: '⚡', text: `Average exposure INSUFFICIENT_DATA across ${report.total_parts} parts`, color: '#4EA8DE' },
      ]
    : [
        criticalPart
          ? { icon: '🔴', text: `${criticalPart.pn} is CRITICAL — ${criticalPart.reasons[0] ?? 'immediate action required'}`, color: '#E76F51' }
          : { icon: '✅', text: 'No critical components detected', color: '#2A9D8F' },
        report.high > 0
          ? { icon: '🟠', text: `${report.high} parts at HIGH risk — review sourcing strategy`, color: '#F4A261' }
          : { icon: '✅', text: 'No high-risk sourcing issues', color: '#2A9D8F' },
        { icon: '📊', text: `BOM completeness ${report.completeness}% — ${report.completeness > 90 ? 'excellent data quality' : 'consider enriching part specs'}`, color: '#E9C46A' },
        { icon: '⚡', text: report.avg_score != null ? `Average exposure ${(report.avg_score * 100).toFixed(0)}% across ${report.total_parts} parts` : `Average exposure INSUFFICIENT_DATA across ${report.total_parts} parts`, color: '#4EA8DE' },
      ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="glass-card p-6 rounded-2xl space-y-4 relative overflow-hidden"
      style={{
        background: `linear-gradient(135deg, color-mix(in oklab, ${urgencyColor} 8%, var(--bg-card)) 0%, var(--bg-card) 60%)`,
        borderLeft: `3px solid ${urgencyColor}`,
      }}
    >
      {/* Decorative glow */}
      <div className="absolute top-0 right-0 w-48 h-48 rounded-full pointer-events-none"
        style={{
          background: `radial-gradient(circle, color-mix(in oklab, ${urgencyColor} 15%, transparent) 0%, transparent 70%)`,
        }}
      />

      <div className="flex items-center gap-3 relative z-10">
        <span
          className="w-10 h-10 rounded-xl flex items-center justify-center text-xl shrink-0"
          style={{
            background: `color-mix(in oklab, ${urgencyColor} 18%, var(--bg-elevated))`,
            boxShadow: `0 2px 12px -2px color-mix(in oklab, ${urgencyColor} 45%, transparent)`,
          }}
        >
          🤖
        </span>
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest" style={{ color: urgencyColor }}>AI Risk Intelligence</span>
          <h3 className="text-sm font-bold text-[var(--text-primary)]">Automated BOM Health Assessment</h3>
        </div>
        <span
          className="ml-auto px-2 py-0.5 rounded-full text-[10px] font-bold border font-mono"
          style={{
            color: urgencyColor,
            borderColor: `color-mix(in oklab, ${urgencyColor} 40%, transparent)`,
            background: `color-mix(in oklab, ${urgencyColor} 12%, var(--bg-card))`,
          }}
        >
          LIVE
        </span>
      </div>

      {/* Risk insights list */}
      <div className="space-y-2 relative z-10">
        {insights.map((ins, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15 + i * 0.08 }}
            className="flex items-start gap-3 p-3 rounded-xl border"
            style={{
              background: `color-mix(in oklab, ${ins.color} 6%, var(--bg-elevated))`,
              borderColor: `color-mix(in oklab, ${ins.color} 25%, transparent)`,
            }}
          >
            <span className="text-base shrink-0 leading-none mt-0.5">{ins.icon}</span>
            <p className="text-xs leading-relaxed" style={{ color: ins.color }}>{ins.text}</p>
          </motion.div>
        ))}
      </div>

      {/* Top risk chips */}
      {topRisk.length > 0 && (
        <div className="relative z-10">
          <p className="text-[10px] font-mono text-[var(--text-muted)] uppercase tracking-wider mb-2">Top Risk Components</p>
          <div className="flex flex-wrap gap-2">
            {topRisk.map(p => {
              const c = bandHex(p.band as RiskBand);
              return (
                <motion.span
                  key={`${p.pn}-${p.ref}`}
                  whileHover={{ scale: 1.05 }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-mono font-bold border cursor-default"
                  style={{
                    color: c,
                    background: `color-mix(in oklab, ${c} 12%, var(--bg-card))`,
                    borderColor: `color-mix(in oklab, ${c} 35%, transparent)`,
                    boxShadow: `0 2px 8px -2px color-mix(in oklab, ${c} 30%, transparent)`,
                  }}
                >
                  <span className="w-1.5 h-1.5 rounded-full shrink-0 animate-pulse" style={{ backgroundColor: c }} />
                  {p.pn}
                  <span className="ml-1 px-1.5 py-0.5 rounded-full text-[9px] font-bold"
                    style={{ background: `color-mix(in oklab, ${c} 20%, var(--bg-card))` }}>
                    {(hasNumericScore(p.score) ? Math.round(p.score * 100) : 'INSUFFICIENT_DATA')}
                  </span>
                </motion.span>
              );
            })}
          </div>
        </div>
      )}

      <div className="relative z-10 flex items-center justify-between pt-2 border-t border-[var(--border-subtle)] text-[10px] text-[var(--text-muted)] font-mono">
        <span className="flex items-center gap-1"><Zap className="w-3 h-3" /> Deterministic Rule Engine v2.4</span>
        <span className="flex items-center gap-1 text-emerald-500"><CheckCircle2 className="w-3 h-3" /> 100% Verifiable · No LLM</span>
      </div>
    </motion.div>
  );
};

const DataQualityPanel: React.FC<{ report: RiskReportDashboard }> = ({ report }) => {
  const integrity = report.input_integrity;
  const quality = report.source_quality;
  if (!integrity && !quality) return null;
  const status = integrity?.status || 'UNKNOWN';
  const concerns = (quality?.vendor_supply_stale_parts || 0)
    + (quality?.vendor_supply_unknown_parts || 0)
    + (quality?.parts_with_unresolved_conflicts || 0);
  return (
    <section aria-label="Input data quality" className="glass-card rounded-2xl border border-amber-500/30 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Input data quality</h2>
        <span className="rounded-full bg-amber-500/15 px-2.5 py-1 text-xs font-semibold text-amber-300">{status}</span>
      </div>
      <p className="mt-2 text-sm text-slate-400">
        {integrity?.selected_revision
          ? `Selected BOM revision ${integrity.selected_revision}${integrity.revision_verified ? '' : ' (release revision unverified)'}.`
          : integrity?.source_bom
            ? `Input snapshot: ${integrity.source_bom}; manufacturer revision is unverified.`
            : 'BOM revision and source freshness need review.'}
        {quality ? ` Supplier inputs: ${quality.vendor_supply_current_parts || 0} part(s) have current offers; ${concerns} stale, unknown, or conflict flags need review.` : ''}
      </p>
      {integrity?.limitations?.[0] && <p className="mt-1 text-xs text-slate-500">{integrity.limitations[0]}</p>}
    </section>
  );
};

// ── Needs Attention row ─────────────────────────────────────────────────────
const AttentionRow: React.FC<{
  comp: BOMComponent;
  onClick: () => void;
  index: number;
}> = ({ comp, onClick, index }) => {
  const band = comp.band as RiskBand;
  const color = bandHex(band);
  const sparkData = buildPerformanceCurve(comp);
  const scoreInt = hasNumericScore(comp.score) ? Math.round(comp.score * 100) : undefined;
  const CatIcon = (comp.category && CATEGORY_ICONS[comp.category]) || Package;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      onClick={onClick}
      className="flex items-center gap-3 px-4 py-3.5 cursor-pointer transition-all group rounded-xl"
      style={{
        background: `linear-gradient(90deg, color-mix(in oklab, ${color} 7%, var(--bg-card)) 0%, var(--bg-card) 35%)`,
        borderLeft: `4px solid color-mix(in oklab, ${color} 75%, transparent)`,
      }}
      whileHover={{
        background: `linear-gradient(90deg, color-mix(in oklab, ${color} 13%, var(--bg-card)) 0%, var(--bg-card) 45%)` as any,
      }}
    >
      <span
        className="hidden sm:flex shrink-0 w-9 h-9 rounded-xl items-center justify-center border"
        style={{
          color,
          background: `color-mix(in oklab, ${color} 12%, var(--bg-card))`,
          borderColor: `color-mix(in oklab, ${color} 35%, transparent)`,
        }}
      >
        <CatIcon className="w-4 h-4" />
      </span>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-[var(--text-primary)] font-mono truncate">{comp.pn}</p>
        <p className="text-xs text-[var(--text-muted)] truncate flex items-center gap-1.5">
          <span>{comp.ref} · qty {comp.qty}</span>
          <span style={{ color: 'var(--border-strong)' }}>•</span>
          <span>exp {hasNumericScore(comp.exp) ? `${(comp.exp * 100).toFixed(0)}%` : 'INSUFFICIENT_DATA'}</span>
          {comp.lead_time_weeks && (
            <>
              <span style={{ color: 'var(--border-strong)' }}>•</span>
              <span style={{ color }}>{comp.lead_time_weeks}wk lead</span>
            </>
          )}
        </p>
      </div>

      <div className="shrink-0 hidden sm:block opacity-80 group-hover:opacity-100 transition-opacity">
        <Sparkline data={sparkData} color={color} width={80} height={28} />
      </div>

      <RiskBadge band={band} score={scoreInt} />
      <ArrowRight className="w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-[var(--text-primary)] transition-colors shrink-0" />
    </motion.div>
  );
};

// ── Main Dashboard ──────────────────────────────────────────────────────────
export const DashboardPage: React.FC<DashboardPageProps> = ({
  report,
  bandFilter,
  onBandFilterChange,
  onSelectComponent,
  onNavigateToUpload,
}) => {
  const [localFilter, setLocalFilter] = useState<RiskBand | 'ALL'>('ALL');
  const activeFilter = bandFilter ?? localFilter;
  const setActiveFilter = (b: RiskBand | 'ALL') => {
    setLocalFilter(b);
    onBandFilterChange?.(b);
  };

  if (!report) {
    return (
      <div className="p-8 text-center glass-panel rounded-2xl">
        <Cpu className="w-12 h-12 text-[var(--accent-gold)] mx-auto animate-bounce mb-3" />
        <h2 className="text-xl font-bold">Connecting to Risk Engine…</h2>
        <p className="text-sm text-[var(--text-muted)] mt-1">Make sure the Python API is running on <code className="font-mono">:8000</code></p>
      </div>
    );
  }

  const parts = report.parts || [];
  const filteredParts = activeFilter === 'ALL' ? parts : parts.filter(p => p.band === activeFilter);
  const insufficientOverall = String(report.overall || '').toUpperCase() === 'INSUFFICIENT_DATA' || !hasNumericScore(report.avg_score);
  const healthScore = insufficientOverall || report.avg_score == null ? null : Math.max(0, Math.min(100, Math.round((1 - report.avg_score) * 100)));
  const healthColor = insufficientOverall || report.avg_score == null ? bandHex('INSUFFICIENT_DATA') : scoreHex(report.avg_score);
  const avgRiskLabel = insufficientOverall || report.avg_score == null ? 'INSUFFICIENT_DATA' : String(Math.round(report.avg_score * 100));

  const trendData = [...parts]
    .filter(p => hasNumericScore(p.score))
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .map((p, i) => ({ time: p.ref || `P${i}`, risk: parseFloat((p.score ?? 0).toFixed(3)) }));

  // Derive real counts from normalized parts
  const critCount = parts.filter(p => p.band === 'CRITICAL').length;
  const highCount = parts.filter(p => p.band === 'HIGH').length;
  const medCount = parts.filter(p => p.band === 'MEDIUM').length;
  const lowCount = parts.filter(p => p.band === 'LOW').length;

  return (
    <div className="space-y-6 pb-12">

      {/* ── Hero summary strip */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-5 rounded-2xl flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4"
      >
        <div className="space-y-1">
          <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest">Active BOM</span>
          <h2 className="text-xl font-extrabold text-[var(--text-primary)]">{report.name}</h2>
          <p className="text-xs text-[var(--text-muted)] font-mono flex items-center gap-1.5">
            <Boxes className="w-3.5 h-3.5" /> {report.total_parts} parts · {report.total_units} units · completeness {insufficientOverall ? 'INSUFFICIENT_DATA' : `${report.completeness}%`}
          </p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 w-full lg:w-auto">
          <StatsStat label="Parts" value={report.total_parts} icon={<Boxes className="w-4 h-4" />} color="var(--accent-blue)" />
          <StatsStat label="Avg Risk" value={avgRiskLabel} sub={insufficientOverall ? undefined : '/ 100'} icon={<Activity className="w-4 h-4" />} color="var(--accent-amber)" />
          <StatsStat label="Critical" value={critCount} icon={<AlertTriangle className="w-4 h-4" />} color={bandColorVar.CRITICAL} />
          <StatsStat label="Healthy" value={lowCount} icon={<CheckCircle2 className="w-4 h-4" />} color={bandColorVar.LOW} />
        </div>
      </motion.div>

      {/* ── Health gauge + trend chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="glass-card p-6 rounded-2xl flex items-center justify-between relative overflow-hidden">
          <div className="space-y-2 z-10">
            <span className="text-xs font-mono text-[var(--text-muted)] uppercase tracking-wider">BOM Health Score</span>
            <div className="flex items-baseline gap-2">
              <span className="text-5xl font-extrabold tracking-tight text-[var(--text-primary)]">{healthScore == null ? 'INSUFFICIENT_DATA' : healthScore}</span>
              {healthScore != null && <span className="text-lg font-medium text-[var(--text-muted)]">/ 100</span>}
            </div>
            <div className="flex items-center gap-2 text-xs">
              <RiskBadge band={report.overall as RiskBand} />
              <span className="text-[var(--text-secondary)]">{report.total_parts} Lines</span>
            </div>
          </div>
          <div className="relative w-28 h-28 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
              <path className="text-[var(--bg-elevated)]" strokeWidth="4" stroke="currentColor" fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
              <motion.path
                strokeWidth="4" strokeLinecap="round" stroke={healthColor} fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                initial={{ strokeDasharray: '0, 100' }}
                animate={{ strokeDasharray: `${healthScore ?? 0}, 100` }}
                transition={{ duration: 1.2, ease: 'easeOut' }}
              />
            </svg>
            <div className="absolute flex flex-col items-center">
              <ShieldAlert className="w-5 h-5 text-[var(--accent-gold)]" />
            </div>
          </div>
        </div>

        <div className="glass-card p-6 rounded-2xl lg:col-span-2 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <div>
              <span className="text-xs font-mono text-[var(--text-muted)] uppercase tracking-wider">Risk Index · Per Component</span>
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">Score Distribution Across BOM</h3>
            </div>
            <span className="flex items-center gap-1 text-xs font-mono font-medium" style={{ color: bandColorVar.LOW }}>
              <TrendingUp className="w-3.5 h-3.5" />{lowCount} healthy parts
            </span>
          </div>
          <div className="h-32 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={healthColor} stopOpacity={0.45} />
                    <stop offset="95%" stopColor={healthColor} stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={10} tickLine={false} />
                <YAxis hide domain={[0, 1]} />
                <Tooltip contentStyle={{ background: 'var(--bg-surface-solid)', border: '1px solid var(--border-subtle)', borderRadius: '12px', fontSize: '12px' }} />
                <Area type="monotone" dataKey="risk" stroke={healthColor} strokeWidth={2} fillOpacity={1} fill="url(#riskGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── AI Summary */}
      <DataQualityPanel report={report} />
      <AISummaryPanel report={report} />

      {/* ── PS5 Product-Level Risk Aggregation (Part 13) ── */}
      <ProductRiskSummaryCard />

      {/* ── Filter pills (real counts, consistent with components page) */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { band: 'ALL' as const, label: 'All Parts', count: parts.length, icon: Activity, color: 'var(--text-secondary)' },
          { band: 'CRITICAL' as const, label: 'Critical', count: critCount, icon: AlertTriangle, color: bandHex('CRITICAL') },
          { band: 'HIGH' as const, label: 'At Risk', count: highCount, icon: Flame, color: bandHex('HIGH') },
          { band: 'MEDIUM' as const, label: 'Medium', count: medCount, icon: ShieldAlert, color: bandHex('MEDIUM') },
          { band: 'LOW' as const, label: 'Healthy', count: lowCount, icon: CheckCircle2, color: bandHex('LOW') },
        ].map(({ band, label, count, icon: Icon, color }) => (
          <button
            key={band}
            onClick={() => setActiveFilter(activeFilter === band ? 'ALL' : band)}
            className="glass-card p-4 rounded-2xl text-left transition-all cursor-pointer hover:scale-[1.02]"
            style={{
              boxShadow: activeFilter === band
                ? `0 0 0 2px ${color === 'var(--text-secondary)' ? 'var(--border-strong)' : color}`
                : 'none',
              background: activeFilter === band
                ? `color-mix(in oklab, ${color} 12%, var(--bg-card))`
                : 'var(--bg-card)',
            }}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-[var(--text-secondary)] font-medium">{label}</span>
              <Icon className="w-4 h-4" style={{ color }} />
            </div>
            <div className="text-3xl font-extrabold" style={{ color }}>{count}</div>
          </button>
        ))}
      </div>

      {/* ── Visual Exposure Map & Infographic Topology (Uncluttered Treemap, Bubbles & Pareto) ── */}
      <ComponentVisualExposureMap parts={parts} onSelectComponent={onSelectComponent} />

      {/* ── Needs Attention list */}
      <div className="rounded-2xl overflow-hidden border border-[var(--border-subtle)] bg-[var(--bg-card)]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-subtle)]">
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            Needs attention
            <span className="ml-2 text-sm font-normal text-[var(--text-muted)]">{filteredParts.length}</span>
          </h3>
          <button
            onClick={onNavigateToUpload}
            className="text-xs text-[var(--accent-amber)] hover:underline flex items-center gap-1 font-medium cursor-pointer"
          >
            Upload BOM <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="divide-y divide-[var(--border-subtle)]">
          {filteredParts.length === 0 ? (
            <div className="py-10 text-center text-sm text-[var(--text-muted)]">No components match this filter.</div>
          ) : (
            filteredParts.map((comp, i) => (
              <div key={`${comp.pn}-${comp.ref}`} className="px-2 py-1">
                <AttentionRow comp={comp} onClick={() => onSelectComponent(comp)} index={i} />
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
