# GhostOps Setup Instructions

## Overview
We are building GhostOps by combining:
- **CLOVIS** (inspiration repo) — Electron overlay, vision agent, routing, screen annotation
- **GhostOps** (our code) — Live API voice, Firestore memory, Cloud Run backend

The end result is a voice-controlled desktop agent with visual overlay, workflow learning, and cloud persistence.

---

## Phase 1: Copy CLOVIS Code Into GhostOps

### Step 1.1: Backup current GhostOps code
```bash
cd /Users/j_kanishkha/Projects/hack/ghostops
mkdir -p _backup
cp -r desktop/ _backup/desktop
cp -r backend/ _backup/backend
cp -r tests/ _backup/tests
cp -r deploy/ _backup/deploy
cp pyproject.toml _backup/pyproject.toml
cp Dockerfile _backup/Dockerfile
```

**Test:** `ls _backup/` should show desktop, backend, tests, deploy, pyproject.toml, Dockerfile

### Step 1.2: Copy CLOVIS core folders into ghostops
```bash
cd /Users/j_kanishkha/Projects/hack/ghostops

# Copy CLOVIS source folders
cp -r /Users/j_kanishkha/Projects/hack/inspiration/2026-Gemini-Competition-Submission/agents ./agents
cp -r /Users/j_kanishkha/Projects/hack/inspiration/2026-Gemini-Competition-Submission/models ./models
cp -r /Users/j_kanishkha/Projects/hack/inspiration/2026-Gemini-Competition-Submission/ui ./ui
cp -r /Users/j_kanishkha/Projects/hack/inspiration/2026-Gemini-Competition-Submission/core ./core
cp -r /Users/j_kanishkha/Projects/hack/inspiration/2026-Gemini-Competition-Submission/integrations ./integrations

# Copy CLOVIS entry point and config
cp /Users/j_kanishkha/Projects/hack/inspiration/2026-Gemini-Competition-Submission/app.py ./app.py
cp /Users/j_kanishkha/Projects/hack/inspiration/2026-Gemini-Competition-Submission/settings.json ./settings.json
cp /Users/j_kanishkha/Projects/hack/inspiration/2026-Gemini-Competition-Submission/requirements.txt ./requirements_clovis.txt
```

**Test:** `ls agents/ models/ ui/ core/ integrations/ app.py settings.json` — all should exist

### Step 1.3: Rename "clovis" agent folder to "screen"
The `agents/clovis/` folder handles screen annotation. Rename it to avoid confusion with the CLOVIS project name.

```bash
cd /Users/j_kanishkha/Projects/hack/ghostops
mv agents/clovis agents/screen
```

**Test:** `ls agents/` should show: `browser/`, `cua_cli/`, `cua_vision/`, `screen/`

### Step 1.4: Create the new folders for our additions
```bash
cd /Users/j_kanishkha/Projects/hack/ghostops
mkdir -p voice
mkdir -p agents/workflow
```

**Test:** `ls voice/ agents/workflow/` — both should exist (empty for now)

---

## Phase 2: Rename All CLOVIS References to GhostOps

### Step 2.1: Rename in Python files
Search and replace ALL occurrences of "CLOVIS" and "clovis" across the codebase.

**Files to update (search all `.py` files in agents/, models/, core/, integrations/, and app.py):**

| Find | Replace with |
|------|-------------|
| `CLOVIS` (uppercase) | `GhostOps` |
| `clovis` (lowercase, in strings/comments) | `ghostops` |
| `agents.clovis` (import paths) | `agents.screen` |
| `from agents.clovis` | `from agents.screen` |
| `agents/clovis` (file path refs) | `agents/screen` |
| `invoke_clovis` (function call name in routing) | `invoke_screen_annotator` |
| `CLOVIS model` (in comments/prompts) | `Screen Annotator` |

**Key files that MUST be updated:**
1. `models/models.py` — has many references to `clovis` in routing logic and imports
2. `models/function_calls.py` — has `invoke_clovis` function declaration
3. `models/prompts.py` — has CLOVIS in the system prompt
4. `agents/screen/agent.py` — rename class from ClovisAgent to ScreenAgent
5. `agents/screen/prompts.py` — rename references
6. `agents/screen/tools.py` — rename references
7. `app.py` — rename references
8. `core/settings.py` — rename `clovis_model` to `screen_model` if present

