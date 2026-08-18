const PALETTE = {
  parchment: '#f5f4ed', ivory: '#faf9f5', brand: '#1b365d', brandTint: '#eef2f7',
  nearBlack: '#141413', olive: '#504e49', stone: '#6b6a64', border: '#e8e6dc'
};

export const DIAGRAM_TYPES = [
  'architecture', 'architecture-board', 'workflow', 'sequence', 'dataflow', 'lifecycle',
  'quadrant', 'timeline', 'tree', 'layer-stack', 'venn',
  'bar', 'line', 'donut', 'candlestick', 'waterfall', 'class', 'er'
];

const escapeXml = (value = '') => String(value)
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&apos;');
const slug = (value = '') => String(value).toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-|-$/g, '') || 'diagram';
const text = (x, y, value, cls = 'node-title', anchor = 'middle') =>
  `<text x="${x}" y="${y}" text-anchor="${anchor}" class="${cls}">${escapeXml(value)}</text>`;

function frame(spec, width, height, body, geometry = { nodes: [], edges: [] }) {
  const title = spec.meta?.title || 'Diagram';
  const description = spec.meta?.description || spec.meta?.caption || spec.meta?.subtitle || title;
  const header = spec.meta?.subtitle
    ? `${text(40, 36, title, 'node-title', 'start')}${text(40, 56, spec.meta.subtitle, 'node-subtitle', 'start')}`
    : text(40, 42, title, 'node-title', 'start');
  return {
    width,
    height,
    geometry,
    svg: `<svg class="diagram" data-title="${escapeXml(slug(title))}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="diagram-title diagram-desc" xmlns="http://www.w3.org/2000/svg">
<title id="diagram-title">${escapeXml(title)}</title><desc id="diagram-desc">${escapeXml(description)}</desc>
<defs>
  <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.9" fill="#e3e2dc"/></pattern>
  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1 L9 5 L1 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round"/></marker>
</defs>
<rect width="100%" height="100%" fill="${PALETTE.parchment}"/><rect width="100%" height="100%" fill="url(#dots)" opacity=".5"/>
${header}<line x1="40" y1="68" x2="${width - 40}" y2="68" stroke="${PALETTE.brand}" stroke-width="1"/>
${body}
</svg>`
  };
}

function nodeBox(node, x, y, width = 152, height = 64) {
  const classes = ['node', node.variant === 'emphasis' || node.focal ? 'focal' : '', node.maturity === 'future' ? 'future' : ''].filter(Boolean).join(' ');
  const detail = node.detail || node.description || node.sublabel || node.label;
  const tag = node.tag ? text(x + width - 10, y + 17, node.tag, 'node-subtitle', 'end') : '';
  return `<g class="${classes}" data-node-id="${escapeXml(node.id)}" data-label="${escapeXml(node.label)}" data-detail="${escapeXml(detail)}">
<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="8"/>
${text(x + 12, y + 28, node.label, 'node-title', 'start')}
${node.sublabel ? text(x + 12, y + 48, node.sublabel, 'node-subtitle', 'start') : ''}${tag}</g>`;
}

function routeBetween(from, to) {
  const fromCenter = { x: from.x + from.w / 2, y: from.y + from.h / 2 };
  const toCenter = { x: to.x + to.w / 2, y: to.y + to.h / 2 };
  if (Math.abs(toCenter.x - fromCenter.x) >= Math.abs(toCenter.y - fromCenter.y)) {
    const leftToRight = fromCenter.x <= toCenter.x;
    const start = { x: leftToRight ? from.x + from.w : from.x, y: fromCenter.y };
    const end = { x: leftToRight ? to.x : to.x + to.w, y: toCenter.y };
    const middle = (start.x + end.x) / 2;
    return [start, { x: middle, y: start.y }, { x: middle, y: end.y }, end];
  }
  const topToBottom = fromCenter.y <= toCenter.y;
  const start = { x: fromCenter.x, y: topToBottom ? from.y + from.h : from.y };
  const end = { x: toCenter.x, y: topToBottom ? to.y : to.y + to.h };
  const middle = (start.y + end.y) / 2;
  return [start, { x: start.x, y: middle }, { x: end.x, y: middle }, end];
}

