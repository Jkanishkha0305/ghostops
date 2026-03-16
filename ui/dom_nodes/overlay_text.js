export function createOverlayTextRoot(textLayer, textId, onDblClick) {
  const el = document.createElement('div');
  el.className = 'overlay-text';
  el.dataset.textId = textId;
  if (onDblClick) {
    el.addEventListener('dblclick', onDblClick);
  }
  textLayer.appendChild(el);
  const { bubble, textEl } = ensureOverlayTextBubble(el);
  return { el, bubble, textEl };
}

export function ensureOverlayTextBubble(root) {
  let bubble = root.querySelector('.ai-ar-panel');
  if (!bubble) {
    bubble = document.createElement('div');
    bubble.className = 'ai-ar-panel';

    const textEl = document.createElement('div');
    textEl.className = 'ai-ar-text';
    bubble.appendChild(textEl);
    root.replaceChildren(bubble);

    _attachDrag(root, bubble);
  }
  const textEl = bubble.querySelector('.ai-ar-text');
  return { bubble, textEl };
}

function _attachDrag(root, bubble) {
  // Drag from anywhere on the bubble EXCEPT the selectable text content
  bubble.addEventListener('mousedown', (e) => {
    // Let text selection work normally on the text node itself
    if (e.target.closest('.ai-ar-text')) return;
    if (e.button !== 0) return;

    e.preventDefault();
    e.stopPropagation();

    // Tell the hit-test system to keep the window interactive during drag
    window.overlaySetDragging?.(true);

    // getBoundingClientRect already accounts for CSS transforms
    const rect = root.getBoundingClientRect();
    const origLeft = rect.left;
    const origTop = rect.top;

    // Replace transform with explicit pixel coords so the move math is simple
    root.style.transform = 'none';
    root.style.setProperty('--text-translate-x', '0%');
    root.style.setProperty('--text-translate-y', '0%');
    root.style.left = `${origLeft}px`;
    root.style.top = `${origTop}px`;

    const startX = e.clientX;
    const startY = e.clientY;

    const onMove = (ev) => {
      root.style.left = `${origLeft + ev.clientX - startX}px`;
      root.style.top = `${origTop + ev.clientY - startY}px`;
    };

    const onUp = () => {
      window.overlaySetDragging?.(false);
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}

export function ensureModelMeta(bubble) {
  let meta = bubble.querySelector('.ai-model-meta');
  if (!meta) {
    meta = document.createElement('div');
    meta.className = 'ai-model-meta';
    const nameEl = document.createElement('div');
    nameEl.className = 'ai-model-name';
    const lineEl = document.createElement('div');
    lineEl.className = 'ai-model-divider';
    meta.appendChild(nameEl);
    meta.appendChild(lineEl);
    bubble.insertBefore(meta, bubble.firstChild);
  }
  const nameEl = meta.querySelector('.ai-model-name');
  return { meta, nameEl };
}

export function removeModelMeta(bubble) {
  const meta = bubble.querySelector('.ai-model-meta');
  if (meta) {
    meta.remove();
  }
}
