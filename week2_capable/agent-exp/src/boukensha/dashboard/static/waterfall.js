const _steps = [];
let _startTime = null;

window.addWaterfallEvent = function addWaterfallEvent(event) {
  const now = Date.now();
  if (!_startTime) _startTime = now;
  const elapsed = now - _startTime;

  if (event.phase === 'iteration') {
    _steps.push({ label: 'Iter ' + event.n, start: elapsed, end: null, type: 'iteration' });
  } else if (event.phase === 'tool_call') {
    _steps.push({ label: event.name, start: elapsed, end: null, type: 'tool' });
  } else if (event.phase === 'tool_result' || event.phase === 'response') {
    const last = _steps.findLast(s => s.end === null);
    if (last) last.end = elapsed;
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

  container.innerHTML = `<svg width="${labelW + svgW}" height="${svgH}" style="display:block">` +
    _steps.map((s, i) => {
      const y = i * rowH + pad;
      const x = s.start * scale;
      const w = Math.max(4, ((s.end || maxTime) - s.start) * scale);
      const fill = s.type === 'tool' ? '#4af' : '#fa4';
      const dur = s.end ? (s.end - s.start) + 'ms' : '…';
      return `<text x="2" y="${y + 16}" fill="#888" font-size="12" font-family="monospace">${s.label}</text>` +
        `<rect x="${labelW + x}" y="${y}" width="${w}" height="${rowH - 8}" fill="${fill}" rx="3" opacity="0.8"/>` +
        `<text x="${labelW + x + w + 4}" y="${y + 14}" fill="#666" font-size="11">${dur}</text>`;
    }).join('') + '</svg>';
}
