import React, { useState, useMemo, useEffect } from 'react';
import type { BOMComponent, RiskBand } from '../types';
import {
  Sparkline, RiskBadge, stagger, staggerItem,
  bandLabel, RiskDot, StatsStat,
} from '../components/primitives';
import {
  Search, Grid, Table as TableIcon, ChevronRight, Filter,
  Cpu, Power, Layers, Radar, Waves, Package, ArrowUpDown,
  ArrowUp, ArrowDown, Boxes, AlertTriangle, CheckCircle2, Flame, ShieldAlert,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { buildPerformanceCurve, bandHex, hasNumericScore, scoreDisplay } from '../utils/riskUtils';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, Cell } from 'recharts';
import { X } from 'lucide-react';

// Recharts' formatter type is overly narrow for tooltip values that may be absent.
const Tooltip = RechartsTooltip as React.ComponentType<any>;

interface ComponentTablePageProps {
  components: BOMComponent[];
  bandFilter?: RiskBand | 'ALL';
  onBandFilterChange?: (band: RiskBand | 'ALL') => void;
  onSelectComponent: (comp: BOMComponent) => void;
  onNavigateToUpload?: () => void;
}

const CATEGORY_ICONS: Record<string, React.FC<{ className?: string }>> = {
  'Microcontroller': Cpu,
  'Power Management': Power,
  'Sensor': Radar,
  'Passive': Layers,
  'Transistor': Waves,
  'Interface': Layers,
};

const riskDistributionCategories = ['Resistors', 'Capacitors', 'ICs', 'Connectors', 'Sensors', 'Power Components'] as const;

const distributionCategory = (comp: BOMComponent): typeof riskDistributionCategories[number] => {
  const value = `${comp.category ?? ''} ${comp.pn} ${comp.ref}`.toLowerCase();
  if (value.includes('resistor') || /^r\d/.test(comp.ref.toLowerCase())) return 'Resistors';
  if (value.includes('capacitor') || /^c\d/.test(comp.ref.toLowerCase()) || value.includes('passive')) return 'Capacitors';
  if (value.includes('connector')) return 'Connectors';
  if (value.includes('sensor')) return 'Sensors';
  if (value.includes('power')) return 'Power Components';
  return 'ICs';
};

const packageFor = (comp: BOMComponent) => comp.package ?? 'UNKNOWN';
const lifecycleFor = (comp: BOMComponent) => comp.lifecycle_status && comp.lifecycle_status !== 'INSUFFICIENT_DATA' ? comp.lifecycle_status : 'INSUFFICIENT_DATA';
const secondSourceLabel = (value: boolean | null | undefined) => value === true ? 'Yes' : value === false ? 'No' : 'INSUFFICIENT_DATA';
const criticalityFor = (comp: BOMComponent) => comp.criticality ?? (comp.band === 'CRITICAL' ? 'Critical' : comp.band === 'HIGH' ? 'High' : comp.band === 'MEDIUM' ? 'Medium' : 'Low');

