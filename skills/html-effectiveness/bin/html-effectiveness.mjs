#!/usr/bin/env node
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ARTIFACT_TYPES, createArtifact, createDiagramArtifact } from '../lib/html.mjs';
import { DIAGRAM_TYPES } from '../lib/render.mjs';
import { parseMermaid } from '../lib/mermaid.mjs';
import { validateHtml, validateSpec } from '../lib/validate.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [command, ...args] = process.argv.slice(2);
const sha256 = (value) => crypto.createHash('sha256').update(value).digest('hex');
const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'));
const writeFile = (file, value) => { fs.mkdirSync(path.dirname(path.resolve(file)), { recursive: true }); fs.writeFileSync(file, value); };
const output = (value) => process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
const fail = (message, details = {}) => { output({ ok: false, error: message, ...details }); process.exitCode = 1; };

function usage() {
  process.stdout.write(`HTML Effectiveness\n\nCommands:\n  list\n  guide <scenario>\n  init <artifact-type> <title> <output.html> [lang]\n  validate <spec.json|artifact.html>\n  deliver <spec.json> <output.html>\n  convert-mermaid <input.mmd> <output.json>\n  doctor\n`);
}

function guide(scenario) {
  const value = scenario.toLowerCase();
  const rules = [
    [/etl|lineage|pipeline|data flow|数据流|血缘/, 'dataflow'],
    [/sequence|api call|request lifecycle|时序|调用链/, 'sequence'],
    [/state|lifecycle|retry|状态|生命周期/, 'lifecycle'],
    [/workflow|approval|ci\/cd|流程|审批|泳道/, 'workflow'],
    [/architecture board|platform panorama|control plane|架构总览|控制面/, 'architecture-board'],
    [/architecture|infrastructure|topology|架构|拓扑/, 'architecture'],
    [/quadrant|priority matrix|象限/, 'quadrant'],
    [/timeline|roadmap|milestone|时间线|里程碑/, 'timeline'],
    [/tree|hierarchy|org chart|树|层级/, 'tree'],
    [/layer|stack|osi|分层/, 'layer-stack'],
    [/venn|intersection|交集/, 'venn'],
    [/candlestick|ohlc|k线|蜡烛/, 'candlestick'],
    [/waterfall|bridge|瀑布/, 'waterfall'],
    [/share|proportion|占比|构成/, 'donut'],
    [/trend|time series|趋势/, 'line'],
    [/compare|category|比较|分类/, 'bar'],
    [/class diagram|类图/, 'class'],
    [/er diagram|entity relationship|实体关系/, 'er']
  ];
  const match = rules.find(([pattern]) => pattern.test(value));
  return match?.[1] || 'architecture';
}

if (!command || command === 'help' || command === '--help') usage();
else if (command === 'list') output({ artifact_types: ARTIFACT_TYPES, diagram_types: DIAGRAM_TYPES });
else if (command === 'guide') {
  const scenario = args.join(' '); if (!scenario) fail('guide requires a scenario.'); else output({ ok: true, diagram_type: guide(scenario) });
} else if (command === 'init') {
  const [type, title, file, lang = 'en'] = args;
  if (!type || !title || !file) fail('init requires <artifact-type> <title> <output.html>.');
  else {
    try { const html = createArtifact(type, title, lang); writeFile(file, html); output({ ok: true, artifact_type: type, output: path.resolve(file), bytes: Buffer.byteLength(html), sha256: sha256(html) }); }
    catch (error) { fail(error.message); }
  }
} else if (command === 'validate') {
  const [file] = args;
  if (!file) fail('validate requires a JSON specification or HTML artifact.');
  else {
    try {
      const source = fs.readFileSync(file, 'utf8');
      if (file.endsWith('.json')) {
        const result = validateSpec(JSON.parse(source));
        output({ ok: result.ok, errors: result.errors, warnings: result.warnings, checks: { semantic: true, budgets: true, geometry: Boolean(result.rendered) } });
        if (!result.ok) process.exitCode = 1;
      } else {
        const result = validateHtml(source); output({ ...result, checks: { self_contained: true, metadata: true, accessibility: true } }); if (!result.ok) process.exitCode = 1;
      }
    } catch (error) { fail(error.message); }
  }
} else if (command === 'deliver') {
  const [input, file] = args;
  if (!input || !file) fail('deliver requires <spec.json> <output.html>.');
  else {
    try {
      const specSource = fs.readFileSync(input, 'utf8'); const spec = JSON.parse(specSource); const checked = validateSpec(spec);
      if (!checked.ok) fail('Specification validation failed.', { errors: checked.errors, warnings: checked.warnings });
      else {
        const html = createDiagramArtifact(spec, checked.rendered); const htmlChecked = validateHtml(html);
        if (!htmlChecked.ok) fail('Artifact validation failed.', { errors: htmlChecked.errors, warnings: htmlChecked.warnings });
        else {
          writeFile(file, html);
          output({ ok: true, diagram_type: spec.diagram_type, output: path.resolve(file), checks: { semantic: true, budgets: true, geometry: true, self_contained: true, accessibility: true }, warnings: [...checked.warnings, ...htmlChecked.warnings], receipt: { spec_sha256: sha256(specSource), artifact_sha256: sha256(html), spec_bytes: Buffer.byteLength(specSource), artifact_bytes: Buffer.byteLength(html) } });
        }
      }
    } catch (error) { fail(error.message); }
  }
} else if (command === 'convert-mermaid') {
  const [input, file] = args;
  if (!input || !file) fail('convert-mermaid requires <input.mmd> <output.json>.');
  else {
    try { const spec = parseMermaid(fs.readFileSync(input, 'utf8')); const checked = validateSpec(spec); if (!checked.ok) fail('Converted Mermaid is invalid.', { errors: checked.errors }); else { writeFile(file, `${JSON.stringify(spec, null, 2)}\n`); output({ ok: true, diagram_type: spec.diagram_type, output: path.resolve(file), warnings: checked.warnings }); } }
    catch (error) { fail(error.message); }
  }
} else if (command === 'doctor') {
  const files = ['assets/artifact.css', 'assets/runtime.js', 'schemas/diagram.schema.json', 'lib/render.mjs', 'lib/validate.mjs'].map((file) => ({ file, present: fs.existsSync(path.join(ROOT, file)) }));
  const ok = files.every((item) => item.present);
  output({ ok, node: process.version, root: ROOT, files }); if (!ok) process.exitCode = 1;
} else fail(`Unknown command: ${command}.`);
