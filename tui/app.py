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
            lines.append(f"[bold {c['quota']}]MiniMax Quota:[/]\n")
            for model in quota["model_remains"]:
                name = model.get("model_name", "unknown")
                total = model.get("current_interval_total_count", 0)
                used = model.get("current_interval_usage_count", 0)
                remaining = total - used
                weekly_total = model.get("current_weekly_total_count", 0)
                weekly_used = model.get("current_weekly_usage_count", 0)
                weekly_remaining = weekly_total - weekly_used

                # Show model name
                lines.append(f"[cyan]{name}:[/]")

                # Daily quota
                if total > 0:
                    pct = (used / total) * 100
                    lines.append(f"  Daily: [{make_bar(pct)}] {remaining}/{total}")
                elif weekly_total > 0:
                    pct = (weekly_used / weekly_total) * 100
                    lines.append(f"  Weekly: [{make_bar(pct)}] {weekly_remaining}/{weekly_total}")
                else:
                    lines.append(f"  [dim]unlimited[/]")
                lines.append("")
        else:
            lines.append("[dim]MiniMax quota unavailable[/]")

        self.query_one("#agents-info", Static).update("\n".join(lines))

    def action_switch_tab_1(self):
        self.active_tab = "system"

    def action_switch_tab_2(self):
        self.active_tab = "agents"

    def action_refresh(self):
        self.update_metrics()
