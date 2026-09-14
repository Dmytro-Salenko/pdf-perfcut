'use strict';

const dropZone   = document.getElementById('drop-zone');
const fileInput  = document.getElementById('file-input');
const statusEl   = document.getElementById('status');

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
  const file = e.dataTransfer.files[0];
  if (file) processFile(file);
});

// ---- Click / keyboard ----
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) processFile(fileInput.files[0]);
});
dropZone.addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') fileInput.click();
});

// ---- Core ----
async function processFile(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showError('Please select a PDF file.');
    return;
  }

  showProcessing(file.name);
  dropZone.classList.add('processing');

  const form = new FormData();
  form.append('file', file);

  try {
    const res = await fetch('/api/convert', { method: 'POST', body: form });

    if (!res.ok) {
      let detail = `Server error ${res.status}`;
      try {
        const body = await res.json();
        if (body.detail) detail = body.detail;
      } catch (_) {}
      throw new Error(detail);
    }

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const outName = file.name.replace(/\.pdf$/i, '_perfcut.pdf');
    showSuccess(url, outName);

  } catch (err) {
    showError(err.message || 'Unknown error.');
  } finally {
    dropZone.classList.remove('processing');
    fileInput.value = '';
  }
}

function showProcessing(name) {
  statusEl.innerHTML = `
    <div class="status-msg processing">
      <span class="spinner"></span>
      Processing <strong>${esc(name)}</strong>…
    </div>`;
}

function showSuccess(url, filename) {
  statusEl.innerHTML = `
    <div class="status-msg success">
      <div>
        <div>✓ Done — PerfCutContour added.</div>
        <a class="download-btn" href="${url}" download="${esc(filename)}">
          ↓ Download PDF
        </a>
      </div>
    </div>`;
}

function showError(msg) {
  statusEl.innerHTML = `
    <div class="status-msg error">
      ✗ ${esc(msg)}
    </div>`;
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
