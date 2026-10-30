import React, { useState, useEffect, useCallback } from 'react';
import { DollarSign } from 'lucide-react';
import { SUBSTITUTE_API_BASE } from '../api';
import type { CostComparisonData, CostScenarioItem } from '../types';

interface Props {
  partNumber: string;
  defaultVolume?: number;
  defaultPrice?: number;
}

export const EngineeringEconomicsCard: React.FC<Props> = ({
  partNumber,
  defaultVolume = 5000,
  defaultPrice = 3.50,
}) => {
  const [volume, setVolume] = useState<number>(defaultVolume);
  const [horizonYears, setHorizonYears] = useState<number>(5);
  const [unitPrice, setUnitPrice] = useState<number>(defaultPrice);
  const [costData, setCostData] = useState<CostComparisonData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchEconomics = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${SUBSTITUTE_API_BASE}/api/cost/scenarios`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          part_number: partNumber,
          annual_volume: volume,
          horizon_years: horizonYears,
          current_unit_price: unitPrice,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setCostData(data);
      }
    } catch {
      // offline fallback handled gracefully
    } finally {
      setLoading(false);
    }
  }, [partNumber, volume, horizonYears, unitPrice]);

  useEffect(() => {
    fetchEconomics();
  }, [fetchEconomics]);

  if (loading && !costData) {
    return (
      <div className="glass-card p-6 rounded-2xl text-center text-xs text-[var(--text-muted)]">
        <div className="animate-spin w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full mx-auto mb-2" />
        Evaluating lifecycle economics…
      </div>
    );
  }

  const scenarios: CostScenarioItem[] = costData?.scenarios ? Object.values(costData.scenarios) : [];

  return (
    <div className="glass-card p-6 rounded-2xl space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg flex items-center justify-center text-emerald-500" style={{ background: 'color-mix(in oklab, var(--risk-low) 15%, var(--bg-elevated))' }}>
            <DollarSign className="w-4 h-4" />
          </span>
          <div>
            <span className="text-[10px] font-mono text-emerald-500 uppercase tracking-widest font-semibold">
              Lifecycle Economics & Cost Optimization (Part 12)
            </span>
            <h3 className="text-sm font-bold text-[var(--text-primary)]">
              4-Strategy Lifecycle Cost & Break-Even Comparison
            </h3>
          </div>
        </div>
        {costData?.break_even_vs_substitute_units && (
          <span className="text-[11px] font-mono px-2.5 py-1 rounded-full border bg-[var(--bg-elevated)] border-[var(--border-subtle)] text-[var(--text-secondary)]">
            Break-even volume: {costData.break_even_vs_substitute_units.toLocaleString()} units
          </span>
        )}
      </div>

      {/* Interactive Parameters Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
        <div>
          <label className="text-[10px] font-mono text-[var(--text-muted)] uppercase block mb-1">
            Production Volume: {volume.toLocaleString()} units/yr
          </label>
          <input
            type="range"
            min="1000"
            max="25000"
            step="1000"
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
            className="w-full accent-[var(--accent-gold)]"
          />
        </div>

        <div>
          <label className="text-[10px] font-mono text-[var(--text-muted)] uppercase block mb-1">
            Analysis Horizon: {horizonYears} Years
          </label>
          <input
            type="range"
            min="1"
            max="10"
            step="1"
            value={horizonYears}
            onChange={(e) => setHorizonYears(Number(e.target.value))}
            className="w-full accent-[var(--accent-gold)]"
          />
        </div>

        <div>
          <label className="text-[10px] font-mono text-[var(--text-muted)] uppercase block mb-1">
            Current Unit Price: ${unitPrice.toFixed(2)}
          </label>
          <input
            type="range"
            min="0.50"
            max="25.00"
            step="0.50"
            value={unitPrice}
            onChange={(e) => setUnitPrice(Number(e.target.value))}
            className="w-full accent-[var(--accent-gold)]"
          />
        </div>
      </div>

      {/* 4 Strategy Comparison Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        {scenarios.map((s) => {
          const isBest = costData?.best_economic_strategy === s.strategy_name;
          return (
            <div
              key={s.strategy_key}
              className="p-4 rounded-xl border relative flex flex-col justify-between space-y-3"
              style={{
                background: isBest ? 'color-mix(in oklab, var(--risk-low) 8%, var(--bg-elevated))' : 'var(--bg-elevated)',
                borderColor: isBest ? 'color-mix(in oklab, var(--risk-low) 40%, transparent)' : 'var(--border-subtle)',
              }}
            >
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-mono uppercase text-[var(--text-muted)]">{s.strategy_key}</span>
                  {isBest && (
                    <span className="text-[9px] font-black px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-500 border border-emerald-500/30">
                      OPTIMAL STRATEGY
                    </span>
                  )}
                </div>
                <h4 className="text-xs font-bold text-[var(--text-primary)] leading-tight">{s.strategy_name}</h4>
                <div className="mt-2 font-mono">
                  <span className="text-xl font-black text-[var(--text-primary)]">
                    ${Math.round(s.total_lifecycle_cost).toLocaleString()}
                  </span>
                  <span className="text-[10px] text-[var(--text-muted)] block">
                    (${s.unit_cost_amortized.toFixed(2)} / unit amortized)
                  </span>
                </div>
              </div>

              <div className="space-y-1 pt-2 border-t border-[var(--border-subtle)] text-[11px] font-mono">
                <div className="flex justify-between text-[var(--text-muted)]">
                  <span>Parts Cost:</span>
                  <span className="text-[var(--text-primary)]">${Math.round(s.parts_purchase_cost).toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-[var(--text-muted)]">
                  <span>NRE / Qual:</span>
                  <span className="text-[var(--text-primary)]">
                    ${Math.round(s.redesign_engineering_cost + s.qualification_testing_cost).toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between text-[var(--text-muted)]">
                  <span>Inventory / Delay:</span>
                  <span className="text-[var(--text-primary)]">
                    ${Math.round(s.inventory_holding_cost + s.procurement_delay_cost).toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between text-[var(--text-muted)]">
                  <span>Disruption Risk:</span>
                  <span className="text-[var(--text-primary)]">${Math.round(s.disruption_risk_cost).toLocaleString()}</span>
                </div>
                <div className="flex justify-between font-bold pt-1 border-t border-[var(--border-subtle)]" style={{ color: s.net_savings_vs_baseline >= 0 ? 'var(--risk-low)' : 'var(--risk-critical)' }}>
                  <span>Net Savings:</span>
                  <span>
                    {s.net_savings_vs_baseline >= 0 ? `+$${Math.round(s.net_savings_vs_baseline).toLocaleString()}` : `-$${Math.abs(Math.round(s.net_savings_vs_baseline)).toLocaleString()}`}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {costData?.key_economic_tradeoffs && (
        <div className="p-3.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] space-y-1.5 text-xs">
          <span className="font-bold text-[var(--text-primary)]">Key Economic & Risk Trade-offs:</span>
          <ul className="space-y-1 text-[var(--text-secondary)] list-disc pl-4">
            {costData.key_economic_tradeoffs.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
