package api

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/jimmyhu/Documents/CC/Projects/system_monitor/collector"
)

// Handler holds HTTP handler dependencies
type Handler struct {
	collector *collector.Collector
	mux       *http.ServeMux
}

// OMLXResponse represents the OMLX API response format
type OMLXResponse struct {
	Version string      `json:"version"`
	Type    string      `json:"type"`
	Data    interface{} `json:"data"`
}

// QuotaInfo represents resource quota information
type QuotaInfo struct {
	CPU    int `json:"cpu"`
	Memory int `json:"memory"` // MB
	Disk   int `json:"disk"`   // GB
}

// NewHandler creates a new HTTP handler
func NewHandler(col *collector.Collector) http.Handler {
	h := &Handler{
		collector: col,
		mux:       http.NewServeMux(),
	}

	h.mux.HandleFunc("/api/snapshot", h.handleSystemSnapshot)
	h.mux.HandleFunc("/api/system", h.handleSystemSnapshot)
	h.mux.HandleFunc("/api/oml", h.handleOML)
	h.mux.HandleFunc("/api/oml/models", h.handleOMLModels)
	h.mux.HandleFunc("/api/quota", h.handleQuota)
	h.mux.HandleFunc("/api/banwagon", h.handleBanwagon)
	h.mux.HandleFunc("/metrics", h.handleNotFound)
	h.mux.HandleFunc("/health", h.handleNotFound)
	h.mux.HandleFunc("/", h.handleIndex)

	return h
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	h.mux.ServeHTTP(w, r)
}

func (h *Handler) handleNotFound(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusNotFound)
	json.NewEncoder(w).Encode(map[string]string{"error": "not found"})
}

func (h *Handler) handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		h.handleNotFound(w, r)
		return
	}
	http.ServeFile(w, r, "frontend/index.html")
}

func (h *Handler) handleSystemSnapshot(w http.ResponseWriter, r *http.Request) {
	snapshot, ok := h.collector.Cache().Get()
	if !ok {
		http.Error(w, `{"error": "no data yet"}`, http.StatusServiceUnavailable)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-cache")
	json.NewEncoder(w).Encode(snapshot)
}

func (h *Handler) handleOML(w http.ResponseWriter, r *http.Request) {
	proxyTolocalhost8000(w, r, "/api/status")
}

func (h *Handler) handleOMLModels(w http.ResponseWriter, r *http.Request) {
	proxyTolocalhost8000(w, r, "/v1/models/status")
}

func proxyTolocalhost8000(w http.ResponseWriter, r *http.Request, path string) {
	target := &url.URL{
		Scheme: "http",
		Host:   "localhost:8000",
		Path:   path,
	}

	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.Director = func(req *http.Request) {
		req.URL = target
		req.Host = "localhost:8000"
		req.Header.Set("Authorization", "Bearer oMLX")
	}
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		log.Printf("Proxy to localhost:8000 failed: %v", err)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(map[string]string{"error": "oMLX unavailable"})
	}

	proxy.ServeHTTP(w, r)
}

