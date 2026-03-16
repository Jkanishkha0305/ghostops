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

    // Force window interactive through the entire drag (bypasses cursor poll)
    window.overlaySetDragging?.(true);
    window.api?.startDrag?.();

    // Resolve actual position, flattening any CSS transforms
    const rect = root.getBoundingClientRect();
    const origLeft = rect.left;
    const origTop = rect.top;

    root.style.transform = 'none';
    root.style.setProperty('--text-translate-x', '0%');
    root.style.setProperty('--text-translate-y', '0%');
    root.style.left = `${origLeft}px`;
    root.style.top = `${origTop}px`;

    const startX = e.clientX;
    const startY = e.clientY;
    strip.classList.add('dragging');

    const onMove = (ev) => {
      root.style.left = `${origLeft + ev.clientX - startX}px`;
      root.style.top = `${origTop + ev.clientY - startY}px`;
    };

    const onUp = () => {
      console.log('[drag] mouseup end');
      strip.classList.remove('dragging');
      window.overlaySetDragging?.(false);
      window.api?.endDrag?.();
      document.removeEventListener('mousemove', onMove, true);
      document.removeEventListener('mouseup', onUp, true);
    };

    // Use capture phase so events fire even if the element moves under the cursor
    document.addEventListener('mousemove', onMove, true);
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
