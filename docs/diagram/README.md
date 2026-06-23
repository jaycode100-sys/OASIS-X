<div align="center">

<img src="https://img.shields.io/badge/OASIS--X-SWIFT%20FHS-0f172a?style=for-the-badge&labelColor=1d4ed8" height="36"/>

# OASIS-X / SWIFT FHS

### Smart Waveform Integrated Fibre-optic Transmission Fault Healing System

*An autonomous, AI-powered system for predictive fault detection and self-healing in Nigerian optical fibre networks*

<br/>

[![Python](https://img.shields.io/badge/Python-3.13-3b82f6?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-10b981?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-IsolationForest-f59e0b?style=flat-square&logo=scikitlearn&logoColor=white)](https://scikit-learn.org)
[![JWT](https://img.shields.io/badge/Auth-JWT%20HS256-8b5cf6?style=flat-square&logo=jsonwebtokens&logoColor=white)](https://jwt.io)
[![SQLite](https://img.shields.io/badge/Database-SQLite-ef4444?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Render](https://img.shields.io/badge/Deployed%20on-Render-46e3b7?style=flat-square&logo=render&logoColor=white)](https://render.com)

<br/>

> **[🚀 Live Demo](#)** &nbsp;|&nbsp; **[📄 Technical Supplement](docs/OASIS-X_Technical_Supplement.pdf)** &nbsp;|&nbsp; **[📐 Diagrams](#-system-diagrams)**

</div>

---

## 📌 Overview

OASIS-X is a full-stack intelligent monitoring and self-healing platform built for optical fibre network infrastructure in Nigerian cities (Lagos, Abuja, Kano, Port Harcourt). It simulates real-time telemetry, detects anomalies using machine learning, reasons about faults using a locally-hosted LLM, and recommends healing actions — all presented through an interactive web dashboard.

The system is designed around the **NCC (Nigerian Communications Commission)** QoS thresholds for OSNR, BER, latency, and packet loss, making it directly applicable to real-world Nigerian ISP and telco infrastructure.

---

## ✨ Key Features

- **Real-time Telemetry Simulation** — Generates optical network data (OSNR, BER, latency, packet loss, chromatic dispersion) with seasonal effects, city-specific profiles, and injectable fault events
- **ML Anomaly Detection** — IsolationForest model (contamination = 0.12) trained on network state, classifying spans as `NORMAL`, `DEGRADING`, or `CRITICAL`
- **NCC Compliance Engine** — Evaluates every pipeline run against Nigerian Communications Commission QoS thresholds; generates compliance scores per city
- **LLM-Powered Diagnosis** — Uses a locally fine-tuned `swift-fhs` Ollama model to reason about root causes and suggest remediation; automatically falls back to a deterministic rule engine when unavailable
- **Digital Twin** — NetworkX-based lightweight fibre graph that simulates fault injection and healing actions before execution
- **Nexus Chat Agent** — Conversational AI interface for querying system state, diagnosis history, and NCC context in natural language
- **Secure REST API** — FastAPI with JWT Bearer authentication (HS256), role-based access (User / Superadmin), and full Swagger UI at `/docs`
- **Interactive Dashboard** — Chart.js visualisations, live KPI cards, data table with per-row fault diagnosis, run history, and CSV export

---

## 🏗 System Architecture

<div align="center">
  <img src="docs/diagrams/oasis_1_architecture.png" alt="OASIS-X System Architecture" width="90%"/>
  <br/>
  <sub><b>Figure 1</b> — Five-layer architecture: Presentation → API → Pipeline → Models → Data</sub>
</div>

<br/>

The system is structured into five distinct layers:

| Layer | Components | Responsibility |
|---|---|---|
| **Presentation** | `index.html`, `app.js`, `login.html`, Chart.js | Dashboard, charts, chat UI, login |
| **API** | `api/app.py`, `api/auth.py`, `api/routes.py` | REST endpoints, JWT auth, CORS |
| **Pipeline** | `decision_engine`, `llm_agent`, `chat_agent`, `digital_twin` | Core reasoning and action logic |
| **Models** | `data_simulator`, `anomaly_detector`, `ncc_feed` | Data generation, ML, NCC compliance |
| **Data** | `database.py`, `oasis.db` | SQLite persistence for all system state |

---

## 🗂 Project Structure

```
OASIS-X/
├── api/
│   ├── app.py              # FastAPI app factory + startup
│   ├── auth.py             # JWT auth, user management endpoints
│   └── routes.py           # All pipeline, diagnosis & chat endpoints
├── root/
│   ├── decision_engine.py  # State classification + action planning
│   ├── llm_agent.py        # swift-fhs LLM + rule-based fallback
│   ├── chat_agent.py       # Nexus conversational AI
│   └── digital_twin.py     # NetworkX fibre graph simulation
├── models/
│   ├── data_simulator.py   # Nigerian telemetry generation
│   ├── anomaly_detector.py # IsolationForest anomaly detection
│   └── ncc_feed.py         # NCC QoS compliance engine
├── data/
│   └── database.py         # SQLite CRUD (pipeline runs, chat, users)
├── static/                 # Frontend (HTML, CSS, JS)
├── main.py                 # CLI entry point
├── simulator.py            # OpticalHealingSimulator class
└── requirements.txt
```

---

## 📐 System Diagrams

### Class Diagram

<div align="center">
  <img src="docs/diagrams/oasis_2_class_diagram.png" alt="UML Class Diagram" width="95%"/>
  <br/>
  <sub><b>Figure 2</b> — UML Class Diagram showing all 12 core classes and their dependency relationships</sub>
</div>

<br/>

### Sequence Diagram — Run Pipeline

<div align="center">
  <img src="docs/diagrams/oasis_3_sequence_diagram.png" alt="Sequence Diagram" width="90%"/>
  <br/>
  <sub><b>Figure 3</b> — Sequence diagram for a full pipeline execution from browser request to JSON response</sub>
</div>

<br/>

### Use Case Diagram

<div align="center">
  <img src="docs/diagrams/oasis_4_usecase_diagram.png" alt="Use Case Diagram" width="80%"/>
  <br/>
  <sub><b>Figure 4</b> — Use cases for Network Engineer, Superadmin, and System Scheduler actors</sub>
</div>

<br/>

### Module Dependency Diagram

<div align="center">
  <img src="docs/diagrams/oasis_5_module_dependency.png" alt="Module Dependency" width="85%"/>
  <br/>
  <sub><b>Figure 5</b> — Import graph showing how all modules depend on each other across layers</sub>
</div>

---

## 🛠 Tech Stack

| Category | Technology |
|---|---|
| **Backend** | Python 3.13, FastAPI, Uvicorn |
| **Machine Learning** | scikit-learn (IsolationForest), pandas, numpy |
| **Graph / Twin** | NetworkX |
| **LLM** | Ollama (`swift-fhs` model), rule-based fallback |
| **Authentication** | JWT HS256 via `python-jose`, `passlib` bcrypt |
| **Database** | SQLite (via standard `sqlite3`) |
| **Frontend** | Vanilla JS, Chart.js, HTML5, CSS3 |
| **Deployment** | Render (auto-deploy on push) |

---

## ⚡ Quick Start

### Prerequisites
- Python 3.13+
- (Optional) [Ollama](https://ollama.ai) with `swift-fhs` model for LLM diagnosis

### 1. Clone & install

```bash
git clone https://github.com/jaycode100-sys/OASIS-X.git
cd OASIS-X
pip install -r requirements.txt
```

### 2. Set environment variables

```bash
# Required
export OASIS_SECRET_KEY="your-secret-key-here"   # generate: python -c "import secrets; print(secrets.token_hex(32))"

# Optional (LLM — falls back to rule engine if Ollama not available)
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_TIMEOUT=120
```

### 3. Run

```bash
# Start the web server
uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload

# OR run the CLI simulation loop
python main.py
```

Open **http://localhost:8000** — login with `admin / admin123` (change on first use).

---

## 🌐 API Endpoints

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/token` | Login, returns JWT | ❌ |
| `GET` | `/api/status` | System health check | ✅ |
| `GET` | `/api/run` | Run full pipeline | ✅ |
| `POST` | `/api/diagnose` | Diagnose a specific fault row | ✅ |
| `POST` | `/api/simulate-event` | Inject a fault event | ✅ |
| `GET` | `/api/ncc-context` | NCC compliance context for a city | ✅ |
| `GET` | `/api/logs` | Pipeline run history | ✅ |
| `POST` | `/api/chat` | Chat with Nexus AI | ✅ |
| `GET` | `/users/me` | Current user info | ✅ |
| `POST` | `/users/register` | Register new user | ✅ Admin |

Full interactive API docs available at `/docs` (Swagger UI) when running.

---

## 🔐 Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OASIS_SECRET_KEY` | ✅ | — | JWT signing secret. Use `secrets.token_hex(32)` to generate. |
| `OLLAMA_BASE_URL` | ❌ | `http://localhost:11434` | Ollama server URL for LLM diagnosis |
| `SWIFT_LLM_MODEL` | ❌ | `swift-fhs` | Ollama model name |
| `OLLAMA_TIMEOUT` | ❌ | `120` | Seconds before falling back to rule engine |

---

## 🇳🇬 Nigerian Context

OASIS-X is purpose-built for Nigerian network conditions:

- **City profiles** for Lagos, Abuja, Kano, Port Harcourt, and Ibadan with unique baseline OSNR, interference, and seasonal degradation patterns
- **NCC QoS thresholds** enforced: OSNR ≥ 15 dB, BER ≤ 10⁻⁵, Latency ≤ 150 ms, Packet Loss ≤ 1%
- **Seasonal simulation** of harmattan dust, rainy season humidity, and heat effects on fibre attenuation
- **Generator failure injection** modelling power instability common to Nigerian infrastructure

---

## 📄 Documentation

The full technical architecture supplement (including all UML diagrams) is available in [`docs/OASIS-X_Technical_Supplement.pdf`](docs/OASIS-X_Technical_Supplement.pdf).

---

<div align="center">
  <sub>Built for Final Year Project Defence · Computer Engineering · 2025</sub>
</div>
