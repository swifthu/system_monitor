"""
system_monitor.py 单元测试

测试核心函数：
- get_memory_info() / _get_memory_info_fallback()
- get_cpu_usage() / _get_cpu_usage_fallback()
- get_disk_io()
- get_network_io()
- get_disk_usage()
- get_memory_pressure()
- take_snapshot()
- format_snapshot() / format_compact()
"""
import pytest
import subprocess
import sys
import os
import time
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Mock 数据 ────────────────────────────────────────────────────────────────

MOCK_VMEM = MagicMock(
    total=32 * 1024**3,
    used=16 * 1024**3,
    available=16 * 1024**3,
    percent=50.0,
)
MOCK_SWAP = MagicMock(
    total=2 * 1024**3,
    used=0.5 * 1024**3,
    percent=25.0,
)
MOCK_CPU_TIMES = MagicMock(user=1000.0, system=500.0, idle=1500.0)
MOCK_DISK_IO = MagicMock(read_bytes=1024**3, write_bytes=512**3)
MOCK_NET_IO = MagicMock(bytes_recv=1024**3, bytes_sent=512**3)
MOCK_PARTITION = MagicMock(mountpoint="/", fstype="apfs")
MOCK_DISK_USAGE = MagicMock(total=500*1024**3, used=200*1024**3, free=300*1024**3, percent=40.0)


def make_mock_psutil(vmem=MOCK_VMEM, swap=MOCK_SWAP, cpu_times=MOCK_CPU_TIMES,
                     per_cpu=None, disk_io=MOCK_DISK_IO, net_io=MOCK_NET_IO,
                     disk_partitions=None, disk_usage=None):
    """构建模拟 psutil 模块"""
    psutil = MagicMock()
    psutil.virtual_memory.return_value = vmem
    psutil.swap_memory.return_value = swap
    psutil.cpu_times.return_value = cpu_times
    psutil.cpu_percent.return_value = 50.0
    psutil.cpu_percent.return_value = 50.0
    if per_cpu is None:
        per_cpu = [50.0] * 8
    psutil.cpu_percent.return_value = 50.0
    type(psutil).per_cpu = property(lambda self: per_cpu)

    # per_cpu 是一个 MagicMock，cpu_percent(percpu=True) 返回 per_cpu
    psutil.cpu_percent = MagicMock(side_effect=lambda interval=None, percpu=False:
                                   per_cpu if percpu else 50.0)
    psutil.disk_io_counters.return_value = disk_io
    psutil.net_io_counters.return_value = net_io

    if disk_partitions is None:
        disk_partitions = [MOCK_PARTITION]
    psutil.disk_partitions.return_value = disk_partitions

    if disk_usage is None:
        disk_usage = MOCK_DISK_USAGE
    psutil.disk_usage.return_value = disk_usage

    return psutil


# ─── get_memory_info ───────────────────────────────────────────────────────────

class TestGetMemoryInfo:
    """测试 get_memory_info() 和 _get_memory_info_fallback()"""

    @patch.dict('sys.modules', {'psutil': MagicMock()})
    @patch('system_monitor.psutil')
    def test_get_memory_info_success(self, mock_psutil):
        """psutil 可用时返回正确格式"""
        from system_monitor import get_memory_info

        mock_psutil.virtual_memory.return_value = MOCK_VMEM
        mock_psutil.swap_memory.return_value = MOCK_SWAP

        result = get_memory_info()

        assert 'total_gb' in result
        assert 'used_gb' in result
        assert 'available_gb' in result
        assert 'percent' in result
        assert 'swap_used_gb' in result
        assert 'swap_total_gb' in result
        assert isinstance(result['total_gb'], float)
        assert result['percent'] == 50.0

    @patch('system_monitor.psutil')
    def test_get_memory_info_import_error_fallback(self, mock_psutil):
        """psutil ImportError 时调用 fallback"""
        from system_monitor import get_memory_info, _get_memory_info_fallback

        mock_psutil.virtual_memory.side_effect = ImportError

        with patch('system_monitor._get_memory_info_fallback') as mock_fb:
            mock_fb.return_value = {'total_gb': 16.0, 'used_gb': 8.0,
                                     'available_gb': 8.0, 'percent': 50.0,
                                     'swap_used_gb': 0.5, 'swap_total_gb': 2.0}
            result = get_memory_info()
            # 因为 ImportError 触发 fallback
            assert result['total_gb'] == 16.0


