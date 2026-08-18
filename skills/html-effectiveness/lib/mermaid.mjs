function cleanLabel(value) {
  return String(value || '').trim().replace(/^[[({]+|[\])}]+$/g, '').replace(/^['"]|['"]$/g, '');
}

function id(value) {
  return String(value || '').trim().replace(/[^A-Za-z0-9_-]/g, '_');
}

function parseFlowchart(lines) {
  const nodes = new Map(); const edges = [];
  const edgePattern = /^\s*([A-Za-z0-9_-]+)(?:\[([^\]]+)\]|\(([^)]+)\)|\{([^}]+)\})?\s*(-->|---|-.->|==>)\s*(?:\|([^|]+)\|\s*)?([A-Za-z0-9_-]+)(?:\[([^\]]+)\]|\(([^)]+)\)|\{([^}]+)\})?/;
  lines.forEach((line) => {
    const match = line.match(edgePattern); if (!match) return;
    const from = id(match[1]); const to = id(match[7]);
    nodes.set(from, { id: from, label: cleanLabel(match[2] || match[3] || match[4] || from) });
    nodes.set(to, { id: to, label: cleanLabel(match[8] || match[9] || match[10] || to) });
    edges.push({ from, to, label: cleanLabel(match[6] || ''), role: match[5] === '-.->' ? 'async' : match[5] === '==>' ? 'main' : 'branch' });
  });
  const ordered = [...nodes.values()].map((node, index) => ({ ...node, lane: 'main', col: index }));
  return { diagram_type: 'workflow', meta: { title: 'Imported workflow', density: 'teaching' }, lanes: [{ id: 'main', label: 'Flow' }], nodes: ordered, edges };
}

function parseSequence(lines) {
  const participants = new Map(); const messages = [];
  lines.forEach((line) => {
    let match = line.match(/^\s*participant\s+([A-Za-z0-9_-]+)(?:\s+as\s+(.+))?/i);
    if (match) { participants.set(match[1], { id: match[1], label: cleanLabel(match[2] || match[1]) }); return; }
    match = line.match(/^\s*([A-Za-z0-9_][A-Za-z0-9_-]*?)\s*(-->>|->>|-->|->)\s*([A-Za-z0-9_][A-Za-z0-9_-]*)\s*:\s*(.+)$/);
    if (!match) return;
    const from = match[1]; const to = match[3];
    if (!participants.has(from)) participants.set(from, { id: from, label: from });
    if (!participants.has(to)) participants.set(to, { id: to, label: to });
    messages.push({ from, to, label: cleanLabel(match[4]), variant: match[2].includes('--') ? 'return' : 'default' });
  });
  return { diagram_type: 'sequence', meta: { title: 'Imported sequence', density: 'teaching' }, participants: [...participants.values()], messages };
}

function parseState(lines) {
  const states = new Map(); const transitions = [];
  function ensureState(raw) {
    const trimmed = String(raw).trim();
    const terminal = trimmed === '[*]';
    const stateId = terminal ? (states.has('start') ? 'end' : 'start') : id(cleanLabel(trimmed));
    if (!states.has(stateId)) {
      states.set(stateId, {
        id: stateId,
        label: terminal ? (stateId === 'start' ? 'Start' : 'End') : cleanLabel(trimmed),
        type: stateId === 'start' ? 'start' : stateId === 'end' ? 'success' : 'active',
        lane: 'main',
        col: Math.min(4, states.size)
      });
    }
    return stateId;
  }
  lines.forEach((line) => {
    const match = line.match(/^\s*([^:]+?)\s*-->\s*([^:]+?)(?:\s*:\s*(.+))?$/); if (!match) return;
    const from = ensureState(match[1]); const to = ensureState(match[2]);
    transitions.push({ from, to, label: cleanLabel(match[3] || '') });
  });
  return { diagram_type: 'lifecycle', meta: { title: 'Imported lifecycle', density: 'teaching' }, lanes: [{ id: 'main', label: 'Lifecycle' }], states: [...states.values()], transitions };
}

function parseClass(lines) {
  const classes = new Map(); const relationships = [];
  lines.forEach((line) => {
    let match = line.match(/^\s*class\s+([A-Za-z0-9_-]+)/); if (match) { classes.set(match[1], { id: match[1], label: match[1], attributes: [] }); return; }
    match = line.match(/^\s*([A-Za-z0-9_-]+)\s*(<\|--|\*--|o--|-->|--)\s*([A-Za-z0-9_-]+)/); if (!match) return;
    [match[1], match[3]].forEach((name) => { if (!classes.has(name)) classes.set(name, { id: name, label: name, attributes: [] }); });
    relationships.push({ from: match[1], to: match[3], label: match[2] });
  });
  return { diagram_type: 'class', meta: { title: 'Imported class model', density: 'teaching' }, classes: [...classes.values()], relationships };
}

function parseEr(lines) {
  const entities = new Map(); const relationships = [];
  lines.forEach((line) => {
    const match = line.match(/^\s*([A-Za-z0-9_-]+)\s+([|}{o]+--[|}{o]+)\s+([A-Za-z0-9_-]+)\s*:\s*(.*)$/); if (!match) return;
    [match[1], match[3]].forEach((name) => { if (!entities.has(name)) entities.set(name, { id: name, label: name, fields: [] }); });
    relationships.push({ from: match[1], to: match[3], label: cleanLabel(match[4]) });
  });
  return { diagram_type: 'er', meta: { title: 'Imported entity relationship model', density: 'teaching' }, entities: [...entities.values()], relationships };
}

function parseXy(lines) {
  const categoriesLine = lines.find((line) => /x-axis/i.test(line));
  const valuesLine = lines.find((line) => /^\s*(bar|line)\s+/i.test(line));
  const categories = categoriesLine?.match(/\[([^\]]+)\]/)?.[1]?.split(',').map(cleanLabel) || [];
  const values = valuesLine?.match(/\[([^\]]+)\]/)?.[1]?.split(',').map(Number) || [];
  const type = /^\s*line/i.test(valuesLine || '') ? 'line' : 'bar';
  return { diagram_type: type, meta: { title: 'Imported chart', density: 'editorial' }, categories, series: [{ name: 'Value', values }] };
}

export function parseMermaid(source) {
  const lines = source.split(/\r?\n/).filter((line) => line.trim() && !line.trim().startsWith('%%'));
  const first = lines[0]?.trim() || '';
  if (/^(graph|flowchart)\b/i.test(first)) return parseFlowchart(lines.slice(1));
  if (/^sequenceDiagram\b/i.test(first)) return parseSequence(lines.slice(1));
  if (/^stateDiagram/i.test(first)) return parseState(lines.slice(1));
  if (/^classDiagram/i.test(first)) return parseClass(lines.slice(1));
  if (/^erDiagram/i.test(first)) return parseEr(lines.slice(1));
  if (/^xychart-beta/i.test(first)) return parseXy(lines.slice(1));
  throw new Error('Unsupported Mermaid diagram. Use flowchart, sequenceDiagram, stateDiagram-v2, classDiagram, erDiagram, or xychart-beta.');
}