function edgePath(edge, boxes) {
  const from = boxes.get(edge.from);
  const to = boxes.get(edge.to);
  if (!from || !to) return null;
  const points = routeBetween(from, to);
  const d = points.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ');
  const classes = ['edge', edge.variant === 'emphasis' || edge.role === 'main' ? 'focal' : '', edge.role === 'async' || edge.variant === 'dashed' ? 'async' : ''].filter(Boolean).join(' ');
  let label = '';
  if (edge.label) {
    const estimatedWidth = String(edge.label).length * 6.6;
    const horizontal = points[0].y === points.at(-1).y;
    const vertical = points[0].x === points.at(-1).x;
    const available = horizontal
      ? Math.abs(points.at(-1).x - points[0].x)
      : vertical ? Math.abs(points.at(-1).y - points[0].y) : 0;
    if (horizontal && available >= estimatedWidth + 16) {
      label = text((points[0].x + points.at(-1).x) / 2, points[0].y - 9, edge.label, 'edge-label');
    } else if (vertical && available >= 28) {
      label = text(points[0].x + 9, (points[0].y + points.at(-1).y) / 2 + 4, edge.label, 'edge-label', 'start');
    }
  }
  return { html: `<path class="${classes}" data-edge-from="${escapeXml(edge.from)}" data-edge-to="${escapeXml(edge.to)}" d="${d}"/>${label}`, points };
}

function renderArchitecture(spec) {
  const items = spec.components || spec.nodes || [];
  const cols = Math.max(1, Math.min(4, spec.layout?.cols || Math.ceil(Math.sqrt(items.length || 1))));
  const rows = Math.max(1, Math.ceil(items.length / cols));
  const width = Math.max(760, 104 + cols * 196);
  const height = 130 + rows * 116;
  const boxes = new Map();
  items.forEach((item, index) => {
    const col = item.col ?? index % cols;
    const row = item.row ?? Math.floor(index / cols);
    boxes.set(item.id, { x: 64 + col * 196, y: 96 + row * 116, w: item.width || 156, h: item.height || 64 });
  });
  const geometry = { nodes: [...boxes].map(([id, box]) => ({ id, ...box })), edges: [] };
  const connections = spec.connections || spec.edges || [];
  const edgeHtml = connections.map((edge) => {
    const result = edgePath(edge, boxes);
    if (!result) return '';
    geometry.edges.push({ from: edge.from, to: edge.to, points: result.points });
    return result.html;
  }).join('');
  const boundaries = (spec.boundaries || []).map((boundary) => {
    const wrapped = boundary.wraps.map((id) => boxes.get(id)).filter(Boolean);
    if (!wrapped.length) return '';
    const minX = Math.min(...wrapped.map((box) => box.x)) - 18;
    const minY = Math.min(...wrapped.map((box) => box.y)) - 26;
    const maxX = Math.max(...wrapped.map((box) => box.x + box.w)) + 18;
    const maxY = Math.max(...wrapped.map((box) => box.y + box.h)) + 18;
    return `<g><rect x="${minX}" y="${minY}" width="${maxX - minX}" height="${maxY - minY}" rx="12" fill="none" stroke="${PALETTE.stone}" stroke-dasharray="7 5"/>${text(minX + 8, minY + 16, boundary.label, 'stage-label', 'start')}</g>`;
  }).join('');
  const nodes = items.map((item) => { const box = boxes.get(item.id); return nodeBox(item, box.x, box.y, box.w, box.h); }).join('');
  return frame(spec, width, height, `${boundaries}${edgeHtml}${nodes}`, geometry);
}