const RiskDetailModal: React.FC<{ component: BOMComponent | null; onClose: () => void }> = ({ component, onClose }) => {
  useEffect(() => {
    if (!component) return;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [component, onClose]);

  if (!component) return null;

  const band = component.band as RiskBand;
  const color = bandHex(band);
  const riskScore = typeof component.score === 'number' ? Math.round(component.score * 100) : null;
  const unitCost = component.price;
  const costData: { strategy: string; cost: number; risk: string; effort: string }[] = [];
  const factorRows = [
    ['Lifecycle Status', lifecycleFor(component)],
    ['Availability', component.stock_level != null ? `${component.stock_level.toLocaleString()} units` : 'INSUFFICIENT_DATA'],
    ['Lead Time', component.lead_time_weeks != null ? `${component.lead_time_weeks} weeks` : 'INSUFFICIENT_DATA'],
    ['Second Source', secondSourceLabel(component.has_second_source)],
    ['Criticality', criticalityFor(component)],
  ];

  return (
    <AnimatePresence>
      <div
        className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-4 py-8 sm:py-12"
        style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}
        onClick={event => { if (event.target === event.currentTarget) onClose(); }}
        role="dialog"
        aria-modal="true"
        aria-label={`${component.pn} BOM risk analysis`}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: -12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: -12 }}
          transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-4xl rounded-2xl overflow-hidden shadow-2xl border"
          style={{ background: 'var(--bg-surface-solid)', borderColor: 'var(--border-strong)', boxShadow: '0 32px 80px -16px rgba(0,0,0,0.6), 0 0 0 1px var(--border-subtle)' }}
        >
          <div className="flex items-start justify-between gap-4 px-5 py-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
            <div>
              <p className="text-sm font-extrabold font-mono text-[var(--text-primary)]">{component.pn}</p>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">{component.category ?? 'Component'} · {packageFor(component)}</p>
              <div className="flex items-center gap-2 mt-2"><RiskBadge band={band} score={riskScore ?? undefined} /><span className="text-xs font-semibold" style={{ color }}>Risk score: {riskScore == null ? 'INSUFFICIENT_DATA' : `${riskScore} / 100`}</span></div>
            </div>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] transition-colors cursor-pointer" aria-label="Close component analysis"><X className="w-4 h-4 text-[var(--text-muted)]" /></button>
          </div>

          <div className="max-h-[calc(100vh-8rem)] overflow-y-auto p-5 space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <section className="glass-card p-4 rounded-2xl space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">Risk Factors</h3>
                {factorRows.map(([label, value]) => <div key={label} className="flex items-center justify-between gap-3 py-2 border-b border-[var(--border-subtle)] last:border-0"><span className="text-xs text-[var(--text-muted)]">{label}</span><span className="text-xs font-semibold text-[var(--text-primary)] text-right">{value}</span></div>)}
                <div className="pt-1"><div className="h-1.5 rounded-full bg-[var(--bg-elevated)] overflow-hidden"><div className="h-full rounded-full" style={{ width: `${riskScore ?? 0}%`, background: color }} /></div></div>
              </section>
              <section className="glass-card p-4 rounded-2xl space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">Cost Impact Comparison</h3>
                {costData.length ? <><div className="h-44"><ResponsiveContainer width="100%" height="100%"><BarChart data={costData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}><XAxis dataKey="strategy" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} /><YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} /><Tooltip formatter={(value: number) => [`₹${value}`, 'Estimated cost']} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 12 }} /><Bar dataKey="cost" radius={[4, 4, 0, 0]}>{costData.map((entry, index) => <Cell key={entry.strategy} fill={index === 0 ? 'var(--risk-critical)' : index === 1 ? 'var(--accent-gold)' : 'var(--risk-low)'} />)}</Bar></BarChart></ResponsiveContainer></div><div className="text-[11px] text-[var(--text-secondary)] grid grid-cols-3 gap-2">{costData.map(item => <div key={item.strategy}><strong className="text-[var(--text-primary)]">{item.strategy}</strong><br />₹{item.cost} · {item.risk}<br />{item.effort} effort</div>)}</div></> : <p className="text-xs text-[var(--text-muted)]">{unitCost == null ? 'INSUFFICIENT_DATA — no verified unit price, LTB, substitute, or redesign cost is available.' : 'INSUFFICIENT_DATA — strategy costs are not derived from a single unit price.'}</p>}
              </section>
            </div>

            <section className="glass-card p-4 rounded-2xl space-y-3">
              <div><h3 className="text-sm font-bold text-[var(--text-primary)]">Recommended Substitutes</h3><p className="text-xs text-[var(--text-muted)] mt-0.5">Recommendations are advisory and require engineering validation before implementation.</p></div>
              <p className="text-xs text-[var(--text-muted)]">No verified substitute recommendations are available for this component yet.</p>
            </section>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

