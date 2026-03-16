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

    // Drag strip — sits above text content, clearly grabbable
    const strip = document.createElement('div');
    strip.className = 'ai-ar-drag-strip';
    strip.innerHTML = '<span class="ai-ar-grip">⠿</span>';
    bubble.appendChild(strip);

    const textEl = document.createElement('div');
    textEl.className = 'ai-ar-text';
    bubble.appendChild(textEl);
    root.replaceChildren(bubble);

    _attachDrag(root, strip);
  }
  const textEl = bubble.querySelector('.ai-ar-text');
  return { bubble, textEl };
}

function _attachDrag(root, strip) {
  strip.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();

    console.log('[drag] mousedown start');

    // Flatten any CSS transforms before recording position
    const rect = root.getBoundingClientRect();
    const origLeft = rect.left;
    const origTop = rect.top;
    root.style.transform = 'none';
    root.style.setProperty('--text-translate-x', '0%');
    root.style.setProperty('--text-translate-y', '0%');
    root.style.left = `${origLeft}px`;
    root.style.top = `${origTop}px`;

    strip.classList.add('dragging');

    // Register with cursor-poller-driven drag.
    // On macOS, mousemove does not fire in a focusable:false Electron window during
    // a drag gesture — the cursor poller (getCursorScreenPoint every 30ms) does.
    window.overlayActiveDrag = {
      el: root,
      startCursorX: e.clientX,
      startCursorY: e.clientY,
      startElLeft: origLeft,
      startElTop: origTop,
    };
    window.overlaySetDragging?.(true);
    window.api?.startDrag?.();

    const onUp = () => {
      console.log('[drag] mouseup end');
      strip.classList.remove('dragging');
      window.overlayActiveDrag = null;
      window.overlaySetDragging?.(false);
      window.api?.endDrag?.();
      document.removeEventListener('mouseup', onUp, true);
    };

    document.addEventListener('mouseup', onUp, true);
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
    // Insert after the drag strip
    const strip = bubble.querySelector('.ai-ar-drag-strip');
    const insertAfter = strip ? strip.nextSibling : bubble.firstChild;
    bubble.insertBefore(meta, insertAfter);
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
