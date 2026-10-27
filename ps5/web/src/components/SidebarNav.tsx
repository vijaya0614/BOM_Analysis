import React from 'react';
import type { PageId } from '../types';
import {
  LayoutDashboard, Upload, Layers, FileText,
  Building2, Settings, Download,
  ChevronLeft, ChevronRight, ShieldAlert, Zap
} from 'lucide-react';
import { motion } from 'framer-motion';

interface SidebarNavProps {
  activePage: PageId;
  onPageChange: (page: PageId) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onOpenCommandPalette: () => void;
}

const navItems: {
  id: PageId; label: string; icon: React.FC<{ className?: string }>; badge?: string;
}[] = [
  { id: 'upload',     label: 'BOM Materials',      icon: Upload },
  { id: 'dashboard',  label: 'Dashboard',          icon: LayoutDashboard },
  { id: 'components', label: 'Components',         icon: Layers },
  { id: 'detail',     label: 'Component Detail',   icon: FileText },
  { id: 'vendor',     label: 'Vendor Comparison',  icon: Building2, badge: 'LIVE' },
  { id: 'report',     label: 'AI Report',          icon: Download },
  { id: 'settings',   label: 'Settings',           icon: Settings },
];

export const SidebarNav: React.FC<SidebarNavProps> = ({
  activePage, onPageChange, isCollapsed, onToggleCollapse, onOpenCommandPalette
}) => {
  return (
    <aside
      className={`sticky top-0 h-screen flex flex-col justify-between transition-all duration-300 z-30 glass-panel border-r border-[var(--border-subtle)] ${
        isCollapsed ? 'w-[60px]' : 'w-60'
      }`}
      style={{
        background: 'var(--bg-surface)',
        boxShadow: '4px 0 24px rgba(0,0,0,0.08)',
      }}
    >
      {/* ── Logo strip */}
      <div>
        <div className="relative flex items-center justify-between px-3 py-4 border-b border-[var(--border-subtle)] overflow-hidden">
          {/* Glow behind logo */}
          <div className="absolute inset-0 pointer-events-none"
            style={{ background: 'radial-gradient(ellipse at 30% 50%, color-mix(in oklab, var(--accent-gold) 15%, transparent), transparent 70%)' }} />

          <div className="flex items-center gap-2.5 min-w-0 relative z-10">
            <motion.div
              whileHover={{ rotate: [0, -8, 8, 0] }}
              transition={{ duration: 0.5 }}
              className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg"
              style={{
                background: 'var(--gradient-brand)',
                boxShadow: '0 2px 12px color-mix(in oklab, var(--accent-gold) 40%, transparent)',
              }}
            >
              <ShieldAlert className="w-5 h-5 text-white" />
            </motion.div>
            {!isCollapsed && (
              <div className="min-w-0">
                <div className="text-sm font-black tracking-tight gradient-text leading-tight">SENTINEL</div>
                <div className="text-[9px] text-[var(--text-muted)] font-mono tracking-widest uppercase">BOM Risk Twin</div>
              </div>
            )}
          </div>

          <button
            onClick={onToggleCollapse}
            className="relative z-10 p-1 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all flex-shrink-0"
          >
            {isCollapsed
              ? <ChevronRight className="w-3.5 h-3.5" />
              : <ChevronLeft  className="w-3.5 h-3.5" />
            }
          </button>
        </div>

        {/* Status badge */}
        {!isCollapsed && (
          <div className="mx-3 mt-3 mb-1 px-3 py-1.5 rounded-lg flex items-center gap-2 text-[10px] font-mono"
            style={{
              background: 'color-mix(in oklab, var(--risk-low) 12%, var(--bg-elevated))',
              border: '1px solid color-mix(in oklab, var(--risk-low) 28%, transparent)',
            }}
          >
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: 'var(--risk-low)' }} />
            <span style={{ color: 'var(--risk-low)' }} className="font-semibold">System Nominal</span>
          </div>
        )}

        {/* Nav items */}
        <nav className="p-2 space-y-0.5 mt-2">
          {navItems.map(item => {
            const Icon = item.icon;
            const isActive = activePage === item.id;
            return (
              <motion.button
                key={item.id}
                onClick={() => onPageChange(item.id)}
                whileHover={{ x: isActive ? 0 : 2 }}
                transition={{ duration: 0.15 }}
                className={`relative w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all duration-200 group overflow-hidden ${
                  isActive ? 'text-white' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]'
                }`}
                title={isCollapsed ? item.label : undefined}
              >
                {isActive && (
                  <motion.div
                    layoutId="activeNav"
                    className="absolute inset-0 rounded-xl"
                    style={{ background: 'var(--gradient-brand)' }}
                    transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  />
                )}
                {isActive && (
                  <div className="absolute inset-0 rounded-xl opacity-40"
                    style={{ background: 'radial-gradient(ellipse at 20% 50%, rgba(255,255,255,0.3), transparent 60%)' }} />
                )}

                <Icon className={`w-4 h-4 z-10 flex-shrink-0 transition-all ${
                  isActive ? 'text-white' : 'text-[var(--text-muted)] group-hover:text-[var(--accent-gold)]'
                }`} />

                {!isCollapsed && (
                  <span className="z-10 truncate font-semibold tracking-wide">{item.label}</span>
                )}

                {!isCollapsed && item.badge && (
                  <span className="ml-auto z-10 px-1.5 py-0.5 rounded-md text-[8px] font-black tracking-widest"
                    style={{
                      background: 'color-mix(in oklab, var(--risk-low) 20%, var(--bg-elevated))',
                      color: 'var(--risk-low)',
                      border: '1px solid color-mix(in oklab, var(--risk-low) 35%, transparent)',
                    }}>
                    {item.badge}
                  </span>
                )}

                {!isCollapsed && isActive && (
                  <Zap className="ml-auto z-10 w-3 h-3 text-white/70" />
                )}
              </motion.button>
            );
          })}
        </nav>
      </div>

      {/* ── Command palette trigger */}
      <div className="p-3 border-t border-[var(--border-subtle)]">
        <motion.button
          onClick={onOpenCommandPalette}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          className="w-full flex items-center justify-between px-3 py-2 rounded-xl border text-xs transition-all cursor-pointer"
          style={{
            background: 'var(--bg-elevated)',
            borderColor: 'var(--border-subtle)',
            color: 'var(--text-muted)',
          }}
        >
          <span className="flex items-center gap-2 min-w-0">
            <kbd className="font-mono text-[10px] px-1.5 py-0.5 rounded-md bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--accent-gold)] font-bold">⌘K</kbd>
            {!isCollapsed && <span className="truncate">Search & Jump…</span>}
          </span>
        </motion.button>
      </div>
    </aside>
  );
};