const EmptyBoard: React.FC<{ onClear: () => void }> = ({ onClear }) => (
  <motion.div
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    className="flex flex-col items-center justify-center py-20 gap-5"
  >
    <div className="relative">
      <svg width="120" height="90" viewBox="0 0 96 72" fill="none">
        <rect x="4" y="4" width="88" height="64" rx="6" stroke="var(--border-strong)" strokeWidth="2" strokeDasharray="6 3" />
        <circle cx="16" cy="16" r="4" stroke="var(--border-strong)" strokeWidth="1.5" />
        <circle cx="80" cy="16" r="4" stroke="var(--border-strong)" strokeWidth="1.5" />
        <circle cx="16" cy="56" r="4" stroke="var(--border-strong)" strokeWidth="1.5" />
        <circle cx="80" cy="56" r="4" stroke="var(--border-strong)" strokeWidth="1.5" />
        <motion.polyline
          points="24,52 36,36 48,44 64,28 76,32"
          stroke="var(--accent-amber)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1, ease: 'easeOut', delay: 0.2 }}
        />
        <motion.circle cx="76" cy="32" r="3" fill="var(--accent-amber)"
          initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 1.1 }} />
      </svg>
    </div>
    <div className="text-center space-y-1">
      <p className="text-sm font-semibold text-[var(--text-primary)]">No components match this filter</p>
      <p className="text-xs text-[var(--text-muted)]">Try adjusting your search or clearing the active filters.</p>
    </div>
    <button
      onClick={onClear}
      className="px-4 py-2 rounded-xl text-xs font-bold bg-[var(--accent-gold)] text-white hover:opacity-90 transition-all cursor-pointer shadow-sm"
    >
      Clear all filters
    </button>
  </motion.div>
);

