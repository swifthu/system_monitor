package collector

import (
	"bufio"
	"encoding/json"
	"errors"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// macmonState represents the state machine for macmon pipe
type macmonState int

const (
	macmonMonitoring macmonState = iota
	macmonFallback
	macmonRetryMacmon
)

func (s macmonState) String() string {
	switch s {
	case macmonMonitoring:
		return "MONITORING"
	case macmonFallback:
		return "FALLBACK"
	case macmonRetryMacmon:
		return "RETRY_MACMON"
	default:
		return "UNKNOWN"
	}
}

var (
	macmonCurState   macmonState = macmonMonitoring
	macmonFailCount  int         = 0
	macmonRetryCount int         = 0
	macmonStaleData   *PowerInfo  // last valid data returned during fallback
	externalMacmon    *bufio.Reader // macmon reader set by collector
)

const (
	macmonMaxConsecutiveFailures = 3
	macmonRetryInterval           = 10 // retry every 10 collections
	macmonTimeout                 = 5 * time.Second
)

// CollectPower gathers power/energy statistics
// Prioritizes macmon pipe from collector, falls back to powermetrics
func CollectPower() (*PowerInfo, error) {
	state := macmonCurState

	// Try macmon unless in fallback or external macmon is available
	if state != macmonFallback {
		if externalMacmon != nil {
			result, err := readFromExternalMacmon()
			if err == nil && result != nil {
				macmonFailCount = 0
				if state == macmonRetryMacmon {
					macmonCurState = macmonMonitoring
				}
				return result, nil
			}
		} else {
			result, err := collectFromMacmon()
			if err == nil && result != nil {
				macmonFailCount = 0
				if state == macmonRetryMacmon {
					macmonCurState = macmonMonitoring
				}
				return result, nil
			}
		}

		// Transient failure
		macmonFailCount++
		if macmonFailCount >= macmonMaxConsecutiveFailures {
			macmonCurState = macmonFallback
			macmonRetryCount = 0
		}
		prevState := macmonCurState

		// If we have stale data, return it
		if prevState == macmonFallback && macmonStaleData != nil {
			return macmonStaleData, nil
		}

		// Try powermetrics as immediate fallback
		result, _ := collectFromPowermetrics()
		if result != nil {
			macmonStaleData = result
			return result, nil
		}

		return &PowerInfo{}, nil
	}

	// In fallback mode, try powermetrics
	result, err := collectFromPowermetrics()
	if err == nil && result != nil {
		macmonStaleData = result
		macmonRetryCount++
		if macmonRetryCount >= macmonRetryInterval {
			macmonCurState = macmonRetryMacmon
			macmonRetryCount = 0
			// Don't restart macmon here - collector manages it
		}
		return result, nil
	}

	// Still return stale data if available
	if macmonStaleData != nil {
		return macmonStaleData, nil
	}
	return &PowerInfo{}, nil
}

// readFromExternalMacmon reads from macmon stdout provided by collector
func readFromExternalMacmon() (*PowerInfo, error) {
	if externalMacmon == nil {
		return nil, errors.New("external macmon not available")
	}

	// Set a timeout
	type result struct {
		info *PowerInfo
		err  error
	}
	ch := make(chan result, 1)

	go func() {
		info, err := readMacmonLine(externalMacmon)
		ch <- result{info, err}
	}()

	select {
	case r := <-ch:
		return r.info, r.err
	case <-time.After(macmonTimeout):
		return nil, errors.New("macmon read timeout")
	}
}

// SetExternalMacmon sets the macmon stdout reader from collector
func SetExternalMacmon(reader *bufio.Reader) {
	externalMacmon = reader
}

// collectFromMacmon is a fallback when collector hasn't started macmon
// (collector should be preferred - this is only for direct CollectPower calls without collector)
func collectFromMacmon() (*PowerInfo, error) {
	// If external macmon is set, don't try to start our own
	if externalMacmon != nil {
		return readFromExternalMacmon()
	}
	return nil, errors.New("macmon not managed by collector, use powermetrics fallback")
}

// restartMacmon is a no-op since collector manages macmon lifecycle
func restartMacmon() {
	// macmon is managed by collector, nothing to restart here
}

// readMacmonLine reads and parses one line from macmon
func readMacmonLine(stdout *bufio.Reader) (*PowerInfo, error) {
	if stdout == nil {
		return nil, errors.New("macmon stdout not available")
	}

	line, err := stdout.ReadString('\n')
	if err != nil {
		return nil, err
	}

	line = strings.TrimSpace(line)
	if line == "" {
		return nil, errors.New("empty line")
	}

	var data map[string]interface{}
	if err := json.Unmarshal([]byte(line), &data); err != nil {
		return nil, err
	}

	info := &PowerInfo{}

	// all_power is the total system power in Watts
	if v, ok := data["all_power"].(float64); ok {
		info.Percent = v
	}

	// Individual power components
	if v, ok := data["cpu_power"].(float64); ok {
		info.CPUPower = v
	}
	if v, ok := data["gpu_power"].(float64); ok {
		info.GPUPower = v
	}
	if v, ok := data["ram_power"].(float64); ok {
		info.RAMPower = v
	}
	if v, ok := data["sys_power"].(float64); ok {
		info.SYSPower = v
	}
	if v, ok := data["ane_power"].(float64); ok {
		info.ANEPower = v
	}

	// Temperature
	if temp, ok := data["temp"].(map[string]interface{}); ok {
		if cpuTemp, ok := temp["cpu_temp_avg"].(float64); ok {
			info.CPUTemp = cpuTemp
		}
		if gpuTemp, ok := temp["gpu_temp_avg"].(float64); ok {
			info.GPUTemp = gpuTemp
		}
	}

	return info, nil
}

// collectFromPowermetrics reads power data using sudo powermetrics
func collectFromPowermetrics() (*PowerInfo, error) {
	cmd := exec.Command("sudo", "powermetrics", "--samplers", "cpu_power", "-i", "500", "-n", "1")
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	output := string(out)
	info := &PowerInfo{}

	// CPU Power: XXX mW
	if m := regexp.MustCompile(`CPU Power:\s*([\d.]+)\s*mW`).FindStringSubmatch(output); m != nil {
		if v, err := strconv.ParseFloat(m[1], 64); err == nil {
			info.Percent = v / 1000 // convert mW to W
		}
	}

	return info, nil
}
