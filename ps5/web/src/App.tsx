import React, { useState, useEffect, useCallback } from 'react';
import type { PageId, RiskReportDashboard, BOMComponent, RiskBand, IndustryBom, IndustryBomSession, IndustryImportResult, IndustryStatus } from './types';
import { ThemeProvider } from './context/ThemeContext';
import { HardwareTwinProvider } from './context/HardwareTwinContext';
import { useHardwareTwin } from './context/useHardwareTwin';
import { PcbTraceBackground } from './components/PcbTraceBackground';
import { SidebarNav } from './components/SidebarNav';
import { CommandPalette } from './components/CommandPalette';
import { LiveRiskPulseStrip } from './components/LiveRiskPulseStrip';
import { normalizeBand } from './components/primitives';
import { SENTINEL_API_BASE } from './api';

import { DashboardPage } from './pages/DashboardPage';
import { BomUploadPage } from './pages/BomUploadPage';
import { ComponentTablePage } from './pages/ComponentTablePage';
import { ComponentDetailPage } from './pages/ComponentDetailPage';
import { VendorComparisonPage } from './pages/VendorComparisonPage';
import { SettingsPage } from './pages/SettingsPage';
import { ReportDownloadPage } from './pages/ReportDownloadPage';
import { DecisionPage } from './pages/DecisionPage';
import { FmeaMatrixPage } from './pages/FmeaMatrixPage';

// Approved substitutes: map from original pn → approved substitute pn
export type ApprovalMap = Record<string, string>;

/** Ensure every part has uppercase band + deterministic sparkline for consistent UI. */
function normalizeDashboard(dash: RiskReportDashboard): RiskReportDashboard {
  const parts = (dash.parts || []).map((p) => {
    const band = String(p.band || '').toUpperCase() === 'INSUFFICIENT_DATA'
      ? 'INSUFFICIENT_DATA' as const
      : normalizeBand(p.band, p.score ?? undefined);
    const sparkline = band === 'INSUFFICIENT_DATA' ? [] : (p.sparkline_data && p.sparkline_data.length >= 2 ? p.sparkline_data : []);
    const enriched: BOMComponent = {
      ...p,
      band,
      sparkline_data: sparkline,
    };
    return enriched;
  });

  const critical = parts.filter(p => p.band === 'CRITICAL').length;
  const high = parts.filter(p => p.band === 'HIGH').length;
  const medium = parts.filter(p => p.band === 'MEDIUM').length;
  const low = parts.filter(p => p.band === 'LOW').length;

  return {
    ...dash,
    overall: String(dash.overall || '').toUpperCase() === 'INSUFFICIENT_DATA'
      ? 'INSUFFICIENT_DATA'
      : normalizeBand(dash.overall, dash.avg_score ?? undefined),
    critical,
    high,
    medium,
    low,
    total_parts: parts.length || dash.total_parts,
    parts,
  };
}

