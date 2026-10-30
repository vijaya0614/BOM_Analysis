export type RiskBand = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT_DATA';

/** Per-factor risk contributions from the engine (0–100). Null means unmeasured. */
export interface RiskFactors {
  lifecycle: number | null;
  sourcing: number | null;
  lead_time: number | null;
  stock: number | null;
  criticality: number | null;
  composite: number | null;
}

export interface BOMComponent {
  pn: string;
  ref: string;
  qty: number;
  band: RiskBand;
  score: number | null;
  exp: number | null;
  conf: number;
  criticality?: string;
  reasons: string[];
  component_id?: string;
  substitute_lookup_id?: string;
  catalog_status?: string;
  // Extra detailed mock/live fields
  lead_time_weeks?: number;
  stock_level?: number;
  stock?: number;
  description?: string;
  price?: number;
  sparkline_data?: number[];
  risk_factors?: RiskFactors;
  lifecycle_status?: 'ACTIVE' | 'NRND' | 'EOL' | 'SINGLE_SOURCE' | 'UNCONFIRMED' | 'INSUFFICIENT_DATA' | 'UNKNOWN';
  /** Manufacturing package/footprint when supplied by the BOM or catalog. */
  package?: string;
  /** Whether an independently qualified source is available. Null means unmeasured. */
  has_second_source?: boolean | null;
  evidence_status?: string;
  source_quality?: {
    vendor_supply?: string;
    vendor_records_used?: number;
    vendor_records_excluded?: number;
    lifecycle?: string;
    conflicts?: Array<{ field_name?: string; value_a?: string; value_b?: string }>;
  };
  is_dynamically_inferred?: boolean;
  category?: 'Microcontroller' | 'Power Management' | 'Sensor' | 'Transistor' | 'Passive' | 'Interface';
}

export interface DemoSampleProject {
  id: string;
  name: string;
  bom_lines: number;
  unique_mpns: number;
  total_quantity: number;
  unresolved_lines: number;
}

export interface ProviderHealth {
  provider: string;
  configured: boolean;
  authentication_status: string;
  product_access_ready?: boolean;
  environment?: string;
  api_base?: string;
  scope?: string;
  quota_status?: string;
  last_error_category?: string | null;
  last_success?: string | null;
  last_error?: string | null;
}

export interface IndustryStatus {
  incoming_files: number;
  documents_registered: number;
  bom_lines: number;
  unresolved_mpns: number;
  latest_manifest: string;
  data_source: 'REAL_PUBLIC_SOURCE';
  providers: { digikey: ProviderHealth; nexar: ProviderHealth; mouser: ProviderHealth };
}

export interface IndustryImportResult {
  import_id: string;
  dry_run: boolean;
  files_detected: number;
  products_detected: string[];
  bom_files: number;
  bom_rows: number;
  documents_registered: number;
  duplicates: number;
  warnings: string[];
  errors: string[];
  manifest: string;
}

export interface IndustryBom {
  product_id: string;
  project_key: string;
  name: string;
  manufacturer: string;
  bom_lines: number;
  unique_mpns: number;
  source_documents: number;
  source_document: string;
  enriched_components: number;
  data_source: 'REAL_PUBLIC_SOURCE';
}

export interface IndustryBomSession extends IndustryBom {
  status: 'READY';
  source: 'Industry Dataset';
  enrichment_status: string;
  last_updated: string;
}

export interface IndustryVendorRecord {
  vendor_name: string;
  vendor_part_number: string;
  region: string;
  country: string;
  stock_quantity: string;
  stock_status: string;
  lead_time_days: string;
  unit_price: string;
  currency: string;
  authorized: string;
  last_updated: string;
  retrieved_at?: string;
  expires_at?: string;
  retrieval_state?: 'LIVE' | 'CACHED' | 'STALE' | 'UNKNOWN';
  provider?: string;
  data_provenance: string;
  confidence: string;
}

