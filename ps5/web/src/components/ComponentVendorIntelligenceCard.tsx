import React, { useState } from 'react';
import {
  Globe, Truck, ShieldAlert, ShieldCheck, DollarSign,
  Layers, MapPin, Database, Award, ArrowUpRight
} from 'lucide-react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip,
  AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid
} from 'recharts';
import type { ComponentVendorIntelligence } from '../types';

interface Props {
  intelligence: ComponentVendorIntelligence;
}

const DISTRIBUTOR_COLORS: Record<string, string> = {
  'Digi-Key': '#DC2626',
  'Digi-Key Electronics': '#DC2626',
  'Mouser': '#2563EB',
  'Mouser Electronics': '#2563EB',
  'Arrow': '#F59E0B',
  'Arrow Electronics': '#F59E0B',
  'Avnet': '#10B981',
  'Farnell': '#8B5CF6',
  'Farnell / Newark': '#8B5CF6',
  'LCSC': '#06B6D4',
  'LCSC Electronics': '#06B6D4',
};

export const ComponentVendorIntelligenceCard: React.FC<Props> = ({ intelligence }) => {
  const [activeTab, setActiveTab] = useState<'distributors' | 'geology' | 'trends' | 'pricing'>('distributors');

  const { geological, market_saturation, part_number, manufacturer } = intelligence;

  // Pie chart data
  const pieData = market_saturation.distributors.map((d) => ({
    name: d.vendor_name,
    value: d.stock,
    share: d.stock_share_pct,
    color: DISTRIBUTOR_COLORS[d.vendor_name] || '#6366F1',
    price: d.unit_price,
    lead: d.lead_time_weeks,
    moq: d.moq,
  }));

  const totalStock = market_saturation.distributors.reduce((acc, curr) => acc + curr.stock, 0);

  const getGeoRiskColor = (tier: string) => {
    switch (tier) {
      case 'LOW': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
      case 'MODERATE': return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
      case 'ELEVATED':
      case 'CRITICAL': return 'text-rose-400 bg-rose-500/10 border-rose-500/30';
      default: return 'text-[var(--text-secondary)] bg-[var(--bg-elevated)] border-[var(--border-subtle)]';
    }
  };

  const getSaturationLabel = (sat: number) => {
    if (sat >= 75) return { label: 'HIGH SATURATION (ABUNDANT)', color: 'text-emerald-400' };
    if (sat >= 40) return { label: 'BALANCED SUPPLY', color: 'text-blue-400' };
    if (sat >= 20) return { label: 'SUPPLY PRESSURE / TIGHT', color: 'text-amber-400' };
    return { label: 'CRITICAL SUPPLY SHORTAGE', color: 'text-rose-400' };
  };

  const satLabel = getSaturationLabel(market_saturation.saturation_index_pct);

  return (
    <div className="glass-card p-6 rounded-2xl space-y-6">
      {/* ── Header ── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
        <div>
          <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest flex items-center gap-1.5">
            <Globe className="w-3.5 h-3.5" /> Global Procurement & Geological Risk
          </span>
          <h3 className="text-lg font-bold text-[var(--text-primary)] font-mono">
            Vendor Ecosystem, Geological Availability & Market Saturation
          </h3>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Real-world authorized distributor inventory, silicon fab location, and multi-sourcing posture for {part_number} ({manufacturer}).
          </p>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-1.5 p-1 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] text-xs font-mono">
          <button
            onClick={() => setActiveTab('distributors')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'distributors' ? 'bg-[var(--accent-gold)] text-black font-bold shadow-sm' : 'text-[var(--text-secondary)] hover:text-white'
            }`}
          >
            Distributors & Stock
          </button>
          <button
            onClick={() => setActiveTab('geology')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'geology' ? 'bg-[var(--accent-gold)] text-black font-bold shadow-sm' : 'text-[var(--text-secondary)] hover:text-white'
            }`}
          >
            Geological & Fab
          </button>
          <button
            onClick={() => setActiveTab('trends')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'trends' ? 'bg-[var(--accent-gold)] text-black font-bold shadow-sm' : 'text-[var(--text-secondary)] hover:text-white'
            }`}
          >
            12M Trends
          </button>
          <button
            onClick={() => setActiveTab('pricing')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'pricing' ? 'bg-[var(--accent-gold)] text-black font-bold shadow-sm' : 'text-[var(--text-secondary)] hover:text-white'
            }`}
          >
            Volume Breaks
          </button>
        </div>
      </div>

      {/* ── Top Level Quick Status Posture ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Saturation */}
        <div className="p-3.5 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] text-[var(--text-muted)] font-mono uppercase flex items-center gap-1">
            <Layers className="w-3 h-3 text-[var(--accent-blue)]" /> Market Saturation
          </span>
          <p className="text-base font-black font-mono text-[var(--text-primary)]">
            {market_saturation.saturation_index_pct.toFixed(1)}%
          </p>
          <p className={`text-[10px] font-bold font-mono ${satLabel.color}`}>
            {satLabel.label}
          </p>
        </div>

        {/* Global Stock */}
        <div className="p-3.5 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] text-[var(--text-muted)] font-mono uppercase flex items-center gap-1">
            <Database className="w-3 h-3 text-emerald-400" /> Authorized Stock Depth
          </span>
          <p className="text-base font-black font-mono text-emerald-400">
            {totalStock.toLocaleString()} units
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            Across 6 primary distributors
          </p>
        </div>

        {/* Sourcing Strategy */}
        <div className="p-3.5 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] text-[var(--text-muted)] font-mono uppercase flex items-center gap-1">
            <Award className="w-3 h-3 text-[var(--accent-gold)]" /> Sourcing Posture
          </span>
          <p className="text-sm font-black font-mono text-[var(--text-primary)] truncate">
            {market_saturation.sourcing_status.replace(/_/g, ' ')}
          </p>
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            HHI: {market_saturation.hhi_index.toFixed(0)} ({market_saturation.hhi_index > 5000 ? 'Concentrated' : 'Diversified'})
          </p>
        </div>

        {/* Geopolitical Risk */}
        <div className="p-3.5 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-1">
          <span className="text-[10px] text-[var(--text-muted)] font-mono uppercase flex items-center gap-1">
            <MapPin className="w-3 h-3 text-rose-400" /> Primary Fab Origin
          </span>
          <p className="text-sm font-black font-mono text-[var(--text-primary)] truncate">
            {geological.primary_fab_country} ({geological.primary_fab_city})
          </p>
          <div className="flex items-center gap-1.5">
            <span className={`px-2 py-0.5 rounded text-[9px] font-bold font-mono border ${getGeoRiskColor(geological.geopolitical_risk_tier)}`}>
              {geological.geopolitical_risk_tier} RISK
            </span>
          </div>
        </div>
      </div>

      {/* ── TAB 1: DISTRIBUTORS & DONUT STOCK CHART ── */}
      {activeTab === 'distributors' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
            {/* Donut Chart */}
            <div className="lg:col-span-5 h-64 relative flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    innerRadius={60}
                    outerRadius={95}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} stroke="var(--bg-card)" strokeWidth={2} />
                    ))}
                  </Pie>
                  <RechartsTooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const d = payload[0].payload;
                        return (
                          <div className="p-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-2xl text-xs font-mono space-y-1">
                            <p className="font-bold text-[var(--text-primary)]">{d.name}</p>
                            <p className="text-emerald-400">Stock: {d.value.toLocaleString()} units ({d.share}%)</p>
                            <p className="text-[var(--text-secondary)]">Price: ${d.price} · MOQ: {d.moq}</p>
                            <p className="text-[var(--text-muted)]">Lead: {d.lead} weeks</p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase">Total Stock</span>
                <span className="text-base font-black font-mono text-[var(--text-primary)]">{totalStock.toLocaleString()}</span>
                <span className="text-[9px] font-mono text-[var(--accent-gold)]">6 Vendors</span>
              </div>
            </div>

            {/* Legend & Summary Details */}
            <div className="lg:col-span-7 space-y-2.5">
              <div className="flex items-center justify-between text-xs font-mono text-[var(--text-muted)] pb-1 border-b border-[var(--border-subtle)]">
                <span>Distributor</span>
                <span>Stock / Share</span>
                <span>Unit Price</span>
                <span>Lead Time</span>
              </div>
              {pieData.map((d) => (
                <div
                  key={d.name}
                  className="p-2.5 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] flex items-center justify-between text-xs font-mono hover:border-[var(--accent-gold)] transition-all"
                >
                  <div className="flex items-center gap-2.5 min-w-[140px]">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: d.color }} />
                    <span className="font-bold text-[var(--text-primary)] truncate">{d.name}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-[var(--text-primary)] font-bold">{d.value.toLocaleString()}</span>
                    <span className="text-[10px] text-[var(--text-muted)] ml-1">({d.share}%)</span>
                  </div>
                  <span className="text-emerald-400 font-bold">${d.price.toFixed(2)}</span>
                  <span className="text-[var(--text-secondary)]">{d.lead} wks</span>
                </div>
              ))}
            </div>
          </div>

          {/* Qualified Alternative Manufacturers */}
          <div className="p-4 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-2">
            <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase tracking-wider">
              Qualified Pin-Compatible Manufacturers (Multi-Sourcing Layer)
            </span>
            <div className="flex flex-wrap items-center gap-2">
              {market_saturation.qualified_manufacturers.map((m, i) => (
                <span
                  key={m}
                  className={`px-3 py-1 rounded-xl text-xs font-mono font-bold border flex items-center gap-1.5 ${
                    i === 0
                      ? 'bg-[var(--accent-gold)]/10 border-[var(--accent-gold)]/40 text-[var(--accent-gold)]'
                      : 'bg-[var(--bg-card)] border-[var(--border-subtle)] text-[var(--text-secondary)]'
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  {m} {i === 0 ? '(Primary OEM)' : '(Qualified Second Source)'}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 2: GEOLOGICAL & FAB DISASTER RISK ── */}
      {activeTab === 'geology' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Primary Fab Facility */}
            <div className="p-4 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-2">
              <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5" /> Silicon Wafer Fabrication
              </span>
              <p className="text-sm font-bold text-[var(--text-primary)] font-mono">{geological.primary_fab_name}</p>
              <p className="text-xs text-[var(--text-secondary)] font-mono">
                {geological.primary_fab_city}, {geological.primary_fab_country}
              </p>
              <div className="pt-2 border-t border-[var(--border-subtle)] space-y-1 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Water Stress Level:</span>
                  <span className="font-bold text-[var(--text-primary)]">{geological.water_stress_level}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Tsunami Zone:</span>
                  <span className={geological.tsunami_hazard_zone ? 'text-rose-400 font-bold' : 'text-emerald-400 font-bold'}>
                    {geological.tsunami_hazard_zone ? 'YES (High Hazard)' : 'NO (Safe)'}
                  </span>
                </div>
              </div>
            </div>

            {/* Packaging & Test Facility */}
            <div className="p-4 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-2">
              <span className="text-[10px] font-mono text-[var(--accent-blue)] uppercase flex items-center gap-1">
                <Truck className="w-3.5 h-3.5" /> Assembly & Packaging Site
              </span>
              <p className="text-sm font-bold text-[var(--text-primary)] font-mono">{geological.secondary_packaging_name}</p>
              <p className="text-xs text-[var(--text-secondary)] font-mono">
                {geological.secondary_packaging_country}
              </p>
              <div className="pt-2 border-t border-[var(--border-subtle)] space-y-1 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Dual Site Qualified:</span>
                  <span className={geological.redundant_site_qualified ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
                    {geological.redundant_site_qualified ? 'YES (Redundant)' : 'SINGLE SITE (Bottleneck)'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--text-muted)]">Rare-Earth Dependence:</span>
                  <span className="text-[var(--text-primary)] font-bold">{geological.rare_earth_dependence_pct}%</span>
                </div>
              </div>
            </div>

            {/* Geological Hazard Indexes */}
            <div className="p-4 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-3">
              <span className="text-[10px] font-mono text-rose-400 uppercase flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5" /> Environmental Hazard Metrics
              </span>
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-[var(--text-muted)]">Seismic Hazard Score:</span>
                  <span className="font-bold text-[var(--text-primary)]">{geological.seismic_risk_score} / 100</span>
                </div>
                <div className="w-full h-1.5 bg-[var(--bg-card)] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      geological.seismic_risk_score > 60 ? 'bg-rose-400' : geological.seismic_risk_score > 30 ? 'bg-amber-400' : 'bg-emerald-400'
                    }`}
                    style={{ width: `${geological.seismic_risk_score}%` }}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-[var(--text-muted)]">Geopolitical Tension Index:</span>
                  <span className="font-bold text-[var(--text-primary)]">{geological.geopolitical_exposure_score} / 100</span>
                </div>
                <div className="w-full h-1.5 bg-[var(--bg-card)] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      geological.geopolitical_exposure_score > 60 ? 'bg-rose-400' : geological.geopolitical_exposure_score > 30 ? 'bg-amber-400' : 'bg-emerald-400'
                    }`}
                    style={{ width: `${geological.geopolitical_exposure_score}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Regional Stock Distribution Bar */}
          <div className="p-4 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-2">
            <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase tracking-wider">
              Geographic Inventory Distribution (% Total Global Buffer)
            </span>
            <div className="w-full h-4 rounded-lg overflow-hidden flex text-[10px] font-mono font-bold text-white">
              <div
                style={{ width: `${geological.regional_stock_americas_pct}%` }}
                className="bg-blue-600 flex items-center justify-center"
                title={`Americas: ${geological.regional_stock_americas_pct}%`}
              >
                {geological.regional_stock_americas_pct >= 15 && `Americas ${geological.regional_stock_americas_pct}%`}
              </div>
              <div
                style={{ width: `${geological.regional_stock_emea_pct}%` }}
                className="bg-emerald-600 flex items-center justify-center"
                title={`EMEA: ${geological.regional_stock_emea_pct}%`}
              >
                {geological.regional_stock_emea_pct >= 15 && `EMEA ${geological.regional_stock_emea_pct}%`}
              </div>
              <div
                style={{ width: `${geological.regional_stock_apac_pct}%` }}
                className="bg-amber-600 flex items-center justify-center"
                title={`APAC: ${geological.regional_stock_apac_pct}%`}
              >
                {geological.regional_stock_apac_pct >= 15 && `APAC ${geological.regional_stock_apac_pct}%`}
              </div>
              <div
                style={{ width: `${geological.regional_stock_domestic_pct}%` }}
                className="bg-purple-600 flex items-center justify-center"
                title={`Domestic: ${geological.regional_stock_domestic_pct}%`}
              >
                {geological.regional_stock_domestic_pct >= 5 && `Buffer`}
              </div>
            </div>
            <div className="flex items-center justify-between text-[11px] font-mono text-[var(--text-muted)] pt-1">
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-blue-600" /> Americas ({geological.regional_stock_americas_pct}%)</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-emerald-600" /> EMEA ({geological.regional_stock_emea_pct}%)</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-amber-600" /> APAC ({geological.regional_stock_apac_pct}%)</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-purple-600" /> Domestic Local Buffer ({geological.regional_stock_domestic_pct}%)</span>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 3: 12-MONTH HISTORICAL PRICE & LEAD TIME TRENDS ── */}
      {activeTab === 'trends' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Price Trend Chart */}
            <div className="p-4 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-mono text-emerald-400 uppercase">Pricing Volatility</span>
                  <h4 className="text-xs font-bold text-[var(--text-primary)] font-mono">12-Month Unit Price ($)</h4>
                </div>
                <span className="text-xs font-bold font-mono text-emerald-400">
                  Latest: ${market_saturation.price_trend_12m[market_saturation.price_trend_12m.length - 1].unit_price}
                </span>
              </div>

              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={market_saturation.price_trend_12m} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10B981" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#10B981" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" opacity={0.3} />
                    <XAxis dataKey="month" tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'monospace' }} />
                    <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'monospace' }} domain={['auto', 'auto']} />
                    <RechartsTooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const d = payload[0].payload;
                          return (
                            <div className="p-2 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs font-mono">
                              <p className="font-bold text-[var(--text-primary)]">{d.month}</p>
                              <p className="text-emerald-400">Contract: ${d.unit_price}</p>
                              {d.spot_market_price && <p className="text-amber-400">Spot: ${d.spot_market_price}</p>}
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Area type="monotone" dataKey="unit_price" stroke="#10B981" strokeWidth={2} fillOpacity={1} fill="url(#priceGradient)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Lead Time Trend Chart */}
            <div className="p-4 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase">Procurement Window</span>
                  <h4 className="text-xs font-bold text-[var(--text-primary)] font-mono">12-Month Lead Time (Weeks)</h4>
                </div>
                <span className="text-xs font-bold font-mono text-[var(--accent-gold)]">
                  Latest: {market_saturation.lead_time_trend_12m[market_saturation.lead_time_trend_12m.length - 1].lead_time_weeks} wks
                </span>
              </div>

              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={market_saturation.lead_time_trend_12m} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" opacity={0.3} />
                    <XAxis dataKey="month" tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'monospace' }} />
                    <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10, fontFamily: 'monospace' }} domain={[0, 'auto']} />
                    <RechartsTooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const d = payload[0].payload;
                          return (
                            <div className="p-2 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] text-xs font-mono">
                              <p className="font-bold text-[var(--text-primary)]">{d.month}</p>
                              <p className="text-[var(--accent-gold)]">Lead Time: {d.lead_time_weeks} weeks</p>
                              <p className="text-[var(--text-muted)]">Target: {d.target_lead_time_weeks} weeks</p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Line type="monotone" dataKey="lead_time_weeks" stroke="var(--accent-gold)" strokeWidth={2.5} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="target_lead_time_weeks" stroke="#EF4444" strokeWidth={1.5} strokeDasharray="4 4" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 4: VOLUME PRICING DISCOUNTS ── */}
      {activeTab === 'pricing' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {market_saturation.volume_price_breaks.map((vb) => (
              <div
                key={vb.tier}
                className="p-4 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] space-y-1.5 text-center hover:border-[var(--accent-gold)] transition-all"
              >
                <span className="text-[11px] font-mono text-[var(--text-muted)] uppercase">{vb.tier} Units</span>
                <p className="text-lg font-black font-mono text-emerald-400">${vb.unit_price.toFixed(3)}</p>
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${vb.savings_pct > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'text-[var(--text-muted)]'}`}>
                  {vb.savings_pct > 0 ? `-${vb.savings_pct}% discount` : 'Base Tier'}
                </span>
              </div>
            ))}
          </div>

          <div className="p-4 bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] text-xs font-mono space-y-1.5 text-[var(--text-secondary)]">
            <p className="font-bold text-[var(--text-primary)] flex items-center gap-1.5">
              <DollarSign className="w-4 h-4 text-emerald-400" /> Contract & Authorized Buffer Purchasing Terms
            </p>
            <p>
              Direct factory procurement for {part_number} qualifies for volume pricing amortization at order tiers exceeding 1,000 units. Standard distributor factory reel MOQ is enforced at 250/2,500 units depending on packaging configuration.
            </p>
          </div>
        </div>
      )}

      {/* ── Technical Documentation & Provenance Links ── */}
      <div className="pt-4 border-t border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <span className="text-[var(--text-muted)] text-[11px]">
          Data Provenance: <strong className="text-[var(--text-primary)]">Authorized Distributor API Feeds + Verified Public Datasheets</strong>
        </span>
        <div className="flex items-center gap-3">
          {intelligence.document_links.map((doc, idx) => (
            <a
              key={idx}
              href={doc.url}
              target="_blank"
              rel="noreferrer"
              className="text-[var(--accent-blue)] hover:underline flex items-center gap-1 text-[11px]"
            >
              {doc.title} <ArrowUpRight className="w-3 h-3" />
            </a>
          ))}
        </div>
      </div>
    </div>
  );
};