class TestGetMemoryInfoFallback:
    """测试 _get_memory_info_fallback()"""

    @patch('system_monitor.subprocess.check_output')
    @patch('system_monitor.subprocess.check_output')
    def test_fallback_vm_stat(self, mock_check_output):
        """vm_stat fallback 解析正常"""
        from system_monitor import _get_memory_info_fallback

        vm_stat_output = """Mach Virtual Memory Statistics: (page size of 4096 bytes)
Pages free:                         500000
Pages active:                       300000
Pages inactive:                     200000
Pages wired down:                   100000
Pages used by compressor:           50000"""

        # 两次调用：vm_stat 和 sysctl hw.pagesize
        mock_check_output.side_effect = [
            vm_stat_output,  # vm_stat
            "4096"           # sysctl -n hw.pagesize
        ]

        result = _get_memory_info_fallback()

        assert 'total_gb' in result
        assert 'used_gb' in result
        assert 'percent' in result
        assert result['total_gb'] > 0
        assert result['percent'] >= 0

    @patch('system_monitor.subprocess.check_output')
    def test_fallback_pagesize_default(self, mock_check_output):
        """sysctl 失败时使用默认 pagesize"""
        from system_monitor import _get_memory_info_fallback

        vm_stat_output = """Mach Virtual Memory Statistics: (page size of 4096 bytes)
Pages free:                         500000
Pages active:                       300000
Pages inactive:                     200000
Pages wired down:                   100000
Pages used by compressor:           50000"""

        mock_check_output.side_effect = [
            vm_stat_output,
            subprocess.CalledProcessError(1, 'sysctl')  # sysctl 失败
        ]

        result = _get_memory_info_fallback()
        assert result['total_gb'] > 0


# ─── get_cpu_usage ─────────────────────────────────────────────────────────────

class TestGetCpuUsage:
    """测试 get_cpu_usage() 和 _get_cpu_usage_fallback()"""

    @patch('system_monitor.psutil')
    def test_get_cpu_usage_success(self, mock_psutil):
        """psutil 正常返回"""
        from system_monitor import get_cpu_usage

        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.cpu_percent = MagicMock(side_effect=lambda interval=None, percpu=False: 50.0)
        mock_psutil.cpu_times.return_value = MOCK_CPU_TIMES
        mock_psutil.cpu_percent.return_value = 50.0

        result = get_cpu_usage()

        assert 'total' in result
        assert 'user' in result
        assert 'system' in result
        assert 'idle' in result
        assert 'cores' in result
        assert isinstance(result['total'], float)

    @patch('system_monitor.psutil')
    def test_get_cpu_usage_fallback_triggered(self, mock_psutil):
        """psutil 异常时触发 fallback"""
        from system_monitor import get_cpu_usage, _get_cpu_usage_fallback

        mock_psutil.cpu_percent.side_effect = Exception("psutil error")

        with patch('system_monitor._get_cpu_usage_fallback') as mock_fb:
            mock_fb.return_value = {'total': 0, 'user': 0, 'system': 0, 'idle': 0, 'cores': 0}
            result = get_cpu_usage()
            assert result['total'] == 0


class TestGetCpuUsageFallback:
    """测试 _get_cpu_usage_fallback()"""

    @patch('system_monitor.subprocess.check_output')
    def test_fallback_top_parsing(self, mock_check_output):
        """top 输出解析正常"""
        from system_monitor import _get_cpu_usage_fallback

        top_output = """CPU usage: 25.5% user, 10.2% sys, 64.3% idle"""
        mock_check_output.return_value = top_output

        result = _get_cpu_usage_fallback()

        assert result['total'] == pytest.approx(35.7, abs=0.1)
        assert result['user'] == 25.5
        assert result['system'] == 10.2
        assert result['idle'] == 64.3
        assert result['cores'] is None

    @patch('system_monitor.subprocess.check_output')
    def test_fallback_top_no_match(self, mock_check_output):
        """top 输出不匹配时返回零值"""
        from system_monitor import _get_cpu_usage_fallback

        mock_check_output.return_value = "some unrelated output"

        result = _get_cpu_usage_fallback()

        assert result['total'] == 0
        assert result['user'] == 0
        assert result['system'] == 0
        assert result['idle'] == 0


# ─── get_disk_io ──────────────────────────────────────────────────────────────

