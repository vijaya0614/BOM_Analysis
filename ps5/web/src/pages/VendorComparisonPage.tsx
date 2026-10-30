import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { BOMComponent, EnrichmentRunResult, IndustryComponentData, ProviderHealth } from '../types';
import { RiskBadge } from '../components/primitives';
import type { RiskBand } from '../components/primitives';
import { bandHex } from '../utils/riskUtils';
import { Building2, Filter, Package, Clock, DollarSign, ShieldCheck, Truck, RefreshCw, Database, Upload } from 'lucide-react';
import { motion } from 'framer-motion';
import { SENTINEL_API_BASE } from '../api';

interface VendorComparisonPageProps {
  components: BOMComponent[];
  onNavigateToUpload?: () => void;
  onDataUpdated?: () => void;
}
type Sort = 'Lead time' | 'Price' | 'Stock';
type AvailablePart = { mpn: string; label: string; component?: BOMComponent };
type DemoVendorIntelligence = {
  part_number: string;
  manufacturer: string;
  description: string;
  data_source: 'CURATED_STATIC_DEMO_DATA' | 'SYNTHETIC_DEMO_DATA';
  vendor_records: Array<{
    vendor_name: string;
    stock_quantity: number;
    lead_time_days: number;
    unit_price: number;
    currency: string;
    authorized: boolean | null;
    data_provenance: string;
  }>;
};

const numeric = (value: string) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};
const shown = (value: string, suffix = '') => value === '' ? 'UNKNOWN' : `${value}${suffix}`;
const providerLabel = (name: string, health?: ProviderHealth) => {
  if (!health?.configured) return `${name}: NOT CONFIGURED`;
  if (health.product_access_ready === false) return `${name}: ACCOUNT ID REQUIRED`;
  if (health.last_error) return `${name}: ERROR · ${health.last_error}`;
  if (health.last_success) return `${name}: CONNECTED`;
  return `${name}: READY TO QUERY`;
};

