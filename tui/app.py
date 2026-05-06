"""System Monitor TUI - Event-driven App."""
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static

from api_client import APIClient
from sse_client import SSEClient

@dataclass
class Cache:
    """Data cache for TUI."""
    system_snapshot: Optional[dict] = None
    quota_data: Optional[dict] = None
    banwagon_data: Optional[dict] = None
    last_system_update: float = 0.0
    last_quota_update: float = 0.0
    last_banwagon_update: float = 0.0

METRIC_COLORS = {
    "cpu": "cyan",
    "memory": "bright_blue",
    "network": "green",
    "power": "magenta",
    "temperature": "red",
    "disk": "yellow",
    "quota": "yellow",
    "banwagon": "red",
}

def format_bytes(bytes_val: float) -> str:
    if bytes_val >= 1e12:
        return f"{bytes_val/1e12:.1f} TB"
    elif bytes_val >= 1e9:
        return f"{bytes_val/1e9:.1f} GB"
    elif bytes_val >= 1e6:
        return f"{bytes_val/1e6:.1f} MB"
    elif bytes_val >= 1e3:
        return f"{bytes_val/1e3:.1f} KB"
    return f"{bytes_val:.0f} B"

def format_rate(bytes_per_sec: float) -> str:
    return f"{format_bytes(bytes_per_sec)}/s"

