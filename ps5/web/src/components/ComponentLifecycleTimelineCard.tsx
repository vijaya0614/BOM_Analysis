import React from 'react';
import { Clock, AlertTriangle, CheckCircle, Calendar, Zap, AlertOctagon } from 'lucide-react';
import type { LifecycleDetails } from '../types';

interface Props {
  lifecycle: LifecycleDetails;
  partNumber: string;
}

export const ComponentLifecycleTimelineCard: React.FC<Props> = ({ lifecycle, partNumber }) => {
  const isEol = lifecycle.lifecycle_status === 'EOL';
  const isNrnd = lifecycle.lifecycle_status === 'NRND';

  const badgeStyle = isEol
    ? 'bg-rose-500/10 border-rose-500/30 text-rose-400'
    : isNrnd
    ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
    : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400';

  const statusLabel = isEol
    ? 'END OF LIFE (EOL)'
    : isNrnd
    ? 'NOT RECOMMENDED FOR NEW DESIGNS (NRND)'
    : 'ACTIVE IN PRODUCTION';

  const stages = [
    { label: 'Introduction', year: lifecycle.introduction_year, done: true },
    { label: 'Volume Maturity', year: lifecycle.introduction_year + 5, done: lifecycle.phase_progress_pct >= 50 },
    { label: 'NRND Notice', year: lifecycle.expected_eol_year - 2, done: isNrnd || isEol },
    { label: 'Last-Time Buy (LTB)', year: lifecycle.expected_eol_year - 1, done: isEol },
    { label: 'End of Life', year: lifecycle.expected_eol_year, done: isEol },
  ];

  return (
    <div className="glass-card p-6 rounded-2xl space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border-subtle)] pb-4">
        <div>
          <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" /> Component Lifecycle Horizon
          </span>
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            Lifecycle Stage & Obsolescence Horizon
          </h3>
        </div>
        <div className={`px-3 py-1 rounded-xl border text-xs font-mono font-bold flex items-center gap-2 ${badgeStyle}`}>
          {isEol ? <AlertOctagon className="w-4 h-4" /> : isNrnd ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
          <span>{statusLabel}</span>
        </div>
      </div>

      {/* Visual Timeline Stepper Infographic */}
      <div className="relative pt-6 pb-2">
        {/* Background track */}
        <div className="w-full h-2.5 bg-[var(--bg-elevated)] rounded-full overflow-hidden border border-[var(--border-subtle)] relative">
          <div
            className={`h-full transition-all duration-1000 ${
              isEol ? 'bg-gradient-to-r from-emerald-500 via-amber-500 to-rose-500' :
              isNrnd ? 'bg-gradient-to-r from-emerald-500 to-amber-500' :
              'bg-gradient-to-r from-emerald-500 to-emerald-400'
            }`}
            style={{ width: `${Math.min(100, Math.max(5, lifecycle.phase_progress_pct))}%` }}
          />
        </div>

        {/* Milestone Markers */}
        <div className="grid grid-cols-5 gap-2 mt-4 text-center">
          {stages.map((stage, i) => (
            <div key={stage.label} className="flex flex-col items-center">
              <div
                className={`w-4 h-4 rounded-full border-2 mb-1.5 flex items-center justify-center transition-all ${
                  stage.done
                    ? i >= 3
                      ? 'border-rose-400 bg-rose-500/20'
                      : i === 2
                      ? 'border-amber-400 bg-amber-500/20'
                      : 'border-emerald-400 bg-emerald-500/20'
                    : 'border-[var(--border-strong)] bg-[var(--bg-elevated)]'
                }`}
              >
                <div
                  className={`w-1.5 h-1.5 rounded-full ${
                    stage.done
                      ? i >= 3
                        ? 'bg-rose-400'
                        : i === 2
                        ? 'bg-amber-400'
                        : 'bg-emerald-400'
                      : 'bg-transparent'
                  }`}
                />
              </div>
              <span className="text-[11px] font-bold text-[var(--text-primary)] font-mono">{stage.label}</span>
              <span className="text-[10px] text-[var(--text-muted)] font-mono">~{stage.year}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Critical LTB / Horizon Callout */}
      {(isEol || isNrnd) && lifecycle.ltb_date && (
        <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <p className="font-bold text-rose-300 font-mono">
              Action Required: Last-Time Buy (LTB) Deadline: {lifecycle.ltb_date}
            </p>
            <p className="text-[var(--text-secondary)]">
              Component {partNumber} is flagged as {lifecycle.lifecycle_status}. Factory production termination scheduled with final order cutoff by {lifecycle.ltb_date} and last shipments by {lifecycle.lts_date || 'N/A'}. Immediate substitute qualification or last-time procurement recommended.
            </p>
          </div>
        </div>
      )}

      {/* Key Factor Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
        <div className="p-3 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] text-[var(--text-muted)] font-mono uppercase flex items-center gap-1">
            <Calendar className="w-3 h-3 text-[var(--accent-gold)]" /> Years Remaining
          </span>
          <p className="text-sm font-bold font-mono text-[var(--text-primary)]">
            {lifecycle.years_remaining > 0 ? `${lifecycle.years_remaining.toFixed(1)} yrs` : 'Terminated / 0 yrs'}
          </p>
        </div>

        <div className="p-3 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] text-[var(--text-muted)] font-mono uppercase flex items-center gap-1">
            <Zap className="w-3 h-3 text-[var(--accent-blue)]" /> Lifecycle Phase
          </span>
          <p className="text-sm font-bold font-mono text-[var(--text-primary)]">
            {lifecycle.phase_progress_pct.toFixed(0)}% Consumed
          </p>
        </div>

        <div className="p-3 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] text-[var(--text-muted)] font-mono uppercase">Weibull Shape (β)</span>
          <p className="text-sm font-bold font-mono text-[var(--text-primary)]">
            {lifecycle.weibull_shape_beta} (Aging Rate)
          </p>
        </div>

        <div className="p-3 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] text-[var(--text-muted)] font-mono uppercase">Scale Life (η)</span>
          <p className="text-sm font-bold font-mono text-[var(--text-primary)]">
            {lifecycle.weibull_scale_eta_years} yrs (Characteristic)
          </p>
        </div>
      </div>
    </div>
  );
};
