# SWIFT FHS — Autonomous Fibre Fault Healing System

**Smart Waveform Integrated Fibre-opric Transmission — Fault Healing System**

A full-stack autonomous predictive fault healing system for Nigerian optical fibre networks. SWIFT FHS combines real-time telemetry simulation, ML-based anomaly detection, NCC QoS compliance monitoring, and optional LLM-powered fault diagnosis into a single interactive dashboard.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [API Reference](#api-reference)
- [LLM Integration](#llm-integration)
- [NCC Compliance Framework](#ncc-compliance-framework)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Development](#development)
- [License](#license)

---

## Overview

SWIFT FHS is designed for Nigerian optical fibre network operators who must maintain service quality under harsh environmental conditions — harmattan dust storms, tropical rain attenuation, generator failures, and peak-hour congestion across Lagos, Abuja, Port Harcourt, and Kano.

The system:

1. **Simulates** realistic fibre telemetry with season-aware environmental degradation
2. **Detects** anomalies via an Isolation Forest model with adaptive thresholding
3. **Classifies** faults and recommends corrective actions through a rule-based decision engine
4. **Evaluates** every telemetry sample against NCC (Nigerian Communications Commission) QoS baselines
5. **Diagnoses** faults using a custom Ollama LLM (`swift-fhs`) fine-tuned with Nigerian fibre domain knowledge
6. **Visualises** the entire pipeline in real time via a Chart.js dashboard

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌──────────────────┐
│  Telemetry   │────▶│   NCC Drift  │────▶│    Anomaly     │────▶│    Decision      │
│  Simulator   │     │   Injector   │     │   Detector     │     │    Engine        │
│  (seasonal   │     │  (city-      │     │  (Isolation    │     │  (rule-based     │
│   profiles)  │     │   specific)  │     │   Forest)      │     │   classifier)    │
└─────────────┘     └──────────────┘     └────────────────┘     └───────┬──────────┘
                                                                        │
                                                                        ▼
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│   FastAPI    │◀────│    LLM       │◀────│    Pipeline    │
│   Server     │     │   Diagnosis  │     │   Cache        │
│   :8080      │     │  (swift-fhs  │     │                │
│              │     │   via        │     │                │
│              │     │   Ollama)    │     │                │
└──────┬───────┘     └──────────────┘     └────────────────┘
       │
       ▼
┌──────────────┐
│   Dashboard  │
│  (Chart.js + │
│   HTML/CSS)  │
└──────────────┘
```

### Data Flow

1. **Generator** produces `n` telemetry rows with city-specific environmental factors (harmattan dust, rain attenuation, generator failure injection)
2. **NCC Drift** applies live QoS baseline drift based on NCC permissible margins per city
3. **Anomaly Detector** scores each row with an Isolation Forest, flags outliers, and computes rolling severity
4. **Decision Engine** maps state + fault cause → recommended action (reroute, monitor, adjust amplifier, dispatch crew)
5. **LLM Diagnosis** (optional) sends telemetry context to the `swift-fhs` Ollama model for natural-language fault analysis
6. **Dashboard** polls `/api/run` and `/api/diagnose/{idx}` to render KPIs, compliance bars, event charts, and diagnosis cards

---

## Features

### Network Awareness (Nigerian Context)
- **4 Cities** – Lagos, Abuja, Port Harcourt, Kano — each with distinct NCC QoS baselines
- **4 Seasons** – harmattan, rainy, dry, normal — with calibrated OSNR/BER/power degradation profiles
- **NCC Compliance** – per-city OSNR (≥15 dB), BER (≤1×10⁻⁵), power, latency, uptime thresholds
- **Environmental Factors** – dust attenuation (0–3 dB harmattan), rain fade (0–5 dB rainy), generator failure simulation

### Real-Time Pipeline
- Generate 50–1000 telemetry samples per run
- Automatic NCC drift injection
- ML anomaly detection with adaptive thresholding
- Rule-based classification and action recommendation
- Rolling risk scoring and state transitions (NORMAL → DEGRADING → CRITICAL)

### LLM-Powered Diagnosis
- Custom Ollama model `swift-fhs` with Nigerian fibre expertise
- Parses telemetry and returns structured diagnosis (root cause, suggestion, confidence, NCC compliance)
- Graceful fallback to rule engine when Ollama is unavailable

### Interactive Dashboard
- Real-time KPI cards (OSNR, BER, latency, NCC compliance %)
- Line charts for OSNR, BER, power over the last 15 samples
- State distribution pie / radar chart
- NCC compliance bar per city
- Event timeline with colour-coded severity
- Diagnosis panel with LLM or rule-engine output
- Fault event injection (one-click simulate fibre cut, generator failure, harmattan degradation, rain attenuation, peak congestion)

---

## Tech Stack

| Component | Technology |
|---|---|
| **Backend** | Python 3.13, FastAPI 0.135, Uvicorn 0.44 |
| **ML / Data** | scikit-learn (Isolation Forest), pandas, NumPy |
| **LLM Runtime** | Ollama (local) + custom `swift-fhs` model (Qwen2.5 0.5B base) |
| **Visualisation** | Chart.js 4.x (via CDN), CSS3 custom properties |
| **API Protocol** | REST (JSON) — single-page frontend fetches from FastAPI |
| **Development** | Jupyter notebooks, ipykernel |

---

## Quick Start

### Prerequisites

- Python 3.12+ (tested with 3.13)
- Ollama (for LLM diagnosis — optional, system works without it)
- Git

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd swift-fhs

# 2. Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Pull base model and create custom model
ollama serve
ollama pull qwen2.5:0.5b
ollama create swift-fhs -f models\.ollama\Modelfile

# 5. Start the API server
python -m uvicorn api.app:app --host 0.0.0.0 --port 8080 --reload

# 6. Open the dashboard
# http://localhost:8080
```

### Windows (Start Script)

```powershell
# Start server in background (persistent)
Start-Process -WindowStyle Hidden -FilePath "venv\Scripts\python.exe" `
  -ArgumentList "-m uvicorn api.app:app --host 0.0.0.0 --port 8080" `
  -WorkingDirectory "C:\path\to\swift-fhs"
```

---

## Usage

### Dashboard

Navigate to `http://localhost:8080`. The dashboard loads with:

- **Header** – system logo, title, real-time clock
- **KPI Cards** – average OSNR, BER, latency, NCC compliance percentage
- **Chart Row** – OSNR/BER line chart (last 15 samples)
- **State Distribution** – pie chart of NORMAL / DEGRADING / CRITICAL states
- **Event Timeline** – colour-coded fault events over the sample window
- **NCC Compliance Bar** – per-city compliance score with colour thresholds
- **Diagnosis Panel** – LLM or rule-engine analysis for the latest row
- **Simulate Events** – buttons to inject specific Nigerian fault scenarios

### API Endpoints

See [API Reference](#api-reference) below for full documentation.

### Simulation

```bash
# Trigger a fibre cut event in Lagos
curl "http://localhost:8080/api/simulate/event/fiber_cut?city=Lagos"

# Trigger harmattan degradation with custom row index
curl "http://localhost:8080/api/simulate/event/harmattan_degradation?row_index=50"
```

---

## API Reference

### `GET /api/status`

Health check.

```json
{
  "system": "running",
  "service": "SWIFT FHS",
  "version": "1.0.0",
  "supported_cities": ["Lagos", "Abuja", "PortHarcourt", "Kano"],
  "current_season": "rainy"
}
```

### `GET /api/run`

Run the full pipeline.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `city` | string | `Lagos` | One of: Lagos, Abuja, PortHarcourt, Kano |
| `season` | string | *auto* | One of: harmattan, rainy, dry, normal (auto-detected) |
| `apply_ncc_drift` | bool | `true` | Inject NCC-compliant drift into telemetry |
| `n` | int | `200` | Number of samples (50–1000) |

### `GET /api/diagnose/{row_index}`

LLM or rule-engine diagnosis for a specific row.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `row_index` | int | *(required)* | Row index (0–199 for 200-sample run) |
| `city` | string | `Lagos` | City context |
| `season` | string | *auto* | Season context |

### `GET /api/simulate/event/{event_type}`

Inject a specific fault event.

| Event | Description |
|---|---|
| `generator_failure` | Power infrastructure outage |
| `fiber_cut` | Physical cable cut |
| `harmattan_degradation` | Dust-driven OSNR attenuation |
| `rain_attenuation` | Heavy rain power drop |
| `peak_congestion` | Lagos evening usage peak |

### `GET /api/nigerian-context`

Return NCC baseline for a given city.

### `GET /api/nigerian-context/all-cities`

Return NCC baselines for all supported cities.

---

## LLM Integration

SWIFT FHS includes a custom Ollama model (`swift-fhs`) built on Qwen2.5 0.5B and fine-tuned via Modelfile with:

- Nigerian NCC QoS thresholds per city
- Fibre fault profiles (harmattan, rain, generator failure, fibre cut, congestion)
- Structured JSON output format for parsing by the API

### How It Works

```
Telemetry Row ──▶ _build_prompt() ──▶ Ollama API ──▶ JSON Response ──▶ Diagnosis
                       │                                         │
                       │                                         ▼
                       └── (fallback) ───▶ _rule_based_diagnosis()
```

The `root/llm_agent.py` module:
1. Probes Ollama availability once (cached for process lifetime)
2. If available & model `swift-fhs` is registered → sends prompt, parses JSON response
3. If Ollama is unreachable or times out → falls back to deterministic rule engine
4. Returns a unified dict with keys: `diagnosis`, `root_cause`, `suggestion`, `confidence`, `ncc_compliant`, `urgency`, `explanation`, `source` (`"llm"` or `"rule_engine"`)

### Custom Model Setup

```bash
ollama serve
ollama pull qwen2.5:0.5b           # Base model (~397 MB)
ollama create swift-fhs -f models\.ollama\Modelfile
# Verify: ollama list
```

The Modelfile includes:
- Full system prompt defining the assistant as a Nigerian fibre network expert
- NCC threshold values per city
- Example diagnosis messages
- Temperature (0.25) and context window (4096) settings

---

## NCC Compliance Framework

The Nigerian Communications Commission (NCC) sets QoS benchmarks for fibre networks. SWIFT FHS models these per city:

| Metric | NCC Minimum | Description |
|---|---|---|
| **OSNR** | ≥15 dB | Optical Signal-to-Noise Ratio |
| **BER** | ≤1×10⁻⁵ | Bit Error Rate |
| **Power** | ≥-15 dBm | Receive power |
| **Latency** | ≤100 ms | Round-trip time |
| **Uptime** | ≥99.5% | Service availability |

The `simulate_ncc_drift` function applies slight random perturbations within NCC margins to simulate realistic telemetry drift. The `evaluate_against_ncc` function returns a per-metric compliance report. The dashboard renders this as a colour-coded compliance bar (green ≥85%, amber 50–84%, red <50%).

---

## Project Structure

```
├── api/
│   ├── __init__.py
│   ├── app.py              # FastAPI application, CORS, static mount, routes
│   └── routes.py           # API endpoints: status, run, diagnose, simulate, nigerian-context
│
├── data/                   # Generated CSV datasets and logs
│
├── models/
│   ├── __init__.py
│   ├── anomaly_detector.py # Isolation Forest anomaly detection
│   ├── data_simulator.py   # Season/city-aware telemetry generator
│   ├── ncc_feed.py         # NCC baseline profiles, drift injection, compliance eval
│   └── .ollama/
│       └── Modelfile       # Ollama model definition for swift-fhs
│
├── notebooks/              # Jupyter notebooks for experimentation
│
├── root/
│   ├── __init__.py
│   ├── decision_engine.py  # State-to-action rule mapping
│   └── llm_agent.py        # LLM diagnosis with Ollama + rule engine fallback
│
├── static/
│   ├── index.html          # Dashboard HTML
│   ├── style.css           # Dark-theme CSS
│   ├── app.js              # Chart.js dashboard logic
│   ├── favicon.svg         # System favicon
│   └── swiftFiber.png      # Logo / favicon asset
│
├── venv/                   # Python virtual environment (git-ignored)
│
├── requirements.txt        # Python dependencies
├── README.md               # This file
└── start_server.py         # Convenience server launcher
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SWIFT_LLM_MODEL` | `swift-fhs` | Ollama model name for diagnosis |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_TIMEOUT` | `30` | LLM inference timeout in seconds |

### Modelfile (Customising the LLM)

Edit `models/.ollama/Modelfile` to:

- Update NCC thresholds per city
- Modify the system prompt or assistant persona
- Add/change example diagnosis messages
- Adjust inference parameters (temperature, context window)

After changes:

```bash
ollama create swift-fhs -f models\.ollama\Modelfile -f
```

---

## Development

### Running Tests

```bash
python -m pytest test.py -v
python -m pytest test_llm_agent.py -v
```

### Adding a New City

1. Add NCC baseline to `models/ncc_feed.py` → `NCC_CITY_PROFILES` dict
2. Add environmental profiles to `models/data_simulator.py`
3. The city will automatically appear in the dashboard city selector
4. Update NCC compliance bar colours if needed in `static/style.css`

### LLM Agent Testing

```bash
# Force re-check Ollama availability (useful in tests)
python -c "from root.llm_agent import reset_availability_cache; reset_availability_cache()"
```

---

## License

Proprietary — SWIFT FHS is developed for internal network operations use.

---

*Built for the challenging conditions of Nigerian optical fibre networks — from the harmattan dust of Kano to the monsoon rains of Port Harcourt.*
