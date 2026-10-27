import sys
import os
import tempfile
import shutil

# Ensure src is in python path
sys.path.insert(0, os.path.abspath("."))

from tests.test_bom_parser import (
    test_expand_reference_token_range,
    test_expand_reference_range_combined,
    test_parse_bom_sample_burglar_alarm
)
from tests.test_risk_merger import test_derive_criticality, test_merge_risk_data
from tests.test_risk_engine import (
    test_band_from_score,
    test_reed_switch_compounding_override,
    test_low_risk_active_resistor,
    test_missing_data_transparency_reason,
    test_fuzzy_ahp_weights_replace_static_priorities,
    test_weibull_conditional_probability_increases_with_horizon,
    test_weibull_obsolescence_uses_lifecycle_and_history,
    test_compute_risk_records_five_year_obsolescence_probability,
)
from tests.test_risk_analyzer import (
    test_prioritization_severity_vs_exposure,
    test_group_by_band,
    test_compute_summary_metrics
)
from tests.test_component_intelligence import (
    test_exact_mpn_lookup_for_all_supported_categories,
    test_missing_mpn_returns_not_found,
    test_missing_tolerance_is_not_fabricated,
    test_missing_reliability_data_is_explicit,
    test_high_confidence_evidence_is_exposed,
    test_missing_degradation_data_is_explicit,
    test_class_level_degradation_scenario_is_labeled,
    test_reliability_outlook_uses_available_evidence_only,
    test_substitute_integration_keeps_existing_logic_and_adds_reliability_layer,
    test_bom_specific_identifier_without_dataset_evidence_stays_unavailable,
    test_no_fabricated_exact_mpn_rate_is_returned,
    test_operating_margin_requires_bom_specific_operating_conditions,
    test_safe_recommendation_requires_reliability_evidence_for_both_parts,
)
from tests.test_hardware_ws import (
    test_device_registration_and_component_mapping,
    test_selection_uses_canonical_selected_state,
    test_risk_colors_are_semantic_and_centralized,
    test_substitute_turns_original_off_and_replacement_recommended_then_active,
    test_unknown_component_and_invalid_message_are_rejected,
    test_manual_and_simulator_ack_but_physical_requires_real_ack,
)
from tests.test_evidence_component_adapter import test_evidence_adapter_preserves_unknown_values_without_synthetic_supply_data
from tests.test_bom_schemas import (
    test_bom_component_accepts_enumerated_fields,
    test_bom_component_rejects_invalid_criticality_and_lifecycle,
    test_substitute_component_exposes_parametric_specs,
    test_redesign_cost_totals_requalification_and_holding,
    test_bill_of_materials_rolls_up_extended_cost,
    test_sqlalchemy_round_trip_with_pydantic,
)
from tests.test_redesign_decision import (
    test_compare_strategies_returns_three_npvs,
    test_low_holding_prefers_last_time_buy,
    test_design_refresh_wins_when_unit_cost_falls_and_nre_is_shared_in_mip,
    test_integer_program_matches_independent_argmin,
    test_engineering_capacity_blocks_requalification,
    test_from_bom_component_and_redesign_cost,
)
from tests.test_reliability_stress import (
    test_part_stress_is_not_linear_mtbf_scaling,
    test_capacitor_voltage_and_temperature_raise_failure_rate,
    test_environment_and_thermal_derating_corrections,
    test_switching_activity_and_recovery_guardbands,
    test_analyze_part_stress_dispatch,
)
from tests.test_find_substitutes import (
    test_hard_filter_requires_exact_package_and_pin_count,
    test_pipeline_returns_top_10_classified_drop_in_or_redesign,
    test_find_substitutes_requires_jwt,
    test_fastapi_find_substitutes_get_and_post,
    test_find_substitutes_rate_limited_per_user,
    test_unhandled_errors_go_to_sentry_with_generic_500,
    test_catalog_pin_counts_are_stable_for_known_packages,
)
from tests.test_comprehensive_edge_cases import (
    test_risk_engine_zero_stock_edge_case,
    test_risk_engine_infinite_and_missing_lead_time_edge_cases,
    test_risk_engine_conflicting_multi_attribute_scores,
    test_risk_engine_historical_data_mapping_and_fitting,
    test_risk_engine_normalization_functions,
    test_redesign_decision_pv_and_annuity_edge_cases,
    test_redesign_decision_mitigation_part_validations,
    test_redesign_decision_unfeasible_strategy_edge_cases,
    test_redesign_decision_optimization_edge_cases,
    test_redesign_decision_optimize_from_bom_roundtrip,
    test_reliability_stress_temperature_and_stress_errors,
    test_reliability_stress_junction_temp_variations,
    test_reliability_stress_capacitor_styles_and_series_resistance,
    test_reliability_stress_semiconductor_styles_and_ratings,
    test_reliability_stress_as_dict_serialization,
)
from tests.providers.test_providers import (
    test_digikey_provider_health,
    test_nexar_provider_health,
    test_digikey_mock_response_parsing,
    test_nexar_mock_response_parsing,
)
from tests.industry_data.test_industry_data import (
    test_normalize_mpn,
    test_resolve_mpn,
    test_data_quality_report,
    test_vendor_feasibility_insufficient_data,
)


