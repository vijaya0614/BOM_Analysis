from src.hardware_ws import ESP32Adapter, ManualAdapter, SimulatorAdapter, TwinRegistry, validate_message


def _hello(device_id="PS5-HW-001", mode="physical", components=None):
    return {
        "type": "device_hello", "device_id": device_id, "device_mode": mode,
        "project_id": "mini_smart_cooling_controller", "components": components or [{"id": "U1"}, {"id": "U1_ALT"}],
    }


def test_device_registration_and_component_mapping():
    registry = TwinRegistry()
    status = registry.register(_hello())
    assert status["status"] == "ONLINE"
    assert registry.devices["PS5-HW-001"].components == {"U1", "U1_ALT"}


def test_selection_uses_canonical_selected_state():
    registry = TwinRegistry(); registry.register(_hello())
    update = registry.apply({"type": "select_component", "project_id": "mini_smart_cooling_controller", "target_device_id": "PS5-HW-001", "component_id": "U1"})
    assert update["state"]["component_states"]["U1"] == "SELECTED"


def test_risk_colors_are_semantic_and_centralized():
    registry = TwinRegistry(); registry.register(_hello())
    for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        update = registry.apply({"type": "risk_update", "project_id": "mini_smart_cooling_controller", "component_id": "U1", "risk_level": level, "risk_score": 50})
        assert update["state"]["component_states"]["U1"] == level


def test_substitute_turns_original_off_and_replacement_recommended_then_active():
    registry = TwinRegistry(); registry.register(_hello())
    update = registry.apply({"type": "alternative_recommended", "project_id": "mini_smart_cooling_controller", "original_component_id": "U1", "substitute_component_id": "U1_ALT", "substitute_mpn": "IRFZ44NS"})
    assert update["state"]["component_states"] == {"U1": "OFF", "U1_ALT": "RECOMMENDED"}
    update = registry.apply({"type": "approve_substitute", "project_id": "mini_smart_cooling_controller"})
    assert update["state"]["component_states"]["U1_ALT"] == "ACTIVE"


def test_unknown_component_and_invalid_message_are_rejected():
    registry = TwinRegistry(); registry.register(_hello(components=[{"id": "U1"}]))
    update = registry.apply({"type": "select_component", "project_id": "mini_smart_cooling_controller", "target_device_id": "PS5-HW-001", "component_id": "Q9"})
    assert update["type"] == "mapping_error"
    assert validate_message({"type": "risk_update", "component_id": "U1", "risk_level": "PURPLE"})[0] is False


def test_manual_and_simulator_ack_but_physical_requires_real_ack():
    update = {"command_id": "cmd_1"}
    assert SimulatorAdapter().apply_state(update)["simulated"] is True
    assert ManualAdapter().apply_state(update)["status"] == "APPLIED"
    assert ESP32Adapter().apply_state(update) is None
    registry = TwinRegistry(); registry.register(_hello())
    assert registry.devices["PS5-HW-001"].synchronized is False
    assert registry.acknowledge("PS5-HW-001", {"type": "component_state_ack", "status": "APPLIED"}) is True