class TestGetDiskIO:
    """测试 get_disk_io()"""

    @patch('system_monitor.psutil')
    @patch('system_monitor.time.time')
    def test_disk_io_first_call(self, mock_time, mock_psutil):
        """首次调用返回 0（无历史数据）"""
        import system_monitor
        system_monitor._last_disk_io = None
        system_monitor._last_io_time = 0

        mock_time.return_value = 1000.0
        mock_psutil.disk_io_counters.return_value = MOCK_DISK_IO

        result = system_monitor.get_disk_io()

        assert result['read_mb_s'] == 0
        assert result['write_mb_s'] == 0

    @patch('system_monitor.psutil')
    @patch('system_monitor.time.time')
    def test_disk_io_second_call(self, mock_time, mock_psutil):
        """第二次调用计算差值"""
        import system_monitor

        old_io = MagicMock(read_bytes=0, write_bytes=0)
        system_monitor._last_disk_io = old_io
        system_monitor._last_io_time = 1000.0

        new_io = MagicMock(read_bytes=10*1024**2, write_bytes=5*1024**2)  # 10MB read, 5MB write
        mock_psutil.disk_io_counters.return_value = new_io
        mock_time.return_value = 1001.0  # 1 秒后

        result = system_monitor.get_disk_io()

        assert result['read_mb_s'] == pytest.approx(10.0, abs=0.1)
        assert result['write_mb_s'] == pytest.approx(5.0, abs=0.1)

    @patch('system_monitor.psutil')
    def test_disk_io_psutil_error(self):
        """psutil 异常时返回零"""
        import system_monitor
        system_monitor._last_disk_io = None
        system_monitor._last_io_time = 0

        with patch('system_monitor.psutil') as mock_psutil:
            mock_psutil.disk_io_counters.side_effect = Exception("error")
            result = system_monitor.get_disk_io()
            assert result['read_mb_s'] == 0
            assert result['write_mb_s'] == 0


# ─── get_network_io ───────────────────────────────────────────────────────────

class TestGetNetworkIO:
    """测试 get_network_io()"""

    @patch('system_monitor.psutil')
    @patch('system_monitor.time.time')
    def test_net_io_first_call(self, mock_time, mock_psutil):
        """首次调用返回 0"""
        import system_monitor
        system_monitor._last_net_io = None
        system_monitor._last_io_time = 0

        mock_time.return_value = 1000.0
        mock_psutil.net_io_counters.return_value = MOCK_NET_IO

        result = system_monitor.get_network_io()

        assert result['recv_mb_s'] == 0
        assert result['sent_mb_s'] == 0

    @patch('system_monitor.psutil')
    @patch('system_monitor.time.time')
    def test_net_io_second_call(self, mock_time, mock_psutil):
        """第二次调用计算差值"""
        import system_monitor

        old_io = MagicMock(bytes_recv=0, bytes_sent=0)
        system_monitor._last_net_io = old_io
        system_monitor._last_io_time = 1000.0

        new_io = MagicMock(bytes_recv=10*1024**2, bytes_sent=5*1024**2)
        mock_psutil.net_io_counters.return_value = new_io
        mock_time.return_value = 1001.0

        result = system_monitor.get_network_io()

        assert result['recv_mb_s'] == pytest.approx(10.0, abs=0.1)
        assert result['sent_mb_s'] == pytest.approx(5.0, abs=0.1)

    @patch('system_monitor.psutil')
    def test_net_io_psutil_error(self):
        """psutil 异常时返回零"""
        import system_monitor
        system_monitor._last_net_io = None
        system_monitor._last_io_time = 0

        with patch('system_monitor.psutil') as mock_psutil:
            mock_psutil.net_io_counters.side_effect = Exception("error")
            result = system_monitor.get_network_io()
            assert result['recv_mb_s'] == 0
            assert result['sent_mb_s'] == 0


# ─── get_disk_usage ───────────────────────────────────────────────────────────

class TestGetDiskUsage:
    """测试 get_disk_usage()"""

    @patch('system_monitor.psutil')
    def test_get_disk_usage_success(self, mock_psutil):
        """psutil 正常返回"""
        from system_monitor import get_disk_usage

        mock_part = MagicMock(mountpoint="/", fstype="apfs")
        mock_usage = MagicMock(total=500*1024**3, used=200*1024**3,
                                free=300*1024**3, percent=40.0)
        mock_psutil.disk_partitions.return_value = [mock_part]
        mock_psutil.disk_usage.return_value = mock_usage

        result = get_disk_usage()

        assert result['total_gb'] == 500.0
        assert result['used_gb'] == 200.0
        assert result['free_gb'] == 300.0
        assert result['percent'] == 40.0

    @patch('system_monitor.psutil')
    def test_get_disk_usage_error(self, mock_psutil):
        """psutil 异常时返回空字典"""
        from system_monitor import get_disk_usage

        mock_psutil.disk_partitions.side_effect = Exception("error")

        result = get_disk_usage()

        assert result == {}