const ComponentCard: React.FC<{
  comp: BOMComponent;
  isOpen: boolean;
  onToggle: () => void;
  onSelect: () => void;
}> = ({ comp, isOpen, onToggle, onSelect }) => {
  const band = comp.band as RiskBand;
  const color = bandHex(band);
  const score = hasNumericScore(comp.score) ? Math.round(comp.score * 100) : undefined;
  const sparkData = buildPerformanceCurve(comp);
  const CatIcon = (comp.category && CATEGORY_ICONS[comp.category]) || Package;

  return (
    <motion.div
      layout
      variants={staggerItem}
      className="rounded-2xl overflow-hidden border card-gradient-border"
      style={{
        borderColor: isOpen ? `color-mix(in oklab, ${color} 50%, transparent)` : 'var(--border-subtle)',
        boxShadow: isOpen
          ? `0 2px 16px -4px color-mix(in oklab, ${color} 35%, transparent), var(--shadow-card)`
          : 'var(--shadow-card)',
        background: 'var(--bg-card)',
      }}
    >
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3.5 cursor-pointer hover:bg-black/[0.015] transition-colors text-left"
        style={{
          background: isOpen
            ? `linear-gradient(90deg, color-mix(in oklab, ${color} 7%, var(--bg-card)) 0%, var(--bg-card) 40%)`
            : undefined,
        }}
      >
        <RiskDot color={color} pulse={band === 'CRITICAL'} />

        <span
          className="hidden md:flex shrink-0 w-9 h-9 rounded-xl items-center justify-center border"
          style={{
            color,
            background: `color-mix(in oklab, ${color} 10%, var(--bg-card))`,
            borderColor: `color-mix(in oklab, ${color} 30%, transparent)`,
          }}
        >
          <CatIcon className="w-4 h-4" />
        </span>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-bold font-mono text-[var(--text-primary)] truncate">{comp.pn}</p>
          <p className="text-[11px] text-[var(--text-muted)] truncate">
            {comp.ref}{comp.category ? ` · ${comp.category}` : ''}
            {comp.lead_time_weeks ? ` · ${comp.lead_time_weeks}wk` : ''}
          </p>
        </div>

        <div className="shrink-0 hidden sm:block">
          <Sparkline data={sparkData} color={color} width={80} height={24} />
        </div>

        <RiskBadge band={band} score={score} />

        <motion.div
          className="shrink-0 text-[var(--text-muted)]"
          animate={{ rotate: isOpen ? 90 : 0 }}
          transition={{ duration: 0.22 }}
        >
          <ChevronRight className="w-4 h-4" />
        </motion.div>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden border-t"
            style={{ borderColor: `color-mix(in oklab, ${color} 20%, transparent)` }}
          >
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.18 }}
              className="px-4 py-4 space-y-3"
            >
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Risk Score', value: hasNumericScore(comp.score) ? `${score}/100` : 'INSUFFICIENT_DATA' },
                  { label: 'Exposure', value: hasNumericScore(comp.exp) ? `${(comp.exp * 100).toFixed(0)}%` : 'INSUFFICIENT_DATA' },
                  { label: 'Confidence', value: comp.band === 'INSUFFICIENT_DATA' || !hasNumericScore(comp.conf) ? 'INSUFFICIENT_DATA' : `${(comp.conf * 100).toFixed(0)}%` },
                ].map(({ label, value }) => (
                  <div key={label} className="text-center p-2 rounded-xl"
                    style={{ background: `color-mix(in oklab, ${color} 6%, var(--bg-elevated))` }}>
                    <p className="text-[10px] text-[var(--text-muted)] font-mono uppercase">{label}</p>
                    <p className="text-base font-extrabold font-mono" style={{ color }}>{value}</p>
                  </div>
                ))}
              </div>

              {comp.reasons.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {comp.reasons.map((r, i) => (
                    <span key={i} className="px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{
                        color,
                        background: `color-mix(in oklab, ${color} 10%, var(--bg-card))`,
                        border: `1px solid color-mix(in oklab, ${color} 30%, transparent)`,
                      }}>
                      {r}
                    </span>
                  ))}
                </div>
              )}

              <button
                onClick={(e) => { e.stopPropagation(); onSelect(); }}
                className="w-full py-2 rounded-xl text-xs font-semibold text-white transition-all hover:brightness-110 active:scale-[0.98]"
                style={{ background: color }}
              >
                View Full Analysis →
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export const ComponentTablePage: React.FC<ComponentTablePageProps> = ({
  components,
  bandFilter,
  onBandFilterChange,
  onSelectComponent,
  onNavigateToUpload,
}) => {
  const [localBands, setLocalBands] = useState<RiskBand[]>([]);
  const [activeCats, setActiveCats] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('table');
  const [openId, setOpenId] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<'score' | 'lead' | 'qty' | 'name' | 'category' | 'lifecycle'>('score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [selectedRiskComponent, setSelectedRiskComponent] = useState<BOMComponent | null>(null);
  // Sync incoming bandFilter from App as a single-band shortcut
  const effectiveSingleBand: RiskBand | null =
    bandFilter && bandFilter !== 'ALL' ? bandFilter as RiskBand : null;

  const allCats = useMemo(
    () => [...new Set(components.map(c => c.category).filter(Boolean))] as string[],
    [components]
  );

  function toggle<T>(arr: T[], v: T, set: (x: T[]) => void) {
    set(arr.includes(v) ? arr.filter(x => x !== v) : [...arr, v]);
  }

  const filtered = useMemo(() => {
    const activeBands = effectiveSingleBand ? [effectiveSingleBand] : localBands;
    const list = components.filter(comp => {
      const band = comp.band as RiskBand;
      const matchBand = activeBands.length === 0 || activeBands.includes(band);
      const matchCat = activeCats.length === 0 || (comp.category && activeCats.includes(comp.category));
      const q = searchQuery.toLowerCase();
      const matchQ = !q ||
        comp.pn.toLowerCase().includes(q) ||
        comp.ref.toLowerCase().includes(q) ||
        comp.reasons.some(r => r.toLowerCase().includes(q));
      return matchBand && matchCat && matchQ;
    });
    const dir = sortDir === 'asc' ? 1 : -1;
    return [...list].sort((a, b) => {
      switch (sortKey) {
        case 'name': return a.pn.localeCompare(b.pn) * dir;
        case 'category': return (a.category ?? '').localeCompare(b.category ?? '') * dir;
        case 'lifecycle': return lifecycleFor(a).localeCompare(lifecycleFor(b)) * dir;
        case 'lead': return ((a.lead_time_weeks ?? 0) - (b.lead_time_weeks ?? 0)) * dir;
        case 'qty': return (a.qty - b.qty) * dir;
        default: return (a.score - b.score) * dir;
      }
    });
  }, [components, localBands, effectiveSingleBand, activeCats, searchQuery, sortKey, sortDir]);

  const clearAll = () => { setLocalBands([]); setActiveCats([]); setSearchQuery(''); onBandFilterChange?.('ALL'); };

  const bandCounts = useMemo(() => ({
    CRITICAL: components.filter(c => c.band === 'CRITICAL').length,
    HIGH: components.filter(c => c.band === 'HIGH').length,
    MEDIUM: components.filter(c => c.band === 'MEDIUM').length,
    LOW: components.filter(c => c.band === 'LOW').length,
  }), [components]);

  const allBands: RiskBand[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
  const bandIcons: Record<RiskBand, React.FC<{ className?: string }>> = {
    CRITICAL: AlertTriangle, HIGH: Flame, MEDIUM: ShieldAlert, LOW: CheckCircle2,
  };

  const riskDistribution = useMemo(() => riskDistributionCategories.map(category => ({
    category,
    count: components.filter(component => distributionCategory(component) === category && component.score >= 0.3).length,
  })), [components]);

  const setTableSort = (nextKey: typeof sortKey) => {
    if (sortKey === nextKey) setSortDir(direction => direction === 'asc' ? 'desc' : 'asc');
    else { setSortKey(nextKey); setSortDir(nextKey === 'name' || nextKey === 'category' || nextKey === 'lifecycle' ? 'asc' : 'desc'); }
  };

  if (components.length === 0) {
    return (
      <div className="space-y-5 pb-12">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-[var(--text-primary)] tracking-tight">Components</h1>
            <p className="text-sm text-[var(--text-muted)] mt-0.5">0 parts loaded</p>
          </div>
        </div>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-12 rounded-2xl text-center space-y-5"
        >
          <div className="w-16 h-16 rounded-2xl mx-auto flex items-center justify-center text-3xl"
            style={{ background: 'color-mix(in oklab, var(--accent-gold) 15%, var(--bg-elevated))' }}>
            📋
          </div>
          <h3 className="text-base font-bold text-[var(--text-primary)]">No components loaded</h3>
          <p className="text-sm text-[var(--text-muted)] max-w-xs mx-auto">
            Upload a BOM CSV to analyze supply-chain risk across your parts list.
          </p>
          {onNavigateToUpload && (
            <button
              onClick={onNavigateToUpload}
              className="px-5 py-2.5 rounded-xl text-sm font-bold text-white hover:opacity-90 transition-all cursor-pointer shadow-sm"
              style={{ background: 'var(--accent-gold)' }}
            >
              Upload BOM →
            </button>
          )}
        </motion.div>
      </div>
    );
  }

  return (
    <div className="space-y-5 pb-12">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-[var(--text-primary)] tracking-tight">Components</h1>
          <p className="text-sm text-[var(--text-muted)] mt-0.5">{components.length} parts · {filtered.length} shown</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="bg-[var(--bg-elevated)] p-1 rounded-xl flex items-center border border-[var(--border-subtle)]">
            {(['cards','table'] as const).map(mode => (
              <button key={mode} onClick={() => setViewMode(mode)}
                className={`p-1.5 rounded-lg transition-colors cursor-pointer ${viewMode === mode ? 'bg-[var(--bg-surface-solid)] text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-muted)]'}`}
              >
                {mode === 'cards' ? <Grid className="w-4 h-4" /> : <TableIcon className="w-4 h-4" />}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats bar — real counts consistent with dashboard */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <StatsStat label="Total Parts" value={components.length} icon={<Boxes className="w-4 h-4" />} color="var(--accent-blue)" />
        <StatsStat label="Critical" value={bandCounts.CRITICAL} icon={<AlertTriangle className="w-4 h-4" />} color={bandHex('CRITICAL')} />
        <StatsStat label="At Risk" value={bandCounts.HIGH} icon={<Flame className="w-4 h-4" />} color={bandHex('HIGH')} />
        <StatsStat label="Medium" value={bandCounts.MEDIUM} icon={<ShieldAlert className="w-4 h-4" />} color={bandHex('MEDIUM')} />
        <StatsStat label="Healthy" value={bandCounts.LOW} icon={<CheckCircle2 className="w-4 h-4" />} color={bandHex('LOW')} />
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
        <input
          type="text"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder="Filter by MPN, designator, or risk reason…"
          className="w-full pl-9 pr-4 py-2.5 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-xl text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-gold)] transition-colors"
        />
      </div>

      {/* Filter chips — consistent band colors */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1 text-xs text-[var(--text-muted)] font-medium">
          <Filter className="w-3.5 h-3.5" /> Risk:
        </span>
        {allBands.map(band => {
          const color = bandHex(band);
          const active = effectiveSingleBand === band || localBands.includes(band);
          const count = bandCounts[band];
          const BIcon = bandIcons[band];
          return (
            <button
              key={band}
              onClick={() => {
                if (effectiveSingleBand) {
                  onBandFilterChange?.('ALL');
                } else {
                  toggle(localBands, band, setLocalBands);
                }
              }}
              className="px-3 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 cursor-pointer transition-all border"
              style={{
                color: active ? color : 'var(--text-secondary)',
                background: active ? `color-mix(in oklab, ${color} 14%, var(--bg-card))` : 'var(--bg-surface)',
                borderColor: active ? `color-mix(in oklab, ${color} 50%, transparent)` : 'var(--border-subtle)',
                boxShadow: active ? `0 0 0 1px ${color}33` : 'none',
              }}
            >
              <BIcon className="w-3 h-3" />
              {bandLabel[band]}
              <span className="text-[10px] bg-black/10 px-1.5 py-0.5 rounded-full">{count}</span>
            </button>
          );
        })}

        {allCats.length > 0 && (
          <>
            <span className="text-[var(--border-strong)] mx-1">|</span>
            <span className="text-xs text-[var(--text-muted)] font-medium">Cat:</span>
            {allCats.map(cat => {
              const active = activeCats.includes(cat);
              return (
                <button key={cat}
                  onClick={() => toggle(activeCats, cat, setActiveCats)}
                  className="px-3 py-1.5 rounded-xl text-xs font-medium flex items-center gap-1 cursor-pointer transition-all border"
                  style={{
                    color: active ? 'var(--accent-gold)' : 'var(--text-secondary)',
                    background: active ? 'color-mix(in oklab, var(--accent-gold) 12%, var(--bg-card))' : 'var(--bg-surface)',
                    borderColor: active ? 'color-mix(in oklab, var(--accent-gold) 40%, transparent)' : 'var(--border-subtle)',
                  }}
                >
                  {cat}
                </button>
              );
            })}
          </>
        )}

        {(localBands.length > 0 || activeCats.length > 0 || searchQuery || effectiveSingleBand) && (
          <button onClick={clearAll} className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] underline cursor-pointer transition-colors ml-1">
            Clear all
          </button>
        )}

        <div className="ml-auto flex items-center gap-2">
          <select
            value={sortKey}
            onChange={e => setSortKey(e.target.value as typeof sortKey)}
            className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-[var(--bg-surface)] text-[var(--text-secondary)] border border-[var(--border-subtle)] outline-none focus:border-[var(--accent-gold)] transition-colors cursor-pointer"
          >
            <option value="score">Sort: Risk Score</option>
            <option value="lead">Sort: Lead Time</option>
            <option value="qty">Sort: Quantity</option>
            <option value="name">Sort: Name</option>
            <option value="category">Sort: Category</option>
            <option value="lifecycle">Sort: Lifecycle</option>
          </select>
          <button
            onClick={() => setSortDir(d => d === 'asc' ? 'desc' : 'asc')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-[var(--bg-surface)] text-[var(--text-secondary)] border border-[var(--border-subtle)] hover:border-[var(--border-strong)] transition-all cursor-pointer"
          >
            <ArrowUpDown className="w-3.5 h-3.5" />
            {sortDir === 'asc' ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
          </button>
        </div>
      </div>

      <div className="glass-card p-4 sm:p-5 rounded-2xl">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <h2 className="text-sm font-bold text-[var(--text-primary)]">Risk Distribution by Component Category</h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">Components with medium or higher BOM risk.</p>
          </div>
        </div>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={riskDistribution} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
              <XAxis dataKey="category" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} interval={0} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <Tooltip cursor={{ fill: 'color-mix(in oklab, var(--accent-gold) 7%, transparent)' }} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 12 }} formatter={(value: number) => [value, 'Risky components']} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]} fill="var(--accent-gold)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Cards view */}
      {viewMode === 'cards' && (
        filtered.length === 0 ? <EmptyBoard onClear={clearAll} /> : (
          <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-2">
            {filtered.map(comp => (
              <ComponentCard
                key={`${comp.pn}-${comp.ref}`}
                comp={comp}
                isOpen={openId === comp.pn}
                onToggle={() => setOpenId(openId === comp.pn ? null : comp.pn)}
                onSelect={() => onSelectComponent(comp)}
              />
            ))}
          </motion.div>
        )
      )}

      {viewMode === 'cards' && (
        filtered.length === 0 ? <EmptyBoard onClear={clearAll} /> : (
          <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-2">
            {filtered.map(comp => (
              <ComponentCard
                key={`${comp.pn}-${comp.ref}`}
                comp={comp}
                isOpen={openId === comp.pn}
                onToggle={() => setOpenId(openId === comp.pn ? null : comp.pn)}
                onSelect={() => onSelectComponent(comp)}
              />
            ))}
          </motion.div>
        )
      )}

      {/* Table view */}
      {viewMode === 'table' && (
        filtered.length === 0 ? <EmptyBoard onClear={clearAll} /> : (
          <div className="glass-card rounded-2xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[var(--bg-elevated)] text-[var(--text-muted)] font-mono uppercase text-[10px] sticky top-0 z-10">
                  <tr>
                    <th className="p-3 pl-4"><button onClick={() => setTableSort('name')} className="cursor-pointer hover:text-[var(--text-primary)]">Component {sortKey === 'name' && (sortDir === 'asc' ? '↑' : '↓')}</button></th>
                    <th className="p-3"><button onClick={() => setTableSort('category')} className="cursor-pointer hover:text-[var(--text-primary)]">Category {sortKey === 'category' && (sortDir === 'asc' ? '↑' : '↓')}</button></th>
                    <th className="p-3">Package</th>
                    <th className="p-3">Criticality</th>
                    <th className="p-3"><button onClick={() => setTableSort('score')} className="cursor-pointer hover:text-[var(--text-primary)]">Risk Score {sortKey === 'score' && (sortDir === 'asc' ? '↑' : '↓')}</button></th>
                    <th className="p-3"><button onClick={() => setTableSort('lifecycle')} className="cursor-pointer hover:text-[var(--text-primary)]">Lifecycle {sortKey === 'lifecycle' && (sortDir === 'asc' ? '↑' : '↓')}</button></th>
                    <th className="p-3"><button onClick={() => setTableSort('lead')} className="cursor-pointer hover:text-[var(--text-primary)]">Lead Time {sortKey === 'lead' && (sortDir === 'asc' ? '↑' : '↓')}</button></th>
                    <th className="p-3">Second Source</th>
                    <th className="p-3 text-right pr-4">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {filtered.map(comp => {
                    const band = comp.band as RiskBand;
                    const color = bandHex(band);
                    return (
                      <tr
                        key={`${comp.pn}-${comp.ref}`}
                        onClick={() => setSelectedRiskComponent(comp)}
                        className="cursor-pointer transition-colors hover:bg-black/[0.025]"
                        style={{ background: `color-mix(in oklab, ${color} 4%, var(--bg-card))` }}
                      >
                        <td className="p-3 pl-4"><p className="font-mono font-bold text-[var(--text-primary)]">{comp.pn}</p><p className="font-mono text-[10px] text-[var(--text-muted)]">{comp.ref}</p></td>
                        <td className="p-3 text-[var(--text-secondary)]">{comp.category ?? '—'}</td>
                        <td className="p-3 font-mono text-[var(--text-secondary)]">{packageFor(comp)}</td>
                        <td className="p-3"><RiskBadge band={band} /></td>
                        <td className="p-3"><span className="font-mono font-bold" style={{ color }}>{scoreDisplay(comp.score, band)}</span>{typeof comp.score === 'number' && <div className="mt-1 h-1 rounded-full bg-[var(--bg-elevated)] overflow-hidden w-14"><div className="h-full rounded-full" style={{ width: `${Math.round(comp.score * 100)}%`, background: color }} /></div>}</td>
                        <td className="p-3 font-mono text-[var(--text-secondary)]">{lifecycleFor(comp)}</td>
                        <td className="p-3 font-mono text-[var(--text-secondary)]">{comp.lead_time_weeks != null ? `${comp.lead_time_weeks} weeks` : 'INSUFFICIENT_DATA'}</td>
                        <td className="p-3 text-[var(--text-secondary)]">{secondSourceLabel(comp.has_second_source)}</td>
                        <td className="p-3 text-right pr-4 font-semibold" style={{ color }}>View →</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )
      )}

      <RiskDetailModal component={selectedRiskComponent} onClose={() => setSelectedRiskComponent(null)} />
    </div>
  );
};
