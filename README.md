<div align="center">

<img src="https://img.shields.io/badge/GhostOps-AI%20Desktop%20Agent-00C8B4?style=for-the-badge&logo=ghost&logoColor=white" alt="GhostOps"/>

# 👻 GhostOps

### *Your invisible AI co-pilot. It sees your screen, learns your workflows, and acts on your behalf.*

[![Gemini Live API](https://img.shields.io/badge/Gemini%20Live%20API-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Run%20%2B%20Firestore-4285F4?style=flat-square&logo=googlecloud&logoColor=white)](https://cloud.google.com)
[![Electron](https://img.shields.io/badge/Electron-Overlay%20UI-47848F?style=flat-square&logo=electron&logoColor=white)](https://electronjs.org)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Groq](https://img.shields.io/badge/Groq-Vision%20%2B%20Text-F55036?style=flat-square)](https://groq.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

> **Built for the [Gemini Live Agent Challenge 2026](https://devpost.com) — UI Navigator category**
> A transparent, always-on desktop overlay powered by multimodal AI that sees, hears, speaks, and acts.

</div>

---

## ✨ What is GhostOps?

GhostOps is a **transparent Electron overlay** that sits invisibly above every window on your desktop. Press one shortcut and it appears — ready to answer questions, annotate your screen, control your computer, automate browser tasks, or **learn and replay your entire workflows**.

It's not a chatbot in a window. It *is* the window.

```
You press ⌘+Shift+Space
         │
         ▼
  ┌──────────────────────────────────────┐
  │  👻  Hey Kanishkha — what do you need? │  ← floating over your real screen
  └──────────────────────────────────────┘
         │
  You type: "watch me set up this repo"
         │
         ▼
  GhostOps records every action you take
  Then replays it perfectly on any machine
```

---

## 🎬 Demo

> **[▶ Watch the 4-minute demo video](#)** — Screen annotation → CLI control → Mouse automation → Workflow learning

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER'S DESKTOP                                  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │               ELECTRON OVERLAY  (always on top)                  │   │
│  │  • Transparent, focusable-on-demand panel                        │   │
│  │  • Canvas: bounding boxes, dots, annotation text                 │   │
│  │  • Command bar: text input + voice mic + drag handle             │   │
│  │  • Status bubbles: real-time task progress                       │   │
│  └─────────────────────┬────────────────────────────────────────────┘   │
│                        │  WebSocket (ws://127.0.0.1:PORT)               │
└────────────────────────┼────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────────┐
│                    PYTHON CORE  (app.py)                                │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   TWO-TIER GROQ ROUTER                          │   │
│  │  llama-3.1-8b-instant → decides which agent handles the task    │   │
│  │                                                                 │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │   │
│  │  │ direct   │ │ screen   │ │  cua_    │ │ browser  │          │   │
│  │  │ response │ │annotator │ │  vision  │ │  agent   │          │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │   │
│  │  ┌──────────┐ ┌──────────┐                                     │   │
│  │  │ cua_cli  │ │workflow  │  ← record/replay engine             │   │
│  │  └──────────┘ └──────────┘                                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────┐    ┌──────────────────────────────────────────┐  │
│  │  Groq Vision     │    │  Google Cloud                            │  │
│  │  llama-4-scout   │    │  ├─ Firestore  (session memory)          │  │
│  │  (screen see)    │    │  ├─ Cloud Run  (backend API)             │  │
│  └──────────────────┘    │  └─ Gemini 2.5 Flash (voice/vision)     │  │
│                          └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Feature Overview

| Feature | Description | Shortcut / Command |
|---|---|---|
| 🧠 **Direct Q&A** | Instant answers without any agent | *"what is 42 × 37"* |
| 🔍 **Screen Annotation** | Floating bounding boxes over live UI | *"what's on my screen"* |
| 🖱️ **Computer Use** | Sees screen → moves cursor → clicks | *"click the new note button"* |
| ⌨️ **CLI Control** | Shell commands, file ops, open apps | *"open notion"* |
| 🌐 **Browser Agent** | Full Playwright web automation | *"search google for X"* |
| 📸 **Screen Context** | Reads screen then acts on what it sees | *"open this repo in Cursor"* |
| 🎙️ **Voice Input** | Whisper STT via mic button | Click 🎤 in overlay |
| 🔁 **Workflow Record** | Watch user → extract steps | *"watch me"* |
| ▶️ **Workflow Replay** | Replay saved workflows via vision | *"replay my-workflow"* |
| 💾 **Memory** | Firestore session memory across restarts | Auto on startup |
| 🎨 **Personalized** | Name-aware, personality-driven responses | `settings.json` |

---

## 🧠 Agent Routing

Every input is routed by a lightweight LLM (Groq llama-3.1-8b-instant, 500K TPD) to the right specialist:

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                  ROUTER (8b-instant)                │
└──┬──────────┬──────────┬──────────┬──────────┬──────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
direct    screen      cua_cli   cua_vision  browser
response  annotator   (shell)   (mouse+KB)  (playwright)
   │          │          │          │          │
   │     bounding    open -a    go_to_     navigate
   │      boxes      Notion     element    click
   │     + labels    git clone  click_left fill form
   ▼          │      ls ~/      type_str   submit
 answer   overlay       │          │          │
          text     terminal   cursor      chrome
                   output     moves
```

---

## 🔁 Workflow Engine

The standout feature. GhostOps **watches you work** and learns to replicate it:

```
RECORD                           EXTRACT                      REPLAY
──────                           ───────                      ──────
User: "watch me"                 Last frame → Groq            For each step:
  │                              vision →                       │
  ▼                              JSON steps:                    ▼
Screenshot every 2s              [{                          VisionAgent.execute(
  +                                action: "click",           "click the New Page
  voice transcription              target: "New Page btn",     button"
  captured into frames             value: ""                 )
  │                              }, ...]                        │
  ▼                                  │                          ▼
User: "remember this             Saved to                   Screenshot →
  as new-page"                   Firestore +                find element →
                                 local cache                move cursor →
                                                            click →
                                                            verify → next step
```

---

## 📦 Installation

### Prerequisites

| Requirement | Version |
|---|---|
| macOS | 12+ (Monterey or later) |
| Python | 3.13+ |
| Node.js | 18+ |
| uv | latest |

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/ghostops.git
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
# Required
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
GOOGLE_CLOUD_PROJECT=your_gcp_project_id

# Optional
ELEVENLABS_API_KEY=your_elevenlabs_key   # for voice output
CLOUD_RUN_URL=https://your-service.run.app  # for persistent memory
FIRESTORE_SESSION_ID=your_username
```

> 💡 **Get your keys:**
> - Gemini: [aistudio.google.com](https://aistudio.google.com) → Get API Key
> - Groq: [console.groq.com](https://console.groq.com) → API Keys (free tier)
> - GCP: [console.cloud.google.com](https://console.cloud.google.com) → create project

### 5. Personalize (optional but recommended)

Edit `settings.json`:

```json
{
  "user_name": "YourName",
  "agent_name": "GhostOps",
  "personalization": "Be concise and slightly witty. You know your user prefers terminal over GUI."
}
```

### 6. Grant macOS permissions

GhostOps needs screen recording and accessibility access:

1. **System Settings → Privacy & Security → Screen Recording** → add Terminal + Electron
2. **System Settings → Privacy & Security → Accessibility** → add Terminal + Electron
3. **System Settings → Privacy & Security → Microphone** → add Electron (for voice input)

### 7. Run GhostOps

Open **two terminals**:

**Terminal 1 — Python backend:**
```bash
source .venv/bin/activate
python app.py
```

**Terminal 2 — Electron overlay:**
```bash
cd ui
npm run dev
```

You should see:
```
Models loaded - Rapid: gemini-2.5-flash, GhostOps: gemini-2.5-flash
Visualization server listening at ws://127.0.0.1:XXXX
Overlay client connected.
```

---

## 🎮 Usage

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `⌘ + Shift + Space` | Show/hide the command overlay |
| `⌘ + Shift + C` | Stop all running tasks immediately |
| `⌘ + Shift + M` | Toggle TTS mute |
| `Escape` | Dismiss overlay |
| `Enter` | Submit command |

### Command Examples

**💬 Direct answers**
```
"what's the square root of 144"
"what time zone is Tokyo in"
"explain what a webhook is"
```

**🔍 Screen annotation**
```
"what's on my screen"
"explain what I'm looking at"
"what does this button do"
"point to the settings icon"
```

**⌨️ CLI tasks**
```
"open notion"
"create a folder called projects on my desktop"
"list my downloads folder"
"what's my local IP address"
"check if git is installed"
```

**🖱️ Computer use** *(app must be open)*
```
"click the new note button"
"type hello world in the search bar"
"click settings in the menu"
"calculate 18% tip on $84 using the calculator"
```

**🌐 Browser automation**
```
"search google for best coffee shops near me"
"go to github.com and search for electron"
"open youtube and search for lofi music"
```

**📸 Screen context** *(reads what's on screen first)*
```
"open this repo in Cursor"
"run the dev server I can see"
"clone and run this project"
```

**🔁 Workflow learning**
```
# Start recording
"watch me"

# Do your workflow manually (GhostOps records every 2 seconds)
# Open an app, fill a form, set up a project...

# Save it
"remember this as setup-project"

# Replay any time
"replay setup-project"
```

---

## 🗂️ Project Structure

```
ghostops/
│
├── 📄 app.py                        ← Main entry point
├── ⚙️  settings.json                 ← User config (name, personality, models)
├── 🔑 .env                          ← API keys (never committed)
│
├── 🤖 agents/
│   ├── screen/                      ← Screen annotation (bounding boxes + labels)
│   │   ├── agent.py
│   │   ├── tools.py                 ← draw_bounding_box, draw_text, etc.
│   │   └── prompts.py
│   │
│   ├── cua_vision/                  ← Computer use (sees screen → clicks)
│   │   ├── agent.py                 ← VisionAgent
│   │   ├── single_call.py           ← Main execution loop + loop detection
│   │   ├── tools.py                 ← go_to_element, click, type_string, etc.
│   │   └── prompts.py
│   │
│   ├── cua_cli/                     ← Shell agent (subprocess execution)
│   │   └── agent.py                 ← CLIAgent, runs shell commands safely
│   │
│   ├── browser/                     ← Browser automation (Playwright + browser-use)
│   │   └── agent.py
│   │
│   └── workflow/                    ← Record + replay engine
│       └── engine.py                ← start_recording, stop_and_save, replay
│
├── 🧠 models/
│   ├── models.py                    ← Two-tier Groq router + agent dispatch
│   ├── function_calls.py            ← Tool declarations for all 6 routes
│   └── prompts.py                   ← Personalized system prompts
│
├── 🎙️  voice/
│   └── live_api.py                  ← Gemini Live API voice session
│
├── 🖥️  ui/
│   ├── main.js                      ← Electron main process
│   ├── renderer.js                  ← Canvas rendering + WebSocket client
│   ├── preload.js                   ← IPC bridge
│   ├── index.html                   ← Overlay HTML
│   ├── animations/
│   │   ├── command_overlay.js       ← Input bar, drag, voice mic
│   │   ├── command_overlay.css
│   │   ├── status_bubble.js         ← Task progress indicator
│   │   └── screen_glow.js
│   └── dom_nodes/
│       ├── overlay_text.js          ← Draggable AI response bubbles
│       └── overlay_box.js           ← Annotation box elements
│
├── 🔧 core/
│   ├── settings.py                  ← Read/write settings.json
│   ├── groq_provider.py             ← Groq text + vision + STT (Whisper)
│   └── registry.py                  ← Shared overlay state
│
├── 🖼️  desktop/
│   └── screen.py                    ← Screenshot capture (PIL/mss)
│
├── 🔗 integrations/
│   └── audio/
│       └── tts.py                   ← ElevenLabs TTS
│
├── ☁️  backend/
│   ├── main.py                      ← FastAPI backend (Cloud Run)
│   └── memory.py                    ← Firestore memory read/write
│
└── 🚀 deploy/
    └── deploy.sh                    ← One-command Cloud Run deployment
```

---

## ☁️ Cloud Deployment

GhostOps uses **Google Cloud Run** for the persistent backend (memory, workflow storage) and **Firestore** for session data.

### Deploy the backend

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com firestore.googleapis.com aiplatform.googleapis.com

# Deploy in one command
bash deploy/deploy.sh
```

After deployment, copy the Cloud Run URL into your `.env`:
```env
CLOUD_RUN_URL=https://ghostops-backend-xxxx-uc.a.run.app
```

### Firestore collections

| Collection | Purpose |
|---|---|
| `sessions/{id}/turns` | Conversation memory per user |
| `workflows/{name}` | Saved workflow steps |

---

## 🔬 How the Vision Loop Works

When GhostOps performs a computer-use task (clicking, typing, navigating), this is the per-step loop:

```
┌─────────────────────────────────────────────────────────────┐
│                    SINGLE CALL VISION ENGINE                │
└───────────────────────────┬─────────────────────────────────┘
                            │
            ┌───────────────▼───────────────┐
            │  1. Capture screenshot         │
            │     (active window or full)    │
            └───────────────┬───────────────┘
                            │
            ┌───────────────▼───────────────┐
            │  2. Send to Groq llama-4-scout │
            │     with task + tool schema    │
            └───────────────┬───────────────┘
                            │
            ┌───────────────▼───────────────┐
            │  3. Model returns tool calls:  │
            │     go_to_element(bbox)        │
            │     click_left_click()         │
            │     type_string("hello")       │
            │     press_ctrl_hotkey("s")     │
            │     task_is_complete()         │
            └───────────────┬───────────────┘
                            │
            ┌───────────────▼───────────────┐
            │  4. Execute tool calls         │
            │     (pyautogui / subprocess)   │
            └───────────────┬───────────────┘
                            │
            ┌───────────────▼───────────────┐
            │  5. Loop detection:            │
            │     same action ×3 → stop      │
            │     same click ×5 → fallback   │
            └───────────────┬───────────────┘
                            │
                     task_is_complete?
                      YES ──┘  NO → back to step 1
```

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Overlay UI** | Electron + HTML Canvas | Transparent, always-on-top, cross-workspace |
| **IPC** | WebSocket (Python ↔ Electron) | Low-latency bidirectional drawing commands |
| **Router LLM** | Groq llama-3.1-8b-instant | 500K TPD, fast enough for routing decisions |
| **Vision LLM** | Groq llama-4-scout-17b | 500K TPD, multimodal, tool calling |
| **Voice** | Gemini Live API (2.5 Flash) | Real-time streaming audio, lowest latency |
| **Browser** | Playwright + browser-use | Reliable cross-browser automation |
| **Screenshot** | PIL ImageGrab + mss | macOS-native, low overhead |
| **Mouse/KB** | pyautogui | Cross-platform desktop control |
| **Memory** | Google Cloud Firestore | Real-time, serverless, persistent |
| **Backend** | FastAPI on Cloud Run | Auto-scaling, no cold starts |
| **STT** | Groq Whisper (large-v3-turbo) | Fast, accurate, on-demand |
| **TTS** | ElevenLabs (optional) | Natural voice output |

---

## ⚡ Model Usage & Limits

| Model | Used For | Daily Limit |
|---|---|---|
| `llama-3.1-8b-instant` | Routing decisions | 500K tokens/day |
| `llama-4-scout-17b` | Vision + screen understanding | 500K tokens/day |
| `whisper-large-v3-turbo` | Voice transcription (STT) | On-demand |
| `gemini-2.5-flash` | Voice sessions (Live API) | Quota-based |

> 💡 To avoid daily limits, switch vision calls to **Vertex AI** (uses GCP credits):
> ```python
> # In models/models.py line ~867:
> self.client = genai.Client(vertexai=True, project="your-project", location="us-central1")
> ```

---

## 🔒 Security & Privacy

- **No data leaves your machine** except API calls (Groq, Gemini, Firestore)
- Screenshots are captured in-memory and sent directly to the model — never written to disk
- `.env` is gitignored — API keys are never committed
- The overlay window is `focusable: false` by default — it doesn't steal keyboard focus until you summon it
- All shell commands run as your user — no privilege escalation

---

## 🐛 Troubleshooting

**Overlay doesn't appear**
```bash
# Check Python server is running
python app.py  # should print "Overlay client connected"
```

**"Rate limit exceeded" errors**
> The 500K daily token limit resets at midnight UTC. Switch to Vertex AI for unlimited usage with your GCP credits.

**Mouse clicks land in wrong place**
> Ensure macOS Accessibility permission is granted for Terminal and the Electron app.

**No audio from voice input**
> Check microphone permission in System Settings → Privacy → Microphone → allow Electron.

**Firestore writes failing**
> Either deploy the backend (`bash deploy/deploy.sh`) or set `CLOUD_RUN_URL=http://localhost:8080` and run the backend locally.

---

## 🗺️ Roadmap

- [ ] **Vertex AI integration** — unlimited vision quota via GCP credits
- [ ] **Playwright browser recording** — record browser workflows, not just desktop
- [ ] **Proactive heartbeat** — agent checks in on you periodically (Cloud Scheduler)
- [ ] **Multi-user sessions** — per-user Firestore isolation with auth
- [ ] **Windows support** — pyautogui + Electron already cross-platform, needs testing
- [ ] **Workflow sharing** — export/import workflows between users

---

## 🙏 Credits & Acknowledgements

GhostOps is built on the shoulders of:

- **[CLOVIS](https://github.com/original/clovis)** — The Electron overlay architecture, canvas rendering system, two-tier Groq router, and CUA vision loop. Core UI and agent dispatch design.
- **[browser-use](https://github.com/browser-use/browser-use)** — Browser automation framework
- **[Gemini Live API](https://ai.google.dev/gemini-api/docs/live)** — Real-time voice streaming
- **[Groq](https://groq.com)** — Ultra-fast LLM inference

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with 👻 + ☕ in 72 hours for the Gemini Live Agent Challenge 2026**

*GhostOps — because the best interface is the one that's invisible*

</div>
