window.loadMap = async function loadMap() {
  const r = await fetch('/api/map');
  const { nodes, links } = await r.json();
  if (!nodes.length) {
    document.getElementById('room-detail').textContent = 'No rooms mapped yet. Explore the MUD first.';
    return;
  }

  const svg = d3.select('#map-svg');
  svg.selectAll('*').remove();
  const width = svg.node().clientWidth || 800;
  const height = svg.node().clientHeight || 500;

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2));

  const g = svg.append('g');
  svg.call(d3.zoom().on('zoom', e => g.attr('transform', e.transform)));

  const link = g.append('g').selectAll('line').data(links).join('line')
    .attr('stroke', '#444').attr('stroke-width', 1.5);

  const label = g.append('g').selectAll('text.link-label').data(links).join('text')
    .attr('class', 'link-label').attr('fill', '#666').attr('font-size', 10)
    .attr('text-anchor', 'middle').text(d => d.direction);

  const node = g.append('g').selectAll('circle').data(nodes).join('circle')
    .attr('r', 8).attr('fill', '#4af').attr('stroke', '#222').attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .on('click', (_, d) => {
      document.getElementById('room-detail').textContent =
        'Room: ' + d.title + '\nHash: ' + d.id;
    })
    .call(d3.drag()
      .on('start', (event, d) => { if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end', (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

  const nodeLabel = g.append('g').selectAll('text.node-label').data(nodes).join('text')
    .attr('class', 'node-label').attr('fill', '#aaa').attr('font-size', 11)
    .attr('dx', 11).attr('dy', 4).text(d => d.title);

  sim.on('tick', () => {
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    label.attr('x', d => (d.source.x + d.target.x) / 2)
         .attr('y', d => (d.source.y + d.target.y) / 2);
    node.attr('cx', d => d.x).attr('cy', d => d.y);
    nodeLabel.attr('x', d => d.x).attr('y', d => d.y);
  });
};
