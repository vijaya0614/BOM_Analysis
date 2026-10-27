"""Canonical hardware/digital-twin WebSocket service.

This module intentionally has no third-party dependency so the hackathon MVP can
run in the supplied environment.  It implements the small RFC6455 subset used by
the browser and ESP32 clients and keeps all device state in ``TwinRegistry``.
"""
import asyncio
import base64
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

VALID_MODES = {"physical", "simulator", "manual"}
VALID_STATES = {"SELECTED", "LOW", "MEDIUM", "HIGH", "CRITICAL", "OFF", "RECOMMENDED", "ACTIVE", "NORMAL"}


def risk_to_state(level: str) -> str:
    return {"LOW": "LOW", "MEDIUM": "MEDIUM", "HIGH": "HIGH", "CRITICAL": "CRITICAL"}.get(str(level).upper(), "NORMAL")


def validate_message(message: Any) -> Tuple[bool, str]:
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        return False, "Message must be a JSON object with a string type."
    kind = message["type"]
    if kind == "device_hello":
        if not isinstance(message.get("device_id"), str) or message.get("device_mode") not in VALID_MODES:
            return False, "device_hello requires device_id and device_mode (physical, simulator, or manual)."
        if not isinstance(message.get("components", []), list):
            return False, "device_hello components must be a list."
        return True, ""
    if kind in {"select_component", "risk_update"} and not isinstance(message.get("component_id"), str):
        return False, f"{kind} requires component_id."
    if kind == "risk_update" and str(message.get("risk_level", "")).upper() not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        return False, "risk_update requires LOW, MEDIUM, HIGH, or CRITICAL risk_level."
    if kind == "alternative_recommended":
        if not all(isinstance(message.get(key), str) for key in ("original_component_id", "substitute_component_id", "substitute_mpn")):
            return False, "alternative_recommended requires original_component_id, substitute_component_id, and substitute_mpn."
    if kind not in {"device_hello", "select_component", "risk_update", "alternative_recommended", "approve_substitute", "reset_device", "telemetry", "component_state_ack", "heartbeat"}:
        return False, f"Unsupported message type: {kind}."
    return True, ""


@dataclass
class Device:
    device_id: str
    mode: str
    project_id: str
    components: Set[str]
    sender: Any = None
    online: bool = True
    last_seen: float = field(default_factory=time.time)
    synchronized: bool = False


