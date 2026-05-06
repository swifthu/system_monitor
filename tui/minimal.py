"""Minimal Textual app for debugging."""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static

class MinimalApp(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("SYSTEM", id="system"):
                yield Static("Static content - no updates", id="system-info")
            with TabPane("Quota", id="agents"):
                yield Static("Quota content - no updates", id="agents-info")
        yield Footer()

    def action_quit(self):
        self.exit()

if __name__ == "__main__":
    app = MinimalApp()
    app.run()