function renderWorkflow(spec) {
  const lanes = spec.lanes?.length ? spec.lanes : [{ id: 'main', label: 'Main' }];
  const nodes = spec.nodes || [];
  const maxCol = Math.max(0, ...nodes.map((node) => node.col || 0));
  const width = Math.max(820, 220 + (maxCol + 1) * 180);
  const laneH = 112;
  const height = 96 + lanes.length * laneH + 30;
  const boxes = new Map();
  nodes.forEach((node) => {
    const lane = Math.max(0, lanes.findIndex((item) => item.id === node.lane));
    boxes.set(node.id, { x: 166 + (node.col || 0) * 180, y: 96 + lane * laneH + 24, w: node.width || 146, h: node.height || 62 });
  });
  const geometry = { nodes: [...boxes].map(([id, box]) => ({ id, ...box })), edges: [] };
  const laneHtml = lanes.map((lane, index) => `<g><rect class="lane" x="40" y="${82 + index * laneH}" width="${width - 80}" height="${laneH - 8}" rx="8"/>${text(58, 110 + index * laneH, lane.label, 'lane-label', 'start')}</g>`).join('');
  const edgeHtml = (spec.edges || []).map((edge) => {
    const result = edgePath(edge, boxes); if (!result) return '';
    geometry.edges.push({ from: edge.from, to: edge.to, points: result.points }); return result.html;
  }).join('');
  const nodeHtml = nodes.map((node) => { const box = boxes.get(node.id); return nodeBox(node, box.x, box.y, box.w, box.h); }).join('');
  return frame(spec, width, height, `${laneHtml}${edgeHtml}${nodeHtml}`, geometry);
}

function renderSequence(spec) {
  const participants = spec.participants || [];
  const messages = spec.messages || [];
  const width = Math.max(700, 120 + participants.length * 190);
  const height = Math.max(480, 180 + messages.length * 58);
  const positions = new Map();
  participants.forEach((participant, index) => positions.set(participant.id, 80 + index * ((width - 160) / Math.max(1, participants.length - 1))));
  const participantHtml = participants.map((participant) => {
    const x = positions.get(participant.id);
    return `${nodeBox(participant, x - 70, 92, 140, 54)}<line x1="${x}" y1="146" x2="${x}" y2="${height - 42}" stroke="${PALETTE.border}" stroke-dasharray="5 5"/>`;
  }).join('');
  const geometry = { nodes: participants.map((participant) => ({ id: participant.id, x: positions.get(participant.id) - 70, y: 92, w: 140, h: 54 })), edges: [] };
  const messageHtml = messages.map((message, index) => {
    const x1 = positions.get(message.from); const x2 = positions.get(message.to); const y = message.y || 190 + index * 58;
    geometry.edges.push({ from: message.from, to: message.to, points: [{ x: x1, y }, { x: x2, y }] });
    const cls = message.variant === 'return' || message.variant === 'dashed' ? 'edge async' : message.variant === 'emphasis' ? 'edge focal' : 'edge';
    return `<path class="${cls}" data-edge-from="${escapeXml(message.from)}" data-edge-to="${escapeXml(message.to)}" d="M ${x1} ${y} L ${x2} ${y}"/>${text((x1 + x2) / 2, y - 9, message.label, 'edge-label')}${message.note ? text((x1 + x2) / 2, y + 17, message.note, 'node-subtitle') : ''}`;
  }).join('');
  return frame(spec, width, height, `${participantHtml}${messageHtml}`, geometry);
}

function renderDataflow(spec) {
  const stages = spec.stages || [];
  const nodes = spec.nodes || [];
  const maxRows = Math.max(1, ...stages.map((_, stage) => nodes.filter((node) => node.stage === stage).length));
  const width = Math.max(820, 100 + stages.length * 210);
  const height = 150 + maxRows * 100;
  const boxes = new Map();
  nodes.forEach((node, index) => {
    const stage = node.stage || 0; const row = node.row ?? nodes.filter((candidate, i) => i < index && candidate.stage === stage).length;
    boxes.set(node.id, { x: 62 + stage * 210, y: 116 + row * 94, w: 160, h: 60 });
  });
  const geometry = { nodes: [...boxes].map(([id, box]) => ({ id, ...box })), edges: [] };
  const stageHtml = stages.map((stage, index) => `<g><rect class="stage" x="42" y="88" width="190" height="${height - 118}" rx="8" transform="translate(${index * 210} 0)"/>${text(58 + index * 210, 108, stage.label || stage, 'stage-label', 'start')}</g>`).join('');
  const edgeHtml = (spec.flows || spec.edges || []).map((edge) => { const result = edgePath(edge, boxes); if (!result) return ''; geometry.edges.push({ from: edge.from, to: edge.to, points: result.points }); return result.html; }).join('');
  const nodeHtml = nodes.map((node) => { const box = boxes.get(node.id); return nodeBox(node, box.x, box.y, box.w, box.h); }).join('');
  return frame(spec, width, height, `${stageHtml}${edgeHtml}${nodeHtml}`, geometry);
}

