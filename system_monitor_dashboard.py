#!/usr/bin/env python3
"""
System Monitor Dashboard - HTTP Server + HTML Dashboard
"""

import http.server
import socketserver
import json
import threading
import time
import os
import sys

PORT = 8001
API_INTERVAL = 8.0

# ─── HTML ────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>System Monitor</title>
<style>
  :root {
    --bg: #f0f4f8; --card-bg: #ffffff; --text: #2d3748;
    --text-muted: #718096; --border: #e2e8f0;
    --shadow: 0 2px 12px rgba(0,0,0,0.06); --radius: 14px;
    --mem: #38b2ac; --cpu: #4299e1; --power: #ed8936;
    --temp: #f56565; --disk: #9f7aea; --net: #48bb78;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    background: var(--bg); color: var(--text);
    min-height: 100vh; padding: 18px 22px 28px;
  }
  header {
    display: flex; align-items: center; justify-content: space-between;
    max-width: 1200px; margin: 0 auto 16px;
  }
  header h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.3px; }
  header h1 span { color: var(--text-muted); font-weight: 400; font-size: 13px; }
  .timestamp { font-size: 12px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .interval-ctrl { display: flex; align-items: center; gap: 10px; font-size: 12px; color: var(--text-muted); }
  .interval-ctrl label { font-weight: 600; }
  .interval-ctrl .val { font-weight: 700; color: var(--cpu); min-width: 28px; font-variant-numeric: tabular-nums; }
  input[type=range] { -webkit-appearance: none; appearance: none; height: 4px; border-radius: 4px; background: var(--border); outline: none; cursor: pointer; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 14px; height: 14px; border-radius: 50%; background: var(--cpu); cursor: pointer; box-shadow: 0 1px 4px rgba(66,153,225,0.4); }
  input[type=range]::-moz-range-thumb { width: 14px; height: 14px; border-radius: 50%; background: var(--cpu); cursor: pointer; border: none; box-shadow: 0 1px 4px rgba(66,153,225,0.4); }

  /* Tabs */
  .tabs {
    display: flex; gap: 4px; max-width: 1200px; margin: 0 auto 14px;
    border-bottom: 2px solid var(--border);
  }
  .tab {
    padding: 8px 22px; font-size: 13px; font-weight: 600;
    color: var(--text-muted); cursor: pointer;
    border-radius: 8px 8px 0 0;
    border: 2px solid transparent; border-bottom: none;
    transition: all 0.15s; letter-spacing: 0.3px;
  }
  .tab:hover { background: #ebf8ff; color: var(--cpu); }
  .tab.active {
    color: var(--cpu); border-color: var(--border); border-bottom-color: var(--card-bg);
    background: var(--card-bg); margin-bottom: -2px;
  }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  /* Grid */
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 14px; max-width: 1200px; margin: 0 auto 14px;
  }
  .card {
    background: var(--card-bg); border-radius: var(--radius);
    padding: 18px 20px; box-shadow: var(--shadow); border: 1px solid var(--border);
  }
  .card-title {
    font-size: 10px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;
    color: var(--text-muted); margin-bottom: 12px;
  }
  .card.mem { border-left: 3px solid var(--mem); }
  .card.mem .card-title { color: var(--mem); }
  .card.cpu { border-left: 3px solid var(--cpu); }
  .card.cpu .card-title { color: var(--cpu); }
  .card.power { border-left: 3px solid var(--power); }
  .card.power .card-title { color: var(--power); }
  .card.temp { border-left: 3px solid var(--temp); }
  .card.temp .card-title { color: var(--temp); }
  .card.disk { border-left: 3px solid var(--disk); }
  .card.disk .card-title { color: var(--disk); }
  .card.net { border-left: 3px solid var(--net); }
  .card.net .card-title { color: var(--net); }

  .big-val { font-size: 36px; font-weight: 800; font-variant-numeric: tabular-nums; line-height: 1; margin-bottom: 3px; }
  .big-unit { font-size: 14px; font-weight: 400; color: var(--text-muted); margin-left: 3px; }
  .sub-text { font-size: 12px; color: var(--text-muted); margin-bottom: 10px; }

  .bar-bg { background: var(--bg); border-radius: 6px; height: 5px; margin-bottom: 10px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 6px; transition: width 0.5s ease; }
  .bar-fill.mem { background: var(--mem); }
  .bar-fill.cpu { background: var(--cpu); }
  .bar-fill.gpu { background: var(--power); }
  .bar-fill.disk { background: var(--disk); }
  .bar-fill.temp { background: var(--temp); }

  .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
  .detail-item { background: var(--bg); border-radius: 7px; padding: 7px 9px; }
  .detail-label { font-size: 9px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .detail-value { font-size: 15px; font-weight: 700; font-variant-numeric: tabular-nums; margin-top: 2px; }

  .pressure-badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; }
  .pressure-badge.normal { background: #c6f6d5; color: #276749; }
  .pressure-badge.warning { background: #feebc8; color: #c05621; }
  .pressure-badge.critical { background: #fed7d7; color: #c53030; }
  .pressure-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }

  .power-row { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }
  .power-label { font-size: 10px; color: var(--text-muted); width: 38px; }
  .power-bar-bg { flex: 1; background: var(--bg); border-radius: 4px; height: 5px; }
  .power-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
  .power-val { font-size: 11px; font-weight: 700; width: 50px; text-align: right; font-variant-numeric: tabular-nums; }

  .io-grid { display: flex; gap: 10px; }
  .io-item { flex: 1; text-align: center; }

  .full { grid-column: 1 / -1; }

  /* Sparklines */
  .spark-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px 20px; }
  .spark-item { }
  .spark-title { font-size: 9px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
  .spark-canvas { display: block; }

  /* Placeholders */
  .placeholder {
    display: flex; align-items: center; justify-content: center;
    min-height: 200px; color: var(--text-muted); font-size: 14px;
    background: var(--card-bg); border-radius: var(--radius);
    border: 1px dashed var(--border);
  }

  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  .live-dot { display:inline-block; width:6px; height:6px; border-radius:50%; background:#48bb78; animation:pulse 2s infinite; margin-right:3px; }

  footer { text-align: center; font-size: 11px; color: var(--text-muted); margin-top: 14px; max-width: 1200px; margin-left: auto; margin-right: auto; }
</style>
</head>
<body>

<header>
  <h1>System Monitor <span>/ Jimmy's Mac mini</span></h1>
  <div style="display:flex;align-items:center;gap:16px;">
    <div id="fetch-error" style="display:none;font-size:11px;color:#fc8181;background:#fed7d7;padding:2px 8px;border-radius:10px;">⚠ 数据过期</div>
    <div class="timestamp" id="ts">--</div>
    <div class="interval-ctrl">
      <label>Interval</label>
      <input type="range" id="int-slider" min="1" max="10" value="2" step="1">
      <span class="val" id="int-val">2s</span>
    </div>
  </div>
</header>

<!-- Tabs -->
<div class="tabs">
  <div class="tab active" data-tab="system">SYSTEM</div>
  <div class="tab" data-tab="oml">oMLX</div>
  <div class="tab" data-tab="openclaw">OPENCLAW</div>
</div>

<!-- SYSTEM -->
<div id="tab-system" class="tab-panel active">
  <div class="grid">
    <!-- CPU + GPU 合并卡片 -->
    <div class="card cpu">
      <div style="display:grid;grid-template-columns:1fr;gap:16px;">
        <div>
          <div class="card-title">CPU</div>
          <div class="big-val" id="cpu-pct">--<span class="big-unit">%</span></div>
          <div class="bar-bg"><div class="bar-fill cpu" id="cpu-bar" style="width:0%"></div></div>
        </div>
        <div>
          <div class="card-title" style="color:var(--power);">GPU</div>
          <div class="big-val" id="gpu-pct">--<span class="big-unit">%</span></div>
          <div class="bar-bg"><div class="bar-fill" id="gpu-bar" style="width:0%;background:var(--power)"></div></div>
        </div>
      </div>
    </div>

    <!-- Memory -->
    <div class="card mem">
      <div class="card-title">Memory</div>
      <div class="big-val" id="mem-pct">--<span class="big-unit">%</span></div>
      <div class="sub-text" id="mem-detail">-- / -- GB</div>
      <div class="bar-bg"><div class="bar-fill mem" id="mem-bar" style="width:0%"></div></div>
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div style="font-size:11px;color:var(--text-muted)">Swap <span id="mem-swap">--</span></div>
        <div class="pressure-badge normal" id="mem-pressure"><span class="pressure-dot"></span><span id="mem-pressure-text">--</span></div>
      </div>
    </div>

    <!-- Power -->
    <div class="card power">
      <div class="card-title">Power</div>
      <div class="big-val" id="pw-total">--<span class="big-unit">W</span></div>
      <div class="sub-text" id="pw-sub" style="display:none;"></div>
      <div id="pw-rows"></div>
    </div>

    <!-- Temperature -->
    <div class="card temp">
      <div class="card-title">Temperature</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div style="text-align:center;">
          <div style="font-size:28px;font-weight:800;font-variant-numeric:tabular-nums;" id="temp-cpu">--<span style="font-size:13px;font-weight:400;color:var(--text-muted)">°C</span></div>
          <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">CPU</div>
          <div class="bar-bg" style="margin-top:6px;"><div class="bar-fill temp" id="temp-cpu-bar" style="width:0%"></div></div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:28px;font-weight:800;font-variant-numeric:tabular-nums;" id="temp-gpu">--<span style="font-size:13px;font-weight:400;color:var(--text-muted)">°C</span></div>
          <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">GPU</div>
          <div class="bar-bg" style="margin-top:6px;"><div class="bar-fill temp" id="temp-gpu-bar" style="width:0%"></div></div>
        </div>
      </div>
    </div>

    <!-- Disk -->
    <div class="card disk">
      <div class="card-title">Disk</div>
      <div class="big-val" id="disk-pct">--<span class="big-unit">%</span></div>
      <div class="sub-text" id="disk-detail">-- / -- GB</div>
      <div class="bar-bg"><div class="bar-fill disk" id="disk-bar" style="width:0%"></div></div>
      <div class="io-grid">
        <div class="io-item">
          <div class="detail-value" style="font-size:13px;" id="disk-read">--</div>
          <div class="detail-label">↑ Read MB/s</div>
        </div>
        <div class="io-item">
          <div class="detail-value" style="font-size:13px;" id="disk-write">--</div>
          <div class="detail-label">↓ Write MB/s</div>
        </div>
      </div>
    </div>

    <!-- Network -->
    <div class="card net">
      <div class="card-title">Network</div>
      <div class="io-grid">
        <div class="io-item">
          <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">Download</div>
          <div style="font-size:24px;font-weight:800;font-variant-numeric:tabular-nums;" id="net-down">--</div>
          <div class="detail-label">MB/s</div>
        </div>
        <div class="io-item">
          <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">Upload</div>
          <div style="font-size:24px;font-weight:800;font-variant-numeric:tabular-nums;" id="net-up">--</div>
          <div class="detail-label">MB/s</div>
        </div>
      </div>
    </div>
  </div>

  <!-- History -->
  <div class="grid">
    <div class="card full">
      <div class="card-title" style="margin-bottom:10px;">History <span class="live-dot"></span>Live</div>
      <div class="spark-row">
        <div class="spark-item">
          <div class="spark-title">Memory %</div>
          <canvas class="spark-canvas" id="spark-mem" width="320" height="70"></canvas>
        </div>
        <div class="spark-item">
          <div class="spark-title">CPU/GPU %</div>
          <canvas class="spark-canvas" id="spark-cpu" width="320" height="70"></canvas>
        </div>

        <div class="spark-item">
          <div class="spark-title">Power W</div>
          <canvas class="spark-canvas" id="spark-pw" width="320" height="70"></canvas>
        </div>
        <div class="spark-item">
          <div class="spark-title">CPU/GPU °C</div>
          <canvas class="spark-canvas" id="spark-tcpu" width="320" height="70"></canvas>
        </div>

        <div class="spark-item">
          <div class="spark-title">Net ↓ MB/s</div>
          <canvas class="spark-canvas" id="spark-net" width="320" height="70"></canvas>
        </div>
        <div class="spark-item">
          <div class="spark-title">Net ↑ MB/s</div>
          <canvas class="spark-canvas" id="spark-net-up" width="320" height="70"></canvas>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- oMLX -->
<div id="tab-oml" class="tab-panel">
  <div class="grid">
    <div class="card" style="border-left:3px solid #9f7aea;">
      <div class="card-title" style="color:#9f7aea;">Status</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div style="text-align:center;padding:8px 4px;background:#f7fafc;border-radius:8px;">
          <div style="font-size:22px;font-weight:800;color:#2d3748;" id="oml-models-discovered">--</div>
          <div style="font-size:9px;color:#a0aec0;text-transform:uppercase;letter-spacing:0.5px;">Discovered</div>
        </div>
        <div style="text-align:center;padding:8px 4px;background:#f7fafc;border-radius:8px;">
          <div style="font-size:22px;font-weight:800;color:#48bb78;" id="oml-models-loaded">--</div>
          <div style="font-size:9px;color:#a0aec0;text-transform:uppercase;letter-spacing:0.5px;">Loaded</div>
        </div>
      </div>
      <div style="text-align:center;padding:8px 4px;background:#f7fafc;border-radius:8px;margin-top:8px;">
        <div style="font-size:14px;font-weight:700;color:#4299e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" id="oml-models-default">--</div>
        <div style="font-size:9px;color:#a0aec0;text-transform:uppercase;letter-spacing:0.5px;">Default</div>
      </div>
    </div>

    <div class="card" style="border-left:3px solid #ed8936;">
      <div class="card-title" style="color:#ed8936;">Performance</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:18px;font-weight:800;color:#2d3748;" id="oml-prefill-tps">--</div>
          <div style="font-size:8px;color:#a0aec0;">Prefill tok/s</div>
        </div>
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:18px;font-weight:800;color:#2d3748;" id="oml-gen-tps">--</div>
          <div style="font-size:8px;color:#a0aec0;">Gen tok/s</div>
        </div>
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:18px;font-weight:800;color:#2d3748;" id="oml-cache-eff">--</div>
          <div style="font-size:8px;color:#a0aec0;">Cache %</div>
        </div>
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:18px;font-weight:800;color:#2d3748;" id="oml-requests">--</div>
          <div style="font-size:8px;color:#a0aec0;">Requests</div>
        </div>
      </div>
    </div>

    <div class="card" style="border-left:3px solid #38b2ac;">
      <div class="card-title" style="color:#38b2ac;">Memory</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:18px;font-weight:800;color:#2d3748;" id="oml-mem-used">--</div>
          <div style="font-size:8px;color:#a0aec0;">Used</div>
        </div>
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:18px;font-weight:800;color:#2d3748;" id="oml-mem-max">--</div>
          <div style="font-size:8px;color:#a0aec0;">Max</div>
        </div>
      </div>
      <div style="margin-top:8px;">
        <div style="display:flex;justify-content:space-between;font-size:10px;color:#718096;margin-bottom:3px;">
          <span>Memory</span><span id="oml-mem-pct">--%</span>
        </div>
        <div class="bar-bg"><div class="bar-fill" id="oml-mem-bar" style="width:0%;background:#38b2ac;"></div></div>
      </div>
    </div>

    <div class="card" style="border-left:3px solid #718096;">
      <div class="card-title" style="color:#718096;">TOKENS &amp; TASK</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:18px;font-weight:800;color:#2d3748;" id="oml-prompt-tok">--</div>
          <div style="font-size:8px;color:#a0aec0;">Prompt</div>
        </div>
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:18px;font-weight:800;color:#2d3748;" id="oml-completion-tok">--</div>
          <div style="font-size:8px;color:#a0aec0;">Completion</div>
        </div>
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:18px;font-weight:800;color:#2d3748;" id="oml-active-req">--</div>
          <div style="font-size:8px;color:#a0aec0;">Active</div>
        </div>
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:18px;font-weight:800;color:#2d3748;" id="oml-waiting-req">--</div>
          <div style="font-size:8px;color:#a0aec0;">Waiting</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Model List -->
  <div class="grid">
    <div class="card full" style="border-left:3px solid #9f7aea;">
      <div class="card-title" style="margin-bottom:10px;color:#9f7aea;">Models</div>
      <div id="oml-models-list" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;"></div>
    </div>
  </div>
</div>

<!-- OPENCLAW -->
<div id="tab-openclaw" class="tab-panel">
  <div class="grid">
    <div class="card" style="border-left:3px solid #805ad5;">
      <div class="card-title" style="color:#805ad5;">Gateway</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:16px;font-weight:800;color:#2d3748;" id="oc-version">--</div>
          <div style="font-size:8px;color:#a0aec0;">Version</div>
        </div>
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:16px;font-weight:800;color:#2d3748;" id="oc-uptime">--</div>
          <div style="font-size:8px;color:#a0aec0;">Uptime</div>
        </div>
      </div>
      <div style="margin-top:8px;">
        <div style="display:flex;justify-content:space-between;font-size:10px;color:#718096;margin-bottom:3px;">
          <span>Tasks</span><span id="oc-task-pct">--</span>
        </div>
        <div class="bar-bg"><div class="bar-fill" id="oc-task-bar" style="width:0%;background:#805ad5;"></div></div>
      </div>
    </div>

    <div class="card" style="border-left:3px solid #38a169;">
      <div class="card-title" style="color:#38a169;">Tasks</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;">
        <div style="text-align:center;padding:5px 3px;background:#f7fafc;border-radius:6px;">
          <div style="font-size:15px;font-weight:800;color:#2d3748;" id="oc-task-total">--</div>
          <div style="font-size:7px;color:#a0aec0;">Total</div>
        </div>
        <div style="text-align:center;padding:5px 3px;background:#f7fafc;border-radius:6px;">
          <div style="font-size:15px;font-weight:800;color:#3182ce;" id="oc-task-active">--</div>
          <div style="font-size:7px;color:#a0aec0;">Active</div>
        </div>
        <div style="text-align:center;padding:5px 3px;background:#f7fafc;border-radius:6px;">
          <div style="font-size:15px;font-weight:800;color:#48bb78;" id="oc-task-succeeded">--</div>
          <div style="font-size:7px;color:#a0aec0;">Succeeded</div>
        </div>
        <div style="text-align:center;padding:5px 3px;background:#f7fafc;border-radius:6px;">
          <div style="font-size:15px;font-weight:800;color:#fc8181;" id="oc-task-failed">--</div>
          <div style="font-size:7px;color:#a0aec0;">Failed</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-top:6px;">
        <div style="text-align:center;padding:4px 3px;background:#f7fafc;border-radius:5px;">
          <div style="font-size:12px;font-weight:700;color:#2d3748;" id="oc-task-cli">--</div>
          <div style="font-size:7px;color:#a0aec0;">CLI</div>
        </div>
        <div style="text-align:center;padding:4px 3px;background:#f7fafc;border-radius:5px;">
          <div style="font-size:12px;font-weight:700;color:#2d3748;" id="oc-task-cron">--</div>
          <div style="font-size:7px;color:#a0aec0;">Cron</div>
        </div>
        <div style="text-align:center;padding:4px 3px;background:#f7fafc;border-radius:5px;">
          <div style="font-size:12px;font-weight:700;color:#2d3748;" id="oc-task-timedout">--</div>
          <div style="font-size:7px;color:#a0aec0;">Timeout</div>
        </div>
      </div>
    </div>

    <div class="card" style="border-left:3px solid #3182ce;">
      <div class="card-title" style="color:#3182ce;">Telegram</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:16px;font-weight:800;" id="oc-tg-status">--</div>
          <div style="font-size:8px;color:#a0aec0;">Status</div>
        </div>
        <div style="text-align:center;padding:6px 4px;background:#f7fafc;border-radius:7px;">
          <div style="font-size:14px;font-weight:700;color:#2d3748;" id="oc-tg-bot">--</div>
          <div style="font-size:8px;color:#a0aec0;">Bot</div>
        </div>
      </div>
      <div style="margin-top:8px;">
        <div style="display:flex;justify-content:space-between;font-size:10px;color:#718096;margin-bottom:3px;">
          <span>Telegram</span><span id="oc-tg-channels">--</span>
        </div>
      </div>
    </div>

    <div class="card" style="border-left:3px solid #ed8936;">
      <div class="card-title" style="color:#ed8936;">Sessions</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;">
        <div style="text-align:center;padding:5px 3px;background:#f7fafc;border-radius:6px;">
          <div style="font-size:15px;font-weight:800;color:#2d3748;" id="oc-sess-count">--</div>
          <div style="font-size:7px;color:#a0aec0;">Total</div>
        </div>
        <div style="text-align:center;padding:5px 3px;background:#f7fafc;border-radius:6px;">
          <div style="font-size:15px;font-weight:800;color:#ed8936;" id="oc-sess-minutes">--</div>
          <div style="font-size:7px;color:#a0aec0;">Active Min</div>
        </div>
        <div style="text-align:center;padding:5px 3px;background:#f7fafc;border-radius:6px;">
          <div style="font-size:15px;font-weight:800;color:#2d3748;" id="oc-sess-agents">--</div>
          <div style="font-size:7px;color:#a0aec0;">Agents</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Agents List -->
  <div class="grid" style="margin-top:0;">
    <div class="card full" style="border-left:3px solid #ed8936;">
      <div class="card-title" style="margin-bottom:10px;color:#ed8936;">Agents</div>
      <div id="oc-agents-list" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;"></div>
    </div>
  </div>
</div>

<footer>Auto-refresh <span id="footer-interval">2</span>s &nbsp;·&nbsp; Source: macmon &nbsp;·&nbsp; <span class="live-dot"></span>Live</footer>

<script>
const API = '/json';
const MAX_HIST = 60;
let UPDATE_INTERVAL = 2;

let history = { mem: [], cpu: [], gpuUsage: [], power: [], cpuTemp: [], gpuTemp: [], netDown: [], netUp: [] };

function el(id) { return document.getElementById(id); }
function round(v, d) { if (v == null || isNaN(v)) return '--'; return Number(v).toFixed(d != null ? d : 1); }

// Tab switching
document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    document.getElementById('tab-' + t.dataset.tab).classList.add('active');
  });
});

