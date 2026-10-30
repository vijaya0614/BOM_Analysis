import React from 'react';
import { AlertTriangle } from 'lucide-react';
import type { FmeaEntry } from '../types';

interface Props {
  entries: FmeaEntry[];
  loading?: boolean;
}

export const EngineeringFmeaCard: React.FC<Props> = ({ entries, loading }) => {
  if (loading) {
    return (
      <div className="glass-card p-6 rounded-2xl space-y-3">
        <div className="animate-spin w-5 h-5 border-2 border-[var(--risk-high)] border-t-transparent rounded-full mx-auto" />
        <p className="text-center text-xs text-[var(--text-muted)]">Generating component failure mode & effects analysis…</p>
      </div>
    );
  }

  if (!entries || entries.length === 0) return null;

  const getApBadge = (priority: string) => {
    if (priority === 'HIGH') {
      return (
        <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full border text-rose-500 border-rose-500/30 bg-rose-500/10">
          HIGH PRIORITY
        </span>
      );
    }
    if (priority === 'MEDIUM') {
      return (
        <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full border text-amber-500 border-amber-500/30 bg-amber-500/10">
          MEDIUM
        </span>
      );
    }
    return (
      <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full border text-emerald-500 border-emerald-500/30 bg-emerald-500/10">
        LOW
      </span>
    );
  };

  return (
    <div className="glass-card p-6 rounded-2xl space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--risk-high)]" style={{ background: 'color-mix(in oklab, var(--risk-high) 15%, var(--bg-elevated))' }}>
            <AlertTriangle className="w-4 h-4" />
          </span>
          <div>
            <span className="text-[10px] font-mono text-[var(--risk-high)] uppercase tracking-widest font-semibold">
              Failure Mode & Effects Analysis (Part 11)
            </span>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">
              Component FMEA & Action Priority Matrix
            </h3>
          </div>
        </div>
        <span className="text-[11px] font-mono px-2.5 py-1 rounded-full border bg-[var(--bg-elevated)] border-[var(--border-subtle)] text-[var(--text-secondary)]">
          {entries.length} suggested failure mechanisms
        </span>
      </div>

      <p className="text-xs text-[var(--text-secondary)]">
        Severity (S), Occurrence (O), and Detection (D) ratings are based on component category and operational mission profile.
        Risk Priority Number (RPN = S × O × D) informs engineering mitigation priority.
      </p>

      {/* FMEA Table */}
      <div className="border border-[var(--border-subtle)] rounded-xl overflow-x-auto">
        <table className="w-full text-left text-xs min-w-[700px]">
          <thead className="bg-[var(--bg-elevated)] text-[var(--text-muted)] text-[10px] font-mono uppercase border-b border-[var(--border-subtle)]">
            <tr>
              <th className="py-2 px-3">Failure Mode</th>
              <th className="py-2 px-3">Mechanism / Cause</th>
              <th className="py-2 px-3">End-System Effect</th>
              <th className="py-2 px-3 text-center">S</th>
              <th className="py-2 px-3 text-center">O</th>
              <th className="py-2 px-3 text-center">D</th>
              <th className="py-2 px-3 text-center">RPN</th>
              <th className="py-2 px-3">Action Priority</th>
              <th className="py-2 px-3">Recommended Control / Mitigation</th>
              <th className="py-2 px-3 text-center">Residual RPN</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-subtle)]">
            {entries.map((f, idx) => (
              <tr key={idx} className="hover:bg-[var(--bg-elevated)] transition-colors">
                <td className="py-2.5 px-3 font-bold text-[var(--text-primary)]">{f.failure_mode}</td>
                <td className="py-2.5 px-3 text-[var(--text-secondary)]">{f.potential_cause}</td>
                <td className="py-2.5 px-3 text-[var(--text-secondary)]">{f.end_system_effect}</td>
                <td className="py-2.5 px-3 text-center font-mono font-bold">{f.severity}</td>
                <td className="py-2.5 px-3 text-center font-mono">{f.occurrence}</td>
                <td className="py-2.5 px-3 text-center font-mono">{f.detection}</td>
                <td className="py-2.5 px-3 text-center font-mono font-black" style={{ color: f.action_priority === 'HIGH' ? 'var(--risk-critical)' : f.action_priority === 'MEDIUM' ? 'var(--risk-high)' : 'var(--risk-low)' }}>
                  {f.rpn}
                </td>
                <td className="py-2.5 px-3">{getApBadge(f.action_priority)}</td>
                <td className="py-2.5 px-3 text-[11px] text-[var(--text-secondary)]">{f.recommended_action}</td>
                <td className="py-2.5 px-3 text-center font-mono text-emerald-500 font-bold">
                  {f.residual_rpn ?? Math.round(f.rpn * 0.45)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