# ─── get_memory_pressure ──────────────────────────────────────────────────────

class TestGetMemoryPressure:
    """测试 get_memory_pressure()"""

    @patch('system_monitor.subprocess.check_output')
    def test_pressure_normal(self, mock_check_output):
        """正常压力（free >= 25%）"""
        from system_monitor import get_memory_pressure

        mock_check_output.return_value = "System-wide memory free percentage: 30%"

        result = get_memory_pressure()

        assert result['level'] == 'normal'
        assert result['free_percent'] == 30
        assert result['used_percent'] == 70

    @patch('system_monitor.subprocess.check_output')
    def test_pressure_warning(self, mock_check_output):
        """警告压力（10% <= free < 25%）"""
        from system_monitor import get_memory_pressure

        mock_check_output.return_value = "System-wide memory free percentage: 15%"

        result = get_memory_pressure()

        assert result['level'] == 'warning'

    @patch('system_monitor.subprocess.check_output')
    def test_pressure_critical(self, mock_check_output):
        """严重压力（free < 10%）"""
        from system_monitor import get_memory_pressure

        mock_check_output.return_value = "System-wide memory free percentage: 5%"

        result = get_memory_pressure()

        assert result['level'] == 'critical'

    @patch('system_monitor.subprocess.check_output')
    def test_pressure_no_match(self, mock_check_output):
        """输出不匹配时返回 unknown"""
        from system_monitor import get_memory_pressure

        mock_check_output.return_value = "some unrelated output"

        result = get_memory_pressure()

        assert result['level'] == 'unknown'

    @patch('system_monitor.subprocess.check_output')
    def test_pressure_error(self, mock_check_output):
        """异常时返回 error"""
        from system_monitor import get_memory_pressure

        mock_check_output.side_effect = Exception("error")

        result = get_memory_pressure()

        assert result['level'] == 'error'


# ─── take_snapshot ─────────────────────────────────────────────────────────────

class TestTakeSnapshot:
    """测试 take_snapshot()"""

    @patch('system_monitor.get_power_info')
    @patch('system_monitor.get_network_io')
    @patch('system_monitor.get_disk_usage')
    @patch('system_monitor.get_disk_io')
    @patch('system_monitor.get_cpu_usage')
    @patch('system_monitor.get_memory_pressure')
    @patch('system_monitor.get_memory_info')
    def test_take_snapshot_returns_snapshot(self, mock_mem, mock_pressure,
                                            mock_cpu, mock_disk_io,
                                            mock_disk_usage, mock_net_io,
                                            mock_power):
        """take_snapshot 返回完整的 SystemSnapshot"""
        from system_monitor import take_snapshot, SystemSnapshot

        mock_mem.return_value = {
            'total_gb': 32.0, 'used_gb': 16.0, 'available_gb': 16.0,
            'percent': 50.0, 'swap_used_gb': 0.5, 'swap_total_gb': 2.0
        }
        mock_pressure.return_value = {'level': 'normal', 'free_percent': 50, 'used_percent': 50}
        mock_cpu.return_value = {
            'total': 50.0, 'user': 30.0, 'system': 20.0, 'idle': 50.0, 'cores': 8
        }
        mock_disk_io.return_value = {'read_mb_s': 10.0, 'write_mb_s': 5.0}
        mock_disk_usage.return_value = {
            'total_gb': 500.0, 'used_gb': 200.0, 'free_gb': 300.0, 'percent': 40.0
        }
        mock_net_io.return_value = {'recv_mb_s': 1.0, 'sent_mb_s': 0.5}
        mock_power.return_value = {'all_power_w': 10.0, 'cpu_power_w': 5.0,
                                   'gpu_power_w': 3.0, 'source': 'test'}

        snap = take_snapshot()

        assert isinstance(snap, SystemSnapshot)
        assert snap.memory_percent == 50.0
        assert snap.memory_used_gb == 16.0
        assert snap.cpu_percent == 50.0
        assert snap.disk_read_mb_s == 10.0
        assert snap.net_recv_mb_s == 1.0
        assert snap.power_info['all_power_w'] == 10.0


