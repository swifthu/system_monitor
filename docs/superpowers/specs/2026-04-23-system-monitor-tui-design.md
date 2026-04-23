# System Monitor TUI - Design Spec

## Overview

Replace the web frontend with a Python Textual TUI that calls the existing Go backend API (`localhost:8001`).

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Python TUI (Textual)                          │
│  ├── api_client.py   - HTTP calls to Go backend │
│  ├── tui/app.py      - Main Textual App         │
│  └── tui/widgets.py  - Metric card widgets      │
└─────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│  Go Backend (localhost:8001)                    │
│  /api/snapshot  - Real-time system data         │
│  /api/metrics/query - Historical metrics        │
│  /api/metrics/list - Available metrics          │
└─────────────────────────────────────────────────┘
```

## Dependencies

- Python 3.12+
- `textual` - TUI framework
- `httpx` - Async HTTP client

## Tabs

| Tab | Content | Color |
|-----|---------|-------|
| DASHBOARD | CPU, Memory, Network, Battery, GPU, Temperature cards | Per-metric color |
| SYSTEM | Detailed system info: CPU cores, Disk, Network interfaces, Temps, GPU | Default |
| AGENTS | oMLX, Quota, Banwagon status | Default |

## Layout

```
┌─────────────────────────────────────────────────────────┐
│  SYSTEM MONITOR                            [q] [r]      │
├─────────────────────────────────────────────────────────┤
│  [1] DASHBOARD  │  [2] SYSTEM  │  [3] AGENTS            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─ CPU ────────┐ ┌─ Memory ──────┐ ┌─ Network ──────┐ │
│  │ 45.2%        │ │ 16.2 GB       │ │ ↓ 1.23 MB/s    │ │
│  │ ████████░░░░ │ │ ██████████░░░ │ │ ↑ 0.45 MB/s   │ │
│  └──────────────┘ └───────────────┘ └────────────────┘ │
│     cyan            blue           green               │
│                                                         │
│  ┌─ Battery ───┐ ┌─ GPU ─────────┐ ┌─ Temperature ──┐ │
│  │ 87%  ⚡2:15  │ │ 45W / 150W   │ │ CPU: 62°C     │ │
│  │ ███████░░░░ │ │ ███░░░░░░░░░ │ │ GPU: 71°C     │ │
│  └──────────────┘ └───────────────┘ └────────────────┘ │
│     yellow          magenta          red               │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Press 1-3 to switch tabs  │  Press r to refresh       │
└─────────────────────────────────────────────────────────┘
```

## Color Scheme

| Metric | Color | Hex |
|--------|-------|-----|
| CPU | cyan | #00d4ff |
| Memory | blue | #4d9de0 |
| Network | green | #3fb950 |
| Battery | yellow | #f0c000 |
| GPU | magenta | #d53f8c |
| Temperature | red | #f85149 |

## Features

- **Real-time refresh**: Every 2 seconds via timer
- **Keyboard navigation**: `1/2/3` switch tabs, `q` quit, `r` refresh
- **API polling**: `GET /api/snapshot` for current state
- **Progress bars**: ASCII art bars showing usage percentage
- **Error handling**: Show `--` when API unavailable

## File Structure

```
tui/
├── app.py          # Main App with TabbedContent
├── widgets.py      # MetricCard widget
api_client.py      # HTTP client for Go backend
main.py            # CLI entry point
```

## Implementation Notes

- Use `httpx.AsyncClient` for non-blocking API calls
- Textual `Timer` for periodic refresh
- CSS styling via `app.py` inline styles or TCSS file
- All metrics displayed as card grid with colored headers