**How to do it:**
```bash
cd /Users/j_kanishkha/Projects/hack/ghostops

# Find all files with clovis references (excluding .venv, _backup, node_modules)
grep -r -l "clovis\|CLOVIS" --include="*.py" --include="*.js" --include="*.json" \
  --exclude-dir=.venv --exclude-dir=_backup --exclude-dir=node_modules .
```

Then for each file, replace:
- Import paths: `from agents.clovis` → `from agents.screen`
- Function names: `invoke_clovis` → `invoke_screen_annotator`
- Class names: `ClovisAgent` → `ScreenAgent` (if exists)
- Display strings: `"CLOVIS"` → `"GhostOps"`
- Model config keys: `clovis_model` → `screen_model`

**Test after renaming:**
```bash
# Should return ZERO results
grep -r "clovis\|CLOVIS" --include="*.py" --include="*.js" \
  --exclude-dir=.venv --exclude-dir=_backup --exclude-dir=node_modules .
```

### Step 2.2: Update settings.json
Edit `settings.json`:
- Change `"clovis_model"` key to `"screen_model"` (if present)
- Keep the model value the same (e.g., `"gemini-3-flash-preview"`)

### Step 2.3: Update the Electron UI title
In `ui/main.js`, find any window title references and change to "GhostOps".

**Test:** No file in the project should contain "clovis" or "CLOVIS" (except maybe a credit comment in README).

---

## Phase 3: Merge Dependencies

### Step 3.1: Merge requirements
We need both CLOVIS's dependencies and GhostOps's. Create a unified `requirements.txt`:

```bash
cd /Users/j_kanishkha/Projects/hack/ghostops
```

The final `requirements.txt` should contain (merge `requirements_clovis.txt` with what GhostOps needs):

```
# Core AI
google-genai>=1.67.0
google-adk>=0.1.0
google-cloud-firestore>=2.19.0

# Backend
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9
httpx>=0.27.0
python-dotenv>=1.0.0
pydantic>=2.0.0

# Desktop / CUA
pyaudio>=0.2.14
mss>=9.0.2
Pillow>=10.0.0
pyautogui>=0.9.54
pygetwindow>=0.0.9
keyboard>=0.13.5
numpy>=1.24.0

# Browser (optional, CLOVIS has it)
browser-use
playwright

# Audio (CLOVIS TTS - optional)
requests>=2.31.0
python-vlc>=3.0.18122

# WebSocket (CLOVIS UI server)
websockets
```

### Step 3.2: Install dependencies

use uv pls, that is much better 
```bash
cd /Users/j_kanishkha/Projects/hack/ghostops
source .venv/bin/activate
pip install -r requirements.txt
```

**Test:** `python -c "import google.genai; import pyaudio; import mss; import websockets; print('All imports OK')"` should print "All imports OK"

### Step 3.3: Install Electron dependencies
```bash
cd /Users/j_kanishkha/Projects/hack/ghostops/ui
npm install
```

**Test:** `ls ui/node_modules/electron/` should exist

---

## Phase 4: Verify CLOVIS Core Works

### Step 4.1: Test the Electron overlay launches
```bash
cd /Users/j_kanishkha/Projects/hack/ghostops/ui
npx electron .
```

**Test:** A transparent overlay window should appear on your screen. Close it with Cmd+Q.

### Step 4.2: Test screenshot capture
```bash
cd /Users/j_kanishkha/Projects/hack/ghostops
source .venv/bin/activate
python -c "
from desktop.screen import _capture_raw
raw = _capture_raw()
print(f'Screenshot: {len(raw)} bytes')
assert len(raw) > 1000, 'Screenshot too small'
print('OK')
"
```

### Step 4.3: Test Gemini API connection
```bash
source .venv/bin/activate
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
resp = client.models.generate_content(model='gemini-2.0-flash', contents='Say OK')
print(f'Gemini: {resp.text}')
"
```

**Test:** Should print "OK" or similar.