// Mini sparkline (no axes, simple line)
function drawMiniSpark(canvasId, data, color, maxVal) {
  const canvas = el(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!data || data.length < 2) return;

  const valid = data.filter(v => v != null);
  const m = maxVal || (valid.length ? Math.max(...valid, 1) * 1.2 : 100);
  const step = W / Math.max(data.length - 1, 1);

  ctx.beginPath();
  let started = false;
  data.forEach((v, i) => {
    if (v == null) { started = false; return; }
    const x = i * step;
    const y = H - (Math.max(0, v) / m) * H;
    if (!started) { ctx.moveTo(x, y); started = true; }
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Gradient fill
  if (data.length > 1) {
    const lastValid = data.map((v, i) => v != null ? i : -1).filter(i => i >= 0).pop();
    if (lastValid !== undefined) {
      const lastX = lastValid * step;
      ctx.lineTo(lastX, H);
      ctx.lineTo(0, H);
      ctx.closePath();
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, color + '44');
      grad.addColorStop(1, color + '00');
      ctx.fillStyle = grad;
      ctx.fill();
    }
  }
}

// Sparkline with Y axis labels
function drawSpark(canvasId, data, color, maxVal) {
  const canvas = el(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (data.length < 2) return;

  const AXIS_LEFT = 30;     // Y label width
  const AXIS_BOTTOM = 14;   // X label height
  const PAD_TOP = 4;
  const plotW = W - AXIS_LEFT - 4;
  const plotH = H - AXIS_BOTTOM - PAD_TOP;

  const valid = data.filter(v => v != null);
  const m = maxVal || (valid.length ? Math.max(...valid, 0.01) * 1.25 : 1);
  const step = plotW / (data.length - 1);

  // Y axis grid + labels (4 ticks)
  ctx.font = '8px system-ui, sans-serif';
  ctx.textAlign = 'right';
  for (let g = 0; g <= 3; g++) {
    const yFrac = g / 3;
    const yPx = PAD_TOP + yFrac * plotH;
    const val = m * (1 - yFrac);
    ctx.strokeStyle = '#edf2f7';
    ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.moveTo(AXIS_LEFT, yPx); ctx.lineTo(W - 2, yPx); ctx.stroke();
    ctx.fillStyle = '#a0aec0';
    ctx.fillText(Number(val).toFixed(maxVal ? 0 : 1), AXIS_LEFT - 3, yPx + 3);
  }

  // Y axis line
  ctx.strokeStyle = '#e2e8f0';
  ctx.lineWidth = 0.5;
  ctx.beginPath(); ctx.moveTo(AXIS_LEFT, PAD_TOP); ctx.lineTo(AXIS_LEFT, PAD_TOP + plotH); ctx.stroke();

  // Gradient fill
  const grad = ctx.createLinearGradient(0, PAD_TOP, 0, PAD_TOP + plotH);
  grad.addColorStop(0, color + '55'); grad.addColorStop(1, color + '00');

  // Build path
  const pts = [];
  let started = false;
  data.forEach((v, i) => {
    if (v == null) { started = false; return; }
    const x = AXIS_LEFT + i * step;
    const y = PAD_TOP + plotH - (Math.max(0, v) / m) * plotH;
    pts.push([x, y]);
    if (!started) { ctx.beginPath(); ctx.moveTo(x, y); started = true; }
    else ctx.lineTo(x, y);
  });

  if (pts.length > 0) {
    ctx.lineTo(pts[pts.length - 1][0], PAD_TOP + plotH);
    ctx.lineTo(pts[0][0], PAD_TOP + plotH);
    ctx.closePath();
    ctx.fillStyle = grad; ctx.fill();
    ctx.beginPath(); started = false;
    pts.forEach(([x, y]) => { if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y); });
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
  }

  // X labels: start, middle, end
  ctx.textAlign = 'center';
  ctx.fillStyle = '#a0aec0';
  [0, Math.floor(data.length / 2), data.length - 1].forEach(i => {
    if (i >= 0 && i < data.length) {
      const x = AXIS_LEFT + i * step;
      const age = (data.length - 1 - i) * UPDATE_INTERVAL;
      ctx.fillText('-' + age + 's', x, H - 2);
    }
  });
}

// Draw multiple lines on the same canvas (dual-line sparkline with legend)
function drawSpark2(canvasId, series) {
  // series = [{ data: [...], color: '#xxx', label: 'CPU' }, ...]
  const canvas = el(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  const AXIS_LEFT = 30, AXIS_BOTTOM = 14, PAD_TOP = 4;
  const plotW = W - AXIS_LEFT - 4, plotH = H - AXIS_BOTTOM - PAD_TOP;

  // Compute max across all series
  let m = 0;
  series.forEach(s => {
    const valid = (s.data || []).filter(v => v != null);
    if (valid.length) m = Math.max(m, ...valid);
  });
  m = m * 1.25 || 1;

  // Y grid + labels
  ctx.font = '8px system-ui, sans-serif';
  ctx.textAlign = 'right';
  for (let g = 0; g <= 3; g++) {
    const yFrac = g / 3;
    const yPx = PAD_TOP + yFrac * plotH;
    const val = m * (1 - yFrac);
    ctx.strokeStyle = '#edf2f7'; ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.moveTo(AXIS_LEFT, yPx); ctx.lineTo(W - 2, yPx); ctx.stroke();
    ctx.fillStyle = '#a0aec0';
    ctx.fillText(val.toFixed(0), AXIS_LEFT - 3, yPx + 3);
  }
  ctx.strokeStyle = '#e2e8f0'; ctx.lineWidth = 0.5;
  ctx.beginPath(); ctx.moveTo(AXIS_LEFT, PAD_TOP); ctx.lineTo(AXIS_LEFT, PAD_TOP + plotH); ctx.stroke();

  // Draw each series (no fill, lines only)
  series.forEach(({ data, color }) => {
    if (!data || data.length < 2) return;
    const step = plotW / (data.length - 1);
    let started = false;
    ctx.beginPath();
    data.forEach((v, i) => {
      if (v == null) { started = false; return; }
      const x = AXIS_LEFT + i * step;
      const y = PAD_TOP + plotH - (Math.max(0, v) / m) * plotH;
      if (!started) { ctx.moveTo(x, y); started = true; }
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
  });

  // Legend top-right
  series.forEach(({ data, color, label }, i) => {
    if (!data || data.length === 0) return;
    const lx = W - 4, ly = PAD_TOP + 8 + i * 12;
    ctx.strokeStyle = color; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(lx - 12, ly); ctx.lineTo(lx - 4, ly); ctx.stroke();
    ctx.fillStyle = '#a0aec0'; ctx.font = '8px system-ui, sans-serif'; ctx.textAlign = 'left';
    ctx.fillText(label, lx, ly + 3);
  });

  // X labels
  ctx.textAlign = 'center'; ctx.fillStyle = '#a0aec0';
  [0, Math.floor((series[0].data || []).length / 2), (series[0].data || []).length - 1].forEach(i => {
    if (i >= 0 && i < (series[0].data || []).length) {
      const x = AXIS_LEFT + i * (plotW / Math.max(1, (series[0].data || []).length - 1));
      const age = ((series[0].data || []).length - 1 - i) * UPDATE_INTERVAL;
      ctx.fillText('-' + age + 's', x, H - 2);
    }
  });
}

// Per-core bar renderer - compact 2-row grid (5 per row max)
function renderCoreBars(gridId, cores, color) {
  const grid = el(gridId);
  if (!grid) return;
  if (!cores || cores.length === 0) { grid.innerHTML = ''; return; }
  // Limit to 10 cores max, arrange in 2 rows of 5
  const displayCores = cores.slice(0, 10);
  const cols = Math.min(displayCores.length, 5);
  const rows = Math.ceil(displayCores.length / cols);
  let html = `<div style="display:grid;grid-template-columns:repeat(${cols},1fr);gap:4px;">`;
  displayCores.forEach((v, i) => {
    const pct = v != null ? Math.min(100, Math.max(0, v)) : 0;
    const label = v != null ? Math.round(v) + '%' : '--';
    html += `<div style="text-align:center;padding:3px 2px;background:#f7fafc;border-radius:4px;">
      <div style="font-size:8px;color:#a0aec0;margin-bottom:2px;">${i}</div>
      <div style="background:#edf2f7;border-radius:3px;height:18px;overflow:hidden;">
        <div style="height:100%;width:${pct}%;background:${color};border-radius:3px;transition:width 0.3s;"></div>
      </div>
      <div style="font-size:9px;font-weight:700;color:#2d3748;margin-top:1px;font-variant-numeric:tabular-nums;">${label}</div>
    </div>`;
  });
  html += '</div>';
  grid.innerHTML = html;
}

function updateUI(data) {
  if (!data || !data.memory) { console.warn('no data yet'); return; }
  try {
  const mem = data.memory, cpu = data.cpu, pw = data.power;
  const disk = data.disk, net = data.network;

  const ts = data.timestamp ? new Date(data.timestamp * 1000) : new Date();
  el('ts').textContent = ts.toLocaleString('zh-CN', {hour12: false}) + ' (刷新中)';

  // Memory
  el('mem-pct').innerHTML = round(mem.percent, 0) + '<span class="big-unit">%</span>';
  el('mem-detail').textContent = round(mem.used_gb, 1) + ' / ' + round(mem.total_gb, 1) + ' GB';
  el('mem-bar').style.width = Math.min(100, mem.percent) + '%';
  el('mem-swap').textContent = round(mem.swap_used_gb, 1) + ' / ' + round(mem.swap_total_gb, 1) + ' GB';
  const pt = el('mem-pressure'), ptText = el('mem-pressure-text');
  pt.className = 'pressure-badge ' + (mem.pressure || 'normal');
  ptText.textContent = (mem.pressure || '--').toUpperCase();

  // CPU - use avg of per_core since cpu.percent from cpu_times can be stale
  const cpuPerCore = cpu.per_core || [];
  const cpuAvg = cpuPerCore.length > 0 ? cpuPerCore.reduce((a,b) => a+b, 0) / cpuPerCore.length : 0;
  const gpuPct = (pw && pw.gpu_usage_pct != null) ? pw.gpu_usage_pct : 0;
  el('cpu-pct').innerHTML = round(cpuAvg, 0) + '<span class="big-unit">%</span>';
  el('cpu-bar').style.width = Math.min(100, cpuAvg) + '%';
  el('gpu-pct').innerHTML = gpuPct >= 0 ? round(gpuPct, 0) + '<span class="big-unit">%</span>' : '--<span class="big-unit">%</span>';
  el('gpu-bar').style.width = Math.min(100, Math.max(0, gpuPct)) + '%';

  // Power - component breakdown
  const pwRows = el('pw-rows');
  if (!pwRows) {
    el('pw-total').innerHTML = '--<span class="big-unit">W</span>';
  } else {
    const components = [
      { key: 'cpu', label: 'CPU', val: (pw && pw.cpu_power_w) || 0, color: '#ed8936' },
      { key: 'gpu', label: 'GPU', val: (pw && pw.gpu_power_w) || 0, color: '#9f7aea' },
      { key: 'ram', label: 'RAM', val: (pw && pw.ram_power_w) || 0, color: '#38b2ac' },
      { key: 'ane', label: 'ANE', val: (pw && pw.ane_power_w) || 0, color: '#48bb78' },
      { key: 'sys', label: 'SYS', val: (pw && pw.sys_power_w) || 0, color: '#2d3748' },
    ];
    const validComps = components.filter(c => c.val > 0);
    const totalSys = (pw && pw.sys_power_w) || 0;
    el('pw-total').innerHTML = totalSys > 0 ? round(totalSys, 2) + '<span class="big-unit">W</span>' : '--<span class="big-unit">W</span>';
    if (validComps.length === 0) {
      pwRows.innerHTML = '<div style="font-size:11px;color:var(--text-muted);padding:8px 0;">No power data</div>';
    } else {
      const maxPw = Math.max(...validComps.map(c => c.val), 1) * 1.3;
      pwRows.innerHTML = validComps.map(c => `
        <div class="power-row">
          <div class="power-label">${c.label}</div>
          <div class="power-bar-bg"><div class="power-bar-fill" style="width:${Math.min(100, (c.val / maxPw) * 100)}%;background:${c.color};"></div></div>
          <div class="power-val">${round(c.val, 2)}W</div>
        </div>`).join('');
    }
  }

  // Temperature
  const cpuT = (pw && pw.cpu_temp_c) || 0;
  const gpuT = (pw && pw.gpu_temp_c) || 0;
  const mkTemp = (id, val) => el(id).innerHTML = val > 0 ? round(val, 0) + '<span style="font-size:13px;font-weight:400;color:var(--text-muted)">°C</span>' : '--<span style="font-size:13px;font-weight:400;color:var(--text-muted)">°C</span>';
  mkTemp('temp-cpu', cpuT); mkTemp('temp-gpu', gpuT);
  el('temp-cpu-bar').style.width = Math.min(100, cpuT) + '%';
  el('temp-gpu-bar').style.width = Math.min(100, gpuT) + '%';

  // Disk - compute used from percent to avoid inconsistent raw data
  const diskPct = disk.percent || 0;
  const diskTotal = disk.total_gb || 0;
  const diskUsed = diskPct > 0 ? Math.round(diskTotal * diskPct / 100 * 10) / 10 : 0;
  el('disk-pct').innerHTML = round(diskPct, 0) + '<span class="big-unit">%</span>';
  el('disk-detail').textContent = diskUsed + ' / ' + round(diskTotal, 0) + ' GB';
  el('disk-bar').style.width = Math.min(100, diskPct) + '%';
  el('disk-read').textContent = disk.read_mb_s > 0.05 ? round(disk.read_mb_s, 1) : '--';
  el('disk-write').textContent = disk.write_mb_s > 0.05 ? round(disk.write_mb_s, 1) : '--';

  // Network
  el('net-down').textContent = net.recv_mb_s > 0.01 ? round(net.recv_mb_s, 2) : '--';
  el('net-up').textContent = net.sent_mb_s > 0.01 ? round(net.sent_mb_s, 2) : '--';

  // History
  history.mem.push(mem.percent);
  history.cpu.push(cpu.percent);
  history.gpuUsage.push(pw && pw.gpu_usage_pct != null ? pw.gpu_usage_pct : null);
  history.power.push((pw && pw.sys_power_w) || null);
  history.cpuTemp.push(cpuT > 0 ? cpuT : null);
  history.gpuTemp.push(gpuT > 0 ? gpuT : null);
  history.netDown.push(net.recv_mb_s > 0 ? net.recv_mb_s : 0);
  history.netUp.push(net.sent_mb_s > 0 ? net.sent_mb_s : 0);
  [history.mem, history.cpu, history.gpuUsage, history.power, history.cpuTemp, history.gpuTemp, history.netDown, history.netUp].forEach(arr => {
    if (arr.length > MAX_HIST) arr.shift();
  });

  // Dual-line sparklines: CPU+GPU overlaid, CPU+GPU temp overlaid
  drawSpark2('spark-cpu',
    [{ data: history.cpu, color: '#4299e1', label: 'CPU' },
     { data: history.gpuUsage, color: '#ed8936', label: 'GPU' }]);
  drawSpark2('spark-tcpu',
    [{ data: history.cpuTemp, color: '#4299e1', label: 'CPU' },
     { data: history.gpuTemp, color: '#ed8936', label: 'GPU' }]);
  // Single-line sparklines
  drawSpark('spark-mem', history.mem, '#38b2ac', 100);
  const vp = history.power.filter(v => v != null);
  const mp = vp.length ? Math.max(...vp, 2) : 2;
  drawSpark('spark-pw', history.power, '#ed8936', mp * 1.3);
  drawSpark('spark-net', history.netDown, '#48bb78', null);
  drawSpark('spark-net-up', history.netUp, '#4299e1', null);
  } catch(e) { console.error('updateUI error:', e); }
}

async function fetchData() {
  try {
    const r = await fetch(API + '?t=' + Date.now());
    if (r.ok) {
      updateUI(await r.json());
      el('fetch-error').style.display = 'none';
    } else {
      el('fetch-error').style.display = 'inline-block';
    }
  } catch(e) { el('fetch-error').style.display = 'inline-block'; console.warn('fetch error', e); }
}

// System + oMLX polling (uses UPDATE_INTERVAL slider)
let pollInProgress = false;
async function pollSystemAndOmlx() {
  if (paused || pollInProgress) return;
  pollInProgress = true;
  try {
    await Promise.allSettled([fetchData(), fetchOmlx()]);
  } finally {
    pollInProgress = false;
  }
}

// OpenClaw polling — independent 10s fixed interval (CLI is slow, separate from main cycle)
let ocPollTimer = null;
function startOpenClawTimer() {
  if (ocPollTimer) clearInterval(ocPollTimer);
  ocPollTimer = setInterval(fetchOpenClaw, 10000);
}

// oMLX fetch (called by pollAll)
async function fetchOmlx() {
  try {
    const r = await fetch('/oml');
    if (!r.ok) return;
    const d = await r.json();
    // Models overview
    el('oml-models-discovered').textContent = d.models_discovered || 0;
    el('oml-models-loaded').textContent = d.models_loaded || 0;
    const defModel = (d.default_model || '').split('/').pop();
    el('oml-models-default').textContent = defModel || '--';
    // Performance
    el('oml-prefill-tps').textContent = d.avg_prefill_tps != null ? d.avg_prefill_tps : '--';
    el('oml-gen-tps').textContent = d.avg_generation_tps != null ? d.avg_generation_tps : '--';
    el('oml-cache-eff').textContent = d.cache_efficiency != null ? d.cache_efficiency + '%' : '--';
    el('oml-requests').textContent = d.total_requests || 0;
    // Memory
    el('oml-mem-used').textContent = d.model_memory_used_formatted || '--';
    el('oml-mem-max').textContent = d.model_memory_max_formatted || '--';
    const memMax = d.model_memory_max || 1;
    const memUsed = d.model_memory_used || 0;
    const memPct = memMax > 0 ? Math.round(memUsed / memMax * 100) : 0;
    el('oml-mem-pct').textContent = memPct + '%';
    el('oml-mem-bar').style.width = Math.min(100, memPct) + '%';
    // Tokens
    const fmt = v => v >= 1000000 ? (v/1000000).toFixed(1)+'M' : v >= 1000 ? (v/1000).toFixed(1)+'K' : v;
    el('oml-prompt-tok').textContent = fmt(d.total_prompt_tokens || 0);
    el('oml-completion-tok').textContent = fmt(d.total_completion_tokens || 0);
    // Tasks
    el('oml-active-req').textContent = d.active_requests || 0;
    el('oml-waiting-req').textContent = d.waiting_requests || 0;
    // fetchModels must be awaited to prevent race with next poll cycle
    await fetchModels();
  } catch(e) { console.warn('oml fetch error', e); }
}
async function fetchModels() {
  try {
    const r = await fetch('/oml/models');
    if (!r.ok) return;
    const resp = await r.json();
    const models = resp.models || [];
    const list = el('oml-models-list');
    if (!Array.isArray(models)) return;
    const fmtBytes = b => {
      if (!b) return '--';
      if (b >= 1e12) return (b/1e12).toFixed(1)+'TB';
      if (b >= 1e9) return (b/1e9).toFixed(1)+'GB';
      return (b/1e6).toFixed(0)+'MB';
    };
    list.innerHTML = models.map(m => {
      const name = (m.id || '').split('/').pop();
      const isLoading = m.is_loading;
      const isLoaded = m.loaded;
      const isError = !isLoaded && !isLoading;
      const state = isLoading ? 'loading' : isLoaded ? 'loaded' : 'idle';
      const stateColor = isLoaded ? '#48bb78' : isLoading ? '#ed8936' : isError ? '#fc8181' : '#a0aec0';
      const memSize = fmtBytes(m.estimated_size) || '--';
      return '<div style="padding:8px 10px;background:#f7fafc;border-radius:7px;border-left:3px solid ' + stateColor + ';">' +
        '<div style="font-size:12px;font-weight:700;color:#2d3748;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + name + '">' + name + '</div>' +
        '<div style="font-size:9px;color:#718096;margin-top:2px;">' + state + ' &middot; ' + memSize + '</div>' +
        '</div>';
    }).join('');
  } catch(e) { console.warn('models fetch error', e); }
}

// OpenClaw fetch (called by pollAll) - concurrent with AbortController timeout
// OpenClaw CLI commands are slow (~3-7s), use 8s timeout per request
async function fetchOpenClaw() {
  try {
    const withTimeout = (url, ms) => {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), ms);
      return fetch(url, { signal: ctrl.signal })
        .then(r => { clearTimeout(t); return r.ok ? r.json() : null; })
        .catch(() => { clearTimeout(t); return null; });
    };
    const [st, hl, ag, ss] = await Promise.all([
      withTimeout('/openclaw/status', 8000),
      withTimeout('/openclaw/health', 8000),
      withTimeout('/openclaw/agents', 10000),
      withTimeout('/openclaw/sessions', 12000),
    ]);

    if (!st) return;

    // Gateway card
    el('oc-version').textContent = st.runtimeVersion || '--';
    // uptime is in seconds from the status API
    const uptimeSec = st.uptime;
    el('oc-uptime').textContent = uptimeSec != null ? (uptimeSec >= 3600 ? Math.round(uptimeSec/3600) + 'h' : uptimeSec >= 60 ? Math.round(uptimeSec/60) + 'm' : uptimeSec + 's') : '--';

    // Tasks card
    const tk = st.tasks || {};
    el('oc-task-total').textContent = tk.total || 0;
    el('oc-task-active').textContent = tk.active || 0;
    const succ = tk.byStatus?.succeeded || 0;
    const fail = tk.byStatus?.failed || 0;
    const timed = tk.byStatus?.timed_out || 0;
    el('oc-task-succeeded').textContent = succ;
    el('oc-task-failed').textContent = fail;
    el('oc-task-timedout').textContent = timed;
    el('oc-task-cli').textContent = tk.byRuntime?.cli || 0;
    el('oc-task-cron').textContent = tk.byRuntime?.cron || 0;
    const taskPct = tk.total > 0 ? Math.round((succ + fail + timed) / tk.total * 100) : 0;
    el('oc-task-pct').textContent = taskPct + '%';
    el('oc-task-bar').style.width = taskPct + '%';

    // Telegram card
    if (hl) {
      const tg = hl.channels?.telegram;
      el('oc-tg-status').textContent = (tg?.running ? 'ON' : 'OFF');
      el('oc-tg-status').style.color = tg?.running ? '#48bb78' : '#fc8181';
      el('oc-tg-bot').textContent = tg?.probe?.bot?.username || '--';
      const channels = (st.channelSummary || []).filter(c => c.includes('configured')).length;
      el('oc-tg-channels').textContent = channels + ' configured';
    }

    // Sessions card
    if (ss) {
      el('oc-sess-count').textContent = ss.count || 0;
      el('oc-sess-minutes').textContent = ss.activeMinutes != null ? ss.activeMinutes + 'm' : '--';
      const agentIds = [...new Set((ss.sessions || []).map(s => s.agentId))];
      el('oc-sess-agents').textContent = agentIds.length || '--';
    }

    // Agents list
    if (ag && Array.isArray(ag)) {
      const list = el('oc-agents-list');
      list.innerHTML = ag.map(a => {
        const sched = (st.heartbeat?.agents || []).find(h => h.agentId === a.id);
        const schedStr = sched?.enabled ? sched.every : 'disabled';
        const schedColor = sched?.enabled ? '#ed8936' : '#a0aec0';
        const route = (a.routes || [])[0] || '--';
        return '<div style="padding:8px 10px;background:#f7fafc;border-radius:7px;border-left:3px solid #ed8936;">' +
          '<div style="font-size:13px;font-weight:700;color:#2d3748;">' + (a.name || a.id) + '</div>' +
          '<div style="font-size:9px;color:#718096;margin-top:2px;">' + (a.model || '--').split('/').pop() + ' · ' + route + '</div>' +
          '<div style="font-size:9px;color:' + schedColor + ';margin-top:2px;">⏱ ' + schedStr + '</div>' +
          '</div>';
      }).join('');
    }
  } catch(e) { console.warn('openclaw fetch error', e); }
}

// Tab switching — single registration (no separate timers, all polling is global)


// Global polling timer (SYSTEM + oMLX only)
let fetchTimer = null;
let paused = false;
function startTimer() {
  if (fetchTimer) clearInterval(fetchTimer);
  fetchTimer = setInterval(pollSystemAndOmlx, UPDATE_INTERVAL * 1000);
}
function restartTimer() {
  startTimer();
  pollSystemAndOmlx();
}
startTimer();
pollSystemAndOmlx();
// Start OpenClaw independent timer (10s fixed)
startOpenClawTimer();
fetchOpenClaw(); // immediate first fetch

// Page Visibility API - pause all polling when hidden
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    paused = true;
    if (fetchTimer) clearInterval(fetchTimer);
    fetchTimer = null;
    if (ocPollTimer) { clearInterval(ocPollTimer); ocPollTimer = null; }
  } else {
    paused = false;
    startTimer();
    startOpenClawTimer();
  }
});

