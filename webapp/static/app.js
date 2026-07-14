// PoolAIQ demo frontend — no build step, vanilla JS by design (keeps the demo
// runnable with zero setup beyond `python3 app.py`).

const uploadZone = document.getElementById('uploadZone');
const photoInput = document.getElementById('photoInput');
const uploadInner = document.getElementById('uploadInner');
const previewImg = document.getElementById('previewImg');
const analyzeBtn = document.getElementById('analyzeBtn');

const stripEmpty = document.getElementById('stripEmpty');
const padRow = document.getElementById('padRow');

const reasoningEmpty = document.getElementById('reasoningEmpty');
const reasoningResult = document.getElementById('reasoningResult');
const contextLine = document.getElementById('contextLine');
const diagnosisText = document.getElementById('diagnosisText');
const rootCauseFlag = document.getElementById('rootCauseFlag');
const actionType = document.getElementById('actionType');
const actionInstructions = document.getElementById('actionInstructions');
const confidenceFill = document.getElementById('confidenceFill');
const confidenceValue = document.getElementById('confidenceValue');
const approveBtn = document.getElementById('approveBtn');
const rejectBtn = document.getElementById('rejectBtn');
const approvalConfirm = document.getElementById('approvalConfirm');

let selectedFile = null;

// ---------- Upload handling ----------

uploadZone.addEventListener('click', () => photoInput.click());
uploadZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') photoInput.click();
});
uploadZone.tabIndex = 0;

photoInput.addEventListener('change', (e) => {
  if (e.target.files[0]) handleFile(e.target.files[0]);
});

['dragover', 'dragenter'].forEach(evt =>
  uploadZone.addEventListener(evt, (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
  })
);
['dragleave', 'drop'].forEach(evt =>
  uploadZone.addEventListener(evt, (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
  })
);
uploadZone.addEventListener('drop', (e) => {
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

function handleFile(file) {
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    previewImg.src = e.target.result;
    previewImg.hidden = false;
    uploadInner.hidden = true;
  };
  reader.readAsDataURL(file);
  analyzeBtn.disabled = false;
  clearScenarioActive();
}

analyzeBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  setLoading(true);

  const formData = new FormData();
  formData.append('photo', selectedFile);

  try {
    const res = await fetch('/api/analyze', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.error) {
      renderError(data.error);
    } else {
      renderResult(data);
      if (data.persisted) {
        loadTrend();  // refresh the trend chart/table with the newly persisted reading
      }
    }
  } catch (err) {
    renderError('Could not reach the server: ' + err.message);
  }
  setLoading(false);
});

// ---------- Scenario replay ----------

document.querySelectorAll('.scenario-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    clearScenarioActive();
    btn.classList.add('active');
    setLoading(true);

    try {
      const res = await fetch('/api/analyze_demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: btn.dataset.scenario }),
      });
      const data = await res.json();
      renderResult(data);
    } catch (err) {
      renderError('Could not reach the server: ' + err.message);
    }
    setLoading(false);
  });
});

function clearScenarioActive() {
  document.querySelectorAll('.scenario-btn').forEach(b => b.classList.remove('active'));
}

// ---------- Rendering ----------

function setLoading(isLoading) {
  analyzeBtn.textContent = isLoading ? 'Analyzing…' : 'Analyze photo';
  analyzeBtn.disabled = isLoading || !selectedFile;
}

const IDEAL_RANGES = {
  free_chlorine_ppm: [1, 4],
  ph: [7.2, 7.8],
  total_alkalinity_ppm: [80, 120],
  cyanuric_acid_ppm: [50, 100],
  copper_ppm: [0, 0.2],
  phosphates_ppb: [0, 100],
  salt_ppm: [2700, 3400],
};