function renderLifecycle(spec) {
  const mapped = {
    ...spec,
    nodes: (spec.states || []).map((state) => ({ ...state, variant: ['active', 'success', 'decision'].includes(state.type) ? 'emphasis' : state.variant })),
    edges: spec.transitions || [],
    lanes: spec.lanes || [{ id: 'main', label: 'Lifecycle' }]
  };
  return renderWorkflow(mapped);
}

function renderBoard(spec) {
  const sections = spec.sections || [];
  const blocks = spec.blocks || [];
  const width = 1200;
  const sectionH = 142;
  const height = 110 + Math.max(1, sections.length) * sectionH;
  const geometry = { nodes: [], edges: [] };
  const body = sections.map((section, sectionIndex) => {
    const members = blocks.filter((block) => block.section === section.id);
    const cellW = (width - 240) / Math.max(1, members.length);
    const cells = members.map((block, index) => {
      const box = { id: block.id, x: 190 + index * cellW, y: 102 + sectionIndex * sectionH, w: Math.min(190, cellW - 18), h: 86 };
      geometry.nodes.push(box);
      return nodeBox(block, box.x, box.y, box.w, box.h);
    }).join('');
    return `<rect class="lane" x="40" y="88" width="1120" height="126" rx="8" transform="translate(0 ${sectionIndex * sectionH})"/>${text(62, 120 + sectionIndex * sectionH, section.label, 'lane-label', 'start')}${cells}`;
  }).join('');
  return frame(spec, width, height, body, geometry);
}

function renderQuadrant(spec) {
  const width = 760; const height = 600; const left = 100; const top = 110; const size = 420;
  const points = spec.points || [];
  const body = `<rect x="${left}" y="${top}" width="${size}" height="${size}" fill="${PALETTE.ivory}" stroke="${PALETTE.border}"/>
<line x1="${left + size / 2}" y1="${top}" x2="${left + size / 2}" y2="${top + size}" stroke="${PALETTE.border}"/><line x1="${left}" y1="${top + size / 2}" x2="${left + size}" y2="${top + size / 2}" stroke="${PALETTE.border}"/>
${text(left + size / 2, top + size + 36, spec.axes?.x || 'X', 'axis-label')}${text(left - 58, top + size / 2, spec.axes?.y || 'Y', 'axis-label')}
${points.map((point) => { const x = left + Math.max(0, Math.min(1, point.x)) * size; const y = top + (1 - Math.max(0, Math.min(1, point.y))) * size; return `<g class="node ${point.focal ? 'focal' : ''}" data-node-id="${escapeXml(point.id || point.label)}" data-label="${escapeXml(point.label)}" data-detail="${escapeXml(point.detail || point.label)}"><circle cx="${x}" cy="${y}" r="10"/>${text(x + 16, y + 5, point.label, 'node-title', 'start')}</g>`; }).join('')}`;
  return frame(spec, width, height, body, { nodes: [], edges: [] });
}

function renderTimeline(spec) {
  const events = spec.events || [];
  const width = Math.max(760, 120 + events.length * 170); const height = 330; const y = 180;
  const body = `<line x1="70" y1="${y}" x2="${width - 70}" y2="${y}" stroke="${PALETTE.brand}" stroke-width="2"/>
${events.map((event, index) => { const x = 90 + index * ((width - 180) / Math.max(1, events.length - 1)); const above = index % 2 === 0; return `<g class="node ${event.focal ? 'focal' : ''}" data-node-id="${escapeXml(event.id || index)}" data-label="${escapeXml(event.label)}" data-detail="${escapeXml(event.detail || event.description || event.label)}"><circle cx="${x}" cy="${y}" r="9"/><line x1="${x}" y1="${y + (above ? -9 : 9)}" x2="${x}" y2="${y + (above ? -52 : 52)}" stroke="${PALETTE.stone}"/>${text(x, y + (above ? -68 : 75), event.label, 'node-title')}${text(x, y + (above ? -88 : 96), event.date || '', 'node-subtitle')}</g>`; }).join('')}`;
  return frame(spec, width, height, body, { nodes: [], edges: [] });
}

