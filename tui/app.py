"""System Monitor TUI - Main App."""
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static

from api_client import APIClient, get_mmx_quota

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

def toFloat64(v) -> float:
    """Convert various types to float64."""
    if v is None:
        return 0
    if isinstance(v, float):
        return v
    if isinstance(v, int):
        return float(v)
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0

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
        self.api = APIClient(inline=False)  # Use HTTP mode to avoid subprocess blocking
        self.refresh_interval = 2.0
        self.snapshot = None
        self.quota_cache = None  # Cache for MiniMax quota, updated separately
        self.banwagon_cache = None  # Cache for Banwagon, updated on demand

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("SYSTEM", id="system"):
                yield Static("", id="system-info")
            with TabPane("Quota", id="agents"):
                yield Static("", id="agents-info")
        yield Footer()

    def _schedule_refresh(self):
        self.call_later(self.update_metrics)

    def _refresh_quota_cache(self):
        """Update quota cache in background (non-blocking)."""
        import subprocess, json
        try:
            result = subprocess.run(["mmx", "quota"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.quota_cache = json.loads(result.stdout)
        except Exception:
            pass

    async def on_mount(self):
        self.set_interval(self.refresh_interval, self._schedule_refresh)
        self.set_interval(30.0, self._refresh_quota_cache)  # Update quota every 30s
        self._refresh_quota_cache()  # Initial quota fetch
        self._refresh_banwagon_cache()  # Initial Banwagon fetch
        await self.update_metrics()

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

    def _update_system_tab(self, snapshot):
        """Build SYSTEM tab with all metrics."""
        lines = []
        c = METRIC_COLORS

        # Layout constants (match AGENTS tab)
        name_col_width = 45
        bar_col_width = 36

        # === Row 0: Header ===
        lines.append("[bold]System Monitor[/]  [dim]Press 1/2 to switch tabs[/]")

        # === Row 1-2: CPU | Memory ===
        cpu_percent = 0.0
        if snapshot.cpu_cores:
            cpu_percent = sum(100 - core.idle for core in snapshot.cpu_cores) / len(snapshot.cpu_cores)

        mem_pct = snapshot.memory_used_percent

        bar_left = f"[{make_bar(cpu_percent)}] {cpu_percent:.1f}%"
        bar_right = f"[{make_bar(mem_pct)}] {mem_pct:.1f}%"
        lines.append(f"[bold {c['cpu']}]CPU[/]" + " " * (name_col_width - 4) + f"[bold {c['memory']}]Memory[/]")
        lines.append(bar_left + " " * (name_col_width - len(bar_left)) + bar_right)

        lines.append("")

        # === Network | Disk (titles on same line) ===
        # rx_rate/tx_rate from API are in MB/s, convert to bytes/s for format_rate
        total_rx = sum(n.rx_rate * 1024 * 1024 for n in snapshot.network)
        total_tx = sum(n.tx_rate * 1024 * 1024 for n in snapshot.network)

        disk_summary = ""
        for d in snapshot.disk:
            disk_summary += f" [dim]{format_bytes(d.used)}/{format_bytes(d.total)}[/]"

        lines.append(f"[bold {c['network']}]Network[/]" + " " * (name_col_width - 7) + f"[bold {c['disk']}]Disk[/][dim]{disk_summary}[/]")

        left_bar = f"↓ {format_rate(total_rx)}  ↑ {format_rate(total_tx)}"
        disk_bars = ""
        for d in snapshot.disk:
            disk_bars += f"[{make_bar(d.used_percent)}] {d.used_percent:.1f}%  "
        right_bar = disk_bars.strip()
        lines.append(left_bar + " " * (name_col_width - len(left_bar)) + right_bar)

        lines.append("")

        # === Power | Temperature (title on same line, values below) ===
        cpu_w = snapshot.cpu_power_w
        gpu_w = snapshot.gpu_power_w

        temp_parts = []
        if snapshot.cpu_temp > 0:
            temp_parts.append(f"CPU: {snapshot.cpu_temp:.0f}°C")
        if snapshot.gpu_temp > 0:
            temp_parts.append(f"GPU: {snapshot.gpu_temp:.0f}°C")

        total_w = snapshot.power_percent
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

        # MiniMax Quota via cache (updated separately to avoid blocking)
        quota = self.quota_cache
        if quota and "model_remains" in quota:
            models = quota["model_remains"]

            # Compute weekly reset countdown from first model's weekly data
            first = models[0]
            weekly_remains = first.get("weekly_remains_time", 0)
            if weekly_remains > 0:
                wh = int(weekly_remains // 3600000)
                wm = int((weekly_remains % 3600000) // 60000)
                weekly_str = f" (weekly reset in {wh}h {wm}m)"
            else:
                weekly_str = ""
            lines.append(f"[bold {c['quota']}]MiniMax Quota:{weekly_str}[/]\n")

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

        lines.append("")  # blank line before Banwagon

        # Banwagon Quota (two accounts side by side, from cache)
        bw = self.banwagon_cache
        if bw:
            accounts = bw.get("accounts", [])
            if len(accounts) >= 2:
                name_col_width = 45
                bar_col_width = 36

                # Row 1: Banwagon headers
                acc0 = accounts[0]
                acc1 = accounts[1]
                loc0 = acc0.get("node_location", "Unknown")
                loc1 = acc1.get("node_location", "Unknown")
                lines.append(f"[bold {c['banwagon']}]Banwagon CN2GIA[/][dim] - {loc0}[/]" + " " * (name_col_width - len(loc0) - 26) + f"[bold {c['banwagon']}]Banwagon DC9[/][dim] - {loc1}[/]")

                # Row 2: Progress bars
                total0 = toFloat64(acc0.get("plan_monthly_data")) / 1024**3
                used0 = toFloat64(acc0.get("data_counter")) / 1024**3
                total1 = toFloat64(acc1.get("plan_monthly_data")) / 1024**3
                used1 = toFloat64(acc1.get("data_counter")) / 1024**3
                pct0 = (used0 / total0 * 100) if total0 > 0 else 0
                pct1 = (used1 / total1 * 100) if total1 > 0 else 0
                bar0 = f"[{make_bar(pct0)}] {used0:.1f}/{total0:.1f} GB"
                bar1 = f"[{make_bar(pct1)}] {used1:.1f}/{total1:.1f} GB"
                lines.append(f"{bar0:<{bar_col_width}} {bar1}")

                # Row 3: Reset times
                from datetime import datetime
                reset0 = toFloat64(acc0.get("data_next_reset"))
                reset1 = toFloat64(acc1.get("data_next_reset"))
                reset_str0 = f"[dim]reset in {(datetime.fromtimestamp(reset0) - datetime.now()).days} days[/]" if reset0 > 0 else "[dim]--[/]"
                reset_str1 = f"[dim]reset in {(datetime.fromtimestamp(reset1) - datetime.now()).days} days[/]" if reset1 > 0 else "[dim]--[/]"
                lines.append(f"{reset_str0:<{name_col_width}} {reset_str1}")
        else:
            lines.append("[dim]Banwagon data (press r to refresh)[/]")

        self.query_one("#agents-info", Static).update("\n".join(lines))

    def action_switch_tab_1(self):
        """Switch to SYSTEM tab - no data update, use cached data."""
        pass

    def action_switch_tab_2(self):
        """Switch to Quota tab - no data update, use cached data."""
        pass

    def _refresh_banwagon_cache(self):
        """Refresh Banwagon cache on demand."""
        import httpx
        try:
            resp = httpx.get(f"{self.api.base_url}/api/banwagon", timeout=5)
            if resp.status_code == 200:
                self.banwagon_cache = resp.json()
        except Exception:
            pass

    def action_refresh(self):
        self._refresh_banwagon_cache()
        self.update_metrics()
