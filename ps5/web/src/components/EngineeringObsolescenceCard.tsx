import React from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import { Clock, ShieldAlert } from 'lucide-react';
import type { ObsolescenceForecastData } from '../types';

interface Props {
  data: ObsolescenceForecastData | null;
  loading?: boolean;
}

export const EngineeringObsolescenceCard: React.FC<Props> = ({ data, loading }) => {
  if (loading) {
    return (
      <div className="glass-card p-6 rounded-2xl space-y-3">
        <div className="animate-spin w-5 h-5 border-2 border-[var(--accent-gold)] border-t-transparent rounded-full mx-auto" />
        <p className="text-center text-xs text-[var(--text-muted)]">Calculating Weibull survival model…</p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const horizons = Object.entries(data.horizons || {});
  
  // Build 10-year Weibull survival curve: S(t) = exp(-(t/eta)^beta)
  const beta = data.weibull_shape_beta || 3.0;
  const eta = data.weibull_scale_eta_years || 12.0;
  const curvePoints = Array.from({ length: 11 }, (_, t) => {
    const survival = Math.exp(-Math.pow(t / eta, beta)) * 100;
    return {
      year: `${t}y`,
      t,
      survival: Number(survival.toFixed(1)),
      unavailable: Number((100 - survival).toFixed(1)),
    };
  });

  const getCatColor = (cat: string) => {
    if (cat === 'CRITICAL') return 'var(--risk-critical)';
    if (cat === 'HIGH') return 'var(--risk-high)';
    if (cat === 'MODERATE') return 'var(--risk-medium)';
    return 'var(--risk-low)';
  };

  return (
    <div className="glass-card p-6 rounded-2xl space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'color-mix(in oklab, var(--accent-gold) 15%, var(--bg-elevated))', color: 'var(--accent-gold)' }}>
            <Clock className="w-4 h-4" />
          </span>
          <div>
            <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest font-semibold">
              Obsolescence Forecasting (Part 5)
            </span>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">
              Weibull Survival & Unavailability Horizons
            </h3>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono px-2.5 py-1 rounded-full border bg-[var(--bg-elevated)] border-[var(--border-subtle)] text-[var(--text-secondary)]">
            β = {data.weibull_shape_beta} · η = {data.weibull_scale_eta_years} yrs
          </span>
          <span className="text-[11px] font-bold px-2.5 py-1 rounded-full border" style={{
            color: data.is_high_risk ? 'var(--risk-critical)' : 'var(--risk-low)',
            background: data.is_high_risk ? 'color-mix(in oklab, var(--risk-critical) 12%, var(--bg-card))' : 'color-mix(in oklab, var(--risk-low) 12%, var(--bg-card))',
            borderColor: data.is_high_risk ? 'color-mix(in oklab, var(--risk-critical) 35%, transparent)' : 'color-mix(in oklab, var(--risk-low) 35%, transparent)',
          }}>
            {data.is_high_risk ? 'HIGH OBSOLESCENCE RISK' : 'LOW OBSOLESCENCE RISK'}
          </span>
        </div>
      </div>

      {/* Horizon Probability Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {horizons.map(([key, h]) => {
          const color = getCatColor(h.risk_category);
          return (
            <div
              key={key}
              className="p-4 rounded-xl border relative overflow-hidden space-y-1.5"
              style={{
                background: `color-mix(in oklab, ${color} 6%, var(--bg-elevated))`,
                borderColor: `color-mix(in oklab, ${color} 25%, transparent)`,
              }}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[var(--text-secondary)]">{key.replace('_', ' ')} Horizon</span>
                <span
                  className="px-2 py-0.5 rounded-full text-[10px] font-extrabold border"
                  style={{
                    color,
                    background: `color-mix(in oklab, ${color} 15%, var(--bg-card))`,
                    borderColor: `color-mix(in oklab, ${color} 40%, transparent)`,
                  }}
                >
                  {h.risk_category}
                </span>
              </div>
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-2xl font-black font-mono" style={{ color }}>
                  {(h.unavailability_probability * 100).toFixed(1)}%
                </span>
                <span className="text-[10px] text-[var(--text-muted)] font-mono">unavailability prob.</span>
              </div>
              <p className="text-[10px] text-[var(--text-muted)] font-mono">
                P(T ≤ {data.years_in_market + h.years}y | T &gt; {data.years_in_market}y)
              </p>
            </div>
          );
        })}
      </div>

      {/* Weibull Survival Curve Chart */}
      <div className="p-4 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-2">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-[var(--text-primary)]">Weibull Survival Function: S(t) = exp[−(t/η)^β]</p>
            <p className="text-[10px] text-[var(--text-muted)]">Current component market age: {data.years_in_market} years</p>
          </div>
          <span className="text-[10px] font-mono text-[var(--accent-gold)]">Method: {data.methodology}</span>
        </div>
        <div className="h-44 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={curvePoints} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
              <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
              <XAxis dataKey="year" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-surface-solid)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '10px',
                  fontSize: '11px',
                }}
                formatter={(v) => [`${Number(v)}%`, 'Availability S(t)']}
              />
              <ReferenceLine x={`${data.years_in_market}y`} stroke="var(--accent-gold)" strokeDasharray="3 3" label={{ value: 'Current Age', fill: 'var(--accent-gold)', fontSize: 9, position: 'top' }} />
              <Line type="monotone" dataKey="survival" name="Availability S(t)" stroke="var(--accent-blue)" strokeWidth={2.5} dot={{ r: 2.5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recommended Obsolescence Mitigation */}
      <div className="p-3.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] flex items-start gap-2.5 text-xs">
        <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0 text-[var(--accent-gold)]" />
        <div className="space-y-1">
          <span className="font-bold text-[var(--text-primary)]">Recommended Mitigation:</span>
          <p className="text-[var(--text-secondary)]">{data.recommended_mitigation}</p>
        </div>
      </div>
    </div>
  );
};