export const VendorComparisonPage: React.FC<VendorComparisonPageProps> = ({ components, onNavigateToUpload, onDataUpdated }) => {
  const [selectedPn, setSelectedPn] = useState('');
  const [activeSort, setActiveSort] = useState<Sort>('Lead time');
  const [expandedVendorId, setExpandedVendorId] = useState<string | null>(null);
  const [industryData, setIndustryData] = useState<IndustryComponentData | null>(null);
  const [demoData, setDemoData] = useState<DemoVendorIntelligence | null>(null);
  const [providers, setProviders] = useState<Record<string, ProviderHealth>>({});
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState<EnrichmentRunResult | null>(null);

  const availableParts = useMemo<AvailablePart[]>(() => {
    const byMpn = new Map<string, AvailablePart>();
    components.forEach(component => byMpn.set(component.pn, { mpn: component.pn, label: `${component.pn} · active BOM`, component }));
    return [...byMpn.values()].sort((a, b) => a.mpn.localeCompare(b.mpn));
  }, [components]);
  const selectedPart = availableParts.find(part => part.mpn === selectedPn);
  const selectedComponent = selectedPart?.component;
  const band = selectedComponent?.band as RiskBand | undefined;
  const color = band ? bandHex(band) : 'var(--accent-blue)';

  const loadVendorData = useCallback(async (mpn: string) => {
    if (!mpn) return;
    setLoading(true); setIndustryData(null); setDemoData(null); setExpandedVendorId(null);
    try {
      const [liveResponse, demoResponse] = await Promise.all([
        fetch(`${SENTINEL_API_BASE}/api/industry/component/${encodeURIComponent(mpn)}`),
        fetch(`${SENTINEL_API_BASE}/api/vendor/intelligence/${encodeURIComponent(mpn)}`),
      ]);
      setIndustryData(liveResponse.ok ? await liveResponse.json() : null);
      setDemoData(demoResponse.ok ? await demoResponse.json() : null);
    } catch { setIndustryData(null); setDemoData(null); } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetch(`${SENTINEL_API_BASE}/api/industry/providers`)
      .then(response => response.ok ? response.json() : {})
      .then(setProviders)
      .catch(() => setProviders({}));
  }, []);
  useEffect(() => {
    if (availableParts.length && !availableParts.some(part => part.mpn === selectedPn)) setSelectedPn(availableParts[0].mpn);
  }, [availableParts, selectedPn]);
  useEffect(() => { if (selectedPn) void loadVendorData(selectedPn); }, [selectedPn, loadVendorData]);

  const refreshVerifiedData = async () => {
    if (!selectedPn) return;
    setRefreshing(true); setRefreshResult(null);
    try {
      const response = await fetch(`${SENTINEL_API_BASE}/api/enrichment/run`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mpns: [selectedPn], providers: ['digikey', 'nexar', 'mouser'], region: 'IN', force_refresh: true }),
      });
      const payload = await response.json();
      setRefreshResult(payload);
      await loadVendorData(selectedPn);
      onDataUpdated?.();
    } catch {
      setRefreshResult({ resolved: 0, unresolved: 1, cache_hits: 0, api_calls: 0, errors: 1, digikey_matches: 0, nexar_matches: 0, vendor_records: 0, failed: [{ mpn: selectedPn, provider: 'SENTINEL', error: 'REQUEST_FAILED' }] });
    } finally { setRefreshing(false); }
  };

  const vendors = useMemo(() => [...(industryData?.vendor_records || [])].sort((left, right) => {
    const a = activeSort === 'Stock' ? numeric(left.stock_quantity) : activeSort === 'Price' ? numeric(left.unit_price) : numeric(left.lead_time_days);
    const b = activeSort === 'Stock' ? numeric(right.stock_quantity) : activeSort === 'Price' ? numeric(right.unit_price) : numeric(right.lead_time_days);
    if (a === null && b === null) return 0; if (a === null) return 1; if (b === null) return -1;
    return activeSort === 'Stock' ? b - a : a - b;
  }), [activeSort, industryData]);
  const sortButtons: Sort[] = ['Lead time', 'Price', 'Stock'];
  const demoVendors = useMemo(() => [...(demoData?.vendor_records || [])].sort((left, right) => {
    const a = activeSort === 'Stock' ? left.stock_quantity : activeSort === 'Price' ? left.unit_price : left.lead_time_days;
    const b = activeSort === 'Stock' ? right.stock_quantity : activeSort === 'Price' ? right.unit_price : right.lead_time_days;
    return activeSort === 'Stock' ? b - a : a - b;
  }), [activeSort, demoData]);
  const providerFailure = refreshResult?.failed?.map(item => `${item.provider}: ${item.error}`).join(' · ');

  if (availableParts.length === 0) return <div className="glass-card p-7 rounded-2xl flex items-start gap-3"><Upload className="w-5 h-5 shrink-0 text-[var(--accent-blue)]" /><div><h3 className="text-sm font-bold text-[var(--text-primary)]">No normalized components available</h3><p className="text-xs text-[var(--text-muted)] mt-1">Upload a BOM or industry package first. SENTINEL will normalize real MPNs before any provider lookup.</p>{onNavigateToUpload && <button onClick={onNavigateToUpload} className="mt-3 text-xs font-bold text-[var(--accent-gold)]">Open BOM Materials →</button>}</div></div>;

  return <div className="space-y-6 pb-12">
    <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="space-y-1">
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-[10px] font-black font-mono tracking-widest uppercase border" style={{ color: 'var(--accent-gold)', borderColor: 'color-mix(in oklab, var(--accent-gold) 30%, transparent)', background: 'color-mix(in oklab, var(--accent-gold) 10%, var(--bg-elevated))' }}><Building2 className="w-3 h-3" /> Procurement Intelligence</div>
      <h2 className="text-2xl font-black tracking-tight text-[var(--text-primary)]">Vendor & Distributor Comparison</h2>
      <p className="text-xs text-[var(--text-secondary)]">Compare a part from the active BOM. Live provider offers and illustrative demo catalog values are shown in separate sections.</p>
    </motion.div>

    <div className="glass-card p-4 rounded-2xl flex flex-wrap items-center gap-2 text-[10px] font-mono"><Database className="w-4 h-4 text-[var(--accent-blue)]" /><span className="font-bold text-[var(--text-primary)]">LIVE PROVIDER STATUS</span>{['digikey', 'nexar', 'mouser'].map(name => { const health = providers[name]; const tone = health?.last_error ? 'var(--risk-high)' : health?.last_success ? 'var(--risk-low)' : 'var(--text-muted)'; return <span key={name} className="px-2.5 py-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]" style={{ color: tone }}>● {providerLabel(name.toUpperCase(), health)}</span>; })}</div>

    <div className="glass-card p-5 rounded-2xl flex flex-col xl:flex-row items-start xl:items-center justify-between gap-4" style={{ borderLeft: `3px solid ${color}` }}>
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3"><label className="text-xs font-bold text-[var(--text-muted)] font-mono shrink-0">ACTIVE BOM PART:</label><select value={selectedPn} onChange={event => setSelectedPn(event.target.value)} className="max-w-[min(100%,38rem)] px-3.5 py-2 rounded-xl text-xs font-mono font-bold text-[var(--text-primary)] outline-none cursor-pointer border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-strong)' }}>{availableParts.map(part => <option key={part.mpn} value={part.mpn}>{part.label}</option>)}</select></div>
      <div className="flex items-center gap-2 flex-wrap">{band && selectedComponent && <RiskBadge band={band} score={typeof selectedComponent.score === 'number' ? Math.round(selectedComponent.score * 100) : undefined} />}<span className="text-[10px] font-mono px-2.5 py-1 rounded-xl border" style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border-subtle)', color: industryData?.data_source === 'REAL_DISTRIBUTOR_DATA' ? 'var(--risk-low)' : 'var(--text-muted)' }}>{industryData?.data_source === 'REAL_DISTRIBUTOR_DATA' ? 'REAL DISTRIBUTOR DATA' : 'NO VERIFIED OFFER'}</span><button type="button" onClick={refreshVerifiedData} disabled={refreshing} className="px-3 py-2 rounded-xl text-[10px] font-black text-white flex items-center gap-1.5 disabled:opacity-50" style={{ background: 'var(--gradient-brand)' }}><RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} /> {refreshing ? 'Refreshing…' : refreshResult ? 'Updated — refresh again' : 'Refresh Live Data'}</button></div>
    </div>

    {refreshResult && <div className="glass-card p-4 rounded-2xl text-xs"><p className="font-bold text-[var(--text-primary)]">{(refreshResult.vendor_records || refreshResult.mouser_matches || refreshResult.resolved) ? `Updated ${refreshResult.timestamp || ''}` : refreshResult.errors ? 'Refresh failed — details below' : `Updated ${refreshResult.timestamp || ''}`}: {refreshResult.resolved} resolved, {refreshResult.vendor_records} verified offers, {refreshResult.cache_hits} cache hits.</p>{providerFailure ? <p className="mt-1 text-[var(--risk-high)] font-mono text-[10px]">Provider response: {providerFailure}</p> : <p className="mt-1 text-[var(--text-muted)] text-[10px]">Only returned provider evidence is displayed below.</p>}</div>}

    <div className="flex items-center gap-2 flex-wrap"><span className="text-xs text-[var(--text-muted)] font-mono flex items-center gap-1"><Filter className="w-3.5 h-3.5" /> Sort by:</span>{sortButtons.map(tab => <motion.button key={tab} whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }} onClick={() => setActiveSort(tab)} className="px-3 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-all border" style={activeSort === tab ? { background: 'var(--gradient-brand)', color: '#fff', border: 'none' } : { background: 'var(--bg-surface)', color: 'var(--text-secondary)', borderColor: 'var(--border-subtle)' }}>{tab}</motion.button>)}<span className="ml-auto text-[10px] font-mono text-[var(--text-muted)]">{vendors.length} verified records</span></div>

    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3"><h3 className="text-sm font-bold text-[var(--text-primary)]">Live provider offers</h3><span className="text-[10px] font-mono text-[var(--text-muted)]">{vendors.length} verified records</span></div>
      {loading ? <div className="glass-card p-10 rounded-2xl text-center text-xs text-[var(--text-muted)]"><div className="animate-spin w-5 h-5 border-2 border-[var(--accent-gold)] border-t-transparent rounded-full mx-auto mb-2" />Checking provider-backed records...</div> : vendors.length === 0 ? <div className="glass-card p-8 rounded-2xl flex items-start gap-3"><Truck className="w-5 h-5 text-[var(--accent-blue)] shrink-0" /><div><h3 className="text-sm font-bold text-[var(--text-primary)]">No verified provider offer for {selectedPn}</h3><p className="text-xs text-[var(--text-muted)] mt-1">Provider accounts may be unconfigured. Refresh live data to query this MPN. No demo estimates are included in live offer results.</p></div></div> : <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{vendors.map((vendor, index) => {
      const id = `${vendor.vendor_name}-${vendor.vendor_part_number}-${index}`; const expanded = expandedVendorId === id;
      return <motion.div key={id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.06 }} whileHover={{ y: -2 }} onClick={() => setExpandedVendorId(expanded ? null : id)} className="glass-card p-5 rounded-2xl cursor-pointer space-y-4 relative overflow-hidden">
        <div className="flex items-center justify-between gap-2"><div><h4 className="font-black text-sm text-[var(--text-primary)] font-mono">{vendor.vendor_name || 'Unknown distributor'}</h4><p className="text-[10px] font-mono text-[var(--text-muted)] mt-1">{vendor.provider?.toUpperCase() || 'UNKNOWN PROVIDER'}</p></div><div className="flex flex-col items-end gap-1"><span className="text-[10px] font-mono px-2 py-0.5 rounded-md border text-[var(--text-muted)] border-[var(--border-subtle)] bg-[var(--bg-elevated)]">{vendor.region || 'UNKNOWN'}</span><span className="text-[9px] font-black" style={{ color: vendor.retrieval_state === 'LIVE' ? 'var(--risk-low)' : vendor.retrieval_state === 'STALE' ? 'var(--risk-high)' : 'var(--text-muted)' }}>{vendor.retrieval_state || 'UNKNOWN'}</span></div></div>
        <div className="grid grid-cols-2 gap-3 text-xs">{[[Package, 'Stock', shown(vendor.stock_quantity), numeric(vendor.stock_quantity) == null ? 'var(--text-muted)' : numeric(vendor.stock_quantity)! > 0 ? 'var(--risk-low)' : 'var(--risk-high)'], [Clock, 'Lead time', shown(vendor.lead_time_days, 'd'), 'var(--text-primary)'], [DollarSign, 'Unit price', vendor.unit_price ? `${vendor.currency || ''} ${vendor.unit_price}` : 'UNKNOWN', 'var(--text-primary)'], [ShieldCheck, 'Authorized', vendor.authorized === 'True' ? 'YES' : vendor.authorized === 'False' ? 'NO' : 'UNKNOWN', 'var(--text-primary)']].map(([Icon, label, value, itemColor]) => { const ItemIcon = Icon as typeof Package; return <div key={label as string} className="p-2 rounded-lg bg-[var(--bg-elevated)]"><p className="text-[10px] text-[var(--text-muted)] font-mono flex items-center gap-1"><ItemIcon className="w-3 h-3" />{label as string}</p><p className="font-black font-mono text-sm mt-1" style={{ color: itemColor as string }}>{value as string}</p></div>; })}</div>
        {expanded && <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="border-t pt-3 space-y-2 text-[10px] font-mono text-[var(--text-secondary)] border-[var(--border-subtle)]"><div className="flex justify-between gap-2"><span>Vendor part number</span><strong className="text-right text-[var(--text-primary)]">{shown(vendor.vendor_part_number)}</strong></div><div className="flex justify-between gap-2"><span>Retrieved</span><strong className="text-right text-[var(--text-primary)]">{shown(vendor.retrieved_at || vendor.last_updated)}</strong></div><div className="flex justify-between gap-2"><span>Expires</span><strong className="text-right text-[var(--text-primary)]">{shown(vendor.expires_at || '')}</strong></div><div className="flex justify-between gap-2"><span>Provenance</span><strong className="text-right text-[var(--text-primary)]">{shown(vendor.data_provenance)}</strong></div></motion.div>}
      </motion.div>;
    })}</div>}
    </section>

    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="text-sm font-bold text-[var(--text-primary)]">Illustrative demo comparison · {demoData?.manufacturer || selectedPn}</h3><p className="text-[10px] text-[var(--text-muted)] mt-1">{demoData?.description || selectedPn}</p></div><span className="text-[10px] font-black font-mono px-2.5 py-1 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-300">{demoData?.data_source === 'CURATED_STATIC_DEMO_DATA' ? 'CURATED STATIC DEMO' : demoData?.data_source === 'SYNTHETIC_DEMO_DATA' ? 'SYNTHETIC DEMO · NOT LIVE' : 'DEMO VALUES UNAVAILABLE'}</span></div>
      <p className="text-[10px] text-[var(--text-muted)]">Illustrative comparison values only. They are not provider quotes, current stock, or purchasing guidance.</p>
      {loading ? <div className="glass-card p-8 rounded-2xl text-center text-xs text-[var(--text-muted)]">Loading clearly labeled demo comparison…</div> : demoVendors.length === 0 ? <div className="glass-card p-8 rounded-2xl text-xs text-[var(--text-muted)]">No demo comparison is available for this part.</div> : <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{demoVendors.map(vendor => <div key={vendor.vendor_name} className="glass-card p-5 rounded-2xl space-y-3"><div className="flex items-center justify-between gap-2"><h4 className="font-bold text-sm text-[var(--text-primary)]">{vendor.vendor_name}</h4><span className="text-[9px] font-black text-amber-300">DEMO</span></div><div className="grid grid-cols-3 gap-2 text-[10px]"><div><p className="text-[var(--text-muted)]">Stock</p><strong>{vendor.stock_quantity.toLocaleString()}</strong></div><div><p className="text-[var(--text-muted)]">Lead time</p><strong>{vendor.lead_time_days}d</strong></div><div><p className="text-[var(--text-muted)]">Unit price</p><strong>{vendor.currency} {vendor.unit_price}</strong></div></div><p className="text-[9px] text-[var(--text-muted)]">{vendor.data_provenance.replaceAll('_', ' ')}</p></div>)}</div>}
    </section>
  </div>;
};
