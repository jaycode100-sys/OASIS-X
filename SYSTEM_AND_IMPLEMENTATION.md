# OASIS-X / SWIFT FHS — System & Implementation

> **SWIFT FHS** (Smart Waveform Integrated Fibre-optic Transmission — Fault Healing System) is an autonomous predictive fault healing system for Nigerian optical fibre networks. It monitors telemetry in real time, detects anomalies via ML, classifies network states, diagnoses faults (optionally via LLM), and recommends healing actions — all through an interactive dashboard.

---

## 1. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                        │
│          static/index.html + app.js + style.css + login.html     │
│          Chart.js dashboard · Chat UI · Fault injector           │
└──────────────────────────┬───────────────────────────────────────┘
                           │  HTTP (JSON) ──── Auth: JWT Bearer
┌──────────────────────────▼───────────────────────────────────────┐
│                       API LAYER (FastAPI)                         │
│  ┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐  │
│  │  api/auth.py  │   │  api/routes.py   │   │  api/schemas.py  │  │
│  │  JWT login    │   │  All endpoints   │   │  (empty)         │  │
│  │  Role check   │   │  Pipeline/chat   │   │                  │  │
│  └──────────────┘   └────────┬─────────┘   └──────────────────┘  │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                     PIPELINE LAYER (root/)                        │
│  ┌──────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │ decision_engine  │  │  llm_agent.py  │  │  chat_agent.py   │  │
│  │ State classify   │  │  LLM diagnosis │  │  Nexus chat      │  │
│  │ Action planning  │  │  Rule fallback │  │  Technical/simple│  │
│  └──────────────────┘  └────────────────┘  └──────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              digital_twin.py (NetworkX graph)            │    │
│  │           Fault injection + healing simulation            │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                      MODELS LAYER (models/)                       │
│  ┌──────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │ data_simulator   │  │ anomaly_detector│  │  ncc_feed.py     │  │
│  │ Telemetry gen    │  │ IsolationForest │  │ NCC baselines    │  │
│  │ Fault injection  │  │ Feature eng.    │  │ Drift + QoS eval │  │
│  └──────────────────┘  └────────────────┘  └──────────────────┘  │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                     DATA LAYER (data/)                            │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  database.py · SQLite (oasis.db)                         │    │
│  │  Tables: pipeline_runs, telemetry_rows, diagnosis_logs,  │    │
│  │          chat_messages, users                            │    │
│  └──────────────────────────────────────────────────────────┘    │
│  data/raw_fibre_logs.csv (generated telemetry snapshots)         │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow (single pipeline pass)

```
generate_network_data()
  │  Simulates n telemetry rows with city-specific baselines,
  │  time-of-day congestion, seasonal effects (harmattan/rain),
  │  gradual fibre aging, sudden fibre cut, optional generator failure.
  ▼
simulate_ncc_drift()
  │  Applies sinusoidal OSNR drift, latency congestion variance,
  │  BER micro-fluctuations based on NCC city profile.
  ▼
detect_anomalies()
  │  Feature engineering (osnr_drop, ber_rise, rolling trends)
  │  → IsolationForest (contamination=0.12) → anomaly_flag
  ▼
process_decisions()
  │  Vectorized risk_score calculation
  │  → State classification (NORMAL / DEGRADING / CRITICAL)
  │  → Recommended action (NO_ACTION / ADJUST_AMPLIFIER / REROUTE)
  ▼
get_llm_diagnosis()  (optional — falls back to rule engine)
  │  Ollama swift-fhs model → JSON diagnosis
  │  OR _rule_based_diagnosis() deterministic fallback
  ▼
Return to API → JSON response → Dashboard renders charts/table
```

---

## 2. Directory Structure