export interface IndustryComponentData {
  mpn: string;
  model?: { manufacturer?: string; description?: string; package?: string; datasheet_url?: string; lifecycle_status?: string } | null;
  vendor_records: IndustryVendorRecord[];
  documents?: Array<{ title: string; url: string; document_type: string; confidence: string }>;
  lifecycle_evidence: Array<{ status: string; confidence: string; source_id: string }>;
  technical_specs: Array<{ parameter_name: string; nominal_value: string; provenance: string }>;
  provenance: Array<{ data_provenance: string; confidence: string; retrieved_at: string }>;
  data_source: 'REAL_DISTRIBUTOR_DATA' | 'REAL_PUBLIC_SOURCE' | 'CURATED_STATIC_DEMO_DATA' | 'SYNTHETIC_DEMO_DATA' | 'MISSING';
}

export interface IndustryComponentSummary {
  mpn: string;
  manufacturer: string;
  description: string;
  package: string;
  lifecycle_status: string;
}

export interface EnrichmentRunResult {
  timestamp?: string;
  resolved: number;
  unresolved: number;
  cache_hits: number;
  api_calls: number;
  errors: number;
  digikey_matches: number;
  nexar_matches: number;
  mouser_matches?: number;
  vendor_records: number;
  providers?: Record<string, { attempted: number; resolved: number; errors: number; last_error: string }>;
  failed?: Array<{ mpn: string; provider: string; error: string }>;
}

export interface RiskReportDashboard {
  name: string;
  source_bom?: string;
  overall: RiskBand;
  max_score: number | null;
  avg_score: number | null;
  completeness: number;
  total_parts: number;
  total_units: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  input_integrity?: {
    status: string;
    source_bom?: string;
    selected_revision?: string;
    revision_verified?: boolean;
    source_observed_at?: string[] | string;
    limitations?: string[];
  };
  source_quality?: {
    vendor_supply_current_parts?: number;
    vendor_supply_stale_parts?: number;
    vendor_supply_unknown_parts?: number;
    parts_with_unresolved_conflicts?: number;
  };
  parts: BOMComponent[];
}

export interface CheckItem {
  parameter: string;
  original: any;
  candidate: any;
  status: 'MATCHED' | 'MISMATCHED' | 'UNKNOWN';
}

export interface SubstituteCandidate {
  rank: number;
  part_number: string;
  classification: 'DROP_IN_CANDIDATE' | 'REQUIRES_REDESIGN' | 'INCOMPATIBLE' | 'INSUFFICIENT_EVIDENCE';
  compatibility_score: number;
  confidence_score: number;
  supply_chain_score: number;
  explanation: string;
  lead_time_weeks?: number;
  stock?: number;
  has_second_source?: boolean;
  lifecycle?: string;
  checks?: CheckItem[];
  drop_in_evidence?: DropInEvidence;
  evidence_summary?: {
    matched_parameters?: string[];
    mismatched_parameters?: string[];
    unknown_parameters?: string[];
  };
  component?: {
    component_id: string;
    part_number: string;
    manufacturer?: string;
    category?: string;
    package?: string;
  };
  reliability_outlook?: {
    status: string;
    outcome: 'IMPROVED' | 'UNCHANGED' | 'DEGRADED' | 'INSUFFICIENT_DATA';
    confidence: string;
    reason: string;
    evidence: Array<{
      factor: string;
      original: string;
      candidate: string;
      reason: string;
    }>;
    limitations: string[];
  };
  final_engineering_recommendation?: {
    status: string;
    recommendation: string;
    reason: string;
    confidence: string;
    limitations: string[];
  };
}

export interface DropInEvidence {
  status: 'SUPPORTED' | 'INSUFFICIENT_DATA';
  unknown_parameters: string[];
  limitations: string[];
  requirements: Array<{
    parameter: string;
    status: string;
    original: { value: unknown; status: string; source?: Record<string, unknown> | null };
    candidate: { value: unknown; status: string; source?: Record<string, unknown> | null };
  }>;
}

export interface EvidenceRecord {
  source_id: string;
  source_title: string;
  source_type: string;
  manufacturer: string;
  source_url: string;
  source_page: string;
  parameter_supported: string;
  evidence_summary: string;
  evidence_quality: string;
  confidence: string;
  notes: string;
}

export interface ProfileField {
  field: string;
  label: string;
  value: string;
  unit: string;
  status: string;
  confidence: string;
  source_document: string;
  source_page: string;
}

export interface ReliabilityRecord {
  fit: string;
  mtbf: string;
  mttf: string;
  reliability_metric_type: string;
  test_temperature: string;
  usage_temperature: string;
  test_duration_hours: string;
  sample_size: string;
  failures: string;
  confidence_level: string;
  reliability_test_type: string;
  qualification_standard: string;
  reliability_source: string;
  source_document: string;
  source_page: string;
  data_confidence: string;
}

