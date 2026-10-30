import React from 'react';
import { Flame, Wrench } from 'lucide-react';
import type { MissionProfileData } from '../types';

interface Props {
  data: MissionProfileData | null;
  loading?: boolean;
}

export const EngineeringMissionProfileCard: React.FC<Props> = ({ data, loading }) => {
  if (loading) {
    return (
      <div className="glass-card p-6 rounded-2xl space-y-3">
        <div className="animate-spin w-5 h-5 border-2 border-rose-500 border-t-transparent rounded-full mx-auto" />
        <p className="text-center text-xs text-[var(--text-muted)]">Evaluating Arrhenius & thermal damage accumulation…</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="glass-card p-6 rounded-2xl space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg flex items-center justify-center text-rose-500" style={{ background: 'color-mix(in oklab, var(--risk-critical) 15%, var(--bg-elevated))' }}>
            <Flame className="w-4 h-4" />
          </span>
          <div>
            <span className="text-[10px] font-mono text-rose-500 uppercase tracking-widest font-semibold">
              Mission Profile & Thermal Life Consumption (Part 9)
            </span>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">
              Arrhenius Acceleration & Miner's Rule Damage
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono px-2.5 py-1 rounded-full border bg-[var(--bg-elevated)] border-[var(--border-subtle)] text-[var(--text-secondary)]">
            R_θ = {data.thermal_resistance_c_per_w} °C/W · Rated T_max = {data.rated_temp_max_c} °C
          </span>
          <span
            className="text-[11px] font-extrabold px-2.5 py-1 rounded-full border"
            style={{
              color: data.is_service_life_adequate ? 'var(--risk-low)' : 'var(--risk-critical)',
              background: data.is_service_life_adequate ? 'color-mix(in oklab, var(--risk-low) 12%, var(--bg-card))' : 'color-mix(in oklab, var(--risk-critical) 12%, var(--bg-card))',
              borderColor: data.is_service_life_adequate ? 'color-mix(in oklab, var(--risk-low) 35%, transparent)' : 'color-mix(in oklab, var(--risk-critical) 35%, transparent)',
            }}
          >
            {data.is_service_life_adequate ? 'ADEQUATE SERVICE LIFE' : 'LIFETIME CONSUMPTION EXCEEDED'}
          </span>
        </div>
      </div>

      {/* 4 Summary Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Peak Junction Temp (T_j)</span>
          <p className="text-lg font-black font-mono text-[var(--text-primary)]">
            {data.peak_junction_temp_c} °C
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            Rated max: {data.rated_temp_max_c} °C
          </p>
        </div>

        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Worst Thermal Margin</span>
          <p className="text-lg font-black font-mono" style={{ color: data.worst_thermal_margin_c > 15 ? 'var(--risk-low)' : data.worst_thermal_margin_c > 0 ? 'var(--risk-high)' : 'var(--risk-critical)' }}>
            {data.worst_thermal_margin_c.toFixed(1)} °C
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            {data.worst_thermal_margin_c <= 0 ? 'Exceeds rated junction limit' : 'Safe thermal headroom'}
          </p>
        </div>

        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Annual Damage (D)</span>
          <p className="text-lg font-black font-mono text-[var(--text-primary)]">
            {data.annual_cumulative_damage_d.toFixed(3)} / yr
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            Miner's rule: Σ (Δt_j / L_j)
          </p>
        </div>

        <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Projected Useful Life</span>
          <p className="text-lg font-black font-mono" style={{ color: data.is_service_life_adequate ? 'var(--risk-low)' : 'var(--risk-critical)' }}>
            {data.projected_life_years.toFixed(1)} yrs
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            Target: 10 yrs ({data.life_consumption_over_target_pct.toFixed(0)}% consumed)
          </p>
        </div>
      </div>

      {/* Operating Phases Breakdown */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[var(--text-primary)]">Mission Profile Operational Phases</span>
          <span className="text-[10px] font-mono text-[var(--text-muted)]">Arrhenius AF: exp[(Ea/k)(1/Tuse - 1/Tref)]</span>
        </div>
        <div className="border border-[var(--border-subtle)] rounded-xl overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-[var(--bg-elevated)] text-[var(--text-muted)] text-[10px] font-mono uppercase border-b border-[var(--border-subtle)]">
              <tr>
                <th className="py-2 px-3">Phase Name</th>
                <th className="py-2 px-3">Hours/yr</th>
                <th className="py-2 px-3">T_amb</th>
                <th className="py-2 px-3">Power</th>
                <th className="py-2 px-3">ΔT (P·R_θ)</th>
                <th className="py-2 px-3">T_junction</th>
                <th className="py-2 px-3">Arrhenius AF</th>
                <th className="py-2 px-3">Margin</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {data.phases.map((p, idx) => (
                <tr key={idx} className="hover:bg-[var(--bg-elevated)] transition-colors">
                  <td className="py-2 px-3 font-semibold text-[var(--text-primary)]">{p.phase_name}</td>
                  <td className="py-2 px-3 font-mono text-[var(--text-secondary)]">{p.annual_hours} h</td>
                  <td className="py-2 px-3 font-mono text-[var(--text-secondary)]">{p.ambient_temp_c} °C</td>
                  <td className="py-2 px-3 font-mono text-[var(--text-secondary)]">{p.power_watts} W</td>
                  <td className="py-2 px-3 font-mono text-[var(--text-secondary)]">+{p.temp_rise_delta_c} °C</td>
                  <td className="py-2 px-3 font-mono font-bold text-[var(--text-primary)]">{p.junction_temp_c} °C</td>
                  <td className="py-2 px-3 font-mono text-[var(--accent-gold)]">{p.arrhenius_af.toFixed(1)}x</td>
                  <td className="py-2 px-3 font-mono" style={{ color: p.thermal_margin_c > 0 ? 'var(--risk-low)' : 'var(--risk-critical)' }}>
                    {p.thermal_margin_c.toFixed(1)} °C
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Side-by-Side Mitigation Strategies */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Wrench className="w-3.5 h-3.5 text-[var(--accent-gold)]" />
          <span className="text-xs font-bold text-[var(--text-primary)]">Side-by-Side Hypothetical Mitigation Trade-Offs</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {data.mitigation_comparisons.map((m, idx) => (
            <div
              key={idx}
              className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[var(--text-primary)]">{m.strategy}</span>
                <span
                  className="text-[9px] font-extrabold px-2 py-0.5 rounded-full border"
                  style={{
                    color: m.adequate_for_target ? 'var(--risk-low)' : 'var(--risk-high)',
                    borderColor: m.adequate_for_target ? 'var(--risk-low)' : 'var(--risk-high)',
                  }}
                >
                  {m.adequate_for_target ? 'TARGET MET' : 'PARTIAL RELIEF'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div>
                  <span className="text-[10px] text-[var(--text-muted)] block">T_j Peak</span>
                  <span className="font-bold text-[var(--text-primary)]">{m.peak_junction_temp_c} °C</span>
                </div>
                <div>
                  <span className="text-[10px] text-[var(--text-muted)] block">Margin</span>
                  <span className="font-bold text-[var(--text-primary)]">+{m.thermal_margin_c} °C</span>
                </div>
                <div>
                  <span className="text-[10px] text-[var(--text-muted)] block">Proj. Life</span>
                  <span className="font-bold text-[var(--text-primary)]">{m.projected_life_years} yrs</span>
                </div>
                <div>
                  <span className="text-[10px] text-[var(--text-muted)] block">Consumption</span>
                  <span className="font-bold text-[var(--text-primary)]">{m.life_consumption_pct.toFixed(0)}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
