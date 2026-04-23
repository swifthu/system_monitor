"""System Monitor TUI - Main App."""
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static

from api_client import APIClient, SystemSnapshot
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

    CSS_PATH = "tui/styles.tcss"

    def __init__(self):
        super().__init__()
        self.api = APIClient()
        self.refresh_interval = 2.0

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("DASHBOARD", id="dashboard"):
                yield self._build_dashboard()
            with TabPane("SYSTEM", id="system"):
                yield self._build_system()
            with TabPane("AGENTS", id="agents"):
                yield self._build_agents()
        yield Footer()

    def _build_dashboard(self) -> Container:
        """Build dashboard grid of metric cards."""
        grid = Container(id="dashboard-grid")
        grid.styles.display = "grid"
        grid.styles.grid_size = "3"
        grid.styles.gap = "1"

        # Row 1: CPU, Memory, Network
        grid.mount(
            MetricCard("CPU", "--", METRIC_COLORS["cpu"], id="cpu-card"),
            MetricCard("Memory", "--", METRIC_COLORS["memory"], id="mem-card"),
            MetricCard("Network", "--", METRIC_COLORS["network"], id="net-card"),
        )
        return grid

    def _build_system(self) -> Container:
        """Build system detail view."""
        container = Container(id="system-container")
        container.styles.padding = "1"
        container.mount(
            Static("[bold]System Details[/]\n\nComing soon...", id="system-placeholder")
        )
        return container

    def _build_agents(self) -> Container:
        """Build agents overview."""
        container = Container(id="agents-container")
        container.styles.padding = "1"
        container.mount(
            Static("[bold]Agent Status[/]\n\nComing soon...", id="agents-placeholder")
        )
        return container

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

        # Update CPU card
        self.query_one("#cpu-card", MetricCard).update(
            f"{snapshot.cpu_percent:.1f}%",
            bar_value=snapshot.cpu_percent
        )

        # Update Memory card
        mem_percent = (snapshot.memory_used / snapshot.memory_total * 100) if snapshot.memory_total > 0 else 0
        self.query_one("#mem-card", MetricCard).update(
            f"{format_bytes(snapshot.memory_used)} / {format_bytes(snapshot.memory_total)}",
            bar_value=mem_percent
        )

        # Update Network card
        self.query_one("#net-card", MetricCard).update(
            f"↓ {format_rate(snapshot.network_rx)}\n↑ {format_rate(snapshot.network_tx)}"
        )

    def action_switch_tab_1(self):
        self.active_tab = "dashboard"

    def action_switch_tab_2(self):
        self.active_tab = "system"

    def action_switch_tab_3(self):
        self.active_tab = "agents"

    def action_refresh(self):
        self.update_metrics()