export interface DegradationRecord {
  degradation_parameter: string;
  initial_value: string;
  initial_unit: string;
  degradation_direction: string;
  degradation_model: string;
  degradation_rate: string;
  rate_unit: string;
  stress_factor: string;
  temperature_dependency: string;
  operating_boundary: string;
  boundary_unit: string;
  failure_indicator: string;
  evidence_type: string;
  source_document: string;
  source_page: string;
  data_confidence: string;
}

export interface OperatingMarginRecord {
  parameter: string;
  measured_or_assumed_operating_value: string;
  allowed_or_rated_boundary: string;
  margin: string;
  unit: string;
  source: string;
  confidence: string;
}

export interface ComponentEvidenceAnalysis {
  status: string;
  confidence: string;
  data: {
    profile: {
      identity: {
        mpn: string;
        manufacturer: string;
        component_type: string;
        description: string;
        package: string;
      };
      electrical_profile: ProfileField[];
      operating_profile?: ProfileField[];
      tolerance_profile?: ProfileField[];
      component_specific_parameters: ProfileField[];
      relevant_parameter: string;
      datasheet_source: string;
      source_document: string;
      source_page: string;
    } | null;
    evidence: EvidenceRecord[];
    reliability: {
      status: string;
      confidence: string;
      data: ReliabilityRecord[];
      summary: string;
      limitations: string[];
    };
    degradation: {
      status: string;
      confidence: string;
      data: DegradationRecord[];
      summary: string;
      limitations: string[];
    };
    operating_margins: {
      status: string;
      confidence: string;
      data: OperatingMarginRecord[];
      limitations: string[];
    };
    degradation_scenario: {
      status: string;
      mode: string;
      timeline: Array<{
        time: string;
        parameter: string;
        condition: string;
        operating_margin: string;
        risk_outlook: string;
        recommended_action: string;
      }>;
      message: string;
      limitations: string[];
    };
    downstream_impact: {
      status: string;
      confidence: string;
      data: Array<unknown>;
      limitations: string[];
    };
  };
  limitations: string[];
  resolution: string[];
}

export interface Vendor {
  id: string;
  name: string;
  region: 'US' | 'EU' | 'APAC';
  stock: number;
  lead_time_days: number;
  unit_price: number;
  reliability: number; // 0-100
  fill_rate: number; // 0-100%
  counterfeit_incidence: number; // 0-100% lower is better
  recommended?: boolean;
  rationale?: string;
}

export type LEDColorState = 
  | 'off'
  | 'white_blink'
  | 'red_blink'
  | 'blue_pulse'
  | 'green_solid'
  | 'yellow_solid'
  | 'red_solid';

export interface LEDNode {
  id: string; // e.g. "C1", "C2", "U1", "LM2596"
  ledIndex: number; // 1 to 8
  label: string;
  state: LEDColorState;
  mappedComponentPn?: string;
  riskBand?: RiskBand;
}

export type PageId = 
  | 'dashboard'
  | 'upload'
  | 'components'
  | 'detail'
  | 'fmea'
  | 'decision'
  | 'vendor'
  | 'settings'
  | 'report';

export interface DecisionPathEdge {
  relationship_type?: string;
  function?: string;
  confidence?: string;
  source?: string;
}

export interface CandidateDecision {
  candidate_id: string;
  candidate_part_number: string;
  classification: string;
  drop_in_evidence?: DropInEvidence;
  candidate_generation: SubstituteCandidate;
  vendor_status: string;
  vendor_gate: Record<string, unknown>;
  engineering_gates: Array<{ parameter: string; status: string; reason: string; [key: string]: unknown }>;
  reliability_outlook: { outcome?: string; confidence?: string; reason?: string; limitations?: string[] };
  downstream_impact: {
    status: string;
    confidence?: string;
    data: Array<{ node_id: string; status: string; path: string[]; path_edges?: DecisionPathEdge[]; source?: string }>;
    limitations?: string[];
  };
  overall_status: string;
  reason_codes: string[];
  hard_gate_failures: string[];
  rank: number | null;
}