```
implementation/
├── api/
│   ├── __init__.py              # Package marker
│   ├── app.py                   # FastAPI app creation, CORS, static mount, startup
│   ├── auth.py                  # JWT auth: login, register, user mgmt, dependencies
│   ├── routes.py                # All API endpoints (pipeline, NCC, chat, logs)
│   └── schemas.py               # (empty — schemas defined inline in auth.py)
├── data/
│   ├── __init__.py              # Package marker
│   ├── database.py              # SQLite CRUD: pipeline_runs, users, etc.
│   ├── oasis.db                 # SQLite database (auto-created)
│   └── raw_fibre_logs.csv       # Generated telemetry snapshots
├── models/
│   ├── __init__.py              # Package marker
│   ├── .ollama/
│   │   ├── Modelfile            # swift-fhs Ollama model definition
│   │   └── ChatModelfile        # nexus-chat Ollama model definition
│   ├── anomaly_detector.py      # IsolationForest anomaly detection
│   ├── data_simulator.py        # Nigerian telemetry data generator
│   └── ncc_feed.py              # NCC baseline profiles + drift + compliance
├── root/
│   ├── __init__.py              # Package marker
│   ├── chat_agent.py            # Nexus conversational chat via Ollama
│   ├── decision_engine.py       # State classification + action planning
│   ├── digital_twin.py          # NetworkX fibre network digital twin
│   └── llm_agent.py             # LLM diagnosis engine + rule fallback
├── static/
│   ├── favicon.svg              # OASIS-X icon
│   ├── app.js                   # Frontend logic (auth, charts, chat, CRUD)
│   ├── index.html               # Dashboard HTML
│   ├── login.html               # Standalone login page
│   ├── nexus.jpg                # Nexus chat avatar
│   ├── oasis.png                # OASIS-X logo
│   └── style.css                # Dashboard styling (dark theme)
├── logs/                        # Simulation history export (auto-created)
├── notebooks/
│   ├── data_exploration.ipynb   # EDA notebook
│   └── model_testing.ipynb      # Model testing notebook
├── venv/                        # Python virtual environment
├── .vscode/
│   └── settings.json            # Python analysis extraPaths
├── main.py                      # CLI entry: runs OpticalHealingSimulator
├── simulator.py                 # OpticalHealingSimulator class
├── start_server.py              # Convenience server launcher (port 8080)
├── test.py                      # Quick smoke test
├── test_llm_agent.py            # LLM agent test
├── requirements.txt             # Python dependencies
├── IMPLEMENTATION.txt           # Original architecture notes
├── README.md                    # Project README
└── commands.txt                 # Development commands
```

---

## 3. Module Reference

### 3.1 `api/app.py` — Application Entry Point

| Item | Value |
|---|---|
| Framework | FastAPI |
| Title | OASIS-X |
| Version | 1.0.0 |
| Port (dev) | 8000 |
| Port (start_server.py) | 8080 |
| CORS | Allow all origins |

**Startup sequence:**
1. `init_db()` → create SQLite tables
2. `seed_default_users()` → create admin/user accounts
3. Mount `/static` → serve dashboard files
4. Include auth router at `/api`
5. Include pipeline router at `/api`

**Serves:**
- `GET /` → dashboard (`index.html`)
- `GET /login` → login page (`login.html`)
- `GET /docs` → Swagger UI (FastAPI auto)

### 3.2 `api/auth.py` — JWT Authentication

| Component | Detail |
|---|---|
| Algorithm | HS256 |
| Token expiry | 8 hours (480 min) |
| Password hash | bcrypt via passlib |
| Secret key | `OASIS_SECRET_KEY` env var (dev fallback) |

**Endpoints:**

| Method | Path | Auth | Role |
|---|---|---|---|
| POST | `/api/auth/login` | Public | — |
| GET | `/api/auth/me` | Bearer token | Any |
| POST | `/api/auth/register` | Bearer token | superadmin |
| GET | `/api/auth/users` | Bearer token | superadmin |
| DELETE | `/api/auth/users/{id}` | Bearer token | superadmin |

**Dependencies:**
- `get_current_user()` — Extracts user from `Authorization: Bearer <token>`
- `require_role(role)` — Returns a dependency that checks user role

**Default seeded users:**

| Username | Password | Role |
|---|---|---|
| admin | admin123 | superadmin |
| user | user123 | user |

### 3.3 `api/routes.py` — API Endpoints

**Pipeline:**
- `GET /api/status` — System health + current season + supported cities (no auth)
- `GET /api/llm-status` — Ollama availability (no auth)
- `GET /api/run` — Full pipeline: generate → drift → detect → decide. Params: `city`, `season`, `apply_ncc_drift`, `n`
- `GET /api/diagnose/{row_index}` — Row-level diagnosis
- `GET /api/simulate/event/{event_type}` — Fault injection (5 types)

