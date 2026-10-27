import { createContext } from 'react';
import type { LEDNode } from '../types';
import type { BOMComponent } from '../types';

export interface HardwareTwinContextType {
  isConnected: boolean;
  msgRate: number;
  activeCommand: string;
  leds: LEDNode[];
  isFlashing: boolean;
  rawLogs: string[];
  projectId: string;
  syncProjectComponents: (projectId: string, components: BOMComponent[]) => void;
  selectComponent: (id: string) => void;
  triggerRiskState: (id: string, riskLevel: 'LOW' | 'HIGH' | 'CRITICAL' | 'MEDIUM', score?: number, reasons?: string[]) => void;
  recommendSubstitute: (originalId: string, substituteId?: string, substituteMpn?: string) => void;
  approveSubstitute: () => void;
  reset: () => void;
  executeProtocolSequence: () => void;
  toggleConnection: () => void;
}

export const HardwareTwinContext = createContext<HardwareTwinContextType | undefined>(undefined);