export interface CandidateDecisionResponse {
  product_id: string;
  target_component_id: string;
  status: string;
  risk_trigger: { status: string; triggered?: boolean; reason_codes?: string[]; limitations?: string[] };
  candidate_generation: { original?: { part_number?: string; manufacturer?: string; category?: string; refdes?: string }; candidates?: SubstituteCandidate[] };
  ranking_rule: string;
  candidates: CandidateDecision[];
  reason_codes?: string[];
}

// ── PS5 Comprehensive Engineering Interfaces ──────────────────────────────────
export interface HorizonForecast {
  years: number;
  unavailability_probability: number;
  risk_category: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
}

export interface ObsolescenceForecastData {
  part_number: string;
  category: string;
  current_status: string;
  years_in_market: number;
  weibull_shape_beta: number;
  weibull_scale_eta_years: number;
  methodology: string;
  horizons: Record<string, HorizonForecast>;
  is_high_risk: boolean;
  recommended_mitigation: string;
  assumptions: string[];
}

export interface ToleranceCheckItem {
  parameter: string;
  threshold_rule: string;
  measured_value: string;
  status: 'PASS' | 'FAIL' | 'UNKNOWN';
  detail: string;
}

export interface MarketSupplyRiskData {
  part_number: string;
  available_stock: number | null;
  weekly_demand: number | null;
  inventory_coverage_weeks: number | null;
  estimated_lead_time_weeks: number | null;
  available_procurement_window_weeks: number | null;
  lead_time_margin_weeks: number | null;
  can_arrive_before_deadline: boolean | null;
  hhi_concentration: number | null;
  hhi_tier: string;
  supply_pressure_index: number;
  spi_risk_category: string;
  tolerance_checks: Array<{
    parameter: string;
    configured_threshold: unknown;
    observed_value: unknown;
    status: 'PASS' | 'FAIL' | 'UNKNOWN';
    explanation: string;
  }>;
}

export interface MissionPhaseResult {
  phase_name: string;
  annual_hours: number;
  ambient_temp_c: number;
  power_watts: number;
  temp_rise_delta_c: number;
  junction_temp_c: number;
  arrhenius_af: number;
  phase_damage_fraction: number;
  thermal_margin_c: number;
  is_junction_temp_exceeded: boolean;
}

export interface MitigationComparison {
  strategy: string;
  peak_junction_temp_c: number;
  thermal_margin_c: number;
  projected_life_years: number;
  life_consumption_pct: number;
  adequate_for_target: boolean;
}

export interface MissionProfileData {
  component_name: string;
  part_number: string;
  rated_temp_max_c: number;
  thermal_resistance_c_per_w: number;
  peak_junction_temp_c: number;
  worst_thermal_margin_c: number;
  annual_cumulative_damage_d: number;
  projected_life_years: number;
  life_consumption_over_target_pct: number;
  is_service_life_adequate: boolean;
  phases: MissionPhaseResult[];
  mitigation_comparisons: MitigationComparison[];
  assumptions: string[];
}

export interface SensitivityParam {
  parameter: string;
  sensitivity_derivative: number;
  variance_contribution_pct: number;
}

export interface HistogramBin {
  bin_start: number;
  bin_end: number;
  bin_center: number;
  count: number;
  frequency: number;
}

export interface ToleranceAnalysisData {
  analysis_name: string;
  nominal_output: number;
  output_unit: string;
  worst_case_min: number;
  worst_case_max: number;
  rss_sigma: number;
  rss_3sigma_min: number;
  rss_3sigma_max: number;
  monte_carlo_samples: number;
  monte_carlo_mean: number;
  monte_carlo_std: number;
  monte_carlo_violation_rate_pct: number;
  spec_min_limit: number | null;
  spec_max_limit: number | null;
  histogram_bins: HistogramBin[];
  sensitivity_ranking: SensitivityParam[];
  assumptions: string[];
}

export interface FmeaEntry {
  item_name: string;
  function: string;
  failure_mode: string;
  local_effect: string;
  end_system_effect: string;
  potential_cause: string;
  prevention_controls: string;
  detection_controls: string;
  severity: number;
  occurrence: number;
  detection: number;
  rpn: number;
  action_priority: 'HIGH' | 'MEDIUM' | 'LOW';
  recommended_action: string;
  residual_severity?: number;
  residual_occurrence?: number;
  residual_detection?: number;
  residual_rpn?: number;
}

