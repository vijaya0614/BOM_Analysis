import React, { useState, useEffect } from 'react';
import type { PageId, BOMComponent } from '../types';
import { Search, LayoutDashboard, Upload, Layers, FileText, Building2, Settings, Download, X, Zap } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { RiskBadge } from './primitives';
import { bandHex } from '../utils/riskUtils';
import type { RiskBand } from './primitives';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (page: PageId) => void;
  components: BOMComponent[];
  onSelectComponent: (comp: BOMComponent) => void;
}

const pages: { id: PageId; label: string; icon: any; desc: string }[] = [
  { id: 'dashboard',  label: 'Dashboard',          icon: LayoutDashboard, desc: 'BOM health overview & risk map' },
  { id: 'upload',     label: 'BOM Upload',          icon: Upload,          desc: 'Ingest a new BOM CSV' },
  { id: 'components', label: 'Components',          icon: Layers,          desc: 'Browse & filter all parts' },
  { id: 'detail',     label: 'Component Detail',    icon: FileText,        desc: 'Deep-dive risk analysis' },
  { id: 'vendor',     label: 'Vendor Comparison',   icon: Building2,       desc: 'Distributor sourcing intelligence' },
  { id: 'report',     label: 'AI Report',           icon: Download,        desc: 'Export intelligence report' },
  { id: 'settings',   label: 'Settings',            icon: Settings,        desc: 'Theme & API config' },
];

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen, onClose, onNavigate, components, onSelectComponent
}) => {
  const [query, setQuery] = useState('');

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); if (isOpen) onClose(); }
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  useEffect(() => { if (isOpen) setQuery(''); }, [isOpen]);

  if (!isOpen) return null;

  const filteredPages = pages.filter(p =>
    p.label.toLowerCase().includes(query.toLowerCase()) || p.desc.toLowerCase().includes(query.toLowerCase())
  );
  const filteredComps = components.filter(c =>
    c.pn.toLowerCase().includes(query.toLowerCase()) || c.ref.toLowerCase().includes(query.toLowerCase())
  ).slice(0, 5);

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 px-4"
        style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}
        onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
        <motion.div
          initial={{ opacity: 0, scale: 0.94, y: -16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.94, y: -16 }}
          transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-2xl rounded-2xl overflow-hidden shadow-2xl border"
          style={{ background: 'var(--bg-surface-solid)', borderColor: 'var(--border-strong)', boxShadow: '0 32px 80px -16px rgba(0,0,0,0.6), 0 0 0 1px var(--border-subtle)' }}>

          {/* Input */}
          <div className="flex items-center px-5 py-4 border-b gap-3" style={{ borderColor: 'var(--border-subtle)' }}>
            <Search className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--accent-gold)' }} />
            <input type="text" value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Search components, pages, or actions…"
              className="flex-1 bg-transparent border-none outline-none text-sm placeholder-[var(--text-muted)]"
              style={{ color: 'var(--text-primary)' }}
              autoFocus />
            <div className="flex items-center gap-2">
              <kbd className="text-[10px] px-1.5 py-0.5 rounded font-mono font-bold border"
                style={{ color: 'var(--text-muted)', borderColor: 'var(--border-subtle)', background: 'var(--bg-elevated)' }}>ESC</kbd>
              <button onClick={onClose} className="p-1 rounded-lg hover:bg-[var(--bg-elevated)] transition-colors cursor-pointer">
                <X className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
              </button>
            </div>
          </div>

          {/* Results */}
          <div className="max-h-96 overflow-y-auto p-2 space-y-3">

            {/* Pages */}
            {filteredPages.length > 0 && (
              <div>
                <div className="px-3 py-1.5 text-[10px] font-black font-mono uppercase tracking-widest"
                  style={{ color: 'var(--text-muted)' }}>
                  ⌘ Navigation
                </div>
                {filteredPages.map((page) => {
                  const Icon = page.icon;
                  return (
                    <motion.button key={page.id} whileHover={{ x: 3 }}
                      onClick={() => { onNavigate(page.id); onClose(); }}
                      className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-all cursor-pointer group"
                      style={{ ':hover': { background: 'var(--bg-elevated)' } } as any}
>
                      <span className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0 transition-all"
                        style={{ background: 'color-mix(in oklab, var(--accent-gold) 12%, var(--bg-elevated))', color: 'var(--accent-gold)' }}>
                        <Icon className="w-4 h-4" />
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold text-[var(--text-primary)]">{page.label}</p>
                        <p className="text-[10px] text-[var(--text-muted)] truncate">{page.desc}</p>
                      </div>
                      <Zap className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" style={{ color: 'var(--accent-gold)' }} />
                    </motion.button>
                  );
                })}
              </div>
            )}

            {/* Components */}
            {filteredComps.length > 0 && (
              <div>
                <div className="px-3 py-1.5 text-[10px] font-black font-mono uppercase tracking-widest"
                  style={{ color: 'var(--text-muted)' }}>
                  ⚡ Components
                </div>
                {filteredComps.map(comp => {
                  const color = bandHex(comp.band as RiskBand);
                  return (
                    <motion.button key={`${comp.pn}-${comp.ref}`} whileHover={{ x: 3 }}
                      onClick={() => { onSelectComponent(comp); onNavigate('detail'); onClose(); }}
                      className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-all cursor-pointer group hover:bg-[var(--bg-elevated)]">
                      <div className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0 border"
                        style={{ background: `color-mix(in oklab, ${color} 14%, var(--bg-elevated))`, borderColor: `color-mix(in oklab, ${color} 30%, transparent)` }}>
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-black font-mono text-[var(--text-primary)]">{comp.pn}</p>
                        <p className="text-[10px] text-[var(--text-muted)] font-mono">{comp.ref} · qty {comp.qty}</p>
                      </div>
                      <RiskBadge band={comp.band} score={Math.round(comp.score * 100)} />
                    </motion.button>
                  );
                })}
              </div>
            )}

            {filteredPages.length === 0 && filteredComps.length === 0 && (
              <div className="py-12 text-center space-y-2">
                <p className="text-sm font-bold text-[var(--text-muted)]">No results for "{query}"</p>
                <p className="text-xs text-[var(--text-muted)]">Try part numbers, page names, or risk reasons</p>
              </div>
            )}
          </div>

          {/* Footer hint */}
          <div className="px-5 py-3 border-t flex items-center gap-3 text-[10px] font-mono text-[var(--text-muted)]"
            style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-elevated)' }}>
            <span>↑↓ navigate</span>
            <span>↵ select</span>
            <span>esc close</span>
            <span className="ml-auto gradient-text font-black">SENTINEL</span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
