import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import { Sliders } from 'lucide-react';
import type { ToleranceAnalysisData } from '../types';

interface Props {
  data: ToleranceAnalysisData | null;
  loading?: boolean;
}

const format = (value: number | null | undefined, digits = 3) =>
  value == null || !Number.isFinite(value) ? 'UNKNOWN' : value.toFixed(digits);

export const EngineeringToleranceCard: React.FC<Props> = ({ data, loading }) => {
  if (loading) {
    return (
      <div className="glass-card p-6 rounded-2xl space-y-3">
        <div className="animate-spin w-5 h-5 border-2 border-[var(--accent-blue)] border-t-transparent rounded-full mx-auto" />
        <p className="text-center text-xs text-[var(--text-muted)]">Running WCCA, RSS, and Monte Carlo simulation…</p>
      </div>
    );
  }

  if (!data) return null;

  const hasSpec = data.spec_min_limit != null && data.spec_max_limit != null;
  const wccaPass = hasSpec
    ? data.worst_case_min >= data.spec_min_limit! && data.worst_case_max <= data.spec_max_limit!
    : null;
  const metricColor = wccaPass == null
    ? 'var(--text-muted)'
    : wccaPass ? 'var(--risk-low)' : 'var(--risk-critical)';
  const bins = data.histogram_bins ?? [];
  const sensitivities = data.sensitivity_ranking ?? [];

  return (
    <div className="glass-card p-6 rounded-2xl space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--accent-blue)]" style={{ background: 'color-mix(in oklab, var(--accent-blue) 15%, var(--bg-elevated))' }}>
            <Sliders className="w-4 h-4" />
          </span>
          <div>
            <span className="text-[10px] font-mono text-[var(--accent-blue)] uppercase tracking-widest font-semibold">
              Electrical Tolerance & Monte Carlo (Part 8)
            </span>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">
              Worst-Case (WCCA), RSS Statistical, & Sensitivity Analysis
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono px-2.5 py-1 rounded-full border bg-[var(--bg-elevated)] border-[var(--border-subtle)] text-[var(--text-secondary)]">
            {Number.isFinite(data.monte_carlo_samples) ? data.monte_carlo_samples.toLocaleString() : 'UNKNOWN'} Monte Carlo runs
          </span>
          <span className="text-[11px] font-extrabold px-2.5 py-1 rounded-full border" style={{
            color: metricColor,
            background: `color-mix(in oklab, ${metricColor} 12%, var(--bg-card))`,
            borderColor: `color-mix(in oklab, ${metricColor} 35%, transparent)`,
          }}>
            {wccaPass == null ? 'WCCA SPEC UNKNOWN' : wccaPass ? 'WCCA CONSTRAINTS MET' : 'WCCA BOUNDARY VIOLATION'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Nominal Output</span>
          <p className="text-lg font-black font-mono text-[var(--text-primary)]">{format(data.nominal_output)} {data.output_unit}</p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">Spec: [{format(data.spec_min_limit, 2)}, {format(data.spec_max_limit, 2)}] {data.output_unit}</p>
        </div>
        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">WCCA Extreme Range</span>
          <p className="text-lg font-black font-mono" style={{ color: metricColor }}>[{format(data.worst_case_min)}, {format(data.worst_case_max)}]</p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">{wccaPass == null ? 'Specification limits unavailable' : wccaPass ? 'Enclosed in spec bounds' : 'Exceeds spec bounds'}</p>
        </div>
        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">RSS 3σ Range</span>
          <p className="text-lg font-black font-mono text-[var(--text-primary)]">[{format(data.rss_3sigma_min)}, {format(data.rss_3sigma_max)}]</p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">RSS 1σ = {format(data.rss_sigma, 4)} {data.output_unit}</p>
        </div>
        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">MC Violation Rate</span>
          <p className="text-lg font-black font-mono" style={{ color: data.monte_carlo_violation_rate_pct === 0 ? 'var(--risk-low)' : data.monte_carlo_violation_rate_pct == null ? 'var(--text-muted)' : 'var(--risk-critical)' }}>{format(data.monte_carlo_violation_rate_pct, 2)}%</p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">{data.monte_carlo_samples?.toLocaleString() ?? 'UNKNOWN'} samples</p>
        </div>
      </div>

      <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-2">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-[var(--text-primary)]">Monte Carlo Output Distribution ({data.monte_carlo_samples?.toLocaleString() ?? 'UNKNOWN'} Samples)</p>
            <p className="text-[10px] text-[var(--text-muted)]">μ = {format(data.monte_carlo_mean)} {data.output_unit} · σ = {format(data.monte_carlo_std, 4)}</p>
          </div>
          <span className="text-[10px] font-mono text-[var(--accent-gold)]">Deterministic simulation</span>
        </div>
        <div className="h-44 w-full">
          {bins.length ? <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bins} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
              <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
              <XAxis dataKey="bin_center" tick={{ fontSize: 9, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} tickFormatter={(v) => Number(v).toFixed(2)} />
              <YAxis tick={{ fontSize: 9, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ background: 'var(--bg-surface-solid)', border: '1px solid var(--border-subtle)', borderRadius: '10px', fontSize: '11px' }} formatter={(val, _name, props: any) => [`${val} samples (${(props.payload.frequency * 100).toFixed(1)}%)`, 'Count']} />
              {data.spec_min_limit != null && <ReferenceLine x={data.spec_min_limit} stroke="var(--risk-critical)" strokeDasharray="3 3" label={{ value: 'Spec Min', fill: 'var(--risk-critical)', fontSize: 9 }} />}
              {data.spec_max_limit != null && <ReferenceLine x={data.spec_max_limit} stroke="var(--risk-critical)" strokeDasharray="3 3" label={{ value: 'Spec Max', fill: 'var(--risk-critical)', fontSize: 9 }} />}
              <Bar dataKey="count" fill="var(--accent-blue)" radius={[4, 4, 0, 0]} opacity={0.85} />
            </BarChart>
          </ResponsiveContainer> : <p className="pt-12 text-center text-xs text-[var(--text-muted)]">No histogram data available.</p>}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[var(--text-primary)]">Circuit Parameter Sensitivity Ranking</span>
          <span className="text-[10px] font-mono text-[var(--text-muted)]">Contribution to output variance</span>
        </div>
        <div className="border border-[var(--border-subtle)] rounded-xl overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--bg-elevated)] text-[var(--text-muted)] text-[10px] font-mono uppercase border-b border-[var(--border-subtle)]">
              <tr><th className="py-2 px-3">Parameter</th><th className="py-2 px-3">Sensitivity Derivative</th><th className="py-2 px-3">Variance Contribution</th></tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {sensitivities.map((s, idx) => <tr key={`${s.parameter}-${idx}`} className="hover:bg-[var(--bg-elevated)] transition-colors">
                <td className="py-2 px-3 font-semibold text-[var(--text-primary)]">{s.parameter || 'UNKNOWN'}</td>
                <td className="py-2 px-3 font-mono text-[var(--text-secondary)]">{format(s.sensitivity_derivative, 4)}</td>
                <td className="py-2 px-3 font-mono font-bold text-[var(--text-primary)]">{format(s.variance_contribution_pct, 1)}%</td>
              </tr>)}
              {!sensitivities.length && <tr><td colSpan={3} className="py-3 px-3 text-[var(--text-muted)]">No sensitivity data available.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
