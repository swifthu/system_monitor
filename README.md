# System Monitor

macOS 系统监控工具，支持 **oMLX** 模型运行状态和 **BANWAGON** 流量监控。

## 功能概览

### SYSTEM Tab
| 监控项 | 说明 |
|--------|------|
| CPU | 整体利用率 |
| Memory | 使用率、已用/总容量 |
| Power | 系统总功耗 + CPU/GPU/RAM/SYS 分项 breakdown |
| Temperature | CPU / GPU 温度 |
| Disk | 容量、使用率（Total - Free 计算） |
| Network | 上传 / 下载速度 (MB/s) |

### oMLX Tab
| 监控项 | 说明 |
|--------|------|
| Status | 发现模型数、已加载模型数、当前默认模型 |
| Performance | 平均 prefill tok/s、generation tok/s、Cache 命中率 |
| Memory | 模型显存已用 / 最大 |
| Models | 所有模型列表（状态、内存占用） |

> 需要 oMLX 运行在 `localhost:8000`

### QUOTA Tab
| 监控项 | 说明 |
|--------|------|
| MiniMax Models | 各模型 5H / Week 配额剩余量，实时进度条 |
| BANWAGON | 月流量使用量 / 配额（GB）、RAM / Disk 配置、IP / OS / 位置信息、重置倒计时 |

## 快速开始

```bash
cd /Users/jimmyhu/Documents/CC/Projects/system_monitor
go build -o server .
./server
```

访问 http://localhost:8001

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /` | Web UI (HTML) |
| `GET /api/snapshot` | 系统监控完整 JSON |
| `GET /api/oml` | oMLX 状态 |
| `GET /api/oml/models` | oMLX 模型详细列表 |
| `GET /api/quota` | MiniMax 配额信息 |
| `GET /api/banwagon` | BANWAGON 流量信息 |

## 数据源

- **macmon**: Apple Silicon GPU/功耗数据（`macmon pipe --interval 200`）
- **powermetrics**: Intel Mac 功耗（sudo）
- **netstat -ib**: 网络 IO 速率
- **diskutil**: APFS 磁盘容量

## 架构

- **后端**: Go 1.26+
- **前端**: 原生 HTML/CSS/JS，无框架依赖
- **Collector**: 并发采集，2s 默认间隔
- **macmon**: 单进程管理，避免重复启动

## 项目结构

```
system_monitor/
├── main.go              # 入口
├── api/
│   ├── handlers.go      # HTTP handlers
│   ├── system.go       # /api/snapshot
│   ├── omlx.go          # /api/oml
│   └── quota.go         # /api/quota
├── collector/
│   ├── collector.go     # 主 collector
│   ├── power.go         # 功耗采集
│   ├── cpu.go           # CPU 采集
│   ├── memory.go        # 内存采集
│   ├── disk.go          # 磁盘采集
│   ├── network.go       # 网络采集
│   └── types.go         # 数据类型
├── config/
│   └── config.go        # 配置文件
├── frontend/
│   └── index.html       # Web UI
└── tests/
    └── integration_test.go
```
