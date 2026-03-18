## Inspiration

Every developer knows the feeling: you're in a deep flow state — three terminals open, a half-written function in your head — and you need to look something up. You alt-tab, open a browser, lose your place, lose your thought. The AI assistant is in *another window*, waiting for you to come to it.

I wanted to flip that. What if the AI came to *you*? Not in a sidebar. Not a chatbot. Just... there, invisible, floating above every window — summoned with one keystroke and gone just as fast.

That's the idea behind **GhostOps**: an AI that lives on your screen like a ghost. You never have to context-switch to talk to it.

---

## How We Use DigitalOcean Gradient AI

GhostOps is built **end-to-end on DigitalOcean**:

### Serverless Inference (Primary AI Engine)
Every AI call in GhostOps routes through **DigitalOcean Gradient AI's Serverless Inference API** at `https://inference.do-ai.run/v1/`. We use the OpenAI-compatible endpoint with DO Model Access Keys for authentication.

- **`llama3.3-70b-instruct`** — Powers the intelligent multi-agent router. Classifies user intent from natural language and delegates to the correct specialist agent (vision, CLI, screen annotator, browser, or direct response). Also generates safe shell commands for the CLI agent.
- **`openai-gpt-4o` (via DO)** — Vision model for screenshot analysis, screen element detection, bounding box extraction, and GUI automation. This drives the computer-use loop: screenshot → model → tool calls → execute → repeat.
- **`anthropic-claude-haiku-4.5` (via DO)** — Fast classification and routing for lightweight tasks.

The provider implementation (`core/do_provider.py`) is a drop-in module using the standard `openai` Python SDK pointed at DO's inference endpoint. We built a provider switcher (`core/provider.py`) that lets us swap between DO, Gemini, and Groq backends via a single `AI_PROVIDER` environment variable — but DO is the default and primary.

### App Platform (Backend Hosting)
The GhostOps backend API — a FastAPI service handling vision processing, conversation memory, and health monitoring — is deployed on **DigitalOcean App Platform** with auto-deploy on push.

- **Live at:** https://clownfish-app-dqd9h.ondigitalocean.app
- Auto-detects our `Dockerfile`, builds and deploys on every `git push`
- Deployment spec in `.do/app.yaml`

### DO Platform Integration (Agent Architecture)
We built platform management tooling (`core/do_platform.py`) to register our 4 specialist agents on the DO Gradient AI Agent platform:
- `ghostops-router` — Intent classification and delegation
- `ghostops-vision` — Screen understanding and GUI control
- `ghostops-cli` — Safe shell command generation
- `ghostops-screen` — Visual annotation and explanation

This module also manages DO Knowledge Bases (for RAG-powered agent memory) and DO Guardrails (jailbreak protection, content moderation, sensitive data filtering).

---

## How I Built It

### The Overlay
The foundation is an **Electron window with `transparent: true`, `frame: false`, and `alwaysOnTop: 'screen-saver'`**. On macOS this is a `panel`-type window — it floats above everything, including full-screen apps and Mission Control. By default it's `focusable: false` and ignores all mouse events, so it's completely invisible to your workflow.

When you press Cmd+Shift+Space, a command bar fades up. The window becomes interactive just long enough for you to type or speak your request — then retreats to ghost mode.

### Multi-Agent Routing via DO Gradient AI
Every command is routed by **llama3.3-70b-instruct on DigitalOcean Gradient AI** to one of six specialist agents:
- **direct_response** — instant answers without tools
- **invoke_screen_annotator** — takes a screenshot, sends it to DO's vision model (gpt-4o), draws floating bounding boxes over identified elements
- **invoke_cua_vision** — computer use: screenshot → DO vision model → tool calls (move cursor, click, type) → repeat until complete
- **invoke_cua_cli** — shell commands, file ops, `open -a AppName`
- **invoke_browser** — full Playwright browser automation
- **request_screen_context** — reads the screen first via DO vision, then decides what to do

