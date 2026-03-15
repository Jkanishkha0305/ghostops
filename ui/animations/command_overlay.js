const commandOverlay = document.getElementById('command-overlay');
const commandInput = document.getElementById('command-input');
const commandSend = document.getElementById('command-send');
const commandLogo = document.getElementById('command-logo');
const commandLogoSpin = document.getElementById('command-logo-spin');
const commandBar = document.getElementById('command-bar');
const commandInputWrap = commandOverlay?.querySelector('.command-input-wrap');
const MAX_INPUT_HEIGHT = 180;
let overlayActive = false;
let overlayClosing = false;
let inputFocused = false;
let lastSubmittedText = '';
let lastSubmittedAt = 0;
let hideOverlayTimeout = null;
let logoSyncRaf = null;
let logoSyncUntil = 0;

function getElementTranslations(el) {
  if (!el) return { x: 0, y: 0 };
  const computed = window.getComputedStyle(el);
  const transform = computed?.transform;
  if (!transform || transform === 'none') {
    return { x: 0, y: 0 };
  }

  // matrix(a, b, c, d, tx, ty)
  const matrix2d = transform.match(/^matrix\(([^)]+)\)$/);
  if (matrix2d) {
    const values = matrix2d[1].split(',').map((part) => Number(part.trim()));
    if (values.length === 6) {
      return { x: values[4], y: values[5] };
    }
  }

  // matrix3d(..., tx, ty, tz)
  const matrix3d = transform.match(/^matrix3d\(([^)]+)\)$/);
  if (matrix3d) {
    const values = matrix3d[1].split(',').map((part) => Number(part.trim()));
    if (values.length === 16) {
      return { x: values[12], y: values[13] };
    }
  }

  return { x: 0, y: 0 };
}

function syncCommandLogoPosition() {
  if (!commandLogo || !commandInputWrap) return;
  // Use the left edge of the input wrap as the anchor for the "begining" position
  const anchorRect = commandInputWrap.getBoundingClientRect();
  if (!anchorRect || !Number.isFinite(anchorRect.top) || anchorRect.height <= 0) return;

  // Align logo center to the left edge of the input bar + user's preferred offset
  const anchorCenterX = anchorRect.left + 30;
  const anchorCenterY = anchorRect.top + (anchorRect.height / 2);
  const logoWidth = commandLogo.offsetWidth || 70;
  const logoHeight = commandLogo.offsetHeight || 70;
  const translations = getElementTranslations(commandLogo);

  commandLogo.style.left = `${Math.round(anchorCenterX - (logoWidth / 2) - translations.x)}px`;
  commandLogo.style.top = `${Math.round(anchorCenterY - (logoHeight / 2) - translations.y)}px`;
}

function stopLogoSyncLoop() {
  if (logoSyncRaf !== null) {
    cancelAnimationFrame(logoSyncRaf);
    logoSyncRaf = null;
  }
  logoSyncUntil = 0;
}

function startLogoSyncLoop(durationMs = 1800) {
  stopLogoSyncLoop();
  logoSyncUntil = performance.now() + durationMs;

  const tick = () => {
    if (!overlayActive) {
      stopLogoSyncLoop();
      return;
    }
    syncCommandLogoPosition();
    if (performance.now() < logoSyncUntil) {
      logoSyncRaf = requestAnimationFrame(tick);
      return;
    }
    logoSyncRaf = null;
    syncCommandLogoPosition();
  };

  logoSyncRaf = requestAnimationFrame(tick);
}

function cacheDirectResponseAnchor() {
  const anchorEl = commandInputWrap || commandBar;
  if (!anchorEl) return;
  const rect = anchorEl.getBoundingClientRect();
  const width = commandInputWrap?.offsetWidth || commandBar?.offsetWidth || rect.width;
  window.overlayDirectResponseAnchor = {
    centerX: window.innerWidth * 0.5,
    // Final settled anchor under the centered bar (independent of in-flight intro animation).
    top: Math.round((window.innerHeight * 0.5) - 12),
    width
  };
}

function resizeInput() {
  if (!commandInput) return;
  commandInput.style.height = 'auto';
  const targetHeight = Math.min(MAX_INPUT_HEIGHT, commandInput.scrollHeight);
  commandInput.style.height = `${targetHeight}px`;
  if (overlayActive) {
    requestAnimationFrame(() => {
      syncCommandLogoVerticalPosition();
    });
  }
}

function setInputMode(enabled) {
  if (window.api?.setInputMode) {
    window.api.setInputMode(enabled);
  }
}