function renderTree(spec) {
  const nodes = spec.nodes || [];
  const byParent = new Map();
  nodes.forEach((node) => { const key = node.parent || '__root__'; if (!byParent.has(key)) byParent.set(key, []); byParent.get(key).push(node); });
  const ordered = [];
  function visit(parent, depth) { (byParent.get(parent) || []).forEach((node) => { ordered.push({ node, depth }); visit(node.id, depth + 1); }); }
  visit('__root__', 0);
  const width = 820; const height = Math.max(260, 110 + ordered.length * 74);
  const boxes = new Map();
  ordered.forEach(({ node, depth }, index) => boxes.set(node.id, { x: 72 + depth * 170, y: 96 + index * 68, w: 150, h: 52 }));
  const edges = ordered.filter(({ node }) => node.parent).map(({ node }) => ({ from: node.parent, to: node.id }));
  const geometry = { nodes: [...boxes].map(([id, box]) => ({ id, ...box })), edges: [] };
  const edgeHtml = edges.map((edge) => { const result = edgePath(edge, boxes); if (!result) return ''; geometry.edges.push({ ...edge, points: result.points }); return result.html; }).join('');
  const nodeHtml = ordered.map(({ node }) => { const box = boxes.get(node.id); return nodeBox(node, box.x, box.y, box.w, box.h); }).join('');
  return frame(spec, width, height, `${edgeHtml}${nodeHtml}`, geometry);
}

function renderLayerStack(spec) {
  const layers = spec.layers || [];
  const width = 820; const height = 120 + layers.length * 92;
  const body = layers.map((layer, index) => `<g class="node ${layer.focal ? 'focal' : ''}" data-node-id="${escapeXml(layer.id || index)}" data-label="${escapeXml(layer.label)}" data-detail="${escapeXml(layer.description || layer.label)}"><rect x="80" y="${96 + index * 84}" width="660" height="68" rx="8"/>${text(104, 124 + index * 84, layer.label, 'node-title', 'start')}${text(104, 146 + index * 84, layer.description || '', 'node-subtitle', 'start')}${text(718, 132 + index * 84, layer.tag || '', 'stage-label', 'end')}</g>`).join('');
  return frame(spec, width, height, body, { nodes: [], edges: [] });
}

function renderVenn(spec) {
  const sets = (spec.sets || []).slice(0, 3); const width = 760; const height = 520;
  const centers = [{ x: 300, y: 265 }, { x: 450, y: 265 }, { x: 375, y: 360 }];
  const body = sets.map((set, index) => `<g class="node ${set.focal ? 'focal' : ''}" data-node-id="${escapeXml(set.id || index)}" data-label="${escapeXml(set.label)}" data-detail="${escapeXml(set.detail || set.label)}"><circle cx="${centers[index].x}" cy="${centers[index].y}" r="130" fill="${index === 0 ? PALETTE.brandTint : PALETTE.ivory}" fill-opacity=".64" stroke="${index === 0 ? PALETTE.brand : PALETTE.stone}" stroke-width="1.5"/>${text(centers[index].x, centers[index].y - 88, set.label, 'node-title')}</g>`).join('');
  return frame(spec, width, height, body, { nodes: [], edges: [] });
}

function chartScaffold(spec, width = 820, height = 500) {
  const plot = { x: 90, y: 105, w: width - 150, h: height - 180 };
  const body = `<line x1="${plot.x}" y1="${plot.y + plot.h}" x2="${plot.x + plot.w}" y2="${plot.y + plot.h}" stroke="${PALETTE.stone}"/><line x1="${plot.x}" y1="${plot.y}" x2="${plot.x}" y2="${plot.y + plot.h}" stroke="${PALETTE.stone}"/>`;
  return { width, height, plot, body };
}