// Interval slider
const slider = el('int-slider');
slider.addEventListener('input', function() {
  const v = parseInt(this.value);
  UPDATE_INTERVAL = v;
  el('int-val').textContent = v + 's';
  el('footer-interval').textContent = v;
  startTimer();
  fetch('/api/interval?val=' + v).catch(() => {});
});
</script>
</body>
</html>
"""

# ─── Python Server ────────────────────────────────────────────────────────────

latest_data = None
latest_lock = threading.Lock()
collector_interval = [8.0]

# HTTP handler 专用的网络 IO 跟踪器（与 collector 分离）
_http_last_net_io = None
_http_last_io_time = 0
_http_net_lock = threading.Lock()


def get_http_network_io() -> dict:
    """HTTP handler 专用的网络 IO 计算（线程安全）"""
    global _http_last_net_io, _http_last_io_time
    import psutil
    import time

    n = psutil.net_io_counters()
    now = time.time()

    with _http_net_lock:
        if _http_last_net_io is not None:
            dt = now - _http_last_io_time
            if dt >= 0.1:
                recv_mb = (n.bytes_recv - _http_last_net_io.bytes_recv) / dt / (1024**2)
                sent_mb = (n.bytes_sent - _http_last_net_io.bytes_sent) / dt / (1024**2)
                _http_last_net_io = n
                _http_last_io_time = now
                return {"recv_mb_s": max(0, round(recv_mb, 2)), "sent_mb_s": max(0, round(sent_mb, 2))}
            # dt 太小，不计算但更新时间戳
            _http_last_io_time = now
            return {"recv_mb_s": 0, "sent_mb_s": 0}
        _http_last_net_io = n
        _http_last_io_time = now
        return {"recv_mb_s": 0, "sent_mb_s": 0}


# Global snapshot function set by run()
take_snapshot = None
_macmon_start = None
_macmon_stop = None

# Request tracking for adaptive collection
_last_request_time = time.time()
_request_lock = threading.Lock()
_collection_stale = True  # True = need to collect on next request

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        global latest_data, take_snapshot, _last_request_time, _request_lock

        # Track request for adaptive collection
        with _request_lock:
            _last_request_time = time.time()

        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))

        elif self.path.startswith("/json"):
            # Always sample fresh data directly (bypasses collector interval)
            _ts = take_snapshot
            if _ts is None:
                self.send_error(503, "Collector not ready")
                return
            try:
                snap = _ts()
                pi = snap.power_info
                data = {
                    "timestamp": snap.timestamp,
                    "memory": {
                        "percent": snap.memory_percent,
                        "used_gb": snap.memory_used_gb,
                        "total_gb": snap.memory_total_gb,
                        "pressure": snap.memory_pressure_level,
                        "free_percent": snap.memory_free_percent,
                        "swap_used_gb": snap.swap_used_gb,
                        "swap_total_gb": snap.swap_total_gb,
                    },
                    "cpu": {
                        "percent": snap.cpu_percent,
                        "user": snap.cpu_user,
                        "system": snap.cpu_system,
                        "idle": snap.cpu_idle,
                        "cores": snap.cpu_cores,
                        "per_core": snap.cpu_per_core,
                    },
                    "power": {
                        "all_power_w": pi.get("all_power_w", 0) if pi else 0,
                        "sys_power_w": pi.get("sys_power_w", 0) if pi else 0,
                        "cpu_power_w": pi.get("cpu_power_w", 0) if pi else 0,
                        "gpu_power_w": pi.get("gpu_power_w", 0) if pi else 0,
                        "ram_power_w": pi.get("ram_power_w", 0) if pi else 0,
                        "ane_power_w": pi.get("ane_power_w", 0) if pi else 0,
                        "cpu_temp_c": pi.get("cpu_temp_c", 0) if pi else 0,
                        "gpu_temp_c": pi.get("gpu_temp_c", 0) if pi else 0,
                        "cpu_usage_pct": pi.get("cpu_usage_pct", 0) if pi else 0,
                        "gpu_usage_pct": pi.get("gpu_usage_pct", 0) if pi else 0,
                        "gpu_usage": pi.get("gpu_usage", []) if pi else [],
                        "source": pi.get("source", "") if pi else "",
                    },
                    "disk": {
                        "percent": snap.disk_percent,
                        "used_gb": snap.disk_used_gb,
                        "total_gb": snap.disk_total_gb,
                        "read_mb_s": snap.disk_read_mb_s,
                        "write_mb_s": snap.disk_write_mb_s,
                    },
                    "network": get_http_network_io(),
                }
            except Exception as e:
                self.send_error(500, str(e))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        elif self.path.startswith("/oml/models"):
            # Proxy to oMLX /v1/models/status (check BEFORE /oml)
            try:
                import urllib.request
                req = urllib.request.Request(
                    "http://localhost:8000/v1/models/status",
                    headers={"Authorization": "Bearer oMLX"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp.read())
            except Exception as e:
                self.send_error(502, str(e))
            return

        elif self.path.startswith("/oml"):
            # Proxy to oMLX API (avoids CORS)
            try:
                import urllib.request
                req = urllib.request.Request(
                    "http://localhost:8000/api/status",
                    headers={"Authorization": "Bearer oMLX"}
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp.read())
            except Exception as e:
                self.send_error(502, str(e))
            return

        elif self.path.startswith("/openclaw/status"):
            # Proxy: openclaw gateway call status --json
            try:
                import subprocess
                r = subprocess.run(['openclaw', 'gateway', 'call', 'status', '--json'],
                                   capture_output=True, timeout=10)
                out = r.stdout.decode().strip()
                # Try parse; if empty/wrap, use raw
                try:
                    data = json.loads(out)
                    body = json.dumps(data).encode()
                except:
                    body = json.dumps({"raw": out}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(502, str(e))
            return

        elif self.path.startswith("/openclaw/health"):
            # Proxy: openclaw gateway call health --json
            try:
                import subprocess
                r = subprocess.run(['openclaw', 'gateway', 'call', 'health', '--json'],
                                   capture_output=True, timeout=10)
                out = r.stdout.decode().strip()
                try:
                    data = json.loads(out)
                    body = json.dumps(data).encode()
                except:
                    body = json.dumps({"raw": out}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(502, str(e))
            return

        elif self.path.startswith("/openclaw/agents"):
            # Proxy: openclaw agents list --json
            try:
                import subprocess
                r = subprocess.run(['openclaw', 'agents', 'list', '--json'],
                                   capture_output=True, timeout=10)
                out = r.stdout.decode().strip()
                try:
                    data = json.loads(out)
                    body = json.dumps(data).encode()
                except:
                    body = json.dumps({"raw": out}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(502, str(e))
            return

        elif self.path.startswith("/openclaw/sessions"):
            # Proxy: openclaw sessions --all-agents --json
            # NOTE: this CLI command can take ~7s to respond
            try:
                import subprocess
                r = subprocess.run(['openclaw', 'sessions', '--all-agents', '--json'],
                                   capture_output=True, timeout=30)
                out = r.stdout.decode().strip()
                try:
                    data = json.loads(out)
                    body = json.dumps(data).encode()
                except:
                    body = json.dumps({"raw": out}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(502, str(e))
            return

        elif self.path.startswith("/metrics"):
            _ts = take_snapshot
            if _ts is None:
                self.send_error(503)
                return
            try:
                snap = _ts()
                pi = snap.power_info or {}
                lines = [
                    f"system_memory_percent {snap.memory_percent}",
                    f"system_cpu_percent {snap.cpu_percent}",
                    f"system_power_watts {(pi.get('all_power_w') or 0) + (pi.get('sys_power_w') or 0)}",
                    f"system_cpu_temp_celsius {pi.get('cpu_temp_c') or 0}",
                    f"system_gpu_temp_celsius {pi.get('gpu_temp_c') or 0}",
                    f"system_gpu_usage_percent {pi.get('gpu_usage_pct') or 0}",
                ]
                body = "\n".join(lines).encode()
            except Exception as e:
                self.send_error(500, str(e))
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)

        elif self.path.startswith("/api/interval"):
            import urllib.parse
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                v = float(params.get('val', [8])[0])
                collector_interval[0] = max(1.0, min(v, 30.0))
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")
            except Exception:
                self.send_error(400)
            return

        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


class QuietTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def run(host="127.0.0.1", port=8001, interval=8.0):
    global take_snapshot, _macmon_start, _macmon_stop
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, script_dir)

    print("Starting macmon...")
    try:
        from system_monitor import take_snapshot as _ts, _macmon_start as _ms, _macmon_stop as _mst
        take_snapshot, _macmon_start, _macmon_stop = _ts, _ms, _mst
        _macmon_start()
    except Exception as e:
        print(f"Warning: could not start system_monitor: {e}")
        take_snapshot = _macmon_start = _macmon_stop = None

    def collector():
        global latest_data, _last_request_time
        idle_threshold = 300  # 5 minutes idle before collector skips snapshot
        while True:
            try:
                # Check if there were recent requests
                with _request_lock:
                    idle = (time.time() - _last_request_time) > idle_threshold

                if idle:
                    time.sleep(collector_interval[0])
                    continue

                if take_snapshot:
                    snap = take_snapshot()
                    pi = snap.power_info
                    d = {
                        "timestamp": snap.timestamp,
                        "memory": {
                            "percent": snap.memory_percent,
                            "used_gb": snap.memory_used_gb,
                            "total_gb": snap.memory_total_gb,
                            "pressure": snap.memory_pressure_level,
                            "free_percent": snap.memory_free_percent,
                            "swap_used_gb": snap.swap_used_gb,
                            "swap_total_gb": snap.swap_total_gb,
                        },
                        "cpu": {
                            "percent": snap.cpu_percent,
                            "user": snap.cpu_user,
                            "system": snap.cpu_system,
                            "idle": snap.cpu_idle,
                            "cores": snap.cpu_cores,
                            "per_core": snap.cpu_per_core,
                        },
                        "power": pi,
                        "disk": {
                            "read_mb_s": snap.disk_read_mb_s,
                            "write_mb_s": snap.disk_write_mb_s,
                            "total_gb": snap.disk_total_gb,
                            "used_gb": snap.disk_used_gb,
                            "free_gb": snap.disk_free_gb,
                            "percent": snap.disk_percent,
                        },
                        "network": {
                            "recv_mb_s": snap.net_recv_mb_s,
                            "sent_mb_s": snap.net_sent_mb_s,
                        },
                    }
                    with latest_lock:
                        latest_data = d
            except Exception as e:
                print(f"Collector error: {e}")
            time.sleep(collector_interval[0])

    t = threading.Thread(target=collector, daemon=True)
    t.start()

    with QuietTCPServer((host, port), Handler) as httpd:
        print(f"")
        print(f"  Dashboard : http://localhost:{port}/")
        print(f"  LAN access: http://{host}:{port}/")
        print(f"  JSON API  : http://localhost:{port}/json")
        print(f"  Prometheus: http://localhost:{port}/metrics")
        print(f"  Health    : http://localhost:{port}/health")
        print(f"  Interval  : {interval}s")
        print(f"")
        print(f"Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            try:
                _macmon_stop()
            except Exception:
                pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0", help="绑定地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--interval", type=float, default=8.0)
    args = parser.parse_args()
    run(host=args.host, port=args.port, interval=args.interval)
