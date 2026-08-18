import assert from 'node:assert/strict';
import test from 'node:test';
import { createArtifact, createDiagramArtifact } from '../lib/html.mjs';
import { parseMermaid } from '../lib/mermaid.mjs';
import { DIAGRAM_TYPES, renderDiagram } from '../lib/render.mjs';
import { validateHtml, validateSpec } from '../lib/validate.mjs';

const meta = (title, density = 'editorial') => ({ title, description: `${title} accessible description.`, density });

const fixtures = {
  architecture: { diagram_type: 'architecture', meta: meta('Architecture'), components: [{ id: 'a', label: 'Client', col: 0, row: 0 }, { id: 'b', label: 'Service', col: 1, row: 0, focal: true }], connections: [{ from: 'a', to: 'b', label: 'Request' }] },
  'architecture-board': { diagram_type: 'architecture-board', meta: meta('Board', 'board'), sections: [{ id: 'business', label: 'Business' }, { id: 'runtime', label: 'Runtime' }], blocks: [{ id: 'users', label: 'Users', section: 'business' }, { id: 'api', label: 'API', section: 'runtime', focal: true }] },
  workflow: { diagram_type: 'workflow', meta: meta('Workflow'), lanes: [{ id: 'user', label: 'User' }, { id: 'system', label: 'System' }], nodes: [{ id: 'request', label: 'Request', lane: 'user', col: 0 }, { id: 'process', label: 'Process', lane: 'system', col: 1, focal: true }], edges: [{ from: 'request', to: 'process', role: 'main' }] },
  sequence: { diagram_type: 'sequence', meta: meta('Sequence'), participants: [{ id: 'client', label: 'Client' }, { id: 'api', label: 'API' }], messages: [{ from: 'client', to: 'api', label: 'Call' }, { from: 'api', to: 'client', label: 'Result', variant: 'return' }] },
  dataflow: { diagram_type: 'dataflow', meta: meta('Dataflow'), stages: [{ label: 'Source' }, { label: 'Use' }], nodes: [{ id: 'source', label: 'Source', stage: 0, row: 0 }, { id: 'sink', label: 'Sink', stage: 1, row: 0, focal: true }], flows: [{ from: 'source', to: 'sink', label: 'Events' }] },
  lifecycle: { diagram_type: 'lifecycle', meta: meta('Lifecycle'), lanes: [{ id: 'main', label: 'Task' }], states: [{ id: 'start', label: 'Start', type: 'start', lane: 'main', col: 0 }, { id: 'done', label: 'Done', type: 'success', lane: 'main', col: 1 }], transitions: [{ from: 'start', to: 'done', label: 'Complete' }] },
  quadrant: { diagram_type: 'quadrant', meta: meta('Quadrant'), axes: { x: 'Effort', y: 'Value' }, points: [{ id: 'p1', label: 'Choice', x: 0.7, y: 0.8, focal: true }] },
  timeline: { diagram_type: 'timeline', meta: meta('Timeline'), events: [{ id: 'e1', label: 'Start', date: 'Q1' }, { id: 'e2', label: 'Finish', date: 'Q2', focal: true }] },
  tree: { diagram_type: 'tree', meta: meta('Tree'), nodes: [{ id: 'root', label: 'Root' }, { id: 'child', label: 'Child', parent: 'root' }] },
  'layer-stack': { diagram_type: 'layer-stack', meta: meta('Layers'), layers: [{ id: 'surface', label: 'Surface' }, { id: 'runtime', label: 'Runtime', focal: true }] },
  venn: { diagram_type: 'venn', meta: meta('Venn'), sets: [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }] },
  bar: { diagram_type: 'bar', meta: meta('Bar'), categories: ['A', 'B'], series: [{ name: 'Value', values: [3, 5] }] },
  line: { diagram_type: 'line', meta: meta('Line'), categories: ['Q1', 'Q2'], series: [{ name: 'Value', values: [3, 5] }] },
  donut: { diagram_type: 'donut', meta: meta('Donut'), values: [{ label: 'A', value: 60 }, { label: 'B', value: 40 }] },
  candlestick: { diagram_type: 'candlestick', meta: meta('Candlestick'), values: [{ label: 'D1', open: 10, high: 14, low: 9, close: 13 }, { label: 'D2', open: 13, high: 15, low: 11, close: 12 }] },
  waterfall: { diagram_type: 'waterfall', meta: meta('Waterfall'), values: [{ label: 'Base', value: 100, total: true }, { label: 'Growth', value: 20 }, { label: 'Cost', value: -10 }] },
  class: { diagram_type: 'class', meta: meta('Class'), classes: [{ id: 'user', label: 'User', attributes: ['id'] }, { id: 'team', label: 'Team', attributes: ['id'] }], relationships: [{ from: 'user', to: 'team', label: 'belongs to' }] },
  er: { diagram_type: 'er', meta: meta('ER'), entities: [{ id: 'user', label: 'User', fields: ['id'] }, { id: 'order', label: 'Order', fields: ['id'] }], relationships: [{ from: 'user', to: 'order', label: 'places' }] }
};

