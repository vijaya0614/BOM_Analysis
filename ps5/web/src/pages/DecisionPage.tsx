import React, { useEffect, useState } from 'react';
import { AlertTriangle, ArrowLeft, CircuitBoard, Database, LoaderCircle, ShieldAlert, XCircle } from 'lucide-react';
import { SUBSTITUTE_API_BASE } from '../api';
import type { CandidateDecision, CandidateDecisionResponse, DecisionPathEdge } from '../types';

interface DecisionPageProps {
  productId: string;
  componentId: string;
  onBack: () => void;
}

const missing = (value: unknown) => value == null || value === '' || value === 'UNKNOWN' || value === 'INSUFFICIENT_DATA';
const text = (value: unknown) => missing(value) ? 'INSUFFICIENT_DATA' : String(value);
const tone = (status: unknown) => {
  const value = String(status || 'INSUFFICIENT_DATA').toUpperCase();
  if (value === 'PASS' || value === 'FOUND' || value === 'FEASIBLE' || value === 'HIGH') return 'var(--risk-low)';
  if (value.includes('FAIL') || value === 'INCOMPATIBLE') return 'var(--risk-critical)';
  if (value.includes('WARNING') || value.includes('REDESIGN') || value === 'LIMITED') return 'var(--risk-high)';
  return 'var(--text-muted)';
};

const StatusBadge: React.FC<{ value: unknown }> = ({ value }) => {
  const label = text(value);
  const color = tone(label);
  return <span className="px-2.5 py-1 rounded-full text-[10px] font-bold border" style={{ color, background: `color-mix(in oklab, ${color} 12%, var(--bg-card))`, borderColor: `color-mix(in oklab, ${color} 35%, transparent)` }}>{label.replace(/_/g, ' ')}</span>;
};

const Field: React.FC<{ label: string; value: unknown }> = ({ label, value }) => (
  <div className="flex justify-between items-start gap-4 py-2 border-b border-[var(--border-subtle)] last:border-0">
    <span className="text-[11px] text-[var(--text-muted)] font-mono">{label}</span><span className="text-xs text-right font-semibold text-[var(--text-primary)]">{text(value)}</span>
  </div>
);

const EdgeEvidence: React.FC<{ edge: DecisionPathEdge }> = ({ edge }) => (
  <div className="p-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-xs space-y-1.5">
    <div className="flex justify-between gap-3"><strong>{text(edge.relationship_type)}</strong><StatusBadge value={edge.confidence} /></div>
    {edge.function && <p className="text-[var(--text-secondary)]">{edge.function}</p>}
    {edge.source && <p className="font-mono text-[10px] text-[var(--text-muted)]">Source: {edge.source}</p>}
  </div>
);

