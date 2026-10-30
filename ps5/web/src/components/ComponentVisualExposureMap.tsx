import React, { useState, useMemo } from 'react';
import type { BOMComponent } from '../types';
import type { RiskBand } from '../components/primitives';
import { bandHex, hasNumericScore } from '../utils/riskUtils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Layers, Cpu, Power, Radar, Waves, Boxes,
  LayoutGrid, CircleDot, BarChart3, ChevronRight, AlertTriangle
} from 'lucide-react';

interface ComponentVisualExposureMapProps {
  parts: BOMComponent[];
  onSelectComponent: (comp: BOMComponent) => void;
}

type ViewMode = 'TREEMAP' | 'BUBBLES' | 'PARETO';
type CategoryFilter = 'ALL' | 'ACTIVE_RISK' | 'ICS' | 'PASSIVES';

const formatRefDes = (refStr?: string) => {
  if (!refStr) return '—';
  const tokens = refStr.split(',').map(s => s.trim()).filter(Boolean);
  if (tokens.length <= 1) return tokens[0] || '—';
  return `${tokens[0]} (+${tokens.length - 1})`;
};

const formatBubbleScore = (score: unknown, band?: string | null) => {
  if (String(band || '').toUpperCase() === 'INSUFFICIENT_DATA' || !hasNumericScore(score)) {
    return '—';
  }
  const val = Math.round((score as number) > 1 ? (score as number) : (score as number) * 100);
  return `${val}`;
};