test('all documented diagram types render and validate', () => {
  assert.deepEqual(Object.keys(fixtures).sort(), [...DIAGRAM_TYPES].sort());
  for (const type of DIAGRAM_TYPES) {
    const result = validateSpec({ schema_version: 1, ...fixtures[type] });
    assert.equal(result.ok, true, `${type}: ${result.errors.join('; ')}`);
    assert.match(result.rendered.svg, /role="img"/);
    assert.match(result.rendered.svg, /<title/);
    assert.match(result.rendered.svg, /<desc/);
  }
});

test('delivered diagram is self-contained and accessible', () => {
  const checked = validateSpec({ schema_version: 1, ...fixtures.architecture });
  const html = createDiagramArtifact(fixtures.architecture, checked.rendered);
  const result = validateHtml(html);
  assert.equal(result.ok, true, result.errors.join('; '));
  assert.doesNotMatch(html, /<script[^>]+src=/i);
  assert.doesNotMatch(html, /https:\/\/(?:cdn|esm\.)/i);
});

test('artifact scaffolds are self-contained', () => {
  for (const type of ['exploration', 'code-review', 'design', 'prototype', 'research', 'report', 'deck', 'illustration', 'editor', 'changelog']) {
    const html = createArtifact(type, `Test ${type}`, 'en');
    const result = validateHtml(html);
    assert.equal(result.ok, true, `${type}: ${result.errors.join('; ')}`);
  }
});

test('Mermaid adapters produce native specifications', () => {
  const sources = [
    ['flowchart LR\nA[Start] --> B[Finish]', 'workflow'],
    ['sequenceDiagram\nA->>B: Call', 'sequence'],
    ['stateDiagram-v2\n[*] --> Ready\nReady --> [*]', 'lifecycle'],
    ['classDiagram\nclass User\nUser --> Team', 'class'],
    ['erDiagram\nUSER ||--o{ ORDER : places', 'er'],
    ['xychart-beta\nx-axis [Q1, Q2]\nbar [3, 5]', 'bar']
  ];
  sources.forEach(([source, type]) => {
    const spec = parseMermaid(source);
    assert.equal(spec.diagram_type, type);
    const result = validateSpec({ schema_version: 1, ...spec });
    assert.equal(result.ok, true, `${type}: ${result.errors.join('; ')}`);
  });

  const sequence = parseMermaid('sequenceDiagram\nparticipant A\nparticipant B\nA-->>B: Result');
  assert.deepEqual(sequence.participants.map((item) => item.id), ['A', 'B']);
  assert.deepEqual(sequence.messages, [{ from: 'A', to: 'B', label: 'Result', variant: 'return' }]);
});

test('invalid density, chart, and geometry inputs fail', () => {
  const crowded = { diagram_type: 'architecture', meta: meta('Crowded'), components: Array.from({ length: 10 }, (_, index) => ({ id: `n${index}`, label: `N${index}` })), connections: [] };
  assert.equal(validateSpec(crowded).ok, false);
  const donut = { diagram_type: 'donut', meta: meta('Crowded donut'), values: Array.from({ length: 7 }, (_, index) => ({ label: `S${index}`, value: 1 })) };
  assert.equal(validateSpec(donut).ok, false);

  const offCanvas = { diagram_type: 'architecture', meta: meta('Off canvas'), components: [{ id: 'node', label: 'Node', col: 10, row: 0 }] };
  assert.match(validateSpec(offCanvas).errors.join('; '), /outside the .* viewBox/);

  const crowdedBoard = {
    diagram_type: 'architecture-board',
    meta: meta('Crowded board', 'board'),
    sections: [{ id: 'main', label: 'Main' }],
    blocks: Array.from({ length: 25 }, (_, index) => ({ id: `b${index}`, label: `Block ${index}`, section: 'main' }))
  };
  assert.match(validateSpec(crowdedBoard).errors.join('; '), /too small to render legibly/);
});

test('remote CSS resources fail self-contained validation', () => {
  const html = '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width"><title>Remote font</title><style>@font-face{src:url(https://example.com/font.woff2)}</style></head><body></body></html>';
  const result = validateHtml(html);
  assert.equal(result.ok, false);
  assert.match(result.errors.join('; '), /External resource pattern found/);
});
