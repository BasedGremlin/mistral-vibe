#!/usr/bin/env python3
"""
WORDLIB -- ETHER AI Flask Application
All modules: Dashboard, Chat, Library, Knowledge Base,
             Research, Strategy Notes, Recovery Guide
"""

import os, sys, json, time, hashlib, re
from pathlib import Path
from datetime import datetime

from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, flash, session, abort)
from flask_sqlalchemy import SQLAlchemy

# ── RAG (optional) ─────────────────────────────────────────────────────────
# rag_manager.py lives in src/. Resolve via core.paths (single source of truth),
# with a guarded fallback so the hub launches from any cwd.
try:
    from core.paths import PATHS as _PATHS
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.paths import PATHS as _PATHS
_SRC_DIR = _PATHS.src
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

try:
    from rag_manager import USBRAGManager as _RAGClass
    _RAG_SUPPORTED = True
except ImportError:
    _RAG_SUPPORTED = False

# ── Self-editor (self-modification engine) ──────────────────────────────────
try:
    from self_editor import get_editor as _get_editor
    _SELF_EDIT_SUPPORTED = True
except ImportError:
    _SELF_EDIT_SUPPORTED = False
    def _get_editor():
        return None

# ── Ether Core (the blob brain) ─────────────────────────────────────────────
try:
    from ether_core import get_core as _get_core
    _CORE_SUPPORTED = True
except ImportError:
    _CORE_SUPPORTED = False
    def _get_core():
        return None

_rag = None   # lazy-initialised on first chat

def get_rag():
    """Return a ready RAG manager, or None if unavailable."""
    global _rag
    if not _RAG_SUPPORTED:
        return None
    if _rag is None:
        try:
            mgr = _RAGClass()
            if mgr.build_index():
                _rag = mgr
        except Exception as e:
            print(f"[RAG] Init failed: {e} -- RAG disabled")
    return _rag

# ── Paths ──────────────────────────────────────────────────────────────────
# Default root comes from core.paths (single source of truth). ETHER_BASE
# remains an intentional override so the hub can be pointed at another root.
BASE_DIR  = Path(os.environ.get("ETHER_BASE", _PATHS.root)).resolve()
DATA_DIR  = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
PORT      = int(os.environ.get("ETHER_PORT", 5757))

# ── Flask init ─────────────────────────────────────────────────────────────
app = Flask(__name__,
            template_folder=str(BASE_DIR / "app" / "templates"),
            static_folder=str(BASE_DIR / "app" / "static"))

app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", hashlib.md5(str(BASE_DIR).encode()).hexdigest()),
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{DATA_DIR / 'ether.db'}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=32 * 1024 * 1024,
)

db = SQLAlchemy(app)

# ═══════════════════════════════════════════════════════════════════════════
#  DATABASE MODELS
# ═══════════════════════════════════════════════════════════════════════════