### Step 4.4: Test Live API voice (the proven test)
```bash
source .venv/bin/activate
python -c "
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
import pyaudio
from google import genai
from google.genai import types

async def test():
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    config = types.LiveConnectConfig(response_modalities=['AUDIO'])
    pya = pyaudio.PyAudio()
    spk = pya.open(format=pyaudio.paInt16, channels=1, rate=24000, output=True, frames_per_buffer=1024)
    async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
        await session.send_client_content(
            turns=types.Content(role='user', parts=[types.Part(text='Say: GhostOps is alive')])
        )
        audio_bytes = 0
        async for resp in session.receive():
            if resp.data:
                spk.write(resp.data)
                audio_bytes += len(resp.data)
            if resp.server_content and resp.server_content.turn_complete:
                break
        print(f'Audio played: {audio_bytes} bytes')
    spk.stop_stream(); spk.close(); pya.terminate()
    print('VOICE TEST PASSED' if audio_bytes > 0 else 'VOICE TEST FAILED')

asyncio.run(test())
"
```

**Test:** You should HEAR "GhostOps is alive" from your speakers.

---

## Phase 5: Initialize Git (Fresh History)

### Step 5.1: Remove any existing git history
```bash
cd /Users/j_kanishkha/Projects/hack/ghostops
rm -rf .git
```

### Step 5.2: Create .gitignore
Create a `.gitignore` file with:
```
.venv/
__pycache__/
*.pyc
.env
node_modules/
y/
_backup/
.claude/
*.egg-info/
dist/
build/
settings.json
```

### Step 5.3: Initialize fresh repo
```bash
cd /Users/j_kanishkha/Projects/hack/ghostops
git init
git add -A
git commit -m "Initial commit: GhostOps base (CLOVIS overlay + GhostOps voice/memory)

Built on top of CLOVIS (https://github.com/user/2026-Gemini-Competition-Submission)
with original author credit. Added voice (Gemini Live API), memory (Firestore),
and cloud deployment (Cloud Run).
"
```

**Test:** `git log --oneline` should show exactly 1 commit.

---

## Phase 6: Build New Features (in this order)

After all the above is verified, proceed to build:

### 6.1: Voice Module (`voice/live_api.py`)
Create a clean voice module that:
- Connects to Gemini Live API
- Streams mic audio in, plays speaker audio out
- Handles tool calls by dispatching to the CLOVIS routing or ADK agents
- Tool: `execute_task(description)` — sends complex tasks to ADK
- Tool: `get_screen_context()` — captures screenshot, describes via Gemini
- Tool: `start_recording()` — begins workflow recording
- Tool: `stop_recording(name)` — stops and saves workflow
- Tool: `replay_workflow(name)` — replays a saved workflow

Source reference: Lift audio I/O from `_backup/desktop/main.py` (lines 60-290).
The Live API connection, mic thread, speaker thread, send/receive loops are all proven working.

**Test:** Run the voice module standalone. Say "hello" and get audio response back.

### 6.2: ADK Agent Wrappers (`models/adk_agents.py`)
Create thin ADK wrappers around CLOVIS's existing agents:
- `RouterAgent` — dispatches to sub-agents based on user intent
- `ScreenAgent` — wraps `agents/screen/` annotation logic
- `DesktopAgent` — wraps `agents/cua_vision/` vision-action loop
- `CLIAgent` — wraps `agents/cua_cli/` shell execution
- `WorkflowAgent` — NEW agent for recording/replay

Each wrapper should be ~20-30 lines. Call the existing CLOVIS functions, don't rewrite them.

**Test:** Call each ADK agent directly with a test prompt and verify it returns a result.

### 6.3: Workflow Engine (`agents/workflow/engine.py`)
The wow factor. Build:

**Recording mode:**
- Captures screenshot every 2 seconds into an in-memory list
- Stores Live API voice transcription alongside (what user narrates)
- Start with voice command "watch me" or "start recording"
- Stop with "remember this as [name]"

**Step extraction:**
- Send all captured screenshots + transcription to Gemini 2.5 Flash
- Prompt: "The user performed a workflow. Here are screenshots taken every 2 seconds, and their narration: [text]. Extract the workflow as a JSON array of steps: [{step_number, action, target_description, value_if_any}]"
- Parse the JSON response

**Workflow storage:**
- Save to Firestore: `workflows/{name}` with steps JSON and metadata
- Load by name

