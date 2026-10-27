import React, { useId } from 'react';

export const PcbTraceBackground: React.FC = () => {
  const id = useId();
  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
      <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id={`${id}-g1`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%"   stopColor="var(--accent-gold)"   stopOpacity="1" />
            <stop offset="50%"  stopColor="var(--accent-amber)"  stopOpacity="1" />
            <stop offset="100%" stopColor="var(--accent-emerald)" stopOpacity="1" />
          </linearGradient>
          <linearGradient id={`${id}-g2`} x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%"   stopColor="var(--accent-blue)"  stopOpacity="1" />
            <stop offset="100%" stopColor="var(--accent-gold)"  stopOpacity="1" />
          </linearGradient>
          <linearGradient id={`${id}-g3`} x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor="var(--risk-low)"      stopOpacity="1" />
            <stop offset="100%" stopColor="var(--accent-blue)"   stopOpacity="1" />
          </linearGradient>
          <filter id={`${id}-glow`}>
            <feGaussianBlur stdDeviation="1" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Static base grid — subtle */}
        <g stroke="var(--pcb-trace)" strokeWidth="1" fill="none">
          <path d="M 50 0 V 220 H 320 V 480 H 720 V 920" />
          <path d="M 210 0 V 130 H 520 V 370 H 920 V 820" />
          <path d="M 0 310 H 190 V 620 H 620 V 1020" />
          <path d="M 820 0 V 260 H 1240 V 720 H 1640" />
          <path d="M 420 0 V 190 H 870 V 570 H 1420 V 920" />
          <path d="M 0 760 H 360 V 960 H 1120" />
          <path d="M 1020 0 V 310 H 1520 V 660" />
          <path d="M 0 510 H 260 V 810 H 920" />
          <path d="M 680 0 V 100 H 940 V 440 H 1280" />
        </g>

        {/* Animated flow 1 — brand gradient */}
        <g stroke={`url(#${id}-g1)`} strokeWidth="3" fill="none" strokeLinecap="round"
          strokeDasharray="36 164" style={{ animation: 'traceFlow 2.8s linear infinite' }}>
          <path d="M 50 0 V 220 H 320 V 480 H 720 V 920" />
          <path d="M 420 0 V 190 H 870 V 570 H 1420 V 920" style={{ animationDelay: '0.9s' }} />
        </g>

        {/* Animated flow 2 — blue gradient */}
        <g stroke={`url(#${id}-g2)`} strokeWidth="2.5" fill="none" strokeLinecap="round"
          strokeDasharray="28 172" style={{ animation: 'traceFlow 3.2s linear infinite', animationDelay: '0.7s' }}>
          <path d="M 210 0 V 130 H 520 V 370 H 920 V 820" />
          <path d="M 820 0 V 260 H 1240 V 720 H 1640" style={{ animationDelay: '1.4s' }} />
        </g>

        {/* Animated flow 3 — green gradient */}
        <g stroke={`url(#${id}-g3)`} strokeWidth="2.5" fill="none" strokeLinecap="round"
          strokeDasharray="22 178" style={{ animation: 'traceFlow 3.8s linear infinite', animationDelay: '1.2s' }}>
          <path d="M 0 310 H 190 V 620 H 620 V 1020" />
          <path d="M 0 510 H 260 V 810 H 920" style={{ animationDelay: '2.1s' }} />
        </g>

        {/* Junction pads */}
        <g fill="var(--border-strong)" filter={`url(#${id}-glow)`}>
          {[[320,220],[520,130],[720,480],[190,620],[1240,260],[870,190],[360,960],[920,820],[940,440]].map(([cx,cy],i) => (
            <circle key={i} cx={cx} cy={cy} r="3.5" />
          ))}
        </g>

        {/* Pulsing hot nodes */}
        {[
          [320, 220, 'var(--accent-amber)'],
          [720, 480, 'var(--risk-critical)'],
          [190, 620, 'var(--risk-low)'],
          [1240, 260, 'var(--accent-blue)'],
          [870, 190, 'var(--accent-gold)'],
        ].map(([cx, cy, col], i) => (
          <circle key={i} cx={cx as number} cy={cy as number} r="7" fill={col as string} opacity="0.18"
            style={{ animation: `ping ${3 + i * 0.6}s cubic-bezier(0,0,0.2,1) infinite`, animationDelay: `${i * 0.4}s` }} />
        ))}
      </svg>

      <style>{`
        @keyframes ping {
          75%, 100% { transform: scale(2.8); opacity: 0; }
        }
      `}</style>
    </div>
  );
};