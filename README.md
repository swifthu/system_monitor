# System Monitor

macOS 系统监控工具，支持 **MiniMax API 配额** 和 **BANWAGON 流量** 监控，基于 Go 后端 + Python Textual TUI。

## 功能概览

### SYSTEM Tab

| 监控项 | 说明 |
|--------|------|
| CPU | 整体利用率（进度条） |
| Memory | 使用率（进度条） |
| Network | 上传/下载速度 (KB/s 或 MB/s) |
| Disk | 容量使用率（进度条）+ 已用/总量 GB |
| Power | 系统总功耗 (All: X.XW) |
| Temperature | CPU / GPU 温度 |

### QUOTA Tab

| 监控项 | 说明 |
|--------|------|
| MiniMax Models | 各模型 5H/Week 配额剩余量，进度条 + 重置倒计时 |
| Banwagon | 月流量使用量/配额（GB），位置信息，重置倒计时 |

## 快速开始

```bash
# 1. 安装依赖
pip install textual httpx

# 2. 启动 Go 后端
go build -o server .
./server

# 3. 启动 TUI（新窗口）
source ~/.venv/bin/activate
python3 -m tui.app
# 或
python3 main.py
```

访问 http://localhost:8001 查看 Web UI（备选）

## 键盘快捷键

| 键 | 功能 |
|----|------|
| `1` | 切换到 SYSTEM Tab |
| `2` | 切换到 QUOTA Tab |
| `r` | 刷新数据 |
| `q` | 退出 |

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /` | Web UI (HTML) |
| `GET /api/snapshot` | 系统监控完整 JSON |
| `GET /api/banwagon` | BANWAGON 流量信息 |

## 数据源

- **macmon**: Apple Silicon 功耗/温度（`macmon pipe --interval 200`）
- **powermetrics**: 备用功耗采集（sudo）
- **netstat -ib**: 网络 IO 速率
- **diskutil**: APFS 磁盘容量
- **mmx CLI**: MiniMax API 配额（通过 CLI 调用）

## 架构

```
system_monitor/
├── main.go              # Go 后端入口
├── api_client.py         # Python API 客户端
├── server               # 编译后的 Go 二进制
├── collector/            # Go 采集模块
│   ├── collector.go     # 主 collector + macmon 管理
│   ├── power.go         # 功耗/温度采集
│   ├── cpu.go           # CPU 采集
│   ├── memory.go        # 内存采集
│   ├── disk.go          # 磁盘采集
│   ├── network.go       # 网络采集
│   └── types.go         # 数据类型
├── tui/                 # Python Textual TUI
│   ├── app.py           # 主应用
│   └── styles.tcss      # 样式
└── config.json          # 配置文件
```

## 配置文件

`config.json` 包含 BANWAGON API 密钥：

```json
{
  "banwagon_veid": "your_veid",
  "banwagon_api_key": "your_api_key"
}
```

## 技术栈

- **后端**: Go 1.26+（高并发数据采集）
- **TUI**: Python 3.12 + Textual（终端 UI 框架）
- **前端**: 原生 HTML/CSS/JS（Web UI 备选）
