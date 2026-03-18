<div align="center">

<img src="assets/GhostOps.png" alt="GhostOps" width="100%"/>


# GhostOps

### *Your invisible AI co-pilot. It sees your screen, learns your workflows, and acts on your behalf.*

[![DigitalOcean Gradient AI](https://img.shields.io/badge/DigitalOcean%20Gradient%E2%84%A2%20AI-Serverless%20Inference-0080FF?style=flat-square&logo=digitalocean&logoColor=white)](https://docs.digitalocean.com/products/gradient-ai-platform/)
[![Gemini Live API](https://img.shields.io/badge/Gemini%20Live%20API-Voice%20Streaming-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![DO App Platform](https://img.shields.io/badge/DigitalOcean-App%20Platform-0080FF?style=flat-square&logo=digitalocean&logoColor=white)](https://clownfish-app-dqd9h.ondigitalocean.app)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Firestore%20%2B%20Voice-4285F4?style=flat-square&logo=googlecloud&logoColor=white)](https://cloud.google.com)
[![Electron](https://img.shields.io/badge/Electron-Overlay%20UI-47848F?style=flat-square&logo=electron&logoColor=white)](https://electronjs.org)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

> **Built for the [DigitalOcean Gradient AI Hackathon](https://digitalocean.devpost.com)**
> A transparent, always-on desktop overlay powered by DigitalOcean Gradient AI that sees, hears, speaks, and acts.

</div>

---

## What is GhostOps?

GhostOps is a **transparent Electron overlay** that sits invisibly above every window on your desktop. Press one shortcut and it appears — ready to answer questions, annotate your screen, control your computer, automate browser tasks, or **learn and replay your entire workflows**.

All AI inference is powered by **DigitalOcean Gradient AI's serverless inference** — routing decisions, vision understanding, and tool calling all run through DO's OpenAI-compatible endpoint with models like `llama3.3-70b-instruct` and `openai-gpt-4o`.

It's not a chatbot in a window. It *is* the window.

```
You press Cmd+Shift+Space
         |
         v
  +--------------------------------------+
  |  Hey Kanishkha -- what do you need?  |  <-- floating over your real screen
  +--------------------------------------+
         |
  You type: "watch me set up this repo"
         |
         v
  GhostOps records every action you take
  Then replays it perfectly on any machine
```

---

## Demo

> **[Watch the demo video](#)** — Screen annotation -> CLI control -> Mouse automation -> Workflow learning

---

## How We Use DigitalOcean Gradient AI

GhostOps is built on **DigitalOcean Gradient AI** as its primary AI infrastructure:

| DO Gradient AI Feature | How GhostOps Uses It |
|---|---|
| **Serverless Inference API** | All LLM calls route through `https://inference.do-ai.run/v1/` — text generation, vision analysis, and function calling |
| **Model Access Keys** | Authentication via DO Model Access Keys for secure, scoped API access |
| **llama3.3-70b-instruct** | Powers the intelligent agent router — classifies user intent and delegates to the right specialist agent |
| **openai-gpt-4o (via DO)** | Vision model for screenshot analysis, screen understanding, element detection, and GUI automation |
| **OpenAI-Compatible API** | Drop-in integration via the standard `openai` Python SDK, pointing at DO's inference endpoint |
| **Multi-Model Catalog** | Access to 30+ models (Claude, GPT, Llama, DeepSeek, Nemotron) through a single endpoint |
| **App Platform** | Backend API deployed on DO App Platform — auto-scaling, zero-ops hosting ([Live](https://clownfish-app-dqd9h.ondigitalocean.app/health)) |

### Architecture with DO Gradient AI

```
User Input (text or voice)
     |
     v
+---------------------------------------------------+
|  DO Gradient AI - Serverless Inference             |
|  https://inference.do-ai.run/v1/                   |
|                                                     |
|  llama3.3-70b    --> Agent Router (classify intent) |
|  openai-gpt-4o   --> Vision (screen understanding)  |
|  llama3.3-70b    --> CLI Agent (command generation)  |
+--------+------------------------------------------+
         |
         v
+---------------------------------------------------+
|  DO App Platform — Backend API                     |
|  https://clownfish-app-dqd9h.ondigitalocean.app   |
|  FastAPI (vision, memory, health)                   |
+--------+------------------------------------------+
         |
         v
+---------------------------------------------------+
|  Local Desktop Agent (Python + Electron)           |
|  pyautogui (mouse/KB) + Playwright (browser)       |
|  Electron overlay (transparent, always-on-top)      |
+---------------------------------------------------+
```

---

## Architecture

```
+-------------------------------------------------------------------------+
|                         USER'S DESKTOP                                   |
|                                                                          |
|  +------------------------------------------------------------------+   |
|  |               ELECTRON OVERLAY  (always on top)                   |   |
|  |  Transparent, focusable-on-demand panel                           |   |
|  |  Canvas: bounding boxes, dots, annotation text                    |   |
|  |  Command bar: text input + voice mic + drag handle                |   |
|  |  Status bubbles: real-time task progress                          |   |
|  +---------------------+--------------------------------------------+   |
|                         |  WebSocket (ws://127.0.0.1:PORT)               |
+-------------------------+------------------------------------------------+
                          |
+--------------------------+-----------------------------------------------+
|                    PYTHON CORE  (app.py)                                  |
|                                                                          |
|  +------------------------------------------------------------------+   |
|  |              MULTI-AGENT ROUTER (DO Gradient AI)                  |   |
|  |  llama3.3-70b classifies intent, delegates to specialists         |   |
|  |                                                                   |   |
|  |  +----------+ +----------+ +----------+ +----------+             |   |
|  |  | answer   | | annotate | | control  | | browse   |             |   |
|  |  | directly | | screen   | | computer | |  web     |             |   |
|  |  +----------+ +----------+ +----------+ +----------+             |   |
|  |  +----------+ +----------+ +----------+ +----------+             |   |
|  |  | run_shell| | read     | | workflow | | workflow |             |   |
|  |  | command  | | screen   | | record   | | replay   |             |   |
|  |  +----------+ +----------+ +----------+ +----------+             |   |
|  +------------------------------------------------------------------+   |
|                                                                          |
|  +------------------+    +------------------+  +-------------------+   |
|  |  DO Gradient AI  |    |  DO App Platform |  |  Google Cloud     |   |
|  |  Serverless      |    |  Backend API     |  |  +- Firestore     |   |
|  |  Inference       |    |  (FastAPI)       |  |  |  (memory)      |   |
|  |  (vision + text) |    |  /vision /memory |  |  +- Gemini Live   |   |
|  +------------------+    +------------------+  |  |  (voice)       |   |
|                                                 +-------------------+   |
+--------------------------------------------------------------------------+
```

---

## Feature Overview

| Feature | Description | Example Command |
|---|---|---|
| **Direct Q&A** | Instant answers via DO inference | *"what is 42 x 37"* |
| **Screen Annotation** | Floating bounding boxes over live UI | *"what's on my screen"* |
| **Computer Use** | Sees screen, moves cursor, clicks | *"click the new note button"* |
| **CLI Control** | Shell commands, file ops, open apps | *"open notion"* |
| **Browser Agent** | Full Playwright web automation | *"search google for X"* |
| **Screen Context** | Reads screen then acts on what it sees | *"open this repo in Cursor"* |
| **Voice Input** | STT via mic button | Click mic in overlay |
| **Workflow Record** | Watch user, extract steps | *"watch me"* |
| **Workflow Replay** | Replay saved workflows via vision | *"replay my-workflow"* |
| **Memory** | Firestore session memory across restarts | Auto on startup |
| **Personalized** | Name-aware, personality-driven responses | `settings.json` |

---

## Agent Routing

Every input is routed by **llama3.3-70b-instruct on DigitalOcean Gradient AI** to the right specialist:

```
User Input
    |
    v
+-----------------------------------------------------+
|     ROUTER (llama3.3-70b via DO Gradient AI)         |
+--+----------+----------+----------+----------+------+
   |          |          |          |          |
   v          v          v          v          v
direct    screen      cua_cli   cua_vision  browser
response  annotator   (shell)   (mouse+KB)  (playwright)
   |          |          |          |          |
   |     bounding    open -a    go_to_     navigate
   |      boxes      Notion     element    click
   |     + labels    git clone  click_left fill form
   v          |      ls ~/      type_str   submit
 answer   overlay       |          |          |
          text     terminal   cursor      chrome
                   output     moves
```

---

## Workflow Engine

The standout feature. GhostOps **watches you work** and learns to replicate it:

```
RECORD                           EXTRACT                      REPLAY
------                           -------                      ------
User: "watch me"                 Last frame -> Gemini         For each step:
  |                              vision ->                       |
  v                              JSON steps:                     v
Screenshot every 2s              [{                          VisionAgent.execute(
  +                                action: "click",           "click the New Page
  voice transcription              target: "New Page btn",     button"
  captured into frames             value: ""                 )
  |                              }, ...]                        |
  v                                  |                          v
User: "remember this             Saved to                   Screenshot ->
  as new-page"                   Firestore +                find element ->
                                 local cache                move cursor ->
                                                            click ->
                                                            verify -> next step
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **AI Inference** | **DigitalOcean Gradient AI** (Serverless) | All LLM routing, text generation, vision analysis, function calling |
| **Models** | llama3.3-70b-instruct, openai-gpt-4o (via DO) | Agent routing, screen understanding, command generation |
| **Overlay UI** | Electron 35 + HTML Canvas | Transparent, always-on-top, cross-workspace overlay |
| **IPC** | WebSocket (Python <-> Electron) | Low-latency bidirectional drawing commands |
| **Voice** | Gemini Live API (2.5 Flash) | Real-time streaming audio I/O |
| **Browser** | Playwright + browser-use | Reliable cross-browser automation |
| **Screenshot** | PIL ImageGrab + mss | macOS-native screen capture |
| **Mouse/KB** | pyautogui | Cross-platform desktop control |
| **Memory** | Google Cloud Firestore | Real-time, serverless, persistent sessions |
| **Backend** | FastAPI on **DO App Platform** | Auto-scaling, zero-ops hosting on DigitalOcean |
| **TTS** | ElevenLabs (optional) | Natural voice output |
| **Language** | Python 3.13 + Node.js 18+ | Backend + UI |

---

## Model Usage via DigitalOcean Gradient AI

| Model (on DO) | Used For | Notes |
|---|---|---|
| `llama3.3-70b-instruct` | Agent routing + CLI command generation | Fast, accurate classification and text gen |
| `openai-gpt-4o` | Vision: screenshots, element detection, GUI automation | Multimodal, understands screen layouts |
| `gemini-2.5-flash` | Voice sessions (Gemini Live API) | Real-time bidirectional audio streaming |

All inference calls go through:
```
POST https://inference.do-ai.run/v1/chat/completions
Authorization: Bearer $GRADIENT_MODEL_ACCESS_KEY
```

The DO provider (`core/do_provider.py`) is a drop-in replacement using the OpenAI-compatible API, with full support for:
- Text generation (`generate_text`)
- Vision analysis (`generate_vision`)
- Vision + function calling (`generate_vision_with_tools`)
- Audio transcription (fallback to Groq Whisper)

---

## Installation

### Prerequisites

| Requirement | Version |
|---|---|
| macOS | 12+ (Monterey or later) |
| Python | 3.13+ |
| Node.js | 18+ |
| uv | latest |
| DigitalOcean account | [Sign up](https://mlh.link/digitalocean-signup) for $200 free credits |

### 1. Clone the repo

```bash
git clone https://github.com/jkanishkha0305/ghostops.git
cd ghostops
```

### 2. Set up Python environment

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install dependencies
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 3. Install Electron dependencies

```bash
cd ui
npm install
cd ..
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
# DigitalOcean Gradient AI (Required)
GRADIENT_MODEL_ACCESS_KEY=your_do_model_access_key

# DigitalOcean API Token
DIGITAL_OCEAN_KEY=your_digitalocean_api_token

# Google (for Gemini Live API voice + Firestore)
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_CLOUD_PROJECT=your_gcp_project_id

# Optional
ELEVENLABS_API_KEY=your_elevenlabs_key   # for voice output
CLOUD_RUN_URL=https://your-service.run.app  # for persistent memory
FIRESTORE_SESSION_ID=your_username
```

> **Get your DO Model Access Key:**
> 1. Go to [DigitalOcean Control Panel](https://cloud.digitalocean.com)
> 2. Navigate to Gradient AI Platform -> Serverless Inference
> 3. Scroll to **Model Access Keys** -> Create Access Key
>
> Or via API:
> ```bash
> curl -X POST -H "Authorization: Bearer $DIGITAL_OCEAN_KEY" \
>   -H "Content-Type: application/json" \
>   "https://api.digitalocean.com/v2/gen-ai/models/api_keys" \
>   -d '{"name": "ghostops"}'
> ```

### 5. Personalize (optional)

Edit `settings.json`:

```json
{
  "user_name": "YourName",
  "agent_name": "GhostOps",
  "personalization": "Be concise and slightly witty."
}
```

### 6. Grant macOS permissions

1. **System Settings -> Privacy & Security -> Screen Recording** -> add Terminal + Electron
2. **System Settings -> Privacy & Security -> Accessibility** -> add Terminal + Electron
3. **System Settings -> Privacy & Security -> Microphone** -> add Electron (for voice input)

### 7. Run GhostOps

Open **two terminals**:

**Terminal 1 -- Python backend:**
```bash
source .venv/bin/activate
python app.py
```

**Terminal 2 -- Electron overlay:**
```bash
cd ui
npm run dev
```

You should see:
```
Models loaded - using DO Gradient AI serverless inference
Visualization server listening at ws://127.0.0.1:XXXX
Overlay client connected.
```

---

## Usage

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Cmd + Shift + Space` | Show/hide the command overlay |
| `Cmd + Shift + C` | Stop all running tasks immediately |
| `Cmd + Shift + M` | Toggle TTS mute |
| `Escape` | Dismiss overlay |
| `Enter` | Submit command |

### Command Examples

**Direct answers**
```
"what's the square root of 144"
"explain what a webhook is"
```

**Screen annotation**
```
"what's on my screen"
"explain what I'm looking at"
"point to the settings icon"
```

**CLI tasks**
```
"open notion"
"create a folder called projects on my desktop"
"what's my local IP address"
```

**Computer use** *(app must be open)*
```
"click the new note button"
"type hello world in the search bar"
"calculate 18% tip on $84 using the calculator"
```

**Browser automation**
```
"search google for best coffee shops near me"
"go to github.com and search for electron"
```

**Workflow learning**
```
# Start recording
"watch me"

# Do your workflow manually (GhostOps records every 2 seconds)

# Save it
"remember this as setup-project"

# Replay any time
"replay setup-project"
```

---

## How the Vision Loop Works

When GhostOps performs a computer-use task, this is the per-step loop:

```
+-------------------------------------------------------------+
|                    SINGLE CALL VISION ENGINE                 |
+----------------------------+--------------------------------+
                             |
             +---------------v---------------+
             |  1. Capture screenshot         |
             |     (active window or full)    |
             +---------------+---------------+
                             |
             +---------------v---------------+
             |  2. Send to openai-gpt-4o      |
             |     via DO Gradient AI          |
             |     with task + tool schema    |
             +---------------+---------------+
                             |
             +---------------v---------------+
             |  3. Model returns tool calls:  |
             |     go_to_element(bbox)        |
             |     click_left_click()         |
             |     type_string("hello")       |
             |     press_ctrl_hotkey("s")     |
             |     task_is_complete()         |
             +---------------+---------------+
                             |
             +---------------v---------------+
             |  4. Execute tool calls         |
             |     (pyautogui / subprocess)   |
             +---------------+---------------+
                             |
             +---------------v---------------+
             |  5. Loop detection:            |
             |     same action x3 -> stop     |
             |     same click x5 -> fallback  |
             +---------------+---------------+
                             |
                      task_is_complete?
                       YES --+  NO -> back to step 1
```

---

## Project Structure

```
ghostops/
|
+-- app.py                        <-- Main entry point
+-- settings.json                 <-- User config (name, personality, models)
+-- .env                          <-- API keys (never committed)
+-- LICENSE                       <-- MIT License
|
+-- agents/
|   +-- adk_orchestrator.py       <-- Google ADK multi-agent orchestrator (9 tools)
|   +-- screen/                   <-- Screen annotation (bounding boxes + labels)
|   |   +-- agent.py
|   |   +-- tools.py              <-- draw_bounding_box, draw_text, etc.
|   |   +-- prompts.py
|   |
|   +-- cua_vision/               <-- Computer use (sees screen -> clicks)
|   |   +-- agent.py              <-- VisionAgent
|   |   +-- single_call.py        <-- Vision execution loop + loop detection
|   |   +-- tools.py              <-- go_to_element, click, type_string, etc.
|   |   +-- prompts.py
|   |
|   +-- cua_cli/                  <-- Shell agent (subprocess execution)
|   |   +-- agent.py              <-- CLIAgent, runs shell commands safely
|   |
|   +-- browser/                  <-- Browser automation (Playwright + browser-use)
|   |   +-- agent.py
|   |
|   +-- workflow/                 <-- Record + replay engine
|       +-- engine.py             <-- start_recording, stop_and_save, replay
|
+-- models/
|   +-- models.py                 <-- Router + agent dispatch via DO Gradient AI
|   +-- function_calls.py         <-- Tool declarations for all 6 routes
|   +-- prompts.py                <-- Personalized system prompts
|
+-- core/
|   +-- do_provider.py            <-- DigitalOcean Gradient AI provider (primary)
|   +-- gemini_provider.py        <-- Gemini provider (voice/fallback)
|   +-- groq_provider.py          <-- Groq provider (STT fallback)
|   +-- settings.py               <-- Read/write settings.json
|   +-- registry.py               <-- Shared overlay state
|
+-- voice/
|   +-- live_api.py               <-- Gemini Live API voice session
|
+-- ui/
|   +-- main.js                   <-- Electron main process
|   +-- renderer.js               <-- Canvas rendering + WebSocket client
|   +-- preload.js                <-- IPC bridge
|   +-- index.html                <-- Overlay HTML
|   +-- server.py                 <-- WebSocket VisualizationServer
|   +-- animations/               <-- UI component JS + CSS
|   +-- dom_nodes/                <-- Draggable response bubbles + annotation boxes
|   +-- package.json              <-- Electron + forge dependencies
|
+-- backend/
|   +-- main.py                   <-- FastAPI backend (DO App Platform)
|   +-- memory.py                 <-- Firestore memory read/write
|
+-- .do/
|   +-- app.yaml                  <-- DO App Platform deployment spec
|
+-- desktop/
|   +-- screen.py                 <-- Screenshot capture (PIL/mss)
|
+-- integrations/
|   +-- audio/
|       +-- tts.py                <-- ElevenLabs TTS
|
+-- deploy/
    +-- deploy.sh                 <-- One-command Cloud Run deployment
```

---

## Cloud Deployment

### Backend on DigitalOcean App Platform

The backend is deployed on **DigitalOcean App Platform** with auto-deploy on push:

**Live URL:** [https://clownfish-app-dqd9h.ondigitalocean.app](https://clownfish-app-dqd9h.ondigitalocean.app/health)

The app spec is in `.do/app.yaml`. To deploy your own:

1. Fork this repo
2. Go to [DigitalOcean App Platform](https://cloud.digitalocean.com/apps) -> Create App
3. Connect your GitHub repo, select `main` branch
4. It auto-detects the `Dockerfile` and deploys
5. Add env vars: `AI_PROVIDER=do`, `GRADIENT_MODEL_ACCESS_KEY`, `GEMINI_API_KEY`

Or via CLI:
```bash
doctl apps create --spec .do/app.yaml
```

Then set the live URL in your `.env`:
```env
CLOUD_RUN_URL=https://clownfish-app-dqd9h.ondigitalocean.app
```

### Firestore collections

| Collection | Purpose |
|---|---|
| `sessions/{id}/turns` | Conversation memory per user |
| `workflows/{name}` | Saved workflow steps |

---

## Security & Privacy

- **No data leaves your machine** except API calls to DO Gradient AI inference, DO App Platform backend, and Firestore
- Screenshots are captured in-memory and sent directly to the model -- never written to disk
- `.env` is gitignored -- API keys are never committed
- The overlay window is `focusable: false` by default -- it doesn't steal keyboard focus until summoned
- All shell commands are safety-checked -- dangerous commands (`rm -rf /`, `mkfs`, etc.) are blocked
- All inference routes through DO's secure, authenticated endpoints

---

## Troubleshooting

**Overlay doesn't appear**
```bash
# Check Python server is running
python app.py  # should print "Overlay client connected"
```

**Mouse clicks land in wrong place**
> Ensure macOS Accessibility permission is granted for Terminal and the Electron app.

**No audio from voice input**
> Check microphone permission in System Settings -> Privacy -> Microphone -> allow Electron.

**DO inference errors**
> Verify your `GRADIENT_MODEL_ACCESS_KEY` is set correctly in `.env`. Test with:
> ```bash
> curl -X POST https://inference.do-ai.run/v1/chat/completions \
>   -H "Authorization: Bearer $GRADIENT_MODEL_ACCESS_KEY" \
>   -H "Content-Type: application/json" \
>   -d '{"model":"llama3.3-70b-instruct","messages":[{"role":"user","content":"hello"}],"max_completion_tokens":256}'
> ```

---

## Roadmap

- [ ] Deploy agents via DO Agent Development Kit (ADK)
- [ ] DO Knowledge Bases for RAG-powered agent memory
- [ ] DO Guardrails for safe agent action filtering
- [ ] Multi-user sessions with per-user isolation
- [ ] Windows + Linux support
- [ ] Workflow sharing and export/import
- [ ] Proactive agent heartbeat (checks in on you periodically)

---

## Credits & Acknowledgements

- **[DigitalOcean Gradient AI](https://docs.digitalocean.com/products/gradient-ai-platform/)** -- Serverless inference powering all AI agents
- **[Gemini Live API](https://ai.google.dev/gemini-api/docs/live)** -- Real-time voice streaming
- **[browser-use](https://github.com/browser-use/browser-use)** -- Browser automation framework
- **[Google GenAI SDK](https://ai.google.dev)** -- Multimodal AI backbone
- **[Electron](https://electronjs.org)** -- Desktop overlay framework

---

## License

MIT License -- see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with DigitalOcean Gradient AI for the [DigitalOcean Gradient AI Hackathon](https://digitalocean.devpost.com)**

*GhostOps -- because the best interface is the one that's invisible*

</div>