def make_bar(value: float, width: int = 20) -> str:
    """Create a progress bar using block characters."""
    filled = int(value / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty

class SystemMonitorApp(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("1", "switch_tab_1", "SYSTEM", show=False),
        Binding("2", "switch_tab_2", "Quota", show=False),
    ]

    CSS_PATH = "styles.tcss"

    def __init__(self):
        super().__init__()
        self.api = APIClient(inline=True)
        self.cache = Cache()
        self.sse_client: Optional[SSEClient] = None
        self.refresh_interval = 2.0
        self.quota_interval = 10.0  # Quota 刷新间隔 10 秒

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("SYSTEM", id="system"):
                yield Static("", id="system-info")
            with TabPane("Quota", id="agents"):
                yield Static("", id="agents-info")
        yield Footer()

    async def on_mount(self):
        # Fetch initial snapshot immediately while SSE connects in background
        asyncio.create_task(self._fetch_initial_snapshot())
        # Start quota refresh timer (independent of SSE)
        self.set_interval(self.quota_interval, self._refresh_quota)
        # Start SSE connection for system data (non-blocking)
        asyncio.create_task(self._start_sse())
        # Initial quota load
        await self._refresh_quota()

    async def _start_sse(self):
        """Start SSE connection for system data streaming."""
        self.sse_client = SSEClient(f"{self.api.base_url}/api/stream")
        await self.sse_client.connect(
            on_message=self._on_sse_message,
            on_connect=self._on_sse_connect,
        )

    async def _fetch_initial_snapshot(self):
        """Fetch initial snapshot via REST API while SSE is connecting."""
        try:
            snapshot = await self.api.get_snapshot()
            if snapshot:
                data = _snapshot_to_dict(snapshot)
                self.cache.system_snapshot = data
                self.cache.last_system_update = asyncio.get_event_loop().time()
                self._update_system_tab(data)
        except Exception:
            pass

    async def _on_sse_connect(self):
        """Called when SSE connection is established."""
        pass  # Connection established, data will flow automatically

    async def _on_sse_message(self, data: dict):
        """Handle incoming SSE data."""
        self.cache.system_snapshot = data
        self.cache.last_system_update = asyncio.get_event_loop().time()
        # Update system tab if it's active
        if self.active_tab == "system":
            self._update_system_tab(data)

    async def _refresh_quota(self):
        """Refresh quota data (MiniMax + Banwagon) - runs in background."""
        # MiniMax quota - uses existing mmx CLI approach (async subprocess)
        try:
            proc = await asyncio.create_subprocess_exec(
                "mmx", "quota",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            if proc.returncode == 0:
                import json
                quota = json.loads(stdout)
                self.cache.quota_data = quota
                self.cache.last_quota_update = asyncio.get_event_loop().time()
        except Exception:
            pass

        # Banwagon - fetch via API
        try:
            import httpx
            resp = httpx.get(f"{self.api.base_url}/api/banwagon", timeout=5)
            if resp.status_code == 200:
                self.cache.banwagon_data = resp.json()
                self.cache.last_banwagon_update = asyncio.get_event_loop().time()
        except Exception:
            pass

        # Update quota tab if it's active
        if self.active_tab == "agents":
            self._update_agents_tab()

    async def on_unmount(self):
        """Cleanup on app exit."""
        if self.sse_client:
            await self.sse_client.disconnect()

    async def update_metrics(self):
        try:
            self.snapshot = await self.api.get_snapshot()
        except Exception:
            return

        if not self.snapshot:
            return

        snapshot = self.snapshot
        self._update_system_tab(snapshot)
        self._update_agents_tab()

    def _update_system_tab(self, data: dict):
        """Build SYSTEM tab with all metrics."""
        lines = []
        c = METRIC_COLORS

        # Layout constants (match AGENTS tab)
        name_col_width = 45
        bar_col_width = 36

        # === Row 0: Header ===
        lines.append("[bold]System Monitor[/]  [dim]Press 1/2 to switch tabs[/]")

        # === Row 1-2: CPU | Memory ===
        cpu_list = data.get("cpu", [])
        cpu_percent = 0.0
        if cpu_list:
            cpu_percent = sum(100 - core.get("idle", 0) for core in cpu_list) / len(cpu_list)

        memory = data.get("memory", {})
        mem_pct = memory.get("used_percent", 0.0)

        bar_left = f"[{make_bar(cpu_percent)}] {cpu_percent:.1f}%"
        bar_right = f"[{make_bar(mem_pct)}] {mem_pct:.1f}%"
        lines.append(f"[bold {c['cpu']}]CPU[/]" + " " * (name_col_width - 4) + f"[bold {c['memory']}]Memory[/]")
        lines.append(bar_left + " " * (name_col_width - len(bar_left)) + bar_right)

        lines.append("")

        # === Network | Disk (titles on same line) ===
        network_list = data.get("network", [])
        # rx_rate/tx_rate from API are in MB/s, convert to bytes/s for format_rate
        total_rx = sum(n.get("rx_rate", 0) * 1024 * 1024 for n in network_list)
        total_tx = sum(n.get("tx_rate", 0) * 1024 * 1024 for n in network_list)

        disk_list = data.get("disk", [])
        disk_summary = ""
        for d in disk_list:
            disk_summary += f" [dim]{format_bytes(d.get('used', 0))}/{format_bytes(d.get('total', 0))}[/]"

        lines.append(f"[bold {c['network']}]Network[/]" + " " * (name_col_width - 7) + f"[bold {c['disk']}]Disk[/][dim]{disk_summary}[/]")

        left_bar = f"↓ {format_rate(total_rx)}  ↑ {format_rate(total_tx)}"
        disk_bars = ""
        for d in disk_list:
            disk_bars += f"[{make_bar(d.get('used_percent', 0))}] {d.get('used_percent', 0):.1f}%  "
        right_bar = disk_bars.strip()
        lines.append(left_bar + " " * (name_col_width - len(left_bar)) + right_bar)

        lines.append("")

        # === Power | Temperature (title on same line, values below) ===
        power = data.get("power", {})
        cpu_w = power.get("cpu_power_w", 0.0)
        gpu_w = power.get("gpu_power_w", 0.0)

        temp_parts = []
        cpu_temp = power.get("cpu_temp", 0.0)
        gpu_temp = power.get("gpu_temp", 0.0)
        if cpu_temp > 0:
            temp_parts.append(f"CPU: {cpu_temp:.0f}°C")
        if gpu_temp > 0:
            temp_parts.append(f"GPU: {gpu_temp:.0f}°C")

        total_w = power.get("percent", 0.0)
        power_parts = []
        if cpu_w > 0:
            power_parts.append(f"CPU: {cpu_w:.1f}W")
        if gpu_w > 0:
            power_parts.append(f"GPU: {gpu_w:.1f}W")
        power_val = "  " + "  ".join(power_parts) + f"  (All: {total_w:.1f}W)"
        temp_val = "  " + "  ".join(temp_parts)
        lines.append(f"[bold {c['power']}]Power[/]" + " " * (name_col_width - 5) + f"[bold {c['temperature']}]Temperature[/]")
        lines.append(power_val + " " * (name_col_width - len(power_val)) + temp_val)

        self.query_one("#system-info", Static).update("\n".join(lines))

    def _update_agents_tab(self):
        """Build AGENTS tab with quota info."""
        lines = []
        c = METRIC_COLORS

        lines.append("[bold]QUOTA[/]  [dim]Press 1/2 to switch tabs[/]\n")

        # MiniMax Quota from cache
        quota = self.cache.quota_data
        if quota and "model_remains" in quota:
            models = quota["model_remains"]

            lines.append(f"[bold {c['quota']}]MiniMax Quota:[/]\n")

            # Each model takes 3 rows: name, bar, reset time
            # Two models side by side with aligned columns
            name_col_width = 45
            bar_col_width = 36

            for i in range(0, len(models), 2):
                left = models[i]
                right = models[i + 1] if i + 1 < len(models) else None

                left_name = left.get("model_name", "unknown")
                left_total = left.get("current_interval_total_count", 0)
                left_used = left.get("current_interval_usage_count", 0)
                left_remaining = left_total - left_used
                left_pct = (left_used / left_total * 100) if left_total > 0 else 0
                left_remains_time = left.get("remains_time", 0)

                right_name = right.get("model_name", "unknown") if right else ""
                right_total = right.get("current_interval_total_count", 0) if right else 0
                right_used = right.get("current_interval_usage_count", 0) if right else 0
                right_remaining = right_total - right_used
                right_pct = (right_used / right_total * 100) if right_total > 0 else 0
                right_remains_time = right.get("remains_time", 0) if right else 0

                def format_reset_time(ms):
                    if ms <= 0:
                        return ""
                    h = int(ms // 3600000)
                    m = int((ms % 3600000) // 60000)
                    return f"reset in {h}h {m}m"

                if right:
                    # Row 1: Model names (aligned to 45 chars)
                    left_line = f"[cyan]{left_name}[/]"
                    right_line = f"[cyan]{right_name}[/]"
                    lines.append(f"{left_line:<{name_col_width}} {right_line}")

                    # Row 2: Progress bars (aligned to 36 chars)
                    left_bar = f"[{make_bar(left_pct)}] {left_remaining}/{left_total}" if left_total > 0 else "[dim]unlimited[/]"
                    right_bar = f"[{make_bar(right_pct)}] {right_remaining}/{right_total}" if right_total > 0 else "[dim]unlimited[/]"
                    lines.append(f"{left_bar:<{bar_col_width}} {right_bar}")

                    # Row 3: Reset time (aligned to 45 chars)
                    left_reset = format_reset_time(left_remains_time)
                    right_reset = format_reset_time(right_remains_time)
                    lines.append(f"{'[dim]' + left_reset + '[/]':<{name_col_width}} {'[dim]' + right_reset + '[/]'}")

                    lines.append("")  # blank line between model pairs
                else:
                    # Only left model
                    lines.append(f"[cyan]{left_name}[/]")
                    if left_total > 0:
                        lines.append(f"[{make_bar(left_pct)}] {left_remaining}/{left_total}")
                    else:
                        lines.append("[dim]unlimited[/]")
                    reset_str = format_reset_time(left_remains_time)
                    if reset_str:
                        lines.append(f"[dim]{reset_str}[/]")

        else:
            lines.append("[dim]MiniMax quota unavailable[/]")

        # Banwagon Quota from cache
        bw = self.cache.banwagon_data
        if bw:
            lines.append("")
            bw_location = bw.get("location", "Unknown")
            bw_total_gb = bw.get("total_gb", 0)
            bw_used_gb = bw.get("used_gb", 0)
            bw_next_reset = bw.get("data_next_reset", 0)

            lines.append(f"[bold {c['banwagon']}]Banwagon[/]  [dim]{bw_location}[/]")
            bw_pct = (bw_used_gb / bw_total_gb * 100) if bw_total_gb > 0 else 0
            lines.append(f"[{make_bar(bw_pct)}] {bw_used_gb:.1f}/{bw_total_gb} GB")

            if bw_next_reset > 0:
                from datetime import datetime
                reset_date = datetime.fromtimestamp(bw_next_reset)
                now = datetime.now()
                days_left = (reset_date - now).days
                lines.append(f"[dim]reset in {days_left} days[/]")

        self.query_one("#agents-info", Static).update("\n".join(lines))

    def action_switch_tab_1(self):
        self.active_tab = "system"
        if self.cache.system_snapshot:
            self._update_system_tab(self.cache.system_snapshot)

    def action_switch_tab_2(self):
        self.active_tab = "agents"
        # Always render cached data immediately if available
        if self.cache.quota_data or self.cache.banwagon_data:
            self._update_agents_tab()
        else:
            # No cache at all, show "loading" immediately
            self.query_one("#agents-info", Static).update("[dim]Loading quota...[/]")
        # Check if quota cache is stale (>quota_interval seconds), refresh if needed
        now = asyncio.get_event_loop().time()
        if self.cache.last_quota_update == 0 or (now - self.cache.last_quota_update) > self.quota_interval:
            asyncio.create_task(self._refresh_quota())

    def action_refresh(self):
        asyncio.create_task(self._fetch_initial_snapshot())

def _snapshot_to_dict(snapshot) -> dict:
    """Convert SystemSnapshot to dict for caching."""
    return {
        "timestamp": snapshot.timestamp,
        "memory": {
            "total": snapshot.memory_total,
            "used": snapshot.memory_used,
            "free": snapshot.memory_free,
            "available": snapshot.memory_available,
            "used_percent": snapshot.memory_used_percent,
        },
        "cpu": [
            {
                "cpu": c.cpu,
                "user": c.user,
                "system": c.system,
                "idle": c.idle,
            }
            for c in snapshot.cpu_cores
        ],
        "power": {
            "percent": snapshot.power_percent,
            "charge": snapshot.power_charge,
            "time_remaining": snapshot.power_time_remaining,
            "cpu_power_w": snapshot.cpu_power_w,
            "gpu_power_w": snapshot.gpu_power_w,
            "cpu_temp": snapshot.cpu_temp,
            "gpu_temp": snapshot.gpu_temp,
        },
        "disk": [
            {"path": d.path, "total": d.total, "used": d.used, "used_percent": d.used_percent}
            for d in snapshot.disk
        ],
        "network": [
            {"interface": n.interface, "rx_rate": n.rx_rate, "tx_rate": n.tx_rate}
            for n in snapshot.network
        ],
    }