function showCommandOverlay() {
  if (!commandOverlay) return;
  if (overlayActive && !overlayClosing) return;

  // If the user re-summons quickly during fade-out, cancel close and reopen
  // immediately so animations and state don't get stuck between phases.
  if (overlayClosing) {
    overlayClosing = false;
    if (hideOverlayTimeout) {
      clearTimeout(hideOverlayTimeout);
      hideOverlayTimeout = null;
    }
    commandOverlay.classList.remove('closing');
    overlayActive = false;
  }

  overlayActive = true;
  overlayClosing = false;
  window.overlayInputActiveFlag = true;
  window.overlayInputFocusedFlag = false;
  // Force a fresh class transition so spawn/move animations reliably replay.
  commandOverlay.classList.remove('active');
  void commandOverlay.offsetWidth;
  commandOverlay.classList.remove('agent-active');
  commandOverlay.classList.remove('closing');
  commandOverlay.classList.add('active');
  if (commandBar) {
    commandBar.style.animation = '';
    commandBar.style.opacity = '';
    commandBar.style.transform = '';
    commandBar.style.pointerEvents = '';
  }
  if (commandLogo) {
    commandLogo.style.opacity = '';
    commandLogo.style.transform = '';
    commandLogo.style.pointerEvents = '';
    commandLogo.style.animation = '';
  }
  if (commandLogoSpin) {
    commandLogoSpin.style.animation = '';
  }
  if (commandInputWrap) {
    commandInputWrap.style.animation = '';
    commandInputWrap.style.transform = '';
    commandInputWrap.style.opacity = '';
    commandInputWrap.style.pointerEvents = '';
  }
  commandInput.value = '';
  resizeInput();
  setInputMode(true);
  startLogoSyncLoop(1800);
  setTimeout(() => {
    syncCommandLogoPosition();
    commandInput.focus();
  }, 20);
}

function collapseCommandBar() {
  if (commandOverlay) {
    commandOverlay.classList.add('agent-active');
  }
  if (commandBar) {
    commandBar.style.opacity = '0';
    commandBar.style.transform = 'translateY(20px)';
    commandBar.style.pointerEvents = 'none';
  }
  if (commandLogo) {
    commandLogo.style.animation = 'none';
    commandLogo.style.opacity = '0';
    commandLogo.style.transform = 'translateY(20px)';
    commandLogo.style.pointerEvents = 'none';
  }
  if (commandLogoSpin) {
    commandLogoSpin.style.animation = 'none';
  }
  if (commandInputWrap) {
    commandInputWrap.style.animation = 'none';
    commandInputWrap.style.opacity = '0';
    commandInputWrap.style.pointerEvents = 'none';
  }
  if (window.overlayHideResponse) {
    window.overlayHideResponse();
  }
}

function hideCommandOverlay() {
  if (!commandOverlay || !overlayActive || overlayClosing) return;
  overlayClosing = true;
  commandOverlay.classList.remove('agent-active');
  commandOverlay.classList.add('closing');
  commandInput.value = '';
  resizeInput();
  setInputMode(false);
  window.overlayInputActiveFlag = false;
  window.overlayInputFocusedFlag = false;
  if (window.overlaySend) {
    window.overlaySend({ command: 'overlay_hide', id: 'direct_response' });
  }
  if (window.overlayHideResponse) {
    window.overlayHideResponse();
  }
  stopLogoSyncLoop();
  if (hideOverlayTimeout) {
    clearTimeout(hideOverlayTimeout);
    hideOverlayTimeout = null;
  }
  hideOverlayTimeout = setTimeout(() => {
    overlayActive = false;
    overlayClosing = false;
    hideOverlayTimeout = null;
    commandOverlay.classList.remove('active');
    commandOverlay.classList.remove('closing');
  }, 1000);
}

function forceResetCommandOverlay() {
  if (hideOverlayTimeout) {
    clearTimeout(hideOverlayTimeout);
    hideOverlayTimeout = null;
  }

  stopLogoSyncLoop();
  overlayActive = false;
  overlayClosing = false;
  inputFocused = false;
  window.overlayInputActiveFlag = false;
  window.overlayInputFocusedFlag = false;

  if (commandInput) {
    commandInput.blur();
    commandInput.value = '';
  }
  resizeInput();
  setInputMode(false);

  if (commandOverlay) {
    commandOverlay.classList.remove('active');
    commandOverlay.classList.remove('closing');
    commandOverlay.classList.remove('agent-active');
  }

  if (commandBar) {
    commandBar.style.animation = '';
    commandBar.style.opacity = '';
    commandBar.style.transform = '';
    commandBar.style.pointerEvents = '';
  }
  if (commandLogo) {
    commandLogo.style.opacity = '';
    commandLogo.style.transform = '';
    commandLogo.style.pointerEvents = '';
    commandLogo.style.animation = '';
  }
  if (commandLogoSpin) {
    commandLogoSpin.style.animation = '';
  }
  if (commandInputWrap) {
    commandInputWrap.style.animation = '';
    commandInputWrap.style.transform = '';
    commandInputWrap.style.opacity = '';
    commandInputWrap.style.pointerEvents = '';
  }

  if (window.overlayHideResponse) {
    window.overlayHideResponse();
  }
}

