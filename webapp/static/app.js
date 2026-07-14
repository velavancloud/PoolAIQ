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

function renderResult(data) {
  reasoningEmpty.hidden = true;
  reasoningResult.hidden = false;
  approvalConfirm.hidden = true;
  approvalConfirm.className = 'approval-confirm';

  renderStrip(data.new_reading);

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

  const conf = rec.confidence || 0;
  confidenceFill.style.width = `${conf * 100}%`;
  confidenceValue.textContent = `${Math.round(conf * 100)}%`;

  approveBtn.onclick = () => showApprovalConfirm(true);
  rejectBtn.onclick = () => showApprovalConfirm(false);
}

function showApprovalConfirm(approved) {
  approvalConfirm.hidden = false;
  approvalConfirm.className = 'approval-confirm ' + (approved ? 'approved' : 'rejected');
  approvalConfirm.textContent = approved
    ? '✓ Approved — task would be created and a reminder scheduled per the notification_plan in api/task_schema.json.'
    : '✗ Rejected — no task created. In production this would prompt PoolAIQ to ask what\'s wrong with the recommendation.';
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
