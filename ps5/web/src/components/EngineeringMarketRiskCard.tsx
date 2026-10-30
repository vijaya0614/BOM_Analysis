import React from 'react';
import { CheckCircle2, XCircle, HelpCircle, Layers } from 'lucide-react';
import type { MarketSupplyRiskData } from '../types';

interface Props {
  data: MarketSupplyRiskData | null;
  loading?: boolean;
}

export const EngineeringMarketRiskCard: React.FC<Props> = ({ data, loading }) => {
  if (loading) {
    return (
      <div className="glass-card p-6 rounded-2xl space-y-3">
        <div className="animate-spin w-5 h-5 border-2 border-[var(--accent-blue)] border-t-transparent rounded-full mx-auto" />
        <p className="text-center text-xs text-[var(--text-muted)]">Analyzing market supply pressure…</p>
      </div>
    );
  }

  if (!data) return null;

  const tier = (data.spi_risk_category || 'UNKNOWN').toUpperCase();
  const spiColor = tier === 'CRITICAL'
    ? 'var(--risk-critical)'
    : tier === 'HIGH'
      ? 'var(--risk-high)'
      : tier === 'MODERATE'
        ? 'var(--risk-medium)'
        : tier === 'LOW'
          ? 'var(--risk-low)'
          : 'var(--text-muted)';
  const overallStatus = data.tolerance_checks?.some((check) => check.status === 'FAIL')
    ? 'FAIL'
    : data.tolerance_checks?.length && data.tolerance_checks.every((check) => check.status === 'PASS')
      ? 'PASS'
      : 'UNKNOWN';

  const getStatusBadge = (status: string) => {
    if (status === 'PASS') {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-extrabold px-2 py-0.5 rounded-full border text-emerald-500 border-emerald-500/30 bg-emerald-500/10">
          <CheckCircle2 className="w-3 h-3" /> PASS
        </span>
      );
    }
    if (status === 'FAIL') {
      return (
        <span className="inline-flex items-center gap-1 text-[10px] font-extrabold px-2 py-0.5 rounded-full border text-rose-500 border-rose-500/30 bg-rose-500/10">
          <XCircle className="w-3 h-3" /> FAIL
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-extrabold px-2 py-0.5 rounded-full border text-[var(--text-muted)] border-[var(--border-subtle)] bg-[var(--bg-elevated)]">
        <HelpCircle className="w-3 h-3" /> UNKNOWN
      </span>
    );
  };

  return (
    <div className="glass-card p-6 rounded-2xl space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'color-mix(in oklab, var(--accent-blue) 15%, var(--bg-elevated))', color: 'var(--accent-blue)' }}>
            <Layers className="w-4 h-4" />
          </span>
          <div>
            <span className="text-[10px] font-mono text-[var(--accent-blue)] uppercase tracking-widest font-semibold">
              Market Conditions & Supply Pressure (Part 6)
            </span>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">
              Supply Pressure Index (SPI) & Availability Gates
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right">
            <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Supply Pressure Index</span>
            <div className="text-lg font-black font-mono leading-none" style={{ color: spiColor }}>
              {Number.isFinite(data.supply_pressure_index) ? data.supply_pressure_index.toFixed(1) : 'UNKNOWN'} / 100
            </div>
          </div>
          <span className="text-[11px] font-extrabold px-2.5 py-1 rounded-full border" style={{
            color: spiColor,
            background: `color-mix(in oklab, ${spiColor} 12%, var(--bg-card))`,
            borderColor: `color-mix(in oklab, ${spiColor} 35%, transparent)`,
          }}>
            {tier}
          </span>
        </div>
      </div>

      {/* 4 Quantitative Supply Pillars */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Inventory Coverage</span>
          <p className="text-lg font-black font-mono text-[var(--text-primary)]">
              {data.inventory_coverage_weeks != null ? `${data.inventory_coverage_weeks} wks` : 'UNKNOWN'}
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            {data.available_stock != null ? data.available_stock.toLocaleString() : 'UNKNOWN'} units @ {data.weekly_demand ?? 'UNKNOWN'}/wk
          </p>
        </div>

        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Lead-Time Margin</span>
          <p className="text-lg font-black font-mono" style={{ color: data.lead_time_margin_weeks == null ? 'var(--text-muted)' : data.lead_time_margin_weeks >= 0 ? 'var(--risk-low)' : 'var(--risk-critical)' }}>
            {data.lead_time_margin_weeks == null ? 'UNKNOWN' : `${data.lead_time_margin_weeks > 0 ? '+' : ''}${data.lead_time_margin_weeks} wks`}
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            Lead: {data.estimated_lead_time_weeks ?? 'UNKNOWN'}wk vs Window: {data.available_procurement_window_weeks ?? 'UNKNOWN'}wk
          </p>
        </div>

        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Supplier HHI</span>
          <p className="text-lg font-black font-mono text-[var(--text-primary)]">
            {data.hhi_concentration != null ? data.hhi_concentration : 'UNKNOWN'}
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            {data.hhi_tier || 'UNKNOWN'} (Σ s_i²)
          </p>
        </div>

        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Arrival Feasibility</span>
          <p className="text-lg font-black font-mono" style={{ color: data.can_arrive_before_deadline == null ? 'var(--text-muted)' : data.can_arrive_before_deadline ? 'var(--risk-low)' : 'var(--risk-critical)' }}>
            {data.can_arrive_before_deadline == null ? 'UNKNOWN' : data.can_arrive_before_deadline ? 'ON TIME' : 'DEADLINE BREACH'}
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            {overallStatus === 'PASS' ? 'All tolerances passed' : overallStatus === 'FAIL' ? 'Tolerance violation' : 'Insufficient data'}
          </p>
        </div>
      </div>

      {/* Configured Availability Tolerance Checks */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[var(--text-primary)]">Configured Availability Tolerances</span>
          <span className="text-[10px] font-mono text-[var(--text-muted)]">Pass/Fail verification against defined targets</span>
        </div>
        <div className="border border-[var(--border-subtle)] rounded-xl overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--bg-elevated)] text-[var(--text-muted)] text-[10px] font-mono uppercase border-b border-[var(--border-subtle)]">
              <tr>
                <th className="py-2 px-3">Parameter</th>
                <th className="py-2 px-3">Rule / Threshold</th>
                <th className="py-2 px-3">Measured Value</th>
                <th className="py-2 px-3">Status</th>
                <th className="py-2 px-3">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {(data.tolerance_checks || []).map((item, idx) => (
                <tr key={idx} className="hover:bg-[var(--bg-elevated)] transition-colors">
                  <td className="py-2 px-3 font-semibold text-[var(--text-primary)]">{(item.parameter || 'UNKNOWN').replace(/_/g, ' ')}</td>
                  <td className="py-2 px-3 font-mono text-[var(--text-secondary)]">{String(item.configured_threshold ?? 'UNKNOWN')}</td>
                  <td className="py-2 px-3 font-mono text-[var(--text-primary)]">{String(item.observed_value ?? 'UNKNOWN')}</td>
                  <td className="py-2 px-3">{getStatusBadge(item.status)}</td>
                  <td className="py-2 px-3 text-[11px] text-[var(--text-muted)]">{item.explanation || 'No explanation provided'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
