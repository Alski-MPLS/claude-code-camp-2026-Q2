const _steps = [];
let _startTime = null;
let _selectedIdx = null;

// Each step: { label, start, end, type, startAt, endAt, args, result, inputTokens, outputTokens }

window.addWaterfallEvent = function addWaterfallEvent(event) {
  const now = Date.now();
  if (!_startTime) _startTime = now;
  const elapsed = now - _startTime;

  if (event.phase === 'iteration') {
    _steps.push({
      label: 'Iter ' + event.n,
      start: elapsed, end: null,
      type: 'iteration',
      startAt: event.at || null, endAt: null,
      args: null, result: null,
      inputTokens: null, outputTokens: null,
    });
  } else if (event.phase === 'tool_call') {
    _steps.push({
      label: event.name,
      start: elapsed, end: null,
      type: 'tool',
      startAt: event.at || null, endAt: null,
      args: event.args || null,
      result: null,
      inputTokens: null, outputTokens: null,
    });
  } else if (event.phase === 'tool_result') {
    const last = _steps.findLast(s => s.type === 'tool' && s.end === null);
    if (last) {
      last.end = elapsed;
      last.endAt = event.at || null;
      last.result = event.result || null;
    }
  } else if (event.phase === 'response') {
    // Close the current open step (tool or iteration)
    const last = _steps.findLast(s => s.end === null);
    if (last) {
      last.end = elapsed;
      last.endAt = event.at || null;
    }
    // Attach token counts to the most recent iteration step
    const iterStep = _steps.findLast(s => s.type === 'iteration');
    if (iterStep && event.usage) {
      iterStep.inputTokens = event.usage.input_tokens ?? null;
      iterStep.outputTokens = event.usage.output_tokens ?? null;
    }
  }
  renderWaterfall();
};

function renderWaterfall() {
  const container = document.getElementById('waterfall-container');
  if (!_steps.length) return;
  const maxTime = Math.max(..._steps.map(s => s.end || Date.now() - _startTime));
  const rowH = 28, pad = 4, labelW = 160;
  const svgW = Math.max(container.clientWidth - labelW, 400);
  const svgH = _steps.length * rowH + 20;
  const scale = svgW / (maxTime || 1);

  container.innerHTML = `<svg width="${labelW + svgW}" height="${svgH}" style="display:block;cursor:pointer">` +
    _steps.map((s, i) => {
      const y = i * rowH + pad;
      const x = s.start * scale;
      const w = Math.max(4, ((s.end || maxTime) - s.start) * scale);
      const fill = s.type === 'tool' ? '#4af' : '#fa4';
      const dur = s.end ? (s.end - s.start) + 'ms' : '…';
      const selected = i === _selectedIdx;
      const stroke = selected ? ' stroke="#fff" stroke-width="2"' : '';
      return `<g data-idx="${i}">` +
        `<text x="2" y="${y + 16}" fill="#888" font-size="12" font-family="monospace">${escapeHtml(s.label)}</text>` +
        `<rect x="${labelW + x}" y="${y}" width="${w}" height="${rowH - 8}" fill="${fill}" rx="3" opacity="0.8"${stroke}/>` +
        `<text x="${labelW + x + w + 4}" y="${y + 14}" fill="#666" font-size="11">${dur}</text>` +
        `</g>`;
    }).join('') + '</svg>';

  container.querySelector('svg').addEventListener('click', e => {
    const g = e.target.closest('g[data-idx]');
    if (!g) { clearDetail(); return; }
    const idx = parseInt(g.dataset.idx, 10);
    _selectedIdx = idx;
    renderWaterfall();
    showDetail(_steps[idx]);
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function showDetail(step) {
  const panel = document.getElementById('waterfall-detail');
  panel.hidden = false;

  document.getElementById('waterfall-detail-title').textContent = step.label;

  // Timing
  const dur = step.end != null ? (step.end - step.start) + ' ms' : '(running…)';
  const startFmt = step.startAt ? new Date(step.startAt).toLocaleTimeString() : '—';
  const endFmt = step.endAt ? new Date(step.endAt).toLocaleTimeString() : '—';
  document.getElementById('wf-timing').textContent =
    `start: ${startFmt}  end: ${endFmt}  duration: ${dur}`;

  // Tokens
  const inp = step.inputTokens != null ? step.inputTokens : '—';
  const out = step.outputTokens != null ? step.outputTokens : '—';
  document.getElementById('wf-tokens').textContent = `input: ${inp}  output: ${out}`;

  // Args
  document.getElementById('wf-args').textContent =
    step.args != null ? JSON.stringify(step.args, null, 2) : '(no args)';

  // Result
  document.getElementById('wf-result').textContent =
    step.result != null ? step.result : '(no result)';
}

function clearDetail() {
  _selectedIdx = null;
  document.getElementById('waterfall-detail').hidden = true;
  renderWaterfall();
}
