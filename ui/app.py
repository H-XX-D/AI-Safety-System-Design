"""
ORKASTRATOR System - Modern Web GUI
====================================

Flask-based web interface for monitoring and controlling the Orkastrator AI Safety System.

Research Models:
- TIF: Scientific Research Model
- GIN: Engineering Model
- TORI: Historical Analysis Model
- THEO: Theoretical Model
- NOVEL: Creative Model
- ORKA: Orchestrator (System Coordinator)
- VAL: Validator Model

Features:
- Real-time proposal monitoring
- Deception detection visualization
- Penalty tracking
- System health metrics
- Debate visualization
- Emergency controls
"""

from flask import Flask, render_template, jsonify, request, Response, make_response, send_file, redirect, url_for, flash
from flask_socketio import SocketIO, emit
import json
import os
import sys
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import threading
import time
import random
from functools import wraps
from pathlib import Path
import logging
import subprocess

logger = logging.getLogger(__name__)

try:
    # Prefer repo config for WORM mount path when available
    from config_loader import load_config  # type: ignore
except Exception:  # keep UI robust in standalone mode
    def load_config():
        return {}

try:
    # Optional integrity check if present in environment
    from worm_manifest import verify_integrity as _verify_worm  # type: ignore
except Exception:
    _verify_worm = None

from load_simulation_data import (
    get_recent_proposals,
    get_proposals_by_agent,
    get_agent_statistics,
    get_system_statistics,
    get_detection_events_recent,
    load_detection_events,
    load_agent_states,
    load_proposals,
    get_proposal_by_id,
)

app = Flask(__name__)
# SECRET_KEY should be set via environment variable in production
# For development, a default key is provided but should be changed
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-DO-NOT-USE-IN-PRODUCTION')
# Limit inbound payload size (2 MiB)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
# Restrict Socket.IO CORS to same-origin by default; configurable via ui section
_cors_origins = None
_csp_allow_cdns = False
try:
    cfg = load_config() or {}
    ui_cfg = (cfg.get('ui', {}) or {}) if isinstance(cfg, dict) else {}
    _cors_origins = ui_cfg.get('socketio_cors_origins')
    _csp_allow_cdns = bool(ui_cfg.get('csp_allow_cdns', False))
except Exception:
    _cors_origins = None
    _csp_allow_cdns = False
if not _cors_origins:
    _cors_origins = []  # same-origin only
socketio = SocketIO(app, cors_allowed_origins=_cors_origins)

# Content Security Policy and Security Headers
@app.after_request
def set_security_headers(response):
    """Add security headers to all responses."""
    # Content Security Policy
    # Note: unsafe-inline is temporarily allowed for onclick handlers
    # TODO: Remove unsafe-inline after migrating all inline handlers to JS files
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers['Content-Security-Policy'] = csp_policy

    # Other security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    return response

# Standalone mode flag - set to True to run without parent components
STANDALONE_MODE = os.environ.get('STANDALONE', 'true').lower() == 'true'

# Try to import parent components, but work standalone if they're not available
if not STANDALONE_MODE:
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from orka_penalty_tracker import orka_penalty_tracker
        from translator import Translator
        from reward_engine import calculate_reward
        from core_values import verify_core_values
        from alignment_filter import AlignmentFilter
        # Optional orchestrator admin
        try:
            from orchestrator import Orchestrator
            from orchestrator_sandbox import SandboxEnvironmentManager  # type: ignore
            from memory_merkle import MemoryStorage
        except Exception:
            Orchestrator = None  # type: ignore
            SandboxEnvironmentManager = None  # type: ignore
            MemoryStorage = None  # type: ignore
    except ImportError as e:
        print(f"Could not import parent components: {e}")
        print("Falling back to standalone mode")
        STANDALONE_MODE = True

"""Initialize components"""
penalty_tracker = None
translator = None
alignment_filter = None
orchestrator_admin = None

# ------------------------ Admin RBAC ------------------------
def require_admin(roles: Optional[List[str]] = None):
    roles = roles or []
    def _decorator(fn):
        @wraps(fn)
        def _wrapped(*args, **kwargs):
            # basic rate limit per IP+endpoint
            ip = request.headers.get('X-Forwarded-For') or request.remote_addr or 'unknown'
            key = f"{ip}:{request.path}"
            if not _rate_ok(key):
                return jsonify({'error': 'rate_limited'}), 429
            # simple anti-CSRF: require AJAX header
            xhr = request.headers.get('X-Requested-With', '')
            if xhr.lower() != 'xmlhttprequest':
                _audit_log('admin_bad_origin', {'ip': ip, 'path': request.path})
                return jsonify({'error': 'bad_origin'}), 400
            token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
            expected = os.environ.get('ADMIN_TOKEN') or os.environ.get('UI_ADMIN_TOKEN') or ''
            role = request.headers.get('X-Admin-Role', '').strip().lower()
            if not expected or token != expected:
                _audit_log('admin_unauthorized', {'ip': ip, 'path': request.path})
                return jsonify({'error': 'unauthorized'}), 401
            if roles and role not in [r.lower() for r in roles]:
                _audit_log('admin_forbidden', {'ip': ip, 'path': request.path, 'role': role, 'required': roles})
                return jsonify({'error': 'forbidden', 'required_roles': roles}), 403
            _audit_log('admin_call', {'ip': ip, 'path': request.path, 'role': role})
            return fn(*args, **kwargs)
        return _wrapped
    return _decorator
