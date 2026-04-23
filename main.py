"""System Monitor TUI - CLI Entry Point."""
from tui.app import SystemMonitorApp

def main():
    app = SystemMonitorApp()
    app.run()

if __name__ == "__main__":
    main()
