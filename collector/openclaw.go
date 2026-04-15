package collector

import (
	"database/sql"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	_ "modernc.org/sqlite"
)

// OpenClawData holds all OpenCLAW monitoring data
type OpenClawData struct {
	Timestamp     int64           `json:"timestamp"`
	Tasks         TaskStats       `json:"tasks"`
	RecentTasks   []TaskHistory   `json:"recent_tasks"`
	CronJobs      []CronJob       `json:"cron_jobs"`
	Telegram      []TelegramBot   `json:"telegram"`
	Agents        []AgentInfo     `json:"agents"`
	Models        []ModelInfo     `json:"models"`
	SessionStats  []SessionStats  `json:"session_stats"`
}

type TaskStats struct {
	Total     int               `json:"total"`
	Succeeded int               `json:"succeeded"`
	Failed    int               `json:"failed"`
	TimedOut  int               `json:"timed_out"`
	ByAgent   []AgentTaskStats  `json:"by_agent"`
}

type AgentTaskStats struct {
	AgentID   string `json:"agent_id"`
	Succeeded int    `json:"succeeded"`
	Failed    int    `json:"failed"`
	TimedOut  int    `json:"timed_out"`
}

type TaskHistory struct {
	TaskID            string `json:"task_id"`
	AgentID           string `json:"agent_id"`
	Runtime           string `json:"runtime"`
	ScopeKind         string `json:"scope_kind"`
	Status            string `json:"status"`
	Label             string `json:"label"`
	TerminalSummary   string `json:"terminal_summary"`
	ErrorMsg          string `json:"error_msg"`
	CreatedAt         int64  `json:"created_at"`
}

type CronJob struct {
	ID                string `json:"id"`
	Name              string `json:"name"`
	AgentID           string `json:"agent_id"`
	Enabled           bool   `json:"enabled"`
	NextRunAtMs       int64  `json:"next_run_at_ms"`
	LastStatus        string `json:"last_status"`
	ConsecutiveErrors int    `json:"consecutive_errors"`
}

type TelegramBot struct {
	Name         string `json:"name"`
	LastUpdateMs int64  `json:"last_update_ms"`
	Active       bool   `json:"active"`
}

type AgentInfo struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Model string `json:"model"`
}

type ModelInfo struct {
	ID            string  `json:"id"`
	Name          string  `json:"name"`
	Provider      string  `json:"provider"`
	InputCost     float64 `json:"input_cost"`
	OutputCost    float64 `json:"output_cost"`
	ContextWindow int     `json:"context_window"`
}

type SessionStats struct {
	AgentID        string `json:"agent_id"`
	SessionCount   int    `json:"session_count"`
	LastSessionAt  int64  `json:"last_session_at"`
}

// Package-level cache
var (
	ocCache     *OpenClawData
	ocCacheTime time.Time
	ocCacheTTL  = 30 * time.Second
)

// CollectOpenClaw returns OpenCLAW monitoring data with 30s cache
func CollectOpenClaw() (*OpenClawData, error) {
	if ocCache != nil && time.Since(ocCacheTime) < ocCacheTTL {
		return ocCache, nil
	}
	home := openClawHome()
	dbPath := filepath.Join(home, "tasks", "runs.sqlite")
	cronPath := filepath.Join(home, "cron", "jobs.json")
	tgDir := filepath.Join(home, "telegram")
	configPath := filepath.Join(home, "openclaw.json")
	agentsDir := filepath.Join(home, "agents")
	tasks, _ := readTaskStats(dbPath)
	recent, _ := readRecentTasks(dbPath, 10)
	cron, _ := readCronJobs(cronPath)
	tg, _ := readTelegramBots(tgDir)
	agents, _ := readAgents(configPath)
	models, _ := readModels(configPath)
	sessions, _ := readSessionStats(agentsDir)
	data := OpenClawData{
		Timestamp:    time.Now().Unix(),
		Tasks:       tasks,
		RecentTasks: recent,
		CronJobs:    cron,
		Telegram:    tg,
		Agents:      agents,
		Models:      models,
		SessionStats: sessions,
	}
	ocCache = &data
	ocCacheTime = time.Now()
	return &data, nil
}

func openClawHome() string {
	if home := os.Getenv("OPENCLAW_HOME"); home != "" {
		return home
	}
	if home, err := os.UserHomeDir(); err == nil {
		return filepath.Join(home, ".openclaw")
	}
	return filepath.Join(os.Getenv("HOME"), ".openclaw")
}

func readTaskStats(dbPath string) (TaskStats, error) {
	db, err := sql.Open("sqlite", dbPath+"?_busy_timeout=5000")
	if err != nil {
		return TaskStats{}, err
	}
	defer db.Close()
	var stats TaskStats
	rows, err := db.Query("SELECT agent_id, status, COUNT(*) as cnt FROM task_runs GROUP BY agent_id, status")
	if err != nil {
		return stats, err
	}
	defer rows.Close()
	agentMap := map[string]*AgentTaskStats{}
	for rows.Next() {
		var agentID, status string
		var cnt int
		if err := rows.Scan(&agentID, &status, &cnt); err != nil {
			continue
		}
		if _, ok := agentMap[agentID]; !ok {
			agentMap[agentID] = &AgentTaskStats{AgentID: agentID}
		}
		stats.Total += cnt
		switch status {
		case "succeeded":
			stats.Succeeded += cnt
			agentMap[agentID].Succeeded += cnt
		case "failed":
			stats.Failed += cnt
			agentMap[agentID].Failed += cnt
		case "timed_out":
			stats.TimedOut += cnt
			agentMap[agentID].TimedOut += cnt
		}
	}
	for _, a := range agentMap {
		stats.ByAgent = append(stats.ByAgent, *a)
	}
	sort.Slice(stats.ByAgent, func(i, j int) bool { return stats.ByAgent[i].AgentID < stats.ByAgent[j].AgentID })
	return stats, nil
}

