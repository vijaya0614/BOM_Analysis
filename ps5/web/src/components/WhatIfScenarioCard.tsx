import React, { useState, useEffect, useCallback } from 'react';
import { Sliders, ShieldCheck } from 'lucide-react';
import { SUBSTITUTE_API_BASE } from '../api';

interface Props {
  partNumber: string;
}

export const WhatIfScenarioCard: React.FC<Props> = ({ partNumber }) => {
  const [ambientTemp, setAmbientTemp] = useState<number>(55.0);
  const [coolingRth, setCoolingRth] = useState<number>(30.0);
  const voltage = 5.0;
  const [current, setCurrent] = useState<number>(0.35);
  const [volume, setVolume] = useState<number>(5000);
  const [scenarioResult, setScenarioResult] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const runComparison = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${SUBSTITUTE_API_BASE}/api/scenarios/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          part_number: partNumber,
          category: 'Power Management',
          baseline_inputs: {
            scenario_name: 'Baseline Operational Conditions',
            ambient_temperature_c: 25.0,
            operating_voltage: 5.0,
            operating_current: 0.25,
            thermal_resistance_c_per_w: 42.0,
            annual_production_volume: 5000,
          },
          scenario_inputs: {
            scenario_name: 'Proposed Stress & Mitigation Scenario',
            ambient_temperature_c: ambientTemp,
            operating_voltage: voltage,
            operating_current: current,
            thermal_resistance_c_per_w: coolingRth,
            annual_production_volume: volume,
          },
        }),
      });
      if (res.ok) {
        setScenarioResult(await res.json());
      }
    } catch {
      // offline fallback
    } finally {
      setLoading(false);
    }
  }, [partNumber, ambientTemp, voltage, current, coolingRth, volume]);

  useEffect(() => {
    runComparison();
  }, [runComparison]);

  if (loading && !scenarioResult) {
    return (
      <div className="glass-card p-6 rounded-2xl text-center text-xs text-[var(--text-muted)]">
        <div className="animate-spin w-5 h-5 border-2 border-[var(--accent-gold)] border-t-transparent rounded-full mx-auto mb-2" />
        Running what-if differential scenario…
      </div>
    );
  }

  const delta = scenarioResult?.comparison_deltas;

  return (
    <div className="glass-card p-6 rounded-2xl space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--accent-gold)]" style={{ background: 'color-mix(in oklab, var(--accent-gold) 15%, var(--bg-elevated))' }}>
            <Sliders className="w-4 h-4" />
          </span>
          <div>
            <span className="text-[10px] font-mono text-[var(--accent-gold)] uppercase tracking-widest font-semibold">
              Scenario Engine & Decision Support (Part 14)
            </span>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">
              Interactive What-If Scenario Sandbox: Baseline vs Proposed
            </h3>
          </div>
        </div>
        <span className="text-[11px] font-mono px-2.5 py-1 rounded-full border bg-[var(--bg-elevated)] border-[var(--border-subtle)] text-[var(--text-secondary)]">
          Live Differential Analysis
        </span>
      </div>

      <p className="text-xs text-[var(--text-secondary)]">
        Adjust operating temperature, cooling resistance, electrical stress, and volume to observe real-time impact
        on thermal junction margins, degradation rate, Arrhenius acceleration, and lifecycle financial exposure.
      </p>

      {/* Control sliders */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-3.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
        <div>
          <label className="text-[10px] font-mono text-[var(--text-muted)] uppercase block mb-1">
            Ambient Temp: {ambientTemp}°C
          </label>
          <input
            type="range"
            min="20"
            max="85"
            step="5"
            value={ambientTemp}
            onChange={(e) => setAmbientTemp(Number(e.target.value))}
            className="w-full accent-[var(--accent-gold)]"
          />
        </div>

        <div>
          <label className="text-[10px] font-mono text-[var(--text-muted)] uppercase block mb-1">
            Cooling R_θ: {coolingRth} °C/W
          </label>
          <input
            type="range"
            min="15"
            max="60"
            step="5"
            value={coolingRth}
            onChange={(e) => setCoolingRth(Number(e.target.value))}
            className="w-full accent-[var(--accent-gold)]"
          />
        </div>

        <div>
          <label className="text-[10px] font-mono text-[var(--text-muted)] uppercase block mb-1">
            Current Stress: {current} A
          </label>
          <input
            type="range"
            min="0.10"
            max="1.50"
            step="0.05"
            value={current}
            onChange={(e) => setCurrent(Number(e.target.value))}
            className="w-full accent-[var(--accent-gold)]"
          />
        </div>

        <div>
          <label className="text-[10px] font-mono text-[var(--text-muted)] uppercase block mb-1">
            Production Vol: {volume.toLocaleString()}
          </label>
          <input
            type="range"
            min="1000"
            max="20000"
            step="1000"
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
            className="w-full accent-[var(--accent-gold)]"
          />
        </div>
      </div>

      {/* Delta Comparison Cards */}
      {delta && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
            <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Thermal Margin Delta</span>
            <p className="text-lg font-black font-mono" style={{ color: delta.thermal_margin_delta_c >= 0 ? 'var(--risk-low)' : 'var(--risk-critical)' }}>
              {delta.thermal_margin_delta_c > 0 ? `+${delta.thermal_margin_delta_c.toFixed(1)}` : delta.thermal_margin_delta_c.toFixed(1)} °C
            </p>
            <p className="text-[10px] text-[var(--text-muted)] font-mono">
              Baseline: {scenarioResult.baseline_snapshot.thermal_margin_c}°C → {scenarioResult.scenario_snapshot.thermal_margin_c}°C
            </p>
          </div>

          <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
            <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Supply Pressure Delta</span>
            <p className="text-lg font-black font-mono" style={{ color: delta.spi_delta <= 0 ? 'var(--risk-low)' : 'var(--risk-critical)' }}>
              {delta.spi_delta > 0 ? `+${delta.spi_delta.toFixed(1)}` : delta.spi_delta.toFixed(1)} pts
            </p>
            <p className="text-[10px] text-[var(--text-muted)] font-mono">
              SPI: {scenarioResult.baseline_snapshot.supply_pressure_index} → {scenarioResult.scenario_snapshot.supply_pressure_index}
            </p>
          </div>

          <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
            <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Life Consumption Delta</span>
            <p className="text-lg font-black font-mono" style={{ color: delta.life_consumption_delta_pct <= 0 ? 'var(--risk-low)' : 'var(--risk-critical)' }}>
              {delta.life_consumption_delta_pct > 0 ? `+${delta.life_consumption_delta_pct.toFixed(0)}` : delta.life_consumption_delta_pct.toFixed(0)}%
            </p>
            <p className="text-[10px] text-[var(--text-muted)] font-mono">
              Arrhenius AF: {scenarioResult.scenario_snapshot.arrhenius_af.toFixed(1)}x
            </p>
          </div>

          <div className="p-3.5 rounded-xl border bg-[var(--bg-elevated)] border-[var(--border-subtle)] space-y-1">
            <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">Lifecycle Cost Delta</span>
            <p className="text-lg font-black font-mono" style={{ color: delta.total_lifecycle_cost_delta <= 0 ? 'var(--risk-low)' : 'var(--risk-critical)' }}>
              {delta.total_lifecycle_cost_delta > 0 ? `+$${Math.round(delta.total_lifecycle_cost_delta).toLocaleString()}` : `-$${Math.abs(Math.round(delta.total_lifecycle_cost_delta)).toLocaleString()}`}
            </p>
            <p className="text-[10px] text-[var(--text-muted)] font-mono">
              Net savings: ${Math.round(delta.net_savings).toLocaleString()}
            </p>
          </div>
        </div>
      )}

      {scenarioResult?.decision_recommendation && (
        <div className="p-3.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] flex items-start gap-2.5 text-xs">
          <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0 text-emerald-500" />
          <div>
            <span className="font-bold text-[var(--text-primary)]">Defensible Scenario Verdict: </span>
            <span className="text-[var(--text-secondary)]">{scenarioResult.decision_recommendation}</span>
          </div>
        </div>
      )}
    </div>
  );
};