const LABELS = {
  free_chlorine_ppm: 'FCl',
  total_chlorine_ppm: 'TCl',
  ph: 'pH',
  total_alkalinity_ppm: 'ALK',
  cyanuric_acid_ppm: 'CYA',
  copper_ppm: 'Cu',
  phosphates_ppb: 'PO4',
  salt_ppm: 'Salt',
};

function statusFor(field, value) {
  if (value === null || value === undefined) return 'unknown';
  const range = IDEAL_RANGES[field];
  if (!range) return 'ok';
  if (value < range[0]) return 'low';
  if (value > range[1]) return 'high';
  return 'ok';
}

function renderStrip(reading) {
  stripEmpty.hidden = true;
  padRow.hidden = false;
  padRow.innerHTML = '';

  Object.keys(LABELS).forEach((field, i) => {
    const value = reading[field];
    const status = statusFor(field, value);
    const cell = document.createElement('div');
    cell.className = 'pad-cell';
    cell.dataset.status = status;
    cell.style.animationDelay = `${i * 60}ms`;
    cell.innerHTML = `
      <span class="pad-label">${LABELS[field]}</span>
      <span class="pad-value">${value !== null && value !== undefined ? value : '—'}</span>
    `;
    padRow.appendChild(cell);
  });
}

const retrievalBlock = document.getElementById('retrievalBlock');
const citationList = document.getElementById('citationList');

function renderCitations(citations) {
  if (!citations || citations.length === 0) {
    retrievalBlock.hidden = true;
    return;
  }
  retrievalBlock.hidden = false;
  citationList.innerHTML = '';

  citations.forEach(raw => {
    // format: "KB[id] (score=0.24): text..." or "HISTORY[date] (score=0.11): text..."
    const isKB = raw.startsWith('KB[');
    const match = raw.match(/^(KB|HISTORY)\[(.+?)\]\s*\(score=([\d.]+)\):\s*(.+)$/);
    const item = document.createElement('div');
    item.className = 'citation-item';

    if (match) {
      const [, source, ref, score, text] = match;
      item.innerHTML = `
        <span class="citation-source ${isKB ? 'kb' : 'history'}">${isKB ? 'knowledge base' : 'this pool'}</span>
        <span class="citation-text">${text}<span class="citation-score">match ${Math.round(parseFloat(score) * 100)}%</span></span>
      `;
    } else {
      item.innerHTML = `<span class="citation-text">${raw}</span>`;
    }
    citationList.appendChild(item);
  });
}

function renderResult(data) {
  reasoningEmpty.hidden = true;
  reasoningResult.hidden = false;
  approvalConfirm.hidden = true;
  approvalConfirm.className = 'approval-confirm';

  renderStrip(data.new_reading);
  renderCitations(data.recommendation.retrieved_context_used);

  contextLine.textContent =
    `Reasoned over ${data.history_length_used} historical readings for this pool ` +
    `(not just this one) — extraction confidence: ${
      data.extraction && data.extraction.extraction_confidence !== undefined
        ? Math.round(data.extraction.extraction_confidence * 100) + '%'
        : 'n/a (replay)'
    }`;

  const rec = data.recommendation;
  diagnosisText.textContent = rec.diagnosis || '—';

  if (rec.root_cause_vs_symptom === 'root_cause') {
    rootCauseFlag.hidden = false;
    rootCauseFlag.textContent = '⚠ Root-cause pattern detected — see diagnosis above. This is the exact kind of cross-visit pattern single-appointment retail advice cannot see.';
  } else if (rec.safety_gate_triggered) {
    rootCauseFlag.hidden = false;
    rootCauseFlag.textContent = '⛔ Hard safety rule triggered — no new chemical may be added until the active wait window clears.';
  } else {
    rootCauseFlag.hidden = true;
  }

  const action = rec.proposed_action || {};
  actionType.textContent = (action.type || 'unknown').replace(/_/g, ' ');
  actionInstructions.textContent = action.instructions || 'No specific instructions.';
  renderProductCard(action);

  const conf = rec.confidence || 0;
  confidenceFill.style.width = `${conf * 100}%`;
  confidenceValue.textContent = `${Math.round(conf * 100)}%`;

  approveBtn.onclick = () => handleApproval(true, action.instructions);
  rejectBtn.onclick = () => handleApproval(false, action.instructions);
}