export const DecisionPage: React.FC<DecisionPageProps> = ({ productId, componentId, onBack }) => {
  const [decision, setDecision] = useState<CandidateDecisionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(null); setDecision(null);
    fetch(`${SUBSTITUTE_API_BASE}/decision/${encodeURIComponent(productId)}/${encodeURIComponent(componentId)}`, { signal: controller.signal })
      .then(async response => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.message || body.error || `Decision API returned ${response.status}.`);
        setDecision(body as CandidateDecisionResponse);
      })
      .catch(cause => { if (cause.name !== 'AbortError') setError(cause instanceof Error ? cause.message : 'Unable to load decision.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [productId, componentId]);

  if (loading) return <div className="glass-card p-10 rounded-2xl text-center text-xs text-[var(--text-muted)]"><LoaderCircle className="w-5 h-5 animate-spin mx-auto mb-3 text-[var(--accent-gold)]" />Loading engineering decision…</div>;
  if (error) return <div className="glass-card p-8 rounded-2xl"><div className="flex gap-3"><XCircle className="text-[var(--risk-critical)] shrink-0" /><div><h1 className="font-bold">Decision unavailable</h1><p className="mt-1 text-sm text-[var(--text-muted)]">{error}</p><button onClick={onBack} className="mt-4 text-xs font-bold text-[var(--accent-gold)] cursor-pointer">Back to component</button></div></div></div>;
  if (!decision) return null;
  const candidate: CandidateDecision | undefined = decision.candidates[0];
  const generated = candidate?.candidate_generation;
  const original = decision.candidate_generation.original;
  const compatibility = generated?.compatibility_score;
  const checks = generated?.checks || [];
  const impact = candidate?.downstream_impact;

  return <div className="space-y-5 pb-8">
    <button onClick={onBack} className="flex items-center gap-2 text-xs font-bold text-[var(--text-muted)] hover:text-[var(--accent-gold)] cursor-pointer"><ArrowLeft className="w-4 h-4" />Back to component</button>
    <section className="glass-card p-6 sm:p-8 rounded-2xl overflow-hidden relative">
      <div className="absolute inset-y-0 left-0 w-1" style={{ background: tone(candidate?.overall_status || decision.status) }} />
      <div className="flex flex-col lg:flex-row justify-between gap-6">
        <div><span className="text-[10px] font-mono uppercase tracking-widest text-[var(--accent-gold)]">Engineering decision</span><h1 className="mt-1 text-2xl font-black">{original?.part_number || componentId} <span className="text-[var(--text-muted)]">→</span> {candidate?.candidate_part_number || 'No feasible candidate'}</h1><p className="mt-2 text-sm text-[var(--text-secondary)]">{productId} · {componentId} · {text(original?.category)}</p></div>
        <div className="flex flex-wrap items-start gap-2"><StatusBadge value={candidate?.overall_status || decision.status} /><StatusBadge value={candidate?.classification} /><StatusBadge value={decision.risk_trigger.status} /></div>
      </div>
      <p className="mt-5 text-sm text-[var(--text-secondary)]">Hard engineering constraints are evaluated before vendor and ranking factors. This result retains unavailable evidence as insufficient data.</p>
    </section>

    {!candidate ? <section className="glass-card p-8 rounded-2xl text-center"><ShieldAlert className="mx-auto text-[var(--risk-high)]" /><h2 className="mt-3 font-bold">No feasible candidate decision</h2><p className="mt-1 text-sm text-[var(--text-muted)]">{decision.reason_codes?.join(', ') || 'No candidates were returned by the decision service.'}</p></section> : <>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <section className="glass-card p-6 rounded-2xl xl:col-span-1"><span className="text-[10px] font-mono uppercase tracking-widest text-[var(--accent-gold)]">Selected candidate</span><h2 className="mt-1 text-lg font-black">{candidate.candidate_part_number}</h2><div className="mt-4"><Field label="Candidate ID" value={candidate.candidate_id} /><Field label="Manufacturer" value={generated?.component?.manufacturer} /><Field label="Package" value={generated?.component?.package} /><Field label="Compatibility" value={compatibility == null ? undefined : `${compatibility} / ${generated?.confidence_score ?? 'INSUFFICIENT_DATA'}`} /><Field label="Vendor feasibility" value={candidate.vendor_status} /><Field label="Geographic fit" value={candidate.vendor_gate.regional_fit} /><Field label="Verified sources" value={candidate.vendor_gate.source_count} /><Field label="Best lead time" value={candidate.vendor_gate.best_lead_time} /><Field label="Reliability outlook" value={candidate.reliability_outlook.outcome} /></div></section>
        <section className="glass-card p-6 rounded-2xl xl:col-span-2"><div className="flex justify-between gap-4"><div><span className="text-[10px] font-mono uppercase tracking-widest text-[var(--accent-gold)]">Why this decision?</span><h2 className="mt-1 text-lg font-black">Auditable candidate reasoning</h2></div><StatusBadge value={candidate.rank == null ? 'ELIMINATED' : `RANK ${candidate.rank}`} /></div><div className="mt-5 grid sm:grid-cols-2 gap-3">{candidate.reason_codes.map(reason => <div key={reason} className="flex gap-2 p-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-xs"><AlertTriangle className="w-4 h-4 shrink-0" style={{ color: tone(reason) }} /><span>{reason.replace(/_/g, ' ')}</span></div>)}</div>{candidate.hard_gate_failures.length > 0 && <p className="mt-4 text-xs text-[var(--risk-critical)]">Hard-gate failures: {candidate.hard_gate_failures.join(', ')}</p>}</section>
      </div>

      <section className="glass-card p-6 rounded-2xl"><div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><span className="text-[10px] font-mono uppercase tracking-widest text-[var(--accent-gold)]">Compatibility and specification evidence</span><h2 className="mt-1 text-lg font-black">{compatibility ?? 'INSUFFICIENT_DATA'} / {generated?.confidence_score ?? 'INSUFFICIENT_DATA'}</h2></div><StatusBadge value={candidate.classification} /></div><div className="mt-5 grid md:grid-cols-2 gap-3">{checks.map(check => <div key={check.parameter} className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)]"><div className="flex justify-between gap-3"><strong className="text-sm">{check.parameter.replace(/_/g, ' ')}</strong><StatusBadge value={check.status} /></div><p className="mt-2 text-xs text-[var(--text-secondary)]">Original: {text(check.original)} · Candidate: {text(check.candidate)}</p></div>)}</div>{checks.length === 0 && <p className="mt-4 text-sm text-[var(--text-muted)]">No verified compatibility checks were returned.</p>}</section>

      <section className="glass-card p-6 rounded-2xl"><span className="text-[10px] font-mono uppercase tracking-widest text-[var(--accent-gold)]">Engineering gates</span><h2 className="mt-1 text-lg font-black">Limits and tolerance</h2><div className="mt-4 grid md:grid-cols-3 gap-3">{candidate.engineering_gates.map(gate => <div key={gate.parameter} className="p-4 rounded-xl border border-[var(--border-subtle)]"><div className="flex justify-between gap-2"><strong className="text-xs">{gate.parameter.replace(/_/g, ' ')}</strong><StatusBadge value={gate.status} /></div><p className="mt-2 text-xs text-[var(--text-muted)]">{gate.reason.replace(/_/g, ' ')}</p></div>)}</div></section>

      <section className="glass-card p-6 rounded-2xl"><div className="flex justify-between gap-4"><div><span className="text-[10px] font-mono uppercase tracking-widest text-[var(--accent-gold)]">Dependency impact</span><h2 className="mt-1 text-lg font-black">{impact?.data.length || 0} affected graph paths</h2></div><StatusBadge value={impact?.status} /></div>{impact?.data.length ? <div className="mt-5 space-y-3">{impact.data.map((node, index) => <div key={`${node.node_id}-${index}`} className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)]"><div className="flex items-center gap-2"><CircuitBoard className="w-4 h-4 text-[var(--accent-blue)]" /><strong className="text-sm">{node.path.join(' → ')}</strong></div><div className="mt-3 grid lg:grid-cols-2 gap-3">{node.path_edges?.map((edge, edgeIndex) => <EdgeEvidence key={edgeIndex} edge={edge} />)}</div></div>)}</div> : <p className="mt-4 text-sm text-[var(--text-muted)]">{impact?.limitations?.join(' ') || 'No dependency paths are available.'}</p>}</section>

      <section className="glass-card p-6 rounded-2xl"><div className="flex items-center gap-2"><Database className="w-4 h-4 text-[var(--accent-gold)]" /><div><span className="text-[10px] font-mono uppercase tracking-widest text-[var(--accent-gold)]">Evidence and data quality</span><h2 className="text-lg font-black">Reliability and source limitations</h2></div></div><div className="mt-4 grid md:grid-cols-2 gap-3"><div className="p-4 rounded-xl border border-[var(--border-subtle)]"><Field label="Reliability outcome" value={candidate.reliability_outlook.outcome} /><Field label="Confidence" value={candidate.reliability_outlook.confidence} /><p className="mt-3 text-xs text-[var(--text-muted)]">{candidate.reliability_outlook.reason || 'No reliability conclusion was returned.'}</p></div><div className="p-4 rounded-xl border border-[var(--border-subtle)]"><p className="text-xs font-bold">Known limitations</p><ul className="mt-2 space-y-2 text-xs text-[var(--text-muted)]">{(candidate.reliability_outlook.limitations || []).map(item => <li key={item}>• {item}</li>)}{(impact?.limitations || []).map(item => <li key={item}>• {item}</li>)}</ul></div></div></section>
    </>}
  </div>;
};
