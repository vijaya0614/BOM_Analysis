import React, { useState } from 'react';
import type { RiskReportDashboard, BOMComponent } from '../types';
import type { ApprovalMap } from '../App';
import {
  FileText, Printer, Sparkles, FileSpreadsheet,
  ShieldAlert, TrendingUp, CheckCircle2, AlertCircle,
  Cpu, Zap, Activity, Download, ChevronRight, AlertTriangle
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { getRiskColor } from '../components/primitives';
import { SUBSTITUTE_API_BASE } from '../api';

interface ReportDownloadPageProps {
  report: RiskReportDashboard | null;
  approvedSubstitutes?: ApprovalMap;
}

// ──────────────────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────────────────

const BAND_CONFIG: Record<string, { bg: string; border: string; text: string; bar: string; label: string }> = {
  CRITICAL:          { bg: 'bg-red-500/15',    border: 'border-red-500/40',    text: 'text-red-400',    bar: 'bg-red-500',    label: 'Critical' },
  HIGH:              { bg: 'bg-amber-500/15',  border: 'border-amber-500/40',  text: 'text-amber-400',  bar: 'bg-amber-500',  label: 'High' },
  MEDIUM:            { bg: 'bg-yellow-400/15', border: 'border-yellow-400/40', text: 'text-yellow-400', bar: 'bg-yellow-400', label: 'Medium' },
  LOW:               { bg: 'bg-emerald-500/15',border: 'border-emerald-500/40',text: 'text-emerald-400',bar: 'bg-emerald-500',label: 'Low' },
  INSUFFICIENT_DATA: { bg: 'bg-gray-500/15',   border: 'border-gray-500/40',   text: 'text-gray-400',   bar: 'bg-gray-500',   label: 'Insufficient Data' },
};

const OVERALL_GRADIENT: Record<string, string> = {
  CRITICAL:          'from-red-600 to-rose-700',
  HIGH:              'from-amber-500 to-orange-600',
  MEDIUM:            'from-yellow-400 to-amber-500',
  LOW:               'from-emerald-500 to-teal-500',
  INSUFFICIENT_DATA: 'from-gray-500 to-slate-600',
};

const OVERALL_GLOW: Record<string, string> = {
  CRITICAL:          'shadow-red-500/30',
  HIGH:              'shadow-amber-500/30',
  MEDIUM:            'shadow-yellow-400/30',
  LOW:               'shadow-emerald-500/30',
  INSUFFICIENT_DATA: 'shadow-gray-500/30',
};

// Radial risk score gauge
const RiskGauge: React.FC<{ score: number | null; band: string }> = ({ score, band }) => {
  const numScore = score ?? 0;
  const pct = Math.min(numScore, 1);
  const r = 36;
  const circ = 2 * Math.PI * r;
  const dash = circ * pct;
  const cfg = BAND_CONFIG[band as keyof typeof BAND_CONFIG] ?? BAND_CONFIG.LOW;
  const strokeColor = score == null ? '#94867F' : getRiskColor(numScore);

  return (
    <svg width="88" height="88" viewBox="0 0 88 88" className="shrink-0">
      {/* Track */}
      <circle cx="44" cy="44" r={r} fill="none" stroke="currentColor"
        className="text-[var(--bg-elevated)]" strokeWidth="7" />
      {/* Arc */}
      <circle
        cx="44" cy="44" r={r} fill="none"
        stroke={strokeColor} strokeWidth="7"
        strokeLinecap="round"
        strokeDasharray={`${dash} ${circ}`}
        transform="rotate(-90 44 44)"
        style={{ filter: `drop-shadow(0 1px 3px color-mix(in oklab, ${strokeColor} 45%, transparent))` }}
      />
      {/* Center label */}
      <text x="44" y="40" textAnchor="middle" dominantBaseline="middle"
        className={cfg.text} fill={strokeColor}
        style={{ fontSize: '14px', fontWeight: 700, fontFamily: 'monospace' }}>
        {score == null ? '—' : (score * 100).toFixed(0)}
      </text>
      <text x="44" y="55" textAnchor="middle" dominantBaseline="middle"
        fill="currentColor" style={{ fontSize: '8px', opacity: 0.4, fontFamily: 'monospace' }}>
        SCORE
      </text>
    </svg>
  );
};

// Mini horizontal bar
const RiskBar: React.FC<{ value: number | null; band: string }> = ({ value, band }) => {
  const numVal = value ?? 0;
  const cfg = BAND_CONFIG[band as keyof typeof BAND_CONFIG] ?? BAND_CONFIG.LOW;
  return (
    <div className="h-1.5 w-full bg-[var(--bg-elevated)] rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full ${cfg.bar}`}
        style={{ width: `${Math.min(numVal * 100, 100)}%`, transition: 'width 0.8s cubic-bezier(0.16,1,0.3,1)' }}
      />
    </div>
  );
};

// Distribution pill
const BandPill: React.FC<{ count: number; band: keyof typeof BAND_CONFIG }> = ({ count, band }) => {
  const cfg = BAND_CONFIG[band];
  return (
    <div className={`flex flex-col items-center px-4 py-3 rounded-2xl border ${cfg.bg} ${cfg.border}`}>
      <span className={`text-2xl font-black font-mono ${cfg.text}`}>{count}</span>
      <span className={`text-[10px] font-bold uppercase tracking-wider ${cfg.text} opacity-80`}>{cfg.label}</span>
    </div>
  );
};

// AI narrative generator
const buildNarrative = (report: RiskReportDashboard): string => {
  const topRisk = report.parts.reduce((a, b) => ((a.score ?? 0) > (b.score ?? 0) ? a : b), report.parts[0]);
  const singleSource = report.parts.filter(p => p.reasons.some(r => r.toLowerCase().includes('single'))).length;
  const eolCount = report.parts.filter(p => p.reasons.some(r => r.toLowerCase().includes('eol') || r.toLowerCase().includes('obsolescence'))).length;
  const topScoreLabel = topRisk && topRisk.score != null ? `${(topRisk.score * 100).toFixed(0)}/100` : 'INSUFFICIENT_DATA';

  return `Sentinel's risk engine processed ${report.total_parts} unique line items covering ${report.total_units} total units across this BOM. ` +
    `The overall supply-chain risk posture is rated ${report.overall}${topRisk ? ` — driven primarily by ${topRisk.pn}, which carries the highest individual risk score of ${topScoreLabel}. ` : '. '}` +
    (singleSource > 0 ? `${singleSource} component${singleSource > 1 ? 's' : ''} exhibit single-source exposure, presenting concentration risk. ` : '') +
    (eolCount > 0 ? `${eolCount} part${eolCount > 1 ? 's are' : ' is'} flagged for end-of-life obsolescence risk. ` : '') +
    `Data completeness across all catalog entries stands at ${report.completeness}%, with ${report.low} low-risk passives healthy and dual-sourced.`;
};

// ──────────────────────────────────────────────────────────────────────────────
// Component Card (compact)
// ──────────────────────────────────────────────────────────────────────────────
const ComponentCard: React.FC<{ comp: BOMComponent }> = ({ comp }) => {
  const cfg = BAND_CONFIG[comp.band] ?? BAND_CONFIG.LOW;
  return (
    <div className={`glass-card p-4 rounded-2xl border ${cfg.border} space-y-3`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className={`text-[10px] font-bold uppercase tracking-widest font-mono ${cfg.text}`}>{cfg.label} Risk</p>
          <h4 className="text-sm font-extrabold font-mono text-[var(--text-primary)] truncate">{comp.pn}</h4>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">{comp.ref} · Qty {comp.qty}</p>
        </div>
        <RiskGauge score={comp.score} band={comp.band} />
      </div>

      {/* Score bars */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[10px] text-[var(--text-muted)] font-mono">
          <span>Exposure</span><span>{comp.exp != null ? `${(comp.exp * 100).toFixed(0)}%` : '—'}</span>
        </div>
        <RiskBar value={comp.exp} band={comp.band} />
        <div className="flex items-center justify-between text-[10px] text-[var(--text-muted)] font-mono">
          <span>Confidence</span><span>{(comp.conf * 100).toFixed(0)}%</span>
        </div>
        <div className="h-1.5 w-full bg-[var(--bg-elevated)] rounded-full overflow-hidden">
          <div className="h-full rounded-full bg-[var(--accent-blue)]"
            style={{ width: `${Math.min(comp.conf * 100, 100)}%` }} />
        </div>
      </div>

      {/* Top trigger */}
      {comp.reasons.length > 0 && (
        <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed line-clamp-2">
          ⚑ {comp.reasons[0]}
        </p>
      )}
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────────
// Main Page
// ──────────────────────────────────────────────────────────────────────────────
export const ReportDownloadPage: React.FC<ReportDownloadPageProps> = ({ report, approvedSubstitutes = {} }) => {
  const [incVendorQuotes, setIncVendorQuotes] = useState(true);
  const [incHardwareTwin, setIncHardwareTwin] = useState(true);

  const triggerDownloadAnimation = () => {
    confetti({ particleCount: 80, spread: 70, origin: { y: 0.6 } });
  };

  const handlePrintPdf = () => {
    triggerDownloadAnimation();
    setTimeout(() => window.print(), 300);
  };

  const handleDownloadJson = () => {
    triggerDownloadAnimation();
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(report || {}, null, 2));
    const a = document.createElement('a');
    a.href = dataStr;
    a.download = `Sentinel_Report_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a); a.click(); a.remove();
  };

  const handleDownloadCsv = () => {
    triggerDownloadAnimation();
    if (!report?.parts) return;
    let csv = "data:text/csv;charset=utf-8,Part Number,Reference,Qty,Risk Band,Score,Exposure,Top Trigger\n";
    report.parts.forEach(p => {
      const s = p.score != null ? p.score.toFixed(3) : 'INSUFFICIENT_DATA';
      const e = p.exp != null ? p.exp.toFixed(3) : 'INSUFFICIENT_DATA';
      csv += `"${p.pn}","${p.ref}",${p.qty},"${p.band}",${s},${e},"${p.reasons[0] ?? ''}"\n`;
    });
    const a = document.createElement("a");
    a.href = encodeURI(csv);
    a.download = `Sentinel_Audit_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
  };

  const handleDownloadEngineeringAuditJson = async () => {
    try {
      const res = await fetch(`${SUBSTITUTE_API_BASE}/api/reports/full-engineering-audit`);
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ps5_engineering_audit_report_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('Failed to download full engineering audit:', err);
    }
  };

  if (!report) {
    return (
      <div className="h-64 flex flex-col items-center justify-center glass-panel rounded-3xl gap-3 text-center">
        <AlertCircle className="w-10 h-10 text-[var(--text-muted)]" />
        <p className="text-sm text-[var(--text-muted)]">No BOM loaded — upload or select a sample project first.</p>
      </div>
    );
  }

  const overallGradient = OVERALL_GRADIENT[report.overall] ?? OVERALL_GRADIENT.LOW;
  const overallGlow = OVERALL_GLOW[report.overall] ?? OVERALL_GLOW.LOW;
  const narrative = buildNarrative(report);

  // Show only components that are CRITICAL / HIGH in the detailed section
  const elevatedParts = report.parts.filter(p => p.band === 'CRITICAL' || p.band === 'HIGH');
const healthyParts  = report.parts.filter(p => p.band === 'MEDIUM' || p.band === 'LOW');

  return (
    <div className="space-y-6 pb-16">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="glass-card p-5 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <Sparkles className="w-4 h-4 text-[var(--accent-gold)]" />
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[var(--accent-gold)]">AI Intelligence Report</span>
          </div>
          <h2 className="text-xl font-extrabold text-[var(--text-primary)]">{report.name}</h2>
          <p className="text-[11px] text-[var(--text-muted)] font-mono mt-0.5">
            Generated {new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={handlePrintPdf}
            className="px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 bg-[var(--accent-gold)] text-white hover:opacity-90 transition-all shadow-lg cursor-pointer">
            <Printer className="w-3.5 h-3.5" /> PDF / Print
          </button>
          <button onClick={handleDownloadEngineeringAuditJson}
            className="px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 bg-[var(--bg-elevated)] text-[var(--accent-gold)] border border-[var(--border-strong)] hover:border-[var(--accent-gold)] transition-all cursor-pointer">
            <Zap className="w-3.5 h-3.5 text-[var(--accent-gold)]" /> PS5 Full Audit
          </button>
          <button onClick={handleDownloadJson}
            className="px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:border-[var(--border-strong)] transition-all cursor-pointer">
            <FileText className="w-3.5 h-3.5 text-blue-400" /> JSON
          </button>
          <button onClick={handleDownloadCsv}
            className="px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 bg-[var(--bg-elevated)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:border-[var(--border-strong)] transition-all cursor-pointer">
            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" /> CSV
          </button>
        </div>
      </div>

      {/* ── Overall Risk Banner ─────────────────────────────────────────── */}
      <div className={`relative overflow-hidden rounded-3xl p-6 bg-gradient-to-br ${overallGradient} shadow-2xl ${overallGlow}`}>
        {/* Ambient glow blob */}
        <div className="absolute -top-10 -right-10 w-48 h-48 rounded-full blur-3xl opacity-30 bg-white" />
        <div className="relative flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-white/90" />
              <span className="text-white/80 text-xs font-mono font-bold uppercase tracking-widest">Overall BOM Risk</span>
            </div>
            <p className="text-4xl font-black text-white tracking-tight">{report.overall}</p>
            <p className="text-white/70 text-xs font-mono">
              Max score {report.max_score != null ? `${(report.max_score * 100).toFixed(0)}/100` : 'INSUFFICIENT_DATA'} · Avg {report.avg_score != null ? `${(report.avg_score * 100).toFixed(0)}/100` : 'INSUFFICIENT_DATA'}
            </p>
          </div>

          {/* Distribution pills */}
          <div className="flex gap-2">
            <BandPill count={report.critical} band="CRITICAL" />
            <BandPill count={report.high}     band="HIGH" />
            <BandPill count={report.medium}   band="MEDIUM" />
            <BandPill count={report.low}      band="LOW" />
          </div>
        </div>
      </div>

      {/* ── KPI Row ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { icon: Cpu,       label: 'Total Parts',    value: `${report.total_parts}`,       sub: 'unique line items' },
          { icon: Activity,  label: 'Data Quality',   value: `${report.completeness}%`,     sub: 'catalog coverage' },
          { icon: TrendingUp,label: 'Avg Risk Score', value: report.avg_score != null ? `${(report.avg_score * 100).toFixed(0)}/100` : 'INSUFFICIENT_DATA', sub: 'across all parts' },
          { icon: Zap,       label: 'Units in BOM',   value: `${report.total_units}`,       sub: 'total component count' },
        ].map(kpi => (
          <div key={kpi.label} className="glass-card p-4 rounded-2xl flex flex-col gap-2">
            <kpi.icon className="w-4 h-4 text-[var(--accent-gold)]" />
            <p className="text-[10px] text-[var(--text-muted)] font-mono uppercase tracking-wide">{kpi.label}</p>
            <p className="text-xl font-extrabold font-mono text-[var(--text-primary)]">{kpi.value}</p>
            <p className="text-[10px] text-[var(--text-muted)]">{kpi.sub}</p>
          </div>
        ))}
      </div>

      {/* ── AI Narrative ────────────────────────────────────────────────── */}
      <div className="glass-card p-5 rounded-2xl border border-[var(--accent-gold)]/20 space-y-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-[var(--accent-gold)]" />
          <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[var(--accent-gold)]">AI Analysis Narrative</span>
        </div>
        <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{narrative}</p>

        {/* Highlight chips */}
        <div className="flex flex-wrap gap-2 pt-1">
          {report.parts.filter(p => p.band === 'CRITICAL' || p.band === 'HIGH').map(p => (
            <span key={`${p.pn}-${p.ref}`}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-[var(--risk-critical)]/10 text-[var(--risk-critical)] border border-[var(--risk-critical)]/20">
              <AlertTriangle className="w-2.5 h-2.5" /> {p.pn}
            </span>
          ))}
          {report.parts.filter(p => p.band === 'LOW').slice(0, 3).map(p => (
            <span key={`${p.pn}-${p.ref}`}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-2.5 h-2.5" /> {p.pn}
            </span>
          ))}
        </div>
      </div>

      {/* ── Elevated Risk Components ─────────────────────────────────────── */}
      {elevatedParts.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-red-400" />
            <h3 className="text-sm font-bold text-[var(--text-primary)]">Components Requiring Action</h3>
            <span className="text-[10px] font-mono text-[var(--text-muted)] ml-auto">{elevatedParts.length} flagged</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {elevatedParts.map(comp => <ComponentCard key={`${comp.pn}-${comp.ref}`} comp={comp} />)}
          </div>
        </div>
      )}

      {/* ── Healthy Components (collapsed list) ─────────────────────────── */}
      {healthyParts.length > 0 && (
        <div className="glass-card p-4 rounded-2xl space-y-2">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-bold text-[var(--text-primary)]">Healthy Components</h3>
            <span className="text-[10px] font-mono text-[var(--text-muted)] ml-auto">{healthyParts.length} parts</span>
          </div>
          {healthyParts.map(comp => {
            const cfg = BAND_CONFIG[comp.band] ?? BAND_CONFIG.LOW;
            return (
              <div key={`${comp.pn}-${comp.ref}`} className="flex items-center gap-3 py-2 border-t border-[var(--border-subtle)] first:border-0">
                <div className={`w-2 h-2 rounded-full ${cfg.bar} shrink-0`} />
                <span className="text-xs font-mono font-bold text-[var(--text-primary)] flex-1">{comp.pn}</span>
                <span className="text-[10px] text-[var(--text-muted)] font-mono">{comp.ref}</span>
                <span className={`text-[10px] font-bold font-mono ${cfg.text} ml-3`}>{comp.score != null ? (comp.score * 100).toFixed(0) : '—'}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* ── AI Substitute Strategy ───────────────────────────────────────── */}
      {incVendorQuotes && (
        <div className="glass-card p-5 rounded-2xl border border-[var(--accent-blue)]/25 space-y-3">
          <div className="flex items-center gap-2">
            <ChevronRight className="w-4 h-4 text-[var(--accent-blue)]" />
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[var(--accent-blue)]">Substitute Strategy</span>
          </div>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            Drop-in replacement candidates are only listed when a substitute search was actually run for this export.
            Missing vendor or engineering evidence remains INSUFFICIENT_DATA.
          </p>
          <div className="flex flex-col gap-2">
            {elevatedParts.slice(0, 2).map(p => (
              <div key={`${p.pn}-${p.ref}`} className="flex items-center gap-3 p-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
                <div className="flex-1">
                  <span className="text-xs font-mono font-bold text-[var(--text-primary)]">{p.pn}</span>
                  <span className="text-[10px] text-[var(--text-muted)] ml-2 font-mono">→ {approvedSubstitutes?.[p.pn] ? `approved ${approvedSubstitutes[p.pn]}` : 'substitute search not included in this export'}</span>
                </div>
                <span className="text-[10px] text-[var(--accent-blue)] font-mono font-semibold">View in Component Detail →</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Hardware Twin Log ────────────────────────────────────────────── */}
      {incHardwareTwin && (
        <div className="glass-card p-5 rounded-2xl space-y-3">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-[var(--accent-emerald)]" />
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[var(--accent-emerald)]">ESP32 Hardware Mirror · Telemetry</span>
          </div>
          <div className="bg-[var(--bg-elevated)] rounded-xl p-4 font-mono text-[11px] space-y-1.5 border border-[var(--border-subtle)]">
            {[
              { badge: 'NOTE', msg: 'Hardware telemetry was not captured for this export.' },
              { badge: 'SYS',  msg: `${report.total_parts} parts in report · completeness ${report.completeness}%` },
            ].map((row, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="shrink-0 text-[9px] px-1.5 py-0.5 rounded font-bold bg-[var(--border-subtle)] text-[var(--text-muted)]">{row.badge}</span>
                <span className="text-[var(--text-secondary)]">{row.msg}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Report Options ───────────────────────────────────────────────── */}
      <div className="glass-card p-4 rounded-2xl flex flex-wrap items-center gap-4 text-xs text-[var(--text-secondary)]">
        <span className="font-mono font-bold text-[var(--text-primary)] text-[11px]">Include in export:</span>
        {[
          { label: 'Substitute Strategy', state: incVendorQuotes, set: setIncVendorQuotes },
          { label: 'Hardware Mirror Log',  state: incHardwareTwin,  set: setIncHardwareTwin },
        ].map(opt => (
          <label key={opt.label} className="flex items-center gap-2 cursor-pointer select-none">
            <input type="checkbox" checked={opt.state} onChange={e => opt.set(e.target.checked)}
              className="accent-[var(--accent-gold)] w-3.5 h-3.5" />
            <span className="text-[11px]">{opt.label}</span>
          </label>
        ))}
        <button onClick={handlePrintPdf}
          className="ml-auto px-4 py-1.5 rounded-xl text-[11px] font-bold flex items-center gap-1.5 bg-[var(--accent-gold)] text-white hover:opacity-90 transition-all cursor-pointer shadow">
          <Download className="w-3 h-3" /> Export Report
        </button>
      </div>
    </div>
  );
};