**NCC:**
- `GET /api/nigerian-context` — NCC baseline per city
- `GET /api/nigerian-context/all-cities` — All city profiles

**Logs:**
- `POST /api/logs` — Save pipeline run
- `GET /api/logs` — List runs
- `GET /api/logs/{run_id}` — Get run detail
- `DELETE /api/logs/{run_id}` — Delete run

**Chat:**
- `POST /api/chat` — Send message to Nexus
- `GET /api/chat/history` — Get chat history
- `DELETE /api/chat/history` — Clear history

### 3.4 `data/database.py` — SQLite Layer

| Property | Value |
|---|---|
| Database | data/oasis.db |
| Journal mode | WAL |
| Thread safety | Per-thread connections via `threading.local()` |
| Foreign keys | ON |

**Tables:**

| Table | Key Columns | Purpose |
|---|---|---|
| `pipeline_runs` | id, city, season, n_samples, summary_json | Pipeline execution metadata |
| `telemetry_rows` | id, run_id, row_index, row_data_json | Per-row telemetry (JSON blob) |
| `diagnosis_logs` | id, run_id, row_index, diagnosis_json | Diagnosis records |
| `chat_messages` | id, role, content | Chat history |
| `users` | id, username, hashed_password, role | Authentication |

### 3.5 `models/data_simulator.py` — Telemetry Generator

Generates `n` rows of realistic Nigerian optical fibre telemetry.

**Parameters:**
- `n` — Number of samples (default: 200)
- `seed` — Random seed for reproducibility
- `season` — `harmattan` | `rainy` | `dry` | `normal`
- `city` — `Lagos` | `Abuja` | `PortHarcourt` | `Kano`
- `inject_generator_failure` — Boolean (default: True)

**Output columns:** `time`, `hour_of_day`, `osnr_db`, `ber`, `power_dbm`, `latency_ms`, `event`, `fault_cause`, `environmental_factor`, `season`, `city`

**Fault injection schedule:**
| Step | Event | Details |
|---|---|---|
| 75 | GENERATOR_FAILURE | 18-step: 3 step collapse → dark phase → 5 step recovery |
| 120 | FIBRE_AGING (gradual) | Linear OSNR degradation, BER/power drift |
| 165 | FIBER_CUT (sudden) | OSNR clamped to ≤8 dB, BER ×50, power = -25 dBm |

**Seasonal effects:**
- **Harmattan** (Nov–Feb): Up to -2 dB OSNR loss from dust
- **Rainy** (Apr–Oct): 15%/step chance of 2.5–6 dB power drop + 3-8× BER spike

### 3.6 `models/anomaly_detector.py` — ML Anomaly Detection

| Property | Value |
|---|---|
| Algorithm | IsolationForest (sklearn) |
| Contamination | 0.12 |
| Features | osnr_db, ber, power_dbm, latency_ms, osnr_drop, ber_rise, osnr_trend, ber_trend |
| Model persistence | `models/anomaly_model.pkl` via joblib |

**Behaviour:**
- On first run: trains a new model, saves to disk
- On subsequent runs: loads saved model (unless `retrain=True`)
- Adds columns: `anomaly_score` (-1 or 1), `anomaly_flag` (1 if anomaly)

### 3.7 `models/ncc_feed.py` — NCC Compliance Framework

**NCC QoS thresholds:**
| Metric | Min | Target |
|---|---|---|
| OSNR | 15 dB | 20 dB |
| BER | — | 1e-7 max: 1e-5 |
| Latency | — | 25 ms max: 150 ms |
| Availability | 99% | 99.9% |

**City profiles** (Lagos, Abuja, PortHarcourt, Kano) include:
- Per-city OSNR/latency/BER/power baselines
- Peak hour patterns and latency multipliers
- Generator failure risk probabilities

**`simulate_ncc_drift()`** applies sinusoidal OSNR drift, latency congestion variance, and BER micro-fluctuations.

**`evaluate_against_ncc()`** returns per-metric compliance percentages + overall COMPLIANT/NON_COMPLIANT status.