The routing uses function calling through DO's OpenAI-compatible API. A single structured output decides which agent handles the task — no keyword matching, no regex trees.

### Voice Integration
Hold the mic button and just *talk*. The Gemini Live API streams bidirectional audio — you can interrupt mid-sentence and GhostOps adapts in real time. The same six agents are available over voice, dispatched through the same DO-powered routing layer.

### Workflow Recording and Replay
GhostOps can **watch you work** and learn to replicate it. Say "watch me" — it starts screenshotting every 2 seconds and transcribing your keystrokes. Say "remember this as setup-project" — it sends the final frame to DO's vision model, extracts a structured list of steps as JSON, and saves them.

Next time: "replay setup-project" — GhostOps runs through each step using the vision agent on DO, taking a fresh screenshot at each step to find and interact with the correct element on screen.

### Cloud Backend on DigitalOcean
The backend API runs on **DigitalOcean App Platform** — FastAPI serving vision, memory, and health endpoints. Session memory persists in Firestore so GhostOps remembers context across restarts. The deployment is fully automated via `.do/app.yaml` with deploy-on-push from GitHub.

---

## Challenges

### The Mouse Problem
Electron's `focusable: false` windows on macOS don't receive `mousemove` events. This is by design — a ghost window can't intercept events meant for real windows underneath. But drag-to-reposition needs `mousemove`.

The solution: a cursor poller. Every 30ms, the Electron main process calls `screen.getCursorScreenPoint()` and sends the coordinates to the renderer via IPC. Completely invisible to the OS, perfectly smooth.

### Screen Resolution in the Vision Loop
The computer-use agent takes a screenshot and asks DO's vision model to return bounding box coordinates for the target element. But screenshots are captured at native retina resolution (4000x1440) while coordinates need to match the logical screen space for `pyautogui`. Getting the coordinate space mapping right — accounting for device pixel ratio, window scaling, and multi-monitor offsets — took more iteration than any other part of the project.

### DO Minimum Token Constraint
DigitalOcean's inference API requires `max_completion_tokens >= 256`. Several of our agent calls used smaller values (128 for quick routing). We had to wrap all calls with `max(256, max_tokens)` to meet the platform requirement without over-generating for simple tasks.

### Provider Architecture
We wanted to keep the ability to swap AI backends without touching agent code. The solution: a provider switcher pattern where `core/provider.py` reads `AI_PROVIDER` from the environment and imports the matching backend. All 11 import sites in the codebase point to the switcher — changing one env var swaps every AI call in the system.

---

## What I Learned

- **DO Gradient AI's OpenAI-compatible API makes migration easy.** We went from a different provider to DO by changing a base URL and API key. The `openai` Python SDK works out of the box.
- **llama3.3-70b on DO is genuinely good at structured routing.** Give it a classification task with function calling and it reliably picks the right agent — no fine-tuning needed.
- **gpt-4o via DO is strong at screen understanding.** Give it a screenshot and ask "where is the New Tab button?" — it finds it. This makes the computer-use loop surprisingly reliable.
- **App Platform deploy-on-push is a huge time saver.** Push to main, backend is live in minutes. Zero DevOps overhead.
- **Transparent overlays are deep OS-level territory.** Between window types, z-order, focus management, and accessibility permissions, building something that truly sits above all other windows without breaking normal desktop behavior is a surprisingly complex systems problem.
- **Multimodal routing is more powerful than text routing.** The `request_screen_context` agent sends the screen to DO's vision model before routing, so "open this repo in Cursor" works even if you never typed the repo name — the model reads it off the screen.

---

## What's Next

- Deploy agents via DO Gradient AI Agent Development Kit (ADK)
- DO Knowledge Bases for RAG-powered agent memory
- DO Guardrails for safe agent action filtering
- Proactive heartbeats — GhostOps checks in on you based on what it last knew you were working on
- Browser workflow recording — capture Playwright traces, not just desktop screenshots
- Windows and Linux support
