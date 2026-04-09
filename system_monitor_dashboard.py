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
    <!-- CPU -->
    <div class="card cpu">
      <div class="card-title">CPU</div>
      <div class="big-val" id="cpu-pct">--<span class="big-unit">%</span></div>
      <div class="bar-bg"><div class="bar-fill cpu" id="cpu-bar" style="width:0%"></div></div>
    </div>

    <!-- GPU (独立卡片) -->
    <div class="card" style="border-left:3px solid var(--power);">
      <div class="card-title" style="color:var(--power);">GPU</div>
      <div class="big-val" id="gpu-pct" style="color:var(--power);">--<span class="big-unit">%</span></div>
      <div class="bar-bg"><div class="bar-fill" id="gpu-bar" style="width:0%;background:var(--power)"></div></div>
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
      <div class="sub-text">SoC + System</div>
      <div class="power-row">
        <div class="power-label">SoC</div>
        <div class="power-bar-bg"><div class="power-bar-fill" id="pw-soc-bar" style="width:0%"></div></div>
        <div class="power-val" id="pw-soc-val">--</div>
      </div>
      <div class="power-row">
        <div class="power-label">SYS</div>
        <div class="power-bar-bg"><div class="power-bar-fill" id="pw-sys-bar" style="width:0%"></div></div>
        <div class="power-val" id="pw-sys-val">--</div>
      </div>
      <div class="power-row" style="margin-top:4px;border-top:1px solid var(--border);padding-top:6px;">
        <div class="power-label" style="font-weight:700;">Total</div>
        <div class="power-bar-bg"><div class="power-bar-fill" id="pw-total-bar" style="width:0%;background:#2d3748;"></div></div>
        <div class="power-val" id="pw-total-disp" style="font-weight:800;">--</div>
      </div>
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
          <div class="spark-title">CPU %</div>
          <canvas class="spark-canvas" id="spark-cpu" width="320" height="70"></canvas>
        </div>

        <div class="spark-item">
          <div class="spark-title">Power W</div>
          <canvas class="spark-canvas" id="spark-pw" width="320" height="70"></canvas>
        </div>
        <div class="spark-item">
          <div class="spark-title">CPU °C</div>
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
  <div class="placeholder">oMLX 监控面板 — 待接入</div>
</div>

<!-- OPENCLAW -->
<div id="tab-openclaw" class="tab-panel">
  <div class="placeholder">OpenClaw 状态面板 — 待接入</div>
</div>

<footer>Auto-refresh 8s &nbsp;·&nbsp; Source: macmon &nbsp;·&nbsp; <span class="live-dot"></span>Live</footer>

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

  // Draw each series
  series.forEach(({ data, color }) => {
    if (!data || data.length < 2) return;
    const step = plotW / (data.length - 1);

    // Gradient fill
    const grad = ctx.createLinearGradient(0, PAD_TOP, 0, PAD_TOP + plotH);
    grad.addColorStop(0, color + '44'); grad.addColorStop(1, color + '00');

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

  // CPU
  // CPU + GPU (from power_info)
  const gpuPct = (pw && pw.gpu_usage_pct != null) ? pw.gpu_usage_pct : 0;
  el('cpu-pct').innerHTML = round(cpu.percent, 0) + '<span class="big-unit">%</span>';
  el('cpu-bar').style.width = Math.min(100, cpu.percent) + '%';
  el('gpu-pct').innerHTML = gpuPct > 0 ? round(gpuPct, 0) + '<span class="big-unit">%</span>' : '--<span class="big-unit">%</span>';
  el('gpu-bar').style.width = Math.min(100, gpuPct) + '%';

  // Power
  const socPw = (pw && pw.all_power_w) || 0;
  const sysPw = (pw && pw.sys_power_w) || 0;
  const totalPw = socPw + sysPw;
  el('pw-total').innerHTML = totalPw > 0 ? round(totalPw, 2) + '<span class="big-unit">W</span>' : '--<span class="big-unit">W</span>';
  el('pw-total-disp').textContent = totalPw > 0 ? round(totalPw, 2) + 'W' : '--';
  const maxPw = 15;
  [['soc', socPw, '#ed8936'], ['sys', sysPw, '#9f7aea']].forEach(([k, v, c]) => {
    const bar = el('pw-' + k + '-bar'), val = el('pw-' + k + '-val');
    val.textContent = v > 0 ? round(v, 2) + 'W' : '--';
    bar.style.width = Math.min(100, (v / maxPw) * 100) + '%';
    bar.style.background = c;
  });
  el('pw-total-bar').style.width = Math.min(100, (totalPw / maxPw) * 100) + '%';

  // Temperature
  const cpuT = (pw && pw.cpu_temp_c) || 0;
  const gpuT = (pw && pw.gpu_temp_c) || 0;
  const mkTemp = (id, val) => el(id).innerHTML = val > 0 ? round(val, 0) + '<span style="font-size:13px;font-weight:400;color:var(--text-muted)">°C</span>' : '--<span style="font-size:13px;font-weight:400;color:var(--text-muted)">°C</span>';
  mkTemp('temp-cpu', cpuT); mkTemp('temp-gpu', gpuT);
  el('temp-cpu-bar').style.width = Math.min(100, cpuT) + '%';
  el('temp-gpu-bar').style.width = Math.min(100, gpuT) + '%';

  // Disk
  const diskPct = disk.percent || 0;
  el('disk-pct').innerHTML = round(diskPct, 0) + '<span class="big-unit">%</span>';
  el('disk-detail').textContent = round(disk.used_gb, 0) + ' / ' + round(disk.total_gb, 0) + ' GB';
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
  history.power.push(totalPw > 0 ? totalPw : null);
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
    if (r.ok) updateUI(await r.json());
  } catch(e) { console.warn('fetch error', e); }
}
let fetchTimer = null;
function restartTimer() {
  if (fetchTimer) clearInterval(fetchTimer);
  fetchTimer = setInterval(fetchData, UPDATE_INTERVAL * 1000);
}
restartTimer();
fetchData();

// Interval slider
const slider = el('int-slider');
slider.addEventListener('input', function() {
  const v = parseInt(this.value);
  UPDATE_INTERVAL = v;
  el('int-val').textContent = v + 's';
  restartTimer();
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

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        global latest_data, take_snapshot

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
            except Exception:
                body = b""
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


class QuietTCPServer(socketserver.TCPServer):
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
        global latest_data
        while True:
            try:
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
    parser.add_argument("--host", type=str, default="127.0.0.1", help="绑定地址 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--interval", type=float, default=8.0)
    args = parser.parse_args()
    run(host=args.host, port=args.port, interval=args.interval)
