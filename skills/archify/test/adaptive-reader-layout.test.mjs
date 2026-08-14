import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const skillRoot = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(skillRoot, 'assets', 'template.html'), 'utf8');
const skill = fs.readFileSync(path.join(skillRoot, 'SKILL.md'), 'utf8');
const reader = template.slice(
  template.indexOf('Adaptive Reader Shell'),
  template.indexOf('Archify.view = (function ()'),
);

test('wide desktop diagrams use one height-budgeted reader shell instead of breakpoint jumps', () => {
  assert.match(template, /max-width: var\(--archify-reader-width, 1440px\)/);
  assert.doesNotMatch(template, /@media \(min-width: 1680px\)[\s\S]{0,180}\.container/);
  assert.doesNotMatch(template, /@media \(min-width: 1920px\)[\s\S]{0,180}\.container/);
  assert.match(reader, /var WIDE_RATIO = 1\.55/);
  assert.match(reader, /var MAX_READER_WIDTH = 1920/);
  assert.match(reader, /var availableSvgHeight = Math\.max\(1, window\.innerHeight - fixedHeight\)/);
  assert.match(reader, /var desiredWidth = availableSvgHeight \* ratio \+ chrome\.diagramX/);
  assert.match(reader, /html\.style\.setProperty\('--archify-reader-width', rounded \+ 'px'\)/);
});

test('adaptive width preserves canonical SVG geometry and yields to specialized viewer modes', () => {
  assert.match(reader, /window\.innerWidth >= MIN_DESKTOP_WIDTH/);
  assert.match(reader, /html\.getAttribute\('data-embed'\) !== 'true'/);
  assert.match(reader, /html\.getAttribute\('data-present'\) !== 'true'/);
  assert.match(reader, /window\.matchMedia\('print'\)\.matches/);
  assert.doesNotMatch(reader, /svg\.setAttribute\(['"](?:viewBox|width|height)/);
  assert.doesNotMatch(reader, /svg\.style\.(?:width|height)/);
  assert.doesNotMatch(reader, /overflow\s*=\s*['"]hidden/);
});

test('reader remeasures real content and reduces width before allowing desktop page overflow', () => {
  assert.match(reader, /document\.fonts\.ready\.then\(schedule\)/);
  assert.match(reader, /new ResizeObserver\(schedule\)/);
  assert.match(reader, /new MutationObserver\(schedule\)/);
  assert.match(reader, /document\.documentElement\.scrollHeight/);
  assert.match(reader, /lastWidth - overflow \* ratio - 4/);
  assert.match(skill, /1440×900, 1600×1000, and 1920×1080/);
  assert.match(skill, /2048×1320/);
  assert.match(skill, /Generate one responsive artifact for laptops and external displays/);
  assert.match(skill, /preserve the authored SVG\/viewBox, proportions, semantic geometry/);
});