# ─── format_snapshot / format_compact ─────────────────────────────────────────

class TestFormatSnapshot:
    """测试 format_snapshot() 和 format_compact()"""

    @patch('system_monitor.time.strftime')
    def test_format_snapshot(self, mock_strftime):
        """format_snapshot 生成多行字符串"""
        from system_monitor import format_snapshot, SystemSnapshot

        mock_strftime.return_value = "12:00:00"

        snap = SystemSnapshot(
            timestamp=time.time(),
            memory_percent=50.0, memory_used_gb=16.0, memory_total_gb=32.0,
            memory_pressure_level='normal', memory_free_percent=50,
            swap_used_gb=0.5, swap_total_gb=2.0,
            cpu_percent=50.0, cpu_user=30.0, cpu_system=20.0,
            cpu_idle=50.0, cpu_cores=8,
            power_info={'all_power_w': 10.5, 'cpu_power_w': 5.0,
                       'gpu_power_w': 3.0, 'ane_power_w': 0.5,
                       'ram_power_w': 0.0, 'sys_power_w': 2.0,
                       'cpu_temp_c': 60.0, 'gpu_temp_c': 55.0,
                       'cpu_usage_pct': 50.0, 'gpu_usage_pct': 30.0},
            disk_read_mb_s=10.0, disk_write_mb_s=5.0,
            disk_total_gb=500.0, disk_used_gb=200.0,
            disk_free_gb=300.0, disk_percent=40.0,
            net_recv_mb_s=1.5, net_sent_mb_s=0.8,
        )

        output = format_snapshot(snap)

        assert isinstance(output, str)
        assert "12:00:00" in output
        assert "50.0%" in output  # memory percent

    @patch('system_monitor.time.strftime')
    def test_format_compact(self, mock_strftime):
        """format_compact 生成单行紧凑字符串"""
        from system_monitor import format_compact, SystemSnapshot

        mock_strftime.return_value = "12:00:00"

        snap = SystemSnapshot(
            timestamp=time.time(),
            memory_percent=50.0, memory_used_gb=16.0, memory_total_gb=32.0,
            memory_pressure_level='normal', memory_free_percent=50,
            swap_used_gb=0.5, swap_total_gb=2.0,
            cpu_percent=50.0, cpu_user=30.0, cpu_system=20.0,
            cpu_idle=50.0, cpu_cores=8,
            power_info={'all_power_w': 10.5, 'cpu_power_w': 5.0,
                       'gpu_power_w': 3.0, 'ane_power_w': 0.5,
                       'ram_power_w': 0.0, 'sys_power_w': 2.0,
                       'cpu_temp_c': 60.0, 'gpu_temp_c': 55.0,
                       'cpu_usage_pct': 50.0, 'gpu_usage_pct': 30.0},
            disk_read_mb_s=10.0, disk_write_mb_s=5.0,
            disk_total_gb=500.0, disk_used_gb=200.0,
            disk_free_gb=300.0, disk_percent=40.0,
            net_recv_mb_s=1.5, net_sent_mb_s=0.8,
        )

        output = format_compact(snap)

        assert isinstance(output, str)
        assert "12:00:00" in output
        assert "50%" in output  # memory percent

    @patch('system_monitor.time.strftime')
    def test_format_compact_no_power(self, mock_strftime):
        """format_compact 无功率数据"""
        from system_monitor import format_compact, SystemSnapshot

        mock_strftime.return_value = "12:00:00"

        snap = SystemSnapshot(
            timestamp=time.time(),
            memory_percent=50.0, memory_used_gb=16.0, memory_total_gb=32.0,
            memory_pressure_level='normal', memory_free_percent=50,
            swap_used_gb=0.5, swap_total_gb=2.0,
            cpu_percent=50.0, cpu_user=30.0, cpu_system=20.0,
            cpu_idle=50.0, cpu_cores=8,
            power_info={'all_power_w': None, 'source': None},
            disk_read_mb_s=0.0, disk_write_mb_s=0.0,
            disk_total_gb=500.0, disk_used_gb=200.0,
            disk_free_gb=300.0, disk_percent=40.0,
            net_recv_mb_s=0.0, net_sent_mb_s=0.0,
        )

        output = format_compact(snap)

        assert isinstance(output, str)
        assert "⚡-" in output  # 无功率


