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
        self.api = APIClient()
        self.refresh_interval = 2.0
        self.snapshot = None

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("SYSTEM", id="system"):
                yield Static("", id="system-info")
            with TabPane("Quota", id="agents"):
                yield Static("", id="agents-info")
        yield Footer()

    async def on_mount(self):
        self.set_interval(self.refresh_interval, self.update_metrics)
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

        # MiniMax Quota via mmx CLI
        quota = get_mmx_quota()
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

        # Banwagon Quota
        try:
            import httpx
            resp = httpx.get(f"{self.api.base_url}/api/banwagon", timeout=5)
            if resp.status_code == 200:
                bw = resp.json()
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
        except Exception:
            pass

        self.query_one("#agents-info", Static).update("\n".join(lines))

    def action_switch_tab_1(self):
        self.active_tab = "system"

    def action_switch_tab_2(self):
        self.active_tab = "agents"

    def action_refresh(self):
        self.update_metrics()
