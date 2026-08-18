import { DIAGRAM_TYPES, renderDiagram } from './render.mjs';

const budgets = {
  editorial: 9,
  teaching: 12,
  board: 25
};

function itemsFor(spec) {
  return spec.components || spec.nodes || spec.states || spec.participants || spec.blocks || spec.events || spec.layers || spec.points || spec.sets || spec.classes || spec.entities || [];
}

function edgesFor(spec) {
  return spec.connections || spec.edges || spec.transitions || spec.messages || spec.flows || spec.relationships || [];
}

function segmentIntersectsRect(a, b, rect) {
  if (a.x === b.x) {
    return a.x > rect.x && a.x < rect.x + rect.w && Math.max(a.y, b.y) > rect.y && Math.min(a.y, b.y) < rect.y + rect.h;
  }
  if (a.y === b.y) {
    return a.y > rect.y && a.y < rect.y + rect.h && Math.max(a.x, b.x) > rect.x && Math.min(a.x, b.x) < rect.x + rect.w;
  }
  return false;
}

export function validateSpec(spec) {
  const errors = [];
  const warnings = [];
  if (!spec || typeof spec !== 'object' || Array.isArray(spec)) errors.push('Specification must be an object.');
  if (!DIAGRAM_TYPES.includes(spec?.diagram_type)) errors.push(`diagram_type must be one of: ${DIAGRAM_TYPES.join(', ')}.`);
  if (!spec?.meta?.title?.trim()) errors.push('meta.title is required.');
  if (spec?.schema_version !== undefined && spec.schema_version !== 1) errors.push('schema_version must be 1.');

  const items = itemsFor(spec || {});
  const ids = new Set();
  items.forEach((item, index) => {
    if (!item.id && !['timeline', 'layer-stack', 'quadrant', 'venn'].includes(spec.diagram_type)) errors.push(`Item ${index} requires id.`);
    if (!item.label) errors.push(`Item ${item.id || index} requires label.`);
    if (item.id && ids.has(item.id)) errors.push(`Duplicate item id: ${item.id}.`);
    if (item.id) ids.add(item.id);
    if (String(item.label || '').length > 36) warnings.push(`Label is long and can wrap poorly: ${item.label}.`);
    if (String(item.description || item.detail || '').length > 140) warnings.push(`Node detail is too long: ${item.id || item.label}.`);
  });

  edgesFor(spec || {}).forEach((edge, index) => {
    if (!edge.from || !edge.to) errors.push(`Relationship ${index} requires from and to.`);
    if (ids.size && edge.from && !ids.has(edge.from)) errors.push(`Relationship ${index} has unknown source: ${edge.from}.`);
    if (ids.size && edge.to && !ids.has(edge.to)) errors.push(`Relationship ${index} has unknown target: ${edge.to}.`);
  });

  const density = spec?.meta?.density || (spec?.diagram_type === 'architecture-board' ? 'board' : 'editorial');
  const budget = budgets[density] || budgets.editorial;
  if (items.length > budget) errors.push(`${spec.diagram_type} has ${items.length} primary items; ${density} budget is ${budget}. Split or merge the diagram.`);
  const focalCount = items.filter((item) => item.focal || item.variant === 'emphasis').length;
  if (focalCount > 2) warnings.push(`The diagram has ${focalCount} focal items; use at most 2.`);

  if (spec?.diagram_type === 'donut' && (spec.values || []).length > 6) errors.push('Donut charts support at most 6 segments. Use a bar chart.');
  if (spec?.diagram_type === 'bar' && (spec.categories || []).length > 8) errors.push('Bar charts support at most 8 categories.');
  if (spec?.diagram_type === 'line' && (spec.categories || []).length > 12) errors.push('Line charts support at most 12 points.');
  if (spec?.diagram_type === 'candlestick' && (spec.values || []).length > 30) errors.push('Candlestick charts support at most 30 periods.');
  if (spec?.diagram_type === 'waterfall' && (spec.values || []).length > 8) errors.push('Waterfall charts support at most 8 steps.');
  if (spec?.diagram_type === 'venn' && (spec.sets || []).length > 3) errors.push('Venn diagrams support at most 3 sets.');

  let rendered;
  if (!errors.length) {
    try { rendered = renderDiagram(spec); } catch (error) { errors.push(`Renderer failed: ${error.message}`); }
  }

  if (rendered) {
    const nodes = rendered.geometry.nodes;
    nodes.forEach((node) => {
      if (node.w < 96 || node.h < 44) errors.push(`Node ${node.id} is too small to render legibly (${node.w}x${node.h}).`);
      if (node.x < 0 || node.y < 0 || node.x + node.w > rendered.width || node.y + node.h > rendered.height) {
        errors.push(`Node ${node.id} is outside the ${rendered.width}x${rendered.height} viewBox.`);
      }
    });
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i]; const b = nodes[j];
        const overlaps = a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
        if (overlaps) errors.push(`Nodes overlap: ${a.id} and ${b.id}.`);
      }
    }
    rendered.geometry.edges.forEach((edge) => {
      nodes.filter((node) => node.id !== edge.from && node.id !== edge.to).forEach((node) => {
        for (let index = 1; index < edge.points.length; index += 1) {
          if (segmentIntersectsRect(edge.points[index - 1], edge.points[index], node)) {
            errors.push(`Relationship ${edge.from} -> ${edge.to} crosses node ${node.id}.`);
            break;
          }
        }
      });
      for (let index = 1; index < edge.points.length; index += 1) {
        const a = edge.points[index - 1]; const b = edge.points[index];
        if (Math.hypot(b.x - a.x, b.y - a.y) > 0 && Math.hypot(b.x - a.x, b.y - a.y) < 8) warnings.push(`Relationship ${edge.from} -> ${edge.to} has a segment shorter than 8px.`);
      }
    });
  }

  return { ok: errors.length === 0, errors, warnings, rendered };
}

export function validateHtml(html) {
  const errors = [];
  const warnings = [];
  const externalPatterns = [
    /<script\b[^>]*\bsrc\s*=/i,
    /<link\b[^>]*\bhref\s*=/i,
    /<(?:img|iframe|video|audio|source)\b[^>]*\bsrc\s*=\s*["']https?:/i,
    /@import\s+/i,
    /url\s*\(\s*["']?\s*https?:/i,
    /\b(?:fetch|import)\s*\(\s*["']https?:/i
  ];
  externalPatterns.forEach((pattern) => { if (pattern.test(html)) errors.push(`External resource pattern found: ${pattern}.`); });
  if (/\{\{[A-Z0-9_]+\}\}/.test(html)) errors.push('Unfilled template placeholders remain.');
  if (!/<meta\s+name=["']viewport["']/.test(html)) errors.push('Viewport metadata is missing.');
  if (!/<html\s+lang=["'][^"']+/.test(html)) errors.push('Document language is missing.');
  if (!/<title>[^<]+<\/title>/.test(html)) errors.push('Document title is missing.');
  if (/<svg\b/.test(html) && !/<svg\b[^>]*\brole=["']img["']/.test(html)) errors.push('SVG diagram requires role="img".');
  if (/<svg\b/.test(html) && (!/<title\b/.test(html) || !/<desc\b/.test(html))) errors.push('SVG diagram requires title and desc.');
  if (/font-weight\s*:\s*[789]00/.test(html)) warnings.push('Heavy font weight found.');
  if (/\b(?:linear|radial)-gradient\s*\(/.test(html)) warnings.push('Gradient found; diagrams use solid fills.');
  return { ok: errors.length === 0, errors, warnings };
}