function renderBar(spec) {
  const chart = chartScaffold(spec); const categories = spec.categories || []; const series = spec.series?.length ? spec.series : [{ name: 'Value', values: spec.values || [] }];
  const max = Math.max(1, ...series.flatMap((item) => item.values.map(Number)));
  const groupW = chart.plot.w / Math.max(1, categories.length); const barW = Math.min(34, groupW / (series.length + 1));
  let body = chart.body;
  categories.forEach((category, index) => {
    body += text(chart.plot.x + groupW * (index + .5), chart.plot.y + chart.plot.h + 25, category, 'node-subtitle');
    series.forEach((item, seriesIndex) => { const value = Number(item.values[index] || 0); const h = value / max * chart.plot.h; const x = chart.plot.x + groupW * index + groupW / 2 + (seriesIndex - (series.length - 1) / 2) * (barW + 4) - barW / 2; const y = chart.plot.y + chart.plot.h - h; body += `<rect x="${x}" y="${y}" width="${barW}" height="${h}" rx="2" fill="${seriesIndex === 0 ? PALETTE.brand : seriesIndex === 1 ? PALETTE.olive : PALETTE.stone}"/>${text(x + barW / 2, y - 7, value, 'node-subtitle')}`; });
  });
  return frame(spec, chart.width, chart.height, body, { nodes: [], edges: [] });
}

function renderLine(spec) {
  const chart = chartScaffold(spec); const categories = spec.categories || []; const series = spec.series || [];
  const max = Math.max(1, ...series.flatMap((item) => item.values.map(Number))); let body = chart.body;
  series.forEach((item, seriesIndex) => {
    const points = item.values.map((value, index) => ({ x: chart.plot.x + index * chart.plot.w / Math.max(1, categories.length - 1), y: chart.plot.y + chart.plot.h - Number(value) / max * chart.plot.h }));
    body += `<polyline points="${points.map((point) => `${point.x},${point.y}`).join(' ')}" fill="none" stroke="${seriesIndex === 0 ? PALETTE.brand : PALETTE.olive}" stroke-width="${seriesIndex === 0 ? 2.5 : 1.5}"/>${points.map((point) => `<circle cx="${point.x}" cy="${point.y}" r="4" fill="${seriesIndex === 0 ? PALETTE.brand : PALETTE.olive}"/>`).join('')}`;
  });
  categories.forEach((category, index) => { body += text(chart.plot.x + index * chart.plot.w / Math.max(1, categories.length - 1), chart.plot.y + chart.plot.h + 25, category, 'node-subtitle'); });
  return frame(spec, chart.width, chart.height, body, { nodes: [], edges: [] });
}

function polar(cx, cy, radius, angle) { const radians = (angle - 90) * Math.PI / 180; return { x: cx + radius * Math.cos(radians), y: cy + radius * Math.sin(radians) }; }
function renderDonut(spec) {
  const values = spec.values || []; const total = Math.max(1, values.reduce((sum, item) => sum + Number(item.value), 0)); const width = 760; const height = 520; const cx = 300; const cy = 290; const outer = 142; const inner = 78; let angle = 0;
  const colors = [PALETTE.brand, PALETTE.olive, PALETTE.stone, '#b8b7b0', '#d4d3cd', PALETTE.brandTint];
  const arcs = values.map((item, index) => { const span = Number(item.value) / total * 360; const startOuter = polar(cx, cy, outer, angle); const endOuter = polar(cx, cy, outer, angle + span); const startInner = polar(cx, cy, inner, angle + span); const endInner = polar(cx, cy, inner, angle); const large = span > 180 ? 1 : 0; const d = `M ${startOuter.x} ${startOuter.y} A ${outer} ${outer} 0 ${large} 1 ${endOuter.x} ${endOuter.y} L ${startInner.x} ${startInner.y} A ${inner} ${inner} 0 ${large} 0 ${endInner.x} ${endInner.y} Z`; angle += span; return `<path d="${d}" fill="${colors[index % colors.length]}"/>`; }).join('');
  const legend = values.map((item, index) => `<rect x="520" y="${150 + index * 38}" width="12" height="12" rx="2" fill="${colors[index % colors.length]}"/>${text(542, 161 + index * 38, `${item.label} ${item.value}`, 'node-subtitle', 'start')}`).join('');
  return frame(spec, width, height, `${arcs}${text(cx, cy + 6, total, 'node-title')}${legend}`, { nodes: [], edges: [] });
}

