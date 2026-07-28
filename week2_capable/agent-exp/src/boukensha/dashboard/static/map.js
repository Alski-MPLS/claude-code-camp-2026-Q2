// Compass-anchored layout: rooms sit on a fixed grid so that "north of"
// always renders above, "east of" always renders to the right, etc.
// There is no free axis left for up/down (vertical MUD levels), so those
// connections are drawn as short dashed diagonals instead of moving the
// room to a new grid cell.
const GRID = 220;
const ROOM_LABEL_MAX = 15;

function shortRoomLabel(title) {
  return title.length > ROOM_LABEL_MAX ? title.slice(0, ROOM_LABEL_MAX - 1) + '…' : title;
}

const DIR_OFFSET = {
  north: [0, -1], south: [0, 1], east: [1, 0], west: [-1, 0],
  northeast: [1, -1], northwest: [-1, -1], southeast: [1, 1], southwest: [-1, 1],
  up: [0.4, -0.4], down: [0.4, 0.4],
};

const OPPOSITE = {
  north: "south", south: "north", east: "west", west: "east",
  northeast: "southwest", southwest: "northeast",
  northwest: "southeast", southeast: "northwest",
  up: "down", down: "up",
};

const VERTICAL = new Set(["up", "down"]);

// Ring of cells to try, nearest first, when a compass-computed cell is
// already taken by an unrelated room (real MUDs are frequently
// non-Euclidean: two different rooms can legitimately compute to the same
// offset from unrelated starting points).
const SEARCH_DIRS = [
  [1, 0], [0, 1], [-1, 0], [0, -1],
  [1, 1], [1, -1], [-1, 1], [-1, -1],
];

function cellKey(p) {
  // Round to a tenth of a grid unit so the small fractional up/down
  // offsets don't collide with integer cardinal cells but near-identical
  // floats still collapse to the same key.
  return Math.round(p.x * 10) + ',' + Math.round(p.y * 10);
}

function findFreeCell(desired, occupied) {
  if (!occupied.has(cellKey(desired))) return desired;
  for (let radius = 1; radius < 25; radius++) {
    for (const [dx, dy] of SEARCH_DIRS) {
      const candidate = { x: desired.x + dx * radius, y: desired.y + dy * radius };
      if (!occupied.has(cellKey(candidate))) return candidate;
    }
  }
  return desired; // give up rather than loop forever; a rare overlap beats an infinite loop
}

// Lays rooms out on a fixed grid using BFS from each connected component's
// first-seen room, walking compass exits to place neighbors. Disconnected
// components are placed side by side so they don't overlap. When a
// non-Euclidean layout would put two different rooms in the same cell, the
// later one is nudged to the nearest open cell instead of stacking.
function layoutNodes(nodes, links) {
  const adj = new Map(nodes.map(n => [n.id, []]));
  for (const l of links) {
    const dir = (l.direction || "").toLowerCase();
    if (!adj.has(l.source) || !adj.has(l.target)) continue;
    adj.get(l.source).push({ to: l.target, dir });
    const opp = OPPOSITE[dir];
    if (opp) adj.get(l.target).push({ to: l.source, dir: opp });
  }

  const grid = new Map();
  const visited = new Set();
  let nextComponentX = 0;
  let hadCollision = false;

  for (const start of nodes) {
    if (visited.has(start.id)) continue;

    const local = new Map();
    const occupied = new Set();
    local.set(start.id, { x: 0, y: 0 });
    occupied.add(cellKey({ x: 0, y: 0 }));
    visited.add(start.id);
    const queue = [start.id];
    let minX = 0, maxX = 0;
    while (queue.length) {
      const cur = queue.shift();
      const curPos = local.get(cur);
      for (const { to, dir } of adj.get(cur) || []) {
        if (local.has(to)) continue;
        const offset = DIR_OFFSET[dir] || [1.5, ((local.size * 37) % 5) - 2];
        const desired = { x: curPos.x + offset[0], y: curPos.y + offset[1] };
        const next = findFreeCell(desired, occupied);
        if (next.x !== desired.x || next.y !== desired.y) hadCollision = true;
        local.set(to, next);
        occupied.add(cellKey(next));
        visited.add(to);
        minX = Math.min(minX, next.x);
        maxX = Math.max(maxX, next.x);
        queue.push(to);
      }
    }

    const shiftX = nextComponentX - minX;
    for (const [id, p] of local.entries()) {
      grid.set(id, { x: (p.x + shiftX) * GRID, y: p.y * GRID });
    }
    nextComponentX += (maxX - minX) + 2.5; // gap between components
  }

  grid.hadCollision = hadCollision;
  return grid;
}