async function handleApproval(approved, instructions) {
  if (!approved) {
    approvalConfirm.hidden = false;
    approvalConfirm.className = 'approval-confirm rejected';
    approvalConfirm.textContent = '✗ Rejected — no task created, no notification sent.';
    return;
  }

  approveBtn.disabled = true;
  approveBtn.textContent = 'Sending via MCP…';

  try {
    const res = await fetch('/api/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instructions, task_id: 'demo_task_' + Date.now() }),
    });
    const data = await res.json();
    approvalConfirm.hidden = false;
    approvalConfirm.className = 'approval-confirm approved';
    if (data.notification) {
      approvalConfirm.textContent =
        `✓ Approved — notification dispatched via MCP (send_task_notification). ` +
        `id: ${data.notification.notification_id}, sent: ${new Date(data.notification.sent_at).toLocaleTimeString()}`;
    } else {
      approvalConfirm.textContent = '✓ Approved, but notification dispatch had an issue: ' + (data.notification_error || 'unknown');
    }
  } catch (err) {
    approvalConfirm.hidden = false;
    approvalConfirm.className = 'approval-confirm rejected';
    approvalConfirm.textContent = '✗ Could not reach approval endpoint: ' + err.message;
  }

  approveBtn.disabled = false;
  approveBtn.textContent = 'Approve & create task';
}

const productCard = document.getElementById('productCard');

function renderProductCard(action) {
  const lookup = action.product_lookup;
  if (!lookup || !lookup.found || !lookup.products || lookup.products.length === 0) {
    productCard.hidden = true;
    return;
  }
  const p = lookup.products[0];
  productCard.hidden = false;
  productCard.innerHTML = `
    <div class="product-card-info">
      <span class="product-card-tag">via mcp: find_product</span>
      <span class="product-card-name">${p.name} — ${p.brand}</span>
      <span class="product-card-meta">${p.size} · SKU ${p.sku}</span>
    </div>
    <span class="product-card-price">$${p.price_usd.toFixed(2)}</span>
  `;
}

function renderError(message) {
  reasoningEmpty.hidden = true;
  reasoningResult.hidden = false;
  contextLine.textContent = 'Error';
  diagnosisText.textContent = message;
  rootCauseFlag.hidden = true;
  actionType.textContent = 'error';
  actionInstructions.textContent = 'Try the scenario replay buttons instead, which don\'t require a live API call.';
  confidenceFill.style.width = '0%';
  confidenceValue.textContent = '—';
}


// ---------- Multi-agent orchestration panel ----------

const agentTrace = document.getElementById('agentTrace');
const nodeExtraction = document.getElementById('nodeExtraction');
const nodeReasoning = document.getElementById('nodeReasoning');
const nodeSafety = document.getElementById('nodeSafety');
const nodeExtractionDetail = document.getElementById('nodeExtractionDetail');
const nodeReasoningDetail = document.getElementById('nodeReasoningDetail');
const nodeSafetyDetail = document.getElementById('nodeSafetyDetail');
const agentVerdictBlock = document.getElementById('agentVerdictBlock');
const agentVerdictText = document.getElementById('agentVerdictText');
const agentCheckedRules = document.getElementById('agentCheckedRules');
const verdictLabel = document.getElementById('verdictLabel');

async function runAgentScenario(scenario) {
  agentTrace.hidden = false;
  nodeExtraction.className = 'agent-node';
  nodeReasoning.className = 'agent-node';
  nodeSafety.className = 'agent-node';
  nodeExtractionDetail.textContent = 'Running…';
  nodeReasoningDetail.textContent = '';
  nodeSafetyDetail.textContent = '';
  agentVerdictBlock.className = 'agent-verdict-block';
  agentVerdictText.textContent = '';
  agentCheckedRules.innerHTML = '';

  try {
    const res = await fetch('/api/analyze_agents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario }),
    });
    const data = await res.json();
    renderAgentTrace(data);
  } catch (err) {
    nodeExtractionDetail.textContent = 'Error: ' + err.message;
  }
}

