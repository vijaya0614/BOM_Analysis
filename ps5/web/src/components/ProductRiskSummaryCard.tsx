import React, { useState, useEffect } from 'react';
import { ShieldAlert } from 'lucide-react';
import { SUBSTITUTE_API_BASE } from '../api';

interface SubsystemRollup {
  subsystem_name: string;
  component_count: number;
  critical_or_high_count: number;
  subsystem_risk_rating: string;
  top_risk_part: string;
}

interface ProductRiskData {
  product_name: string;
  analyzed_component_count: number;
  spof_count: number;
  critical_unhedged_lines_count: number;
  estimated_financial_disruption_exposure_usd: number;
  product_risk_index: number;
  subsystem_rollups: SubsystemRollup[];
  top_priority_mitigations: string[];
}

export const ProductRiskSummaryCard: React.FC = () => {
  const [data, setData] = useState<ProductRiskData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    fetchProductSummary();
  }, []);

  const fetchProductSummary = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${SUBSTITUTE_API_BASE}/api/product/risk-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_name: 'PS5 BeagleBone & Industrial Prototype Assembly' }),
      });
      if (res.ok) {
        const resData = await res.json();
        const subsystemRollups: SubsystemRollup[] = [];
        if (Array.isArray(resData.subsystem_rollups)) {
          subsystemRollups.push(...resData.subsystem_rollups);
        } else if (resData.subsystem_risk_breakdown && typeof resData.subsystem_risk_breakdown === 'object') {
          for (const [name, info] of Object.entries<any>(resData.subsystem_risk_breakdown)) {
            subsystemRollups.push({
              subsystem_name: name,
              component_count: info.component_count ?? 1,
              critical_or_high_count: info.critical_lines_count ?? 0,
              subsystem_risk_rating: info.status ?? 'HEALTHY',
              top_risk_part: resData.highest_risk_lines?.find((l: any) => l.subsystem === name)?.part_number ?? 'Nominal',
            });
          }
        }

        const normalized: ProductRiskData = {
          product_name: resData.product_name ?? 'PS5 Prototype Assembly',
          analyzed_component_count: resData.analyzed_component_count ?? resData.total_components_count ?? 15,
          spof_count: resData.spof_count ?? resData.single_points_of_failure_count ?? 0,
          critical_unhedged_lines_count: resData.critical_unhedged_lines_count ?? resData.unhedged_critical_parts_count ?? 0,
          estimated_financial_disruption_exposure_usd: resData.estimated_financial_disruption_exposure_usd ?? resData.total_expected_disruption_exposure ?? 0,
          product_risk_index: resData.product_risk_index ?? (resData.overall_health_score ? (100 - resData.overall_health_score) : 31.0),
          subsystem_rollups: subsystemRollups,
          top_priority_mitigations: resData.top_priority_mitigations ?? resData.key_recommendations ?? [],
        };
        setData(normalized);
      }
    } catch {
      // offline fallback
    } finally {
      setLoading(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="glass-card p-6 rounded-2xl text-center text-xs text-[var(--text-muted)]">
        <div className="animate-spin w-5 h-5 border-2 border-rose-500 border-t-transparent rounded-full mx-auto mb-2" />
        Aggregating product-level risk & SPOF posture…
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="glass-card p-6 rounded-2xl space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--risk-critical)]" style={{ background: 'color-mix(in oklab, var(--risk-critical) 15%, var(--bg-elevated))' }}>
            <ShieldAlert className="w-4 h-4" />
          </span>
          <div>
            <span className="text-[10px] font-mono text-[var(--risk-critical)] uppercase tracking-widest font-semibold">
              Product-Level Risk Aggregation (Part 13)
            </span>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">
              System Risk Posture, SPOF, & Disruption Exposure
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right">
            <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Product Risk Index</span>
            <div className="text-lg font-black font-mono leading-none text-[var(--risk-high)]">
              {data.product_risk_index.toFixed(1)} / 100
            </div>
          </div>
        </div>
      </div>

      {/* 3 Key Product Risk Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Single Points of Failure (SPOF)</span>
          <p className="text-2xl font-black font-mono" style={{ color: data.spof_count > 0 ? 'var(--risk-critical)' : 'var(--risk-low)' }}>
            {data.spof_count} parts
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            {data.spof_count} critical components with single source & no drop-in
          </p>
        </div>

        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Unhedged Critical Lines</span>
          <p className="text-2xl font-black font-mono" style={{ color: data.critical_unhedged_lines_count > 0 ? 'var(--risk-high)' : 'var(--risk-low)' }}>
            {data.critical_unhedged_lines_count} lines
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            Requires engineering qualification or buffer stock
          </p>
        </div>

        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Financial Disruption Exposure</span>
          <p className="text-2xl font-black font-mono text-[var(--risk-critical)]">
            ${Math.round(data.estimated_financial_disruption_exposure_usd).toLocaleString()}
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            P(disruption) × estimated downtime impact
          </p>
        </div>
      </div>

      {/* Subsystem Roll-Up Table */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[var(--text-primary)]">Subsystem Risk Roll-Up</span>
          <span className="text-[10px] font-mono text-[var(--text-muted)]">Aggregated without assuming independence</span>
        </div>
        <div className="border border-[var(--border-subtle)] rounded-xl overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--bg-elevated)] text-[var(--text-muted)] text-[10px] font-mono uppercase border-b border-[var(--border-subtle)]">
              <tr>
                <th className="py-2 px-3">Subsystem</th>
                <th className="py-2 px-3">BOM Parts</th>
                <th className="py-2 px-3">Critical / High</th>
                <th className="py-2 px-3">Subsystem Risk</th>
                <th className="py-2 px-3">Top Risk Component</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {data.subsystem_rollups.map((sub, idx) => (
                <tr key={idx} className="hover:bg-[var(--bg-elevated)] transition-colors">
                  <td className="py-2.5 px-3 font-semibold text-[var(--text-primary)]">{sub.subsystem_name}</td>
                  <td className="py-2.5 px-3 font-mono text-[var(--text-secondary)]">{sub.component_count}</td>
                  <td className="py-2.5 px-3 font-mono font-bold" style={{ color: sub.critical_or_high_count > 0 ? 'var(--risk-high)' : 'var(--risk-low)' }}>
                    {sub.critical_or_high_count}
                  </td>
                  <td className="py-2.5 px-3">
                    <span
                      className="px-2 py-0.5 rounded-full text-[9px] font-extrabold border"
                      style={{
                        color: sub.subsystem_risk_rating === 'CRITICAL' ? 'var(--risk-critical)' : sub.subsystem_risk_rating === 'HIGH' ? 'var(--risk-high)' : 'var(--risk-low)',
                        borderColor: sub.subsystem_risk_rating === 'CRITICAL' ? 'var(--risk-critical)' : sub.subsystem_risk_rating === 'HIGH' ? 'var(--risk-high)' : 'var(--risk-low)',
                      }}
                    >
                      {sub.subsystem_risk_rating}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 font-mono text-xs text-[var(--text-primary)]">{sub.top_risk_part}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Top Priority Mitigations */}
      <div className="p-3.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] space-y-1.5 text-xs">
        <span className="font-bold text-[var(--text-primary)]">System-Level Priority Recommendations:</span>
        <ul className="space-y-1 text-[var(--text-secondary)] list-disc pl-4">
          {data.top_priority_mitigations.map((item, idx) => (
            <li key={idx}>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
};
