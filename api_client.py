"""API client for System Monitor Go backend."""
import httpx
import subprocess
import json
from dataclasses import dataclass
from typing import Optional, List

BASE_URL = "http://localhost:8001"

@dataclass
class CPUCore:
    cpu: int
    user: float
    system: float
    idle: float

@dataclass
class NetworkInterface:
    interface: str
    rx_rate: float
    tx_rate: float

@dataclass
class DiskInfo:
    path: str
    total: float
    used: float
    used_percent: float

@dataclass
class SystemSnapshot:
    timestamp: int
    memory_total: float
    memory_used: float
    memory_free: float
    memory_available: float
    memory_used_percent: float
    cpu_cores: List[CPUCore]
    power_percent: float
    power_charge: bool
    power_time_remaining: int
    cpu_power_w: float
    gpu_power_w: float
    cpu_temp: float
    gpu_temp: float
    disk: List[DiskInfo]
    network: List[NetworkInterface]

class APIClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self._client = httpx.Client(timeout=5.0)

    async def get_snapshot(self) -> Optional[SystemSnapshot]:
        try:
            resp = self._client.get(f"{self.base_url}/api/snapshot")
            resp.raise_for_status()
            data = resp.json()
            return parse_snapshot(data)
        except Exception:
            return None

def parse_snapshot(data: dict) -> SystemSnapshot:
    memory = data.get("memory", {})
    power = data.get("power", {})
    cpu_list = data.get("cpu", [])
    disk_list = data.get("disk", [])
    network_list = data.get("network", [])

    cpu_cores = [
        CPUCore(
            cpu=c.get("cpu", 0),
            user=c.get("user", 0),
            system=c.get("system", 0),
            idle=c.get("idle", 0),
        )
        for c in cpu_list
    ]

    disk_info = [
        DiskInfo(
            path=d.get("path", ""),
            total=d.get("total", 0),
            used=d.get("used", 0),
            used_percent=d.get("used_percent", 0),
        )
        for d in disk_list
    ]

    network_info = [
        NetworkInterface(
            interface=n.get("interface", ""),
            rx_rate=n.get("rx_rate", 0),
            tx_rate=n.get("tx_rate", 0),
        )
        for n in network_list
        if n.get("rx_rate", 0) > 0 or n.get("tx_rate", 0) > 0
    ]

    return SystemSnapshot(
        timestamp=data.get("timestamp", 0),
        memory_total=memory.get("total", 0),
        memory_used=memory.get("used", 0),
        memory_free=memory.get("free", 0),
        memory_available=memory.get("available", 0),
        memory_used_percent=memory.get("used_percent", 0),
        cpu_cores=cpu_cores,
        power_percent=power.get("percent", 0) * 100,
        power_charge=power.get("charge", False),
        power_time_remaining=power.get("time_remaining", 0),
        cpu_power_w=power.get("cpu_power_w", 0),
        gpu_power_w=power.get("gpu_power_w", 0),
        cpu_temp=power.get("cpu_temp", 0),
        gpu_temp=power.get("gpu_temp", 0),
        disk=disk_info,
        network=network_info,
    )

def get_mmx_quota() -> Optional[dict]:
    """Get MiniMax quota using mmx CLI."""
    try:
        result = subprocess.run(
            ["mmx", "quota"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except Exception:
        return None
