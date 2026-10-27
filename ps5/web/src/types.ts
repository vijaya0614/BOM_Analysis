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
  price?: number;
  sparkline_data?: number[];
  risk_factors?: RiskFactors;
  lifecycle_status?: 'ACTIVE' | 'NRND' | 'EOL' | 'SINGLE_SOURCE' | 'UNCONFIRMED' | 'INSUFFICIENT_DATA' | 'UNKNOWN';
  /** Manufacturing package/footprint when supplied by the BOM or catalog. */
  package?: string;
  /** Whether an independently qualified source is available. Null means unmeasured. */
  has_second_source?: boolean | null;
  evidence_status?: string;
  is_dynamically_inferred?: boolean;
  category?: 'Microcontroller' | 'Power Management' | 'Sensor' | 'Transistor' | 'Passive' | 'Interface';
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
  data_source: 'REAL_DISTRIBUTOR_DATA' | 'REAL_PUBLIC_SOURCE' | 'MISSING';
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
  classification: 'DROP_IN_CANDIDATE' | 'REQUIRES_REDESIGN' | 'INCOMPATIBLE';
  compatibility_score: number;
  confidence_score: number;
  supply_chain_score: number;
  explanation: string;
  lead_time_weeks?: number;
  stock?: number;
  has_second_source?: boolean;
  lifecycle?: string;
  checks?: CheckItem[];
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