### 3.8 `root/decision_engine.py` — State Classification & Action Planning

**Constants:**
| Parameter | Value | Meaning |
|---|---|---|
| BASELINE_OSNR_DB | 22.0 | Expected healthy OSNR |
| CRITICAL_OSNR_DB | 15.0 | Below → CRITICAL |
| DEGRADING_OSNR_DB | 19.0 | Below → DEGRADING |
| CRITICAL_BER | 1e-5 | Above → CRITICAL |
| SAFE_RISK_SCORE | 0.3 | Auto-approve threshold |

**State → Action mapping:**
| State | Action |
|---|---|
| CRITICAL | `IMMEDIATE_REROUTE_TO_PROTECTION_PATH` |
| DEGRADING | `ADJUST_AMPLIFIER_GAIN_AND_MONITOR` |
| NORMAL | `NO_ACTION` |

**Risk score formula:** `latency_ms × (BASELINE_OSNR_DB - osnr_db)` (clipped ≥ 0)

**`validate_and_execute()`** — safety validation layer that checks simulation feedback before committing.

### 3.9 `root/llm_agent.py` — LLM Diagnosis Engine

| Property | Value |
|---|---|
| Model | `swift-fhs` (default) / `SWIFT_LLM_MODEL` env var |
| Base URL | `http://localhost:11434` / `OLLAMA_BASE_URL` env var |
| Timeout | 120s / `OLLAMA_TIMEOUT` env var |
| Fallback | Deterministic rule engine (no external deps) |

**Flow:**
1. `get_llm_diagnosis(data)` called
2. `_check_ollama()` probes Ollama API (cached per process)
3. If available → `_build_prompt()` → `_call_ollama()` → parse JSON
4. If unavailable → `_rule_based_diagnosis()` deterministic fallback
5. Returns unified dict: `diagnosis`, `root_cause`, `suggestion`, `confidence`, `ncc_compliant`, `urgency`, `explanation`, `source`

**Ollama model setup:**
```
ollama create swift-fhs -f models/.ollama/Modelfile
```
Base model: `llama3.2:1b` (temperature=0.2, context=1024, top_p=0.85)

### 3.10 `root/chat_agent.py` — Nexus Chat

| Property | Value |
|---|---|
| Model | `nexus-chat` |
| Base model | `llama3.2:1b` |
| Temperature | 0.3 |
| Context window | 4096 |

**Modes:**
- `technical` — Uses precise metrics, NCC thresholds, dB values
- `simple` — Plain language, analogies for non-technical users

**Context injection:** Automatically includes latest pipeline summary, diagnosis, and NCC compliance data when available.

**Ollama model setup:**
```
ollama create nexus-chat -f models/.ollama/ChatModelfile
```

### 3.11 `root/digital_twin.py` — Fibre Network Digital Twin

| Property | Value |
|---|---|
| Library | NetworkX (Graph) |
| Topology | Linear chain, 15 spans (default) |
| Healthy OSNR | 22.0 dB |
| After reroute | 20.5 dB |
| Amplifier boost | +3.0 dB |

**Methods:**
- `inject_fault(span_id, fault_type)` — Sets span OSNR to 7.0 (cut) or 14.0 (degradation)
- `apply_healing(action, span_id)` — Full reroute (healed) or amplifier adjustment (recovering)
- `get_state()` / `get_span_status()` — State inspection

### 3.12 `simulator.py` — CLI Simulation Loop

```python
simulator = OpticalHealingSimulator(cycles=30, delay=0.8, city="Lagos", season=None)
simulator.run()
```

Per cycle: inject fault into digital twin → apply healing action → log state → LLM diagnosis. Exports to `logs/simulation_history.csv`.

### 3.13 Frontend — Dashboard (`static/`)

- **`index.html`** (401 lines) — Full SPA dashboard
- **`app.js`** (707 lines) — All frontend logic
- **`style.css`** (523 lines) — Dark theme CSS
- **`login.html`** (121 lines) — Standalone login page

