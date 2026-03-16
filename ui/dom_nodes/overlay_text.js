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

    // Drag handle — invisible top strip that initiates dragging
    const dragHandle = document.createElement('div');
    dragHandle.className = 'ai-ar-drag-handle';
    bubble.appendChild(dragHandle);

    const textEl = document.createElement('div');
    textEl.className = 'ai-ar-text';
    bubble.appendChild(textEl);
    root.replaceChildren(bubble);

    _attachDrag(root, dragHandle);
  }
  const textEl = bubble.querySelector('.ai-ar-text');
  return { bubble, textEl };
}

function _attachDrag(root, handle) {
  handle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    e.stopPropagation();

    // Notify renderer that a drag is active so hit-test keeps window interactive
    window.overlaySetDragging?.(true);
    handle.classList.add('dragging');

    // Resolve actual pixel position (accounting for any CSS transforms like translate(-50%))
    const bubbleRect = root.getBoundingClientRect();
    const origLeft = bubbleRect.left;
    const origTop = bubbleRect.top;

    // Flatten transform so left/top are screen coordinates
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
      handle.classList.remove('dragging');
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