class DeviceAdapter:
    """Transport-independent device interface; adapters never contain risk logic."""
    mode = "manual"

    def apply_state(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class SimulatorAdapter(DeviceAdapter):
    mode = "simulator"

    def apply_state(self, update: Dict[str, Any]) -> Dict[str, Any]:
        return {"type": "component_state_ack", "command_id": update["command_id"], "status": "APPLIED", "simulated": True}


class ESP32Adapter(DeviceAdapter):
    mode = "physical"

    def apply_state(self, update: Dict[str, Any]) -> None:
        # A physical device must return its own component_state_ack over the socket.
        return None


class ManualAdapter(SimulatorAdapter):
    mode = "manual"


class TwinRegistry:
    """One canonical state model shared by browser, simulator, and ESP32 clients."""
    def __init__(self) -> None:
        self.devices: Dict[str, Device] = {}
        self.adapters: Dict[str, DeviceAdapter] = {}
        self.projects: Dict[str, Dict[str, Any]] = {}

    def state_for(self, project_id: str) -> Dict[str, Any]:
        return self.projects.setdefault(project_id, {"project_id": project_id, "selected_component": None, "risk": {}, "substitute": None, "component_states": {}})

    def register(self, message: Dict[str, Any], sender: Any = None) -> Dict[str, Any]:
        project_id = str(message.get("project_id") or "mini_smart_cooling_controller")
        components = {str(item.get("id")) for item in message.get("components", []) if isinstance(item, dict) and item.get("id")}
        device = Device(message["device_id"], message["device_mode"], project_id, components, sender)
        self.devices[device.device_id] = device
        self.adapters[device.device_id] = {"simulator": SimulatorAdapter(), "physical": ESP32Adapter(), "manual": ManualAdapter()}[device.mode]
        return {"type": "hardware_status", "device_id": device.device_id, "project_id": project_id, "status": "ONLINE", "state": self.state_for(project_id)}

    def _ensure_component(self, project_id: str, component_id: str, target_device_id: Optional[str]) -> Optional[str]:
        if target_device_id:
            device = self.devices.get(target_device_id)
            if device is None:
                return "Unknown target device."
            if device.project_id != project_id:
                return "Target device is associated with another project."
            if component_id not in device.components:
                return f"Component mapping error: {component_id} is not exposed by {target_device_id}."
        return None

    def apply(self, message: Dict[str, Any]) -> Dict[str, Any]:
        project_id = str(message.get("project_id") or "mini_smart_cooling_controller")
        target = message.get("target_device_id")
        state = self.state_for(project_id)
        kind = message["type"]
        component_id = message.get("component_id") or message.get("original_component_id")
        if component_id:
            error = self._ensure_component(project_id, component_id, target)
            if error:
                return {"type": "mapping_error", "project_id": project_id, "message": error}
        if kind == "select_component":
            state["selected_component"] = component_id
            state["component_states"][component_id] = "SELECTED"
        elif kind == "risk_update":
            level = str(message["risk_level"]).upper()
            state["risk"][component_id] = {"score": message.get("risk_score"), "level": level, "reasons": message.get("risk_reasons", [])}
            state["component_states"][component_id] = risk_to_state(level)
        elif kind == "alternative_recommended":
            substitute_id = message["substitute_component_id"]
            state["substitute"] = {"original": component_id, "replacement": substitute_id, "mpn": message["substitute_mpn"]}
            state["component_states"][component_id] = "OFF"
            state["component_states"][substitute_id] = "RECOMMENDED"
        elif kind == "approve_substitute":
            substitute = state.get("substitute")
            if substitute:
                state["component_states"][substitute["original"]] = "OFF"
                state["component_states"][substitute["replacement"]] = "ACTIVE"
        elif kind == "reset_device":
            self.projects[project_id] = {"project_id": project_id, "selected_component": None, "risk": {}, "substitute": None, "component_states": {}}
            state = self.projects[project_id]
        return {"type": "state_update", "project_id": project_id, "target_device_id": target, "state": state, "command_id": message.get("command_id") or f"cmd_{uuid.uuid4().hex[:10]}"}

    def acknowledge(self, device_id: str, message: Dict[str, Any]) -> bool:
        device = self.devices.get(device_id)
        if not device or device.mode != "physical" or message.get("status") != "APPLIED":
            return False
        device.synchronized = True
        return True

    def recipients(self, project_id: str, target_device_id: Optional[str]) -> List[Device]:
        return [device for device in self.devices.values() if device.online and device.project_id == project_id and (not target_device_id or device.device_id == target_device_id)]


REGISTRY = TwinRegistry()


async def _read_frame(reader: asyncio.StreamReader) -> Optional[str]:
    header = await reader.readexactly(2)
    length = header[1] & 0x7F
    masked = bool(header[1] & 0x80)
    if length == 126:
        length = int.from_bytes(await reader.readexactly(2), "big")
    elif length == 127:
        length = int.from_bytes(await reader.readexactly(8), "big")
    mask = await reader.readexactly(4) if masked else b""
    data = await reader.readexactly(length)
    if masked:
        data = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
    return data.decode("utf-8")


async def _send_frame(writer: asyncio.StreamWriter, payload: Dict[str, Any]) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if len(data) < 126:
        header = bytes([0x81, len(data)])
    else:
        header = bytes([0x81, 126]) + len(data).to_bytes(2, "big")
    writer.write(header + data)
    await writer.drain()


async def _client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    device_id: Optional[str] = None
    try:
        request = (await reader.readuntil(b"\r\n\r\n")).decode("utf-8", "ignore")
        headers = dict(line.split(": ", 1) for line in request.split("\r\n")[1:] if ": " in line)
        key = headers.get("Sec-WebSocket-Key")
        if not key:
            writer.close(); return
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " + accept + "\r\n\r\n").encode())
        await writer.drain()
        while True:
            raw = await _read_frame(reader)
            message = json.loads(raw)
            valid, error = validate_message(message)
            if not valid:
                await _send_frame(writer, {"type": "protocol_error", "message": error}); continue
            if message["type"] == "device_hello":
                device_id = message["device_id"]
                await _send_frame(writer, REGISTRY.register(message, writer))
                continue
            if message["type"] == "telemetry":
                await _send_frame(writer, {"type": "telemetry", **message}); continue
            if message["type"] == "component_state_ack":
                if REGISTRY.acknowledge(device_id or "", message):
                    await _send_frame(writer, {"type": "hardware_status", "device_id": device_id, "status": "SYNCHRONIZED"})
                continue
            update = REGISTRY.apply(message)
            project_id = update.get("project_id", message.get("project_id", "mini_smart_cooling_controller"))
            for device in REGISTRY.recipients(project_id, update.get("target_device_id")):
                # Physical firmware receives the documented semantic command;
                # simulator/manual clients receive the canonical resolved state.
                device_payload = ({**message, "command_id": update.get("command_id"), "project_id": project_id} if device.mode == "physical" else update)
                await _send_frame(device.sender, device_payload)
                simulated_ack = REGISTRY.adapters[device.device_id].apply_state(update)
                if simulated_ack:
                    await _send_frame(device.sender, {**simulated_ack, "component_id": message.get("component_id") or message.get("original_component_id")})
            if update["type"] == "mapping_error":
                await _send_frame(writer, {"type": "component_state_ack", "command_id": update.get("command_id"), "status": "REJECTED", "message": update.get("message")})
    except (asyncio.IncompleteReadError, ConnectionError, json.JSONDecodeError):
        pass
    finally:
        if device_id in REGISTRY.devices:
            REGISTRY.devices[device_id].online = False
        writer.close()


async def serve(host: str = "127.0.0.1", port: int = 8002) -> None:
    server = await asyncio.start_server(_client, host, port)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(serve())