**Key features:**
- JWT auth with localStorage token management
- Live KPI metrics (OSNR, BER, latency, anomalies)
- Chart.js doughnut (state distribution) + line chart (OSNR trend)
- NCC compliance bars with color thresholds
- Fault event simulator (5 one-click buttons)
- Row-level diagnosis panel with source/urgency/NCC badges
- Telemetry data table with CSV export
- Pipeline run history with delete
- **Superadmin-only user management** (add/list/delete users)
- Nexus chat panel (technical/simple mode toggle)
- Auto-refresh (30s), clock (Lagos time UTC+1)

---

## 4. Setup & Installation

### Prerequisites
- Python 3.13+
- Ollama (optional — for LLM features)

### Steps

```bash
# 1. Clone / enter project
cd implementation

# 2. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate     # Windows
# source venv/bin/activate  # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Set up Ollama models
ollama create swift-fhs -f models/.ollama/Modelfile
ollama create nexus-chat -f models/.ollama/ChatModelfile

# 5. Run the API server
uvicorn api.app:app --port 8000 --reload

# 6. Open http://localhost:8000/login
#    Login: admin / admin123 (superadmin)
#           user  / user123  (user)
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OASIS_SECRET_KEY` | `oasis-x-dev-secret-key-...` | JWT signing secret |
| `SWIFT_LLM_MODEL` | `swift-fhs` | Ollama diagnosis model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_TIMEOUT` | `120` | Ollama request timeout (s) |

---

## 5. Testing

```bash
# CLI simulator
python main.py

# Quick smoke test
python test.py

# LLM agent test (no Ollama needed — tests rule fallback)
python test_llm_agent.py

# Start server
python start_server.py          # port 8080
# or
uvicorn api.app:app --port 8000 # port 8000
```

---

## 6. API Authentication Summary

```
                    UNPROTECTED (public)
                    ├── GET  /api/status
                    ├── GET  /api/llm-status
                    ├── POST /api/auth/login
                    └── /login, /, /static/*, /docs

                    PROTECTED (any authenticated user)
                    ├── GET  /api/auth/me
                    ├── GET  /api/run
                    ├── GET  /api/diagnose/{id}
                    ├── GET  /api/simulate/event/{type}
                    ├── GET  /api/nigerian-context
                    ├── GET/POST/DELETE /api/logs
                    └── POST/GET/DELETE /api/chat/*

                    SUPERADMIN ONLY
                    ├── POST /api/auth/register
                    ├── GET  /api/auth/users
                    └── DELETE /api/auth/users/{id}
```

---

## 7. Dependencies

| Package | Purpose |
|---|---|
| `fastapi` | REST API framework |
| `uvicorn[standard]` | ASGI server |
| `numpy`, `pandas` | Numerical computing, data manipulation |
| `scikit-learn` | IsolationForest anomaly detection |
| `joblib` | Model serialization |
| `networkx` | Digital twin graph representation |
| `requests` | Ollama HTTP client |
| `python-jose[cryptography]` | JWT creation & validation |
| `passlib[bcrypt]` | Password hashing |
| `python-multipart` | OAuth2 form parsing |
| `matplotlib` | Notebook charting |
| `ipykernel` | Jupyter kernel |

---

## 8. File Index (Line Counts)

| File | Lines | Role |
|---|---|---|
| `api/auth.py` | 173 | JWT auth, login/register, dependencies |
| `api/routes.py` | 321 | All API endpoints |
| `api/app.py` | 67 | FastAPI app assembly |
| `data/database.py` | 174 | SQLite CRUD |
| `models/data_simulator.py` | 245 | Telemetry generation |
| `models/anomaly_detector.py` | 49 | ML anomaly detection |
| `models/ncc_feed.py` | 207 | NCC compliance framework |
| `root/decision_engine.py` | 113 | State classification + actions |
| `root/llm_agent.py` | 288 | LLM diagnosis + rule fallback |
| `root/chat_agent.py` | 62 | Nexus chat agent |
| `root/digital_twin.py` | 99 | Fibre network digital twin |
| `simulator.py` | 106 | CLI simulation loop |
| `static/index.html` | 401 | Dashboard HTML |
| `static/app.js` | 707 | Dashboard frontend logic |
| `static/style.css` | 523 | Dashboard styles |
| `static/login.html` | 121 | Login page |
| **Total** | **~3,656** | |