export interface CostScenarioItem {
  strategy_key: string;
  strategy_name: string;
  parts_purchase_cost: number;
  redesign_engineering_cost: number;
  qualification_testing_cost: number;
  inventory_holding_cost: number;
  procurement_delay_cost: number;
  disruption_risk_cost: number;
  total_lifecycle_cost: number;
  unit_cost_amortized: number;
  net_savings_vs_baseline: number;
  savings_pct_vs_baseline: number;
}

export interface CostComparisonData {
  part_number: string;
  production_volume: number;
  scenarios: Record<string, CostScenarioItem>;
  break_even_vs_substitute_units: number | null;
  best_economic_strategy: string;
  key_economic_tradeoffs: string[];
}

export interface DistributorQuote {
  vendor_name: string;
  stock: number;
  unit_price: number;
  moq: number;
  lead_time_weeks: number;
  packaging: string;
  stock_share_pct: number;
  authorized?: boolean | null;
  currency?: string;
  retrieval_state?: 'LIVE' | 'CACHED' | 'STALE' | 'UNKNOWN';
  data_provenance?: string;
}

export interface GeologicalAvailability {
  primary_fab_country: string;
  primary_fab_city: string;
  primary_fab_name: string;
  seismic_risk_score: number;
  water_stress_level: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL' | string;
  tsunami_hazard_zone: boolean;
  secondary_packaging_country: string;
  secondary_packaging_name: string;
  redundant_site_qualified: boolean;
  rare_earth_dependence_pct: number;
  geopolitical_exposure_score: number;
  geopolitical_risk_tier: 'LOW' | 'MODERATE' | 'ELEVATED' | 'CRITICAL' | string;
  regional_stock_americas_pct: number;
  regional_stock_emea_pct: number;
  regional_stock_apac_pct: number;
  regional_stock_domestic_pct: number;
}

export interface VolumePriceBreak {
  tier: string;
  qty: number;
  unit_price: number;
  savings_pct: number;
}

export interface MarketSaturationData {
  saturation_index_pct: number;
  sourcing_status: 'SINGLE_SOURCE_PROPRIETARY' | 'DUAL_SOURCED' | 'MULTI_SOURCE_COMMODITY' | string;
  qualified_manufacturers: string[];
  hhi_index: number;
  supply_pressure_index: number;
  counterfeit_risk_score: number;
  counterfeit_risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | string;
  distributors: DistributorQuote[];
  volume_price_breaks: VolumePriceBreak[];
  price_trend_12m: { month: string; unit_price: number; spot_market_price?: number }[];
  lead_time_trend_12m: { month: string; lead_time_weeks: number; target_lead_time_weeks?: number }[];
}

export interface LifecycleDetails {
  lifecycle_status: 'ACTIVE' | 'NRND' | 'EOL' | 'OBSOLETE' | 'PRE_RELEASE' | string;
  introduction_year: number;
  expected_eol_year: number;
  ltb_date: string | null;
  lts_date: string | null;
  years_remaining: number;
  phase_progress_pct: number;
  weibull_shape_beta: number;
  weibull_scale_eta_years: number;
}

export interface ResilienceRadar {
  sourcing_security: number;
  lead_time_resilience: number;
  price_stability: number;
  lifecycle_longevity: number;
  geopolitical_safety: number;
  geological_hardiness: number;
}

export interface ComponentVendorIntelligence {
  part_number: string;
  manufacturer: string;
  description: string;
  category: string;
  lifecycle: LifecycleDetails;
  geological: GeologicalAvailability;
  market_saturation: MarketSaturationData;
  resilience: ResilienceRadar;
  normalized_specs: { parameter_name: string; nominal_value: string }[];
  document_links: { title: string; url: string }[];
  data_provenance?: string;
  data_source?: string;
  vendor_records?: Array<{
    vendor_name: string;
    vendor_part_number: string | null;
    stock_quantity: number;
    lead_time_days: number;
    unit_price: number;
    currency: string;
    moq?: number;
    packaging?: string;
    authorized?: boolean | null;
    retrieval_state?: 'LIVE' | 'CACHED' | 'STALE' | 'UNKNOWN';
    data_provenance: string;
  }>;
}
