function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Tab routing
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'overview') loadOverview();
    if (btn.dataset.tab === 'score') loadScore();
    if (btn.dataset.tab === 'map') window.loadMap && window.loadMap();
    if (btn.dataset.tab === 'goals') loadGoals();
    if (btn.dataset.tab === 'sessions') loadSessions();
  });
});

// SSE live feed
const log = document.getElementById('live-log');
const es = new EventSource('/events');
es.onmessage = e => {
  const event = JSON.parse(e.data);
  const div = document.createElement('div');
  div.className = 'phase-' + event.phase;
  if (event.phase === 'response') div.textContent = '[response] ' + event.text;
  else if (event.phase === 'tool_call') div.textContent = '[tool] → ' + event.name + '(' + JSON.stringify(event.args || {}) + ')';
  else if (event.phase === 'tool_result') div.textContent = '[result] ' + (event.result || '');
  else if (event.phase === 'compaction') div.textContent = '[compacted — ' + event.dropped + ' messages dropped]';
  else if (event.phase === 'iteration') div.textContent = '[iter ' + event.n + '/' + event.max + ']';
  else return;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;

  // Forward to waterfall
  window.addWaterfallEvent && window.addWaterfallEvent(event);

  // Refresh the map live while a move/navigation/room-lookup tool resolves,
  // but only if the Map tab is the one currently on screen.
  const MAP_REFRESH_TOOLS = new Set(['move', 'navigate_to', 'process_room']);
  if (event.phase === 'tool_result' && MAP_REFRESH_TOOLS.has(event.name)) {
    const mapTab = document.getElementById('tab-map');
    if (mapTab && mapTab.classList.contains('active')) {
      window.loadMap && window.loadMap();
    }
  }

  // Refresh the Score tab whenever a `check` call resolves (covers score,
  // but also harmless to refresh on inventory/equipment/etc. checks — the
  // underlying /api/players data only changes when it was actually a score
  // check, so a no-op refresh is cheap and simpler than inspecting args).
  if (event.phase === 'tool_result' && event.name === 'check') {
    const scoreTab = document.getElementById('tab-score');
    if (scoreTab && scoreTab.classList.contains('active')) {
      loadScore();
    }
  }
};

// Overview tab
async function loadOverview() {
  const r = await fetch('/api/overview');
  const data = await r.json();

  const grid = document.getElementById('overview-grid');
  grid.innerHTML = [
    ['Rooms known', data.rooms_known, null],
    ['Frontier', data.frontier.frontier, `of ${data.frontier.known_exits} exits · ${data.frontier.walked} mapped`],
    ['Entities', data.entities.total, `${data.entities.mobs} mobs · ${data.entities.objects} objects`],
  ].map(([label, value, sub]) =>
    `<div class="overview-card">
      <div class="overview-card-label">${escapeHtml(label)}</div>
      <div class="overview-card-value">${escapeHtml(String(value))}</div>
      ${sub ? `<div class="overview-card-sub">${escapeHtml(sub)}</div>` : ''}
    </div>`
  ).join('');

  const playersEl = document.getElementById('overview-players');
  if (!data.players.length) {
    playersEl.innerHTML = '<p class="overview-empty">No players tracked yet.</p>';
    return;
  }
  playersEl.innerHTML = data.players.map(p => {
    const stats = p.stats || {};
    const statLine = 'hp' in stats
      ? `${stats.hp}/${stats.max_hp} hp · ${stats.mana}/${stats.max_mana} mana · ${stats.move}/${stats.max_move} move`
      : 'stats not yet checked';
    const from = p.prev_room_hash ? ` — came from ${escapeHtml(p.prev_room_hash)}` : '';
    return `<div class="overview-card overview-player">
      <div class="overview-card-label">${escapeHtml(p.name)}</div>
      <div class="overview-card-value">${escapeHtml(statLine)}</div>
      <div class="overview-location">${escapeHtml(p.title || '')}${from}</div>
    </div>`;
  }).join('');
}

loadOverview();

// Score tab
function scoreBar(label, value, max, cls) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return `<div class="score-bar-row">
    <div class="score-bar-label"><span>${escapeHtml(label)}</span><span>${value}/${max}</span></div>
    <div class="score-bar-track"><div class="score-bar-fill ${cls}" style="width:${pct}%"></div></div>
  </div>`;
}