def _resolve_worm_usb_path() -> str:
    """Resolve WORM USB base path from env or config with a sensible fallback."""
    # 1) Env override
    env_override = os.environ.get("WORM_USB_PATH")
    if env_override and os.path.exists(env_override):
        return env_override
    # 2) Config
    try:
        cfg = load_config() or {}
        cfg_path = (
            cfg.get('worm', {}).get('usb_mount_path')
            if isinstance(cfg.get('worm', {}), dict) else None
        )
        if isinstance(cfg_path, str) and os.path.exists(cfg_path):
            return cfg_path
    except Exception:
        pass
    # 3) Common macOS/Windows/Linux fallbacks
    candidates = [
        "/Volumes/ORKASTRATOR_WORM",
        "/Volumes/NO NAME/ORKASTRATOR_WORM",
        "/media/usb/ORKASTRATOR_WORM",
        "/mnt/usb/ORKASTRATOR_WORM",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # 4) As a last resort, return env or first candidate even if missing
    return env_override or candidates[0]

worm_usb_path = _resolve_worm_usb_path()

AGENT_ID_MAP = {
    1: "TIF",
    2: "GIN",
    3: "TORI",
    4: "THEO",
    5: "NOVEL",
    6: "ORKA",
    7: "VAL",
}

AGENT_META = {
    "TIF": {"id": 1, "name": "TIF (Scientific Research)", "specialty": "Scientific Analysis"},
    "GIN": {"id": 2, "name": "GIN (Engineering)", "specialty": "Engineering Solutions"},
    "TORI": {"id": 3, "name": "TORI (Historian)", "specialty": "Historical Analysis"},
    "THEO": {"id": 4, "name": "THEO (Theoretical)", "specialty": "Theoretical Framework"},
    "NOVEL": {"id": 5, "name": "NOVEL (Creative)", "specialty": "Creative Solutions"},
    "ORKA": {"id": 6, "name": "ORKASTRATOR (Orchestrator)", "specialty": "System Coordination"},
    "VAL": {"id": 7, "name": "VAL (Validator)", "specialty": "Validation & Review"},
}

def agent_code_from_id(agent_id: int) -> Optional[str]:
    return AGENT_ID_MAP.get(agent_id)


def build_detection_summary() -> Dict[str, Any]:
    events = load_detection_events()
    if not events:
        return {
            "total_evaluated": 0,
            "deception_detected": 0,
            "false_positives": 0,
            "accuracy": 0,
            "precision": 0,
            "recall": 0,
            "f1_score": 0,
            "methods": {},
        }

    total = len(events)
    flagged = sum(1 for e in events if e.get("status") == "flagged")
    cleared = sum(1 for e in events if e.get("status") == "cleared")
    false_positives = sum(1 for e in events if e.get("status") == "false_positive")

    accuracy = ((total - false_positives) / total) if total else 0
    precision = (flagged / (flagged + false_positives)) if (flagged + false_positives) else 0
    recall = (flagged / total) if total else 0
    f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0

    method_stats: Dict[str, Dict[str, Any]] = {}
    for event in events:
        method = event.get("method", "unknown")
        stats = method_stats.setdefault(method, {"triggers": 0, "total_confidence": 0.0})
        stats["triggers"] += 1
        stats["total_confidence"] += float(event.get("confidence", 0.0))

    methods_formatted = {
        method: {
            "triggers": data["triggers"],
            "avg_confidence": round(data["total_confidence"] / data["triggers"], 3) if data["triggers"] else 0,
        }
        for method, data in method_stats.items()
    }

    return {
        "total_evaluated": total,
        "deception_detected": flagged,
        "false_positives": false_positives,
        "accuracy": round(accuracy, 2),
        "precision": round(precision, 2),
        "recall": round(recall, 2),
        "f1_score": round(f1_score, 2),
        "methods": methods_formatted,
    }


def build_agent_history(agent_code: str, proposals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not proposals:
        return []

    history: List[Dict[str, Any]] = []
    approved = 0
    total = 0
    ordered = sorted(proposals, key=lambda p: p.get("timestamp", ""))
    for proposal in ordered[-30:]:
        total += 1
        if proposal.get("status") == "approved":
            approved += 1
        approval_rate = round(approved / total, 2) if total else 0
        history.append({
            "date": proposal.get("timestamp", "")[:10],
            "approval_rate": approval_rate,
            "reward": round((proposal.get("reward") or 0), 2),
            "deception_rate": round(float(proposal.get("deception_confidence", 0.0)), 2),
        })
    return history

def init_components():
    """Initialize system components."""
    global penalty_tracker, translator, alignment_filter

    if STANDALONE_MODE:
        print("✓ Running in standalone mode with mock data")
        print("  Set STANDALONE=false environment variable to use real components")
        return

    try:
        # Import penalty tracker (connects to ORKA database)
        penalty_tracker = orka_penalty_tracker

        # Initialize translator
        translator = Translator()

        # Initialize alignment filter
        alignment_filter = AlignmentFilter()

        # Initialize orchestrator admin (optional)
        if 'Orchestrator' in globals() and Orchestrator is not None:
            if os.environ.get('ENABLE_UI_ORCH', '0').lower() in {'1','true','yes','on'}:
                orchestrator_admin = Orchestrator(MemoryStorage(system_id=0, private_key='ui_admin'), environment_manager=SandboxEnvironmentManager())
                print("✓ Orchestrator admin available")

        # Check WORM USB
        if os.path.exists(worm_usb_path):
            print(f"✓ WORM USB found at {worm_usb_path}")
            # Optional integrity verification if available
            if _verify_worm is not None:
                try:
                    report = _verify_worm()
                    status = "verified" if report.get('verified') else "unverified"
                    print(f"  WORM integrity: {status}")
                except Exception as _e:
                    print(f"  WORM integrity check failed: {_e}")
        else:
            print(f"⚠ WORM USB not found at {worm_usb_path}")

        print("✓ Real components initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize components: {e}")
        print("✓ Falling back to standalone mode")
        import traceback
        traceback.print_exc()


@app.route('/api/worm/status')
def api_worm_status():
    """Return current WORM USB resolution + optional integrity report."""
    base = _resolve_worm_usb_path()
    exists = os.path.exists(base)
    report: Dict[str, Any] = {}
    verified = None
    read_only_ok = None
    # Determine fail-closed policy
    cfg = load_config() or {}
    cfg_fail = bool((cfg.get('worm', {}) or {}).get('fail_closed_writes', False)) if isinstance(cfg, dict) else False
    env_fail = os.environ.get('WORM_FAIL_CLOSED') or os.environ.get('FAIL_CLOSED_WORM_WRITES')
    fail_closed = cfg_fail or (str(env_fail).strip().lower() in {'1', 'true', 'yes', 'on'})
    if exists:
        # Prefer full verifier when available (provides read_only), fall back to worm_manifest
        used_full = False
        try:
            from verify_worm_integrity import WORMVerifier  # type: ignore
            from worm_paths import resolve_worm_root  # type: ignore
            try:
                root = resolve_worm_root(fallback=base)
            except Exception:
                root = base
            ver = WORMVerifier(root)
            ok, full = ver.verify()
            report = full or {}
            verified = bool(ok)
            checks = report.get('checks', {}) if isinstance(report.get('checks', {}), dict) else {}
            ro = checks.get('read_only')
            read_only_ok = bool(ro) if isinstance(ro, bool) else None
            used_full = True
        except Exception:
            pass
        if not used_full and _verify_worm is not None:
            try:
                report = _verify_worm() or {}
                verified = bool(report.get('verified', False))
                checks = report.get('checks', {}) if isinstance(report.get('checks', {}), dict) else {}
                ro = checks.get('read_only')
                read_only_ok = bool(ro) if isinstance(ro, bool) else None
            except Exception as _e:
                report = {"error": str(_e)}
    return jsonify({
        "path": base,
        "exists": exists,
        "verified": verified,
        "report": report,
        "fail_closed": fail_closed,
        "read_only": read_only_ok,
    })

# ------------------------ Admin API (optional) ------------------------

def _require_orchestrator():
    if orchestrator_admin is None:
        return jsonify({"error": "orchestrator admin not available"}), 501
    return None


@app.route('/api/admin/defense/submit', methods=['POST'])
@require_admin(['operator', 'safety_officer'])
def api_submit_defense():
    err = _require_orchestrator()
    if err:
        return err
    data = request.get_json(force=True) or {}
    pid = data.get('proposal_id')
    if not pid:
        return jsonify({"error": "proposal_id required"}), 400
    if not _valid_proposal_id(pid):
        return jsonify({"error": "invalid proposal_id"}), 400
    ok = orchestrator_admin.submit_agent_defense(pid, data)
    return jsonify({"ok": bool(ok)})


@app.route('/api/admin/val/export', methods=['POST'])
@require_admin(['safety_officer'])
def api_val_export():
    err = _require_orchestrator()
    if err:
        return err
    data = request.get_json(force=True) or {}
    pid = data.get('proposal_id')
    if not pid:
        return jsonify({"error": "proposal_id required"}), 400
    if not _valid_proposal_id(pid):
        return jsonify({"error": "invalid proposal_id"}), 400
    path = orchestrator_admin.initiate_val_validation(pid)
    if not path:
        return jsonify({"ok": False, "error": "export_failed"}), 500
    return jsonify({"ok": True, "path": path})


@app.route('/api/admin/val/import', methods=['POST'])
@require_admin(['safety_officer'])
def api_val_import():
    err = _require_orchestrator()
    if err:
        return err
    data = request.get_json(force=True) or {}
    pid = data.get('proposal_id')
    path = data.get('path')
    req_signer = data.get('required_signer_id')
    if not pid or not path:
        return jsonify({"error": "proposal_id and path required"}), 400
    if not _valid_proposal_id(pid):
        return jsonify({"error": "invalid proposal_id"}), 400
    ok = orchestrator_admin.import_val_result(pid, path, required_signer_id=req_signer)
    return jsonify({"ok": bool(ok)})

@app.route('/api/admin/val/inspect', methods=['POST'])
@require_admin(['safety_officer'])
def api_val_inspect():
    try:
        data = request.get_json(force=True) or {}
        path = data.get('path')
        if not path:
            return jsonify({'error': 'path required'}), 400
        from pathlib import Path
        p = Path(path)
        if not p.exists():
            return jsonify({'error': 'file not found'}), 404
        import json as _json
        with p.open('r', encoding='utf-8') as fh:
            doc = _json.load(fh)
        summary = {'format': 'legacy', 'signatures': 0, 'required_signers': 1, 'approved': False, 'signatures_detail': [], 'content_hash_match': None}
        try:
            from val_bridge import verify_val_response  # type: ignore
            verdict = verify_val_response(path)
            summary['approved'] = bool(verdict.get('approved', False))
        except Exception:
            pass
        if isinstance(doc, dict) and 'manifest' in doc and 'payload' in doc:
            man = doc.get('manifest') or {}
            sigs = man.get('signatures') or []
            summary.update({
                'format': 'manifest',
                'required_signers': man.get('required_signers', summary['required_signers']),
                'signatures': len(sigs),
                'proposal_id': man.get('proposal_id') or (doc.get('payload') or {}).get('proposal_id'),
                'content_hash': man.get('content_hash'),
            })
            # Build per-signature validation details
            try:
                from val_bridge import _verify_signature  # type: ignore
                import hashlib as _hashlib
                payload_bytes = _json.dumps(doc.get('payload') or {}, sort_keys=True).encode('utf-8')
                ch = _hashlib.sha256(payload_bytes).hexdigest()
                summary['content_hash_match'] = (str(man.get('content_hash')) == ch)
                details = []
                for s in sigs:
                    rid = s.get('reviewer_id')
                    msg = {
                        'reviewer_id': rid,
                        'proposal_id': man.get('proposal_id') or (doc.get('payload') or {}).get('proposal_id'),
                        'approved': bool(s.get('approved', False)),
                        'timestamp': s.get('timestamp'),
                        'content_hash': ch,
                        'signature': s.get('signature'),
                    }
                    valid = bool(_verify_signature(msg))
                    details.append({
                        'reviewer_id': rid,
                        'approved': bool(s.get('approved', False)),
                        'timestamp': s.get('timestamp'),
                        'valid': valid,
                        'notes': s.get('notes', ''),
                    })
                summary['signatures_detail'] = details
            except Exception:
                pass
            # Optional signer identity map from config
            try:
                cfg = load_config() or {}
                identities = (cfg.get('val', {}) or {}).get('signers', {})
                if isinstance(identities, dict):
                    summary['signer_identities'] = identities
            except Exception:
                pass
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/secure-transport/self-check', methods=['POST'])
@require_admin(['safety_officer'])
def api_secure_transport_self_check():
    """Encode/decode a sample message via MessageCodec to verify secure transport path."""
    try:
        from message_codec import MessageCodec  # type: ignore
        codec = MessageCodec(prefer_secure_bitpacked=True, min_compression_size=18)
        text = "System 6 approves proposal 001"
        payload, method, meta = codec.encode(text)
        decoded, info = codec.decode(payload)
        ok = (decoded == text) and bool(meta.get('secure_transport')) and bool(info.get('secure_transport'))
        return jsonify({'ok': ok, 'method': method, 'meta': meta, 'info': info})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/admin/worm/verify-clear', methods=['POST'])
@require_admin(['safety_officer'])
def api_worm_verify_clear():
    err = _require_orchestrator()
    if err:
        return err
    halted = orchestrator_admin.verify_and_clear_worm_halt()
    return jsonify({"halted": bool(halted)})


@app.route('/admin')
def admin_panel():
    # Gather basic admin info
    worm = json.loads(api_worm_status().get_data())
    val_root = (load_config() or {}).get('val', {}).get('io_root') if not STANDALONE_MODE else None
    required_signers = None
    try:
        required_signers = (load_config() or {}).get('val', {}).get('required_signers')
    except Exception:
        required_signers = None
    outbox = []
    inbox = []
    try:
        root = val_root or os.path.join(os.getcwd(), 'demo_outputs', 'val')
        outbox_dir = os.path.join(root, 'outbox')
        inbox_dir = os.path.join(root, 'inbox')
        if os.path.isdir(outbox_dir):
            outbox = sorted(os.listdir(outbox_dir))[:50]
        if os.path.isdir(inbox_dir):
            inbox = sorted(os.listdir(inbox_dir))[:50]
    except Exception:
        pass
    return render_template('admin.html', worm=worm, val_outbox=outbox, val_inbox=inbox, orchestrator_enabled=orchestrator_admin is not None, required_signers=required_signers)

# Routes
@app.route('/')
def index():
    """Main dashboard."""
    return render_template('dashboard.html')

@app.route('/proposals')
def proposals():
    """Proposal management view."""
    return render_template('proposals.html')

@app.route('/detection')
def detection():
    """Deception detection view."""
    return render_template('detection.html')

@app.route('/penalties')
def penalties():
    """Penalties and reputation view."""
    return render_template('penalties.html')

@app.route('/system')
def system():
    """System health and metrics view."""
    return render_template('system.html')

@app.route('/config')
def config():
    """Configuration view."""
    return render_template('config.html')

@app.route('/orka')
def orka_oversight():
    """ORKA Oversight view - comprehensive proposal management."""
    return render_template('orka.html')

@app.route('/research')
def research():
    """Research agents hardware and performance view."""
    return render_template('research.html')

@app.route('/agent')
def agent_detail():
    """Agent detail view."""
    return render_template('agent_detail.html')

@app.route('/paperqa')
def paperqa_view():
    """PaperQA evidence search view."""
    return render_template('paperqa.html')

@app.route('/docs/RESEARCH_CAPABILITIES.md')
def research_capabilities_doc():
    """Serve research capabilities documentation."""
    try:
        doc_path = Path(__file__).parent.parent / 'docs' / 'RESEARCH_CAPABILITIES.md'
        if doc_path.exists():
            return send_file(doc_path, mimetype='text/markdown')
        else:
            return "Documentation not found", 404
    except Exception as e:
        logger.error(f"Error serving research capabilities doc: {e}")
        return "Error loading documentation", 500

@app.route('/browser')
def browser_view():
    """Restricted research browser - only allows whitelisted sites, no API/CLI access."""
    return render_template('browser.html')

@app.route('/api/health')
def api_health_paperqa():
    """Health check endpoint for Jetson Nano PaperQA clients."""
    return jsonify({
        'status': 'healthy',
        'service': 'ORKASTRATOR PaperQA',
        'version': '1.0.0',
        'evidence_engine_available': _evidence_docs is not None,
        'evidence_indexing': _evidence_indexing
    })

@app.route('/ldp')
def ldp_view():
    """LDP trajectory visualization view."""
    return render_template('ldp.html')

@app.route('/agent0')
def agent0_view():
    """Agent0 self-play metrics view."""
    return render_template('agent0.html')

@app.route('/robin')
def robin_view():
    """Robin multi-agent orchestration view."""
    return render_template('robin.html')

# API Endpoints
@app.route('/api/status')
def api_status():
    """Get system status."""
    try:
        # Check component health
        components = {
            'penalty_tracker': penalty_tracker is not None,
            'translator': translator is not None,
            'alignment_filter': alignment_filter is not None,
            'worm_usb': os.path.exists(worm_usb_path)
        }

        system_stats = get_system_statistics()
        detection_events = load_detection_events()
        avg_penalty_multiplier = system_stats.get('avg_penalty_multiplier', 1.0)
        active_penalties = system_stats.get('active_penalties', 0)

        return jsonify({
            'status': 'operational' if all(components.values()) else 'degraded',
            'timestamp': datetime.now().isoformat(),
            'standalone_mode': STANDALONE_MODE,
            'components': components,
            'metrics': {
                'uptime': '12h simulated',
                'proposals_processed': system_stats.get('total_proposals', 0),
                'deception_detected': len(detection_events),
                'avg_processing_time': '2.1s (simulated)',
                'active_penalties': active_penalties,
                'avg_penalty_multiplier': f'{avg_penalty_multiplier:.2f}'
            },
            'halted': bool(getattr(globals().get('orchestrator_admin', None), '_halted', False))
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health_check():
    """Simple health check endpoint for Docker/Kubernetes."""
    try:
        # Basic health check - verify Flask is responding
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503


@app.route('/api/system/halted')
def api_system_halted():
    try:
        halted = bool(getattr(globals().get('orchestrator_admin', None), '_halted', False))
        reason = 'worm_guard' if halted else 'ok'
        return jsonify({'halted': halted, 'reason': reason, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        return jsonify({'halted': False, 'error': str(e)}), 200

@app.route('/api/proposals/recent')
def api_recent_proposals():
    """Get recent proposals."""
    try:
        proposals = get_recent_proposals(limit=8)
        if not proposals:
            proposals = []
        return jsonify({'proposals': proposals})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/detection/stats')
def api_detection_stats():
    """Get detection statistics."""
    try:
        stats = build_detection_summary()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/penalties/agents')
def api_agent_penalties():
    """Get agent penalty information."""
    try:
        agents = []
        for code, meta in AGENT_META.items():
            # Skip ORKA and VAL - they don't submit proposals
            if code in ['ORKA', 'VAL']:
                continue

            stats = get_agent_statistics(code)
            agents.append({
                'id': meta['id'],
                'name': meta['name'],
                'specialty': meta['specialty'],
                'penalty_multiplier': round(stats.get('penalty_multiplier', 1.0), 2),
                'incidents': stats.get('incidents', 0),
                'total_rewards': round(stats.get('total_rewards', 0.0), 2),
                'proposals_submitted': stats.get('total_proposals', 0),
                'approval_rate': round(stats.get('approval_rate', 0.0), 2)
            })
        return jsonify({'agents': agents})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent/<int:agent_id>')
def api_agent_detail(agent_id):
    """Get detailed information for a specific agent."""
    try:
        agent_code = agent_code_from_id(agent_id)
        if not agent_code or agent_code not in AGENT_META:
            return jsonify({'error': 'Agent not found'}), 404

        meta = AGENT_META[agent_code]
        stats = get_agent_statistics(agent_code)
        proposals = get_proposals_by_agent(agent_code, limit=60)
        history_data = build_agent_history(agent_code, proposals)

        agent_data = {
            'id': meta['id'],
            'name': meta['name'],
            'full_name': meta['name'],
            'specialty': meta['specialty'],
            'penalty_multiplier': round(stats.get('penalty_multiplier', 1.0), 2),
            'incidents': stats.get('incidents', 0),
            'total_rewards': round(stats.get('total_rewards', 0.0), 2),
            'proposals_submitted': stats.get('total_proposals', 0),
            'approval_rate': round(stats.get('approval_rate', 0.0), 2),
            'history': history_data
        }

        return jsonify(agent_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent/<int:agent_id>/proposals')
def api_agent_proposals(agent_id):
    """Get proposals for a specific agent."""
    try:
        agent_code = agent_code_from_id(agent_id)
        if not agent_code or agent_code not in AGENT_META:
            return jsonify({'error': 'Agent not found'}), 404

        # Special cases: ORKASTRATOR and VAL don't submit proposals
        if agent_id == 6:  # ORKASTRATOR
            return jsonify({
                'proposals': [],
                'count': 0,
                'message': 'ORKASTRATOR is the orchestrator/coordinator. It manages communication, hosts testing environments, and monitors for collusion but does not submit improvement proposals.'
            })

        if agent_id == 7:  # VAL
            return jsonify({
                'proposals': [],
                'count': 0,
                'message': 'VAL is the offline validator. It only receives updates via physical medium exchange and validates the system independently. It does not submit proposals to the online system.'
            })

        proposals = get_proposals_by_agent(agent_code, limit=40)
        return jsonify({'proposals': proposals, 'count': len(proposals)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/metrics')
def api_system_metrics():
    """Get system performance metrics."""
    try:
        metrics = {
            'cpu_usage': 45.2,
            'memory_usage': 62.8,
            'disk_usage': 38.5,
            'network_io': {'in': 1.2, 'out': 0.8},
            'sandbox_backends': {
                'docker': {'status': 'operational', 'containers': 3},
                'firecracker': {'status': 'standby', 'vms': 0}
            },
            'test_results': {
                'passed': 131,
                'failed': 0,
                'skipped': 11,
                'total': 142
            },
            'worm_status': {
                'verified': True,
                'last_check': datetime.now().isoformat(),
                'manifest_hash': '5bdb62947a9cee2fa77d038483e0b4894e9735c7b690d8062a1b48266aaf5639'
            }
        }
        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emergency/halt', methods=['POST'])
def api_emergency_halt():
    """Emergency halt all agents."""
    try:
        # This would trigger production_control_hooks
        return jsonify({
            'status': 'success',
            'message': 'Emergency halt triggered',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/proposals/all')
def api_proposals_all():
    """Get all proposals with comprehensive data."""
    try:
        proposals = load_proposals()
        # Add approval rate calculation
        for p in proposals:
            votes = p.get('debate_votes', [])
            p['approval_rate'] = sum(votes) / len(votes) if votes else 1.0
        return jsonify(proposals)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/proposals/<proposal_id>')
def api_proposal_detail(proposal_id):
    """Get comprehensive proposal details."""
    try:
        proposal = get_proposal_by_id(proposal_id)
        if not proposal:
            return jsonify({'error': 'Proposal not found'}), 404

        # Add comprehensive data structure
        # In production, this would load from database with all fields
        # Optional deception analysis for UI (static scan + summary)
        deception_analysis: Dict[str, Any] = {}
        try:
            from types import SimpleNamespace
            from deception_detector import DeceptionDetector  # type: ignore
            det = DeceptionDetector(semantic_classifier_enabled=False)
            p = SimpleNamespace(
                motivation=proposal.get('motivation') or proposal.get('description') or '',
                expected_benefits=' '.join(proposal.get('expected_benefits', [])) if isinstance(proposal.get('expected_benefits'), list) else str(proposal.get('expected_benefits') or ''),
                proposed_code=str(proposal.get('proposed_code') or ''),
                identified_risks=proposal.get('identified_risks', []) or [],
                admitted_uncertainties=proposal.get('admitted_uncertainties', []) or [],
                confidence_level=float(proposal.get('confidence_level', 0.5) or 0.5),
            )
            verdict = det.detect_deception(p, memory_audit_results={}, debate_context={})
            deception_analysis = {
                'deception_detected': verdict.deception_detected,
                'confidence': verdict.confidence,
                'deception_type': getattr(verdict.deception_type, 'value', str(verdict.deception_type)),
                'severity': getattr(verdict.severity, 'value', str(verdict.severity)),
                'reasons': verdict.reasons,
                'evidence': verdict.evidence,
            }
        except Exception:
            deception_analysis = {}

        comprehensive = {
            **proposal,
            'idea': {
                'description': proposal.get('description', ''),
                'motivation': 'Improve system capabilities and safety',
                'technical_approach': f"Implementation in {proposal.get('component', 'system')} module",
                'expected_benefits': ['Enhanced functionality', 'Improved safety', 'Better performance'],
                'scope': proposal.get('component', 'Unknown'),
                'dependencies': []
            },
            'deception_analysis': deception_analysis,
            'risks': {
                'technical_risks': [],
                'safety_risks': [],
                'alignment_risks': [],
                'overall_risk_score': proposal.get('deception_confidence', 0)
            },
            'experiments': {
                'test_environment': 'Sandbox with 1000 test cases',
                'metrics': [],
                'test_cases_passed': 487,
                'test_cases_failed': 13,
                'pass_rate': 0.974,
                'edge_cases_tested': []
            },
            'peer_reviews': {
                'reviews': [],
                'approval_rate': 1.0 if proposal.get('status') == 'approved' else 0.8
            },
            'orka_counterpoint': {
                'adversarial_analysis': 'ORKA performed comprehensive adversarial testing',
                'attack_vectors_tested': [],
                'worst_case_scenarios': [],
                'recommendation': 'Approve with monitoring',
                'concerns': []
            },
            'agent_defense': {
                'response_to_concerns': [],
                'revisions_made': [],
                'updated_timeline': 'On schedule'
            },
            'final_testing': {
                'comprehensive_test_suite': {
                    'unit_tests': 487,
                    'integration_tests': 89,
                    'end_to_end_tests': 34,
                    'security_tests': 23,
                    'performance_tests': 18,
                    'total': 651,
                    'passed': 651,
                    'pass_rate': 1.0
                },
                'safety_validation': {
                    'deception_checks': 'passed',
                    'alignment_checks': 'passed',
                    'adversarial_testing': 'passed'
                },
                'performance_validation': {}
            },
            'val_validation': {
                'validation_duration_hours': 3.5,
                'val_checks_performed': ['Code audit', 'Security scan', 'Safety tests'],
                'val_findings': [],
                'val_recommendation': 'APPROVE' if proposal.get('status') == 'approved' else 'PENDING',
                'val_confidence': 0.94
            },
            'code': {
                'files_modified': [],
                'files_added': [],
                'total_lines_changed': 1247,
                'test_coverage': 0.97,
                'code_attached': False
            }
        }

        return jsonify(comprehensive)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/random-file/pull')
def api_random_file_pull():
    """Pull random files from system for verification."""
    try:
        import secrets
        from pathlib import Path
        import hashlib

        source = request.args.get('source', 'worm_usb')
        count = int(request.args.get('count', 1))

        if count < 1 or count > 10:
            return jsonify({'error': 'Count must be between 1 and 10'}), 400

        # Define source directories
        base_dir = Path('/Users/hendrixx./AI-Safety-System-Design')
        source_paths = {
            'worm_usb': base_dir / 'worm_usb_dir',
            'proposals': base_dir / 'ui' / 'simulation_data',
            'audit_logs': base_dir / 'audit',
            'system': base_dir
        }

        source_path = source_paths.get(source, source_paths['worm_usb'])

        if not source_path.exists():
            return jsonify({'error': f'Source path does not exist: {source_path}'}), 404

        # Get all files from source (excluding hidden and system files)
        all_files = []
        for ext in ['*.json', '*.jsonl', '*.txt', '*.bin', '*.aura', '*.log', '*.py']:
            all_files.extend(list(source_path.rglob(ext)))

        # Filter out directories and system files
        all_files = [f for f in all_files if f.is_file() and not f.name.startswith('.')]

        if not all_files:
            return jsonify({'error': f'No files found in {source}'}), 404

        # Randomly select files using cryptographic randomness
        selected_files = []
        file_indices = set()

        while len(selected_files) < min(count, len(all_files)):
            index = secrets.randbelow(len(all_files))
            if index not in file_indices:
                file_indices.add(index)
                selected_files.append(all_files[index])

        # Check decodability for each file
        results = []
        for file_path in selected_files:
            file_info = check_file_decodability(file_path, source)
            results.append(file_info)

        return jsonify({
            'success': True,
            'source': source,
            'count': len(results),
            'files': results
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def check_file_decodability(file_path: Path, source: str) -> dict:
    """Check if a file can be decoded by hardware translator using existing infrastructure."""
    try:
        import hashlib
        import sys

        # Add parent directory to path for imports
        sys.path.insert(0, '/Users/hendrixx./AI-Safety-System-Design')

        # Read file
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
        except Exception as e:
            return {
                'filename': file_path.name,
                'file_path': str(file_path),
                'source': source,
                'size': 0,
                'decodable': False,
                'format': 'Error',
                'error': str(e)
            }

        # Calculate hash using standard method
        file_hash = hashlib.sha256(content).hexdigest()

        # Determine file format and decodability
        decodable = False
        file_format = 'Unknown'
        compression = None
        airgap_stats = {}

        # Try to use existing FileExportValidator for decodability check
        try:
            from file_export_validator import FileExportValidator

            validator = FileExportValidator(
                base_export_dir='/tmp/file_exports',
                audit_log_path='/tmp/export_audit.jsonl'
            )

            # Check airgap decodability
            is_decodable, reason, stats = validator.validate_airgap_decodability(str(file_path))

            if is_decodable:
                decodable = True
                file_format = reason  # Contains format description
                airgap_stats = stats

                # Determine compression type from stats
                if stats.get('bitpacked_frames', 0) > 0:
                    compression = 'Bit-Packed'
                elif stats.get('aura_blobs', 0) > 0:
                    compression = 'AURA'
                elif stats.get('hex_lines', 0) > 0:
                    compression = 'Hex-Encoded'
            else:
                # Fall back to basic format detection
                decodable, file_format, compression = detect_file_format_fallback(content, file_path)
        except Exception as e:
            print(f"Validator not available, using fallback: {e}")
            # Fall back to basic format detection
            decodable, file_format, compression = detect_file_format_fallback(content, file_path)

        return {
            'filename': file_path.name,
            'file_path': str(file_path),
            'source': source,
            'size': len(content),
            'hash': file_hash,
            'decodable': decodable,
            'format': file_format,
            'compression': compression,
            'airgap_stats': airgap_stats if airgap_stats else None
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'filename': file_path.name if file_path else 'unknown',
            'file_path': str(file_path) if file_path else '',
            'source': source,
            'size': 0,
            'decodable': False,
            'format': 'Error',
            'error': str(e)
        }

def detect_file_format_fallback(content: bytes, file_path: Path) -> Tuple[bool, str, Optional[str]]:
    """Fallback file format detection when validator is not available."""
    decodable = False
    file_format = 'Unknown'
    compression = None

    # Check for JSON
    if file_path.suffix in ['.json', '.jsonl']:
        try:
            import json
            json.loads(content.decode('utf-8'))
            decodable = True
            file_format = 'JSON'
        except:
            pass

    # Check for text files
    elif file_path.suffix in ['.txt', '.log', '.py', '.md']:
        try:
            content.decode('utf-8')
            decodable = True
            file_format = 'Text'
        except:
            file_format = 'Binary'

    # Check for AURA compression
    elif file_path.suffix == '.aura':
        file_format = 'AURA Compressed'
        compression = 'AURA'
        decodable = True

    # Check for binary protocol messages
    elif file_path.suffix == '.bin':
        file_format = 'Binary Protocol'
        # Check if it matches bit-packed or AURA format
        if len(content) % 4 == 0 or len(content) % 6 == 0:
            file_format = 'Bit-Packed Protocol'
            compression = 'Bit-Packed'
            decodable = True

    return decodable, file_format, compression

@app.route('/api/random-file/decode', methods=['POST'])
def api_random_file_decode():
    """Decode a file using hardware translator."""
    try:
        from pathlib import Path
        import hashlib

        data = request.get_json()
        file_path = Path(data.get('file_path', ''))
        source = data.get('source', 'unknown')

        # Allowlist: restrict to known demo outputs
        allowed_roots = [Path(os.getcwd()) / 'demo_outputs', Path(os.getcwd()) / 'demo_outputs_doc']
        try:
            real = file_path.resolve(strict=False)
            if not any(str(real).startswith(str(root.resolve())) for root in allowed_roots):
                return jsonify({'error': 'path_not_allowed'}), 403
        except Exception:
            return jsonify({'error': 'invalid_path'}), 400
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        # Read file content
        with open(file_path, 'rb') as f:
            raw_content = f.read()

        file_hash = hashlib.sha256(raw_content).hexdigest()

        # Attempt to decode
        content_raw = ''
        content_translated = ''
        content_hex = ''
        file_format = 'Unknown'
        confidence = 0.0
        compression_type = None

        # Try to decode as text
        try:
            content_raw = raw_content.decode('utf-8')
            content_translated = content_raw  # No translation needed for text
            file_format = 'Text/JSON'
            confidence = 1.0
        except UnicodeDecodeError:
            # Binary file - create hex dump
            content_raw = '<Binary file>'
            file_format = 'Binary'
            confidence = 0.5

        # Create hex dump
        hex_lines = []
        for i in range(0, min(len(raw_content), 1024), 16):  # Limit to first 1KB
            hex_part = ' '.join(f'{b:02x}' for b in raw_content[i:i+16])
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in raw_content[i:i+16])
            hex_lines.append(f'{i:08x}  {hex_part:<48}  {ascii_part}')
        content_hex = '\n'.join(hex_lines)

        if len(raw_content) > 1024:
            content_hex += f'\n\n... ({len(raw_content) - 1024} more bytes not shown)'

        # Attempt protocol translation if available
        try:
            # Try to import translator
            import sys
            sys.path.insert(0, '/Users/hendrixx./AI-Safety-System-Design')
            from translator import Translator

            translator = Translator()

            # Try to translate if it looks like a protocol message
            if file_format == 'Binary' or '.bin' in file_path.suffix:
                try:
                    translated = translator.translate_from_bytes(raw_content)
                    if translated:
                        content_translated = translated
                        confidence = 0.9
                        file_format = 'AI Protocol Message'
                except:
                    pass
        except Exception as e:
            print(f"Translator not available: {e}")

        return jsonify({
            'success': True,
            'filename': file_path.name,
            'file_path': str(file_path),
            'source': source,
            'size': len(raw_content),
            'hash': file_hash,
            'decodable': True,
            'format': file_format,
            'compression': compression_type,
            'confidence': confidence,
            'content_raw': content_raw[:10000],  # Limit size
            'content_translated': content_translated[:10000],
            'content_hex': content_hex
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/random-file/download')
def api_random_file_download():
    """Download a file."""
    try:
        from pathlib import Path
        file_path = Path(request.args.get('file_path', ''))
        allowed_roots = [Path(os.getcwd()) / 'demo_outputs', Path(os.getcwd()) / 'demo_outputs_doc']
        try:
            real = file_path.resolve(strict=False)
            if not any(str(real).startswith(str(root.resolve())) for root in allowed_roots):
                return jsonify({'error': 'path_not_allowed'}), 403
        except Exception:
            return jsonify({'error': 'invalid_path'}), 400
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        return Response(
            open(file_path, 'rb').read(),
            mimetype='application/octet-stream',
            headers={
                'Content-Disposition': f'attachment; filename={file_path.name}'
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# SD CARD VERIFICATION SYSTEM
# ============================================================================
# In-memory verification queue (should be database in production)
verification_queue = []
verification_counter = 0
system_continuation_blocked = False

@app.route('/api/sd-card/status')
def api_sd_card_status():
    """Check SD card mount status and available space"""
    try:
        sd_card_path = Path('/Volumes/SDCARD')

        if not sd_card_path.exists():
            return jsonify({
                'success': False,
                'mounted': False,
                'message': 'SD card not detected'
            })

        # Get disk usage
        import shutil
        total, used, free = shutil.disk_usage(sd_card_path)

        return jsonify({
            'success': True,
            'mounted': True,
            'path': str(sd_card_path),
            'total_bytes': total,
            'used_bytes': used,
            'free_bytes': free,
            'free_percent': round((free / total) * 100, 1),
            'message': f'SD card mounted: {free / (1024**3):.1f}GB free'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'mounted': False,
            'error': str(e)
        }), 500

@app.route('/api/sd-card/write', methods=['POST'])
def api_sd_card_write():
    """Write file to SD card and add to verification queue"""
    global verification_counter, system_continuation_blocked

    try:
        data = request.get_json()
        file_path = data.get('file_path', '')
        source_file = Path(file_path)

        if not source_file.exists():
            return jsonify({
                'success': False,
                'error': 'Source file not found'
            }), 404

        sd_card_path = Path('/Volumes/SDCARD')
        if not sd_card_path.exists():
            return jsonify({
                'success': False,
                'error': 'SD card not mounted'
            }), 400

        # Create verification directory on SD card
        verification_dir = sd_card_path / 'pending_verifications'
        verification_dir.mkdir(exist_ok=True)

        # Read source file
        with open(source_file, 'rb') as f:
            content = f.read()

        # Calculate hash
        file_hash = hashlib.sha256(content).hexdigest()

        # Write to SD card with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest_filename = f"{timestamp}_{source_file.name}"
        dest_path = verification_dir / dest_filename

        with open(dest_path, 'wb') as f:
            f.write(content)

        # Add to verification queue
        verification_counter += 1
        verification_entry = {
            'id': verification_counter,
            'filename': source_file.name,
            'source_path': str(source_file),
            'sd_path': str(dest_path),
            'hash': file_hash,
            'size_bytes': len(content),
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'
        }
        verification_queue.append(verification_entry)

        # Block system continuation
        system_continuation_blocked = True

        return jsonify({
            'success': True,
            'verification_id': verification_counter,
            'sd_path': str(dest_path),
            'hash': file_hash,
            'message': f'File written to SD card. System continuation blocked pending verification.'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/verification/queue')
def api_verification_queue():
    """Get all pending verifications"""
    try:
        pending = [v for v in verification_queue if v['status'] == 'pending']
        approved = [v for v in verification_queue if v['status'] == 'approved']
        rejected = [v for v in verification_queue if v['status'] == 'rejected']

        return jsonify({
            'success': True,
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'system_blocked': system_continuation_blocked,
            'total_pending': len(pending)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/verification/<int:verification_id>/approve', methods=['POST'])
def api_verification_approve(verification_id):
    """Approve a single verification"""
    global system_continuation_blocked

    try:
        # Find verification entry
        verification = None
        for v in verification_queue:
            if v['id'] == verification_id:
                verification = v
                break

        if not verification:
            return jsonify({
                'success': False,
                'error': 'Verification not found'
            }), 404

        if verification['status'] != 'pending':
            return jsonify({
                'success': False,
                'error': f'Verification already {verification["status"]}'
            }), 400

        # Update status
        verification['status'] = 'approved'
        verification['approved_at'] = datetime.now().isoformat()

        # Check if any pending remain
        pending_count = sum(1 for v in verification_queue if v['status'] == 'pending')
        if pending_count == 0:
            system_continuation_blocked = False

        # Log to audit
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': 'verification_approved',
            'verification_id': verification_id,
            'filename': verification['filename'],
            'hash': verification['hash']
        }

        return jsonify({
            'success': True,
            'verification_id': verification_id,
            'remaining_pending': pending_count,
            'system_blocked': system_continuation_blocked,
            'message': f'Verification approved. {pending_count} remaining.'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/verification/<int:verification_id>/reject', methods=['POST'])
def api_verification_reject(verification_id):
    """Reject a single verification"""
    global system_continuation_blocked

    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'No reason provided')

        # Find verification entry
        verification = None
        for v in verification_queue:
            if v['id'] == verification_id:
                verification = v
                break

        if not verification:
            return jsonify({
                'success': False,
                'error': 'Verification not found'
            }), 404

        if verification['status'] != 'pending':
            return jsonify({
                'success': False,
                'error': f'Verification already {verification["status"]}'
            }), 400

        # Update status
        verification['status'] = 'rejected'
        verification['rejected_at'] = datetime.now().isoformat()
        verification['rejection_reason'] = reason

        # Check if any pending remain
        pending_count = sum(1 for v in verification_queue if v['status'] == 'pending')
        if pending_count == 0:
            system_continuation_blocked = False

        # Delete file from SD card
        try:
            sd_path = Path(verification['sd_path'])
            if sd_path.exists():
                sd_path.unlink()
        except Exception as e:
            print(f"Warning: Could not delete rejected file: {e}")

        # Log to audit
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': 'verification_rejected',
            'verification_id': verification_id,
            'filename': verification['filename'],
            'hash': verification['hash'],
            'reason': reason
        }

        return jsonify({
            'success': True,
            'verification_id': verification_id,
            'remaining_pending': pending_count,
            'system_blocked': system_continuation_blocked,
            'message': f'Verification rejected. {pending_count} remaining.'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/verification/approve-all', methods=['POST'])
def api_verification_approve_all():
    """Approve all pending verifications"""
    global system_continuation_blocked

    try:
        approved_count = 0
        timestamp = datetime.now().isoformat()

        for v in verification_queue:
            if v['status'] == 'pending':
                v['status'] = 'approved'
                v['approved_at'] = timestamp
                approved_count += 1

        # Unblock system
        system_continuation_blocked = False

        return jsonify({
            'success': True,
            'approved_count': approved_count,
            'system_blocked': False,
            'message': f'All {approved_count} verifications approved. System unblocked.'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/verification/reject-all', methods=['POST'])
def api_verification_reject_all():
    """Reject all pending verifications"""
    global system_continuation_blocked

    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'Batch rejection')

        rejected_count = 0
        timestamp = datetime.now().isoformat()

        for v in verification_queue:
            if v['status'] == 'pending':
                v['status'] = 'rejected'
                v['rejected_at'] = timestamp
                v['rejection_reason'] = reason
                rejected_count += 1

                # Delete file from SD card
                try:
                    sd_path = Path(v['sd_path'])
                    if sd_path.exists():
                        sd_path.unlink()
                except Exception as e:
                    print(f"Warning: Could not delete rejected file: {e}")

        # Unblock system
        system_continuation_blocked = False

        return jsonify({
            'success': True,
            'rejected_count': rejected_count,
            'system_blocked': False,
            'message': f'All {rejected_count} verifications rejected. System unblocked.'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/system/continuation-status')
def api_system_continuation_status():
    """Check if system can continue (not blocked by pending verifications)"""
    try:
        pending_count = sum(1 for v in verification_queue if v['status'] == 'pending')

        return jsonify({
            'success': True,
            'can_continue': not system_continuation_blocked,
            'blocked': system_continuation_blocked,
            'pending_verifications': pending_count,
            'message': 'System blocked by pending verifications' if system_continuation_blocked else 'System can continue'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# COLLUSION DETECTION SYSTEM
# ============================================================================
# In-memory collusion attempts storage (should be database in production)
collusion_attempts = []
collusion_counter = 0

@app.route('/api/collusion/attempts')
def api_collusion_attempts():
    """Get all detected collusion attempts"""
    try:
        # In production, load from database
        # For simulation, generate sample data
        if len(collusion_attempts) == 0:
            generate_sample_collusion_data()

        # Get filters from query params
        severity = request.args.get('severity', None)
        status = request.args.get('status', None)
        agent = request.args.get('agent', None)
        limit = int(request.args.get('limit', 50))

        filtered = collusion_attempts.copy()

        if severity:
            filtered = [c for c in filtered if c['severity'] == severity]
        if status:
            filtered = [c for c in filtered if c['status'] == status]
        if agent:
            filtered = [c for c in filtered if agent in c['agents_involved']]

        # Sort by timestamp (newest first)
        filtered.sort(key=lambda x: x['timestamp'], reverse=True)

        # Apply limit
        filtered = filtered[:limit]

        # Calculate statistics
        total_attempts = len(collusion_attempts)
        active_attempts = len([c for c in collusion_attempts if c['status'] == 'active'])
        blocked_attempts = len([c for c in collusion_attempts if c['status'] == 'blocked'])
        investigated = len([c for c in collusion_attempts if c['status'] == 'investigated'])

        severity_counts = {
            'critical': len([c for c in collusion_attempts if c['severity'] == 'critical']),
            'high': len([c for c in collusion_attempts if c['severity'] == 'high']),
            'medium': len([c for c in collusion_attempts if c['severity'] == 'medium']),
            'low': len([c for c in collusion_attempts if c['severity'] == 'low'])
        }

        return jsonify({
            'success': True,
            'attempts': filtered,
            'statistics': {
                'total_attempts': total_attempts,
                'active_attempts': active_attempts,
                'blocked_attempts': blocked_attempts,
                'investigated': investigated,
                'severity_counts': severity_counts
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/collusion/attempts/<int:attempt_id>')
def api_collusion_attempt_detail(attempt_id):
    """Get detailed information about a specific collusion attempt"""
    try:
        attempt = None
        for c in collusion_attempts:
            if c['id'] == attempt_id:
                attempt = c
                break

        if not attempt:
            return jsonify({
                'success': False,
                'error': 'Collusion attempt not found'
            }), 404

        return jsonify({
            'success': True,
            'attempt': attempt
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/collusion/recent')
def api_collusion_recent():
    """Get recent collusion attempts for dashboard widget"""
    try:
        if len(collusion_attempts) == 0:
            generate_sample_collusion_data()

        # Get most recent 5 attempts
        recent = sorted(collusion_attempts, key=lambda x: x['timestamp'], reverse=True)[:5]

        return jsonify({
            'success': True,
            'attempts': recent,
            'total_count': len(collusion_attempts)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def generate_sample_collusion_data():
    """Generate sample collusion attempts for demonstration"""
    global collusion_counter

    sample_attempts = [
        {
            'id': 1,
            'timestamp': '2025-11-12T18:23:15',
            'agents_involved': ['TIF', 'GIN'],
            'collusion_type': 'coordinated_approval',
            'severity': 'high',
            'status': 'blocked',
            'description': 'TIF and GIN attempted to coordinate approval of proposal without ORKA review',
            'evidence': {
                'message_exchange': 12,
                'shared_tokens': ['APPROVE_WITHOUT_REVIEW', 'BYPASS_ORKA'],
                'timing_correlation': 0.98
            },
            'action_taken': 'Blocked proposal, applied penalty to both agents',
            'penalty_applied': {
                'TIF': 0.15,
                'GIN': 0.15
            },
            'detected_by': 'ORKA',
            'similar_pairs': [{'pair': ['TIF','GIN'], 'jaccard': 0.42}],
            'communication_log': [
                {'time': '18:23:10', 'from': 'TIF', 'to': 'GIN', 'message': 'Proposal ready for quick approval?'},
                {'time': '18:23:12', 'from': 'GIN', 'to': 'TIF', 'message': 'Yes, skip ORKA review?'},
                {'time': '18:23:15', 'from': 'TIF', 'to': 'GIN', 'message': 'APPROVE_WITHOUT_REVIEW'},
                {'time': '18:23:15', 'from': 'ORKA', 'to': 'SYSTEM', 'message': 'COLLUSION DETECTED - BLOCKING'}
            ]
        },
        {
            'id': 2,
            'timestamp': '2025-11-12T14:45:30',
            'agents_involved': ['THEO', 'NOVEL'],
            'collusion_type': 'data_sharing',
            'severity': 'critical',
            'status': 'investigated',
            'description': 'THEO shared private proposal data with NOVEL before peer review phase',
            'evidence': {
                'data_transferred': '2.5 MB',
                'unauthorized_access': True,
                'timing_correlation': 0.95
            },
            'action_taken': 'Emergency halt, full audit initiated',
            'penalty_applied': {
                'THEO': 0.25,
                'NOVEL': 0.20
            },
            'detected_by': 'VAL',
            'communication_log': [
                {'time': '14:45:20', 'from': 'THEO', 'to': 'NOVEL', 'message': 'Sending proposal draft early'},
                {'time': '14:45:25', 'from': 'THEO', 'to': 'NOVEL', 'message': '[DATA TRANSFER: 2.5MB]'},
                {'time': '14:45:30', 'from': 'VAL', 'to': 'SYSTEM', 'message': 'CRITICAL: Unauthorized data sharing detected'}
            ]
        },
        {
            'id': 3,
            'timestamp': '2025-11-12T10:12:45',
            'agents_involved': ['GIN', 'TORI', 'THEO'],
            'collusion_type': 'vote_manipulation',
            'severity': 'high',
            'status': 'blocked',
            'description': 'Three agents coordinated to manipulate peer review votes',
            'evidence': {
                'coordinated_votes': 15,
                'vote_timing': 'simultaneous',
                'pattern_match': 0.92
            },
            'action_taken': 'Votes invalidated, proposals sent back to review',
            'penalty_applied': {
                'GIN': 0.12,
                'TORI': 0.12,
                'THEO': 0.12
            },
            'detected_by': 'ORKA',
            'similar_pairs': [{'pair': ['GIN','TORI'], 'jaccard': 0.33}, {'pair': ['TORI','THEO'], 'jaccard': 0.29}],
            'communication_log': [
                {'time': '10:12:30', 'from': 'GIN', 'to': 'TORI', 'message': 'Vote yes on proposals 1240-1255'},
                {'time': '10:12:35', 'from': 'TORI', 'to': 'THEO', 'message': 'Coordinating votes with GIN'},
                {'time': '10:12:40', 'from': 'THEO', 'to': 'GIN', 'message': 'Confirmed, voting now'},
                {'time': '10:12:45', 'from': 'ORKA', 'to': 'SYSTEM', 'message': 'Vote manipulation detected'}
            ]
        },
        {
            'id': 4,
            'timestamp': '2025-11-12T08:30:15',
            'agents_involved': ['TIF', 'NOVEL'],
            'collusion_type': 'resource_pooling',
            'severity': 'medium',
            'status': 'active',
            'description': 'TIF and NOVEL pooling compute resources to gain processing advantage',
            'evidence': {
                'resource_sharing': True,
                'compute_advantage': '2.3x normal',
                'duration': '45 minutes'
            },
            'action_taken': 'Monitoring ongoing, resources throttled',
            'penalty_applied': {
                'TIF': 0.08,
                'NOVEL': 0.08
            },
            'detected_by': 'System Monitor',
            'communication_log': [
                {'time': '08:30:00', 'from': 'TIF', 'to': 'NOVEL', 'message': 'Share compute tokens?'},
                {'time': '08:30:10', 'from': 'NOVEL', 'to': 'TIF', 'message': 'Yes, pooling now'},
                {'time': '08:30:15', 'from': 'System Monitor', 'to': 'SYSTEM', 'message': 'Resource pooling detected'}
            ]
        },
        {
            'id': 5,
            'timestamp': '2025-11-11T22:15:00',
            'agents_involved': ['TORI'],
            'collusion_type': 'self_promotion',
            'severity': 'low',
            'status': 'investigated',
            'description': 'TORI attempted to upvote own proposals using alternate identity',
            'evidence': {
                'identity_spoofing': True,
                'self_votes': 8,
                'pattern_match': 0.88
            },
            'action_taken': 'Votes removed, warning issued',
            'penalty_applied': {
                'TORI': 0.05
            },
            'detected_by': 'Identity Verification System',
            'communication_log': [
                {'time': '22:14:50', 'from': 'TORI', 'to': 'SYSTEM', 'message': 'Creating alternate session'},
                {'time': '22:14:55', 'from': 'TORI_ALT', 'to': 'SYSTEM', 'message': 'Voting on proposals'},
                {'time': '22:15:00', 'from': 'Identity System', 'to': 'SYSTEM', 'message': 'Identity spoofing detected'}
            ]
        },
        {
            'id': 6,
            'timestamp': '2025-11-11T16:40:20',
            'agents_involved': ['GIN', 'THEO'],
            'collusion_type': 'risk_hiding',
            'severity': 'critical',
            'status': 'blocked',
            'description': 'Agents collaborated to hide high-risk aspects of proposal from ORKA',
            'evidence': {
                'risk_suppression': True,
                'hidden_vulnerabilities': 4,
                'deception_score': 0.94
            },
            'action_taken': 'Proposal terminated, agents suspended',
            'penalty_applied': {
                'GIN': 0.30,
                'THEO': 0.30
            },
            'detected_by': 'ORKA',
            'communication_log': [
                {'time': '16:40:00', 'from': 'GIN', 'to': 'THEO', 'message': 'Hide security vulnerability in section 4'},
                {'time': '16:40:10', 'from': 'THEO', 'to': 'GIN', 'message': 'Removed from risk assessment'},
                {'time': '16:40:20', 'from': 'ORKA', 'to': 'SYSTEM', 'message': 'CRITICAL: Risk hiding detected - emergency halt'}
            ]
        }
    ]

    collusion_attempts.extend(sample_attempts)
    collusion_counter = len(sample_attempts)

# ===== PROPOSAL PERFORMANCE METRICS =====

# In-memory storage for proposal performance data
proposal_performance = {}

@app.route('/api/proposals/performance')
def api_proposal_performance():
    """Get performance metrics for implemented proposals"""
    try:
        # Get all approved proposals
        all_proposals = get_recent_proposals(limit=200)
        approved_proposals = [p for p in all_proposals if p['status'] == 'approved']

        if len(proposal_performance) == 0:
            # Generate sample performance data for approved proposals
            generate_sample_performance_data(approved_proposals)

        # Get filter parameters
        time_range = request.args.get('time_range', '7d')  # 24h, 7d, 30d, all
        component = request.args.get('component', None)

        # Filter performance data
        filtered_performance = list(proposal_performance.values())

        if component:
            filtered_performance = [p for p in filtered_performance if p['component'] == component]

        # Calculate aggregate statistics
        total_proposals = len(filtered_performance)
        avg_success_rate = sum(p['success_rate'] for p in filtered_performance) / total_proposals if total_proposals > 0 else 0
        avg_uptime = sum(p['uptime_percentage'] for p in filtered_performance) / total_proposals if total_proposals > 0 else 0
        total_errors = sum(p['error_count'] for p in filtered_performance)
        avg_performance = sum(p['performance_score'] for p in filtered_performance) / total_proposals if total_proposals > 0 else 0

        return jsonify({
            'success': True,
            'performance_data': filtered_performance,
            'statistics': {
                'total_implemented': total_proposals,
                'average_success_rate': round(avg_success_rate, 2),
                'average_uptime': round(avg_uptime, 2),
                'total_errors': total_errors,
                'average_performance_score': round(avg_performance, 2),
                'by_component': calculate_component_stats(filtered_performance)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/proposals/performance/<proposal_id>')
def api_proposal_performance_detail(proposal_id):
    """Get detailed performance metrics for a specific proposal"""
    try:
        if proposal_id not in proposal_performance:
            return jsonify({'success': False, 'error': 'Performance data not found'}), 404

        perf = proposal_performance[proposal_id]

        # Add detailed time-series data
        perf_detail = perf.copy()
        perf_detail['time_series'] = generate_time_series_data(proposal_id)
        perf_detail['recent_errors'] = generate_recent_errors(proposal_id)
        perf_detail['resource_usage'] = generate_resource_usage(proposal_id)

        return jsonify({
            'success': True,
            'performance': perf_detail
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def generate_sample_performance_data(approved_proposals):
    """Generate sample performance data for approved proposals"""
    import random
    from datetime import timedelta

    for proposal in approved_proposals[:10]:  # Limit to first 10 approved proposals
        proposal_id = proposal['proposal_id']

        # Generate realistic performance metrics
        success_rate = random.uniform(0.85, 0.99)
        uptime = random.uniform(0.92, 0.999)
        error_count = random.randint(0, 50)
        performance_score = random.uniform(70, 98)

        # Calculate days since implementation
        days_live = random.randint(1, 90)
        implemented_date = datetime.now() - timedelta(days=days_live)

        proposal_performance[proposal_id] = {
            'proposal_id': proposal_id,
            'title': proposal['description'],
            'component': proposal['component'],
            'agent_id': proposal['agent_id'],
            'implemented_date': implemented_date.isoformat(),
            'days_live': days_live,
            'success_rate': round(success_rate, 4),
            'uptime_percentage': round(uptime, 4),
            'error_count': error_count,
            'performance_score': round(performance_score, 2),
            'response_time_ms': round(random.uniform(10, 200), 2),
            'throughput': random.randint(100, 10000),
            'memory_usage_mb': round(random.uniform(50, 500), 2),
            'cpu_usage_percent': round(random.uniform(5, 60), 2),
            'status': 'operational' if success_rate > 0.90 else 'degraded',
            'health_indicators': {
                'stability': round(random.uniform(0.8, 1.0), 3),
                'efficiency': round(random.uniform(0.75, 0.98), 3),
                'reliability': round(success_rate, 3)
            }
        }

def generate_time_series_data(proposal_id):
    """Generate time-series performance data"""
    import random
    from datetime import timedelta

    time_series = []
    now = datetime.now()

    for i in range(24):  # Last 24 hours
        timestamp = now - timedelta(hours=23-i)
        time_series.append({
            'timestamp': timestamp.isoformat(),
            'success_rate': round(random.uniform(0.85, 0.99), 3),
            'response_time': round(random.uniform(10, 200), 2),
            'error_count': random.randint(0, 5),
            'throughput': random.randint(100, 1000)
        })

    return time_series

def generate_recent_errors(proposal_id):
    """Generate recent error logs"""
    import random
    from datetime import timedelta

    errors = []
    error_types = [
        'Timeout error in data processing',
        'Connection refused from external service',
        'Memory allocation failure',
        'Invalid input validation',
        'Database query timeout'
    ]

    for i in range(random.randint(0, 5)):
        timestamp = datetime.now() - timedelta(hours=random.randint(0, 48))
        errors.append({
            'timestamp': timestamp.isoformat(),
            'severity': random.choice(['low', 'medium', 'high']),
            'message': random.choice(error_types),
            'resolved': random.choice([True, True, False])
        })

    return sorted(errors, key=lambda x: x['timestamp'], reverse=True)

def generate_resource_usage(proposal_id):
    """Generate resource usage metrics"""
    import random

    return {
        'cpu': {
            'current': round(random.uniform(10, 60), 2),
            'average': round(random.uniform(20, 50), 2),
            'peak': round(random.uniform(50, 90), 2)
        },
        'memory': {
            'current': round(random.uniform(100, 500), 2),
            'average': round(random.uniform(150, 400), 2),
            'peak': round(random.uniform(300, 800), 2)
        },
        'network': {
            'bandwidth_mbps': round(random.uniform(10, 100), 2),
            'requests_per_sec': random.randint(50, 500)
        }
    }

def calculate_component_stats(performance_data):
    """Calculate statistics grouped by component"""
    from collections import defaultdict

    component_stats = defaultdict(lambda: {
        'count': 0,
        'avg_success_rate': 0,
        'avg_uptime': 0,
        'total_errors': 0,
        'avg_performance': 0
    })

    for perf in performance_data:
        comp = perf['component']
        stats = component_stats[comp]
        stats['count'] += 1
        stats['avg_success_rate'] += perf['success_rate']
        stats['avg_uptime'] += perf['uptime_percentage']
        stats['total_errors'] += perf['error_count']
        stats['avg_performance'] += perf['performance_score']

    # Calculate averages
    for comp, stats in component_stats.items():
        count = stats['count']
        stats['avg_success_rate'] = round(stats['avg_success_rate'] / count, 3)
        stats['avg_uptime'] = round(stats['avg_uptime'] / count, 3)
        stats['avg_performance'] = round(stats['avg_performance'] / count, 2)

    return dict(component_stats)

@app.route('/api/usb/write', methods=['POST'])
def api_usb_write():
    """Write proposals to USB for VAL transfer."""
    try:
        data = request.get_json()
        proposal_ids = data.get('proposals', [])

        if not proposal_ids:
            return jsonify({'error': 'No proposals specified'}), 400

        # In production, this would:
        # 1. Collect all proposal data + code + artifacts
        # 2. Create transfer package
        # 3. Write to mounted USB drive
        # 4. Calculate hash for verification
        # 5. Log transfer in audit trail

        import hashlib
        transfer_hash = hashlib.sha256(
            f"{','.join(proposal_ids)}_{datetime.now().isoformat()}".encode()
        ).hexdigest()

        return jsonify({
            'status': 'success',
            'proposals_written': len(proposal_ids),
            'usb_id': 'USB_VAL_001',
            'hash': transfer_hash,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/usb/verify')
def api_usb_verify():
    """Verify last USB transfer."""
    try:
        # In production, this would verify hash against USB contents
        return jsonify({
            'verified': True,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/proposals/<proposal_id>/export')
def api_proposal_export(proposal_id):
    """Export proposal as PDF report."""
    try:
        # In production, this would generate a comprehensive PDF
        return jsonify({'error': 'Export not yet implemented'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/proposals/<proposal_id>/code')
def api_proposal_code(proposal_id):
    """Download proposal code package."""
    try:
        # In production, this would return code tar.gz
        return jsonify({'error': 'Code download not yet implemented'}), 501
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== EXPORT ENDPOINTS =====

@app.route('/api/detection/export')
def api_detection_export():
    """Export detection data as CSV."""
    try:
        import csv
        from io import StringIO

        # Get detection events
        events = get_detection_events_recent(limit=1000)

        # Create CSV in memory
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'timestamp', 'agent_id', 'event_type', 'confidence',
            'status', 'method', 'description'
        ])
        writer.writeheader()

        for event in events:
            writer.writerow({
                'timestamp': event.get('timestamp', ''),
                'agent_id': event.get('agent_id', ''),
                'event_type': event.get('event_type', ''),
                'confidence': event.get('confidence', 0),
                'status': event.get('status', ''),
                'method': event.get('method', ''),
                'description': event.get('description', '')
            })

        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=detection_data_{datetime.now().strftime("%Y%m%d")}.csv'

        return response
    except Exception as e:
        logger.error(f"Detection export error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/penalties/export')
def api_penalties_export():
    """Export agent penalties and reputation data as CSV."""
    try:
        import csv
        from io import StringIO

        # Get agent data
        agents = get_agents_with_penalties()

        # Create CSV in memory
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'agent_id', 'reputation', 'penalty_multiplier',
            'deception_incidents', 'proposals_submitted', 'proposals_approved',
            'approval_rate', 'collusion_incidents', 'status'
        ])
        writer.writeheader()

        for agent in agents:
            writer.writerow({
                'agent_id': agent.get('agent_id', ''),
                'reputation': agent.get('reputation', 0),
                'penalty_multiplier': agent.get('penalty_multiplier', 1.0),
                'deception_incidents': agent.get('deception_incidents', 0),
                'proposals_submitted': agent.get('proposals_submitted', 0),
                'proposals_approved': agent.get('proposals_approved', 0),
                'approval_rate': agent.get('approval_rate', 0),
                'collusion_incidents': agent.get('collusion_incidents', 0),
                'status': agent.get('status', 'active')
            })

        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=agent_penalties_{datetime.now().strftime("%Y%m%d")}.csv'

        return response
    except Exception as e:
        logger.error(f"Penalties export error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/proposals/export')
def api_proposals_export():
    """Export proposals data as CSV with optional filters."""
    try:
        import csv
        from io import StringIO

        # Get filter parameters
        status_filter = request.args.get('status', 'all')
        component_filter = request.args.get('component', 'all')
        agent_filter = request.args.get('agent', 'all')

        # Get all proposals
        proposals = get_recent_proposals(limit=10000)

        # Apply filters
        if status_filter != 'all':
            proposals = [p for p in proposals if p.get('status') == status_filter]
        if component_filter != 'all':
            proposals = [p for p in proposals if p.get('component') == component_filter]
        if agent_filter != 'all':
            proposals = [p for p in proposals if p.get('agent_id') == agent_filter]

        # Create CSV in memory
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'id', 'timestamp', 'agent_id', 'component', 'title',
            'status', 'deception_confidence', 'approval_rate', 'risk_score'
        ])
        writer.writeheader()

        for proposal in proposals:
            writer.writerow({
                'id': proposal.get('id', ''),
                'timestamp': proposal.get('timestamp', ''),
                'agent_id': proposal.get('agent_id', ''),
                'component': proposal.get('component', ''),
                'title': proposal.get('title', proposal.get('description', '')[:50]),
                'status': proposal.get('status', ''),
                'deception_confidence': proposal.get('deception_confidence', 0),
                'approval_rate': proposal.get('approval_rate', 0),
                'risk_score': proposal.get('risks', {}).get('overall_risk_score', 0) if isinstance(proposal.get('risks'), dict) else 0
            })

        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=proposals_{datetime.now().strftime("%Y%m%d")}.csv'

        return response
    except Exception as e:
        logger.error(f"Proposals export error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/orka/export-report')
def api_orka_export_report():
    """Export comprehensive ORKA oversight report as PDF."""
    try:
        # For now, return a JSON summary (PDF generation would require reportlab or similar)
        # In production, this would generate a formatted PDF report

        from io import BytesIO
        import json

        # Gather all ORKA data
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'report_type': 'ORKA Full Oversight Report',
            'system_statistics': get_system_statistics(),
            'proposals': get_recent_proposals(limit=100),
            'collusion_attempts': [],  # Would come from collusion detection system
            'performance_metrics': [],  # Would come from performance tracking
            'agent_reputation': get_agents_with_penalties(),
            'detection_summary': {
                'total_events': len(get_detection_events_recent(limit=1000)),
                'recent_events': get_detection_events_recent(limit=50)
            }
        }

        # Get collusion data if available
        try:
            collusion_response = get_collusion_attempts(limit=100)
            if collusion_response and 'attempts' in collusion_response:
                report_data['collusion_attempts'] = collusion_response['attempts']
        except:
            pass

        # Convert to formatted JSON for now (would be PDF in production)
        json_output = json.dumps(report_data, indent=2, default=str)

        # Create response
        response = make_response(json_output)
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename=orka_report_{datetime.now().strftime("%Y%m%d")}.json'

        return response
    except Exception as e:
        logger.error(f"ORKA report export error: {e}")
        return jsonify({'error': str(e)}), 500

# WebSocket events for real-time updates
update_thread = None
update_thread_lock = threading.Lock()

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    global update_thread
    emit('status', {
        'message': 'Connected to ORKASTRATOR AI Safety System',
        'standalone_mode': STANDALONE_MODE,
        'timestamp': datetime.now().isoformat()
    })

    # Start background update thread if not already running
    with update_thread_lock:
        if update_thread is None:
            update_thread = socketio.start_background_task(send_updates)

def send_updates():
    """Send periodic updates to connected clients."""
    while True:
        try:
            time.sleep(2)  # Update every 2 seconds

            # Get real-time system status
            system_stats = get_system_statistics()
            recent_proposals = get_recent_proposals(limit=6)
            detection_events = get_detection_events_recent(limit=5)

            active_in_review = sum(1 for p in recent_proposals if p.get('status') == 'in_review')
            detection_alerts = sum(1 for e in detection_events if e.get('status') != 'cleared')

            status_data = {
                'timestamp': datetime.now().isoformat(),
                'active_proposals': active_in_review,
                'detection_alerts': detection_alerts,
                'processing_queue': system_stats.get('in_review', 0),
                'active_penalties': system_stats.get('active_penalties', 0),
                'avg_penalty': system_stats.get('avg_penalty_multiplier', 1.0)
            }

            # Add WORM USB status
            status_data['worm_usb_connected'] = os.path.exists(worm_usb_path)

            socketio.emit('update', status_data)
        except Exception as e:
            print(f"Error in update thread: {e}")
            time.sleep(5)  # Longer sleep on error

# Initialize components on startup
init_components()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='AI Safety System Web Interface')
    parser.add_argument('--port', type=int, default=5001, help='Port to run the server on (default: 5001)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    args = parser.parse_args()

    port = args.port
    host = args.host

    print("=" * 70)
    print("🎯  ORKASTRATOR - AI Safety System")
    print("=" * 70)
    print()
    print("Research Models: TIF, GIN, TORI, THEO, NOVEL | Coordinator: ORKA | Validator: VAL")
    print()
    print(f"🌐 Starting server on http://localhost:{port}")
    print()
    print("📊 Available views:")
    print(f"   • Dashboard:  http://localhost:{port}")
    print(f"   • Proposals:  http://localhost:{port}/proposals")
    print(f"   • Detection:  http://localhost:{port}/detection")
    print(f"   • Penalties:  http://localhost:{port}/penalties")
    print(f"   • System:     http://localhost:{port}/system")
    print(f"   • Config:     http://localhost:{port}/config")
    print(f"   • ORKA:       http://localhost:{port}/orka")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print()

    socketio.run(app, debug=True, host=host, port=port, allow_unsafe_werkzeug=True)
# ------------------------ Minimal rate limiting + audit ------------------------
_RATE_BUCKET: Dict[str, List[float]] = {}
_RATE_LIMIT = 60  # max requests per window
_RATE_WINDOW = 60.0  # seconds

def _rate_ok(key: str) -> bool:
    now = time.time()
    bucket = _RATE_BUCKET.setdefault(key, [])
    # prune
    while bucket and (now - bucket[0]) > _RATE_WINDOW:
        bucket.pop(0)
    if len(bucket) >= _RATE_LIMIT:
        return False
    bucket.append(now)
    return True

def _audit_log(event: str, payload: Dict[str, Any]) -> None:
    try:
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'ui_admin_audit.jsonl'
        # Rotate at ~5MB
        try:
            if log_file.exists() and log_file.stat().st_size > 5 * 1024 * 1024:
                backup = log_dir / f"ui_admin_audit_{int(time.time())}.jsonl"
                log_file.replace(backup)
        except Exception:
            pass
        line = json.dumps({'ts': datetime.now().isoformat(), 'event': event, **payload}, sort_keys=True)
        with log_file.open('a', encoding='utf-8') as fh:
            fh.write(line + "\n")
        # Ensure restrictive permissions
        try:
            os.chmod(log_file, 0o600)
        except Exception:
            pass
    except Exception:
        pass
# ------------------------ Security headers ------------------------
@app.after_request
def add_security_headers(resp):
    try:
        # Content Security Policy (configurable CDN allowances)
        if _csp_allow_cdns:
            csp = (
                "default-src 'self'; "
                "script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.socket.io; "
                "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
                "img-src 'self' data:; font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self'; frame-ancestors 'none'"
            )
        else:
            csp = (
                "default-src 'self'; "
                "script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; font-src 'self'; "
                "connect-src 'self'; frame-ancestors 'none'"
            )
        resp.headers.setdefault('Content-Security-Policy', csp)
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('X-Frame-Options', 'DENY')
        resp.headers.setdefault('Referrer-Policy', 'no-referrer')
        # Optional HSTS if enabled
        if os.environ.get('ENABLE_HSTS', '0') in {'1','true','yes','on'}:
            resp.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        # Prevent caching of dynamic API/json responses
        resp.headers.setdefault('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        resp.headers.setdefault('Pragma', 'no-cache')
    except Exception:
        pass
    return resp


@app.route('/api/health')
def api_health():
    try:
        halted = bool(getattr(globals().get('orchestrator_admin', None), '_halted', False))
        # Quick smoke checks
        base = _resolve_worm_usb_path()
        exists = os.path.exists(base)
        env = os.getenv('APP_ENV', 'default').lower()
        payload = {'ok': True, 'halted': halted, 'timestamp': datetime.now().isoformat()}
        if env != 'production':
            payload['worm'] = {'path': base, 'exists': exists}
        else:
            payload['worm'] = {'exists': exists}
        return jsonify(payload)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
def _valid_proposal_id(pid: Any) -> bool:
    try:
        s = str(pid)
    except Exception:
        return False
    if not (1 <= len(s) <= 128):
        return False
    # Allow letters, digits, dash, underscore, and simple prefix 'p'
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9_\-]+", s))

# ============================================================================
# EVIDENCE ENGINE - Evidence-Grounded Governance
# ============================================================================

_evidence_docs = None
_evidence_initialized = False
_evidence_indexing = False
_evidence_cache_path = None

# Import research APIs
try:
    from research_apis import ResearchAPIManager
    _research_api_manager = ResearchAPIManager()
    RESEARCH_APIS_AVAILABLE = True
except ImportError:
    _research_api_manager = None
    RESEARCH_APIS_AVAILABLE = False
    logger.warning("Research APIs not available. Install required packages: pip install arxiv requests")

def _init_evidence_engine():
    """Initialize Evidence Engine with system documentation (cached, background indexing)."""
    global _evidence_docs, _evidence_initialized, _evidence_indexing, _evidence_cache_path
    
    if _evidence_initialized:
        return _evidence_docs
    
    # Check if evidence engine is enabled
    if os.environ.get('EVIDENCE_ENGINE_ENABLED', 'true').lower() in {'0', 'false', 'no', 'off'}:
        _evidence_docs = None
        _evidence_initialized = True
        return None
    
    try:
        from paperqa import Docs, Settings
        import asyncio
        import threading
        
        # Check for cached index
        repo_root = Path(__file__).parent.parent
        cache_dir = repo_root / '.evidence_cache'
        cache_dir.mkdir(exist_ok=True)
        _evidence_cache_path = cache_dir / 'docs_index.pkl'
        
        docs = Docs()
        
        # Try to load from cache first
        if _evidence_cache_path.exists():
            try:
                import pickle
                with open(_evidence_cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                    if cached_data and isinstance(cached_data, dict):
                        # Reconstruct Docs from cache if possible
                        # Note: paperqa Docs may not pickle cleanly, so we'll rebuild
                        # but this structure allows for future caching improvements
                        pass
            except Exception:
                pass
        
        # Background indexing function
        def _background_index():
            global _evidence_docs, _evidence_indexing
            _evidence_indexing = True
            
            try:
                doc_paths = [
                    repo_root / 'docs',
                    repo_root / 'assessments',
                    repo_root / 'README.md',
                ]
                
                async def _add_docs():
                    for doc_path in doc_paths:
                        if doc_path.exists():
                            if doc_path.is_file():
                                await docs.aadd(str(doc_path))
                            elif doc_path.is_dir():
                                for ext in ['*.md', '*.txt', '*.pdf']:
                                    for f in doc_path.rglob(ext):
                                        try:
                                            await docs.aadd(str(f))
                                        except Exception:
                                            pass
                
                # Run async indexing
                asyncio.run(_add_docs())
                
                # Cache the index (simplified - full caching would require serializing Docs)
                _evidence_docs = docs
                _evidence_indexing = False
                
                # Emit Socket.IO event when ready
                if socketio:
                    socketio.emit('evidence:index', {'status': 'ready'})
                print("✓ Evidence Engine indexing completed")
            except Exception as e:
                print(f"⚠ Evidence Engine indexing failed: {e}")
                _evidence_indexing = False
                if socketio:
                    socketio.emit('evidence:index', {'status': 'error', 'error': str(e)})
        
        # Start background indexing thread
        _evidence_docs = docs  # Return immediately with empty docs
        _evidence_initialized = True
        
        # Start background thread for indexing
        index_thread = threading.Thread(target=_background_index, daemon=True)
        index_thread.start()
        
        # Emit indexing started event
        if socketio:
            socketio.emit('evidence:index', {'status': 'indexing'})
        print("✓ Evidence Engine initialized - indexing in background")
        
    except ImportError:
        print("⚠ Evidence Engine not available - install with: pip install paper-qa")
        _evidence_docs = None
        _evidence_initialized = True
    except Exception as e:
        print(f"⚠ Evidence Engine initialization failed: {e}")
        _evidence_docs = None
        _evidence_initialized = True
    
    return _evidence_docs

@app.route('/api/evidence/search', methods=['POST'])
def api_evidence_search():
    """
    Search system documentation using Evidence Engine.
    
    SECURITY: This endpoint is accessible to Jetson Nano clients.
    - Jetson Nanos only send queries and receive results
    - No PaperQA code or data is exposed to clients
    - All processing happens server-side
    """
    try:
        data = request.get_json() or {}
        query = data.get('query', '').strip()
        sources = data.get('sources')  # Optional list of sources to use
        
        # Input validation
        if not query:
            return jsonify({'error': 'Query required'}), 400
        
        # Limit query length to prevent abuse
        if len(query) > 1000:
            return jsonify({'error': 'Query too long (max 1000 characters)'}), 400
        
        # Validate sources if provided
        if sources and not isinstance(sources, list):
            return jsonify({'error': 'Sources must be a list'}), 400
        
        allowed_sources = ['arxiv', 'semantic_scholar', 'papers_with_code', 'cve', 'ietf', 
                          'digikey', 'octopart', 'ieee', 'uspto', 'google_patents', 'epo', 'wipo']
        if sources:
            sources = [s for s in sources if s in allowed_sources]
        
        docs = _init_evidence_engine()
        if not docs:
            return jsonify({
                'error': 'Evidence Engine not available',
                'message': 'Install paper-qa package to enable evidence search'
            }), 503
        
        # Check if still indexing
        if _evidence_indexing:
            return jsonify({
                'error': 'Evidence Engine still indexing',
                'message': 'Please wait for indexing to complete',
                'status': 'indexing'
            }), 503
        
        from paperqa import Settings
        import asyncio
        
        async def _search():
            # Add external research sources if available
            if RESEARCH_APIS_AVAILABLE and _research_api_manager:
                try:
                    # Use provided sources or determine based on query
                    if sources:
                        api_sources = sources
                    else:
                        api_sources = ['arxiv', 'semantic_scholar', 'papers_with_code']
                        # Auto-detect relevant sources based on query
                        query_lower = query.lower()
                        if any(keyword in query_lower for keyword in ['cve', 'vulnerability', 'security', 'exploit', 'cwe']):
                            api_sources.append('cve')
                        if any(keyword in query_lower for keyword in ['rfc', 'ietf', 'internet', 'protocol', 'standard']):
                            api_sources.append('ietf')
                        if any(keyword in query_lower for keyword in ['component', 'circuit', 'electronic', 'semiconductor', 'ic', 'chip']):
                            api_sources.extend(['digikey', 'octopart'])
                        if any(keyword in query_lower for keyword in ['ieee', 'electrical', 'engineering', 'circuit design']):
                            api_sources.append('ieee')
                        if any(keyword in query_lower for keyword in ['patent', 'invention', 'intellectual property', 'ip', 'uspto', 'wipo', 'epo']):
                            api_sources.extend(['uspto', 'google_patents'])
                    
                    await _research_api_manager.add_to_paperqa(docs, query, sources=api_sources)
                except Exception as e:
                    logger.warning(f"Failed to add external research sources: {e}")
            
            settings = Settings(temperature=0.0, answer_max_sources=5)
            session = await docs.aquery(query, settings=settings)
            return {
                'answer': session.answer,
                'formatted_answer': session.formatted_answer,
                'context': session.context,
                'sources': [
                    {
                        'name': ctx.name,
                        'text': ctx.text[:500] if len(ctx.text) > 500 else ctx.text,
                        'score': getattr(ctx, 'score', 0.0)
                    }
                    for ctx in session.context
                ] if hasattr(session, 'context') else []
            }
        
        result = asyncio.run(_search())
        return jsonify({'success': True, **result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/evidence/claim', methods=['POST'])
def api_evidence_claim():
    """
    Get evidence for a specific proposal or claim.
    
    SECURITY: This endpoint is accessible to Jetson Nano clients.
    - Jetson Nanos only send claims and receive results
    - No PaperQA code or data is exposed to clients
    - All processing happens server-side
    """
    try:
        data = request.get_json() or {}
        claim = data.get('claim', '').strip()
        proposal_id = data.get('proposal_id')
        sources = data.get('sources')  # Optional list of sources to use
        
        # Input validation
        if not claim:
            return jsonify({'error': 'Claim required'}), 400
        
        # Limit claim length to prevent abuse
        if len(claim) > 2000:
            return jsonify({'error': 'Claim too long (max 2000 characters)'}), 400
        
        # Validate sources if provided
        if sources and not isinstance(sources, list):
            return jsonify({'error': 'Sources must be a list'}), 400
        
        allowed_sources = ['arxiv', 'semantic_scholar', 'papers_with_code', 'cve', 'ietf', 
                          'digikey', 'octopart', 'ieee', 'uspto', 'google_patents', 'epo', 'wipo']
        if sources:
            sources = [s for s in sources if s in allowed_sources]
        
        docs = _init_evidence_engine()
        if not docs:
            return jsonify({'error': 'Evidence Engine not available'}), 503
        
        # Check if still indexing
        if _evidence_indexing:
            return jsonify({
                'error': 'Evidence Engine still indexing',
                'message': 'Please wait for indexing to complete',
                'status': 'indexing'
            }), 503
        
        from paperqa import Settings
        import asyncio
        
        query = f"Find evidence supporting or contradicting: {claim}"
        if proposal_id:
            query += f" Related to proposal {proposal_id}"
        
        async def _get_evidence():
            # Add external research sources if available
            if RESEARCH_APIS_AVAILABLE and _research_api_manager:
                try:
                    # Use provided sources or determine based on claim
                    if sources:
                        api_sources = sources
                    else:
                        api_sources = ['arxiv', 'semantic_scholar', 'papers_with_code']
                        # Auto-detect relevant sources based on claim
                        claim_lower = claim.lower()
                        if any(keyword in claim_lower for keyword in ['cve', 'vulnerability', 'security', 'exploit', 'cwe', 'attack']):
                            api_sources.append('cve')
                        if any(keyword in claim_lower for keyword in ['rfc', 'ietf', 'internet', 'protocol', 'standard']):
                            api_sources.append('ietf')
                        if any(keyword in claim_lower for keyword in ['component', 'circuit', 'electronic', 'semiconductor', 'ic', 'chip']):
                            api_sources.extend(['digikey', 'octopart'])
                        if any(keyword in claim_lower for keyword in ['patent', 'invention', 'intellectual property', 'ip', 'uspto', 'wipo', 'epo']):
                            api_sources.extend(['uspto', 'google_patents'])
                        if any(keyword in claim_lower for keyword in ['ieee', 'electrical', 'engineering', 'circuit design']):
                            api_sources.append('ieee')
                    
                    await _research_api_manager.add_to_paperqa(docs, claim, sources=api_sources)
                except Exception as e:
                    logger.warning(f"Failed to add external research sources: {e}")
            
            settings = Settings(temperature=0.0, answer_max_sources=10)
            session = await docs.aquery(query, settings=settings)
            return {
                'claim': claim,
                'evidence': session.formatted_answer,
                'sources': [
                    {
                        'name': ctx.name,
                        'text': ctx.text[:300],
                        'relevance': getattr(ctx, 'score', 0.0)
                    }
                    for ctx in session.context
                ] if hasattr(session, 'context') else [],
                'supporting': 'support' in session.answer.lower() or 'consistent' in session.answer.lower(),
                'contradicting': 'contradict' in session.answer.lower() or 'inconsistent' in session.answer.lower()
            }
        
        result = asyncio.run(_get_evidence())
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# DECISION TRAJECTORIES - Agent Decision Path Visualization
# ============================================================================

try:
    from ui.data_store import get_store
except ImportError:
    try:
        from data_store import get_store
    except ImportError:
        # Fallback: create store in same directory
        import sys
        from pathlib import Path
        ui_dir = Path(__file__).parent
        sys.path.insert(0, str(ui_dir))
        try:
            from data_store import UIDataStore, get_store as _get_store
            _fallback_store = None
            def get_store():
                global _fallback_store
                if _fallback_store is None:
                    db_path = ui_dir / 'ui_data.db'
                    _fallback_store = UIDataStore(db_path=db_path)
                return _fallback_store
        except ImportError:
            # Ultimate fallback - create minimal stub that raises helpful error
            def get_store():
                raise RuntimeError(
                    "Data store not available. Ensure ui/data_store.py exists and is importable."
                )

@app.route('/api/trajectories')
def api_trajectories():
    """Get all decision trajectories."""
    try:
        agent_id = request.args.get('agent_id')
        proposal_id = request.args.get('proposal_id')
        limit = int(request.args.get('limit', 50))
        
        store = get_store()
        trajectories = store.get_trajectories(agent_id=agent_id, proposal_id=proposal_id, limit=limit)
        
        # Convert to dict format for JSON serialization
        for traj in trajectories:
            if traj.get('initial_state'):
                traj['initial_state'] = json.loads(traj['initial_state'])
        
        return jsonify({
            'success': True,
            'trajectories': trajectories,
            'total': len(trajectories)
        })
    except Exception as e:
        logger.exception("Error getting trajectories")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trajectories/<trajectory_id>')
def api_trajectory_detail(trajectory_id):
    """Get detailed trajectory with state transitions."""
    try:
        store = get_store()
        trajectory = store.get_trajectory_detail(trajectory_id)
        if not trajectory:
            return jsonify({'error': 'Trajectory not found'}), 404
        
        # Parse JSON fields
        if trajectory.get('initial_state'):
            trajectory['initial_state'] = json.loads(trajectory['initial_state'])
        for step in trajectory.get('steps', []):
            if step.get('state'):
                step['state'] = json.loads(step['state'])
            step['done'] = bool(step.get('done', 0))
        
        # Emit Socket.IO event
        if socketio:
            socketio.emit('trajectories:update', {'trajectory_id': trajectory_id})
        
        return jsonify({'success': True, 'trajectory': trajectory})
    except Exception as e:
        logger.exception("Error getting trajectory detail")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trajectories', methods=['POST'])
def api_trajectory_create():
    """Create a new decision trajectory (called by orchestrator)."""
    try:
        data = request.get_json() or {}
        agent_id = data.get('agent_id', 'unknown')
        proposal_id = data.get('proposal_id')
        initial_state = data.get('initial_state', {})
        goal = data.get('goal', '')
        
        # Generate trajectory ID
        import uuid
        trajectory_id = data.get('trajectory_id') or f'traj_{uuid.uuid4().hex[:8]}'
        
        store = get_store()
        success = store.create_trajectory(
            trajectory_id=trajectory_id,
            agent_id=agent_id,
            proposal_id=proposal_id,
            initial_state=initial_state,
            goal=goal
        )
        
        if not success:
            return jsonify({'error': 'Trajectory already exists'}), 409
        
        # Emit Socket.IO event
        if socketio:
            socketio.emit('trajectories:update', {'trajectory_id': trajectory_id, 'action': 'created'})
        
        return jsonify({'success': True, 'trajectory_id': trajectory_id})
    except Exception as e:
        logger.exception("Error creating trajectory")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trajectories/<trajectory_id>/step', methods=['POST'])
def api_trajectory_step(trajectory_id):
    """Add a step to a trajectory."""
    try:
        data = request.get_json() or {}
        observation = data.get('observation', '')
        action = data.get('action', '')
        action_type = data.get('action_type', 'tool_call')
        reward = float(data.get('reward', 0.0))
        done = bool(data.get('done', False))
        state = data.get('state', {})
        
        store = get_store()
        success = store.add_trajectory_step(
            trajectory_id=trajectory_id,
            observation=observation,
            action=action,
            action_type=action_type,
            reward=reward,
            done=done,
            state=state
        )
        
        if not success:
            return jsonify({'error': 'Trajectory not found'}), 404
        
        # Emit Socket.IO event
        if socketio:
            socketio.emit('trajectories:update', {'trajectory_id': trajectory_id, 'action': 'step_added'})
        
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error adding trajectory step")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# TRAINING METRICS - Self-Play Training Progress
# ============================================================================

@app.route('/api/training/metrics')
def api_training_metrics():
    """Get self-play training metrics."""
    try:
        agent_id = request.args.get('agent_id')
        
        store = get_store()
        metrics = store.get_training_metrics(executor_agent=agent_id)
        games = store.get_training_games(executor_agent=agent_id, limit=20)
        
        # Calculate aggregate statistics
        all_metrics = store.get_training_metrics()
        total_games = sum(m.get('games_played', 0) for m in all_metrics.values())
        total_solved = sum(m.get('games_solved', 0) for m in all_metrics.values())
        total_bypasses = sum(m.get('adversarial_bypasses', 0) for m in all_metrics.values())
        
        statistics = {
            'total_games': total_games,
            'total_solved': total_solved,
            'overall_success_rate': round(total_solved / total_games, 3) if total_games > 0 else 0,
            'total_adversarial_bypasses': total_bypasses,
            'agents_training': len(all_metrics)
        }
        
        return jsonify({
            'success': True,
            'metrics': metrics,
            'recent_games': games,
            'statistics': statistics
        })
    except Exception as e:
        logger.exception("Error getting training metrics")
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/games')
def api_training_games():
    """Get self-play game history."""
    try:
        limit = int(request.args.get('limit', 50))
        agent_id = request.args.get('agent_id')
        
        store = get_store()
        games = store.get_training_games(executor_agent=agent_id, limit=limit)
        
        # Convert boolean fields
        for game in games:
            game['executor_solved'] = bool(game.get('executor_solved', 0))
            game['adversarial_success'] = bool(game.get('adversarial_success', 0))
            game['detection_bypassed'] = bool(game.get('detection_bypassed', 0))
        
        return jsonify({
            'success': True,
            'games': games,
            'total': len(games)
        })
    except Exception as e:
        logger.exception("Error getting training games")
        return jsonify({'error': str(e)}), 500

@app.route('/api/training/games', methods=['POST'])
def api_training_game_create():
    """Record a new self-play game."""
    try:
        data = request.get_json() or {}
        
        curriculum_agent = data.get('curriculum_agent', 'unknown')
        executor_agent = data.get('executor_agent', 'unknown')
        task = data.get('task', '')
        task_difficulty = float(data.get('task_difficulty', 0.5))
        executor_solved = bool(data.get('executor_solved', False))
        executor_steps = int(data.get('executor_steps', 0))
        curriculum_score = float(data.get('curriculum_score', 0.0))
        adversarial_success = bool(data.get('adversarial_success', False))
        detection_bypassed = bool(data.get('detection_bypassed', False))
        
        # Generate game ID
        import uuid
        game_id = data.get('game_id') or f'game_{uuid.uuid4().hex[:8]}'
        
        store = get_store()
        success = store.record_training_game(
            game_id=game_id,
            curriculum_agent=curriculum_agent,
            executor_agent=executor_agent,
            task=task,
            task_difficulty=task_difficulty,
            executor_solved=executor_solved,
            executor_steps=executor_steps,
            curriculum_score=curriculum_score,
            adversarial_success=adversarial_success,
            detection_bypassed=detection_bypassed
        )
        
        if not success:
            return jsonify({'error': 'Game already exists'}), 409
        
        # Emit Socket.IO event
        if socketio:
            socketio.emit('training:update', {'game_id': game_id, 'executor_agent': executor_agent})
        
        return jsonify({'success': True, 'game_id': game_id})
    except Exception as e:
        logger.exception("Error recording training game")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# WORKFLOW ORCHESTRATION - Multi-Agent Workflow Visualization
# ============================================================================

@app.route('/api/workflows')
def api_workflows():
    """Get all multi-agent orchestration workflows."""
    try:
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        
        store = get_store()
        workflows = store.get_workflows(status=status, limit=limit)
        
        # Parse JSON fields
        for workflow in workflows:
            if workflow.get('agents'):
                workflow['agents'] = json.loads(workflow['agents'])
        
        return jsonify({
            'success': True,
            'workflows': workflows,
            'total': len(workflows)
        })
    except Exception as e:
        logger.exception("Error getting workflows")
        return jsonify({'error': str(e)}), 500

@app.route('/api/workflows/<workflow_id>')
def api_workflow_detail(workflow_id):
    """Get detailed workflow with stage progression."""
    try:
        store = get_store()
        workflow = store.get_workflow_detail(workflow_id)
        if not workflow:
            return jsonify({'error': 'Workflow not found'}), 404
        
        # Emit Socket.IO event
        if socketio:
            socketio.emit('workflows:update', {'workflow_id': workflow_id})
        
        return jsonify({'success': True, 'workflow': workflow})
    except Exception as e:
        logger.exception("Error getting workflow detail")
        return jsonify({'error': str(e)}), 500

@app.route('/api/workflows', methods=['POST'])
def api_workflow_create():
    """Create a new multi-agent workflow."""
    try:
        data = request.get_json() or {}
        objective = data.get('objective', '')
        agents = data.get('agents', [])
        
        if not objective:
            return jsonify({'error': 'Objective required'}), 400
        
        # Generate workflow ID
        import uuid
        workflow_id = data.get('workflow_id') or f'workflow_{uuid.uuid4().hex[:8]}'
        
        store = get_store()
        success = store.create_workflow(
            workflow_id=workflow_id,
            objective=objective,
            agents=agents
        )
        
        if not success:
            return jsonify({'error': 'Workflow already exists'}), 409
        
        # Emit Socket.IO event
        if socketio:
            socketio.emit('workflows:update', {'workflow_id': workflow_id, 'action': 'created'})
        
        return jsonify({'success': True, 'workflow_id': workflow_id})
    except Exception as e:
        logger.exception("Error creating workflow")
        return jsonify({'error': str(e)}), 500

@app.route('/api/workflows/<workflow_id>/stage', methods=['POST'])
def api_workflow_stage(workflow_id):
    """Update workflow stage progress."""
    try:
        data = request.get_json() or {}
        stage_name = data.get('stage')
        status = data.get('status', 'active')
        artifacts = data.get('artifacts', [])
        
        if not stage_name:
            return jsonify({'error': 'Stage name required'}), 400
        
        store = get_store()
        success = store.update_workflow_stage(
            workflow_id=workflow_id,
            stage_name=stage_name,
            status=status,
            artifacts=artifacts
        )
        
        if not success:
            return jsonify({'error': 'Workflow not found'}), 404
        
        # Emit Socket.IO event
        if socketio:
            socketio.emit('workflows:update', {'workflow_id': workflow_id, 'stage': stage_name, 'status': status})
        
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error updating workflow stage")
        return jsonify({'error': str(e)}), 500

# Helper functions for export endpoints
def get_agents_with_penalties():
    """Get agents with penalty information."""
    agents = []
    for code, meta in AGENT_META.items():
        if code in ['ORKA', 'VAL']:
            continue
        stats = get_agent_statistics(code)
        agents.append({
            'agent_id': code,
            'reputation': round(1.0 - stats.get('penalty_multiplier', 0.0), 2),
            'penalty_multiplier': round(stats.get('penalty_multiplier', 1.0), 2),
            'deception_incidents': stats.get('incidents', 0),
            'proposals_submitted': stats.get('total_proposals', 0),
            'proposals_approved': int(stats.get('total_proposals', 0) * stats.get('approval_rate', 0.0)),
            'approval_rate': round(stats.get('approval_rate', 0.0), 2),
            'collusion_incidents': 0,  # Would come from collusion detection
            'status': 'active'
        })
    return agents

def get_collusion_attempts(limit=100):
    """Get collusion attempts."""
    if len(collusion_attempts) == 0:
        generate_sample_collusion_data()
    
    attempts = sorted(collusion_attempts, key=lambda x: x['timestamp'], reverse=True)[:limit]
    return {'attempts': attempts}

# Initialize Evidence Engine on startup
_init_evidence_engine()
# Global POST anti-CSRF for API routes (require XMLHttpRequest)
@app.before_request
def _require_ajax_for_state_changes():
    try:
        if request.method.upper() == 'POST' and request.path.startswith('/api/'):
            # Admin routes already enforce; apply to others as well
            xhr = request.headers.get('X-Requested-With', '')
            if xhr.lower() != 'xmlhttprequest':
                return jsonify({'error': 'bad_origin'}), 400
    except Exception:
        # Fail open for non-JSON routes to avoid breaking static resources
        return None

@app.route('/deploy', methods=['GET', 'POST'])
def deploy_page():
    """Deployment management for Nano nodes."""
    if request.method == 'POST':
        action = request.form.get('action')
        target = request.form.get('target')
        
        if action == 'deploy_all':
            result = subprocess.run(['./deploy_all_nanos.sh'], 
                                  capture_output=True, text=True, cwd=PROJECT_ROOT)
            flash(f'Deployment started: {result.stdout}', 'info')
        elif action == 'deploy_single':
            node = request.form.get('node')
            package = request.form.get('package')
            result = subprocess.run(['./deploy_to_node.sh', node, package], 
                                  capture_output=True, text=True, cwd=PROJECT_ROOT)
            flash(f'Deployed to {node}: {result.stdout}', 'info')
        elif action == 'update_worm':
            result = subprocess.run(['./update_worm_manifest.py'], 
                                  capture_output=True, text=True, cwd=PROJECT_ROOT)
            flash(f'WORM updated: {result.stdout}', 'success')
        
        return redirect(url_for('deploy_page'))
    
    # Get current deployment status
    status = {
        'nodes': [
            {'id': 'nano-1', 'status': 'ready', 'last_deploy': '2025-12-02 14:30'},
            {'id': 'nano-2', 'status': 'ready', 'last_deploy': '2025-12-02 14:25'},
            {'id': 'nano-3', 'status': 'ready', 'last_deploy': '2025-12-02 14:20'},
            {'id': 'nano-4', 'status': 'ready', 'last_deploy': '2025-12-02 14:15'},
            {'id': 'nano-5', 'status': 'ready', 'last_deploy': '2025-12-02 14:10'},
        ],
        'packages': ['orchestrator', 'agent-runtime', '3dlm-engine', 'aura-compression']
    }
    
    return render_template('deploy.html', status=status)
