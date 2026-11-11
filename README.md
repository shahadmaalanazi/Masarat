# MASARAT | مسارات

**MASARAT** is a bilingual multi-agent demo that coordinates a football fan's trip: match details, transport, accommodation, and a budget-aware plan.

**Live demo:** https://shahadmaalanazi.github.io/Masarat/

> This is a prototype. Travel and accommodation prices are simulated and no booking is made.

## What the demo shows

Five agents collaborate through the coordinator:

- **Fan Agent** captures the request and preferences.
- **Coordinator Agent** sends requests, compares offers, and assembles the plan.
- **Venue Agent** provides match and ticket information from the included schedule.
- **Travel Agent** returns transport options.
- **Accommodation Agent** returns stay options.

The interface displays the agent execution timeline, FIPA-ACL message log, available options, and the selected plan. The match schedule is historical project data; travel, stay, and some ticket prices are simulated.

## Run locally

Requirements: Python 3.11 or newer. Install the dependencies and start the demo API:

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run_demo.py
```

Open http://localhost:8765. The web page calls the local API when served by the demo server. For the hosted static page, `site/config.js` points to the deployed Render API.

## Deploy

### GitHub Pages

The GitHub Actions workflow publishes the contents of `site/` on pushes to `main`. In the repository settings, enable Pages and select **GitHub Actions** as the publishing source.

### Render API

`render.yaml` defines the Python web service and its health check. Set `GOOGLE_API_KEY` in the Render service's environment settings if the configured Gemini-backed agent path needs it. Keep API keys in the hosting provider's secret environment settings; never commit them to GitHub or put them in frontend files. `site/config.js` contains only the public API base URL, not a secret.

For deployment configuration details, see [DEPLOY.md](DEPLOY.md).

## Repository layout

- `site/` — GitHub Pages frontend and static assets
- `demo.html` — local demo page
- `*_agent.py` — specialized agents and coordination logic
- `web_demo_server.py` — HTTP API for the demo
- `venue_data.py`, `real_data.py`, and inventory modules — schedule and demo option data
- `.github/workflows/pages.yml` — Pages deployment workflow

## Security

`.gitignore` excludes `.env`, virtual environments, and local generated files. Store credentials as environment variables in Render. If a key was ever committed, revoke and rotate it; deleting it in a later commit does not remove it from Git history.