function renderAgentTrace(data) {
  const ext = data.extraction;
  const reasoning = data.reasoning;
  const safety = data.safety;
  const isVetoed = safety.verdict === 'vetoed';

  nodeExtractionDetail.textContent = ext
    ? `source: ${ext.source_type} · confidence ${Math.round(ext.extraction_confidence * 100)}%`
    : 'no extraction data';

  nodeReasoningDetail.textContent = `proposed: ${reasoning.proposed_action_type.replace(/_/g, ' ')}`;
  nodeReasoning.className = isVetoed ? 'agent-node vetoed-source' : 'agent-node';

  nodeSafetyDetail.textContent = isVetoed ? 'VETOED ⛔' : 'approved ✓';
  nodeSafety.className = isVetoed ? 'agent-node vetoed-source' : 'agent-node approved-terminal';

  agentVerdictBlock.className = 'agent-verdict-block ' + (isVetoed ? 'vetoed' : 'approved');
  verdictLabel.textContent = isVetoed ? 'Safety Agent VETO' : 'Safety Agent Approval';

  if (isVetoed) {
    agentVerdictText.innerHTML =
      `<strong>The Reasoning Agent's proposal was blocked before reaching a human.</strong><br><br>` +
      `Reasoning Agent proposed: <em>"${reasoning.instructions}"</em><br><br>` +
      `Safety Agent reason: ${safety.reason}<br><br>` +
      `Given to the human instead: <em>"${safety.safe_alternative_instructions}"</em>`;
  } else {
    agentVerdictText.innerHTML =
      `<strong>Reasoning Agent's proposal passed all safety checks and is forwarded for human approval.</strong><br><br>` +
      `${reasoning.instructions}`;
  }

  agentCheckedRules.innerHTML = '';
  (safety.checked_rules || []).forEach(rule => {
    const chip = document.createElement('span');
    const triggered = isVetoed && safety.reason.toLowerCase().includes(rule.split('_')[0]);
    chip.className = 'rule-chip' + (triggered ? ' triggered' : '');
    chip.textContent = rule.replace(/_/g, ' ');
    agentCheckedRules.appendChild(chip);
  });
}

document.getElementById('agentNormalBtn').addEventListener('click', () => runAgentScenario('normal'));
document.getElementById('agentVetoBtn').addEventListener('click', () => runAgentScenario('veto'));


// ---------- Trend chart + table (Section 04) ----------

const trendChart = document.getElementById('trendChart');
const trendTableBody = document.getElementById('trendTableBody');
const resetTrendBtn = document.getElementById('resetTrendBtn');
const trendMetricTabs = document.getElementById('trendMetricTabs');

let currentMetric = 'ph';
let trendData = null;

const METRIC_COLORS = {
  ph: '#2C7A7B',
  free_chlorine_ppm: '#C08A2E',
  total_alkalinity_ppm: '#D65A45',
  cyanuric_acid_ppm: '#7A9B76',
};

async function loadTrend() {
  try {
    const res = await fetch('/api/trend');
    trendData = await res.json();
    renderTrendChart();
    renderTrendTable();
  } catch (err) {
    console.error('Failed to load trend:', err);
  }
}