func readRecentTasks(dbPath string, limit int) ([]TaskHistory, error) {
	db, err := sql.Open("sqlite", dbPath+"?_busy_timeout=5000")
	if err != nil {
		return nil, err
	}
	defer db.Close()
	rows, err := db.Query("SELECT task_id, agent_id, runtime, scope_kind, status, label, terminal_summary, error, created_at FROM task_runs ORDER BY created_at DESC LIMIT ?", limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var history []TaskHistory
	for rows.Next() {
		var h TaskHistory
		var agentID, taskID, status, label, terminalSummary, errorMsg, runtime, scopeKind sql.NullString
		if err := rows.Scan(&taskID, &agentID, &runtime, &scopeKind, &status, &label, &terminalSummary, &errorMsg, &h.CreatedAt); err != nil {
			continue
		}
		h.TaskID = taskID.String
		h.AgentID = agentID.String
		h.Runtime = runtime.String
		h.ScopeKind = scopeKind.String
		h.Status = status.String
		h.Label = label.String
		h.TerminalSummary = terminalSummary.String
		h.ErrorMsg = errorMsg.String
		history = append(history, h)
	}
	return history, nil
}

type cronJobsJSON struct {
	Jobs []struct {
		ID      string `json:"id"`
		Name    string `json:"name"`
		AgentID string `json:"agentId"`
		Enabled bool   `json:"enabled"`
		State   struct {
			NextRunAtMs       int64  `json:"nextRunAtMs"`
			LastStatus        string `json:"lastStatus"`
			ConsecutiveErrors int    `json:"consecutiveErrors"`
		} `json:"state"`
	} `json:"jobs"`
}

func readCronJobs(jsonPath string) ([]CronJob, error) {
	data, err := os.ReadFile(jsonPath)
	if err != nil {
		return nil, err
	}
	var parsed cronJobsJSON
	if err := json.Unmarshal(data, &parsed); err != nil {
		return nil, err
	}
	var jobs []CronJob
	for _, j := range parsed.Jobs {
		jobs = append(jobs, CronJob{
			ID:                j.ID,
			Name:              j.Name,
			AgentID:           j.AgentID,
			Enabled:           j.Enabled,
			NextRunAtMs:       j.State.NextRunAtMs,
			LastStatus:        j.State.LastStatus,
			ConsecutiveErrors: j.State.ConsecutiveErrors,
		})
	}
	return jobs, nil
}

func readTelegramBots(dir string) ([]TelegramBot, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	cutoff := time.Now().Add(-30 * time.Minute).UnixMilli()
	var bots []TelegramBot
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		if !strings.HasSuffix(name, ".json") {
			continue
		}
		// Only update-offset-{name}_bot.json files
		if !strings.HasPrefix(name, "update-offset-") {
			continue
		}
		info, _ := e.Info()
		lastMs := info.ModTime().UnixMilli()
		bots = append(bots, TelegramBot{
			Name:         name,
			LastUpdateMs: lastMs,
			Active:       lastMs > cutoff,
		})
	}
	return bots, nil
}

// openclawConfig is used to parse the openclaw.json file
type openclawConfig struct {
	Agents struct {
		List []struct {
			ID    string `json:"id"`
			Name  string `json:"name"`
			Model string `json:"model"` // can be string or object with "primary"
		} `json:"list"`
	} `json:"agents"`
	Models struct {
		Providers map[string]struct {
			Models []struct {
				ID            string `json:"id"`
				Name          string `json:"name"`
				Cost          struct {
					Input  float64 `json:"input"`
					Output float64 `json:"output"`
				} `json:"cost"`
				ContextWindow int `json:"contextWindow"`
			} `json:"models"`
		} `json:"providers"`
	} `json:"models"`
}

func readAgents(configPath string) ([]AgentInfo, error) {
	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, err
	}
	var cfg openclawConfig
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}
	var agents []AgentInfo
	for _, a := range cfg.Agents.List {
		agents = append(agents, AgentInfo{
			ID:    a.ID,
			Name:  a.Name,
			Model: a.Model,
		})
	}
	return agents, nil
}

func readModels(configPath string) ([]ModelInfo, error) {
	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, err
	}
	var cfg openclawConfig
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}
	var models []ModelInfo
	for provider, p := range cfg.Models.Providers {
		for _, m := range p.Models {
			models = append(models, ModelInfo{
				ID:            m.ID,
				Name:          m.Name,
				Provider:      provider,
				InputCost:     m.Cost.Input,
				OutputCost:    m.Cost.Output,
				ContextWindow: m.ContextWindow,
			})
		}
	}
	return models, nil
}

func readSessionStats(agentsDir string) ([]SessionStats, error) {
	entries, err := os.ReadDir(agentsDir)
	if err != nil {
		return nil, err
	}
	var stats []SessionStats
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		agentID := e.Name()
		sessionsPath := filepath.Join(agentsDir, agentID, "sessions")
		files, err := os.ReadDir(sessionsPath)
		if err != nil {
			continue
		}
		count := len(files)
		var lastAt int64
		for _, f := range files {
			info, err := f.Info()
			if err != nil {
				continue
			}
			if info.ModTime().Unix() > lastAt {
				lastAt = info.ModTime().Unix()
			}
		}
		stats = append(stats, SessionStats{
			AgentID:       agentID,
			SessionCount:  count,
			LastSessionAt: lastAt,
		})
	}
	return stats, nil
}
