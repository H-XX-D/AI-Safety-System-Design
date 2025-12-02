# UI Dashboard - Feature Documentation

## Overview

The Web Monitoring Dashboard provides real-time visualization and control for the AI Safety System. It includes comprehensive features for proposal management, monitoring, and human oversight.

## Core Features

1. **ORKA Oversight** - Complete proposal lifecycle management with 9-phase workflow
2. **Evidence Engine** - Search system documentation with citations
3. **Decision Trajectories** - Visualize agent decision paths and state transitions
4. **Training Metrics** - Monitor self-play training progress and adversarial bypasses
5. **Workflow Orchestration** - Track multi-agent collaboration across proposal lifecycle stages

## New Features (Complete Implementation)

### PDF Export
Export comprehensive proposal reports as PDF documents with all 16 sections.

- **Endpoint**: `GET /api/proposals/<id>/export`
- **Features**: Full proposal data, risk visualizations, peer reviews, code sections
- **Dependency**: `reportlab>=4.0.0`

### Code Download
Download proposal code artifacts as tar.gz packages.

- **Endpoint**: `GET /api/proposals/<id>/code`
- **Contents**: metadata.json, proposed_code.py, test_results.json, peer_reviews.json, README.md

### USB Transfer System
Real USB writing for VAL offline validation.

- **Endpoints**:
  - `GET /api/usb/detect` - Detect mounted USB drives
  - `POST /api/usb/write` - Write proposals to USB
  - `GET /api/usb/verify` - Verify transfer integrity
- **Features**: Cross-platform detection (macOS/Linux/Windows), SHA-256 hashing, manifest generation

### 9-Phase Workflow Visualization
Complete workflow tracking for proposals.

- **Endpoint**: `GET /api/proposals/<id>/phases`
- **Phases**:
  1. Submission
  2. Agent Testing
  3. Peer Review
  4. ORKA Counterpoint
  5. Agent Defense
  6. Final Testing
  7. Human Notification
  8. VAL Validation
  9. Deployment

### Notifications API
Real-time notification system.

- **Endpoints**:
  - `GET /api/notifications` - Get all notifications
  - `GET /api/notifications/unread` - Get unread count
  - `POST /api/notifications/<id>/read` - Mark as read
  - `POST /api/notifications/read-all` - Mark all as read
  - `DELETE /api/notifications/<id>` - Delete notification
  - `DELETE /api/notifications` - Clear all

### Activity Log
Comprehensive activity tracking.

- **Endpoint**: `GET /api/activity`
- **Page**: `/activity`
- **Filters**: user, action, resource_type, pagination

### Advanced Search
Full-text search across proposals.

- **Endpoint**: `GET /api/proposals/search`
- **Parameters**: q, agent, status, component, min_risk, max_risk, date_from, date_to, phase
- **Features**: Highlighting, suggestions, pagination

### Proposal Comparison
Side-by-side proposal comparison.

- **Endpoint**: `GET /api/proposals/compare?ids=prop1,prop2`
- **Features**: Risk score comparison, differences detection, similarities analysis

### Real-Time Socket.IO Events
Comprehensive event system for live updates.

- `proposals:new` - New proposal submitted
- `proposals:update` - Proposal status changed
- `proposals:phase_transition` - Phase transition
- `orka:challenge` - ORKA counterpoint generated
- `val:validation` - VAL validation complete
- `deployment:complete` - Deployment finished
- `deception:alert` - Deception detected
- `collusion:attempt` - Collusion detected
- `notifications:new` - New notification

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
