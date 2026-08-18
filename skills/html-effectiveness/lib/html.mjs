import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const css = () => fs.readFileSync(path.join(ROOT, 'assets', 'artifact.css'), 'utf8');
const runtime = () => fs.readFileSync(path.join(ROOT, 'assets', 'runtime.js'), 'utf8');
const escapeHtml = (value = '') => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');

function shell({ title, lang = 'en', body, script = '', bodyClass = '' }) {
  return `<!doctype html>
<html lang="${escapeHtml(lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>${escapeHtml(title)}</title>
<style data-artifact-style>${css()}</style>
</head>
<body class="${escapeHtml(bodyClass)}">
${body}
${script ? `<script>${script}</script>` : ''}
</body>
</html>`;
}

const starters = {
  exploration: (title) => `<main class="shell"><header><div class="eyebrow">Exploration</div><h1>${escapeHtml(title)}</h1><p class="lead">State the decision and the constraints.</p></header><section><h2>Options</h2><div class="grid grid-2"><article class="card"><span class="tag">A</span><h3>First option</h3><p>Explain the option, evidence, benefits, and risks.</p></article><article class="card"><span class="tag">B</span><h3>Second option</h3><p>Explain the option, evidence, benefits, and risks.</p></article></div></section><aside class="callout"><h3>Recommendation</h3><p>Name the selected option and the reason.</p></aside></main>`,
  'code-review': (title) => `<main class="shell"><header><div class="eyebrow">Code review</div><h1>${escapeHtml(title)}</h1><p class="lead">Lead with the highest-impact finding.</p></header><div class="metrics"><div class="metric"><span class="metric-value">0</span><span class="metric-label">P0</span></div><div class="metric"><span class="metric-value">0</span><span class="metric-label">P1</span></div></div><section><h2>Findings</h2><article class="card"><h3>Finding title</h3><p>Give the file, line, evidence, impact, and fix.</p><pre><code>// Relevant code</code></pre></article></section></main>`,
  design: (title) => `<main class="shell"><header><div class="eyebrow">Design system</div><h1>${escapeHtml(title)}</h1></header><section><h2>Tokens</h2><div class="grid grid-3"><article class="card"><h3>Color</h3><p>Show color tokens and roles.</p></article><article class="card"><h3>Type</h3><p>Show the type scale.</p></article><article class="card"><h3>Space</h3><p>Show spacing and shape.</p></article></div></section></main>`,
  prototype: (title) => `<main class="shell"><header><div class="eyebrow">Prototype</div><h1>${escapeHtml(title)}</h1><p class="lead">Use the stage to demonstrate one behavior.</p></header><section class="grid grid-2"><div class="card" id="stage"><h2>Stage</h2><p>Interactive preview.</p></div><form class="card"><h2>Controls</h2><label>Value <input type="range" min="0" max="100" value="50"></label></form></section></main>`,
  research: (title) => `<main class="shell"><header><div class="eyebrow">Research</div><h1>${escapeHtml(title)}</h1><p class="lead">State the answer before the evidence.</p></header><section><h2>Key finding</h2><p>Explain the finding and cite the source.</p><details class="card"><summary>Supporting detail</summary><p>Add evidence that some readers can skip.</p></details></section></main>`,
  report: (title) => `<main class="shell"><header><div class="eyebrow">Report</div><h1>${escapeHtml(title)}</h1><p class="lead">State status, change, and required action.</p></header><div class="metrics"><div class="metric"><span class="metric-value">0</span><span class="metric-label">Primary metric</span></div><div class="metric"><span class="metric-value">On track</span><span class="metric-label">Status</span></div></div><section><h2>Current state</h2><article class="card"><h3>Result</h3><p>Report the evidence and consequence.</p></article></section></main>`,
  deck: (title) => `<main><section class="shell" style="min-height:100vh;display:grid;align-content:center"><div class="eyebrow">Presentation</div><h1>${escapeHtml(title)}</h1><p class="lead">One assertion per slide.</p></section><section class="shell" style="min-height:100vh;display:grid;align-content:center"><h2>First assertion</h2><p class="lead">Use evidence, not a list of topics.</p></section></main>`,
  illustration: (title) => `<main class="shell"><header><div class="eyebrow">Diagram</div><h1>${escapeHtml(title)}</h1><p class="lead">Create a diagram JSON specification, then use the deliver command to compile it here.</p></header><section class="card"><h2>Diagram slot</h2><p>No diagram has been compiled.</p></section></main>`,
  editor: (title) => `<main class="shell"><header><div class="eyebrow">Editor</div><h1>${escapeHtml(title)}</h1><p class="lead">Keep state in data, render from data, and export the data.</p></header><div class="card"><label>Content <input id="editor-value" value="Edit this value"></label><button id="export" type="button">Copy JSON</button></div></main>`,
  changelog: (title) => `<main class="shell"><header><div class="eyebrow">Changelog</div><h1>${escapeHtml(title)}</h1><p class="lead">Put breaking changes first.</p></header><section><h2>Changed</h2><ol><li>Describe one user-visible change.</li></ol></section><footer class="doc-footer"><span>Release date</span><span>Project</span></footer></main>`
};

export const ARTIFACT_TYPES = Object.keys(starters);

export function createArtifact(type, title, lang = 'en') {
  if (!starters[type]) throw new Error(`Unknown artifact type: ${type}`);
  let script = '';
  if (type === 'editor') script = `document.getElementById('export').addEventListener('click',async()=>{const data={value:document.getElementById('editor-value').value};await navigator.clipboard.writeText(JSON.stringify(data,null,2));});`;
  return shell({ title, lang, body: starters[type](title), script });
}

function diagramItems(spec) {
  return spec.components || spec.nodes || spec.states || spec.participants || spec.blocks || spec.events || spec.layers || spec.points || spec.sets || spec.classes || spec.entities || [];
}

export function createDiagramArtifact(spec, rendered) {
  const caption = spec.meta.caption ? `<figcaption>${escapeHtml(spec.meta.caption)}</figcaption>` : '';
  const toolbar = `<div class="diagram-toolbar"><input data-diagram-search type="search" aria-label="Search diagram" placeholder="Search nodes"><button type="button" data-action="zoom-out">−</button><button type="button" data-action="zoom-in">+</button><button type="button" data-action="reset">Reset</button><button type="button" data-action="trace">Trace</button><span class="spacer"></span><button type="button" data-action="export-svg">SVG</button><button type="button" data-action="export-png">PNG</button></div>`;
  const nodeIndex = diagramItems(spec).filter((item) => item.id).map((item) => `<button type="button" data-node-target="${escapeHtml(item.id)}">${escapeHtml(item.label)}</button>`).join('');
  const body = `<main class="shell"><header><div class="eyebrow">${escapeHtml(spec.diagram_type)}</div><h1>${escapeHtml(spec.meta.title)}</h1>${spec.meta.subtitle ? `<p class="lead">${escapeHtml(spec.meta.subtitle)}</p>` : ''}</header><figure>${caption}<div class="diagram-shell" data-diagram-shell>${toolbar}<div class="diagram-viewport" role="region" tabindex="0" aria-label="Scrollable diagram canvas">${rendered.svg}</div>${nodeIndex ? `<div class="diagram-node-index" role="group" aria-label="Diagram nodes">${nodeIndex}</div>` : ''}<div class="diagram-detail" data-diagram-detail aria-live="polite">Select a node to inspect its details.</div></div></figure></main>`;
  return shell({ title: spec.meta.title, lang: spec.meta.lang || 'en', body, script: runtime() });
}
