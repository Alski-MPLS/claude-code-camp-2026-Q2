// Compass-anchored layout: rooms sit on a fixed grid so that "north of"
// always renders above, "east of" always renders to the right, etc.
// There is no free axis left for up/down (vertical MUD levels), so those
// connections are drawn as short dashed diagonals instead of moving the
// room to a new grid cell.
const GRID = 130;

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

// Lays rooms out on a fixed grid using BFS from each connected component's
// first-seen room, walking compass exits to place neighbors. Disconnected
// components are placed side by side so they don't overlap.
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

  for (const start of nodes) {
    if (visited.has(start.id)) continue;

    const local = new Map();
    local.set(start.id, { x: 0, y: 0 });
    visited.add(start.id);
    const queue = [start.id];
    let minX = 0, maxX = 0;
    while (queue.length) {
      const cur = queue.shift();
      const curPos = local.get(cur);
      for (const { to, dir } of adj.get(cur) || []) {
        if (local.has(to)) continue;
        const offset = DIR_OFFSET[dir] || [1.5, ((local.size * 37) % 5) - 2];
        const next = { x: curPos.x + offset[0], y: curPos.y + offset[1] };
        local.set(to, next);
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

  if (!nodes.length) {
    status.textContent = 'No rooms mapped yet. Explore the MUD first.';
    d3.select('#map-svg').selectAll('*').remove();
    return;
  }
  status.textContent = 'Rooms are placed by compass direction — north is up, east is right. ' +
    'Up/down exits are shown as dashed diagonal lines since there is no vertical axis on a flat map.';

  const grid = layoutNodes(nodes, links);
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
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const panX = width / 2 - cx;
  const panY = height / 2 - cy;

  const g = svg.append('g').attr('transform', `translate(${panX},${panY})`);
  currentZoomTransform = d3.zoomIdentity.translate(panX, panY);

  const zoom = d3.zoom().on('zoom', e => {
    currentZoomTransform = e.transform;
    g.attr('transform', e.transform);
    hidePopup();
  });
  svg.call(zoom);
  svg.call(zoom.transform, currentZoomTransform);

  const byId = new Map(nodes.map(n => [n.id, n]));
  const drawLinks = links
    .map(l => ({ ...l, source: byId.get(l.source), target: byId.get(l.target) }))
    .filter(l => l.source && l.target);

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
    .attr('x', d => (d.source.x + d.target.x) / 2)
    .attr('y', d => (d.source.y + d.target.y) / 2)
    .text(d => d.direction);

  const node = g.append('g').selectAll('circle').data(nodes).join('circle')
    .attr('r', 8).attr('cx', d => d.x).attr('cy', d => d.y)
    .attr('fill', '#4af').attr('stroke', '#222').attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation();
      const svgRect = svg.node().getBoundingClientRect();
      const t = currentZoomTransform;
      const screenX = svgRect.left - container.getBoundingClientRect().left + t.applyX(d.x);
      const screenY = svgRect.top - container.getBoundingClientRect().top + t.applyY(d.y);
      showRoomPopup(d, screenX, screenY, container);
    });

  g.append('g').selectAll('text.node-label').data(nodes).join('text')
    .attr('class', 'node-label').attr('fill', '#aaa').attr('font-size', 11)
    .attr('x', d => d.x).attr('y', d => d.y)
    .attr('dx', 11).attr('dy', 4).text(d => d.title);
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
