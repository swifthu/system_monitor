#!/usr/bin/env python3
"""
系统监控脚本 - 内存压力 & 实时功率 & CPU/GPU 温度 & 网络/磁盘 IO
macOS only，Apple Silicon 优先使用 macmon（无需 sudo）
"""

import time
import subprocess
import re
import json
import os
import statistics
import signal
import threading
import http.server
import socketserver
from dataclasses import dataclass, asdict
from typing import Optional

# ─── 内存 ───────────────────────────────────────────────────────────────────

def get_memory_info() -> dict:
    """获取内存使用情况"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 1),
            "used_gb": round(mem.used / (1024**3), 1),
            "available_gb": round(mem.available / (1024**3), 1),
            "percent": mem.percent,
            "swap_used_gb": round(swap.used / (1024**3), 1),
            "swap_total_gb": round(swap.total / (1024**3), 1),
        }
    except ImportError:
        return _get_memory_info_fallback()


def _get_memory_info_fallback() -> dict:
    """vm_stat fallback"""
    output = subprocess.check_output(["vm_stat"], text=True)
    lines = output.strip().split("\n")
    stats = {}
    for line in lines:
        m = re.match(r'\s+(.+?):\s+(\d+)\.?', line)
        if m:
            stats[m.group(1).strip()] = int(m.group(2))
    pagesize = 4096
    try:
        pagesize = int(subprocess.check_output(
            ["sysctl", "-n", "hw.pagesize"], text=True).strip())
    except Exception:
        pass
    free = stats.get("Pages free", 0) * pagesize
    active = stats.get("Pages active", 0) * pagesize
    inactive = stats.get("Pages inactive", 0) * pagesize
    wired = stats.get("Pages wired down", 0) * pagesize
    compressed = stats.get("Pages used by compressor", 0) * pagesize
    total = free + active + inactive + wired + compressed
    used = active + wired + compressed
    return {
        "total_gb": round(total / (1024**3), 1),
        "used_gb": round(used / (1024**3), 1),
        "available_gb": round(free / (1024**3), 1),
        "percent": round(used / total * 100, 1) if total > 0 else 0,
        "swap_used_gb": 0,
        "swap_total_gb": 0,
    }


def get_memory_pressure() -> dict:
    """通过 memory_pressure 获取内存压力级别"""
    try:
        output = subprocess.check_output(
            ["memory_pressure"], text=True, stderr=subprocess.DEVNULL
        )
        m = re.search(r'System-wide memory free percentage:\s*(\d+)%', output)
        if m:
            free_pct = int(m.group(1))
            used_pct = 100 - free_pct
            if free_pct >= 25:
                level = "normal"
            elif free_pct >= 10:
                level = "warning"
            else:
                level = "critical"
            return {"level": level, "free_percent": free_pct, "used_percent": used_pct}
        return {"level": "unknown", "free_percent": None, "used_percent": None}
    except Exception as e:
        return {"level": f"error", "free_percent": None, "used_percent": None}


# ─── CPU ─────────────────────────────────────────────────────────────────────

def get_cpu_usage() -> dict:
    """获取 CPU 使用率（user/system/idle）"""
    try:
        import psutil
        # Warm-up: first call with interval=None gives baseline since boot,
        # then interval=0 returns meaningful deltas on subsequent calls
        psutil.cpu_percent(interval=None)
        per_cpu = psutil.cpu_percent(interval=0, percpu=True)
        total = psutil.cpu_percent(interval=0)
        # user vs system 需要算 cputimes
        times = psutil.cpu_times()
        total_time = times.user + times.system + times.idle
        if total_time > 0:
            user_pct = times.user / total_time * 100
            system_pct = times.system / total_time * 100
        else:
            user_pct = system_pct = 0
        return {
            "total": round(total, 1),
            "user": round(user_pct, 1),
            "system": round(system_pct, 1),
            "idle": round(100 - total, 1),
            "cores": len(per_cpu),
            "per_core": [round(p, 1) for p in per_cpu],
        }
    except Exception:
        return _get_cpu_usage_fallback()


def _get_cpu_usage_fallback() -> dict:
    """top fallback"""
    try:
        output = subprocess.check_output(
            ["top", "-l", "1", "-n", "1"], text=True, stderr=subprocess.DEVNULL
        )
        # 格式: "CPU usage: X% user, Y% sys, Z% idle"
        m = re.search(r'CPU usage:\s*([\d.]+)% user,\s*([\d.]+)% sys,\s*([\d.]+)% idle', output)
        if m:
            user, system, idle = float(m.group(1)), float(m.group(2)), float(m.group(3))
            return {"total": round(user+system, 1), "user": user, "system": system, "idle": idle, "cores": None}
    except Exception:
        pass
    return {"total": 0, "user": 0, "system": 0, "idle": 0, "cores": 0}


# ─── 磁盘 ───────────────────────────────────────────────────────────────────

_last_disk_io = None
_last_net_io = None
_last_io_time = 0

def get_disk_io() -> dict:
    """获取磁盘 IO（读写速度）"""
    global _last_disk_io, _last_io_time
    try:
        import psutil, time
        io = psutil.disk_io_counters()
        now = time.time()
        if _last_disk_io is not None:
            dt = now - _last_io_time
            if dt >= 0.05:  # 降低阈值到 50ms
                read_mb = (io.read_bytes - _last_disk_io.read_bytes) / dt / (1024**2)
                write_mb = (io.write_bytes - _last_disk_io.write_bytes) / dt / (1024**2)
                _last_disk_io = io
                _last_io_time = now
                return {"read_mb_s": max(0, round(read_mb, 1)), "write_mb_s": max(0, round(write_mb, 1))}
        _last_disk_io = io
        _last_io_time = now
        return {"read_mb_s": 0, "write_mb_s": 0}
    except Exception:
        return {"read_mb_s": 0, "write_mb_s": 0}


def get_network_io() -> dict:
    """获取网络 IO（上传/下载速度）"""
    global _last_net_io, _last_io_time
    try:
        import psutil, time
        n = psutil.net_io_counters()
        now = time.time()
        if _last_net_io is not None:
            dt = now - _last_io_time
            if dt >= 0.05:  # 降低阈值到 50ms
                recv_mb = (n.bytes_recv - _last_net_io.bytes_recv) / dt / (1024**2)
                sent_mb = (n.bytes_sent - _last_net_io.bytes_sent) / dt / (1024**2)
                _last_net_io = n
                _last_io_time = now
                return {"recv_mb_s": max(0, round(recv_mb, 2)), "sent_mb_s": max(0, round(sent_mb, 2))}
            # dt太小，只更新时间戳，下次再计算
            _last_io_time = now
            return {"recv_mb_s": 0, "sent_mb_s": 0}
        _last_net_io = n
        _last_io_time = now
        return {"recv_mb_s": 0, "sent_mb_s": 0}
    except Exception:
        return {"recv_mb_s": 0, "sent_mb_s": 0}


def get_disk_usage() -> dict:
    """获取磁盘使用情况"""
    try:
        import psutil
        for part in psutil.disk_partitions():
            if part.mountpoint == "/":
                usage = psutil.disk_usage(part.mountpoint)
                return {
                    "total_gb": round(usage.total / (1024**3), 1),
                    "used_gb": round(usage.used / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent": usage.percent,
                }
    except Exception:
        pass
    return {}


# ─── 网络 ────────────────────────────────────────────────────────────────────

# ─── 功率（macmon 常驻进程）─────────────────────────────────────────────────

# macmon 全局常驻进程
_macmon_proc: Optional[subprocess.Popen] = None
_macmon_buf = ""

def _macmon_start() -> bool:
    """启动 macmon pipe 子进程（常驻）"""
    global _macmon_proc
    if _macmon_proc is not None:
        return True
    try:
        import subprocess
        import os
        import fcntl

        _macmon_proc = subprocess.Popen(
            ["macmon", "pipe", "--interval", "200"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        # 使用 fcntl 设置 O_NONBLOCK，绕过 Python buffered I/O
        fd = _macmon_proc.stdout.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # 预热：等待第一行数据（macmon 启动约 1-2s）
        import select
        buf = b""
        for _ in range(20):  # 最多等 2 秒
            r, _, _ = select.select([_macmon_proc.stdout], [], [], 0.1)
            if r:
                try:
                    chunk = os.read(fd, 4096)
                    if chunk:
                        buf += chunk
                        if b"\n" in buf:
                            return True
                except (IOError, OSError):
                    pass
        # 启动超时，仍认为进程活着
        return True
    except Exception:
        _macmon_proc = None
        return False


_macmon_lock = threading.Lock()

def _macmon_read() -> Optional[dict]:
    """从 macmon 常驻进程读取一行，解析功率数据（线程安全）"""
    global _macmon_proc
    if _macmon_proc is None:
        return None

    with _macmon_lock:
        try:
            import os
            import select

            fd = _macmon_proc.stdout.fileno()

            # 先检查是否有数据可读
            r, _, _ = select.select([_macmon_proc.stdout], [], [], 0.1)
            if not r:
                return None  # 超时，无数据

            # 读取数据（绕过 Python buffered I/O）
            buf = b""
            try:
                chunk = os.read(fd, 4096)
                if not chunk:
                    _macmon_proc = None
                    return None
                buf = chunk
            except (IOError, OSError):
                return None

            # 找到完整行
            if b"\n" in buf:
                line = buf.split(b"\n")[0].decode("utf-8")
            else:
                # 不完整，等待下次调用
                return None

            data = json.loads(line)
            return {
                "all_power_w": round(data.get("all_power", 0), 2),
                "cpu_power_w": round(data.get("cpu_power", 0), 2),
                "gpu_power_w": round(data.get("gpu_power", 0), 2),
                "ane_power_w": round(data.get("ane_power", 0), 2),
                "ram_power_w": round(data.get("ram_power", 0), 2),
                "sys_power_w": round(data.get("sys_power", 0), 2),
                "cpu_temp_c": round(data.get("temp", {}).get("cpu_temp_avg", 0), 1),
                "gpu_temp_c": round(data.get("temp", {}).get("gpu_temp_avg", 0), 1),
                "cpu_usage_pct": round(data.get("cpu_usage_pct", 0) * 100, 1),
                "gpu_usage_pct": round(data.get("gpu_usage", [0, 0])[1] * 100, 1) if data.get("gpu_usage") else 0,
                "gpu_usage": [round(v, 1) for v in data.get("gpu_usage", [])],
                "source": "macmon",
            }
        except Exception:
            _macmon_proc = None
            return None


def _macmon_stop():
    """停止 macmon 常驻进程"""
    global _macmon_proc
    if _macmon_proc:
        _macmon_proc.terminate()
        _macmon_proc.wait()
        _macmon_proc = None


def _parse_powermetrics() -> Optional[dict]:
    """尝试调用 powermetrics（需要 sudo）获取功率"""
    try:
        proc = subprocess.Popen(
            ["sudo", "powermetrics", "--samplers", "cpu_power", "-i", "500", "-n", "1"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        )
        out, _ = proc.communicate(timeout=10)
        
        cpu_mw = re.search(r'CPU Power:\s*([\d.]+)\s+mW', out)
        gpu_mw = re.search(r'GPU Power:\s*([\d.]+)\s+mW', out)
        ane_mw = re.search(r'ANE Power:\s*([\d.]+)\s+mW', out)
        
        if not cpu_mw:
            return None
        
        total_w = 0
        cpu_w = gpu_w = ane_w = 0
        if cpu_mw:
            cpu_w = round(float(cpu_mw.group(1)) / 1000, 2)
            total_w += cpu_w
        if gpu_mw:
            gpu_w = round(float(gpu_mw.group(1)) / 1000, 2)
            total_w += gpu_w
        if ane_mw:
            ane_w = round(float(ane_mw.group(1)) / 1000, 2)
            total_w += ane_w
        
        return {
            "all_power_w": round(total_w, 2),
            "cpu_power_w": cpu_w,
            "gpu_power_w": gpu_w,
            "ane_power_w": ane_w,
            "ram_power_w": 0,
            "sys_power_w": 0,
            "cpu_temp_c": 0,
            "gpu_temp_c": 0,
            "cpu_usage_pct": 0,
            "gpu_usage_pct": 0,
            "source": "powermetrics",
        }
    except Exception:
        return None


def get_power_info() -> dict:
    """获取功率信息，优先 macmon 常驻进程，fallback powermetrics"""
    result = _macmon_read()
    if result:
        return result
    
    # macmon 未启动，尝试启动
    if _macmon_start():
        result = _macmon_read()
        if result:
            return result
    
    # 最后尝试 powermetrics
    result = _parse_powermetrics()
    if result:
        return result
    
    return {
        "all_power_w": None, "cpu_power_w": None, "gpu_power_w": None,
        "ane_power_w": None, "ram_power_w": None, "sys_power_w": None,
        "cpu_temp_c": None, "gpu_temp_c": None,
        "cpu_usage_pct": None, "gpu_usage_pct": None,
        "source": None,
    }


# ─── macmon HTTP server（备用）───────────────────────────────────────────────

def get_macmon_http() -> Optional[dict]:
    """尝试从 macmon HTTP server 获取数据"""
    try:
        import urllib.request
        resp = urllib.request.urlopen("http://localhost:4949/json", timeout=1.0)
        data = json.loads(resp.read())
        return data
    except Exception:
        return None


# ─── 主数据结构 ──────────────────────────────────────────────────────────────

@dataclass
class SystemSnapshot:
    timestamp: float
    # 内存
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    memory_pressure_level: str
    memory_free_percent: Optional[int]
    swap_used_gb: float
    swap_total_gb: float
    # CPU
    cpu_percent: float
    cpu_user: float
    cpu_system: float
    cpu_idle: float
    cpu_cores: int
    cpu_per_core: list
    # 功率
    power_info: dict
    # 磁盘
    disk_read_mb_s: float
    disk_write_mb_s: float
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    disk_percent: float
    # 网络
    net_recv_mb_s: float
    net_sent_mb_s: float


def take_snapshot() -> SystemSnapshot:
    """获取当前系统状态"""
    mem = get_memory_info()
    pressure = get_memory_pressure()
    cpu = get_cpu_usage()
    disk_io = get_disk_io()
    disk_usage = get_disk_usage()
    net_io = get_network_io()
    power = get_power_info()
    
    return SystemSnapshot(
        timestamp=time.time(),
        memory_percent=mem["percent"],
        memory_used_gb=mem["used_gb"],
        memory_total_gb=mem["total_gb"],
        memory_pressure_level=pressure["level"],
        memory_free_percent=pressure["free_percent"],
        swap_used_gb=mem["swap_used_gb"],
        swap_total_gb=mem["swap_total_gb"],
        cpu_percent=cpu["total"],
        cpu_user=cpu["user"],
        cpu_system=cpu["system"],
        cpu_idle=cpu["idle"],
        cpu_cores=cpu["cores"],
        cpu_per_core=cpu.get("per_core", []),
        power_info=power,
        disk_read_mb_s=disk_io["read_mb_s"],
        disk_write_mb_s=disk_io["write_mb_s"],
        disk_total_gb=disk_usage.get("total_gb", 0),
        disk_used_gb=disk_usage.get("used_gb", 0),
        disk_free_gb=disk_usage.get("free_gb", 0),
        disk_percent=disk_usage.get("percent", 0),
        net_recv_mb_s=net_io["recv_mb_s"],
        net_sent_mb_s=net_io["sent_mb_s"],
    )


def format_snapshot(s: SystemSnapshot) -> str:
    """格式化输出"""
    dt = time.strftime("%H:%M:%S", time.localtime(s.timestamp))
    
    # 内存行
    mem_str = (f"💾 内存 {s.memory_percent:.1f}% "
               f"({s.memory_used_gb:.1f}/{s.memory_total_gb:.1f} GB)")
    if s.swap_total_gb > 0:
        mem_str += f" | SWAP {s.swap_used_gb:.1f}/{s.swap_total_gb:.1f} GB"
    
    pressure_emoji = {"normal": "🟢", "warning": "🟡", "critical": "🔴", "unknown": "⚪"}.get(
        s.memory_pressure_level, "⚪")
    free_str = f"{s.memory_free_percent}% free" if s.memory_free_percent is not None else ""
    pressure_str = f"{pressure_emoji} {s.memory_pressure_level.upper()} {free_str}".strip()
    
    # CPU 行
    cpu_str = (f"⚙️ CPU {s.cpu_percent:.1f}% "
               f"(U:{s.cpu_user:.0f}% S:{s.cpu_system:.0f}% I:{s.cpu_idle:.0f}%)")
    if s.cpu_cores > 0:
        cpu_str += f" ×{s.cpu_cores}核"
    
    # 功率行
    pi = s.power_info
    power_parts = []
    if pi.get("all_power_w") is not None:
        power_parts.append(f"功耗 {pi['all_power_w']:.1f} W")
    if pi.get("cpu_power_w"):
        power_parts.append(f"CPU {pi['cpu_power_w']:.1f} W")
    if pi.get("gpu_power_w"):
        power_parts.append(f"GPU {pi['gpu_power_w']:.1f} W")
    if pi.get("ane_power_w"):
        power_parts.append(f"ANE {pi['ane_power_w']:.1f} W")
    
    # 温度
    temp_parts = []
    if pi.get("cpu_temp_c") and pi["cpu_temp_c"] > 0:
        temp_parts.append(f"CPU {pi['cpu_temp_c']:.0f}°C")
    if pi.get("gpu_temp_c") and pi["gpu_temp_c"] > 0:
        temp_parts.append(f"GPU {pi['gpu_temp_c']:.0f}°C")
    
    # 磁盘
    disk_str = ""
    if s.disk_total_gb > 0:
        disk_str = (f"💿 磁盘 {s.disk_percent:.1f}% "
                    f"({s.disk_used_gb:.0f}/{s.disk_total_gb:.0f} GB)")
        io_parts = []
        if s.disk_read_mb_s > 0.1:
            io_parts.append(f"↑{s.disk_read_mb_s:.1f} MB/s")
        if s.disk_write_mb_s > 0.1:
            io_parts.append(f"↓{s.disk_write_mb_s:.1f} MB/s")
        if io_parts:
            disk_str += " [" + " ".join(io_parts) + "]"
    
    # 网络
    net_parts = []
    if s.net_recv_mb_s > 0.01:
        net_parts.append(f"↓{s.net_recv_mb_s:.2f} MB/s")
    if s.net_sent_mb_s > 0.01:
        net_parts.append(f"↑{s.net_sent_mb_s:.2f} MB/s")
    net_str = "🌐 " + " ".join(net_parts) if net_parts else ""
    
    # 组装
    lines = [
        f"[{dt}]",
        f"  {mem_str} | {pressure_str}",
        f"  {cpu_str}",
    ]
    
    if power_parts:
        lines.append(f"  ⚡ {' | '.join(power_parts)}")
    if temp_parts:
        lines.append(f"  🌡️ {' '.join(temp_parts)}")
    if disk_str:
        lines.append(f"  {disk_str}")
    if net_str:
        lines.append(f"  {net_str}")
    
    return "\n".join(lines)


def format_compact(s: SystemSnapshot) -> str:
    """紧凑单行格式"""
    dt = time.strftime("%H:%M:%S", time.localtime(s.timestamp))
    pi = s.power_info
    
    power_str = ""
    if pi.get("all_power_w") is not None:
        power_str = f" ⚡{pi['all_power_w']:.1f}W"
    elif pi.get("source") == "powermetrics":
        power_str = " ⚡(sudo)"
    else:
        power_str = " ⚡-"
    
    temp_str = ""
    if pi.get("cpu_temp_c") and pi["cpu_temp_c"] > 0:
        temp_str = f" 🌡{pi['cpu_temp_c']:.0f}°C"
    
    net_parts = []
    if s.net_recv_mb_s > 0.01:
        net_parts.append(f"↓{s.net_recv_mb_s:.2f}")
    if s.net_sent_mb_s > 0.01:
        net_parts.append(f"↑{s.net_sent_mb_s:.2f}")
    net_str = " 🌐" + " ".join(net_parts) if net_parts else ""
    
    return (f"[{dt}] 💾{s.memory_percent:.0f}% ⚙️{s.cpu_percent:.0f}%"
            f"{power_str}{temp_str}{net_str}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="系统监控")
    parser.add_argument("--compact", action="store_true", help="紧凑单行模式")
    parser.add_argument("--interval", type=float, default=2.0, help="采样间隔（秒）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()
    
    print("=" * 65)
    print("系统监控 - 内存 | CPU | 功率 | 温度 | 磁盘 | 网络")
    print("按 Ctrl+C 退出")
    print("=" * 65)
    print()
    
    # 预热 macmon
    print("正在连接 macmon...")
    macmon_ready = _macmon_start()
    if macmon_ready:
        print("✅ macmon 已连接 (无需 sudo)")
    else:
        print("⚠️  macmon 不可用，尝试 powermetrics...")
    print()
    print()
    
    history = []
    interval = max(0.5, args.interval)
    
    try:
        while True:
            snap = take_snapshot()
            history.append(snap)
            
            if args.json:
                d = asdict(snap)
                d["power_info"] = snap.power_info
                print(json.dumps(d, default=str))
            elif args.compact:
                print(format_compact(snap))
            else:
                print(format_snapshot(snap))
            
            # 每 20 个样本统计
            if len(history) % 20 == 0 and len(history) > 0:
                mem_vals = [s.memory_percent for s in history[-20:]]
                cpu_vals = [s.cpu_percent for s in history[-20:]]
                print(f"\n  ── 近20次平均: 内存 {statistics.mean(mem_vals):.1f}% | CPU {statistics.mean(cpu_vals):.1f}%")
                
                pi_list = [s.power_info.get("all_power_w") for s in history[-20:]
                          if s.power_info.get("all_power_w")]
                if pi_list:
                    print(f"  ── 近20次平均: 功耗 {statistics.mean(pi_list):.2f} W")
                print()
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n退出")
    finally:
        _macmon_stop()
        if len(history) > 1:
            mem_vals = [s.memory_percent for s in history]
            cpu_vals = [s.cpu_percent for s in history]
            pi_list = [s.power_info.get("all_power_w") for s in history
                      if s.power_info.get("all_power_w")]
            print(f"  本次平均: 内存 {statistics.mean(mem_vals):.1f}% | CPU {statistics.mean(cpu_vals):.1f}%")
            if pi_list:
                print(f"  本次平均: 功耗 {statistics.mean(pi_list):.2f} W")
            print(f"  共采集 {len(history)} 次")


# ─── HTTP Server ─────────────────────────────────────────────────────────────

class MetricsHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler serving system metrics as JSON"""
    
    latest_snapshot: Optional[SystemSnapshot] = None
    
    def log_message(self, fmt, *args):
        # 安静日志
        pass
    
    def do_GET(self):
        if self.path == "/" or self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        
        elif self.path == "/json":
            s = MetricsHandler.latest_snapshot
            if s is None:
                self.send_error(503, "No data yet")
                return
            
            import datetime
            d = {
                "timestamp": datetime.datetime.fromtimestamp(s.timestamp).isoformat(),
                "memory": {
                    "percent": s.memory_percent,
                    "used_gb": s.memory_used_gb,
                    "total_gb": s.memory_total_gb,
                    "pressure": s.memory_pressure_level,
                    "free_percent": s.memory_free_percent,
                    "swap_used_gb": s.swap_used_gb,
                    "swap_total_gb": s.swap_total_gb,
                },
                "cpu": {
                    "percent": s.cpu_percent,
                    "user": s.cpu_user,
                    "system": s.cpu_system,
                    "idle": s.cpu_idle,
                    "cores": s.cpu_cores,
                },
                "power": s.power_info,
                "disk": {
                    "read_mb_s": s.disk_read_mb_s,
                    "write_mb_s": s.disk_write_mb_s,
                    "total_gb": s.disk_total_gb,
                    "used_gb": s.disk_used_gb,
                    "free_gb": s.disk_free_gb,
                    "percent": s.disk_percent,
                },
                "network": {
                    "recv_mb_s": s.net_recv_mb_s,
                    "sent_mb_s": s.net_sent_mb_s,
                },
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(d, indent=2).encode())
        
        elif self.path == "/metrics":
            # Prometheus text format
            s = MetricsHandler.latest_snapshot
            if s is None:
                self.send_error(503, "No data yet")
                return
            
            pi = s.power_info
            lines = [
                "# HELP system_memory_percent System memory usage percent",
                "# TYPE system_memory_percent gauge",
                f"system_memory_percent {s.memory_percent}",
                "# HELP system_memory_used_gb System memory used in GB",
                "# TYPE system_memory_used_gb gauge",
                f"system_memory_used_gb {s.memory_used_gb}",
                "# HELP system_cpu_percent System CPU usage percent",
                "# TYPE system_cpu_percent gauge",
                f"system_cpu_percent {s.cpu_percent}",
                "# HELP system_power_watts Total system power in watts",
                "# TYPE system_power_watts gauge",
                f"system_power_watts {pi.get('all_power_w') or 0}",
                "# HELP system_cpu_power_watts CPU power in watts",
                "# TYPE system_cpu_power_watts gauge",
                f"system_cpu_power_watts {pi.get('cpu_power_w') or 0}",
                "# HELP system_gpu_power_watts GPU power in watts",
                "# TYPE system_gpu_power_watts gauge",
                f"system_gpu_power_watts {pi.get('gpu_power_w') or 0}",
                "# HELP system_cpu_temp_celsius CPU temperature in Celsius",
                "# TYPE system_cpu_temp_celsius gauge",
                f"system_cpu_temp_celsius {pi.get('cpu_temp_c') or 0}",
                "# HELP system_gpu_temp_celsius GPU temperature in Celsius",
                "# TYPE system_gpu_temp_celsius gauge",
                f"system_gpu_temp_celsius {pi.get('gpu_temp_c') or 0}",
                "# HELP system_disk_read_mb_s Disk read MB/s",
                "# TYPE system_disk_read_mb_s gauge",
                f"system_disk_read_mb_s {s.disk_read_mb_s}",
                "# HELP system_disk_write_mb_s Disk write MB/s",
                "# TYPE system_disk_write_mb_s gauge",
                f"system_disk_write_mb_s {s.disk_write_mb_s}",
                "# HELP system_net_recv_mb_s Network receive MB/s",
                "# TYPE system_net_recv_mb_s gauge",
                f"system_net_recv_mb_s {s.net_recv_mb_s}",
                "# HELP system_net_sent_mb_s Network send MB/s",
                "# TYPE system_net_sent_mb_s gauge",
                f"system_net_sent_mb_s {s.net_sent_mb_s}",
                "",
            ]
            body = "\n".join(lines).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)
        
        else:
            self.send_error(404)


def run_http_server(port: int = 8001, interval: float = 2.0):
    """启动 HTTP 服务，每 interval 秒更新一次快照"""
    import http.server, socketserver
    import threading
    
    # 启动 macmon
    macmon_ok = _macmon_start()
    print(f"macmon: {'OK' if macmon_ok else 'FAILED'}")
    
    # 后台更新线程
    def updater():
        while True:
            try:
                snap = take_snapshot()
                MetricsHandler.latest_snapshot = snap
            except Exception as e:
                print(f"Update error: {e}")
            time.sleep(interval)
    
    t = threading.Thread(target=updater, daemon=True)
    t.start()
    
    class QuietTCPServer(socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True
    
    with QuietTCPServer(("", port), MetricsHandler) as httpd:
        print(f"🌐 HTTP 服务运行在 http://localhost:{port}")
        print(f"   /json    - 完整 JSON 指标")
        print(f"   /metrics - Prometheus 格式")
        print(f"   /health  - 健康检查")
        print(f"   更新间隔: {interval}s")
        print()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n关闭...")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="系统监控 HTTP 服务")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--interval", type=float, default=2.0)
    parsed = parser.parse_args()
    run_http_server(port=parsed.port, interval=parsed.interval)

