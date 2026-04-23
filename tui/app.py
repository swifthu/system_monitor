"""System Monitor TUI - Main App."""
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static

from api_client import APIClient
from tui.widgets import MetricCard

# Color scheme per metric
METRIC_COLORS = {
    "cpu": "cyan",
    "memory": "blue",
    "network": "green",
    "battery": "yellow",
    "gpu": "magenta",
    "temperature": "red",
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
                yield self._build_system()
            with TabPane("AGENTS", id="agents"):
                yield self._build_agents()
        yield Footer()

    def _build_system(self) -> Static:
        """Build system detail view."""
        return Static("[bold]System Details[/]\n\nComing soon...", id="system-placeholder")

    def _build_agents(self) -> Static:
        """Build agents overview."""
        return Static("[bold]Agent Status[/]\n\nComing soon...", id="agents-placeholder")

    async def on_mount(self):
        self.set_interval(self.refresh_interval, self.update_metrics)
        await self.update_metrics()

    async def update_metrics(self):
        try:
            snapshot = await self.api.get_snapshot()
        except Exception:
            return

        if not snapshot:
            return

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

    def action_switch_tab_1(self):
        self.active_tab = "dashboard"

    def action_switch_tab_2(self):
        self.active_tab = "system"

    def action_switch_tab_3(self):
        self.active_tab = "agents"

    def action_refresh(self):
        self.update_metrics()