**Replay engine:**
- For each step in the workflow:
  1. Take screenshot
  2. Send to Gemini: "Find the element described as '{target_description}' and return its x,y coordinates in 1280x720 space"
  3. Execute the action (click, type, etc.) using CLOVIS's existing CUA tools
  4. Take verification screenshot
  5. Send to Gemini: "Did this step succeed? The expected action was: {action} on {target}"
  6. If yes, continue. If no, retry once or ask user via voice.
  7. Update overlay with status bubbles showing progress

**Test:** Record a simple workflow (open Safari, click address bar, type a URL). Replay it.

### 6.4: Cloud Run Backend
Lift from `_backup/backend/`. The backend should have:
- `POST /memory` — save workflow or turn to Firestore
- `GET /memory/{session_id}` — load workflows or turns
- `GET /health` — deployment proof

**Test:** `curl http://localhost:8080/health` returns `{"status": "ok"}`

### 6.5: Wire Everything Together
Update `app.py` to:
1. Start the Electron overlay (existing CLOVIS code)
2. Start the voice module (new)
3. Connect voice → ADK Router → agents → overlay

**Test:** Full end-to-end: speak a command, see the overlay respond, hear audio back.

---

## Phase 7: Deploy and Submit

### 7.1: Deploy backend to Cloud Run
```bash
cd /Users/j_kanishkha/Projects/hack/ghostops
bash deploy/deploy.sh
```

### 7.2: Record deployment proof
Screen record the GCP console showing the Cloud Run service running.

### 7.3: Record demo video (<4 minutes)
Follow this script:
1. Show GhostOps starting up, greeting via voice
2. Voice command: "Open Safari and go to Google Forms"
3. "Watch what I do" → fill out a form manually
4. "Remember this as demo-form"
5. "Run demo-form" → Ghost replays autonomously with overlay
6. "What workflows do I know?" → Ghost lists them
7. Architecture diagram + tech stack
8. Credits to CLOVIS

### 7.4: Create architecture diagram
Use any diagramming tool. Show:
- Electron Overlay ↔ WebSocket ↔ Python Core
- Python Core: Live API (voice) + ADK Agents (routing) + Workflow Engine
- Cloud Run Backend ↔ Firestore

### 7.5: Submit on Devpost
- Text description
- GitHub repo URL
- Deployment proof video
- Architecture diagram
- Demo video

---

## Quick Reference: File Structure After All Phases

```
ghostops/
├── app.py                      ← Main entry (CLOVIS, modified)
├── agents/
│   ├── screen/                 ← Was agents/clovis/ (renamed)
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   └── tools.py
│   ├── cua_vision/             ← Desktop control (CLOVIS)
│   ├── cua_cli/                ← Shell execution (CLOVIS)
│   ├── browser/                ← Web automation (CLOVIS, stub)
│   └── workflow/               ← NEW: record/replay engine
│       ├── __init__.py
│       └── engine.py
├── models/
│   ├── models.py               ← Routing (modified for ADK)
│   ├── adk_agents.py           ← NEW: ADK agent wrappers
│   ├── function_calls.py       ← Tool declarations (renamed)
│   └── prompts.py              ← System prompts (renamed)
├── voice/
│   ├── __init__.py
│   └── live_api.py             ← NEW: Gemini Live API voice
├── core/
│   ├── settings.py             ← Config (CLOVIS)
│   └── registry.py             ← UI state (CLOVIS)
├── ui/
│   ├── main.js                 ← Electron main (CLOVIS)
│   ├── renderer.js             ← Canvas drawing (CLOVIS)
│   ├── server.py               ← WebSocket server (CLOVIS)
│   ├── package.json
│   └── visualization_api/      ← Drawing helpers (CLOVIS)
├── integrations/
│   └── audio/                  ← TTS (CLOVIS, optional)
├── backend/
│   ├── main.py                 ← FastAPI (GhostOps)
│   └── memory.py               ← Firestore (GhostOps)
├── desktop/
│   ├── screen.py               ← Screenshot capture (GhostOps)
│   └── memory_client.py        ← HTTP client (GhostOps)
├── deploy/
│   └── deploy.sh               ← Cloud Run deployment
├── tests/
│   └── test_smoke.py           ← 3 smoke tests
├── _backup/                    ← Original GhostOps code
├── requirements.txt            ← Merged dependencies
├── Dockerfile
├── .env
├── .gitignore
└── README.md
```