function sendCommand() {
  if (!overlayActive) return;
  const text = commandInput.value.trim();
  if (!text) {
    if (window.overlayCancelNarration) window.overlayCancelNarration();
    if (window.overlayHideResponse) window.overlayHideResponse();
    hideCommandOverlay();
    return;
  }

  if (window.overlayCancelNarration) window.overlayCancelNarration();
  if (window.overlayHideResponse) window.overlayHideResponse();

  const now = Date.now();
  if (text === lastSubmittedText && (now - lastSubmittedAt) < 1200) {
    return;
  }
  lastSubmittedText = text;
  lastSubmittedAt = now;

  if (window.hideStatusBubble && window.isStatusBubbleVisible?.()) {
    window.hideStatusBubble(0);
  }

  cacheDirectResponseAnchor();
  const thinkingAnchor = window.overlayDirectResponseAnchor || {};
  const thinkingX = Number.isFinite(thinkingAnchor.centerX)
    ? thinkingAnchor.centerX
    : Math.round(window.innerWidth * 0.5);
  const thinkingY = Number.isFinite(thinkingAnchor.top)
    ? thinkingAnchor.top
    : Math.round((window.innerHeight * 0.5) - 12);

  // Ensure immediate visual feedback on submit before any backend round-trip.
  if (window.overlayHideResponse) {
    window.overlayHideResponse();
  }
  if (window.overlayShowThinking) {
    window.overlayShowThinking(thinkingX, thinkingY);
  }

  if (window.overlaySend) {
    window.overlaySend({
      event: 'overlay_input',
      text,
      requestId: `overlay_${now}_${Math.random().toString(16).slice(2, 8)}`
    });
  }
  if (window.hideScreenGlow) {
    window.hideScreenGlow();
  }
}

// Function to restore command bar visibility (called when agent finishes)
function restoreCommandBar() {
  const commandBar = document.getElementById('command-bar');
  const commandLogo = document.getElementById('command-logo');
  // Ignore late restore calls while the input overlay is actively shown,
  // unless it is currently collapsed by agent mode.
  if (overlayActive && !commandOverlay?.classList.contains('agent-active')) {
    return;
  }
  if (commandBar) {
    commandOverlay?.classList.remove('agent-active');
    commandBar.style.animation = 'none';
    commandBar.style.opacity = '1';
    commandBar.style.transform = 'translate3d(-50%, calc(-50% - 20px), 0)';
    commandBar.style.pointerEvents = '';
  }
  if (commandLogo) {
    commandLogo.style.animation = 'none';
    commandLogo.style.opacity = '1';
    // Match the user's +30px offset from the left edge (center-230+30 = center-200)
    commandLogo.style.transform = 'translate3d(calc(-50% - 200px), calc(-50% - 43px), 0) scale(0.45)';
    commandLogo.style.pointerEvents = '';
  }
  if (commandLogoSpin) {
    commandLogoSpin.style.animation = 'none';
  }
  if (commandInputWrap) {
    commandInputWrap.style.animation = 'none';
    commandInputWrap.style.transform = 'translate3d(0, -50%, 0) scaleX(1) scaleY(1)';
    commandInputWrap.style.opacity = '1';
    commandInputWrap.style.pointerEvents = '';
  }

  // Auto-clear and prepare for next input when restored
  if (commandInput) {
    commandInput.value = '';
    resizeInput();
    setInputMode(true);
    setTimeout(() => commandInput.focus(), 50);
  }

  requestAnimationFrame(() => {
    syncCommandLogoPosition();
    if (overlayActive) {
      // Keep logo centered while restore transitions settle.
      startLogoSyncLoop(700);
    }
  });
}

window.restoreCommandBar = restoreCommandBar;
window.overlayShowCommandOverlay = showCommandOverlay;
window.overlayCollapseCommandBar = collapseCommandBar;
window.overlayForceResetCommandOverlay = forceResetCommandOverlay;

commandInput?.addEventListener('input', resizeInput);
commandInput?.addEventListener('focus', () => {
  inputFocused = true;
  window.overlayInputFocusedFlag = true;
  setInputMode(true);
});
commandInput?.addEventListener('blur', () => {
  inputFocused = false;
  window.overlayInputFocusedFlag = false;
  // Don't call setInputMode(false) here. We want the window to remain focusable 
  // while the overlay is active so the user can easily click back into it.
});
commandInputWrap?.addEventListener('click', () => {
  commandInput?.focus();
});
commandSend?.addEventListener('click', () => sendCommand());
commandInput?.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    sendCommand();
  } else if (event.key === 'Escape') {
    event.preventDefault();
    hideCommandOverlay();
  }
});

