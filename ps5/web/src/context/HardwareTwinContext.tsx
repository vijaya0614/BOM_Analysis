import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { BOMComponent, LEDNode } from '../types';
import { HardwareTwinContext } from './hardware-twin-context';

const WS_URL = 'ws://127.0.0.1:8002';
const stateToLed = (state: string): LEDNode['state'] => ({
  SELECTED: 'white_blink', LOW: 'green_solid', MEDIUM: 'yellow_solid',
  HIGH: 'red_solid', CRITICAL: 'red_blink', RECOMMENDED: 'blue_pulse',
  ACTIVE: 'green_solid', OFF: 'off', NORMAL: 'off',
} as Record<string, LEDNode['state']>)[state] ?? 'off';

const nodesFromComponents = (components: BOMComponent[]): LEDNode[] => components.flatMap((component, index) => {
  const id = component.ref.split(',')[0].trim();
  if (!id) return [];
  return [{ id, ledIndex: index + 1, label: `${id} ${component.pn}`, state: 'off', mappedComponentPn: component.pn, riskBand: component.band }];
});

export const HardwareTwinProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const socket = useRef<WebSocket | null>(null);
  const reconnect = useRef<number | null>(null);
  const connectRef = useRef<() => void>(() => {});
  const latest = useRef<{ projectId: string; leds: LEDNode[] }>({ projectId: 'mini_smart_cooling_controller', leds: [] });
  const attempts = useRef(0);
  const [projectId, setProjectId] = useState('mini_smart_cooling_controller');
  const [leds, setLeds] = useState<LEDNode[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [activeCommand, setActiveCommand] = useState('WAITING_FOR_DEVICE');
  const [isFlashing, setIsFlashing] = useState(false);
  const [rawLogs, setRawLogs] = useState<string[]>(['Hardware Twin waiting for WebSocket service.']);
  const [msgRate, setMsgRate] = useState(0);

  const addLog = useCallback((message: string) => setRawLogs(previous => [`[${new Date().toLocaleTimeString()}] ${message}`, ...previous].slice(0, 30)), []);
  const flash = useCallback(() => { setIsFlashing(true); window.setTimeout(() => setIsFlashing(false), 600); }, []);
  const send = useCallback((message: Record<string, unknown>) => {
    if (!socket.current || socket.current.readyState !== WebSocket.OPEN) { addLog('Hardware synchronization unavailable: command was not sent.'); return; }
    const command: Record<string, unknown> = { ...message, project_id: projectId, command_id: `cmd_${crypto.randomUUID()}` };
    setActiveCommand(String(command['type']));
    socket.current.send(JSON.stringify(command));
    addLog(`WS TX: ${String(command['type'])}`);
    flash();
  }, [addLog, flash, projectId]);

  const connect = useCallback(() => {
    if (socket.current?.readyState === WebSocket.OPEN || socket.current?.readyState === WebSocket.CONNECTING) return;
    const ws = new WebSocket(WS_URL); socket.current = ws;
    ws.onopen = () => {
      attempts.current = 0; setIsConnected(true); addLog('WebSocket connected: simulator registered.');
      ws.send(JSON.stringify({ type: 'device_hello', device_id: 'PS5-WEB-SIMULATOR', device_mode: 'simulator', project_id: latest.current.projectId, components: latest.current.leds.map((led, index) => ({ id: led.id, mpn: led.mappedComponentPn, indicator: index })) }));
    };
    ws.onmessage = event => {
      const message = JSON.parse(event.data); setMsgRate(value => value + 1);
      if (message.type === 'state_update') {
        const states = message.state?.component_states ?? {};
        setLeds(previous => {
          const mapped = previous.map(led => ({ ...led, state: stateToLed(states[led.id] ?? 'NORMAL') }));
          const substituteNodes = Object.entries(states)
            .filter(([id, state]) => !mapped.some(led => led.id === id) && (state === 'RECOMMENDED' || state === 'ACTIVE'))
            .map(([id, state], index) => ({ id, ledIndex: mapped.length + index + 1, label: `${id} Substitute`, state: stateToLed(String(state)), mappedComponentPn: 'INSUFFICIENT_DATA' }));
          return [...mapped, ...substituteNodes];
        });
      }
      if (message.type === 'component_state_ack') addLog(`Device ACK: ${message.status}`);
      if (message.type === 'mapping_error' || message.type === 'protocol_error') addLog(`Synchronization error: ${message.message}`);
    };
    ws.onclose = () => {
      setIsConnected(false); addLog('WebSocket offline; retrying with backoff.');
      const delay = [1000, 2000, 5000, 10000][Math.min(attempts.current++, 3)];
      reconnect.current = window.setTimeout(() => connectRef.current(), delay);
    };
  }, [addLog]);

  connectRef.current = connect;

  useEffect(() => { connect(); return () => { if (reconnect.current) window.clearTimeout(reconnect.current); socket.current?.close(); }; }, [connect]);

  const syncProjectComponents = useCallback((nextProjectId: string, components: BOMComponent[]) => {
    const nextLeds = nodesFromComponents(components);
    latest.current = { projectId: nextProjectId, leds: nextLeds };
    setProjectId(nextProjectId); setLeds(nextLeds);
    if (socket.current?.readyState === WebSocket.OPEN) {
      socket.current.send(JSON.stringify({ type: 'device_hello', device_id: 'PS5-WEB-SIMULATOR', device_mode: 'simulator', project_id: nextProjectId, components: nextLeds.map((led, index) => ({ id: led.id, mpn: led.mappedComponentPn, indicator: index })) }));
    }
    addLog(`Loaded ${components.length} BOM components for ${nextProjectId}.`);
  }, [addLog]);
  const selectComponent = (componentId: string) => send({ type: 'select_component', component_id: componentId });
  const triggerRiskState = (componentId: string, riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL', score?: number, reasons: string[] = []) => send({ type: 'risk_update', component_id: componentId, risk_level: riskLevel, risk_score: score, risk_reasons: reasons });
  const recommendSubstitute = (originalId: string, substituteId = `${originalId}_ALT`, substituteMpn = 'INSUFFICIENT_DATA') => send({ type: 'alternative_recommended', original_component_id: originalId, substitute_component_id: substituteId, substitute_mpn: substituteMpn });
  const approveSubstitute = () => send({ type: 'approve_substitute' });
  const reset = () => send({ type: 'reset_device' });
  const executeProtocolSequence = () => { const id = leds[0]?.id; if (id) selectComponent(id); };
  const toggleConnection = () => { if (isConnected) socket.current?.close(); else connect(); };

  return <HardwareTwinContext.Provider value={{ isConnected, msgRate, activeCommand, leds, isFlashing, rawLogs, projectId, syncProjectComponents, selectComponent, triggerRiskState, recommendSubstitute, approveSubstitute, reset, executeProtocolSequence, toggleConnection }}>{children}</HardwareTwinContext.Provider>;
};
