"""Custom widgets for System Monitor TUI."""
from textual.widgets import Static

class MetricCard(Static):
    """A card widget displaying a metric with value and optional progress bar."""

    def __init__(self, title: str, value: str, color: str = "white",
                 bar_value: float = None, subtitle: str = None):
        super().__init__()
        self._title = title
        self._value = value
        self._color = color
        self._bar_value = bar_value
        self._subtitle = subtitle or ""

    def render(self) -> str:
        bar = ""
        if self._bar_value is not None:
            filled = int(self._bar_value / 100 * 20)
            empty = 20 - filled
            bar = f"\n[{'#' * filled}{'-' * empty}] {self._bar_value:.0f}%"

        subtitle = f"\n{self._subtitle}" if self._subtitle else ""
        return f"[bold {self._color}]{self._title}[/]\n{self._value}{bar}{subtitle}"

    def update(self, value: str, bar_value: float = None, subtitle: str = None):
        """Update the card value and optional bar."""
        self._value = value
        if bar_value is not None:
            self._bar_value = bar_value
        if subtitle is not None:
            self._subtitle = subtitle
        self.refresh()
