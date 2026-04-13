package collector

import (
	"os/exec"
	"regexp"
	"strconv"
	"strings"
)

// CollectMemory gathers memory statistics using sysctl hw.memsize and vm_stat
func CollectMemory() (*MemoryInfo, error) {
	info := &MemoryInfo{}

	// Get total physical memory via sysctl
	out, err := exec.Command("sysctl", "-n", "hw.memsize").Output()
	if err == nil {
		if val, parseErr := strconv.ParseUint(strings.TrimSpace(string(out)), 10, 64); parseErr == nil {
			info.Total = val
		}
	}

	// Get memory stats from vm_stat
	vmOut, vmErr := exec.Command("vm_stat").Output()
	if vmErr == nil {
		pagesize := uint64(4096)
		if psOut, psErr := exec.Command("sysctl", "-n", "hw.pagesize").Output(); psErr == nil {
			if psVal, psParseErr := strconv.ParseUint(strings.TrimSpace(string(psOut)), 10, 64); psParseErr == nil {
				pagesize = psVal
			}
		}

		lines := strings.Split(string(vmOut), "\n")
		stats := make(map[string]uint64)
		for _, line := range lines {
			line = strings.TrimSpace(line)
			m := regexp.MustCompile(`^\s*(.+?):\s+(\d+)\.`).FindStringSubmatch(line)
			if m != nil {
				key := strings.TrimSpace(m[1])
				val, _ := strconv.ParseUint(m[2], 10, 64)
				stats[key] = val
			}
		}

		free := stats["Pages free"]
		active := stats["Pages active"]
		inactive := stats["Pages inactive"]
		wired := stats["Pages wired down"]
		compressed := stats["Pages used by compressor"]
		if _, ok := stats["Pages used by compressor"]; !ok {
			if v, ok := stats["Pages occupied by compressor"]; ok {
				compressed = v
			}
		}

		info.Free = free * pagesize
		info.Available = (free + inactive) * pagesize
		info.Used = (active + wired + compressed) * pagesize

		if info.Total > 0 {
			info.UsedPercent = float64(info.Used) / float64(info.Total) * 100
		}
	}

	if info.Total == 0 {
		info.Total = info.Free + info.Used
	}

	return info, nil
}

// CollectMemoryPressure gathers memory pressure level
func CollectMemoryPressure() (level string, freePct int, usedPct int) {
	out, err := exec.Command("memory_pressure").Output()
	if err != nil {
		return "unknown", -1, -1
	}

	m := regexp.MustCompile(`System-wide memory free percentage:\s*(\d+)%`).FindStringSubmatch(string(out))
	if m == nil {
		return "unknown", -1, -1
	}

	if v, err := strconv.Atoi(m[1]); err == nil {
		freePct = v
	}

	usedPct = 100 - freePct
	if freePct >= 25 {
		level = "normal"
	} else if freePct >= 10 {
		level = "warning"
	} else {
		level = "critical"
	}

	return
}

// collectSwap retrieves swap memory statistics
func collectSwap() (used uint64, total uint64) {
	out, err := exec.Command("sysctl", "-n", "vm.swapusage").Output()
	if err != nil {
		return 0, 0
	}

	m := regexp.MustCompile(`total\s*=\s*([\d.]+)([KMGT]?)\s+used\s*=\s*([\d.]+)([KMGT]?)\s+free\s*=\s*([\d.]+)([KMGT]?)`).FindStringSubmatch(string(out))
	if m == nil {
		return 0, 0
	}

	total = parseSizeMB(m[1], m[2])
	used = parseSizeMB(m[3], m[4])
	return used, total
}

func parseSizeMB(val, unit string) uint64 {
	f, err := strconv.ParseFloat(val, 64)
	if err != nil {
		return 0
	}
	switch unit {
	case "K", "KB":
		f *= 1024
	case "M", "MB":
		f *= 1024 * 1024
	case "G", "GB":
		f *= 1024 * 1024 * 1024
	case "T", "TB":
		f *= 1024 * 1024 * 1024 * 1024
	}
	return uint64(f)
}

func round2(v float64, precision int) float64 {
	ratio := 1.0
	for i := 0; i < precision; i++ {
		ratio *= 10
	}
	return float64(int(v*ratio+0.5)) / ratio
}
