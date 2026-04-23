"""API client for System Monitor Go backend."""
import httpx
from dataclasses import dataclass
from typing import Optional

BASE_URL = "http://localhost:8001"

@dataclass
class SystemSnapshot:
    cpu_percent: float
    memory_used: float
    memory_total: float
    network_rx: float
    network_tx: float
    battery_percent: int
    battery_time_remaining: Optional[int]
    gpu_power: float
    gpu_total: float
    temp_cpu: float
    temp_gpu: float

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
    cpu = data.get("cpu", {})
    memory = data.get("memory", {})
    network = data.get("network", {})
    battery = data.get("battery", {})
    gpu = data.get("gpu", {})
    temp = data.get("temperature", {})

    return SystemSnapshot(
        cpu_percent=cpu.get("percent", 0),
        memory_used=memory.get("used", 0),
        memory_total=memory.get("total", 0),
        network_rx=network.get("rx_rate", 0),
        network_tx=network.get("tx_rate", 0),
        battery_percent=battery.get("percent", 0),
        battery_time_remaining=battery.get("time_remaining"),
        gpu_power=gpu.get("power", 0),
        gpu_total=gpu.get("total", 0),
        temp_cpu=temp.get("cpu", 0),
        temp_gpu=temp.get("gpu", 0),
    )