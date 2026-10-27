import React, { useState } from 'react';
import { Upload, FileSpreadsheet, CheckCircle2, Cpu, ArrowRight, Zap, Shield, Activity, LayoutDashboard, Database, RefreshCw, Files } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { IndustryBom, IndustryBomSession, IndustryImportResult, IndustryStatus } from '../types';

interface BomUploadPageProps {
  onAnalyzeSample: (projectId: string) => void;
  onUploadCsv: (file: File) => void;
  onAnalysisComplete: () => void;
  onNavigateToDashboard?: () => void;
  industryStatus: IndustryStatus | null;
  industryResult: IndustryImportResult | null;
  industryError: string | null;
  isIndustryImporting: boolean;
  onRunIndustryImport: (dryRun: boolean) => void;
  onUploadIndustryFile: (file: File) => Promise<void>;
  onNavigateToVendor?: () => void;
  industryBoms: IndustryBom[];
  industrySession: IndustryBomSession | null;
  onLoadIndustryBom: (bom: IndustryBom) => Promise<boolean>;
}

const sampleProjects = [
  { id: 'industrial_iot',            name: 'Industrial IoT Gateway',      parts: 25, risk: 'CRITICAL', color: '#E76F51' },
  { id: 'drone_controller',          name: 'Smart Drone Controller',       parts: 30, risk: 'HIGH',     color: '#F4A261' },
  { id: 'medical_oximeter',          name: 'Medical Oximeter',             parts: 20, risk: 'HIGH',     color: '#F4A261' },
  { id: 'burglar_alarm',             name: 'Burglar Alarm System',         parts: 12, risk: 'MEDIUM',   color: '#E9C46A' },
  { id: 'fan_controller',            name: 'Mini Fan Controller',          parts: 13, risk: 'LOW',      color: '#2A9D8F' },
  { id: 'smart_cooling',             name: 'Smart Cooling Controller',     parts: 16, risk: 'MEDIUM',   color: '#E9C46A' },
  { id: 'touch_lamp',                name: 'Touch Sensor Lamp',           parts: 30, risk: 'LOW',      color: '#2A9D8F' },
  { id: 'water_level',               name: 'Water Level Indicator',        parts: 20, risk: 'LOW',      color: '#2A9D8F' },
];

const steps = [
  { icon: FileSpreadsheet, text: 'Parsing CSV Line Items & References' },
  { icon: Shield,          text: 'Scoring Obsolescence & Sourcing Vulnerability' },
  { icon: Activity,        text: 'Cross-Referencing Authorized Distributors' },
  { icon: Cpu,             text: 'Generating Hardware Physical Mirror Payload' },
];

