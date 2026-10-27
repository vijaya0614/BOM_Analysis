import { useContext } from 'react';
import { HardwareTwinContext } from './hardware-twin-context';

export const useHardwareTwin = () => {
  const ctx = useContext(HardwareTwinContext);
  if (!ctx) throw new Error('useHardwareTwin must be used within HardwareTwinProvider');
  return ctx;
};
