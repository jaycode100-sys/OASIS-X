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
- **Per-User Profiles** — Theme (dark/light), avatar, display name, activity feed, theme colour
- **Complaint System** — Real-time user-to-agent chat with polling
- **LLM Diagnosis** — Custom `swift-fhs` model with graceful rule-engine fallback
- **Digital Twin** — Season-aware environmental simulation
- **Interactive Login** — Animated geometric background blobs that morph on proximity and burst on click
- **Telegram & WhatsApp Notifications** — Send network summaries and incident alerts directly to your phone

## Tech Stack

| Component | Technology |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **ML / Data** | scikit-learn (Isolation Forest), pandas, NumPy |
| **LLM Runtime** | Ollama (local or remote) + `nexus-chat` & `swift-fhs` models |
| **Visualisation** | Chart.js 4.x (CDN), pure CSS dark/light themes |
| **Database** | SQLite (per-user profiles, complaints, pipeline logs) |
| **Auth** | JWT (python-jose + passlib/bcrypt) |
| **Notifications** | Telegram Bot API, WhatsApp Business API |

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com/download) (for LLM features — system works without it)
- Git

### Installation

```bash
# 1. Clone
git clone https://github.com/jaycode100-sys/OASIS-X.git
cd OASIS-X

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
ollama create nexus-chat -f models/.ollama/ChatModelfile
ollama create swift-fhs -f models/.ollama/Modelfile

# 5. Configure environment
cp .env.example .env
# Edit .env — at minimum set OASIS_SECRET_KEY

# 6. Start the server
python start_server.py

# 7. Open the dashboard
# http://localhost:8080
```

> **Note:** The server auto-starts Ollama and ensures models are available on first run. If Ollama is not installed, the system works without LLM features (rule-engine fallback for diagnosis, offline message for chat).

## Default Credentials

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Superadmin |
| `user` | `user123` | Regular User |

*The login page does not display credentials. Users must know them in advance.*

## Deploy to Render

1. Push to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Web Service**
3. Connect your GitHub repo `jaycode100-sys/OASIS-X`
4. Configure:
   - **Name:** `oasis-x`
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python start_server.py`
5. Add environment variables:
   - `OASIS_SECRET_KEY` — a random secret string (required for JWT)
   - `PORT` — `8080` (or leave default)
6. Click **Create Web Service**
7. Your dashboard is live at `https://<name>.onrender.com`

### Optional: Render Ollama Sidecar

For full AI features (Nexus chat, LLM diagnosis), deploy Ollama as a separate Render service:

1. Create a **Background Worker** service on Render
2. Use the `ollama/ollama:latest` Docker image
3. Add environment variable: `OLLAMA_BASE_URL=http://<ollama-service>.internal:11434` to your main web service
4. After both services start, open a shell in the Ollama worker and run:
   ```bash
   ollama pull llama3.2:1b
   ollama create nexus-chat -f models/.ollama/ChatModelfile
   ollama create swift-fhs -f models/.ollama/Modelfile
   ```

## Alternative Deployments

### Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/oasis-x)

The project includes `Procfile`, `railway.json`, and `nixpacks.toml` for zero-config deployment. Set `OASIS_SECRET_KEY` as a Railway environment variable.

### Docker

```bash
docker-compose up --build
```

The `docker-compose.yml` includes both the app and an Ollama sidecar with GPU support.

### Fly.io

```bash
fly launch
fly deploy
```

See `fly.toml` for the Ollama sidecar configuration.

## API Endpoints

### Health & Status
- `GET /api/status` — Health check
- `GET /api/llm-status` — Ollama/model availability

### Authentication
- `POST /api/auth/login` — Login (returns JWT)
- `POST /api/auth/signup` — Self-registration
- `GET /api/auth/me` — Current user + profile

### Pipeline
- `POST /api/run` — Run the telemetry pipeline
- `GET /api/logs` — List pipeline logs
- `POST /api/logs` — Save a pipeline run
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
- `PUT /api/profile` — Update profile (theme, avatar, display name, contacts)

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

### Notifications
- `POST /api/notifications/send-summary` — Send dashboard summary to saved contacts
- `POST /api/notifications/telegram` — Send raw Telegram message
- `POST /api/notifications/whatsapp` — Send raw WhatsApp message
- `POST /api/notifications/incident` — Send incident alert
- `POST /api/notifications/daily-summary` — Send daily network summary
- `GET /api/notifications/status` — Check channel availability

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
│   ├── auth.py             # JWT auth + seed users
│   └── notifications.py    # Telegram & WhatsApp integration
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
│   ├── signup.html         # Registration page
│   ├── landing.html        # Public landing page
│   ├── blog.html           # Documentation blog
│   ├── style.css           # Dark/light theme CSS
│   └── app.js              # Frontend logic
├── start_server.py         # Server launcher (auto-starts Ollama)
├── config.py               # Centralised pydantic-settings config
├── desktop_app.py          # Standalone desktop packaging
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container build
├── docker-compose.yml      # Multi-service setup (app + Ollama)
├── Procfile                # Railway/Render start command
├── render.yaml             # Render deployment config
├── fly.toml                # Fly.io deployment config
├── .env.example            # Documented environment variables
└── README.md               # This file
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | Server port |
| `HOST` | `0.0.0.0` | Server bind address |
| `OASIS_SECRET_KEY` | — | **REQUIRED**: JWT signing key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `SWIFT_LLM_MODEL` | `swift-fhs` | Diagnosis model name |
| `CHAT_MODEL` | `nexus-chat` | Chat model name |
| `OLLAMA_TIMEOUT` | `180` | Ollama API timeout (seconds) |
| `OASIS_DB_DIR` | `data` | Database directory |
| `OASIS_DB_PATH` | `data/oasis.db` | Database file path |
| `TELEGRAM_BOT_TOKEN` | — | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | — | Default Telegram chat ID |
| `WHATSAPP_PHONE_NUMBER_ID` | — | WhatsApp Business phone number ID |
| `WHATSAPP_ACCESS_TOKEN` | — | WhatsApp Business API access token |

## Desktop Application

To package OASIS-X as a standalone desktop app:

```bash
pip install pyinstaller pywebview
python desktop_app.py
```

This bundles the Python server + web frontend into a single `.exe` with an embedded webview window (no browser needed). Output is in `dist/OASIS-X/`.

## License

Proprietary — OASIS-X is developed for network operations use.

---

*Built for the challenging conditions of Nigerian optical fibre networks — from the harmattan dust of Kano to the monsoon rains of Port Harcourt.*