export const BomUploadPage: React.FC<BomUploadPageProps> = ({
  onAnalyzeSample, onUploadCsv, onAnalysisComplete, onNavigateToDashboard,
  industryStatus, industryResult, industryError, isIndustryImporting, onRunIndustryImport, onUploadIndustryFile, onNavigateToVendor, industryBoms, industrySession, onLoadIndustryBom
}) => {
  const [isScanning, setIsScanning] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [fileName, setFileName] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [loadingIndustryBom, setLoadingIndustryBom] = useState<string | null>(null);

  const processFile = (file: File) => {
    setFileName(file.name);
    startScanning(() => onUploadCsv(file));
  };

  const handleSampleClick = (id: string, name: string) => {
    setFileName(`${name}`);
    startScanning(() => onAnalyzeSample(id));
  };

  const handleIndustryBom = async (bom: IndustryBom) => {
    setLoadingIndustryBom(bom.product_id);
    setFileName(bom.name);
    try {
      const loaded = await onLoadIndustryBom(bom);
      if (loaded) onAnalysisComplete();
    } finally { setLoadingIndustryBom(null); }
  };

  const startScanning = (onFinish: () => void, navigateAfter = true) => {
    setIsScanning(true);
    setCurrentStep(0);
    const interval = setInterval(() => {
      setCurrentStep(prev => {
        if (prev >= steps.length - 1) {
          clearInterval(interval);
          setTimeout(() => { setIsScanning(false); onFinish(); if (navigateAfter) onAnalysisComplete(); }, 800);
          return prev;
        }
        return prev + 1;
      });
    }, 700);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-4">
      {/* Page header */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-black font-mono tracking-widest uppercase border"
          style={{
            background: 'color-mix(in oklab, var(--accent-gold) 12%, var(--bg-elevated))',
            borderColor: 'color-mix(in oklab, var(--accent-gold) 30%, transparent)',
            color: 'var(--accent-gold)',
          }}>
          <Zap className="w-3 h-3" /> BOM Analysis Engine
        </div>
        <h2 className="text-3xl font-black tracking-tight gradient-text">Ingest Your Bill of Materials</h2>
        <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto leading-relaxed">
          Upload any electronic BOM CSV to calculate supply-chain risk scores, lifecycle status, and build a live hardware mirror.
        </p>
      </motion.div>

      <AnimatePresence mode="wait">
        {!isScanning ? (
          <motion.div key="upload" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.96 }} className="space-y-6">

            {/* Drop Zone */}
            <motion.div
              onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={e => { e.preventDefault(); setIsDragging(false); if (e.dataTransfer.files[0]) processFile(e.dataTransfer.files[0]); }}
              animate={{ scale: isDragging ? 1.01 : 1 }}
              className="relative glass-card p-12 rounded-2xl border-2 border-dashed text-center flex flex-col items-center gap-5 cursor-pointer group overflow-hidden"
              style={{
                borderColor: isDragging ? 'var(--accent-gold)' : 'var(--border-strong)',
                background: isDragging ? 'color-mix(in oklab, var(--accent-gold) 8%, var(--bg-card))' : 'var(--bg-card)',
              }}
            >
              {/* Background glow on drag */}
              {isDragging && (
                <div className="absolute inset-0 pointer-events-none"
                  style={{ background: 'radial-gradient(ellipse at center, color-mix(in oklab, var(--accent-gold) 12%, transparent) 0%, transparent 70%)' }} />
              )}

              <motion.div
                animate={{ y: [0, -6, 0] }}
                transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
                className="w-20 h-20 rounded-2xl flex items-center justify-center relative"
                style={{
                  background: 'var(--gradient-brand)',
                  boxShadow: '0 8px 32px -8px color-mix(in oklab, var(--accent-gold) 50%, transparent)',
                }}
              >
                <Upload className="w-9 h-9 text-white" />
              </motion.div>

              <div className="space-y-2 relative z-10">
                <h3 className="text-lg font-black text-[var(--text-primary)]">Drop your BOM file here</h3>
                <p className="text-xs text-[var(--text-muted)]">CSV or XLSX · Part Number, Reference Designator, Quantity columns</p>
              </div>

              <label className="relative z-10 px-6 py-2.5 rounded-xl text-sm font-black text-white cursor-pointer transition-all hover:brightness-110 active:scale-95 shadow-lg"
                style={{ background: 'var(--gradient-brand)', boxShadow: '0 4px 20px -4px color-mix(in oklab, var(--accent-gold) 45%, transparent)' }}>
                Browse Files
                <input type="file" accept=".csv" onChange={e => { if (e.target.files?.[0]) processFile(e.target.files[0]); }} className="hidden" />
              </label>
            </motion.div>

            {/* Industry data status: uses only backend-reported, provenance-tagged values. */}
            <div className="glass-card p-5 rounded-2xl space-y-4">
              <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-[var(--accent-blue)]" />
                  <div>
                    <h3 className="text-sm font-bold text-[var(--text-primary)]">Industry Reference Data</h3>
                    <p className="text-[10px] text-[var(--text-muted)] font-mono">Local BOM and document provenance only</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button type="button" onClick={() => onRunIndustryImport(true)} disabled={isIndustryImporting}
                    className="px-3 py-1.5 rounded-xl text-[10px] font-bold border cursor-pointer disabled:opacity-50"
                    style={{ color: 'var(--accent-gold)', background: 'var(--bg-elevated)', borderColor: 'var(--border-strong)' }}>
                    Preview
                  </button>
                  <button type="button" onClick={() => onRunIndustryImport(false)} disabled={isIndustryImporting}
                    className="px-3 py-1.5 rounded-xl text-[10px] font-black text-white flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                    style={{ background: 'var(--gradient-brand)' }}>
                    <RefreshCw className={`w-3 h-3 ${isIndustryImporting ? 'animate-spin' : ''}`} /> Import Industry Data
                  </button>
                </div>
              </div>
              {industryStatus ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[
                    ['Incoming files', industryStatus.incoming_files], ['BOM rows', industryStatus.bom_lines],
                    ['Documents', industryStatus.documents_registered], ['Unresolved', industryStatus.unresolved_mpns],
                  ].map(([label, value]) => <div key={String(label)} className="p-2.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)]">
                    <p className="text-lg font-black font-mono text-[var(--text-primary)]">{value}</p><p className="text-[9px] font-mono text-[var(--text-muted)] uppercase">{label}</p>
                  </div>)}
                </div>
              ) : <p className="text-xs text-[var(--text-muted)]">Industry status unavailable while the local API is offline.</p>}
              {industryStatus && !industryStatus.providers.digikey.configured && !industryStatus.providers.nexar.configured && !industryStatus.providers.mouser?.configured && (
                <p className="text-[11px] px-3 py-2 rounded-xl border text-[var(--text-muted)] bg-[var(--bg-elevated)] border-[var(--border-subtle)]">Provider enrichment unavailable - no supplier stock, price, lifecycle, or lead-time data is shown.</p>
              )}
              {industryResult && <div className="flex items-center gap-2 text-[11px] text-[var(--text-secondary)] font-mono"><Files className="w-3.5 h-3.5 text-[var(--accent-blue)]" />{industryResult.dry_run ? 'Preview' : 'Import'}: {industryResult.files_detected} files, {industryResult.bom_rows} BOM rows, {industryResult.documents_registered} documents, {industryResult.duplicates} duplicates.</div>}
              {industryError && <p className="text-[11px] text-[var(--risk-high)] font-mono">{industryError}</p>}
              <div className="pt-3 flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between border-t border-[var(--border-subtle)]">
                <div><p className="text-xs font-bold text-[var(--text-primary)]">Upload an industry BOM or design package</p><p className="text-[10px] text-[var(--text-muted)]">ZIP, CSV, XLS, XLSX, PDF, TXT, JSON · safely preserved, hashed, and normalized</p></div>
                <div className="flex gap-2"><label className="px-3 py-2 rounded-xl text-[10px] font-black text-white cursor-pointer" style={{ background: 'var(--gradient-brand)' }}>Upload industry file<input type="file" accept=".zip,.csv,.xls,.xlsx,.pdf,.txt,.json" onChange={event => { const file = event.target.files?.[0]; if (file) { setFileName(file.name); startScanning(() => { void onUploadIndustryFile(file); }, false); } event.currentTarget.value = ''; }} className="hidden" /></label>{onNavigateToVendor && <button type="button" onClick={onNavigateToVendor} className="px-3 py-2 rounded-xl text-[10px] font-bold border" style={{ color: 'var(--accent-blue)', borderColor: 'var(--border-strong)', background: 'var(--bg-elevated)' }}>Vendor Comparison →</button>}</div>
              </div>
            </div>

            <div className="glass-card p-6 rounded-2xl space-y-4">
              <div className="flex items-center gap-2"><Database className="w-4 h-4 text-[var(--accent-blue)]" /><div><h3 className="text-sm font-bold text-[var(--text-primary)]">Industry BOMs</h3><p className="text-[10px] font-mono text-[var(--text-muted)]">Normalized source data already available in SENTINEL</p></div></div>
              {industryBoms.length ? <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{industryBoms.map(bom => <div key={bom.product_id} className="p-4 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)]"><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-black text-[var(--text-primary)]">{bom.name}</p><p className="text-[10px] text-[var(--text-muted)] font-mono mt-1">{bom.manufacturer || 'Industry source'}</p></div><button type="button" onClick={() => { void handleIndustryBom(bom); }} disabled={loadingIndustryBom !== null} className="px-3 py-1.5 rounded-xl text-[10px] font-black text-white disabled:opacity-50" style={{ background: 'var(--gradient-brand)' }}>{loadingIndustryBom === bom.product_id ? 'Loading…' : 'Load BOM'}</button></div><div className="grid grid-cols-3 gap-2 mt-3 text-[10px] font-mono text-[var(--text-muted)]"><span>{bom.bom_lines} lines</span><span>{bom.unique_mpns} MPNs</span><span>{bom.enriched_components} enriched</span></div><p className="mt-2 text-[10px] text-[var(--text-muted)] truncate">Source: {bom.source_document || `${bom.source_documents} registered documents`}</p></div>)}</div> : <p className="text-xs text-[var(--text-muted)]">No normalized industry BOMs are currently available.</p>}
              {industrySession && <div className="p-4 rounded-xl border bg-[var(--bg-card)] border-[var(--border-strong)]"><div className="flex flex-wrap justify-between gap-2"><div><p className="text-xs font-black text-[var(--text-primary)]">{industrySession.name}</p><p className="text-[10px] font-mono text-[var(--text-muted)]">Source: {industrySession.source} · {industrySession.source_document || 'Registered provenance'}</p></div><span className="text-[10px] font-black text-[var(--risk-low)]">RISK ANALYSIS READY</span></div><div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3 text-[10px] font-mono"><span>{industrySession.bom_lines} BOM lines</span><span>{industrySession.unique_mpns} unique MPNs</span><span>Enrichment {industrySession.enrichment_status}</span><span>{industrySession.last_updated || 'No import timestamp'}</span></div><div className="flex gap-2 mt-3">{onNavigateToDashboard && <button type="button" onClick={onNavigateToDashboard} className="text-[10px] font-bold text-[var(--accent-gold)]">Analyze Risk →</button>}{onNavigateToVendor && <button type="button" onClick={onNavigateToVendor} className="text-[10px] font-bold text-[var(--accent-blue)]">View Vendors →</button>}</div></div>}
            </div>

            {/* Sample projects grid */}
            <div className="glass-card p-6 rounded-2xl space-y-4">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-4 h-4 text-[var(--accent-gold)]" />
                <h3 className="text-sm font-bold text-[var(--text-primary)]">Or load a sample BOM project</h3>
                <span className="ml-auto text-[10px] font-mono text-[var(--text-muted)]">{sampleProjects.length} available</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {sampleProjects.map((p, i) => (
                  <motion.button
                    key={p.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    whileHover={{ scale: 1.03, y: -2 }}
                    onClick={() => handleSampleClick(p.id, p.name)}
                    className="p-3.5 rounded-xl text-left cursor-pointer border transition-all group relative overflow-hidden"
                    style={{
                      background: `color-mix(in oklab, ${p.color} 6%, var(--bg-elevated))`,
                      borderColor: `color-mix(in oklab, ${p.color} 25%, transparent)`,
                      boxShadow: `0 2px 10px -4px color-mix(in oklab, ${p.color} 20%, transparent)`,
                    }}
                  >
                    <div className="absolute top-0 right-0 w-16 h-16 rounded-full pointer-events-none"
                      style={{ background: `radial-gradient(circle, color-mix(in oklab, ${p.color} 15%, transparent) 0%, transparent 70%)` }} />
                    <div className="relative z-10">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[9px] font-black font-mono tracking-widest uppercase px-1.5 py-0.5 rounded-md"
                          style={{ color: p.color, background: `color-mix(in oklab, ${p.color} 18%, var(--bg-card))` }}>
                          {p.risk}
                        </span>
                        <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" style={{ color: p.color }} />
                      </div>
                      <p className="text-xs font-bold text-[var(--text-primary)] leading-tight line-clamp-2">{p.name}</p>
                      <p className="text-[10px] text-[var(--text-muted)] font-mono mt-1">{p.parts} parts</p>
                    </div>
                  </motion.button>
                ))}
              </div>
            </div>

            {/* Dashboard Shortcut Option */}
            {onNavigateToDashboard && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-card p-5 rounded-2xl border flex flex-col sm:flex-row items-center justify-between gap-4"
                style={{
                  background: 'color-mix(in oklab, var(--accent-gold) 6%, var(--bg-card))',
                  borderColor: 'color-mix(in oklab, var(--accent-gold) 25%, transparent)',
                }}
              >
                <div className="flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                    style={{ background: 'var(--gradient-brand)', color: '#fff' }}>
                    <LayoutDashboard className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-[var(--text-primary)]">Explore Active BOM Risk Dashboard</h4>
                    <p className="text-xs text-[var(--text-muted)]">View executive supply-chain risk analytics, component health charts, and lifecycle indicators.</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onNavigateToDashboard}
                  className="px-4 py-2 rounded-xl text-xs font-black text-white shrink-0 cursor-pointer flex items-center gap-2 transition-all hover:brightness-110 active:scale-95 shadow-md"
                  style={{ background: 'var(--gradient-brand)' }}
                >
                  Open Dashboard <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </motion.div>
            )}
          </motion.div>

        ) : (
          /* Scanning animation */
          <motion.div key="scan" initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
            className="glass-card p-10 rounded-2xl text-center space-y-8 relative overflow-hidden">

            {/* PCB board visual */}
            <div className="w-72 h-52 mx-auto relative rounded-xl border overflow-hidden"
              style={{ background: 'color-mix(in oklab, var(--accent-gold) 6%, var(--bg-elevated))', borderColor: 'var(--border-strong)' }}>
              <div className="grid grid-cols-4 gap-3 p-4 opacity-60">
                {[...Array(12)].map((_, i) => (
                  <motion.div key={i}
                    animate={{ opacity: i <= currentStep * 3 ? 1 : 0.3, scale: i === currentStep * 3 ? [1, 1.1, 1] : 1 }}
                    transition={{ duration: 0.3 }}
                    className="h-7 rounded border flex items-center justify-center text-[9px] font-mono font-bold"
                    style={{
                      background: i <= currentStep * 3 ? `color-mix(in oklab, var(--accent-gold) 20%, var(--bg-elevated))` : 'transparent',
                      borderColor: i <= currentStep * 3 ? 'var(--accent-gold)' : 'var(--border-subtle)',
                      color: i <= currentStep * 3 ? 'var(--accent-gold)' : 'var(--text-muted)',
                    }}>
                    U{i + 1}
                  </motion.div>
                ))}
              </div>
              {/* Sweep line */}
              <motion.div className="absolute left-0 right-0 h-0.5"
                style={{ background: 'linear-gradient(90deg, transparent, var(--accent-amber), transparent)', boxShadow: '0 0 12px var(--accent-amber)' }}
                animate={{ top: ['5%', '95%', '5%'] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
              />
              <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-4 py-2 border-t"
                style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-elevated)' }}>
                <span className="text-[10px] font-mono text-[var(--text-muted)] truncate">{fileName}</span>
                <Cpu className="w-3.5 h-3.5 animate-spin" style={{ color: 'var(--accent-blue)' }} />
              </div>
            </div>

            {/* Steps */}
            <div className="space-y-3 max-w-md mx-auto text-left">
              {steps.map((step, idx) => {
                const Icon = step.icon;
                const isDone = idx < currentStep;
                const isActive = idx === currentStep;
                return (
                  <motion.div key={idx}
                    initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: idx * 0.1 }}
                    className="flex items-center gap-3 text-xs px-4 py-3 rounded-xl border transition-all"
                    style={{
                      background: isActive ? 'color-mix(in oklab, var(--accent-gold) 10%, var(--bg-elevated))' : 'var(--bg-elevated)',
                      borderColor: isActive ? 'color-mix(in oklab, var(--accent-gold) 40%, transparent)' : 'var(--border-subtle)',
                    }}>
                    {isDone
                      ? <CheckCircle2 className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--risk-low)' }} />
                      : isActive
                        ? <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}>
                            <Icon className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--accent-gold)' }} />
                          </motion.div>
                        : <div className="w-4 h-4 rounded-full border flex-shrink-0" style={{ borderColor: 'var(--border-subtle)' }} />
                    }
                    <span className={isActive ? 'font-bold text-[var(--text-primary)]' : isDone ? 'text-[var(--text-secondary)]' : 'text-[var(--text-muted)]'}>
                      {step.text}
                    </span>
                    {isDone && <CheckCircle2 className="w-3 h-3 ml-auto flex-shrink-0" style={{ color: 'var(--risk-low)' }} />}
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