document.addEventListener('keydown', (event) => {
  if (!overlayActive) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    hideCommandOverlay();
  }
});

window.addEventListener('resize', () => {
  if (!overlayActive) return;
  syncCommandLogoPosition();
});

// --- Voice Push-To-Talk Logic (Backend-Driven) ---
const commandMic = document.getElementById('command-mic');
let isRecording = false;

window.overlaySetMicTranscript = function (text, isFinal) {
  if (commandInput) {
    if (text) {
      // Only append text if there is something transcribed
      let existing = commandInput.value;
      commandInput.value = existing ? existing + " " + text : text;
      resizeInput();
    }
  }
  if (isFinal) {
    stopRecording(true);
  }
};

function startRecording() {
  if (!isRecording) {
    isRecording = true;
    if (commandMic) commandMic.classList.add('recording');
    if (commandInput) {
      commandInput.placeholder = "Listening...";
      // Removed clearing value so users can mix typing and audio
    }
    if (window.overlaySend) {
      window.overlaySend({ event: 'start_mic' });
    }
    commandInput?.focus();
  }
}

function stopRecording(skipBackendSignal = false) {
  if (isRecording) {
    isRecording = false;
    if (commandMic) commandMic.classList.remove('recording');
    if (commandInput && commandInput.placeholder === "Listening...") {
      commandInput.placeholder = "GhostOps — what do you need?";
    }
    if (window.overlaySend && !skipBackendSignal) {
      window.overlaySend({ event: 'stop_mic' });
    }
    commandInput?.focus();
  }
}

// --- Draggable Command Bar Logic ---
let isDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let barOffsetX = 0;
let barOffsetY = 0;

if (commandBar) {
  commandBar.addEventListener('mousedown', (e) => {
    // Only drag with left click and not on interactive elements like input or buttons
    if (e.button !== 0 || e.target.closest('#command-input, #command-mic, #command-send')) return;

    isDragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    commandBar.classList.add('dragging');

    // Add a temporary overlay to catch mouse moves if needed, or just use window
    window.addEventListener('mousemove', onDragging);
    window.addEventListener('mouseup', stopDragging);

    // Notify Electron to keep capturing mouse
    if (window.api?.setWindowInteractive) {
      window.api.setWindowInteractive(true);
    }
  });
}

function onDragging(e) {
  if (!isDragging || !commandBar) return;

  const dx = e.clientX - dragStartX;
  const dy = e.clientY - dragStartY;

  dragStartX = e.clientX;
  dragStartY = e.clientY;

  barOffsetX += dx;
  barOffsetY += dy;

  // Base transform is translate3d(-50%, calc(-50% - 20px), 0)
  // We add our offsets to this.
  commandBar.style.transform = `translate3d(calc(-50% + ${barOffsetX}px), calc(-50% - 20px + ${barOffsetY}px), 0)`;

  // Update logo position as well
  syncCommandLogoPosition();
}

function stopDragging() {
  if (!isDragging) return;
  isDragging = false;
  commandBar.classList.remove('dragging');

  window.removeEventListener('mousemove', onDragging);
  window.removeEventListener('mouseup', stopDragging);

  // Recalculate anchor for direct responses
  cacheDirectResponseAnchor();
}

if (commandMic) {
  // Prevent the microphone button from stealing focus, which triggers the 
  // aggressive blur() -> setInputMode(false) lock in Electron.
  commandMic.addEventListener('mousedown', (e) => {
    e.preventDefault();
  });

  commandMic.addEventListener('click', (e) => {
    e.preventDefault();
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  });
}

// Ensure recording stops when overlay hides
const originalHideCommandOverlay = hideCommandOverlay;
hideCommandOverlay = function () {
  stopRecording();
  originalHideCommandOverlay();
};

const originalCollapseCommandBar = collapseCommandBar;
collapseCommandBar = function () {
  stopRecording();
  originalCollapseCommandBar();
};

const originalForceResetCommandOverlay = forceResetCommandOverlay;
forceResetCommandOverlay = function () {
  stopRecording();
  originalForceResetCommandOverlay();
};
// --- End Voice Logic ---

if (window.api?.onOverlayImage) {
  window.api.onOverlayImage(() => {
    // Capture screenshot BEFORE showing overlay
    if (window.overlaySend) {
      window.overlaySend({ event: 'capture_screenshot' });
    }
    // Small delay to ensure screenshot is taken before overlay appears
    setTimeout(() => {
      showCommandOverlay();
    }, 50);
  });
}

window.overlayHideCommandOverlay = hideCommandOverlay;

resizeInput();