class TmpPath:
    def __init__(self, dir_path):
        self.dir_path = dir_path
    def __truediv__(self, other):
        class TmpFile:
            def __init__(self, file_path):
                self.file_path = file_path
            def write_text(self, text, encoding="utf-8"):
                with open(self.file_path, "w", encoding=encoding) as f:
                    f.write(text)
            def __str__(self):
                return self.file_path
            def __fspath__(self):
                return self.file_path
        return TmpFile(os.path.join(self.dir_path, other))
    def __str__(self):
        return self.dir_path
    def __fspath__(self):
        return self.dir_path

def run_all_tests():
    print("Running BOM Risk Engine Unit Tests...")
    temp_dir = tempfile.mkdtemp()
    tmp = TmpPath(temp_dir)
    
    tests = [
        ("test_expand_reference_token_range", test_expand_reference_token_range),
        ("test_expand_reference_range_combined", test_expand_reference_range_combined),
        ("test_parse_bom_sample_burglar_alarm", lambda: test_parse_bom_sample_burglar_alarm(tmp)),
        ("test_derive_criticality", test_derive_criticality),
        ("test_merge_risk_data", lambda: test_merge_risk_data(tmp)),
        ("test_band_from_score", test_band_from_score),
        ("test_reed_switch_compounding_override", test_reed_switch_compounding_override),
        ("test_low_risk_active_resistor", test_low_risk_active_resistor),
        ("test_missing_data_transparency_reason", test_missing_data_transparency_reason),
        ("test_fuzzy_ahp_weights_replace_static_priorities", test_fuzzy_ahp_weights_replace_static_priorities),
        ("test_weibull_conditional_probability_increases_with_horizon", test_weibull_conditional_probability_increases_with_horizon),
        ("test_weibull_obsolescence_uses_lifecycle_and_history", test_weibull_obsolescence_uses_lifecycle_and_history),
        ("test_compute_risk_records_five_year_obsolescence_probability", test_compute_risk_records_five_year_obsolescence_probability),
        ("test_prioritization_severity_vs_exposure", test_prioritization_severity_vs_exposure),
        ("test_group_by_band", test_group_by_band),
        ("test_compute_summary_metrics", test_compute_summary_metrics),
        ("test_exact_mpn_lookup_for_all_supported_categories", test_exact_mpn_lookup_for_all_supported_categories),
        ("test_missing_mpn_returns_not_found", test_missing_mpn_returns_not_found),
        ("test_missing_tolerance_is_not_fabricated", test_missing_tolerance_is_not_fabricated),
        ("test_missing_reliability_data_is_explicit", test_missing_reliability_data_is_explicit),
        ("test_high_confidence_evidence_is_exposed", test_high_confidence_evidence_is_exposed),
        ("test_missing_degradation_data_is_explicit", test_missing_degradation_data_is_explicit),
        ("test_class_level_degradation_scenario_is_labeled", test_class_level_degradation_scenario_is_labeled),
        ("test_reliability_outlook_uses_available_evidence_only", test_reliability_outlook_uses_available_evidence_only),
        ("test_substitute_integration_keeps_existing_logic_and_adds_reliability_layer", test_substitute_integration_keeps_existing_logic_and_adds_reliability_layer),
        ("test_bom_specific_identifier_without_dataset_evidence_stays_unavailable", test_bom_specific_identifier_without_dataset_evidence_stays_unavailable),
        ("test_no_fabricated_exact_mpn_rate_is_returned", test_no_fabricated_exact_mpn_rate_is_returned),
        ("test_operating_margin_requires_bom_specific_operating_conditions", test_operating_margin_requires_bom_specific_operating_conditions),
        ("test_safe_recommendation_requires_reliability_evidence_for_both_parts", test_safe_recommendation_requires_reliability_evidence_for_both_parts),
        ("test_device_registration_and_component_mapping", test_device_registration_and_component_mapping),
        ("test_selection_uses_canonical_selected_state", test_selection_uses_canonical_selected_state),
        ("test_risk_colors_are_semantic_and_centralized", test_risk_colors_are_semantic_and_centralized),
        ("test_substitute_turns_original_off_and_replacement_recommended_then_active", test_substitute_turns_original_off_and_replacement_recommended_then_active),
        ("test_unknown_component_and_invalid_message_are_rejected", test_unknown_component_and_invalid_message_are_rejected),
        ("test_manual_and_simulator_ack_but_physical_requires_real_ack", test_manual_and_simulator_ack_but_physical_requires_real_ack),
        ("test_evidence_adapter_preserves_unknown_values_without_synthetic_supply_data", test_evidence_adapter_preserves_unknown_values_without_synthetic_supply_data),
        ("test_bom_component_accepts_enumerated_fields", test_bom_component_accepts_enumerated_fields),
        ("test_bom_component_rejects_invalid_criticality_and_lifecycle", test_bom_component_rejects_invalid_criticality_and_lifecycle),
        ("test_substitute_component_exposes_parametric_specs", test_substitute_component_exposes_parametric_specs),
        ("test_redesign_cost_totals_requalification_and_holding", test_redesign_cost_totals_requalification_and_holding),
        ("test_bill_of_materials_rolls_up_extended_cost", test_bill_of_materials_rolls_up_extended_cost),
        ("test_sqlalchemy_round_trip_with_pydantic", test_sqlalchemy_round_trip_with_pydantic),
        ("test_compare_strategies_returns_three_npvs", test_compare_strategies_returns_three_npvs),
        ("test_low_holding_prefers_last_time_buy", test_low_holding_prefers_last_time_buy),
        ("test_design_refresh_wins_when_unit_cost_falls_and_nre_is_shared_in_mip", test_design_refresh_wins_when_unit_cost_falls_and_nre_is_shared_in_mip),
        ("test_integer_program_matches_independent_argmin", test_integer_program_matches_independent_argmin),
        ("test_engineering_capacity_blocks_requalification", test_engineering_capacity_blocks_requalification),
        ("test_from_bom_component_and_redesign_cost", test_from_bom_component_and_redesign_cost),
        ("test_part_stress_is_not_linear_mtbf_scaling", test_part_stress_is_not_linear_mtbf_scaling),
        ("test_capacitor_voltage_and_temperature_raise_failure_rate", test_capacitor_voltage_and_temperature_raise_failure_rate),
        ("test_environment_and_thermal_derating_corrections", test_environment_and_thermal_derating_corrections),
        ("test_switching_activity_and_recovery_guardbands", test_switching_activity_and_recovery_guardbands),
        ("test_analyze_part_stress_dispatch", test_analyze_part_stress_dispatch),
        ("test_hard_filter_requires_exact_package_and_pin_count", test_hard_filter_requires_exact_package_and_pin_count),
        ("test_pipeline_returns_top_10_classified_drop_in_or_redesign", test_pipeline_returns_top_10_classified_drop_in_or_redesign),
        ("test_find_substitutes_requires_jwt", test_find_substitutes_requires_jwt),
        ("test_fastapi_find_substitutes_get_and_post", test_fastapi_find_substitutes_get_and_post),
        ("test_unhandled_errors_go_to_sentry_with_generic_500", test_unhandled_errors_go_to_sentry_with_generic_500),
        ("test_catalog_pin_counts_are_stable_for_known_packages", test_catalog_pin_counts_are_stable_for_known_packages),
        ("test_risk_engine_zero_stock_edge_case", test_risk_engine_zero_stock_edge_case),
        ("test_risk_engine_infinite_and_missing_lead_time_edge_cases", test_risk_engine_infinite_and_missing_lead_time_edge_cases),
        ("test_risk_engine_conflicting_multi_attribute_scores", test_risk_engine_conflicting_multi_attribute_scores),
        ("test_risk_engine_historical_data_mapping_and_fitting", test_risk_engine_historical_data_mapping_and_fitting),
        ("test_risk_engine_normalization_functions", test_risk_engine_normalization_functions),
        ("test_redesign_decision_pv_and_annuity_edge_cases", test_redesign_decision_pv_and_annuity_edge_cases),
        ("test_redesign_decision_mitigation_part_validations", test_redesign_decision_mitigation_part_validations),
        ("test_redesign_decision_unfeasible_strategy_edge_cases", test_redesign_decision_unfeasible_strategy_edge_cases),
        ("test_redesign_decision_optimization_edge_cases", test_redesign_decision_optimization_edge_cases),
        ("test_redesign_decision_optimize_from_bom_roundtrip", test_redesign_decision_optimize_from_bom_roundtrip),
        ("test_reliability_stress_temperature_and_stress_errors", test_reliability_stress_temperature_and_stress_errors),
        ("test_reliability_stress_junction_temp_variations", test_reliability_stress_junction_temp_variations),
        ("test_reliability_stress_capacitor_styles_and_series_resistance", test_reliability_stress_capacitor_styles_and_series_resistance),
        ("test_reliability_stress_semiconductor_styles_and_ratings", test_reliability_stress_semiconductor_styles_and_ratings),
        ("test_reliability_stress_as_dict_serialization", test_reliability_stress_as_dict_serialization),
        ("test_digikey_provider_health", test_digikey_provider_health),
        ("test_nexar_provider_health", test_nexar_provider_health),
        ("test_digikey_mock_response_parsing", test_digikey_mock_response_parsing),
        ("test_nexar_mock_response_parsing", test_nexar_mock_response_parsing),
        ("test_normalize_mpn", test_normalize_mpn),
        ("test_resolve_mpn", test_resolve_mpn),
        ("test_data_quality_report", test_data_quality_report),
        ("test_vendor_feasibility_insufficient_data", test_vendor_feasibility_insufficient_data),
    ]
    
    passed = 0
    failed = 0
    
    try:
        for name, fn in tests:
            try:
                fn()
                print(f"  [PASS] {name}")
                passed += 1
            except Exception as e:
                import traceback
                print(f"  [FAIL] {name}: {e}")
                traceback.print_exc()
                failed += 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
            
    print(f"\nTest Execution Complete: {passed} PASSED, {failed} FAILED.")
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
