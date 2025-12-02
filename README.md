## Smart City Incident Response Platform Demo

This repository contains a Flask-based demo for the HU hackathon assignment “Smart City Incident Response Platform.”

### Features
- Real-time style dashboard combining incident metrics, charts, and sensor health cards.
- Simulated sensor feed with AI-assisted risk scoring and automatic incident generation.
- Incident lifecycle management (open → acknowledged → resolved) with RESTful APIs.
- Minimal authentication layer with configurable credentials (`APP_USERNAME` / `APP_PASSWORD`).
- Unit tests covering authentication guard rails and the incident lifecycle API.

### Getting started
1. Install dependencies:
	```bash
	pip install -e .[dev]
	```
2. Run the Flask development server:
	```bash 
	python main.py
	```
3. Open the dashboard at `http://127.0.0.1:5000` and sign in with `incident-operator / secure-demo` (override via environment variables for production).

### API overview
- `GET /api/dashboard` — aggregated incidents, metrics, and sensor snapshots.
- `GET /api/incidents` — list incidents; `POST` to create a new incident.
- `PATCH /api/incidents/<id>` — advance the incident status.
- `GET /api/sensors` — pull latest sensor telemetry with AI scoring.
- `POST /api/simulate` — mutate telemetry and optionally create a new incident when thresholds are exceeded.

### Testing
Run the automated tests with:
```bash
pytest
```

### Configuration notes
- Set `APP_SECRET` to change the Flask secret key.
- Provide `APP_USERNAME` and `APP_PASSWORD` to customise the operator login.
- For GitHub OAuth login, configure `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, and optionally `GITHUB_REDIRECT_URI` (defaults to `http://127.0.0.1:5000/oauth/github/callback`).
- The AI module (`app/ai.py`) is rule-based for demo purposes; replace it with an ML pipeline when ready.
