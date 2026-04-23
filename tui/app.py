"""System Monitor TUI - Main App."""
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static

from api_client import APIClient, get_mmx_quota

METRIC_COLORS = {
    "cpu": "cyan",
    "memory": "blue",
    "network": "green",
    "power": "magenta",
    "temperature": "red",
    "disk": "yellow",
    "quota": "yellow",
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
        Binding("2", "switch_tab_2", "AGENTS", show=False),
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
            with TabPane("AGENTS", id="agents"):
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

        # === Header ===
        lines.append("[bold]System Monitor[/]  [dim]Press 1/2 to switch tabs[/]\n")

        # === CPU Section ===
        cpu_percent = 0.0
        if snapshot.cpu_cores:
            cpu_percent = sum(100 - core.idle for core in snapshot.cpu_cores) / len(snapshot.cpu_cores)
        lines.append(f"[bold {c['cpu']}]CPU:[/]  [bold]{cpu_percent:.1f}%[/]  [{make_bar(cpu_percent)}]")

        # === Memory Section ===
        lines.append(f"[bold {c['memory']}]Memory:[/]  [bold]{format_bytes(snapshot.memory_used)} / {format_bytes(snapshot.memory_total)}[/]")
        lines.append(f"         [{make_bar(snapshot.memory_used_percent)}]  {snapshot.memory_used_percent:.1f}%")

        # === Network Section ===
        total_rx = sum(n.rx_rate for n in snapshot.network)
        total_tx = sum(n.tx_rate for n in snapshot.network)
        lines.append(f"[bold {c['network']}]Network:[/]  ↓ {format_rate(total_rx)}  ↑ {format_rate(total_tx)}")

        # === Power Section ===
        if snapshot.power_percent > 1:
            lines.append(f"[bold {c['power']}]Power:[/]  [bold]{snapshot.power_percent:.0f}%[/]  [{make_bar(min(snapshot.power_percent, 100))}]")

        # === Temperature Section ===
        if snapshot.cpu_temp > 0:
            lines.append(f"[bold {c['temperature']}]Temperature:[/]  CPU: {snapshot.cpu_temp:.0f}°C  GPU: {snapshot.gpu_temp:.0f}°C")

        lines.append("")

        # === Disk Section ===
        for d in snapshot.disk:
            lines.append(f"[bold {c['disk']}]Disk:[/]  [bold]{d.path}[/]")
            lines.append(f"        {format_bytes(d.used)} / {format_bytes(d.total)}")
            lines.append(f"        [{make_bar(d.used_percent)}]  {d.used_percent:.1f}%")

        lines.append("")

        # === CPU Cores Section ===
        if snapshot.cpu_cores:
            lines.append(f"[bold {c['cpu']}]CPU Cores:[/]")
            for i, core in enumerate(snapshot.cpu_cores):
                used = 100 - core.idle
                lines.append(f"  Core {i}: [{make_bar(used)}] {used:.1f}%")

        self.query_one("#system-info", Static).update("\n".join(lines))

    def _update_agents_tab(self):
        """Build AGENTS tab with quota info."""
        lines = []
        c = METRIC_COLORS

        lines.append("[bold]Agent Status[/]  [dim]Press 1/2 to switch tabs[/]\n")

        # MiniMax Quota via mmx CLI
        quota = get_mmx_quota()
        if quota and "model_remains" in quota:
            models = quota["model_remains"]

            # Show first model's reset time as header
            if models:
                first = models[0]
                remains_time = first.get("remains_time", 0)
                if remains_time > 0:
                    hours = int(remains_time // 3600000)
                    mins = int((remains_time % 3600000) // 60000)
                    lines.append(f"[bold {c['quota']}]MiniMax Quota:[/]  [dim]reset in {hours}h {mins}m[/]\n")

            # Two-column grid: names on one line, bars on the next
            name_col_width = 36
            bar_col_width = 22

            for i in range(0, len(models), 2):
                left = models[i]
                right = models[i + 1] if i + 1 < len(models) else None

                left_name = left.get("model_name", "unknown")
                left_total = left.get("current_interval_total_count", 0)
                left_used = left.get("current_interval_usage_count", 0)
                left_remaining = left_total - left_used
                left_pct = (left_used / left_total * 100) if left_total > 0 else 0

                right_name = right.get("model_name", "unknown") if right else ""
                right_total = right.get("current_interval_total_count", 0) if right else 0
                right_used = right.get("current_interval_usage_count", 0) if right else 0
                right_remaining = right_total - right_used
                right_pct = (right_used / right_total * 100) if right_total > 0 else 0

                # Line 1: Model names
                if right:
                    name_col_width = 45
                    left_line = f"[cyan]{left_name}[/]"
                    right_line = f"[cyan]{right_name}[/]"
                    lines.append(f"{left_line:<{name_col_width}} {right_line}")

                    # Line 2: Progress bars - fixed width for bar info
                    bar_info_width = 36  # fixed width to align right bars
                    left_bar = f"[{make_bar(left_pct)}] {left_remaining}/{left_total}" if left_total > 0 else "[dim]unlimited[/]"
                    right_bar = f"[{make_bar(right_pct)}] {right_remaining}/{right_total}" if right_total > 0 else "[dim]unlimited[/]"
                    lines.append(f"{left_bar:<{bar_info_width}} {right_bar}")
                    lines.append("")  # blank line between pairs
                else:
                    # Only left model, center it
                    lines.append(f"[cyan]{left_name}[/]")
                    if left_total > 0:
                        lines.append(f"[{make_bar(left_pct)}] {left_remaining}/{left_total}")
                    else:
                        lines.append("[dim]unlimited[/]")

        else:
            lines.append("[dim]MiniMax quota unavailable[/]")

        self.query_one("#agents-info", Static).update("\n".join(lines))

    def action_switch_tab_1(self):
        self.active_tab = "system"

    def action_switch_tab_2(self):
        self.active_tab = "agents"

    def action_refresh(self):
        self.update_metrics()