async function loadScore() {
  const el = document.getElementById('score-cards');
  const r = await fetch('/api/players');
  const players = await r.json();
  if (!players.length) {
    el.innerHTML = '<p class="overview-empty">No players tracked yet.</p>';
    return;
  }
  el.innerHTML = players.map(p => {
    const s = p.stats || {};
    if (!('hp' in s)) {
      return `<div class="score-card">
        <div class="score-card-header"><span class="score-card-name">${escapeHtml(p.name)}</span></div>
        <p class="overview-empty">Stats not yet checked (no score command run).</p>
      </div>`;
    }
    const levelPart = 'level' in s
      ? `Level ${s.level}${s.title ? ' — ' + escapeHtml(s.title) : ''}`
      : 'Level unknown';
    const flags = [];
    if (s.hungry) flags.push('hungry');
    if (s.thirsty) flags.push('thirsty');
    return `<div class="score-card">
      <div class="score-card-header">
        <span class="score-card-name">${escapeHtml(p.name)}</span>
        <span class="score-card-level">${levelPart}</span>
      </div>
      ${scoreBar('HP', s.hp, s.max_hp, 'hp')}
      ${scoreBar('Mana', s.mana, s.max_mana, 'mana')}
      ${scoreBar('Move', s.move, s.max_move, 'move')}
      ${'exp' in s && 'exp_to_next' in s
        ? `<div class="score-exp-row">${s.exp} exp — ${s.exp_to_next} to next level</div>`
        : ''}
      ${'gold' in s ? `<div class="score-gold">${s.gold} gold</div>` : ''}
      ${flags.length ? `<div class="score-flags">${flags.join(', ')}</div>` : ''}
    </div>`;
  }).join('');
}

// Goals tab
async function loadGoals() {
  const el = document.getElementById('goals-content');
  const r = await fetch('/api/goal');
  const data = await r.json();
  el.textContent = Object.entries(data).map(([k, v]) => k + ': ' + v).join('\n');
}

// Sessions tab
async function loadSessions() {
  const r = await fetch('/api/sessions');
  const sessions = await r.json();
  const container = document.getElementById('sessions-list');
  container.innerHTML = '<table><thead><tr><th>Session</th><th>Started</th><th>Model</th><th>Input tokens</th><th>Output tokens</th></tr></thead><tbody>' +
    sessions.map(s =>
      `<tr data-id="${escapeHtml(s.id)}"><td>${escapeHtml(s.id)}</td><td>${escapeHtml(s.started_at || '')}</td><td>${escapeHtml(s.model || '')}</td><td>${s.total_input_tokens}</td><td>${s.total_output_tokens}</td></tr>`
    ).join('') + '</tbody></table>';
  container.querySelectorAll('tr[data-id]').forEach(row => {
    row.addEventListener('click', () => {
      container.querySelectorAll('tr.selected').forEach(r => r.classList.remove('selected'));
      row.classList.add('selected');
      loadSessionDetail(row.dataset.id);
    });
  });
}

async function loadSessionDetail(id) {
  const container = document.getElementById('session-transcript');
  container.innerHTML = '<div class="entry-tool">Loading…</div>';
  const r = await fetch('/api/sessions/' + id);
  const entries = await r.json();
  const html = entries.map(e => {
    if (e.phase === 'response') return `<div class="entry-assistant"><strong>Assistant:</strong> ${escapeHtml(e.text)}</div>`;
    if (e.phase === 'tool_call') return `<div class="entry-tool">→ ${escapeHtml(e.name)}(${escapeHtml(JSON.stringify(e.args || {}))})</div>`;
    if (e.phase === 'tool_result') return `<div class="entry-tool">← ${escapeHtml((e.result || '').slice(0, 300))}</div>`;
    if (e.phase === 'prompt') {
      const last = (e.messages || []).at(-1);
      if (last && last.role === 'user') return `<div class="entry-user"><strong>User:</strong> ${escapeHtml(last.content)}</div>`;
    }
    if (e.phase === 'limit_reached') return `<div class="entry-tool">⚠ limit reached: ${escapeHtml(e.reason || '')}</div>`;
    return '';
  }).join('');
  container.innerHTML = html || `<div class="entry-tool">No transcript entries recorded for this session (${entries.length} raw event${entries.length === 1 ? '' : 's'}, none renderable).</div>`;
}
