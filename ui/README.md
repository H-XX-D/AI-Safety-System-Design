# UI Dashboard - Feature Documentation

## Overview

The Web Monitoring Dashboard provides real-time visualization and control for the AI Safety System. It includes four major feature areas:

1. **Evidence Engine** - Search system documentation with citations
2. **Decision Trajectories** - Visualize agent decision paths and state transitions
3. **Training Metrics** - Monitor self-play training progress and adversarial bypasses
4. **Workflow Orchestration** - Track multi-agent collaboration across proposal lifecycle stages

## Features

### Evidence Engine

Search system documentation (`docs/`, `assessments/`, `README.md`) for evidence supporting or contradicting claims.

- **Endpoint**: `POST /api/evidence/search` - General search
- **Endpoint**: `POST /api/evidence/claim` - Evidence for specific claims
- **Page**: `/evidence` (Evidence Search)

**Configuration**:
- Set `EVIDENCE_ENGINE_ENABLED=false` to disable
- Requires `paper-qa` package (optional dependency)

### Decision Trajectories

Track agent decision-making processes through proposal lifecycle.

- **Endpoints**:
  - `GET /api/trajectories` - List trajectories
  - `GET /api/trajectories/<id>` - Get trajectory detail
  - `POST /api/trajectories` - Create trajectory
  - `POST /api/trajectories/<id>/step` - Add step
- **Page**: `/trajectories` (Decision Trajectories)

Trajectories are automatically created when orchestrator processes proposals.

### Training Metrics

Monitor self-play training progress and adversarial training effectiveness.

- **Endpoints**:
  - `GET /api/training/metrics` - Get metrics
  - `GET /api/training/games` - Get game history
  - `POST /api/training/games` - Record game
- **Page**: `/training` (Training Metrics)

Games are recorded when research agents complete self-play episodes.

### Workflow Orchestration

Visualize multi-agent collaboration across proposal stages.

- **Endpoints**:
  - `GET /api/workflows` - List workflows
  - `GET /api/workflows/<id>` - Get workflow detail
  - `POST /api/workflows` - Create workflow
  - `POST /api/workflows/<id>/stage` - Update stage
- **Page**: `/workflows` (Workflow Orchestration)

Workflows map proposal lifecycle: hypothesis → assay → analysis → candidates → validation

## Data Persistence

All UI data is persisted in SQLite database (`ui/ui_data.db`):

- `trajectories` - Decision trajectory records
- `trajectory_steps` - Individual trajectory steps
- `workflows` - Workflow orchestration records
- `workflow_stages` - Stage progression tracking
- `workflow_artifacts` - Generated artifacts
- `training_games` - Self-play game records

## Real-Time Updates

Pages subscribe to Socket.IO events for live updates:

- `evidence:index` - Evidence engine indexing status
- `trajectories:update` - Trajectory changes
- `training:update` - Training game updates
- `workflows:update` - Workflow stage changes

## Security

- All POST endpoints require `X-Requested-With: XMLHttpRequest` header (anti-CSRF)
- Admin routes require bearer token authentication
- Content Security Policy (CSP) enforced
- HSTS enabled in production mode

## Running the UI

### Development

```bash
cd ui
python app.py
```

Access at `http://localhost:5001`

### Production

```bash
cd ui
gunicorn -w 4 -b 0.0.0.0:5001 --worker-class eventlet -m app:app
```

Or with systemd:

```ini
[Unit]
Description=AI Safety System UI
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/AI-Safety-System-Design/ui
ExecStart=/usr/bin/gunicorn -w 4 -b 127.0.0.1:5001 --worker-class eventlet -m app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

## Configuration

Set environment variables:

- `STANDALONE=true` - Run without backend components (default)
- `EVIDENCE_ENGINE_ENABLED=true` - Enable evidence engine (default)
- `UI_API_BASE=http://localhost:5001` - UI API base URL (for integration)
- `UI_FEATURES_ENABLED=true` - Enable UI feature integration (default)
- `SECRET_KEY` - Flask secret key (required in production)

## Integration

The UI integrates with orchestrator and research systems via `ui_integration.py`:

- Orchestrator hooks emit trajectory and workflow events
- Research system hooks record training games and gather evidence
- All hooks are optional and fail gracefully if UI is unavailable

## Testing

Run UI tests:

```bash
pytest tests/ui/test_ui_features.py -v
```

## Troubleshooting

- **Database locked**: Ensure only one process accesses `ui_data.db` at a time
- **Evidence Engine unavailable**: Install `paper-qa` package or disable via `EVIDENCE_ENGINE_ENABLED=false`
- **Socket.IO not working**: Check CORS settings in config
- **Import errors**: Ensure all dependencies are installed (`pip install -r requirements.txt`)