function renderCandlestick(spec) {
  const chart = chartScaffold(spec, 900, 520); const values = spec.values || []; const lows = values.map((item) => Number(item.low)); const highs = values.map((item) => Number(item.high)); const min = Math.min(...lows, 0); const max = Math.max(...highs, 1); const scaleY = (value) => chart.plot.y + chart.plot.h - (value - min) / Math.max(1, max - min) * chart.plot.h; const step = chart.plot.w / Math.max(1, values.length); let body = chart.body;
  values.forEach((item, index) => { const x = chart.plot.x + step * (index + .5); const open = scaleY(Number(item.open)); const close = scaleY(Number(item.close)); const high = scaleY(Number(item.high)); const low = scaleY(Number(item.low)); const up = Number(item.close) >= Number(item.open); body += `<line x1="${x}" y1="${high}" x2="${x}" y2="${low}" stroke="${up ? PALETTE.brand : PALETTE.stone}" stroke-width="1.2"/><rect x="${x - Math.min(12, step / 3)}" y="${Math.min(open, close)}" width="${Math.min(24, step * .66)}" height="${Math.max(2, Math.abs(close - open))}" fill="${up ? PALETTE.brand : PALETTE.stone}"/>`; });
  return frame(spec, chart.width, chart.height, body, { nodes: [], edges: [] });
}

function renderWaterfall(spec) {
  const chart = chartScaffold(spec); const values = spec.values || []; let running = 0; const totals = values.map((item) => item.total ? Number(item.value) : (running += Number(item.value))); const max = Math.max(1, ...totals.map(Math.abs)); const step = chart.plot.w / Math.max(1, values.length); let body = chart.body; running = 0;
  values.forEach((item, index) => { const value = Number(item.value); const before = running; if (item.total) running = value; else running += value; const topValue = Math.max(before, running); const bottomValue = Math.min(before, running); const y = chart.plot.y + chart.plot.h - topValue / max * chart.plot.h; const h = Math.max(2, (topValue - bottomValue) / max * chart.plot.h); const x = chart.plot.x + step * index + step * .18; body += `<rect x="${x}" y="${y}" width="${step * .64}" height="${h}" rx="2" fill="${item.total ? PALETTE.nearBlack : value >= 0 ? PALETTE.brand : PALETTE.stone}"/>${text(x + step * .32, chart.plot.y + chart.plot.h + 25, item.label, 'node-subtitle')}`; });
  return frame(spec, chart.width, chart.height, body, { nodes: [], edges: [] });
}

function renderModel(spec, kind) {
  const nodes = (kind === 'class' ? spec.classes : spec.entities) || spec.nodes || [];
  const relationships = spec.relationships || spec.edges || [];
  const mapped = { ...spec, components: nodes.map((node, index) => ({ ...node, id: node.id || slug(node.label), col: node.col ?? index % 3, row: node.row ?? Math.floor(index / 3), sublabel: (node.fields || node.attributes || []).slice(0, 3).join(' · ') })), connections: relationships };
  return renderArchitecture(mapped);
}

export function renderDiagram(spec) {
  switch (spec.diagram_type) {
    case 'architecture': return renderArchitecture(spec);
    case 'architecture-board': return renderBoard(spec);
    case 'workflow': return renderWorkflow(spec);
    case 'sequence': return renderSequence(spec);
    case 'dataflow': return renderDataflow(spec);
    case 'lifecycle': return renderLifecycle(spec);
    case 'quadrant': return renderQuadrant(spec);
    case 'timeline': return renderTimeline(spec);
    case 'tree': return renderTree(spec);
    case 'layer-stack': return renderLayerStack(spec);
    case 'venn': return renderVenn(spec);
    case 'bar': return renderBar(spec);
    case 'line': return renderLine(spec);
    case 'donut': return renderDonut(spec);
    case 'candlestick': return renderCandlestick(spec);
    case 'waterfall': return renderWaterfall(spec);
    case 'class': return renderModel(spec, 'class');
    case 'er': return renderModel(spec, 'er');
    default: throw new Error(`Unsupported diagram type: ${spec.diagram_type}`);
  }
}