export const ComponentVisualExposureMap: React.FC<ComponentVisualExposureMapProps> = ({
  parts,
  onSelectComponent,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('TREEMAP');
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('ALL');
  const [hoveredComp, setHoveredComp] = useState<BOMComponent | null>(null);

  // Group components by major engineering categories
  const categoryGroups = useMemo(() => {
    const groups: Record<string, { label: string; icon: React.FC<{ className?: string }>; parts: BOMComponent[] }> = {
      compute: { label: 'Microcontroller & Compute', icon: Cpu, parts: [] },
      power: { label: 'Power Management & PMIC', icon: Power, parts: [] },
      interface: { label: 'Interface, Logic & Bus', icon: Waves, parts: [] },
      sensor: { label: 'Sensors & Signal', icon: Radar, parts: [] },
      passive: { label: 'Passives & Protection', icon: Layers, parts: [] },
      other: { label: 'Electromechanical & Hardware', icon: Boxes, parts: [] },
    };

    parts.forEach(comp => {
      const cat = (comp.category || '').toLowerCase();
      const pn = (comp.pn || '').toUpperCase();
      const ref = (comp.ref || '').toUpperCase();

      if (cat.includes('mcu') || cat.includes('micro') || cat.includes('memory') || pn.includes('AM335') || pn.includes('STM32') || pn.includes('ESP32') || pn.includes('MT41') || pn.includes('THGB')) {
        groups.compute.parts.push(comp);
      } else if (cat.includes('power') || cat.includes('regulator') || pn.includes('TPS') || pn.includes('TLV') || pn.includes('LM317') || pn.includes('CSD') || ref.startsWith('U2') || ref.startsWith('VR')) {
        groups.power.parts.push(comp);
      } else if (cat.includes('interface') || cat.includes('logic') || pn.includes('LAN') || pn.includes('TDA') || pn.includes('SN74') || pn.includes('MCP2551') || pn.includes('USB') || ref.startsWith('J')) {
        groups.interface.parts.push(comp);
      } else if (cat.includes('sensor') || pn.includes('BME') || pn.includes('MPU') || pn.includes('INA')) {
        groups.sensor.parts.push(comp);
      } else if (cat.includes('passive') || pn.includes('RC') || pn.includes('CC') || pn.includes('CL') || pn.includes('CRCW') || pn.includes('GRM') || ref.startsWith('R') || ref.startsWith('C') || ref.startsWith('L')) {
        groups.passive.parts.push(comp);
      } else {
        groups.other.parts.push(comp);
      }
    });

    return Object.entries(groups).filter(([_, g]) => g.parts.length > 0);
  }, [parts]);

  // Filtered parts for Bubbles view
  const filteredBubbles = useMemo(() => {
    switch (categoryFilter) {
      case 'ACTIVE_RISK':
        return parts.filter(p => p.band === 'CRITICAL' || p.band === 'HIGH');
      case 'ICS':
        return parts.filter(p => {
          const cat = (p.category || '').toLowerCase();
          const ref = (p.ref || '').toUpperCase();
          return cat.includes('mcu') || cat.includes('power') || cat.includes('interface') || cat.includes('sensor') || ref.startsWith('U');
        });
      case 'PASSIVES':
        return parts.filter(p => {
          const ref = (p.ref || '').toUpperCase();
          return ref.startsWith('R') || ref.startsWith('C') || ref.startsWith('L') || ref.startsWith('FB');
        });
      default:
        return parts;
    }
  }, [parts, categoryFilter]);

  // Top Pareto risk components
  const paretoParts = useMemo(() => {
    return [...parts]
      .filter(p => hasNumericScore(p.score))
      .sort((a, b) => ((b.score ?? 0) * (b.qty || 1)) - ((a.score ?? 0) * (a.qty || 1)))
      .slice(0, 12);
  }, [parts]);

  return (
    <div className="glass-card p-6 rounded-2xl relative overflow-hidden space-y-5">
      {/* ── Section Header with View Mode Toggles */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-[var(--accent-gold)] uppercase tracking-wider">
              Visual Exposure Map & Infographic
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-[var(--border-subtle)] text-[var(--text-muted)] bg-[var(--bg-elevated)]">
              {parts.length} components
            </span>
          </div>
          <h3 className="text-base font-bold text-[var(--text-primary)] mt-0.5">
            BOM Component Risk Topology
          </h3>
        </div>

        {/* View Mode Switcher */}
        <div className="flex items-center p-1 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] gap-1">
          <button
            type="button"
            onClick={() => setViewMode('TREEMAP')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              viewMode === 'TREEMAP'
                ? 'bg-[var(--accent-gold)] text-white shadow-sm'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            <LayoutGrid className="w-3.5 h-3.5" /> Category Treemap
          </button>
          <button
            type="button"
            onClick={() => setViewMode('BUBBLES')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              viewMode === 'BUBBLES'
                ? 'bg-[var(--accent-gold)] text-white shadow-sm'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            <CircleDot className="w-3.5 h-3.5" /> Risk Bubbles
          </button>
          <button
            type="button"
            onClick={() => setViewMode('PARETO')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              viewMode === 'PARETO'
                ? 'bg-[var(--accent-gold)] text-white shadow-sm'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" /> Risk Pareto
          </button>
        </div>
      </div>

      {/* ── VIEW 1: CATEGORY TREEMAP INFOGRAPHIC ── */}
      {viewMode === 'TREEMAP' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {categoryGroups.map(([key, group]) => {
              const Icon = group.icon;
              const critCount = group.parts.filter(p => p.band === 'CRITICAL').length;
              const highCount = group.parts.filter(p => p.band === 'HIGH').length;
              const hasRisk = critCount > 0 || highCount > 0;

              return (
                <div
                  key={key}
                  className="p-4 rounded-xl border bg-[var(--bg-elevated)]/70 border-[var(--border-subtle)] space-y-3 relative overflow-hidden"
                >
                  <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="w-7 h-7 rounded-lg flex items-center justify-center bg-[var(--bg-card)] text-[var(--accent-gold)]">
                        <Icon className="w-4 h-4" />
                      </span>
                      <div>
                        <h4 className="text-xs font-bold text-[var(--text-primary)]">{group.label}</h4>
                        <span className="text-[10px] font-mono text-[var(--text-muted)]">
                          {group.parts.length} line items
                        </span>
                      </div>
                    </div>
                    {hasRisk ? (
                      <span className="px-2 py-0.5 rounded-full text-[9px] font-extrabold border bg-rose-500/10 text-rose-400 border-rose-500/30 flex items-center gap-1">
                        <AlertTriangle className="w-2.5 h-2.5" />
                        {critCount + highCount} At Risk
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full text-[9px] font-extrabold border bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
                        Nominal
                      </span>
                    )}
                  </div>

                  {/* Component Tiles */}
                  <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto pr-1">
                    {group.parts.map((comp, idx) => {
                      const tone = bandHex(comp.band as RiskBand);
                      const isAtRisk = comp.band === 'CRITICAL' || comp.band === 'HIGH';

                      return (
                        <button
                          key={comp.pn + idx}
                          type="button"
                          onClick={() => onSelectComponent(comp)}
                          onMouseEnter={() => setHoveredComp(comp)}
                          onMouseLeave={() => setHoveredComp(null)}
                          className={`px-2.5 py-1.5 rounded-lg border text-left transition-all cursor-pointer flex items-center justify-between gap-2 ${
                            isAtRisk
                              ? 'bg-[var(--bg-card)] border-rose-500/40 shadow-sm hover:border-rose-400'
                              : 'bg-[var(--bg-card)]/60 border-[var(--border-subtle)] hover:border-[var(--border-strong)]'
                          }`}
                          style={{ minWidth: '120px', flex: '1 1 calc(50% - 6px)' }}
                        >
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: tone }} />
                              <span className="text-[11px] font-mono font-bold text-[var(--text-primary)] truncate max-w-[90px]">
                                {comp.pn}
                              </span>
                            </div>
                            <div className="text-[9px] font-mono text-[var(--text-muted)] pl-3.5">
                              {formatRefDes(comp.ref)}
                            </div>
                          </div>
                          <div className="text-right flex-shrink-0">
                            <span className="text-[10px] font-mono font-extrabold" style={{ color: tone }}>
                              {formatBubbleScore(comp.score, comp.band)}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── VIEW 2: RISK BUBBLES WITH FILTERS & CLEAN OVERFLOW ── */}
      {viewMode === 'BUBBLES' && (
        <div className="space-y-4">
          {/* Category Filter Chips */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-mono uppercase text-[var(--text-muted)] mr-1">Filter:</span>
            {[
              { id: 'ALL' as CategoryFilter, label: `All (${parts.length})` },
              { id: 'ACTIVE_RISK' as CategoryFilter, label: `At Risk (${parts.filter(p => p.band === 'CRITICAL' || p.band === 'HIGH').length})` },
              { id: 'ICS' as CategoryFilter, label: 'ICs & Active' },
              { id: 'PASSIVES' as CategoryFilter, label: 'Passives & Hardware' },
            ].map(f => (
              <button
                key={f.id}
                type="button"
                onClick={() => setCategoryFilter(f.id)}
                className={`px-3 py-1 rounded-full text-xs font-semibold border transition-all cursor-pointer ${
                  categoryFilter === f.id
                    ? 'bg-[var(--accent-gold)] text-white border-[var(--accent-gold)]'
                    : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[var(--border-subtle)] hover:border-[var(--border-strong)]'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Bubbles Area */}
          <div className="min-h-64 w-full relative flex flex-wrap items-center justify-center gap-4 p-5 bg-[var(--bg-elevated)]/40 rounded-xl border border-[var(--border-subtle)] max-h-96 overflow-y-auto">
            <AnimatePresence>
              {filteredBubbles.map((comp, idx) => {
                const band = comp.band as RiskBand;
                const tone = bandHex(band);
                const isCritOrHigh = band === 'CRITICAL' || band === 'HIGH';
                const SIZE = isCritOrHigh ? 88 : 72;

                return (
                  <motion.button
                    key={comp.pn + idx}
                    type="button"
                    onClick={() => onSelectComponent(comp)}
                    onMouseEnter={() => setHoveredComp(comp)}
                    onMouseLeave={() => setHoveredComp(null)}
                    whileHover={{ scale: 1.15, zIndex: 30 }}
                    className="rounded-full flex flex-col items-center justify-center text-center cursor-pointer border-2 relative flex-shrink-0 overflow-hidden transition-all shadow-md"
                    style={{
                      width: SIZE,
                      height: SIZE,
                      backgroundColor: `color-mix(in oklab, ${tone} 16%, var(--bg-card))`,
                      borderColor: `color-mix(in oklab, ${tone} ${isCritOrHigh ? '80%' : '45%'}, transparent)`,
                      boxShadow: isCritOrHigh
                        ? `0 4px 20px -2px color-mix(in oklab, ${tone} 50%, transparent)`
                        : `0 2px 10px -2px color-mix(in oklab, ${tone} 25%, transparent)`,
                    }}
                  >
                    <div className="w-2 h-2 rounded-full mb-0.5" style={{ backgroundColor: tone }} />
                    <span className="font-mono font-bold text-[10px] text-[var(--text-primary)] leading-none max-w-[62px] truncate px-1">
                      {comp.pn}
                    </span>
                    <span className="text-[8px] text-[var(--text-muted)] font-mono max-w-[58px] truncate leading-tight mt-0.5">
                      {formatRefDes(comp.ref)}
                    </span>
                    <span className="text-[9px] font-mono font-extrabold mt-0.5" style={{ color: tone }}>
                      {formatBubbleScore(comp.score, comp.band)}
                    </span>
                  </motion.button>
                );
              })}
            </AnimatePresence>
          </div>
        </div>
      )}

      {/* ── VIEW 3: PARETO RISK DISRUPTION RANKING ── */}
      {viewMode === 'PARETO' && (
        <div className="space-y-3">
          <div className="text-xs text-[var(--text-muted)] flex items-center justify-between">
            <span>Ranked by Composite Risk Score × Assembly Quantity</span>
            <span className="font-mono text-[10px]">Top Risk Drivers</span>
          </div>
          <div className="border border-[var(--border-subtle)] rounded-xl overflow-hidden divide-y divide-[var(--border-subtle)] bg-[var(--bg-elevated)]/30">
            {paretoParts.map((comp, idx) => {
              const tone = bandHex(comp.band as RiskBand);
              const scoreVal = comp.score != null ? Math.round((comp.score > 1 ? comp.score : comp.score * 100)) : 0;

              return (
                <div
                  key={comp.pn + idx}
                  onClick={() => onSelectComponent(comp)}
                  className="p-3 flex items-center justify-between gap-3 hover:bg-[var(--bg-elevated)] transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="w-5 h-5 rounded-md bg-[var(--bg-card)] flex items-center justify-center text-[10px] font-mono font-bold text-[var(--text-muted)]">
                      #{idx + 1}
                    </span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold font-mono text-[var(--text-primary)] truncate">
                          {comp.pn}
                        </span>
                        <span className="text-[10px] font-mono text-[var(--text-muted)]">
                          {formatRefDes(comp.ref)}
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--text-muted)] truncate max-w-md">
                        {comp.reasons[0] || comp.description || 'Standard verified specification'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 flex-shrink-0">
                    {/* Visual Progress Bar */}
                    <div className="w-24 sm:w-36 h-2 bg-[var(--bg-card)] rounded-full overflow-hidden border border-[var(--border-subtle)]">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${scoreVal}%`, backgroundColor: tone }}
                      />
                    </div>
                    <div className="text-right w-12">
                      <span className="text-xs font-mono font-black" style={{ color: tone }}>
                        {scoreVal}
                      </span>
                    </div>
                    <ChevronRight className="w-4 h-4 text-[var(--text-muted)]" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Hover Tooltip Card (Shows rich part identity without clutter) */}
      {hoveredComp && (
        <div
          className="p-3 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-surface-solid)] shadow-2xl absolute bottom-4 left-6 z-40 text-xs space-y-1.5 pointer-events-none transition-all"
          style={{ maxWidth: '320px', backdropFilter: 'blur(16px)' }}
        >
          <div className="flex items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-1.5">
            <span className="font-mono font-bold text-[var(--text-primary)]">{hoveredComp.pn}</span>
            <span
              className="px-1.5 py-0.5 rounded text-[9px] font-extrabold border"
              style={{
                color: bandHex(hoveredComp.band as RiskBand),
                borderColor: bandHex(hoveredComp.band as RiskBand),
              }}
            >
              {hoveredComp.band}
            </span>
          </div>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            Designators: {hoveredComp.ref}
          </p>
          <div className="grid grid-cols-2 gap-2 text-[10px] font-mono pt-1">
            <div>
              <span className="text-[var(--text-muted)]">Qty:</span> {hoveredComp.qty}
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Lifecycle:</span> {hoveredComp.lifecycle_status || 'UNKNOWN'}
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Stock:</span> {hoveredComp.stock_level != null ? hoveredComp.stock_level.toLocaleString() : 'N/A'}
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Lead:</span> {hoveredComp.lead_time_weeks != null ? `${hoveredComp.lead_time_weeks} wks` : 'N/A'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
