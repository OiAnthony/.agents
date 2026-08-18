# Interaction Recipes

Beyond basic patterns (tabs, drag-and-drop, slides), these recipes add
tangible delight and comprehension value. Use when the document type calls
for it — don't force them everywhere.

## Hover-linked glossary (research / explainer)

Place a sticky `<aside>` sidebar with a `<dl>` of key terms. In the body text,
wrap terms in `<span class="term" data-term="ring">`. On hover, highlight the
matching `<dt>` in the sidebar.

```javascript
document.querySelectorAll('.term').forEach(function(el) {
  var g = el.dataset.term;
  el.addEventListener('mouseenter', function() {
    document.querySelector('dt[data-g="' + g + '"]')?.classList.add('hl');
  });
  el.addEventListener('mouseleave', function() {
    document.querySelector('dt[data-g="' + g + '"]')?.classList.remove('hl');
  });
});
```

Style `.term` with `border-bottom: 1.5px dotted; cursor: help` and `.hl` on
the sidebar `<dt>` with a subtle brand-tint background.

## CSS custom-property live tuning (prototype / animation sandbox)

Define adjustable parameters as CSS custom properties on `:root`, then let
sliders or preset buttons swap them via `setProperty()`. Every transition
reacts instantly — zero re-render, zero JS animation libraries.

```javascript
var root = document.documentElement;
slider.addEventListener('input', function() {
  root.style.setProperty('--duration', slider.value + 'ms');
});
presetBtn.addEventListener('click', function() {
  root.style.setProperty('--ease', btn.dataset.ease);
});
```

## Dim-not-hide filtering (editor / triage board)

When filtering by tag or category, don't hide non-matching items — set them to
`opacity: 0.25`. This preserves spatial context so the user sees the overall
landscape. Show a colored filter pill in the toolbar that clears on click.

## Micro-delight animations (prototype / editor)

CSS-only confetti, checkmark draw-on, or scale-bounce on state change. Takes
10-15 lines of CSS and zero JS. Use sparingly — one micro-animation per
document, tied to the primary action.

```css
.confetti { position: absolute; width: 6px; height: 6px; border-radius: 2px; opacity: 0; }
.done .confetti { animation: pop 520ms var(--ease) 200ms forwards; }
@keyframes pop {
  0%   { opacity: 0; transform: translate(0,0) scale(0.6); }
  15%  { opacity: 1; }
  100% { opacity: 0; transform: translate(var(--dx),var(--dy)) rotate(var(--rot)) scale(1); }
}
```

Set `--dx`, `--dy`, `--rot` per particle via inline style or numbered classes.
