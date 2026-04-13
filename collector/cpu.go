package collector

import (
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"syscall"
)

// CollectCPU gathers CPU statistics using hostinfo or top
func CollectCPU() ([]CPUInfo, error) {
	// Try hostinfo first (more accurate on macOS)
	info, err := collectCPUHostInfo()
	if err == nil && info != nil {
		return []CPUInfo{*info}, nil
	}

	// Fallback to top
	return collectCPUTop()
}

// collectCPUHostInfo uses hostinfo to get CPU usage
func collectCPUHostInfo() (*CPUInfo, error) {
	out, err := exec.Command("hostinfo").Output()
	if err != nil {
		return nil, err
	}

	// Parse "CPU usage: X% user, Y% system, Z% idle"
	m := regexp.MustCompile(`CPU usage:\s*([\d.]+)%\s*user,\s*([\d.]+)%\s*system`).FindStringSubmatch(string(out))
	if m == nil {
		return nil, err
	}

	user, _ := strconv.ParseFloat(m[1], 64)
	system, _ := strconv.ParseFloat(m[2], 64)
	idle := 100.0 - user - system

	// Get number of CPUs
	if n, err := exec.Command("sysctl", "-n", "hw.ncpu").Output(); err == nil {
		if v, err := strconv.Atoi(strings.TrimSpace(string(n))); err == nil {
			_ = v // number of CPUs available
		}
	}

	return &CPUInfo{
		CPU:          0,
		User:         user,
		System:       system,
		Idle:         idle,
		TotalPercent: user + system,
	}, nil
}

// collectCPUTop uses top to get CPU usage
func collectCPUTop() ([]CPUInfo, error) {
	out, err := exec.Command("top", "-l", "1", "-n", "1").Output()
	if err != nil {
		return nil, err
	}

	// Parse "CPU usage: X% user, Y% sys, Z% idle"
	m := regexp.MustCompile(`CPU usage:\s*([\d.]+)%\s*user,\s*([\d.]+)%\s*sys,\s*([\d.]+)%\s*idle`).FindStringSubmatch(string(out))
	if m == nil {
		return nil, err
	}

	user, _ := strconv.ParseFloat(m[1], 64)
	system, _ := strconv.ParseFloat(m[2], 64)
	idle, _ := strconv.ParseFloat(m[3], 64)

	if n, err := exec.Command("sysctl", "-n", "hw.ncpu").Output(); err == nil {
		if _, err := strconv.Atoi(strings.TrimSpace(string(n))); err == nil {
			// number of CPUs available
		}
	}

	info := CPUInfo{
		CPU:          0,
		User:         user,
		System:       system,
		Idle:         idle,
		TotalPercent: user + system,
	}

	// Try to get per-core usage
	perCore, _ := collectPerCoreCPU()
	if len(perCore) > 0 {
		result := make([]CPUInfo, len(perCore)+1)
		result[0] = info
		for i, pc := range perCore {
			pc.CPU = i + 1
			result[i+1] = pc
		}
		return result, nil
	}

	return []CPUInfo{info}, nil
}

// collectPerCoreCPU tries to get per-core CPU percentages
func collectPerCoreCPU() ([]CPUInfo, error) {
	// Use mach_host_self to get per-processor info
	out, err := exec.Command("top", "-l", "1", "-n", "1", "-S").Output()
	if err != nil {
		return nil, err
	}

	var result []CPUInfo
	lines := strings.Split(string(out), "\n")
	for _, line := range lines {
		// Look for per-CPU lines
		m := regexp.MustCompile(`CPU(\d+):\s*([\d.]+)%\s*user`).FindStringSubmatch(line)
		if m != nil {
			core, _ := strconv.Atoi(m[1])
			pct, _ := strconv.ParseFloat(m[2], 64)
			result = append(result, CPUInfo{
				CPU:          core,
				User:         pct,
				TotalPercent: pct,
			})
		}
	}

	return result, nil
}

// CollectCPUUsage returns a simple total CPU usage percentage
func CollectCPUUsage() (user, system, idle float64, cores int, err error) {
	info, err := CollectCPU()
	if err != nil || len(info) == 0 {
		return 0, 0, 100, 0, err
	}

	main := info[0]
	return main.User, main.System, main.Idle, len(info), nil
}

// golang.org/x/sys/unix for mach_host_self
var (
	hostCPULoadInfo int
)

// sysctl wrapper for mach cpu load
func getCPULoad() (user, system, idle uint64, err error) {
	// Use sysctl to get cpu ticks
	_, err = exec.Command("sysctl", "-n", "kern.cputhread").Output()
	if err != nil {
		return 0, 0, 0, err
	}

	return 0, 0, 0, nil
}

// mustSyscall is here to use syscall.Syscall without import cycle
var _ = syscall.Syscall