# ─── macmon 进程管理 ──────────────────────────────────────────────────────────

class TestMacmonProcess:
    """测试 macmon 进程启动/停止"""

    @patch('system_monitor.subprocess.Popen')
    @patch('select.select')
    def test_macmon_start_success(self, mock_select, mock_popen):
        """macmon 启动成功"""
        import system_monitor
        system_monitor._macmon_proc = None  # 重置

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline.return_value = '{"all_power": 10.0}\n'
        mock_popen.return_value = mock_proc
        mock_select.return_value = ([mock_proc.stdout], [], [])

        result = system_monitor._macmon_start()

        assert result is True
        mock_popen.assert_called_once()

    @patch('system_monitor.subprocess.Popen')
    def test_macmon_start_failure(self, mock_popen):
        """macmon 启动失败"""
        import system_monitor
        system_monitor._macmon_proc = None
        mock_popen.side_effect = FileNotFoundError

        result = system_monitor._macmon_start()

        assert result is False
        assert system_monitor._macmon_proc is None

    @patch('system_monitor.subprocess.Popen')
    @patch('select.select')
    def test_macmon_stop(self, mock_select, mock_popen):
        """macmon 停止"""
        import system_monitor

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc
        mock_select.return_value = ([mock_proc.stdout], [], [])

        system_monitor._macmon_start()
        system_monitor._macmon_stop()

        assert system_monitor._macmon_proc is None

    @patch('system_monitor.subprocess.Popen')
    @patch('select.select')
    def test_macmon_read_success(self, mock_select, mock_popen):
        """macmon 读取成功"""
        import system_monitor
        system_monitor._macmon_proc = None
        system_monitor._macmon_buf = ""

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline.return_value = '{"all_power": 10.0, "cpu_power": 5.0, "gpu_power": 3.0, "ane_power": 0.5, "ram_power": 0.2, "sys_power": 1.3, "temp": {"cpu_temp_avg": 60.0, "gpu_temp_avg": 55.0}, "cpu_usage_pct": 0.5, "gpu_usage": [0, 0.3]}'
        mock_popen.return_value = mock_proc
        mock_select.return_value = ([mock_proc.stdout], [], [])

        system_monitor._macmon_start()
        result = system_monitor._macmon_read()

        assert result is not None
        assert result['all_power_w'] == 10.0
        assert result['source'] == 'macmon'

    @patch('system_monitor.subprocess.Popen')
    @patch('select.select')
    def test_macmon_read_empty_line(self, mock_select, mock_popen):
        """macmon 读取到空行（进程退出）"""
        import system_monitor
        system_monitor._macmon_proc = None
        system_monitor._macmon_buf = ""

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline.return_value = ""  # 空行表示退出
        mock_popen.return_value = mock_proc
        mock_select.return_value = ([mock_proc.stdout], [], [])

        system_monitor._macmon_start()
        result = system_monitor._macmon_read()

        assert result is None
        assert system_monitor._macmon_proc is None


class TestPowerMetrics:
    """测试 powermetrics fallback"""

    @patch('system_monitor.subprocess.Popen')
    def test_parse_powermetrics_success(self, mock_popen):
        """powermetrics 解析成功"""
        from system_monitor import _parse_powermetrics

        output = """CPU Power: 5000 mW
GPU Power: 3000 mW
ANE Power: 1000 mW"""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (output, "")
        mock_popen.return_value = mock_proc

        result = _parse_powermetrics()

        assert result is not None
        assert result['all_power_w'] == 9.0  # 9W total
        assert result['cpu_power_w'] == 5.0
        assert result['gpu_power_w'] == 3.0
        assert result['source'] == 'powermetrics'

    @patch('system_monitor.subprocess.Popen')
    def test_parse_powermetrics_no_match(self, mock_popen):
        """powermetrics 输出不匹配"""
        from system_monitor import _parse_powermetrics

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("no match here", "")
        mock_popen.return_value = mock_proc

        result = _parse_powermetrics()

        assert result is None

    @patch('system_monitor.subprocess.Popen')
    def test_parse_powermetrics_timeout(self, mock_popen):
        """powermetrics 超时"""
        from system_monitor import _parse_powermetrics

        mock_popen.side_effect = subprocess.TimeoutExpired("powermetrics", 10)

        result = _parse_powermetrics()

        assert result is None
