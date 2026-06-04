# OASIS-X — Autonomous Fibre Fault Healing System

**Smart Waveform Integrated Fibre-optic Transmission — Fault Healing System**

Real-time autonomous optical fibre fault healing dashboard for Nigerian networks with live telemetry, ML-based anomaly detection, LLM-powered chat (Nexus AI), digital twin simulation, per-user profiles, complaint system, and LLM-generated 4-line network summaries.

---

## Features

- **Real-Time Pipeline** — Generate 50–1000 telemetry samples per run with city-specific environmental degradation (harmattan, rain attenuation, generator failures, peak congestion)
- **ML Anomaly Detection** — Isolation Forest with adaptive thresholding
- **NCC Compliance** — Per-city QoS baselines for Lagos, Abuja, Port Harcourt, Kano
- **Nexus AI Chat** — Conversational LLM (technical/simple mode) with dashboard context awareness
- **Fault Injection** — One-click fibre cut, generator failure, harmattan degradation, rain attenuation, peak congestion
- **4-Line Summary** — Auto-generated network situation summary after every pipeline run/diagnosis
- **Per-User Profiles** — Theme (dark/light), avatar, display name, activity feed
- **Complaint System** — Real-time user-to-agent chat with polling
- **LLM Diagnosis** — Custom `swift-fhs` model with graceful rule-engine fallback
- **Digital Twin** — Season-aware environmental simulation
- **Interactive Login** — Animated geometric background blobs that morph on proximity and burst on click

## Tech Stack

| Component | Technology |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **ML / Data** | scikit-learn (Isolation Forest), pandas, NumPy |
| **LLM Runtime** | Ollama (local or remote) + `nexus-chat` & `swift-fhs` models |
| **Visualisation** | Chart.js 4.x (CDN), pure CSS dark/light themes |
| **Database** | SQLite (per-user profiles, complaints, pipeline logs) |
| **Auth** | JWT (python-jose + passlib/bcrypt) |

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/download) (for LLM features — system works without it)
- Git

### Installation

```bash
# 1. Clone
git clone https://github.com/jaycode100-sys/oasis-x.git
cd oasis-x

# 2. Virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up LLM models (optional — skip if you don't want AI features)
ollama serve
ollama pull llama3.2:1b
ollama create nexus-chat -f models\.ollama\ChatModelfile
ollama create swift-fhs -f models\.ollama\Modelfile

# 5. Configure environment
copy .env.example .env
# Edit .env — at minimum set OASIS_SECRET_KEY

# 6. Start the server
python start_server.py

# 7. Open the dashboard
# http://localhost:8080
```

### Docker / Railway (One-Click Deploy)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/oasis-x)

The project includes `Procfile`, `railway.json`, and `nixpacks.toml` for zero-config deployment. Set `OASIS_SECRET_KEY` as a Railway environment variable.

## Default Credentials

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Superadmin |
| `user` | `user123` | Regular User |

*The login page does not display credentials. Users must know them in advance.*

## API Endpoints

### Health & Status
- `GET /api/status` — Health check

### Authentication
- `POST /api/auth/login` — Login (returns JWT)
- `GET /api/auth/me` — Current user + profile

### Pipeline
- `POST /api/run` — Run the telemetry pipeline
- `GET /api/runs` — List pipeline runs
- `GET /api/logs/{run_id}` — Get specific run
- `DELETE /api/logs/{run_id}` — Delete a run

### Diagnosis
- `GET /api/diagnose/{row_index}` — Diagnose a specific row
- `GET /api/chat/diagnose` — Run Ollama diagnostics

### Chat
- `POST /api/chat` — Send message to Nexus AI
- `GET /api/chat/history` — Get chat history
- `DELETE /api/chat/history` — Clear chat history

### Summaries
- `POST /api/summarize` — Generate 4-line network summary

### Profile
- `GET /api/profile` — Get user profile
- `PUT /api/profile` — Update profile (theme, avatar, display name)

### Complaints
- `POST /api/complaints` — Create complaint
- `GET /api/complaints` — List complaints
- `GET /api/complaints/{id}/messages` — Get complaint messages
- `POST /api/complaints/{id}/messages` — Send message
- `POST /api/complaints/{id}/close` — Close complaint

### Activity
- `GET /api/activity` — Activity log (superadmin: all; user: own via `?own=true`)
- `POST /api/activity` — Log activity entry

### Fault Injection
- `POST /api/simulate/event/{event_type}` — Inject fault event

## LLM Models

| Model | Base | Purpose |
|---|---|---|
| `nexus-chat` | `llama3.2:1b` | Conversational chat (Nexus AI) |
| `swift-fhs` | `llama3.2:1b` | Structured JSON diagnosis |
| `llama3.2:1b` | — | Fallback for both |

- **Technical mode**: precise dB values, NCC thresholds
- **Simple mode**: plain language, everyday analogies

## Project Structure

```
├── api/
│   ├── app.py              # FastAPI app, CORS, static mount
│   ├── routes.py           # All API endpoints
│   └── auth.py             # JWT auth + seed users
├── data/
│   └── database.py         # SQLite wrapper (profiles, complaints, logs)
├── models/
│   ├── anomaly_detector.py # Isolation Forest
│   ├── data_simulator.py   # Telemetry generator
│   ├── ncc_feed.py         # NCC baselines + compliance
│   ├── decision_engine.py  # State-to-action mapping
│   └── .ollama/
│       ├── Modelfile       # swift-fhs model definition
│       └── ChatModelfile   # nexus-chat model definition
├── root/
│   ├── chat_agent.py       # Nexus AI chat orchestrator
│   └── llm_agent.py        # LLM diagnosis + 4-line summary
├── static/
│   ├── index.html          # Dashboard
│   ├── login.html          # Login page
│   ├── style.css           # Dark/light theme CSS
│   └── app.js              # Frontend logic
├── start_server.py         # Server launcher
├── simulator.py            # CLI simulation runner
├── main.py                 # Entry point for headless simulation
├── Procfile                # Railway start command
├── railway.json            # Railway deployment config
├── nixpacks.toml           # Nixpacks build config
├── .env.example            # Documented environment variables
└── requirements.txt        # Python dependencies
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | Server port (Railway auto-sets this) |
| `HOST` | `0.0.0.0` | Server bind address |
| `OASIS_SECRET_KEY` | — | **REQUIRED**: JWT signing key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `SWIFT_LLM_MODEL` | `swift-fhs` | Diagnosis model name |
| `CHAT_MODEL` | `nexus-chat` | Chat model name |
| `OLLAMA_TIMEOUT` | `120` | Ollama API timeout (seconds) |
| `OASIS_DB_DIR` | `data` | Database directory |
| `OASIS_DB_PATH` | `data/oasis.db` | Database file path |

## Desktop Application

To package OASIS-X as a standalone desktop app:

```bash
pip install pyinstaller pywebview
python build_desktop.py
```

This bundles the Python server + web frontend into a single `.exe` with an embedded webview window (no browser needed). Output is in `dist/OASIS-X/`.

## Railway Deployment

1. Push to GitHub
2. Create a new Railway project from your repo
3. Add `OASIS_SECRET_KEY` as an environment variable
4. Railway auto-detects `nixpacks.toml` and builds
5. Health check at `/api/status`
6. Your dashboard is live at `https://<project>.railway.app`

## License

Proprietary — OASIS-X is developed for network operations use.

---

*Built for the challenging conditions of Nigerian optical fibre networks — from the harmattan dust of Kano to the monsoon rains of Port Harcourt.*
