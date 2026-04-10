# System Monitor

macOS 系统监控工具，同时支持 **oMLX** 模型运行状态和 **OpenClaw** 多 Agent 调度监控。

## 功能概览

### SYSTEM Tab
| 监控项 | 说明 |
|--------|------|
| CPU | 整体利用率 + 每核实时数据 |
| GPU | 利用率（macmon） |
| Memory | 使用率、压力级别、Swap |
| Power | 系统总功耗（SoC + System） |
| Temperature | CPU / GPU 温度 |
| Disk | 容量、读写速度 |
| Network | 上传 / 下载速度 |
| History | 近 60 条时序 sparkline 图表（CPU+GPU、温度、功耗、网络） |

### oMLX Tab
| 监控项 | 说明 |
|--------|------|
| Status | 发现模型数、已加载模型数、当前默认模型 |
| Performance | 平均 prefill tok/s、generation tok/s、Cache 命中率 |
| Memory | 模型显存已用 / 最大 |
| TOKENS & TASK | Prompt / Completion token 总数、活跃 / 等待请求数 |
| Models | 所有模型列表（状态、内存占用） |

> 需要 oMLX 运行在 `localhost:8000`，API Key：`oMLX`

### OPENCLAW Tab
| 监控项 | 说明 |
|--------|------|
| Gateway | 版本号、任务进度条 |
| Tasks | Total / Active / Succeeded / Failed、CLI / Cron / Timeout breakdown |
| Telegram | Bot 状态（ON/OFF）、Bot 用户名、已配置通道数 |
| Sessions | 会话总数、活跃分钟数、活跃 Agent 数 |
| Agents | 6 个 Agent 卡片（名称、模型、路由、心跳调度） |

> 需要 OpenClaw Gateway 运行中（`openclaw gateway`），CLI 命令行工具已安装

### QUOTA Tab
| 监控项 | 说明 |
|--------|------|
| MiniMax QUOTA | 各模型 5H / Week 配额剩余量及进度条 |
| MiniMax Reset | 5H 窗口剩余时间、周配额重置倒计时 |
| BANWAGON | 月流量使用量 / 配额、RAM / Disk 配置、IP / OS 信息、重置倒计时 |

> BANWAGON 配置位于 `config.json`（不提交到 git）

```bash
# 进入项目目录
cd /Users/jimmyhu/Documents/CC/Projects/system_monitor

# 激活虚拟环境
source /Users/jimmyhu/Documents/CC/.venv/bin/activate

# 启动 Web 仪表板（所有三个 Tab）
python system_monitor_dashboard.py

# 指定端口
python system_monitor_dashboard.py --port 8001

# 绑定所有网络接口（局域网访问）
python system_monitor_dashboard.py --host 0.0.0.0 --port 8001
```

访问 http://localhost:8001

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /` | Web UI (HTML) |
| `GET /json` | 系统监控完整 JSON |
| `GET /metrics` | Prometheus 格式指标 |
| `GET /health` | 健康检查，返回 `OK` |
| `GET /api/interval?val=N` | 设置采集间隔（秒，1~30） |
| `GET /oml` | oMLX 状态（代理到 localhost:8000/api/status） |
| `GET /oml/models` | oMLX 模型详细列表（代理到 localhost:8000/v1/models/status） |
| `GET /openclaw/status` | OpenClaw Gateway 状态 |
| `GET /openclaw/health` | OpenClaw 通道健康状态 |
| `GET /openclaw/agents` | OpenClaw Agent 列表 |
| `GET /openclaw/sessions` | OpenClaw 所有会话 |

## 自适应节电

- **页面隐藏时**：自动停止所有轮询，节省浏览器资源
- **无请求时**：后端 collector 在 5 分钟无请求后进入空闲状态，跳过数据采集
- **Tab 级独立刷新**：SYSTEM + oMLX 共享 slider 控制的轮询间隔；OPENCLAW 独立 10s 固定刷新（OpenClaw CLI 命令较慢 ~5-10s）

## 架构说明

- **并发处理**：使用 `ThreadingTCPServer`，每个 HTTP 请求独立线程处理，OpenClaw 的 4 个并发 CLI 请求可真正并行执行
- **后端**：Python 3.12，psutil（系统数据）+ macmon（GPU/功率数据）
- **前端**：原生 HTML/CSS/JS，无框架依赖，Canvas 绘制 sparkline
- **oMLX 集成**：Python 代理端点转发 HTTP 请求，绕过 CORS 限制
- **OpenClaw 集成**：调用 `openclaw gateway call` 和 `openclaw agents/sessions` CLI 命令获取数据

## 平台

- **macOS only**
- **Apple Silicon** 优先使用 `macmon`（精确 GPU 功耗，无需 sudo）
- **Intel Mac** 使用 `powermetrics`（需要 sudo）

## 安装

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install psutil pytest
```

## 测试

```bash
python -m pytest tests/ -v
```

## 项目结构

```
system_monitor/
├── system_monitor.py          # 数据采集核心模块
├── system_monitor_dashboard.py  # Web Dashboard（包含 HTML/JS/CSS）
├── CLAUDE.md                   # 项目入口（已移至 /Users/jimmyhu/Documents/CC/Agents/CLAUDE.md）
├── README.md                   # 本文档
└── tests/
    ├── test_system_monitor.py  # 系统监控单元测试
    └── test_dashboard.py       # Dashboard HTTP 端点集成测试
```
