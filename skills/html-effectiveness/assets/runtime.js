(function () {
  'use strict';

  function download(name, blob) {
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  function serializeSvg(svg) {
    const copy = svg.cloneNode(true);
    copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    const style = document.querySelector('style[data-artifact-style]');
    if (style) {
      const node = document.createElementNS('http://www.w3.org/2000/svg', 'style');
      node.textContent = style.textContent;
      copy.insertBefore(node, copy.firstChild);
    }
    return new XMLSerializer().serializeToString(copy);
  }

  document.querySelectorAll('[data-diagram-shell]').forEach(function (shell, index) {
    const svg = shell.querySelector('svg.diagram');
    if (!svg) return;
    const input = shell.querySelector('[data-diagram-search]');
    const detail = shell.querySelector('[data-diagram-detail]');
    const originalViewBox = svg.getAttribute('viewBox').split(/\s+/).map(Number);
    let zoom = 1;

    function setZoom(next) {
      zoom = Math.max(0.55, Math.min(2.5, next));
      const width = originalViewBox[2] / zoom;
      const height = originalViewBox[3] / zoom;
      const x = originalViewBox[0] + (originalViewBox[2] - width) / 2;
      const y = originalViewBox[1] + (originalViewBox[3] - height) / 2;
      svg.setAttribute('viewBox', [x, y, width, height].join(' '));
    }

    shell.addEventListener('click', function (event) {
      const action = event.target.closest('[data-action]');
      if (action) {
        const name = action.dataset.action;
        if (name === 'zoom-in') setZoom(zoom * 1.2);
        if (name === 'zoom-out') setZoom(zoom / 1.2);
        if (name === 'reset') { zoom = 1; svg.setAttribute('viewBox', originalViewBox.join(' ')); }
        if (name === 'trace') {
          svg.classList.toggle('trace-mode');
          svg.querySelectorAll('.edge').forEach(function (edge) { edge.classList.toggle('trace'); });
        }
        if (name === 'export-svg') {
          download((svg.dataset.title || 'diagram') + '.svg', new Blob([serializeSvg(svg)], { type: 'image/svg+xml' }));
        }
        if (name === 'export-png') {
          const image = new Image();
          const source = serializeSvg(svg);
          const url = URL.createObjectURL(new Blob([source], { type: 'image/svg+xml' }));
          image.onload = function () {
            const canvas = document.createElement('canvas');
            canvas.width = Math.max(1600, originalViewBox[2] * 2);
            canvas.height = canvas.width * originalViewBox[3] / originalViewBox[2];
            const context = canvas.getContext('2d');
            context.fillStyle = '#f5f4ed';
            context.fillRect(0, 0, canvas.width, canvas.height);
            context.drawImage(image, 0, 0, canvas.width, canvas.height);
            canvas.toBlob(function (blob) { if (blob) download((svg.dataset.title || 'diagram') + '.png', blob); });
            URL.revokeObjectURL(url);
          };
          image.src = url;
        }
        return;
      }

      const targetButton = event.target.closest('[data-node-target]');
      const node = targetButton
        ? svg.querySelector(`[data-node-id="${CSS.escape(targetButton.dataset.nodeTarget)}"]`)
        : event.target.closest('.node');
      if (!node) return;
      svg.querySelectorAll('.node.selected').forEach(function (item) { item.classList.remove('selected'); });
      node.classList.add('selected');
      if (detail) detail.textContent = node.dataset.detail || node.dataset.label || 'No additional detail.';
    });

    if (input) {
      input.addEventListener('input', function () {
        const query = input.value.trim().toLowerCase();
        svg.classList.toggle('searching', Boolean(query));
        svg.querySelectorAll('.node').forEach(function (node) {
          node.classList.toggle('match', !query || (node.textContent + ' ' + (node.dataset.detail || '')).toLowerCase().includes(query));
        });
      });
    }

    if (detail && !detail.id) detail.id = 'diagram-detail-' + index;
  });
})();
