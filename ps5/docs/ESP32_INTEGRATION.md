# ESP32 integration contract

The software simulator and WebSocket protocol are ready. Physical hardware is **not connected or tested** in this repository; GPIO/indicator mappings are intentionally unknown.

## Run the services

```powershell
python -m src.risk_api
python -m src.substitute_api
python -m src.hardware_ws
```

Connect future firmware to `ws://<PC-IP>:8002`. Configure Wi-Fi in the firmware and use the PC's LAN address, not `127.0.0.1`.

## Hello and component mapping

```json
{"type":"device_hello","device_id":"PS5-HW-001","device_mode":"physical","firmware_version":"TODO","project_id":"mini_smart_cooling_controller","components":[{"id":"U1","mpn":"IRLZ44N","indicator_id":"TODO"}]}
```

`indicator_id` is firmware-owned and must not be replaced with guessed GPIO numbers. The server only sends semantic component IDs and states.

## Commands received by firmware

`select_component`, `risk_update`, `alternative_recommended`, and `reset_device` include a `command_id` when acknowledgement is required. Render: `SELECTED` white blink; `LOW`/`MEDIUM`/`HIGH`/`CRITICAL` using existing risk colours; `RECOMMENDED` blue; `OFF` off.

Reply only after applying a command:

```json
{"type":"component_state_ack","command_id":"cmd_001","component_id":"U1","state":"CRITICAL","status":"APPLIED"}
```

The server marks a physical device synchronized only after this ACK. Reconnect with exponential backoff (1, 2, 5, then 10 seconds) and repeat `device_hello`; the server will return the current project state.
