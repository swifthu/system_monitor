"""System Monitor TUI - Main App."""
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static

from api_client import APIClient, get_mmx_quota
from tui.widgets import MetricCard

# Color scheme per metric
METRIC_COLORS = {
    "cpu": "cyan",
    "memory": "blue",
    "network": "green",
    "battery": "yellow",
    "gpu": "magenta",
    "temperature": "red",
    "disk": "magenta",
    "quota": "yellow",
}

def format_bytes(bytes_val: float) -> str:
    """Format bytes to human readable string."""
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
    """Format rate to human readable string."""
    return f"{format_bytes(bytes_per_sec)}/s"

class SystemMonitorApp(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("1", "switch_tab_1", "DASHBOARD", show=False),
        Binding("2", "switch_tab_2", "SYSTEM", show=False),
        Binding("3", "switch_tab_3", "AGENTS", show=False),
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
            with TabPane("DASHBOARD", id="dashboard"):
                yield MetricCard("CPU", "--", METRIC_COLORS["cpu"], id="cpu-card")
                yield MetricCard("Memory", "--", METRIC_COLORS["memory"], id="mem-card")
                yield MetricCard("Network", "--", METRIC_COLORS["network"], id="net-card")
                yield MetricCard("GPU", "--", METRIC_COLORS["gpu"], id="gpu-card")
                yield MetricCard("Temperature", "--", METRIC_COLORS["temperature"], id="temp-card")
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

        # Calculate CPU percent from cores (100 - idle = used percent)
        cpu_percent = 0.0
        if snapshot.cpu_cores:
            cpu_percent = sum(100 - c.idle for c in snapshot.cpu_cores) / len(snapshot.cpu_cores)

        # Update CPU card
        self.query_one("#cpu-card", MetricCard).update(
            f"{cpu_percent:.1f}%",
            bar_value=cpu_percent
        )

        # Update Memory card
        self.query_one("#mem-card", MetricCard).update(
            f"{format_bytes(snapshot.memory_used)} / {format_bytes(snapshot.memory_total)}",
            bar_value=snapshot.memory_used_percent
        )

        # Update Network card - aggregate all active interfaces
        total_rx = sum(n.rx_rate for n in snapshot.network)
        total_tx = sum(n.tx_rate for n in snapshot.network)
        self.query_one("#net-card", MetricCard).update(
            f"↓ {format_rate(total_rx)}\n↑ {format_rate(total_tx)}"
        )

        # Update Power card (show power percent if significant)
        if snapshot.power_percent > 1:  # Only show if > 1%
            self.query_one("#gpu-card", MetricCard).update(
                f"Power: {snapshot.power_percent:.0f}%",
                bar_value=min(snapshot.power_percent, 100)
            )

        # Update Temperature card
        if snapshot.cpu_temp > 0:
            self.query_one("#temp-card", MetricCard).update(f"CPU: {snapshot.cpu_temp:.0f}°C")

        # Update SYSTEM tab
        self._update_system_tab(snapshot)

        # Update AGENTS tab
        self._update_agents_tab()

    def _update_system_tab(self, snapshot):
        """Update SYSTEM tab with disk and CPU core info."""
        lines = ["[bold]System Details[/]\n"]

        # Disk info
        for d in snapshot.disk:
            used_bar = "█" * int(d.used_percent / 5) + "░" * (20 - int(d.used_percent / 5))
            lines.append(f"[bold {METRIC_COLORS['disk']}]Disk: {d.path}[/]")
            lines.append(f"  {format_bytes(d.used)} / {format_bytes(d.total)}")
            lines.append(f"  [{used_bar}] {d.used_percent:.1f}%")
            lines.append("")

        # CPU cores
        if snapshot.cpu_cores:
            lines.append("[bold cyan]CPU Cores:[/]")
            for i, core in enumerate(snapshot.cpu_cores[:4]):  # Show first 4 cores
                used = 100 - core.idle
                bar = "█" * int(used / 5) + "░" * (20 - int(used / 5))
                lines.append(f"  Core {i}: [{bar}] {used:.1f}%")
            if len(snapshot.cpu_cores) > 4:
                lines.append(f"  ... and {len(snapshot.cpu_cores) - 4} more cores")
            lines.append("")

        self.query_one("#system-info", Static).update("\n".join(lines))

    def _update_agents_tab(self):
        """Update AGENTS tab with quota info."""
        lines = ["[bold]Agent Status[/]\n"]

        # MiniMax Quota via mmx CLI
        quota = get_mmx_quota()
        if quota and "model_remains" in quota:
            lines.append("[bold yellow]MiniMax Quota:[/]\n")
            for model in quota["model_remains"][:8]:  # Show first 8 models
                name = model.get("model_name", "unknown")
                total = model.get("current_interval_total_count", 0)
                used = model.get("current_interval_usage_count", 0)
                remaining = total - used
                weekly_total = model.get("current_weekly_total_count", 0)
                weekly_used = model.get("current_weekly_usage_count", 0)
                weekly_remaining = weekly_total - weekly_used

                # Show as progress bar if has limit
                if total > 0:
                    pct = (used / total) * 100
                    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                    lines.append(f"[cyan]{name}:[/]")
                    lines.append(f"  [{bar}] {remaining}/{total} (daily)")
                elif weekly_total > 0:
                    pct = (weekly_used / weekly_total) * 100
                    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                    lines.append(f"[cyan]{name}:[/]")
                    lines.append(f"  [{bar}] {weekly_remaining}/{weekly_total} (weekly)")
                else:
                    lines.append(f"[cyan]{name}:[/] unlimited")
            if len(quota["model_remains"]) > 8:
                lines.append(f"\n... and {len(quota['model_remains']) - 8} more models")
        else:
            lines.append("[dim]MiniMax quota unavailable[/]")

        self.query_one("#agents-info", Static).update("\n".join(lines))

    def action_switch_tab_1(self):
        self.active_tab = "dashboard"

    def action_switch_tab_2(self):
        self.active_tab = "system"

    def action_switch_tab_3(self):
        self.active_tab = "agents"

    def action_refresh(self):
        self.update_metrics()