function renderTrendChart() {
  if (!trendData) return;
  const readings = trendData.readings.filter(r => r[currentMetric] !== null && r[currentMetric] !== undefined);
  if (readings.length === 0) {
    trendChart.innerHTML = '<text x="480" y="130" text-anchor="middle" fill="#5B6B66" font-size="13">No data for this metric yet.</text>';
    return;
  }

  const W = 960, H = 260, PAD = 40;
  const values = readings.map(r => r[currentMetric]);
  const range = trendData.ideal_ranges[currentMetric];

  let minV = Math.min(...values, range ? range[0] : Infinity);
  let maxV = Math.max(...values, range ? range[1] : -Infinity);
  const pad = (maxV - minV) * 0.15 || 1;
  minV -= pad; maxV += pad;

  const x = i => PAD + (i / Math.max(readings.length - 1, 1)) * (W - PAD * 2);
  const y = v => H - PAD - ((v - minV) / (maxV - minV)) * (H - PAD * 2);

  let svg = '';

  // ideal range band
  if (range) {
    svg += `<rect x="${PAD}" y="${y(range[1])}" width="${W - PAD * 2}" height="${y(range[0]) - y(range[1])}" fill="#7A9B76" opacity="0.12" />`;
    svg += `<text x="${W - PAD}" y="${y(range[1]) - 4}" text-anchor="end" font-size="10" fill="#7A9B76" font-family="JetBrains Mono, monospace">ideal ${range[0]}-${range[1]}</text>`;
  }

  // axis line
  svg += `<line x1="${PAD}" y1="${H - PAD}" x2="${W - PAD}" y2="${H - PAD}" stroke="#D9D4C6" stroke-width="1" />`;

  // line path
  const color = METRIC_COLORS[currentMetric] || '#1B4B4F';
  const points = readings.map((r, i) => `${x(i)},${y(r[currentMetric])}`).join(' ');
  svg += `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2.5" />`;

  // points, styled differently for newly-added readings
  readings.forEach((r, i) => {
    const isNew = r.is_new;
    svg += `<circle cx="${x(i)}" cy="${y(r[currentMetric])}" r="${isNew ? 6 : 4}" fill="${isNew ? '#D65A45' : color}" stroke="white" stroke-width="1.5" />`;
    if (i === 0 || i === readings.length - 1 || isNew) {
      const dateLabel = new Date(r.read_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      svg += `<text x="${x(i)}" y="${H - PAD + 16}" text-anchor="middle" font-size="9" fill="#5B6B66" font-family="JetBrains Mono, monospace">${dateLabel}</text>`;
    }
  });

  trendChart.innerHTML = svg;
}

function renderTrendTable() {
  if (!trendData) return;
  trendTableBody.innerHTML = '';
  // most recent first
  const rows = [...trendData.readings].reverse();
  rows.forEach(r => {
    const tr = document.createElement('tr');
    if (r.is_new) tr.className = 'trend-row-new';
    const date = new Date(r.read_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    const note = r.is_new
      ? (r.safety_verdict === 'vetoed' ? '⛔ vetoed' : '✓ new — ' + (r.diagnosis || '').slice(0, 60))
      : '';
    tr.innerHTML = `
      <td>${date}</td>
      <td>${r.source}${r.is_new ? ' <span class="new-badge">NEW</span>' : ''}</td>
      <td>${r.ph ?? '—'}</td>
      <td>${r.free_chlorine_ppm ?? '—'}</td>
      <td>${r.total_alkalinity_ppm ?? '—'}</td>
      <td>${r.cyanuric_acid_ppm ?? '—'}</td>
      <td class="trend-note">${note}</td>
    `;
    trendTableBody.appendChild(tr);
  });
}

trendMetricTabs.addEventListener('click', (e) => {
  const btn = e.target.closest('.metric-tab');
  if (!btn) return;
  document.querySelectorAll('.metric-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentMetric = btn.dataset.metric;
  renderTrendChart();
});

resetTrendBtn.addEventListener('click', async () => {
  if (!confirm('Reset all uploaded readings back to the original 7-reading case study? This cannot be undone.')) return;
  await fetch('/api/trend/reset', { method: 'POST' });
  loadTrend();
});

// Load the trend on page load so the chart isn't empty before any upload
loadTrend();
