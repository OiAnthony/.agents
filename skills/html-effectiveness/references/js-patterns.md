# JavaScript Patterns

## Data-driven rendering

Define data at the top, render from it. This keeps content separate from
presentation and makes export trivial.

```javascript
var DATA = [
  { id: 'T-101', title: 'Fix auth flow', priority: 'high', status: 'open' },
  // ...
];

function render() {
  container.innerHTML = '';
  DATA.forEach(function(item) {
    var el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = '<h3>' + item.title + '</h3>';
    container.appendChild(el);
  });
}
render();
```

## Clipboard export

Every editor must have an export button:

```javascript
function buildExport() {
  return JSON.stringify(DATA, null, 2);
  // or build Markdown, CSV, etc.
}

exportBtn.addEventListener('click', function() {
  navigator.clipboard.writeText(buildExport()).then(function() {
    exportBtn.textContent = 'Copied';
    exportBtn.classList.add('copied');
    setTimeout(function() {
      exportBtn.textContent = 'Copy';
      exportBtn.classList.remove('copied');
    }, 2000);
  });
});
```

## Closed-loop workflow

HTML artifacts are a **bidirectional interface** between the agent and the
human. The user reads, adjusts, exports, and pastes the result back into the
agent for the next iteration.

```
Agent generates HTML → User opens and adjusts → Export button → Clipboard
→ User pastes back into agent → Agent uses exported data → next iteration
```

Practical implications:

1. **Design the export format first.** Before building the editor, decide what
   the agent/codebase needs: Markdown table? JSON config? A prompt with the
   user's choices filled in?

2. **Use `.prompt-box`** at the top of exploration and research documents to
   show the prompt that generated them.

3. **Export as prompt** is often more useful than export as data. For a triage
   board, "Move BIR-241 to Now because…" as a prompt is more actionable than
   raw JSON.

4. **Multiple export formats** when the audience varies: "Copy as Markdown"
   for planning docs, "Copy as JSON" for config, "Copy as Prompt" for
   continuing the conversation.

## Drag and drop

For triage boards and reorderable lists:

```javascript
card.draggable = true;
card.addEventListener('dragstart', function(e) {
  e.dataTransfer.setData('text/plain', item.id);
  card.classList.add('dragging');
});
dropZone.addEventListener('dragover', function(e) { e.preventDefault(); });
dropZone.addEventListener('drop', function(e) {
  e.preventDefault();
  var id = e.dataTransfer.getData('text/plain');
  // move item, re-render
});
```

## Tab navigation

```javascript
tabs.forEach(function(tab) {
  tab.addEventListener('click', function() {
    tabs.forEach(function(t) { t.classList.remove('active'); });
    tab.classList.add('active');
    panels.forEach(function(p) { p.style.display = 'none'; });
    document.getElementById(tab.dataset.panel).style.display = 'block';
  });
});
```

Tab active: `text-near-black border-b-2 border-brand`
Tab inactive: `text-stone border-b-2 border-transparent hover:text-near-black`

## Slide deck (arrow keys)

```css
body { scroll-snap-type: y mandatory; overflow-y: scroll; }
.slide { width: 100vw; height: 100vh; scroll-snap-align: start; }
```

```javascript
document.addEventListener('keydown', function(e) {
  if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
    e.preventDefault();
    currentSlide = Math.min(currentSlide + 1, slides.length - 1);
    slides[currentSlide].scrollIntoView({ behavior: 'smooth' });
  }
});
```
