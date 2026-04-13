package collector

// MemoryInfo holds memory statistics
type MemoryInfo struct {
	Total       uint64  `json:"total"`
	Used        uint64  `json:"used"`
	Free        uint64  `json:"free"`
	Available   uint64  `json:"available"`
	UsedPercent float64 `json:"used_percent"`
}

// CPUInfo holds CPU statistics
type CPUInfo struct {
	CPU       int     `json:"cpu"`
	User      float64 `json:"user"`
	System    float64 `json:"system"`
	Idle      float64 `json:"idle"`
	Nice      float64 `json:"nice"`
	Iowait    float64 `json:"iowait"`
	Irq       float64 `json:"irq"`
	Softirq   float64 `json:"softirq"`
	Steal     float64 `json:"steal"`
	TotalPercent float64 `json:"total_percent"`
}

// PowerInfo holds power/energy statistics
type PowerInfo struct {
	Percent       float64 `json:"percent"` // total power in Watts (all_power)
	Charge        bool    `json:"charge"`
	TimeRemaining int     `json:"time_remaining"` // minutes, -1 if unknown
	CPUPower      float64 `json:"cpu_power_w"`    // CPU power in Watts
	GPUPower      float64 `json:"gpu_power_w"`    // GPU power in Watts
	RAMPower      float64 `json:"ram_power_w"`    // RAM power in Watts
	SYSPower      float64 `json:"sys_power_w"`    // System power in Watts
	ANEPower      float64 `json:"ane_power_w"`    // ANE power in Watts
	CPUTemp       float64 `json:"cpu_temp"`       // CPU temperature in Celsius
	GPUTemp       float64 `json:"gpu_temp"`       // GPU temperature in Celsius
}

// DiskInfo holds disk statistics
type DiskInfo struct {
	Path        string  `json:"path"`
	Total       uint64  `json:"total"`
	Used        uint64  `json:"used"`
	Free        uint64  `json:"free"`
	UsedPercent float64 `json:"used_percent"`
	InodesTotal uint64  `json:"inodes_total"`
	InodesUsed  uint64  `json:"inodes_used"`
	InodesFree  uint64  `json:"inodes_free"`
}

// NetworkInfo holds network statistics
type NetworkInfo struct {
	Interface string  `json:"interface"`
	RxBytes   uint64  `json:"rx_bytes"`
	TxBytes   uint64  `json:"tx_bytes"`
	RxPackets uint64  `json:"rx_packets"`
	TxPackets uint64  `json:"tx_packets"`
	RxErrors  uint64  `json:"rx_errors"`
	TxErrors  uint64  `json:"tx_errors"`
	RxDropped uint64  `json:"rx_dropped"`
	TxDropped uint64  `json:"tx_dropped"`
	RxRate    float64 `json:"rx_rate"` // MB/s
	TxRate    float64 `json:"tx_rate"` // MB/s
}

// SystemSnapshot represents a complete system status snapshot
type SystemSnapshot struct {
	Timestamp int64        `json:"timestamp"`
	Memory    MemoryInfo    `json:"memory"`
	CPU       []CPUInfo    `json:"cpu"`
	Power     PowerInfo     `json:"power"`
	Disk      []DiskInfo    `json:"disk"`
	Network   []NetworkInfo `json:"network"`
}