function popupHtml(title, roomId, room) {
  if (!room) {
    return (
      '<div class="room-popup-title">' + escapeHtml(title) + '</div>' +
      '<div>(no stored details for this room)</div>'
    );
  }
  const exits = Object.keys(room.exits || {});
  let html = '<div class="room-popup-title">' + escapeHtml(title) + '</div>';
  html += '<div>' + escapeHtml(room.description || '(no description recorded)') + '</div>';
  html += '<div class="room-popup-section">Exits: ' + escapeHtml(exits.length ? exits.join(', ') : '(none known)') + '</div>';
  if (room.npcs && room.npcs.length) {
    html += '<div class="room-popup-section">NPCs: ' + escapeHtml(room.npcs.join(', ')) + '</div>';
  }
  if (room.items && room.items.length) {
    html += '<div class="room-popup-section">Items: ' + escapeHtml(room.items.join(', ')) + '</div>';
  }
  return html;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

let currentZoomTransform = d3.zoomIdentity;

// Live player markers: state kept across refreshes so a lightweight poll can
// move stars without redoing the whole compass layout (which would reset
// zoom/pan and close any open popup) unless the room count actually changed.
let nodeById = new Map();
let playersLayer = null;
let lastNodeCount = 0;
let lastLinkCount = 0;
let refreshTimer = null;
const playerColorMap = new Map();
const PLAYER_COLORS = ['#ffd23f', '#ff6b6b', '#6bcbff', '#a56bff', '#6bffb8', '#ff9f6b', '#ff6bcb', '#c9ff6b'];

function colorForPlayer(name) {
  if (!playerColorMap.has(name)) {
    playerColorMap.set(name, PLAYER_COLORS[playerColorMap.size % PLAYER_COLORS.length]);
  }
  return playerColorMap.get(name);
}

function renderPlayers(players) {
  if (!playersLayer) return;
  playersLayer.selectAll('*').remove();
  if (!players || !players.length) return;

  // Group by room so multiple characters standing in the same room fan out
  // side by side instead of drawing one star on top of another.
  const byRoom = new Map();
  for (const p of players) {
    const node = nodeById.get(p.room_hash);
    if (!node) continue; // character is somewhere not on this rendered map
    if (!byRoom.has(p.room_hash)) byRoom.set(p.room_hash, []);
    byRoom.get(p.room_hash).push(p);
  }

  for (const group of byRoom.values()) {
    const node = nodeById.get(group[0].room_hash);
    group.forEach((p, i) => {
      const color = colorForPlayer(p.name);
      const starX = node.x + (i - (group.length - 1) / 2) * 28;
      const starY = node.y - 24;
      // Stagger name labels between two rows so 2+ characters in the same
      // room don't render their names on top of each other.
      const nameY = starY - 12 - (i % 2) * 12;

      const star = playersLayer.append('text')
        .attr('class', 'player-star')
        .attr('x', starX).attr('y', starY)
        .attr('text-anchor', 'middle')
        .attr('font-size', 20)
        .attr('fill', color)
        .attr('stroke', '#181818').attr('stroke-width', 3).attr('paint-order', 'stroke fill')
        .text('★');
      star.append('title').text(p.name);

      playersLayer.append('text')
        .attr('class', 'player-name')
        .attr('x', starX).attr('y', nameY)
        .attr('text-anchor', 'middle')
        .attr('font-size', 10).attr('font-weight', 'bold')
        .attr('fill', color)
        .attr('stroke', '#181818').attr('stroke-width', 3).attr('paint-order', 'stroke fill')
        .text(p.name);
    });
  }

  // Draw movement arrows from previous room to current room
  for (const p of players) {
    if (!p.prev_room_hash || p.prev_room_hash === p.room_hash) continue;
    const fromNode = nodeById.get(p.prev_room_hash);
    const toNode = nodeById.get(p.room_hash);
    if (!fromNode || !toNode) continue;

    playersLayer.append('line')
      .attr('x1', fromNode.x).attr('y1', fromNode.y)
      .attr('x2', toNode.x).attr('y2', toNode.y)
      .attr('stroke', '#ffd23f')
      .attr('stroke-width', 2.5)
      .attr('marker-end', 'url(#arrow-head)')
      .attr('opacity', 0.8);
  }
}

async function refreshTick() {
  const mapTab = document.getElementById('tab-map');
  if (!mapTab || !mapTab.classList.contains('active')) return;
  try {
    const [mapRes, playersRes] = await Promise.all([fetch('/api/map'), fetch('/api/players')]);
    const { nodes, links } = await mapRes.json();
    const players = await playersRes.json();
    if (nodes.length !== lastNodeCount || links.length !== lastLinkCount) {
      // New rooms were discovered since the last full render — relayout.
      await window.loadMap();
      return;
    }
    renderPlayers(players);
  } catch (err) {
    // transient fetch failure — next tick will retry
  }
}

async function showRoomPopup(d, screenX, screenY, container) {
  const popup = document.getElementById('room-popup');
  const body = document.getElementById('room-popup-body');
  body.innerHTML = popupHtml(d.title, d.id, null);
  popup.dataset.roomId = d.id;
  positionPopup(popup, container, screenX, screenY);
  popup.hidden = false;

  try {
    const r = await fetch('/api/room/' + encodeURIComponent(d.id));
    const room = r.ok ? await r.json() : null;
    // Only update if this popup is still showing the same room (guards
    // against a second click swapping rooms while this fetch was in flight).
    if (popup.dataset.roomId === d.id) {
      body.innerHTML = popupHtml(d.title, d.id, room);
      positionPopup(popup, container, screenX, screenY);
    }
  } catch (err) {
    // keep the "no stored details" fallback already rendered
  }
}

function positionPopup(popup, container, nodeX, nodeY) {
  const containerRect = container.getBoundingClientRect();
  popup.hidden = false; // needs to be visible to measure its size
  const popupW = popup.offsetWidth || 260;
  const popupH = popup.offsetHeight || 90;

  const margin = 16;
  let left = nodeX - popupW / 2;
  left = Math.max(margin, Math.min(left, containerRect.width - popupW - margin));

  const spaceAbove = nodeY;
  const placeAbove = spaceAbove > popupH + 24;

  let top;
  popup.classList.remove('arrow-top', 'arrow-bottom');
  if (placeAbove) {
    top = nodeY - popupH - 18;
    popup.classList.add('arrow-bottom');
  } else {
    top = nodeY + 18;
    popup.classList.add('arrow-top');
  }

  popup.style.left = left + 'px';
  popup.style.top = top + 'px';

  const arrow = document.getElementById('room-popup-arrow');
  const arrowX = Math.max(14, Math.min(nodeX - left, popupW - 14));
  arrow.style.left = arrowX + 'px';
  arrow.style.marginLeft = '-6px';
}

function hidePopup() {
  const popup = document.getElementById('room-popup');
  popup.hidden = true;
  delete popup.dataset.roomId;
}

window.loadMap = async function loadMap() {
  const r = await fetch('/api/map');
  const { nodes, links } = await r.json();
  const status = document.getElementById('map-status');
  const container = document.getElementById('map-container');
  hidePopup();

  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(refreshTick, 3000);

  if (!nodes.length) {
    status.textContent = 'No rooms mapped yet. Explore the MUD first.';
    d3.select('#map-svg').selectAll('*').remove();
    nodeById = new Map();
    playersLayer = null;
    lastNodeCount = 0;
    lastLinkCount = 0;
    return;
  }
  const grid = layoutNodes(nodes, links);
  status.textContent = 'Rooms are placed by compass direction — north is up, east is right. ' +
    'Up/down exits are shown as dashed diagonal lines since there is no vertical axis on a flat map.' +
    (grid.hadCollision
      ? ' Some rooms were nudged off their exact compass cell to avoid overlapping another room — this map isn’t a perfect grid.'
      : '');

  for (const n of nodes) {
    const p = grid.get(n.id) || { x: 0, y: 0 };
    n.x = p.x;
    n.y = p.y;
  }

  const svg = d3.select('#map-svg');
  svg.selectAll('*').remove();
  const width = svg.node().clientWidth || 800;
  const height = svg.node().clientHeight || 500;

  const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;

  // Scale down (never up) so the whole map — including label width, not
  // just node dots — fits in view on first load. Room names extend past
  // their node, so pad generously.
  const labelPad = 240;
  const graphW = (maxX - minX) + labelPad;
  const graphH = (maxY - minY) + labelPad;
  const scale = Math.min(1, width / graphW, height / graphH);

  const panX = width / 2 - cx * scale;
  const panY = height / 2 - cy * scale;

  const g = svg.append('g');

  svg.append('defs').html(`
  <marker id="arrow-head" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
    <path d="M0,0 L0,6 L8,3 z" fill="#ffd23f" />
  </marker>
`);

  currentZoomTransform = d3.zoomIdentity.translate(panX, panY).scale(scale);
  g.attr('transform', currentZoomTransform);

  const zoom = d3.zoom().on('zoom', e => {
    currentZoomTransform = e.transform;
    g.attr('transform', e.transform);
    hidePopup();
  });
  svg.call(zoom);
  svg.call(zoom.transform, currentZoomTransform);

  const byId = new Map(nodes.map(n => [n.id, n]));
  // Many rooms record exits both ways (A north-of B and B south-of A); draw
  // that pair once instead of stacking two identical lines/labels.
  const seenPairs = new Set();
  const drawLinks = links
    .filter(l => byId.has(l.source) && byId.has(l.target))
    .filter(l => {
      const key = [l.source, l.target].sort().join('|');
      if (seenPairs.has(key)) return false;
      seenPairs.add(key);
      return true;
    })
    .map(l => ({ ...l, source: byId.get(l.source), target: byId.get(l.target) }));

  g.append('g').selectAll('line').data(drawLinks).join('line')
    .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
    .attr('stroke', d => VERTICAL.has((d.direction || '').toLowerCase()) ? '#a84' : '#444')
    .attr('stroke-width', 1.5)
    .attr('stroke-dasharray', d => VERTICAL.has((d.direction || '').toLowerCase()) ? '4,3' : null);

  g.append('g').selectAll('text.link-label').data(drawLinks).join('text')
    .attr('class', 'link-label')
    .attr('fill', d => VERTICAL.has((d.direction || '').toLowerCase()) ? '#c96' : '#666')
    .attr('font-size', 10).attr('text-anchor', 'middle')
    // Halo + a small upward nudge so the label doesn't sit exactly on the
    // node-label baseline for horizontal (east/west) edges between
    // immediate neighbors.
    .attr('stroke', '#181818').attr('stroke-width', 3).attr('paint-order', 'stroke fill')
    .attr('x', d => (d.source.x + d.target.x) / 2)
    .attr('y', d => (d.source.y + d.target.y) / 2 - 6)
    .text(d => d.direction);

  const RECT_W = 110, RECT_H = 30;

  const nodeGroup = g.append('g').selectAll('g.room-node').data(nodes).join('g')
    .attr('class', 'room-node')
    .attr('transform', d => `translate(${d.x - RECT_W / 2},${d.y - RECT_H / 2})`)
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation();
      const svgRect = svg.node().getBoundingClientRect();
      const t = currentZoomTransform;
      const screenX = svgRect.left - container.getBoundingClientRect().left + t.applyX(d.x);
      const screenY = svgRect.top - container.getBoundingClientRect().top + t.applyY(d.y);
      showRoomPopup(d, screenX, screenY, container);
    });

  nodeGroup.append('rect')
    .attr('width', RECT_W).attr('height', RECT_H)
    .attr('rx', 4)
    .attr('fill', '#1e3a5f').attr('stroke', '#4af').attr('stroke-width', 1.5);

  nodeGroup.append('text')
    .attr('x', RECT_W / 2).attr('y', RECT_H / 2)
    .attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
    .attr('fill', '#aaa').attr('font-size', 11).attr('font-family', 'monospace')
    .attr('stroke', '#181818').attr('stroke-width', 2).attr('paint-order', 'stroke fill')
    .text(d => shortRoomLabel(d.title));

  nodeGroup.append('title').text(d => d.title);

  nodeById = byId;
  lastNodeCount = nodes.length;
  lastLinkCount = links.length;
  playersLayer = g.append('g');

  try {
    const playersRes = await fetch('/api/players');
    renderPlayers(await playersRes.json());
  } catch (err) {
    // no players.json yet, or the fetch failed — map still renders without markers
  }
};

// Click anywhere outside the popup (room nodes stop propagation themselves)
// dismisses it. Registered once at module load, not per-render.
document.addEventListener('click', (event) => {
  const popup = document.getElementById('room-popup');
  if (!popup || popup.hidden) return;
  if (popup.contains(event.target)) return;
  hidePopup();
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') hidePopup();
});
