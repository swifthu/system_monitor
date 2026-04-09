# System Monitor

macOS 系统监控工具，支持内存、CPU、功率、温度、磁盘和网络监控。

## 功能

- **内存监控** — 使用率、压力级别、Swap
- **CPU 监控** — user/system/idle 百分比、多核支持
- **功率监控** — 优先使用 `macmon`（无需 sudo），fallback 到 `powermetrics`（需 sudo）
- **温度监控** — CPU/GPU 温度
- **磁盘 IO** — 读写速度
- **网络 IO** — 上传/下载速度
- **Web 仪表板** — 实时可视化界面

## 安装

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install psutil pytest
```

## 使用

### 命令行模式

```bash
# 默认模式（每2秒采样）
python system_monitor.py

# 紧凑模式
python system_monitor.py --compact

# JSON 输出
python system_monitor.py --json

# 调整采样间隔
python system_monitor.py --interval 5
```

### Web 仪表板

```bash
python system_monitor_dashboard.py --port 8001
```

访问 http://localhost:8001/

### API 端点

- `/json` — 完整 JSON 指标
- `/metrics` — Prometheus 格式
- `/health` — 健康检查

## 测试

```bash
python -m pytest tests/ -v
```

## 平台

- macOS only
- Apple Silicon 优先使用 macmon（无需 sudo）

## 依赖

- Python 3.12+
- psutil
- macmon（可选，用于精确功率数据）
