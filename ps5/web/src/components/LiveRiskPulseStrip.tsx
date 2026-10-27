import React, { useState } from 'react';
import { useHardwareTwin } from '../context/useHardwareTwin';
import { Activity, Cpu, Radio, Zap, Shield, TrendingUp } from 'lucide-react';
import type { LEDColorState } from '../types';

export const LiveRiskPulseStrip: React.FC<{ onSelectComponent?: (id: string) => void }> = ({ onSelectComponent }) => {
  const { isConnected, msgRate, activeCommand, leds, isFlashing, toggleConnection } = useHardwareTwin();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const getLedStyle = (state: LEDColorState): { bg: string; shadow: string } => {
    switch (state) {
      case 'white_blink': return { bg: '#FFFFFF', shadow: '0 0 12px #fff, 0 0 24px rgba(255,255,255,0.4)' };
      case 'red_blink':   return { bg: '#F87171', shadow: '0 0 12px #F87171, 0 0 24px rgba(248,113,113,0.4)' };
      case 'blue_pulse':  return { bg: '#60A5FA', shadow: '0 0 12px #60A5FA, 0 0 24px rgba(96,165,250,0.4)' };
      case 'green_solid': return { bg: '#34D399', shadow: '0 0 10px #34D399, 0 0 20px rgba(52,211,153,0.3)' };
      case 'yellow_solid':return { bg: '#FBBF24', shadow: '0 0 10px #FBBF24, 0 0 20px rgba(251,191,36,0.3)' };
      case 'red_solid':   return { bg: '#EF4444', shadow: '0 0 12px #EF4444, 0 0 24px rgba(239,68,68,0.4)' };
      default:            return { bg: '#374151', shadow: 'none' };
    }
  };

  const getLedAnimClass = (state: LEDColorState) => {
    switch (state) {
      case 'white_blink': return 'led-white-blink';
      case 'red_blink':   return 'led-red-blink';
      case 'blue_pulse':  return 'led-blue-pulse';
      default: return '';
    }
  };

  // Ticker items for the scrolling intel strip
  const tickerItems = [
    { icon: Shield, text: 'SENTINEL RISK ENGINE v2.4', accent: 'var(--accent-gold)' },
    { icon: Activity, text: `${msgRate} MSG/S · LIVE TELEMETRY`, accent: 'var(--risk-low)' },
    { icon: Zap, text: isConnected ? 'ESP32 RIG ACTIVE' : 'RIG OFFLINE', accent: isConnected ? 'var(--risk-low)' : 'var(--risk-critical)' },
    { icon: TrendingUp, text: `ACTIVE COMMAND: ${activeCommand}`, accent: 'var(--accent-blue)' },
    { icon: Cpu, text: 'DETERMINISTIC RULE ENGINE · NO LLM', accent: 'var(--accent-amber)' },
    { icon: Shield, text: 'SUPPLY CHAIN INTELLIGENCE PLATFORM', accent: 'var(--accent-gold)' },
  ];

  return (
    <div className={`sticky top-0 z-40 w-full transition-all duration-300 ${isCollapsed ? 'h-8' : ''}`}
      style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-subtle)', backdropFilter: 'blur(16px)' }}
    >
      {/* Scanline overlay */}
      <div className="absolute inset-0 scanline opacity-20 pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 flex items-center gap-3 h-10">

        {/* Connection status button */}
        <button
          onClick={toggleConnection}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-black font-mono flex-shrink-0 transition-all border cursor-pointer"
          style={{
            color: isConnected ? 'var(--risk-low)' : 'var(--risk-critical)',
            background: `color-mix(in oklab, ${isConnected ? 'var(--risk-low)' : 'var(--risk-critical)'} 12%, var(--bg-card))`,
            borderColor: `color-mix(in oklab, ${isConnected ? 'var(--risk-low)' : 'var(--risk-critical)'} 35%, transparent)`,
          }}
        >
          <Radio className={`w-3 h-3 ${isConnected ? 'animate-pulse' : ''}`} />
          <span className="hidden sm:inline">{isConnected ? 'LIVE' : 'OFFLINE'}</span>
        </button>

        {/* Scrolling ticker */}
        {!isCollapsed && (
          <div className="flex-1 overflow-hidden">
            <div className="flex ticker-track" style={{ width: 'max-content' }}>
              {[...tickerItems, ...tickerItems].map((item, i) => {
                const Icon = item.icon;
                return (
                  <span key={i} className="flex items-center gap-1.5 mr-8 text-[10px] font-mono font-bold flex-shrink-0 uppercase tracking-widest"
                    style={{ color: item.accent }}>
                    <Icon className="w-3 h-3 flex-shrink-0" />
                    {item.text}
                    <span className="mx-3 text-[var(--border-strong)]">◆</span>
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {/* LED array */}
        {!isCollapsed && (
          <div className={`hidden md:flex items-center gap-2 flex-shrink-0 ${isFlashing ? 'led-flash' : ''}`}>
            {leds.slice(0, 6).map(led => {
              const style = getLedStyle(led.state);
              const animClass = getLedAnimClass(led.state);
              return (
                <button
                  key={led.id}
                  onClick={() => onSelectComponent?.(led.id)}
                  title={`${led.label} · ${led.state}`}
                  className={`w-3 h-3 rounded-full cursor-pointer transition-all ${animClass}`}
                  style={{ backgroundColor: style.bg, boxShadow: style.shadow }}
                />
              );
            })}
          </div>
        )}

        {/* Collapse */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-all cursor-pointer"
          title={isCollapsed ? 'Expand' : 'Collapse'}
        >
          <span className="text-[10px] font-mono">{isCollapsed ? '▼' : '▲'}</span>
        </button>
      </div>
    </div>
  );
};