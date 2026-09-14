'use strict';

const dropZone  = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const statusEl  = document.getElementById('status');

// ---- Drag events ----
dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
['dragleave', 'dragend'].forEach(evt =>
  dropZone.addEventListener(evt, () => dropZone.classList.remove('drag-over'))
);
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const files = [...e.dataTransfer.files].filter(f => f.name.toLowerCase().endsWith('.pdf'));
  if (files.length) processFiles(files);
  else showError('Please drop PDF files.');
});

fileInput.addEventListener('change', () => {
  const files = [...fileInput.files].filter(f => f.name.toLowerCase().endsWith('.pdf'));
  if (files.length) processFiles(files);
});

dropZone.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') fileInput.click();
});

// ---- Core ----
async function processFiles(files) {
  dropZone.classList.add('processing');

  if (files.length === 1) {
    await processSingle(files[0]);
  } else {
    await processBatch(files);
  }

  dropZone.classList.remove('processing');
  fileInput.value = '';
}

async function processSingle(file) {
  showProcessing(`Processing ${esc(file.name)}…`);
  const form = new FormData();
  form.append('file', file);

  try {
    const res = await fetch('/api/convert', { method: 'POST', body: form });
    if (!res.ok) throw new Error(await extractDetail(res));
    const blob = await res.blob();
    const outName = file.name.replace(/\.pdf$/i, '_perfcut.pdf');
    showSuccess(URL.createObjectURL(blob), outName, '1 file processed.');
  } catch (err) {
    showError(err.message);
  }
}

async function processBatch(files) {
  showProcessing(`Processing ${files.length} files…`);
  const form = new FormData();
  files.forEach(f => form.append('files', f));

  try {
    const res = await fetch('/api/convert-batch', { method: 'POST', body: form });
    if (!res.ok) throw new Error(await extractDetail(res));

    const blob = await res.blob();
    // Peek at errors.txt count via a second read of the zip isn't possible client-side,
    // so we just show the download and let the user inspect errors.txt if present.
    const total = files.length;
    showSuccess(URL.createObjectURL(blob), 'results.zip',
      `${total} file${total !== 1 ? 's' : ''} submitted — see results.zip (includes errors.txt if any failed).`);
  } catch (err) {
    showError(err.message);
  }
}

// ---- UI helpers ----
function showProcessing(msg) {
  statusEl.innerHTML = `
    <div class="status-msg processing">
      <span class="spinner"></span>
      ${msg}
    </div>`;
}

function showSuccess(url, filename, summary) {
  statusEl.innerHTML = `
    <div class="status-msg success">
      <div>
        <div>✓ ${esc(summary)}</div>
        <a class="download-btn" href="${url}" download="${esc(filename)}">↓ Download ${esc(filename)}</a>
      </div>
    </div>`;
}

function showError(msg) {
  statusEl.innerHTML = `<div class="status-msg error">✗ ${esc(msg)}</div>`;
}

async function extractDetail(res) {
  try {
    const body = await res.json();
    return body.detail || `Server error ${res.status}`;
  } catch (_) {
    return `Server error ${res.status}`;
  }
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
