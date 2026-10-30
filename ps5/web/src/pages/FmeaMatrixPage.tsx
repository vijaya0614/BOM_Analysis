import React, { useEffect, useMemo, useState } from 'react';
import type { BOMComponent } from '../types';
import { SENTINEL_API_BASE } from '../api';
import { ShieldAlert, Filter, Search, Printer, RefreshCw } from 'lucide-react';

interface FmeaMatrixEntry {
  id: string;
  part_number: string;
  reference_designator: string;
  quantity?: number | null;
  subsystem: string;
  failure_mode: string;
  potential_cause: string;
  end_system_effect: string;
  severity: number;
  occurrence: number;
  detection: number;
  rpn: number;
  action_priority: 'HIGH' | 'MEDIUM' | 'LOW';
  recommended_action: string;
  residual_rpn: number;
}

interface Props {
  components: BOMComponent[];
  bomName?: string;
  onSelectComponent: (comp: BOMComponent) => void;
}

export const FmeaMatrixPage: React.FC<Props> = ({ components, bomName = 'Active BOM', onSelectComponent }) => {
  const [entries, setEntries] = useState<FmeaMatrixEntry[]>([]);
  const [unresolvedParts, setUnresolvedParts] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [subsystemFilter, setSubsystemFilter] = useState('ALL');
  const [priorityFilter, setPriorityFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const requestBody = useMemo(() => ({
    bom_name: bomName,
    components: components.map((component) => ({
      part_number: component.pn,
      reference_designator: component.ref,
      quantity: component.qty,
      category: component.category,
      component_name: component.description || component.pn,
    })),
  }), [bomName, components]);

  useEffect(() => {
    let cancelled = false;
    if (requestBody.components.length === 0) {
      setEntries([]);
      setUnresolvedParts(0);
      setLoadError(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError(null);
    fetch(`${SENTINEL_API_BASE}/api/fmea/bom`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody),
    })
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || result.detail || 'FMEA analysis failed.');
        return result;
      })
      .then((result) => {
        if (!cancelled) {
          setEntries(Array.isArray(result.fmea_entries) ? result.fmea_entries : []);
          setUnresolvedParts(Number(result.unresolved_component_count) || 0);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setEntries([]);
          setUnresolvedParts(0);
          setLoadError(error instanceof Error ? error.message : 'Could not load FMEA for this BOM.');
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [requestBody]);

  const subsystems = useMemo(() => ['ALL', ...new Set(entries.map((entry) => entry.subsystem || 'Unclassified'))], [entries]);
  const filteredData = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    return entries.filter((item) => {
      const matchSubsystem = subsystemFilter === 'ALL' || item.subsystem === subsystemFilter;
      const matchPriority = priorityFilter === 'ALL' || item.action_priority === priorityFilter;
      const matchQuery = !q || [item.part_number, item.failure_mode, item.potential_cause, item.subsystem]
        .some((value) => value.toLowerCase().includes(q));
      return matchSubsystem && matchPriority && matchQuery;
    });
  }, [entries, subsystemFilter, priorityFilter, searchQuery]);

  const highPriorityCount = entries.filter((entry) => entry.action_priority === 'HIGH').length;
  const maxEntry = entries.reduce<FmeaMatrixEntry | null>((best, item) => !best || item.rpn > best.rpn ? item : best, null);
  const totalRpn = entries.reduce((sum, item) => sum + item.rpn, 0);
  const residualRpn = entries.reduce((sum, item) => sum + item.residual_rpn, 0);
  const residualReduction = totalRpn > 0 ? Math.round((1 - residualRpn / totalRpn) * 100) : 0;

  const handleRowClick = (mpn: string) => {
    const match = components.find((component) => component.pn === mpn);
    if (match) onSelectComponent(match);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-8 h-8 rounded-lg flex items-center justify-center bg-rose-500/15 text-rose-400"><ShieldAlert className="w-4 h-4" /></span>
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-rose-400 font-semibold">Reliability Engineering (Part 11)</span>
              <h2 className="text-xl font-extrabold text-[var(--text-primary)]">Failure Mode and Effects Analysis (FMEA) Matrix</h2>
            </div>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">{bomName}: suggested failure modes for its loaded BOM components. Select a row to open that component.</p>
        </div>
        <button type="button" onClick={() => window.print()} className="px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:border-[var(--border-strong)] transition-all cursor-pointer">
          <Printer className="w-3.5 h-3.5" /> Print Audit Matrix
        </button>
      </div>

      <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-[11px] text-[var(--text-secondary)]">
        FMEA rows are category-based engineering suggestions tied to this BOM’s part numbers. Severity, occurrence, detection, and residual scores are heuristic estimates, not measured field-failure data; engineering review is required.
      </div>

      {loadError && <div role="alert" className="rounded-xl border border-rose-500/30 bg-rose-500/5 px-4 py-3 text-xs text-rose-300">Could not generate this BOM’s FMEA: {loadError}</div>}
      {!loading && unresolvedParts > 0 && <div className="rounded-xl border border-slate-500/30 bg-slate-500/5 px-4 py-3 text-xs text-[var(--text-secondary)]">{unresolvedParts} unresolved or placeholder part number{unresolvedParts === 1 ? '' : 's'} skipped. Resolve the MPN before assigning component-specific failure modes.</div>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-4 rounded-2xl glass-card border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">BOM Failure Modes</span>
          <p className="text-2xl font-black font-mono text-[var(--text-primary)]">{loading ? '…' : entries.length}</p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">Across {loading ? '…' : new Set(entries.map((entry) => entry.part_number)).size} BOM parts</p>
        </div>
        <div className="p-4 rounded-2xl glass-card border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">High Suggested Priority</span>
          <p className="text-2xl font-black font-mono text-rose-400">{loading ? '…' : highPriorityCount}</p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">Review priority; not a release decision</p>
        </div>
        <div className="p-4 rounded-2xl glass-card border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Peak Suggested RPN</span>
          <p className="text-2xl font-black font-mono text-amber-400">{loading ? '…' : maxEntry?.rpn ?? '—'}</p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono truncate">{maxEntry ? `${maxEntry.part_number}: ${maxEntry.failure_mode}` : 'No generated modes'}</p>
        </div>
        <div className="p-4 rounded-2xl glass-card border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Modelled Residual RPN Reduction</span>
          <p className="text-2xl font-black font-mono text-emerald-400">{loading ? '…' : `+${residualReduction}%`}</p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">Based on template mitigations</p>
        </div>
      </div>

      <div className="glass-card p-4 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-mono text-[var(--text-muted)] flex items-center gap-1"><Filter className="w-3.5 h-3.5" /> Category:</span>
          {subsystems.map((subsystem) => <button key={subsystem} type="button" onClick={() => setSubsystemFilter(subsystem)} className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${subsystemFilter === subsystem ? 'bg-[var(--accent-gold)] text-white border-[var(--accent-gold)]' : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[var(--border-subtle)] hover:border-[var(--border-strong)]'}`}>
            {subsystem === 'ALL' ? 'All Categories' : subsystem}
          </button>)}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-[var(--bg-elevated)] p-1 rounded-xl border border-[var(--border-subtle)]">
            {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((priority) => <button key={priority} type="button" onClick={() => setPriorityFilter(priority)} className={`px-2 py-0.5 rounded-lg text-[10px] font-extrabold transition-all cursor-pointer ${priorityFilter === priority ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'}`}>{priority}</button>)}
          </div>
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-[var(--text-muted)]" />
            <input type="text" placeholder="Search this BOM…" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} className="pl-8 pr-3 py-1.5 rounded-xl text-xs bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-gold)] w-44" />
          </div>
        </div>
      </div>

      <div className="glass-card rounded-2xl overflow-hidden border border-[var(--border-subtle)]">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--bg-elevated)] text-[var(--text-muted)] text-[10px] font-mono uppercase border-b border-[var(--border-subtle)]">
              <tr><th className="py-3 px-4">BOM Component & Category</th><th className="py-3 px-4">Suggested Failure Mode</th><th className="py-3 px-4">Potential Cause</th><th className="py-3 px-4">End-System Effect</th><th className="py-3 px-2 text-center" title="Severity (1-10)">S</th><th className="py-3 px-2 text-center" title="Occurrence (1-10)">O</th><th className="py-3 px-2 text-center" title="Detection (1-10)">D</th><th className="py-3 px-3 text-center font-bold">RPN</th><th className="py-3 px-3 text-center">Suggested Priority</th><th className="py-3 px-4">Suggested Control</th><th className="py-3 px-3 text-center text-emerald-400 font-bold" title="Residual RPN from template assumptions">Res RPN</th></tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {filteredData.map((row) => {
                const isHigh = row.action_priority === 'HIGH';
                const isMedium = row.action_priority === 'MEDIUM';
                return <tr key={row.id} onClick={() => handleRowClick(row.part_number)} className="hover:bg-[var(--bg-elevated)]/50 transition-colors cursor-pointer">
                  <td className="py-3 px-4"><div className="font-mono font-bold text-[var(--text-primary)]">{row.part_number}</div><div className="text-[10px] font-mono text-[var(--text-muted)]">{row.reference_designator || '—'} · {row.subsystem || 'Unclassified'}{row.quantity ? ` · qty ${row.quantity}` : ''}</div></td>
                  <td className="py-3 px-4 font-semibold text-[var(--text-primary)] max-w-xs">{row.failure_mode}</td>
                  <td className="py-3 px-4 text-[var(--text-secondary)] text-[11px] max-w-sm">{row.potential_cause}</td>
                  <td className="py-3 px-4 text-[var(--text-muted)] text-[11px] max-w-xs">{row.end_system_effect}</td>
                  <td className="py-3 px-2 text-center font-mono font-bold text-rose-400">{row.severity}</td><td className="py-3 px-2 text-center font-mono text-amber-400">{row.occurrence}</td><td className="py-3 px-2 text-center font-mono text-blue-400">{row.detection}</td>
                  <td className="py-3 px-3 text-center font-mono font-black text-sm" style={{ color: isHigh ? 'var(--risk-critical)' : isMedium ? 'var(--risk-high)' : 'var(--risk-low)' }}>{row.rpn}</td>
                  <td className="py-3 px-3 text-center"><span className="px-2 py-0.5 rounded-full text-[9px] font-extrabold border" style={{ color: isHigh ? 'var(--risk-critical)' : isMedium ? 'var(--risk-high)' : 'var(--risk-low)', borderColor: isHigh ? 'var(--risk-critical)' : isMedium ? 'var(--risk-high)' : 'var(--risk-low)', background: isHigh ? 'color-mix(in oklab, var(--risk-critical) 12%, transparent)' : isMedium ? 'color-mix(in oklab, var(--risk-high) 12%, transparent)' : 'color-mix(in oklab, var(--risk-low) 12%, transparent)' }}>{row.action_priority}</span></td>
                  <td className="py-3 px-4 text-[11px] text-[var(--text-secondary)] max-w-md">{row.recommended_action}</td>
                  <td className="py-3 px-3 text-center font-mono font-bold text-xs text-emerald-400">{row.residual_rpn}</td>
                </tr>;
              })}
              {!loading && !loadError && filteredData.length === 0 && <tr><td colSpan={11} className="p-8 text-center text-sm text-[var(--text-muted)]">{components.length ? 'No failure modes match these filters.' : 'Load a sample BOM or upload your own BOM to generate its FMEA matrix.'}</td></tr>}
              {loading && <tr><td colSpan={11} className="p-8 text-center text-sm text-[var(--text-muted)]"><RefreshCw className="inline w-4 h-4 mr-2 animate-spin" />Generating suggested modes for {components.length} BOM components…</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