export const MainApp: React.FC = () => {
  const { syncProjectComponents } = useHardwareTwin();
  const [activePage, setActivePage] = useState<PageId>('upload');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState<boolean>(false);

  const [report, setReport] = useState<RiskReportDashboard | null>(null);
  const [selectedComponent, setSelectedComponent] = useState<BOMComponent | null>(null);
  const [decisionTarget, setDecisionTarget] = useState<{ productId: string; componentId: string } | null>(null);
  const [approvedSubstitutes, setApprovedSubstitutes] = useState<ApprovalMap>({});
  // Shared risk-band filter so Critical/High/… stay consistent across pages
  const [bandFilter, setBandFilter] = useState<RiskBand | 'ALL'>('ALL');
  const [industryStatus, setIndustryStatus] = useState<IndustryStatus | null>(null);
  const [industryResult, setIndustryResult] = useState<IndustryImportResult | null>(null);
  const [isIndustryImporting, setIsIndustryImporting] = useState(false);
  const [industryError, setIndustryError] = useState<string | null>(null);
  const [industryBoms, setIndustryBoms] = useState<IndustryBom[]>([]);
  const [industrySession, setIndustrySession] = useState<IndustryBomSession | null>(null);
  const [activeProjectId, setActiveProjectId] = useState('smart_cooling');

  const loadIndustryStatus = async () => {
    try {
      const response = await fetch(`${SENTINEL_API_BASE}/api/industry/status`);
      if (!response.ok) return;
      setIndustryStatus(await response.json());
    } catch {
      setIndustryStatus(null);
    }
  };

  const loadIndustryBoms = async () => {
    try {
      const response = await fetch(`${SENTINEL_API_BASE}/api/industry/boms`);
      if (response.ok) setIndustryBoms((await response.json()).boms || []);
    } catch { setIndustryBoms([]); }
  };

  const runIndustryImport = async (dryRun: boolean) => {
    setIsIndustryImporting(true); setIndustryError(null);
    try {
      const response = await fetch(`${SENTINEL_API_BASE}/api/industry/import`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ dry_run: dryRun })
      });
      const payload = await response.json();
      if (response.ok) setIndustryResult(payload); else setIndustryError(payload.message || 'Industry import failed.');
      await loadIndustryStatus();
      await loadIndustryBoms();
    } catch { setIndustryError('Industry import could not reach the local API.');
    } finally {
      setIsIndustryImporting(false);
    }
  };

  const uploadIndustryFile = async (file: File) => {
    setIsIndustryImporting(true); setIndustryError(null);
    try {
      const contentBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || '').split(',', 2)[1] || '');
        reader.onerror = () => reject(new Error('The selected file could not be read.'));
        reader.readAsDataURL(file);
      });
      const response = await fetch(`${SENTINEL_API_BASE}/api/industry/upload`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, content_base64: contentBase64 }),
      });
      const payload = await response.json();
      if (response.ok) setIndustryResult(payload); else setIndustryError(payload.message || 'Industry upload failed.');
      await loadIndustryStatus();
      await loadIndustryBoms();
    } catch (error) {
      setIndustryError(error instanceof Error ? error.message : 'Industry upload could not reach the local API.');
    } finally { setIsIndustryImporting(false); }
  };

  const loadIndustryBom = async (bom: IndustryBom) => {
    setIndustryError(null);
    try {
      const response = await fetch(`${SENTINEL_API_BASE}/api/industry/bom/load`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ product_id: bom.product_id }),
      });
      const session = await response.json();
      if (!response.ok || session.error) { setIndustryError(session.message || 'Industry BOM could not be loaded.'); return false; }
      setIndustrySession(session);
      await loadRiskReport(bom.project_key);
      return true;
    } catch { setIndustryError('Industry BOM could not reach the local API.'); return false; }
  };

  const applyDashboard = useCallback((dash: RiskReportDashboard, projectId = 'mini_smart_cooling_controller') => {
    const normalized = normalizeDashboard(dash);
    setReport(normalized);
    syncProjectComponents(projectId, normalized.parts);
    if (normalized.parts?.length > 0) {
      setSelectedComponent(prev => {
        if (prev) {
          const match = normalized.parts.find(p => p.pn === prev.pn && p.ref === prev.ref);
          if (match) return match;
        }
        const withLive = normalized.parts.find(part => part.stock_level != null || (part.band !== 'INSUFFICIENT_DATA' && typeof part.score === 'number'));
        return withLive || normalized.parts[0];
      });
    }
  }, [syncProjectComponents]);

  const loadRiskReport = async (projectId: string) => {
    setActiveProjectId(projectId);
    try {
      const res = await fetch(`${SENTINEL_API_BASE}/risk/analyze?project=${encodeURIComponent(projectId)}`);
      const data = await res.json();
      if (data.dashboard) {
        applyDashboard(data.dashboard, projectId);
      }
    } catch { setReport(null); setSelectedComponent(null); }
  };

  useEffect(() => {
    void (async () => {
      await loadIndustryStatus();
      try {
        const response = await fetch(`${SENTINEL_API_BASE}/api/industry/boms`);
        const payload = response.ok ? await response.json() : { boms: [] };
        const boms: IndustryBom[] = payload.boms || [];
        setIndustryBoms(boms);
        const preferred = boms.find(bom => bom.product_id === 'beaglebone-black') || boms[0];
        if (preferred) {
          await loadIndustryBom(preferred);
        } else {
          await loadRiskReport('smart_cooling');
        }
      } catch {
        await loadRiskReport('smart_cooling');
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleUploadCsvText = async (file: File) => {
    try {
      const csvText = await file.text();
      const res = await fetch(`${SENTINEL_API_BASE}/risk/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, csv_text: csvText })
      });
      const data = await res.json();
      if (data.dashboard) {
        applyDashboard(data.dashboard, file.name.replace(/\.[^.]+$/, '') || 'uploaded_bom');
      }
    } catch { /* keep current */ }
  };

  const handleApproveSubstitute = (originalPn: string, substitutePn: string) => {
    setApprovedSubstitutes(prev => ({ ...prev, [originalPn]: substitutePn }));
  };

  const handleBandFilterChange = (band: RiskBand | 'ALL') => {
    setBandFilter(band);
  };

  return (
    <div className="min-h-screen flex flex-col relative text-[var(--text-primary)] transition-colors duration-300">
      {/* Animated PCB Trace Background Layer */}
      <PcbTraceBackground />

      {/* Live Hardware Risk Pulse Strip */}
      <LiveRiskPulseStrip />

      {/* Main Layout Container */}
      <div className="flex-1 flex w-full relative z-10">
        {/* Left Persistent Collapsible Sidebar Navigation */}
        <SidebarNav
          activePage={activePage}
          onPageChange={setActivePage}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
        />

        {/* Dynamic Page View Area */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full overflow-x-hidden">
          {activePage === 'dashboard' && (
            <DashboardPage
              report={report}
              bandFilter={bandFilter}
              onBandFilterChange={handleBandFilterChange}
              onSelectComponent={(comp) => { setSelectedComponent(comp); setActivePage('detail'); }}
              onNavigateToUpload={() => setActivePage('upload')}
              onNavigateToComponents={() => setActivePage('components')}
            />
          )}

          {activePage === 'upload' && (
            <BomUploadPage
              onAnalyzeSample={loadRiskReport}
              onUploadCsv={handleUploadCsvText}
              onAnalysisComplete={() => setActivePage('dashboard')}
              onNavigateToDashboard={() => setActivePage('dashboard')}
              industryStatus={industryStatus}
              industryResult={industryResult}
              industryError={industryError}
              isIndustryImporting={isIndustryImporting}
              onRunIndustryImport={runIndustryImport}
              onUploadIndustryFile={uploadIndustryFile}
              onNavigateToVendor={() => setActivePage('vendor')}
              industryBoms={industryBoms}
              industrySession={industrySession}
              onLoadIndustryBom={loadIndustryBom}
            />
          )}

          {activePage === 'components' && (
            <ComponentTablePage
              components={report?.parts || []}
              bandFilter={bandFilter}
              onBandFilterChange={handleBandFilterChange}
              onSelectComponent={(comp) => { setSelectedComponent(comp); setActivePage('detail'); }}
            />
          )}

          {activePage === 'detail' && (
            <ComponentDetailPage
              component={selectedComponent || (report?.parts ? report.parts[0] : null)}
              approvedSubstitutes={approvedSubstitutes}
              onApproveSubstitute={handleApproveSubstitute}
              onBack={() => setActivePage('components')}
              industryProductId={industrySession?.product_id || null}
              onViewDecision={(component) => {
                if (industrySession?.product_id) {
                  setDecisionTarget({ productId: industrySession.product_id, componentId: component.ref });
                } else {
                  setDecisionTarget({
                    productId: 'demo',
                    componentId: component.substitute_lookup_id || component.component_id || component.pn,
                  });
                }
                setActivePage('decision');
              }}
            />
          )}

          {activePage === 'decision' && decisionTarget && (
            <DecisionPage productId={decisionTarget.productId} componentId={decisionTarget.componentId} onBack={() => setActivePage('detail')} />
          )}

          {activePage === 'fmea' && (
            <FmeaMatrixPage
              components={report?.parts || []}
              bomName={report?.name || activeProjectId}
              onSelectComponent={(comp) => { setSelectedComponent(comp); setActivePage('detail'); }}
            />
          )}

          {activePage === 'vendor' && <VendorComparisonPage components={report?.parts || []} onNavigateToUpload={() => setActivePage('upload')} onDataUpdated={() => void loadRiskReport(activeProjectId)} />}
          {activePage === 'report' && <ReportDownloadPage report={report} approvedSubstitutes={approvedSubstitutes} />}
          {activePage === 'settings' && <SettingsPage />}
        </main>
      </div>

      {/* Command Palette Modal (⌘K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onNavigate={setActivePage}
        components={report?.parts || []}
        onSelectComponent={(comp) => setSelectedComponent(comp)}
      />
    </div>
  );
};

export default function App() {
  return (
    <ThemeProvider>
      <HardwareTwinProvider>
        <MainApp />
      </HardwareTwinProvider>
    </ThemeProvider>
  );
}