func (h *Handler) handleQuota(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	cfg, err := loadConfig()
	if err != nil {
		h.serveQuotaError(w, "failed to load config")
		return
	}

	url := fmt.Sprintf("https://www.minimaxi.com/v1/api/openplatform/coding_plan/remains?GroupId=%s", cfg.MiniMaxGroupID)
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		h.serveQuotaError(w, "failed to create request")
		return
	}
	req.Header.Set("Authorization", "Bearer "+cfg.MiniMaxAPIKey)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		h.serveQuotaError(w, "MiniMax API unavailable")
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		h.serveQuotaError(w, "failed to read response")
		return
	}

	// Parse and transform response to match frontend expectations
	var data struct {
		ModelRemains []struct {
			ModelName                 string `json:"model_name"`
			CurrentIntervalTotalCount int    `json:"current_interval_total_count"`
			CurrentIntervalUsageCount int    `json:"current_interval_usage_count"`
			CurrentWeeklyTotalCount   int    `json:"current_weekly_total_count"`
			CurrentWeeklyUsageCount   int    `json:"current_weekly_usage_count"`
			StartTime                 int64  `json:"start_time"`
			EndTime                   int64  `json:"end_time"`
			WeeklyRemainsTime         int64  `json:"weekly_remains_time"`
		} `json:"model_remains"`
	}

	if err := json.Unmarshal(body, &data); err != nil {
		// If parsing fails, try to return raw error info
		h.serveQuotaError(w, fmt.Sprintf("parse error: %s, body: %s", err, string(body)[:200]))
		return
	}

	// Transform to frontend format
	now := time.Now()
	var mainModel, dailyModel interface{}

	for i, m := range data.ModelRemains {
		if i == 0 {
			mainModel = m
		}
		if mainModel == nil && strings.Contains(m.ModelName, "MiniMax-M") {
			mainModel = m
		}
		// Check if 1D interval (>= 23h)
		intervalMs := m.EndTime - m.StartTime
		if intervalMs >= 82800000 && dailyModel == nil {
			dailyModel = m
		}
	}

	if mainModel == nil && len(data.ModelRemains) > 0 {
		mainModel = data.ModelRemains[0]
	}
	if dailyModel == nil {
		dailyModel = mainModel
	}

	mm := mainModel.(struct {
		ModelName                 string `json:"model_name"`
		CurrentIntervalTotalCount int    `json:"current_interval_total_count"`
		CurrentIntervalUsageCount int    `json:"current_interval_usage_count"`
		CurrentWeeklyTotalCount   int    `json:"current_weekly_total_count"`
		CurrentWeeklyUsageCount   int    `json:"current_weekly_usage_count"`
		StartTime                 int64  `json:"start_time"`
		EndTime                   int64  `json:"end_time"`
		WeeklyRemainsTime         int64  `json:"weekly_remains_time"`
	})

	// Calculate quotas
	total5h := mm.CurrentIntervalTotalCount
	if total5h <= 0 {
		total5h = 0
	}

	totalWeek := mm.CurrentWeeklyTotalCount
	if totalWeek <= 0 {
		totalWeek = 0
	}

	// Calculate reset times
	calcReset := func(endTs int64) string {
		if endTs <= 0 {
			return "--"
		}
		endDt := time.UnixMilli(endTs)
		diff := endDt.Sub(now).Seconds()
		if diff <= 0 {
			return "now"
		}
		if diff >= 3600 {
			return fmt.Sprintf("%.1fh", diff/3600)
		}
		if diff >= 60 {
			return fmt.Sprintf("%.0fm", diff/60)
		}
		return fmt.Sprintf("%.0fs", diff)
	}

	// Time remaining
	remainsMs := mm.WeeklyRemainsTime
	var timeRemain string
	if remainsMs >= 86400000 {
		timeRemain = fmt.Sprintf("%.1fd", float64(remainsMs)/86400000)
	} else if remainsMs >= 3600000 {
		timeRemain = fmt.Sprintf("%.1fh", float64(remainsMs)/3600000)
	} else if remainsMs >= 60000 {
		timeRemain = fmt.Sprintf("%.0fm", float64(remainsMs)/60000)
	} else if remainsMs > 0 {
		timeRemain = fmt.Sprintf("%.0fs", float64(remainsMs)/1000)
	} else {
		timeRemain = "--"
	}

	// Build models list
	modelsList := make([]map[string]interface{}, 0, len(data.ModelRemains))
	for _, m := range data.ModelRemains {
		intervalMs := m.EndTime - m.StartTime
		intervalLabel := "5H"
		if intervalMs >= 82800000 {
			intervalLabel = "1D"
		}

		mRemain5h := m.CurrentIntervalTotalCount - m.CurrentIntervalUsageCount
		mRemainWeek := m.CurrentWeeklyTotalCount - m.CurrentWeeklyUsageCount
		if m.CurrentIntervalTotalCount <= 0 {
			mRemain5h = 0
		}
		if m.CurrentWeeklyTotalCount <= 0 {
			mRemainWeek = 0
		}

		modelsList = append(modelsList, map[string]interface{}{
			"name":          m.ModelName,
			"remain_5h":     mRemain5h,
			"total_5h":      m.CurrentIntervalTotalCount,
			"remain_week":   mRemainWeek,
			"total_week":    m.CurrentWeeklyTotalCount,
			"interval_label": intervalLabel,
			"reset_label":   calcReset(m.EndTime),
		})
	}

	result := map[string]interface{}{
		"reset_5h":   calcReset(mm.EndTime),
		"reset_1d":   calcReset(mm.EndTime),
		"time_remain": timeRemain,
		"models":      modelsList,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func (h *Handler) serveQuotaError(w http.ResponseWriter, msg string) {
	log.Printf("Quota API error: %s", msg)
	// Try to serve cached value if available
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusServiceUnavailable)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

func toFloat64(v interface{}) float64 {
	if v == nil {
		return 0
	}
	switch val := v.(type) {
	case float64:
		return val
	case float32:
		return float64(val)
	case int:
		return float64(val)
	case int64:
		return float64(val)
	default:
		return 0
	}
}

func (h *Handler) handleBanwagon(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	veid := "1120995"
	apiKey := "private_NPyZDHMumVbWt1W0B63Xb58e"
	apiURL := fmt.Sprintf("https://api.64clouds.com/v1/getServiceInfo?veid=%s&api_key=%s", veid, apiKey)

	req, err := http.NewRequestWithContext(ctx, "GET", apiURL, nil)
	if err != nil {
		h.serveBanwagonError(w, "failed to create request")
		return
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		h.serveBanwagonError(w, "--")
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		h.serveBanwagonError(w, "--")
		return
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		h.serveBanwagonError(w, "--")
		return
	}

	// Parse response and extract relevant fields
	var data map[string]interface{}
	if err := json.Unmarshal(body, &data); err != nil {
		h.serveBanwagonError(w, "--")
		return
	}

	// Return simplified response - transform to frontend format
	totalBytes := toFloat64(data["plan_monthly_data"])
	usedBytes := toFloat64(data["data_counter"])
	ramBytes := toFloat64(data["plan_ram"])
	diskBytes := toFloat64(data["plan_disk"])

	// Extract IP address
	ips := data["ip_addresses"].([]interface{})
	ipAddr := ""
	if len(ips) > 0 {
		ipAddr = ips[0].(string)
	}

	result := map[string]interface{}{
		"status":           data["status"],
		"total_gb":         totalBytes / 1024 / 1024 / 1024,
		"used_gb":          usedBytes / 1024 / 1024 / 1024,
		"ram_gb":           ramBytes / 1024 / 1024 / 1024,
		"disk_gb":          diskBytes / 1024 / 1024 / 1024,
		"ip":               ipAddr,
		"os":               data["os"],
		"location":         data["node_location"],
		"data_next_reset":  data["data_next_reset"],
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func (h *Handler) serveBanwagonError(w http.ResponseWriter, msg string) {
	log.Printf("BANWAGON API error: %s", msg)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusServiceUnavailable)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

// Config holds the application configuration
type Config struct {
	MiniMaxGroupID string `json:"minimax_group_id"`
	MiniMaxAPIKey   string `json:"minimax_api_key"`
	BanwagonVeid    string `json:"banwagon_veid"`
	BanwagonAPIKey  string `json:"banwagon_api_key"`
}

func loadConfig() (*Config, error) {
	data, err := os.ReadFile("config.json")
	if err != nil {
		return nil, err
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}
	return &cfg, nil
}