class Note(db.Model):
    __tablename__ = "notes"
    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(256), nullable=False)
    content    = db.Column(db.Text, default="")
    tags       = db.Column(db.String(512), default="")
    category   = db.Column(db.String(64), default="general")
    source_url = db.Column(db.String(2048), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SavedURL(db.Model):
    __tablename__ = "saved_urls"
    id         = db.Column(db.Integer, primary_key=True)
    url        = db.Column(db.String(2048), nullable=False)
    title      = db.Column(db.String(512), default="")
    summary    = db.Column(db.Text, default="")
    raw_text   = db.Column(db.Text, default="")
    tags       = db.Column(db.String(512), default="")
    category   = db.Column(db.String(64), default="general")
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id         = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), nullable=False)
    role       = db.Column(db.String(16), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    model_used = db.Column(db.String(64), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class KBEntry(db.Model):
    __tablename__ = "kb_entries"
    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(256), nullable=False)
    content    = db.Column(db.Text, default="")
    category   = db.Column(db.String(64), default="general")
    tags       = db.Column(db.String(512), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SpecialNote(db.Model):
    """Stores the single-document special pages (strategy, recovery)."""
    __tablename__ = "special_notes"
    id         = db.Column(db.Integer, primary_key=True)
    slug       = db.Column(db.String(64), unique=True, nullable=False)
    content    = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ═══════════════════════════════════════════════════════════════════════════
#  AI ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class EtherAI:
    def __init__(self):
        self.llm   = None
        self.mode  = "template"
        self._init()

    def _init(self):
        gguf_files = list(MODEL_DIR.glob("*.gguf")) if MODEL_DIR.exists() else []
        if not gguf_files:
            return
        try:
            from llama_cpp import Llama
            self.llm  = Llama(model_path=str(gguf_files[0]),
                              n_ctx=4096, n_threads=os.cpu_count() or 4,
                              verbose=False)
            self.mode = "local-llm"
            print(f"[AI] Loaded: {gguf_files[0].name}")
        except Exception as e:
            print(f"[AI] llama_cpp load failed: {e} -- template mode")

    def chat(self, messages):
        if self.llm:
            try:
                resp = self.llm.create_chat_completion(
                    messages=messages, max_tokens=1024, temperature=0.7,
                    stop=["</s>", "User:", "Human:"])
                return resp["choices"][0]["message"]["content"].strip()
            except Exception as e:
                return f"[AI error: {e}]"
        # Template fallback
        user_msg = messages[-1]["content"].lower() if messages else ""
        if any(w in user_msg for w in ["hello","hi","hey"]):
            return "Hello! I'm ETHER AI running on your WORDLIB USB. How can I help?"
        if any(w in user_msg for w in ["model","ai","phi","dolphin","llm"]):
            return ("I'm running in template mode -- no .gguf model found in /models. "
                    "Add a Dolphin or Phi model there and restart to enable full AI.")
        if any(w in user_msg for w in ["search","find","look"]):
            return "Use the global search bar at the top to search your library, notes, and knowledge base."
        return ("I'm ETHER AI in template mode. Add a .gguf model file to the /models folder "
                "on your USB and restart to enable full local AI responses.")

_ai = None
def get_ai():
    global _ai
    if _ai is None:
        _ai = EtherAI()
    return _ai

# ═══════════════════════════════════════════════════════════════════════════
#  SCRAPER
# ═══════════════════════════════════════════════════════════════════════════

def scrape_url(url):
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script","style","nav","footer","header","aside"]):
            tag.decompose()
        title   = (soup.find("title") or soup.find("h1") or type("_", (), {"get_text": lambda s: url})()).get_text().strip()[:256]
        raw     = " ".join(soup.get_text(" ", strip=True).split())
        summary = raw[:600]
        return {"ok": True, "title": title, "summary": summary, "raw_text": raw[:50000]}
    except Exception as e:
        return {"ok": False, "title": url, "summary": "", "raw_text": "", "error": str(e)}

# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES -- CORE
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/nephilim")
def nephilim():
    """NEPHILIM -- living neural agent interface. Striking + genuinely accessible."""
    return render_template("nephilim.html")


@app.route("/console")
def reasoning_console():
    """Reasoning-transparent agent console -- shows real agent activity, WCAG AA."""
    return render_template("console.html")


@app.route("/panel")
def accessible_panel():
    """WCAG 2.2 AA accessible control panel -- keyboard + screen-reader friendly."""
    return render_template("panel.html")


@app.route("/")
def index():
    stats = {
        "notes":   Note.query.count(),
        "urls":    SavedURL.query.count(),
        "kb":      KBEntry.query.count(),
        "ai_mode": get_ai().mode,
    }
    recent = Note.query.order_by(Note.updated_at.desc()).limit(6).all()
    return render_template("index.html", stats=stats, recent=recent)


@app.route("/status")
def status():
    rag = get_rag()
    rag_stats = rag.get_stats() if rag else {"status": "not_initialised"}
    return jsonify({
        "status":   "online",
        "version":  "1.0",
        "ai_mode":  get_ai().mode,
        "rag":      rag_stats,
        "time":     datetime.utcnow().isoformat(),
    })


@app.route("/api/rag/stats")
def rag_stats_api():
    """RAG health endpoint -- called by the dashboard badge."""
    rag = get_rag()
    return jsonify(rag.get_stats() if rag else {"status": "not_initialised"})


@app.route("/api/rag/rebuild", methods=["POST"])
def rag_rebuild():
    """Force a full RAG index rebuild (e.g. after adding new docs to storage/)."""
    global _rag
    rag = get_rag()
    if rag is None:
        return jsonify({"ok": False, "error": "RAG not available"}), 503
    try:
        ok = rag.rebuild()
        return jsonify({"ok": ok, "stats": rag.get_stats()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/rag/query", methods=["POST"])
def rag_query_api():
    """
    The shared RAG endpoint. Godot, OpenClaw, and any other tool POST a
    question here and get back relevant chunks from the knowledge base.
    This makes ETHER AI the single RAG hub for the whole system.

    Request:  {"query": "how do I...", "top_k": 4}
    Response: {"ok": true, "results": [{text, score, source, folder}, ...]}
    """
    data  = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    top_k = int(data.get("top_k", 4))
    if not query:
        return jsonify({"ok": False, "error": "Empty query"}), 400

    rag = get_rag()
    if rag is None or not rag.ready:
        return jsonify({"ok": False, "error": "RAG not available", "results": []}), 503
    try:
        results = rag.query(query, top_k=top_k)
        return jsonify({"ok": True, "results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "results": []}), 500

# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES -- SYSTEM (self-modification, file management)
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/system/summary")
def system_summary():
    """Full project file summary -- used by AI to understand its own structure."""
    ed = _get_editor()
    if not ed:
        return jsonify({"ok": False, "error": "Self-editor not available"}), 503
    return jsonify(ed.get_system_summary())


@app.route("/api/system/files")
def system_files():
    """List all project files, optionally under a subdir."""
    subdir = request.args.get("dir", "")
    ed = _get_editor()
    if not ed:
        return jsonify({"ok": False, "error": "Self-editor not available"}), 503
    return jsonify(ed.list_files(subdir))


@app.route("/api/system/read", methods=["POST"])
def system_read():
    """Read any project file."""
    data = request.get_json(silent=True) or {}
    path = (data.get("path") or "").strip()
    if not path:
        return jsonify({"ok": False, "error": "path required"}), 400
    ed = _get_editor()
    if not ed:
        return jsonify({"ok": False, "error": "Self-editor not available"}), 503
    return jsonify(ed.read_file(path))


@app.route("/api/system/write", methods=["POST"])
def system_write():
    """
    Write content to a whitelisted project file.
    Backs up first. Python files are syntax-validated.
    Body: {"path": "src/launcher.py", "content": "..."}
    """
    data    = request.get_json(silent=True) or {}
    path    = (data.get("path") or "").strip()
    content = data.get("content")
    if not path or content is None:
        return jsonify({"ok": False, "error": "path and content required"}), 400
    ed = _get_editor()
    if not ed:
        return jsonify({"ok": False, "error": "Self-editor not available"}), 503
    return jsonify(ed.write_file(path, content))


@app.route("/api/system/patch", methods=["POST"])
def system_patch():
    """
    Find-and-replace in a project file.
    Body: {"path": "...", "old": "...", "new": "..."}
    Fails if old appears 0 or 2+ times.
    """
    data = request.get_json(silent=True) or {}
    path = (data.get("path") or "").strip()
    old  = data.get("old", "")
    new  = data.get("new", "")
    if not path or not old:
        return jsonify({"ok": False, "error": "path and old required"}), 400
    ed = _get_editor()
    if not ed:
        return jsonify({"ok": False, "error": "Self-editor not available"}), 503
    return jsonify(ed.patch_file(path, old, new))


@app.route("/api/system/rollback", methods=["POST"])
def system_rollback():
    """Restore a file from its most recent backup."""
    data   = request.get_json(silent=True) or {}
    path   = (data.get("path") or "").strip()
    backup = data.get("backup_name")
    if not path:
        return jsonify({"ok": False, "error": "path required"}), 400
    ed = _get_editor()
    if not ed:
        return jsonify({"ok": False, "error": "Self-editor not available"}), 503
    return jsonify(ed.rollback(path, backup))


@app.route("/api/system/backups")
def system_backups():
    """List all available backups."""
    path = request.args.get("path", "")
    ed = _get_editor()
    if not ed:
        return jsonify({"ok": False, "error": "Self-editor not available"}), 503
    return jsonify(ed.list_backups(path or None))


@app.route("/api/core/status")
def core_status():
    """The blob brain's full status -- every real capability + counts."""
    core = _get_core()
    if not core:
        return jsonify({"ok": False, "error": "Ether core not available"}), 503
    return jsonify({"ok": True, **core.status()})


@app.route("/api/core/evolve", methods=["POST"])
def core_evolve():
    """
    Atomic self-modification with rollback.
    Body: {"path": "src/foo.py", "content": "...", "test_command": [...]}
    Validates, snapshots, deploys, tests, and rolls back on failure.
    """
    data    = request.get_json(silent=True) or {}
    path    = (data.get("path") or "").strip()
    content = data.get("content")
    test    = data.get("test_command")
    if not path or content is None:
        return jsonify({"ok": False, "error": "path and content required"}), 400
    core = _get_core()
    if not core:
        return jsonify({"ok": False, "error": "Ether core not available"}), 503
    result = core.evolution.evolve_file(path, content, test)
    return jsonify({
        "ok": result.success, "round": result.round, "target": result.target,
        "snapshot": result.snapshot, "error": result.error,
        "rolled_back": result.rolled_back, "detail": result.detail,
    })


@app.route("/api/core/events")
def core_events():
    """Recent operational events from the blob brain."""
    n = int(request.args.get("n", 20))
    core = _get_core()
    if not core:
        return jsonify({"ok": False, "error": "Ether core not available"}), 503
    return jsonify({"ok": True, "events": core.events.recent(n)})


# ── Multi-agent swarm routes ────────────────────────────────────────────────
try:
    from agents import get_orchestrator as _get_orch
    from agents import Task as _AgentTask
    _AGENTS_SUPPORTED = True
except ImportError:
    _AGENTS_SUPPORTED = False


@app.route("/api/agents/status")
def agents_status():
    if not _AGENTS_SUPPORTED:
        return jsonify({"ok": False, "error": "agents package not available"}), 503
    import os as _os
    orch = _get_orch(_os.environ.get("ETHER_BASE", "."))
    return jsonify({"ok": True, **orch.status()})


@app.route("/api/agents/solve", methods=["POST"])
def agents_solve():
    if not _AGENTS_SUPPORTED:
        return jsonify({"ok": False, "error": "agents package not available"}), 503
    data = request.get_json(silent=True) or {}
    goal = (data.get("goal") or "").strip()
    if not goal:
        return jsonify({"ok": False, "error": "goal required"}), 400
    import os as _os
    orch = _get_orch(_os.environ.get("ETHER_BASE", "."))
    return jsonify(orch.solve(goal))


@app.route("/api/agents/task", methods=["POST"])
def agents_task():
    if not _AGENTS_SUPPORTED:
        return jsonify({"ok": False, "error": "agents package not available"}), 503
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip()
    if not kind:
        return jsonify({"ok": False, "error": "task kind required"}), 400
    import os as _os
    orch = _get_orch(_os.environ.get("ETHER_BASE", "."))
    result = orch.route(_AgentTask(kind=kind, payload=data.get("payload", {})))
    return jsonify(result.as_dict())


@app.route("/api/reasoning/dashboard")
def reasoning_dashboard():
    """Structured data for the reasoning + agent dashboard."""
    if not _AGENTS_SUPPORTED:
        return jsonify({"ok": False, "error": "agents not available"}), 503
    import os as _os
    from pathlib import Path as _P
    root = _P(_os.environ.get("ETHER_BASE", "."))
    orch = _get_orch(root)
    power = orch.route(_AgentTask("power", {}))
    uq = orch.ctx.services.get("uncertainty")
    return jsonify({
        "ok": True,
        "swarm": orch.status(),
        "power": power.output,
        "calibration": uq.calibration_report() if uq else {},
    })


@app.route("/api/agents/gremlin", methods=["POST"])
def agents_gremlin():
    """Run a gremlin improvement cycle (propose-only by default)."""
    if not _AGENTS_SUPPORTED:
        return jsonify({"ok": False, "error": "agents not available"}), 503
    data = request.get_json(silent=True) or {}
    import os as _os
    from pathlib import Path as _P
    orch = _get_orch(_P(_os.environ.get("ETHER_BASE", ".")))
    result = orch.route(_AgentTask("gremlin",
                        {"action": data.get("action", "cycle")}))
    return jsonify(result.as_dict())


@app.route("/api/market/analyze", methods=["POST"])
def market_analyze():
    """Honest market analysis -- analyzes supplied evidence, never fabricates."""
    if not _AGENTS_SUPPORTED:
        return jsonify({"ok": False, "error": "agents not available"}), 503
    import os as _os
    from pathlib import Path as _P
    data = request.get_json(silent=True) or {}
    orch = _get_orch(_P(_os.environ.get("ETHER_BASE", ".")))
    result = orch.route(_AgentTask("market", data))
    return jsonify(result.as_dict())


@app.route("/api/reasoning/calibration")
def reasoning_calibration():
    """Real calibration health (Brier/ECE) for the 'show doubt' haze."""
    import os as _os
    from pathlib import Path as _P
    try:
        import sys as _sys
        _sys.path.insert(0, _os.environ.get("ETHER_BASE", ".") + "/src")
        from reasoning import UncertaintyQuantifier
        uq = UncertaintyQuantifier(_P(_os.environ.get("ETHER_BASE", ".")))
        return jsonify({"ok": True, **uq.calibration_report()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503


@app.route("/api/gremlin/activate", methods=["POST"])
def gremlin_activate():
    """Activate a real gremlin meta tool (consent-gated, logged)."""
    import os as _os
    from pathlib import Path as _P
    data = request.get_json(silent=True) or {}
    try:
        import sys as _sys
        _sys.path.insert(0, _os.environ.get("ETHER_BASE", ".") + "/src")
        from gremlin_coordinator import GremlinCoordinator
        gc = GremlinCoordinator(_P(_os.environ.get("ETHER_BASE", ".")))
        gc.enable(consent=bool(data.get("consent", False)))
        result = gc.activate(data.get("feature", ""), data.get("context", {}))
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503


@app.route("/api/gremlin/features")
def gremlin_features():
    """List gremlin coordinator features (executable vs descriptive-only)."""
    import os as _os
    from pathlib import Path as _P
    try:
        import sys as _sys
        _sys.path.insert(0, _os.environ.get("ETHER_BASE", ".") + "/src")
        from gremlin_coordinator import GremlinCoordinator
        gc = GremlinCoordinator(_P(_os.environ.get("ETHER_BASE", ".")))
        return jsonify({"ok": True, "features": gc.list_features()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503


@app.route("/api/agents/evolution")
def agents_evolution():
    """Meta-evolution status: agent versions + fitness (honest, real or empty)."""
    if not _AGENTS_SUPPORTED:
        return jsonify({"ok": False, "error": "agents not available"}), 503
    import os as _os
    from pathlib import Path as _P
    orch = _get_orch(_P(_os.environ.get("ETHER_BASE", ".")))
    return jsonify({"ok": True, **orch.evolution_status()})


@app.route("/api/system/scaling")
def system_scaling():
    """Current deployment mode + scaling profile."""
    import os as _os
    from pathlib import Path as _P
    try:
        from deployment.scaling import get_profile
        return jsonify({"ok": True,
                        **get_profile(_P(_os.environ.get("ETHER_BASE", "."))).as_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503


@app.route("/api/reasoning/judge", methods=["POST"])
def reasoning_judge():
    """Judge a piece of text with the honest Prometheus wrapper."""
    if not _AGENTS_SUPPORTED:
        return jsonify({"ok": False, "error": "agents not available"}), 503
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    kind = data.get("kind", "creative")
    import os as _os
    from pathlib import Path as _P
    orch = _get_orch(_P(_os.environ.get("ETHER_BASE", ".")))
    judge = orch.ctx.services.get("judge")
    if not judge:
        return jsonify({"ok": False, "error": "judge unavailable"}), 503
    return jsonify({"ok": True, **judge.judge(text, kind).as_dict()})


# ── 404 / 500 handlers ─────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Endpoint not found"}), 404
    return render_template("base.html"), 404

@app.errorhandler(500)
def server_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Internal server error"}), 500
    return render_template("base.html"), 500


# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES -- AI CHAT
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/chat")
def chat_page():
    sid = session.setdefault("chat_session", os.urandom(8).hex())
    msgs = ChatMessage.query.filter_by(session_id=sid).order_by(ChatMessage.created_at).limit(100).all()
    return render_template("chat.html", messages=msgs, ai_mode=get_ai().mode)


@app.route("/chat/send", methods=["POST"])
def chat_send():
    data    = request.get_json()
    user_q  = (data.get("message") or "").strip()
    sid     = session.setdefault("chat_session", os.urandom(8).hex())
    if not user_q:
        return jsonify({"error": "Empty message"}), 400

    db.session.add(ChatMessage(session_id=sid, role="user", content=user_q))
    db.session.commit()

    history = ChatMessage.query.filter_by(session_id=sid).order_by(ChatMessage.created_at).limit(20).all()

    # ── RAG context injection ─────────────────────────────────────────────
    # Query the Ollama RAG index for relevant chunks from storage/ folders.
    # Results are injected into the system prompt so the AI can answer from
    # your actual library without hallucinating.
    rag_context = ""
    rag_sources = []
    rag = get_rag()
    if rag and rag.ready:
        try:
            results = rag.query(user_q, top_k=4)
            if results:
                chunks = "\n\n".join(
                    f"[{r['folder']}/{r['source']}]\n{r['text']}"
                    for r in results
                )
                rag_context = (
                    "\n\nRelevant context from your WORDLIB knowledge base:\n"
                    + chunks
                    + "\n\nUse the above context where relevant. "
                      "Cite the source filename when you draw from it."
                )
                rag_sources = [f"{r['folder']}/{r['source']}" for r in results]
        except Exception as _e:
            pass  # RAG failure is non-fatal

    system_prompt = (
        "You are ETHER AI, a personal knowledge assistant running locally on a USB drive called WORDLIB. "
        "Help with research, notes, coding, and knowledge management. Be direct and useful."
        + rag_context
    )

    msgs = [{"role": "system", "content": system_prompt}]
    msgs += [{"role": m.role, "content": m.content} for m in history]

    reply = get_ai().chat(msgs)
    db.session.add(ChatMessage(session_id=sid, role="assistant",
                               content=reply, model_used=get_ai().mode))
    db.session.commit()
    return jsonify({
        "reply":   reply,
        "mode":    get_ai().mode,
        "rag_on":  bool(rag_sources),
        "sources": rag_sources,
    })


@app.route("/chat/clear", methods=["POST"])
def chat_clear():
    sid = session.get("chat_session")
    if sid:
        ChatMessage.query.filter_by(session_id=sid).delete()
        db.session.commit()
        session.pop("chat_session", None)
    return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES -- LIBRARY (notes + URL scraper)
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/library")
def library():
    q   = request.args.get("q", "")
    cat = request.args.get("cat", "")
    nq  = Note.query
    uq  = SavedURL.query
    if q:
        nq = nq.filter(Note.title.contains(q) | Note.content.contains(q))
        uq = uq.filter(SavedURL.title.contains(q) | SavedURL.summary.contains(q))
    if cat:
        nq = nq.filter_by(category=cat)
        uq = uq.filter_by(category=cat)
    notes = nq.order_by(Note.updated_at.desc()).all()
    urls  = uq.order_by(SavedURL.scraped_at.desc()).all()
    return render_template("library.html", notes=notes, urls=urls, query=q, category=cat)


@app.route("/library/note/new", methods=["GET", "POST"])
def note_new():
    if request.method == "POST":
        note = Note(title    = request.form.get("title", "Untitled"),
                    content  = request.form.get("content", ""),
                    tags     = request.form.get("tags", ""),
                    category = request.form.get("category", "general"))
        db.session.add(note); db.session.commit()
        return redirect(url_for("library"))
    return render_template("note_edit.html", note=None)


@app.route("/library/note/<int:nid>", methods=["GET"])
def note_view(nid):
    return render_template("note_view.html", note=Note.query.get_or_404(nid))


@app.route("/library/note/<int:nid>/edit", methods=["GET", "POST"])
def note_edit(nid):
    note = Note.query.get_or_404(nid)
    if request.method == "POST":
        note.title    = request.form.get("title", note.title)
        note.content  = request.form.get("content", note.content)
        note.tags     = request.form.get("tags", note.tags)
        note.category = request.form.get("category", note.category)
        note.updated_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for("library"))
    return render_template("note_edit.html", note=note)


@app.route("/library/note/<int:nid>/delete", methods=["POST"])
def note_delete(nid):
    db.session.delete(Note.query.get_or_404(nid))
    db.session.commit()
    return redirect(url_for("library"))


@app.route("/library/scrape", methods=["POST"])
def scrape():
    data     = request.get_json()
    url      = (data.get("url") or "").strip()
    tags     = data.get("tags", "")
    category = data.get("category", "general")
    if not url.startswith("http"):
        return jsonify({"error": "Invalid URL"}), 400
    result = scrape_url(url)
    if not result["ok"]:
        return jsonify({"error": result.get("error", "Scrape failed")}), 500
    saved = SavedURL(url=url, title=result["title"], summary=result["summary"],
                     raw_text=result["raw_text"], tags=tags, category=category)
    db.session.add(saved); db.session.commit()
    return jsonify({"ok": True, "title": result["title"], "summary": result["summary"]})


@app.route("/library/url/<int:uid>/delete", methods=["POST"])
def url_delete(uid):
    db.session.delete(SavedURL.query.get_or_404(uid))
    db.session.commit()
    return redirect(url_for("library"))

# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES -- KNOWLEDGE BASE
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/kb")
def knowledge_base():
    q   = request.args.get("q", "")
    cat = request.args.get("cat", "")
    qry = KBEntry.query
    if q:
        qry = qry.filter(KBEntry.title.contains(q) | KBEntry.content.contains(q))
    if cat:
        qry = qry.filter_by(category=cat)
    entries = qry.order_by(KBEntry.created_at.desc()).all()
    cats    = [c[0] for c in db.session.query(KBEntry.category).distinct().all()]
    return render_template("kb.html", entries=entries, query=q, category=cat, categories=cats)


@app.route("/kb/<int:eid>")
def kb_entry(eid):
    return render_template("kb_entry.html", entry=KBEntry.query.get_or_404(eid))


@app.route("/kb/new", methods=["GET", "POST"])
def kb_new():
    if request.method == "POST":
        db.session.add(KBEntry(
            title    = request.form.get("title", "Untitled"),
            content  = request.form.get("content", ""),
            category = request.form.get("category", "general"),
            tags     = request.form.get("tags", "")))
        db.session.commit()
        return redirect(url_for("knowledge_base"))
    return render_template("kb_edit.html", entry=None)


@app.route("/kb/<int:eid>/edit", methods=["GET", "POST"])
def kb_edit(eid):
    entry = KBEntry.query.get_or_404(eid)
    if request.method == "POST":
        entry.title    = request.form.get("title", entry.title)
        entry.content  = request.form.get("content", entry.content)
        entry.category = request.form.get("category", entry.category)
        entry.tags     = request.form.get("tags", entry.tags)
        entry.updated_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for("knowledge_base"))
    return render_template("kb_edit.html", entry=entry)


@app.route("/kb/<int:eid>/delete", methods=["POST"])
def kb_delete(eid):
    db.session.delete(KBEntry.query.get_or_404(eid)); db.session.commit()
    return redirect(url_for("knowledge_base"))

# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES -- RESEARCH (Philippines solar, ecommerce, business)
# ═══════════════════════════════════════════════════════════════════════════

RESEARCH_DATA = {
    "solar_ph": {
        "title": "Philippines Solar Energy",
        "icon": "Solar",
        "notes": [
            "Feed-in Tariff (FiT): PHP 8.69/kWh for solar (residential)",
            "Net Metering available for systems up to 100 kW -- excess sold to grid",
            "Key players: Solar Philippines, SunAsia Energy, Citicore Solar, Cleantech Solar",
            "Average payback period: 5-8 years for rooftop systems",
            "Average irradiance: 5.1-5.5 kWh/m2/day -- excellent solar resource nationally",
            "DOE target: 35% renewable energy share by 2030",
            "Republic Act 9513 (Renewable Energy Act 2008) governs FiT and net metering",
            "CREO/GEAP grants available for off-grid rural barangay solar systems",
            "Top solar provinces: Batangas, Pampanga, Pangasinan, Cebu",
            "Typhoon design load requirement: panels must withstand 200+ km/h winds",
        ]
    },
    "ecommerce_ph": {
        "title": "Philippines E-Commerce",
        "icon": "eCommerce",
        "notes": [
            "Top platforms: Shopee (#1), Lazada (#2), TikTok Shop (fastest growing), Zalora, Carousell",
            "E-commerce GMV 2024: approx USD 17 billion (est.)",
            "Mobile-first: 95%+ of PH online shoppers use smartphones",
            "Payment: GCash and Maya dominate digital wallets; COD still ~40% of orders",
            "Logistics leaders: J&T Express, LBC, Ninja Van, 2GO, GoGo Express",
            "Key categories: fashion, electronics, health/beauty, home, food delivery",
            "Peak events: 11.11, 12.12, Payday sales (15th/30th), Christmas season",
            "Social commerce rising: Facebook Shops, Instagram, TikTok LIVE selling",
            "MSME share: ~60% of Shopee/Lazada sellers are micro/small enterprises",
            "DTI supports MSMEs via eCommerce PH program and free digital training",
        ]
    },
    "business_ph": {
        "title": "General Business -- Philippines",
        "icon": "Business",
        "notes": [
            "BIR registration required for all businesses; annual ITR filing",
            "PEZA zones offer 4-8 year income tax holidays for qualifying businesses",
            "SEC registration for corporations; DTI for sole proprietors",
            "Minimum wage varies by region: NCR ~PHP 610/day (2024)",
            "Barangay clearance required before applying for mayor's permit",
            "OFW remittances ~USD 36B/year -- major economic driver",
            "Top FDI sources: Japan, South Korea, USA, China, Singapore",
            "InterCorporate Investment (FINL): foreigners limited to 40% in most sectors",
            "Retail Trade Liberalization Act 2021: foreigners can now own 100% in retail",
        ]
    }
}

@app.route("/research")
def research():
    topic = request.args.get("topic", "solar_ph")
    data  = RESEARCH_DATA.get(topic, RESEARCH_DATA["solar_ph"])
    return render_template("research.html", data=data, topic=topic, all_topics=RESEARCH_DATA)


# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES -- STRATEGY NOTES (Markdown editor)
# ═══════════════════════════════════════════════════════════════════════════

STRATEGY_DEFAULT = """# Strategy Notes

## EU5 / Castile Colonization (EU4)

### Opening Moves
- Prioritize Reconquista: take Grenada first turn if possible
- Rival Aragon early -- prevents PU complications
- Ally Austria for HRE protection while expanding west

### Colonial Strategy
- Rush exploration tech to unlock Colonialism institution first
- Target Caribbean first: Cuba, Hispaniola for sugar trade nodes
- Colonize Brazil coastline before Portugal locks it (AI sometimes fails)
- Establish trade company in Ivory Coast / Gulf of Guinea early

### Trade Priorities
1. Seville trade node -- protect at all costs
2. English Channel node -- control via colonization or war
3. Cape of Good Hope -- highest value late game

### Tips
- Never break Alliance with Austria until you can handle France alone
- Mandate of Heaven: Castile can form Spain via event (keep Iberian culture)
- Avoid Ottoman war until you have 200+ force limit

---

## Notes

Add your notes here...
"""

@app.route("/strategy")
def strategy():
    note = SpecialNote.query.filter_by(slug="strategy").first()
    if not note:
        note = SpecialNote(slug="strategy", content=STRATEGY_DEFAULT)
        db.session.add(note); db.session.commit()
    return render_template("strategy.html", note=note)


@app.route("/strategy/save", methods=["POST"])
def strategy_save():
    note = SpecialNote.query.filter_by(slug="strategy").first()
    if not note:
        note = SpecialNote(slug="strategy"); db.session.add(note)
    note.content    = request.get_json().get("content", "")
    note.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES -- RECOVERY GUIDE
# ═══════════════════════════════════════════════════════════════════════════

RECOVERY_DEFAULT = """# Recovery & Supplement Protocol

## Daily Stack

### Morning (with food)
- **NAC** 600mg -- antioxidant, liver support, cysteine precursor
- **Magnesium Glycinate** 200mg -- muscle, sleep, reduces anxiety
- **B-Complex** (B50 or B100) -- energy metabolism, nervous system
- **Vitamin C** 500-1000mg -- immune, collagen, antioxidant
- **Omega-3** 1-2g EPA/DHA -- inflammation, brain function

### Evening
- **Magnesium Glycinate** 200mg (second dose -- promotes sleep)
- **Zinc** 15-25mg (if not in B-complex) -- immune, testosterone
- **Melatonin** 0.5-1mg if needed -- sleep onset

## Hydration & Electrolytes
- Target: 2.5-3L water daily
- Add electrolytes post-exercise: sodium, potassium, magnesium
- ORS or coconut water after heavy sweating

## Recovery Priorities
1. Sleep 7-9 hours -- non-negotiable
2. Protein: 1.6-2.2g per kg bodyweight
3. Creatine 3-5g daily -- safe, most studied supplement
4. Avoid alcohol -- disrupts sleep architecture and recovery

## Notes

Add your personal protocol here...
"""

@app.route("/recovery")
def recovery():
    note = SpecialNote.query.filter_by(slug="recovery").first()
    if not note:
        note = SpecialNote(slug="recovery", content=RECOVERY_DEFAULT)
        db.session.add(note); db.session.commit()
    return render_template("recovery.html", note=note)


@app.route("/recovery/save", methods=["POST"])
def recovery_save():
    note = SpecialNote.query.filter_by(slug="recovery").first()
    if not note:
        note = SpecialNote(slug="recovery"); db.session.add(note)
    note.content    = request.get_json().get("content", "")
    note.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})

# ═══════════════════════════════════════════════════════════════════════════
#  API -- GLOBAL SEARCH
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify([])
    results = []
    for n in Note.query.filter(Note.title.contains(q) | Note.content.contains(q)).limit(8).all():
        results.append({"type": "note", "id": n.id, "title": n.title,
                        "snippet": n.content[:120], "url": f"/library/note/{n.id}"})
    for u in SavedURL.query.filter(SavedURL.title.contains(q) | SavedURL.summary.contains(q)).limit(8).all():
        results.append({"type": "url", "id": u.id, "title": u.title,
                        "snippet": u.summary[:120], "url": u.url})
    for k in KBEntry.query.filter(KBEntry.title.contains(q) | KBEntry.content.contains(q)).limit(8).all():
        results.append({"type": "kb", "id": k.id, "title": k.title,
                        "snippet": k.content[:120], "url": f"/kb/{k.id}"})
    return jsonify(results)

# ═══════════════════════════════════════════════════════════════════════════
#  DEFAULT KB CONTENT
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_KB = [
    {
        "title": "Linux Distros -- Ranked by Use Case",
        "category": "linux",
        "tags": "linux,os,distro",
        "content": """# Linux Distro Rankings

## Desktop / Daily Driver
1. **Ubuntu 24.04 LTS** -- largest ecosystem, most tutorials
2. **Linux Mint 21** -- best for Windows migrants, rock stable
3. **Fedora 40** -- cutting edge, GNOME showcase
4. **Pop!_OS** -- developer/gaming focus, System76
5. **NixOS** -- reproducible, declarative config

## Server / Production
1. **Debian 12** -- ultra-stable, gold standard
2. **Rocky Linux 9** -- RHEL-compatible, enterprise
3. **Ubuntu Server 24.04 LTS** -- cloud-native, most tutorials
4. **AlmaLinux** -- CentOS replacement, stable

## Privacy / Security
1. **Tails OS** -- amnesic, Tor-based, leave no trace
2. **Whonix** -- VM-based anonymity layers
3. **Qubes OS** -- compartmentalisation by design
4. **Kali Linux** -- penetration testing

## Lightweight (old hardware)
1. **Puppy Linux** -- runs entirely in RAM, <200MB
2. **antiX** -- systemd-free, fast boot
3. **BunsenLabs** -- Openbox, minimal, Debian-based
4. **Lubuntu** -- LXQt, official Ubuntu spin
"""
    },
    {
        "title": "Python / Flask Dev Environment Setup",
        "category": "dev",
        "tags": "python,flask,dev,setup,windows",
        "content": """# Python / Flask Dev Environment

## Windows Setup
```powershell
# Install Python from python.org (check "Add Python to PATH")
python --version
pip install virtualenv
cd my_project
python -m venv venv
venv\\Scripts\\activate
pip install flask flask-sqlalchemy requests beautifulsoup4
```

## Linux/Mac Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install flask flask-sqlalchemy requests beautifulsoup4
```

## Useful Flask Commands
```bash
flask run --debug
flask shell   # interactive Python with app context
```

## VS Code Extensions
- Python (Microsoft)
- Pylance
- GitLens
- SQLite Viewer
- REST Client

## Flask Project Structure
```
project/
├── app/
│   ├── main.py       # routes
│   └── models.py     # DB models (or use SQLAlchemy in main.py)
├── templates/        # Jinja2 HTML
├── static/           # CSS/JS
├── data/             # SQLite .db file
└── requirements.txt
```
"""
    },
    {
        "title": "PowerShell Quick Reference",
        "category": "dev",
        "tags": "powershell,windows,scripting",
        "content": """# PowerShell Quick Reference

## Navigation
```powershell
Get-Location          # pwd
Set-Location C:\\Users  # cd
Get-ChildItem         # ls / dir
```

## Files
```powershell
New-Item file.txt -ItemType File
Remove-Item file.txt
Copy-Item src.txt dst.txt
Move-Item old.txt new.txt
Get-Content file.txt     # cat
Add-Content file.txt "text"
```

## Processes
```powershell
Get-Process
Stop-Process -Name notepad
Start-Process notepad.exe
```

## Execution Policy
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
Get-ExecutionPolicy
```

## USB AI Note
When writing PS1 scripts: NO emoji, NO Unicode.
Use [OK], [WARN], [ERR] in plain ASCII.
Always generate scripts via HTML_Generator.html.
"""
    },
]

def seed_defaults():
    if KBEntry.query.count() == 0:
        for e in DEFAULT_KB:
            db.session.add(KBEntry(**e))
        db.session.commit()
        print("[DB] Default KB seeded")

# ═══════════════════════════════════════════════════════════════════════════
#  STARTUP
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        db.create_all()
        seed_defaults()
        print(f"[ETHER] DB: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"[ETHER] Models: {MODEL_DIR}")
        print(f"[ETHER] AI mode: {get_ai().mode}")
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
