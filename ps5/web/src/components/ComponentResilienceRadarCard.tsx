import React from 'react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { ShieldCheck, ShieldAlert, Activity } from 'lucide-react';
import type { ResilienceRadar } from '../types';

interface Props {
  resilience: ResilienceRadar;
  partNumber: string;
}

export const ComponentResilienceRadarCard: React.FC<Props> = ({ resilience, partNumber }) => {
  const data = [
    { subject: 'Sourcing Security', score: resilience.sourcing_security, fullMark: 100 },
    { subject: 'Lead Time Resil.', score: resilience.lead_time_resilience, fullMark: 100 },
    { subject: 'Price Stability', score: resilience.price_stability, fullMark: 100 },
    { subject: 'Lifecycle Longevity', score: resilience.lifecycle_longevity, fullMark: 100 },
    { subject: 'Geopol. Safety', score: resilience.geopolitical_safety, fullMark: 100 },
    { subject: 'Geol. Hardiness', score: resilience.geological_hardiness, fullMark: 100 },
  ];

  const overallScore = Math.round(
    (resilience.sourcing_security +
      resilience.lead_time_resilience +
      resilience.price_stability +
      resilience.lifecycle_longevity +
      resilience.geopolitical_safety +
      resilience.geological_hardiness) / 6
  );

  const getTier = (s: number) => {
    if (s >= 75) return { label: 'ROBUST SUPPLY POSTURE', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30' };
    if (s >= 50) return { label: 'MODERATE RESILIENCE', color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30' };
    return { label: 'VULNERABLE COMPONENT', color: 'text-rose-400', bg: 'bg-rose-500/10 border-rose-500/30' };
  };

  const tier = getTier(overallScore);

  return (
    <div className="glass-card p-6 rounded-2xl space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border-subtle)] pb-4">
        <div>
          <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5" /> 6-Factor Multi-Disciplinary Posture
          </span>
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            Supply & Geological Resilience Radar
          </h3>
        </div>
        <div className={`px-3 py-1 rounded-xl border text-xs font-mono font-bold flex items-center gap-1.5 ${tier.bg} ${tier.color}`}>
          {overallScore >= 50 ? <ShieldCheck className="w-3.5 h-3.5" /> : <ShieldAlert className="w-3.5 h-3.5" />}
          <span>{overallScore}/100 · {tier.label}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
        {/* Polar Radar Chart */}
        <div className="lg:col-span-7 h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="75%" data={data}>
              <PolarGrid stroke="var(--border-subtle)" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--text-secondary)', fontSize: 10, fontFamily: 'monospace' }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="var(--border-subtle)" tick={{ fill: 'var(--text-muted)', fontSize: 8 }} />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const d = payload[0].payload;
                    return (
                      <div className="p-2.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-xl text-xs font-mono">
                        <p className="font-bold text-[var(--text-primary)]">{d.subject}</p>
                        <p className="text-[var(--accent-gold)]">{d.score} / 100</p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Radar
                name={partNumber}
                dataKey="score"
                stroke="var(--accent-gold)"
                fill="var(--accent-gold)"
                fillOpacity={0.35}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Breakdown Metric Chips */}
        <div className="lg:col-span-5 grid grid-cols-2 gap-2.5">
          {data.map((item) => {
            const isHigh = item.score >= 70;
            const isMed = item.score >= 45 && item.score < 70;
            const barColor = isHigh ? 'bg-emerald-400' : isMed ? 'bg-amber-400' : 'bg-rose-400';
            const textColor = isHigh ? 'text-emerald-400' : isMed ? 'text-amber-400' : 'text-rose-400';

            return (
              <div key={item.subject} className="p-3 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-1.5">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-[10px] text-[var(--text-muted)] truncate">{item.subject}</span>
                  <span className={`font-bold ${textColor}`}>{item.score}</span>
                </div>
                <div className="w-full h-1.5 bg-[var(--bg-card)] rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-700 ${barColor}`} style={{ width: `${item.score}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
