import asyncio
import base64
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime as dt, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Literal
import datetime
import json
import os
import subprocess
import threading
import time
import urllib.request
import urllib.error

from services.hermes_log_stream import get_log_stream
from services.hermes_api_bridge import run_query as hermes_run_query
from services.hermes_pty import PtyBridge

GATEWAY_STATE_PATH = Path.home() / ".hermes" / "gateway_state.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    stream = get_log_stream()
    stream.set_broadcast(broadcast_log)
    await stream.start()
    yield
    await stream.stop()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

chat_clients: set[WebSocket] = set()
log_clients: set[WebSocket] = set()

EventType = Literal["log", "tool", "agent", "system", "task", "done", "error"]
EventLevel = Literal["info", "warning", "error", "success"]
EventSource = Literal["hermi", "backend", "agent", "system"]


class Event(BaseModel):
    type: EventType = "log"
    level: EventLevel = "info"
    source: EventSource = "hermi"
    message: str
    timestamp: Optional[str] = None
    meta: Optional[dict] = None


_query_lock = asyncio.Lock()
_query_running = False

_weather_cache: dict | None = None
_weather_cache_ts: float = 0
WEATHER_CACHE_TTL = 300  # 5 Minuten


class QueryRequest(BaseModel):
    text: str


class ChatRequest(BaseModel):
    text: str
    session_id: str


class ActionRequest(BaseModel):
    action: str
    mode: str = "full"  # "quick" | "full"


_chat_lock = asyncio.Lock()
_chat_running = False

_action_lock = threading.Lock()


def now_ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


async def _run_query(text: str):
    global _query_running
    _query_running = True
    try:
        await broadcast_chat({
            "type": "query",
            "level": "info",
            "source": "system",
            "message": f"Hermes Query gestartet: {text[:60]}",
            "timestamp": now_ts(),
        })
        await hermes_run_query(text, broadcast_chat)
    finally:
        _query_running = False


async def _run_chat(text: str, session_id: str):
    global _chat_running
    _chat_running = True
    try:
        await broadcast_chat({
            "type": "query",
            "level": "info",
            "source": "system",
            "message": f"Hermes Chat: {text[:60]}",
            "timestamp": now_ts(),
        })
        await hermes_run_query(text, broadcast_chat, session_id)
    finally:
        _chat_running = False


async def _broadcast_to_set(event: dict, clients: set[WebSocket]) -> int:
    disconnected: list[WebSocket] = []
    count = 0
    for ws in clients:
        try:
            await ws.send_json(event)
            count += 1
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        clients.discard(ws)
    return count


async def broadcast_chat(event: dict) -> int:
    return await _broadcast_to_set(event, chat_clients)


async def broadcast_log(event: dict) -> int:
    return await _broadcast_to_set(event, log_clients)


@app.get("/")
def root():
    return {"status": "Hermi Cockpit Backend läuft 🚀"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.datetime.now().isoformat()
    }


@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    chat_clients.add(ws)
    print(f"Chat client connected ({len(chat_clients)} total)")
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        chat_clients.discard(ws)
        print(f"Chat client disconnected ({len(chat_clients)} total)")


@app.websocket("/ws/logs")
async def websocket_logs(ws: WebSocket):
    await ws.accept()
    log_clients.add(ws)
    print(f"Log client connected ({len(log_clients)} total)")
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        log_clients.discard(ws)
        print(f"Log client disconnected ({len(log_clients)} total)")


@app.websocket("/ws/pty")
async def websocket_pty(ws: WebSocket):
    await ws.accept()
    print(f"PTY client connected")
    bridge = PtyBridge()

    async def on_output(data: bytes):
        if data:
            try:
                await ws.send_json({
                    "type": "output",
                    "data": base64.b64encode(data).decode("ascii"),
                })
            except Exception:
                pass
        else:
            try:
                await ws.send_json({"type": "exit", "code": bridge.exit_code or 0})
            except Exception:
                pass

    await bridge.start(on_output)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "input":
                data = msg.get("data", "")
                if data:
                    try:
                        bridge.write(base64.b64decode(data))
                    except Exception:
                        pass
            elif msg.get("type") == "resize":
                rows = msg.get("rows")
                cols = msg.get("cols")
                if isinstance(rows, int) and isinstance(cols, int) and rows > 0 and cols > 0:
                    bridge.resize(rows, cols)
    except WebSocketDisconnect:
        pass
    finally:
        await bridge.stop()
        print(f"PTY client disconnected")



@app.get("/test-event")
async def test_event():
    event = {
        "type": "test_event",
        "level": "info",
        "source": "system",
        "message": f"Test-Event triggered at {datetime.datetime.now().isoformat()}",
        "timestamp": now_ts(),
    }
    count = await broadcast_chat(event)
    return JSONResponse({
        "status": "broadcast",
        "clients_count": len(chat_clients),
        "broadcast_count": count,
        "event": event,
    })


@app.post("/events")
async def ingest_event(event: Event):
    payload = event.model_dump()
    if not payload.get("timestamp"):
        payload["timestamp"] = now_ts()

    count = await broadcast_chat(payload)
    print(f"[Event] type={event.type} level={event.level} source={event.source} "
          f"→ {count} clients")

    return JSONResponse({
        "status": "broadcast" if count > 0 else "stored",
        "clients_count": len(chat_clients),
        "broadcast_count": count,
        "event": payload,
    })


@app.get("/api/system")
def system_metrics():
    try:
        import psutil
    except ImportError:
        return JSONResponse(
            {"error": "psutil not installed"},
            status_code=500,
        )

    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()

    return {
        "cpu_percent": round(cpu, 1),
        "ram_percent": ram.percent,
        "ram_used_gb": round(ram.used / (1024**3), 1),
        "ram_total_gb": round(ram.total / (1024**3), 1),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "network_kb_s": round(net.bytes_sent / 1024 + net.bytes_recv / 1024, 1),
    }


@app.get("/api/status")
def gateway_status():
    result: dict = {"api_server": "offline"}

    try:
        req = urllib.request.Request("http://127.0.0.1:8642/health")
        with urllib.request.urlopen(req, timeout=2) as resp:
            result["api_server"] = "online" if resp.status == 200 else "offline"
    except Exception:
        pass

    if not GATEWAY_STATE_PATH.exists():
        result["gateway_state"] = "unknown"
        result["active_agents_count"] = 0
        result["updated_at"] = ""
        return result

    try:
        data = json.loads(GATEWAY_STATE_PATH.read_text())
        result["gateway_state"] = data.get("gateway_state", "unknown")
        result["active_agents_count"] = int(data.get("active_agents", 0))
        result["updated_at"] = data.get("updated_at", "")
    except (json.JSONDecodeError, OSError):
        result["gateway_state"] = "unknown"
        result["active_agents_count"] = 0
        result["updated_at"] = ""

    return result


@app.post("/api/query")
async def query_hermes(req: QueryRequest):
    global _query_running

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=422, detail="Leerer Query-Text")

    if _query_running:
        raise HTTPException(status_code=409, detail="Query läuft bereits")

    _query_running = True
    asyncio.create_task(_run_query(req.text.strip()))

    return JSONResponse({"status": "accepted", "text": req.text[:60]})


@app.post("/api/chat")
async def chat_hermes(req: ChatRequest):
    global _chat_running

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=422, detail="Leerer Chat-Text")

    if _chat_running:
        raise HTTPException(status_code=409, detail="Chat läuft bereits")

    _chat_running = True
    asyncio.create_task(_run_chat(req.text.strip(), req.session_id))

    return JSONResponse({"status": "accepted", "text": req.text[:60], "session_id": req.session_id})


@app.get("/api/memory")
def memory():
    memory_path = Path.home() / ".hermes" / "memories" / "MEMORY.md"
    if not memory_path.exists():
        return {"status": "empty", "total_chars": 0, "memory_chars": 0, "user_chars": 0,
                "memory_pct": 0, "user_pct": 0, "entries": 0, "preview": ""}
    try:
        text = memory_path.read_text()
    except OSError:
        return {"status": "empty", "total_chars": 0, "memory_chars": 0, "user_chars": 0,
                "memory_pct": 0, "user_pct": 0, "entries": 0, "preview": ""}

    total_chars = len(text)
    entries = text.count("\n\u00a7\n") + (1 if text.startswith("\u00a7\n") else 0)

    memory_section = text
    user_section = ""

    memory_marker = "## MEMORY"
    user_marker = "## USER PROFILE"

    mem_idx = text.find(memory_marker)
    user_idx = text.find(user_marker)

    if mem_idx >= 0 and user_idx >= 0:
        if mem_idx < user_idx:
            memory_section = text[mem_idx + len(memory_marker):user_idx].strip()
            user_section = text[user_idx + len(user_marker):].strip()
        else:
            user_section = text[user_idx + len(user_marker):mem_idx].strip()
            memory_section = text[mem_idx + len(memory_marker):].strip()
    elif mem_idx >= 0:
        memory_section = text[mem_idx + len(memory_marker):].strip()
        user_section = ""
    elif user_idx >= 0:
        memory_section = ""
        user_section = text[user_idx + len(user_marker):].strip()

    memory_chars = len(memory_section)
    user_chars = len(user_section)
    memory_pct = round(memory_chars / total_chars * 100) if total_chars > 0 else 0
    user_pct = round(user_chars / total_chars * 100) if total_chars > 0 else 0

    # Kurze Vorschau (erste 200 Zeichen des Memory-Bereichs)
    preview = memory_section[:200].strip() if memory_section else ""

    return {
        "status": "ok",
        "total_chars": total_chars,
        "memory_chars": memory_chars,
        "user_chars": user_chars,
        "memory_pct": memory_pct,
        "user_pct": user_pct,
        "entries": entries,
        "preview": preview,
    }


@app.get("/api/sessions")
def sessions():
    db_path = Path.home() / ".hermes" / "state.db"
    if not db_path.exists():
        return {"sessions": []}

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, source, model, title, started_at, ended_at, "
            "input_tokens, output_tokens, estimated_cost_usd "
            "FROM sessions ORDER BY rowid DESC LIMIT 20"
        ).fetchall()
        conn.close()

        result = []
        for row in rows:
            d = dict(row)
            if d.get("started_at") is not None:
                d["started_at"] = dt.fromtimestamp(d["started_at"]).strftime("%Y-%m-%d %H:%M")
            if d.get("ended_at") is not None:
                d["ended_at"] = dt.fromtimestamp(d["ended_at"]).strftime("%Y-%m-%d %H:%M")
            result.append(d)

        return {"sessions": result}
    except Exception:
        return {"sessions": []}


@app.get("/api/agents")
def agents():
    skill_runs_path = Path.home() / ".hermes" / "skill-runs.json"
    skills_dir = Path.home() / ".hermes" / "skills" / "holger"

    agent_map: dict[str, dict] = {}

    try:
        if skill_runs_path.exists():
            data = json.loads(skill_runs_path.read_text())
            for name, info in data.get("skills", {}).items():
                reifegrad = info.get("reifegrad", "")
                runs = info.get("runs", 0)
                if reifegrad != "test" or runs > 0:
                    agent_map[name] = {
                        "name": name,
                        "runs": runs,
                        "last_run": info.get("last_run"),
                        "errors": info.get("errors", 0),
                        "reifegrad": reifegrad,
                    }
    except (json.JSONDecodeError, OSError):
        pass

    try:
        if skills_dir.is_dir():
            for entry in sorted(os.listdir(skills_dir)):
                dir_path = skills_dir / entry
                if dir_path.is_dir() and entry not in agent_map:
                    agent_map[entry] = {
                        "name": entry,
                        "runs": 0,
                        "last_run": None,
                        "errors": 0,
                        "reifegrad": "local",
                    }
    except OSError:
        pass

    agent_list = sorted(agent_map.values(), key=lambda x: x["runs"], reverse=True)
    return {"agents": agent_list}


# ── Neue API-Endpunkte ──────────────────────────────────────────────


@app.get("/api/cron")
def cron_jobs():
    try:
        result = subprocess.run(
            [os.path.expanduser("~/.local/bin/hermes"), "cron", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            print(f"[Cron] hermes cron list fehlgeschlagen: {result.stderr.strip()}")
            return {"jobs": []}

        jobs: list[dict] = []
        current: dict | None = None

        for line in result.stdout.strip().split("\n"):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))

            # Skip box-drawing and header lines
            if not stripped or stripped.startswith("\u250c") or stripped.startswith("\u2502") or stripped.startswith("\u2514"):
                continue

            # New job: 2-space indent + hex ID + [status]
            if indent == 2 and " " in stripped:
                parts = stripped.rsplit(" ", 1)
                job_id = parts[0]
                status = parts[1].strip("[]") if len(parts) > 1 and parts[1].startswith("[") else "unknown"
                current = {"id": job_id, "status": status}
                jobs.append(current)
                continue

            # Property line: 4-space indent with key: value
            if current is not None and indent >= 4 and ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                if key == "name":
                    current["name"] = value
                elif key == "schedule":
                    current["schedule"] = value
                elif key == "next_run":
                    current["next_run"] = value
                elif key == "last_run":
                    current["last_run"] = value
                elif key == "skills":
                    current["skills"] = value
                elif key == "deliver":
                    current["deliver"] = value

        return {"jobs": jobs}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("[Cron] hermes CLI nicht verfügbar oder Timeout")
        return {"jobs": []}
    except Exception as e:
        print(f"[Cron] Fehler: {e}")
        return {"jobs": []}


@app.get("/api/weather")
def weather_proxy():
    global _weather_cache, _weather_cache_ts

    now = time.time()
    if _weather_cache and (now - _weather_cache_ts) < WEATHER_CACHE_TTL:
        return _weather_cache

    try:
        req = urllib.request.Request("https://wttr.in/Schwerin?format=j1")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Weather] wttr.in nicht erreichbar: {e}")
        if _weather_cache:
            return _weather_cache
        return JSONResponse(
            {"error": "Wetterdienst nicht erreichbar"},
            status_code=502,
        )

    data["cached_until"] = datetime.datetime.fromtimestamp(
        now + WEATHER_CACHE_TTL
    ).isoformat()
    _weather_cache = data
    _weather_cache_ts = now
    return data


@app.get("/api/news")
def news():
    MAX_ITEMS = 20
    news_path = Path.home() / ".hermes" / "news" / "latest.json"
    if not news_path.exists():
        return {"news": []}
    try:
        data = json.loads(news_path.read_text())
        items = data if isinstance(data, list) else data.get("news", data.get("items", []))
        return {"news": items[:MAX_ITEMS]}
    except (json.JSONDecodeError, OSError):
        return {"news": []}


@app.get("/api/tasks")
def tasks():
    MAX_TASKS = 50
    tasks_path = Path.home() / ".hermes" / "tasks.json"
    if not tasks_path.exists():
        return {"tasks": []}
    try:
        tasks_data = json.loads(tasks_path.read_text())
        items = tasks_data if isinstance(tasks_data, list) else tasks_data.get("tasks", [])
        return {"tasks": items[:MAX_TASKS]}
    except (json.JSONDecodeError, OSError):
        return {"tasks": []}


@app.get("/api/skills")
def skills():
    skills_dir = Path.home() / ".hermes" / "skills" / "holger"
    if not skills_dir.is_dir():
        return {"skills": []}
    try:
        names = sorted(
            entry for entry in os.listdir(skills_dir)
            if (skills_dir / entry).is_dir()
        )
        return {"skills": names}
    except OSError:
        return {"skills": []}


# DEPRECATED: use individual /api/actions/* endpoints instead
@app.post("/api/action")
def action(body: ActionRequest):
    start = time.time()

    def ok(o="", items=None):
        return {
            "status": "ok",
            "action": body.action,
            "output": o,
            "duration_ms": round((time.time() - start) * 1000),
            "items": items or []
        }

    def err(msg):
        return {
            "status": "error",
            "action": body.action,
            "output": msg,
            "duration_ms": round((time.time() - start) * 1000),
            "items": []
        }

    try:
        # ── QUICK CHECK ──
        if body.action == "quick":
            parts = []
            # Memory
            mem_path = Path.home() / ".hermes" / "memories" / "MEMORY.md"
            mem_pct = 0
            if mem_path.exists():
                content = mem_path.read_text()
                mem_pct = min(100, round(len(content) / 8000 * 100))
            parts.append(f"Memory {mem_pct}%")
            # Skills
            skills_dir = Path.home() / ".hermes" / "skills" / "holger"
            if skills_dir.is_dir():
                parts.append(f"Skills {len(os.listdir(skills_dir))}")
            # Updates (only check git fetch indicator, fast)
            hermes_dir = Path.home() / ".hermes" / "hermes-agent"
            if hermes_dir.is_dir():
                r = subprocess.run(
                    ["git", "-C", str(hermes_dir), "rev-list", "--count", "HEAD..origin/main"],
                    capture_output=True, text=True, timeout=5
                )
                n = int(r.stdout.strip() or "0")
                parts.append("Updates: " + (f"{n} neu" if n else "aktuell"))
            return ok("Alles ruhig — " + ", ".join(parts))

        # ── OLLAMA ──
        if body.action == "ollama":
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return err("Ollama nicht erreichbar — " + (result.stderr.strip() or "kein Output"))
            raw = result.stdout.strip()
            if not raw:
                return ok("Keine Modelle installiert")
            items = []
            for line in raw.split("\n")[1:]:  # skip header
                line = line.strip()
                if not line:
                    continue
                cols = line.split()
                if len(cols) >= 4:
                    items.append({"name": cols[0], "id": cols[1], "size": cols[2] + " " + cols[3], "modified": " ".join(cols[4:])})
                elif len(cols) >= 2:
                    items.append({"name": cols[0], "id": cols[1], "size": "", "modified": ""})
            return ok(f"{len(items)} Modelle", items)

        # ── CRONJOBS ──
        if body.action == "cronjobs":
            result = subprocess.run(["hermes", "cron", "list"], capture_output=True, text=True, timeout=10)
            raw = (result.stdout + result.stderr).strip()
            if not raw:
                return ok("Keine Cronjobs eingerichtet")
            items = []
            for line in raw.split("\n"):
                line = line.strip()
                if not line or line.startswith("===") or "NAME" in line.upper():
                    continue
                parts_line = [p.strip() for p in line.split("|")] if "|" in line else line.split()
                if len(parts_line) >= 2:
                    items.append({
                        "name": parts_line[0],
                        "schedule": parts_line[1] if len(parts_line) > 1 else "",
                        "next_run": parts_line[2] if len(parts_line) > 2 else "",
                        "last_run": parts_line[3] if len(parts_line) > 3 else "",
                        "status": "aktiv" if "ok" in line.lower() or "active" in line.lower() else "--"
                    })
                else:
                    items.append({"name": line, "schedule": "", "status": "--"})
            return ok(f"{len(items)} Cronjobs", items) if items else ok(raw)

        # ── SKILLS ──
        if body.action == "skills":
            skills_dir = Path.home() / ".hermes" / "skills" / "holger"
            if not skills_dir.is_dir():
                return err("Skills-Verzeichnis nicht gefunden")
            names = sorted(e for e in os.listdir(skills_dir) if (skills_dir / e).is_dir())
            items = [{"name": n} for n in names]
            return ok(f"{len(names)} Skills geladen", items)

        # ── MEMORY ──
        if body.action == "memory":
            mem_path = Path.home() / ".hermes" / "memories" / "MEMORY.md"
            if not mem_path.exists():
                return err("Memory-Datei nicht gefunden")
            content = mem_path.read_text()
            chars = len(content)
            pct = min(100, round(chars / 8000 * 100))
            return ok(f"Memory {pct}% · {chars} Zeichen", [])

        # ── UPDATE ──
        if body.action == "update":
            hermes_dir = Path.home() / ".hermes" / "hermes-agent"
            if not hermes_dir.is_dir():
                return err("Hermes nicht gefunden")
            # Fetch first for accurate count
            subprocess.run(["git", "-C", str(hermes_dir), "fetch", "origin"], capture_output=True, text=True, timeout=15)
            result = subprocess.run(
                ["git", "-C", str(hermes_dir), "log", "--oneline", "HEAD..origin/main"],
                capture_output=True, text=True, timeout=10
            )
            new = result.stdout.strip()
            if new:
                lines = new.split("\n")
                items = [{"name": l[:100]} for l in lines[:10]]
                return ok(f"{len(lines)} neue(r) Commit(s)", items)
            return ok("Hermes ist aktuell")

        # ── VOLLCHECK ──
        if body.action == "fullcheck":
            parts = []
            items = []
            # Memory
            mem_path = Path.home() / ".hermes" / "memories" / "MEMORY.md"
            mem_pct = 0
            if mem_path.exists():
                mem_pct = min(100, round(len(mem_path.read_text()) / 8000 * 100))
            parts.append(f"Memory {mem_pct}%")
            # Skills
            skills_dir = Path.home() / ".hermes" / "skills" / "holger"
            sk = len(os.listdir(skills_dir)) if skills_dir.is_dir() else 0
            parts.append(f"Skills {sk}")
            # Cronjobs
            try:
                cr = subprocess.run(["hermes", "cron", "list"], capture_output=True, text=True, timeout=10)
                cron_lines = [l for l in (cr.stdout + cr.stderr).strip().split("\n") if l.strip()]
                parts.append(f"Cronjobs {len(cron_lines)}")
            except Exception:
                parts.append("Cronjobs —")
            # Updates
            try:
                hermes_dir = Path.home() / ".hermes" / "hermes-agent"
                if hermes_dir.is_dir():
                    subprocess.run(["git", "-C", str(hermes_dir), "fetch", "origin"], capture_output=True, text=True, timeout=15)
                    r = subprocess.run(["git", "-C", str(hermes_dir), "rev-list", "--count", "HEAD..origin/main"], capture_output=True, text=True, timeout=10)
                    n = int(r.stdout.strip() or "0")
                    parts.append("Updates: " + (f"{n} neu" if n else "aktuell"))
            except Exception:
                parts.append("Updates: —")
            # Ollama
            try:
                ol = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
                ol_models = len([l for l in ol.stdout.strip().split("\n") if l.strip()]) - 1  # -1 header
                parts.append(f"Ollama {max(0, ol_models)} Modelle")
            except Exception:
                parts.append("Ollama —")
            return ok("Briefing erledigt — " + ", ".join(parts), items)

        return err("Unbekannte Aktion: " + body.action)

    except subprocess.TimeoutExpired:
        return err(body.action + ": Timeout nach 10 Sekunden")
    except FileNotFoundError as e:
        return err(body.action + ": Befehl nicht gefunden — " + str(e))
    except Exception as e:
        return err(body.action + ": " + str(e))


@app.get("/api/inbox")
def inbox():
    MAX_ITEMS = 30
    inbox_path = Path.home() / ".hermes" / "shared" / "inbox.md"
    if not inbox_path.exists():
        return {"entries": [], "note": "inbox.md nicht gefunden"}
    try:
        raw = inbox_path.read_text()
        entries = []
        for line in raw.strip().split("\\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("- "):
                line = line[2:]
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                title = parts[0] if len(parts) > 0 else line
                source = parts[1] if len(parts) > 1 else ""
                t = parts[2] if len(parts) > 2 else ""
            else:
                title, source, t = line, "", ""
            entries.append({"id": title[:40], "title": title, "source": source, "time": t})
        return {"entries": entries[:MAX_ITEMS]}
    except OSError as e:
        return {"entries": [], "note": str(e)}


# ── Dashboard-spezifische Endpunkte ─────────────────────────────────


_net_prev_bytes: dict | None = None
_net_prev_ts: float = 0


@app.get("/api/dashboard/status")
def dashboard_status():
    global _net_prev_bytes, _net_prev_ts

    try:
        import psutil
    except ImportError:
        return JSONResponse({"error": "psutil not installed"}, status_code=500)

    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    now = time.time()

    # Real OS uptime
    uptime_seconds = int(time.time() - psutil.boot_time())

    # Network rate (delta-based)
    net_rx_kbps = 0.0
    net_tx_kbps = 0.0
    current = {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv}
    if _net_prev_bytes and _net_prev_ts > 0:
        elapsed = now - _net_prev_ts
        if elapsed > 0:
            rx_delta = current["bytes_recv"] - _net_prev_bytes["bytes_recv"]
            tx_delta = current["bytes_sent"] - _net_prev_bytes["bytes_sent"]
            net_rx_kbps = round(rx_delta / elapsed / 1024, 1)
            net_tx_kbps = round(tx_delta / elapsed / 1024, 1)
    _net_prev_bytes = current
    _net_prev_ts = now

    return {
        "cpu_percent": round(cpu, 1),
        "ram_used_gb": round(ram.used / (1024**3), 1),
        "ram_total_gb": round(ram.total / (1024**3), 1),
        "ram_percent": ram.percent,
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_percent": disk.percent,
        "network_rx_kbps": net_rx_kbps,
        "network_tx_kbps": net_tx_kbps,
        "uptime_seconds": uptime_seconds,
    }


@app.get("/api/dashboard/cron")
def dashboard_cron():
    try:
        result = subprocess.run(
            [os.path.expanduser("~/.local/bin/hermes"), "cron", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {"connected": False, "message": "hermes cron list fehlgeschlagen", "jobs": []}

        jobs: list[dict] = []
        current: dict | None = None

        for line in result.stdout.strip().split("\n"):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))

            if not stripped or stripped.startswith("\u250c") or stripped.startswith("\u2502") or stripped.startswith("\u2514"):
                continue

            if indent == 2 and " " in stripped:
                parts = stripped.rsplit(" ", 1)
                job_id = parts[0]
                status = parts[1].strip("[]") if len(parts) > 1 and parts[1].startswith("[") else "unknown"
                current = {"id": job_id, "status": status}
                jobs.append(current)
                continue

            if current is not None and indent >= 4 and ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                if key == "name":
                    current["name"] = value
                elif key == "schedule":
                    current["schedule"] = value
                elif key == "next_run":
                    current["next_run"] = value
                elif key == "last_run":
                    current["last_run"] = value
                elif key == "skills":
                    current["skills"] = value
                elif key == "deliver":
                    current["deliver"] = value

        return {"connected": True, "jobs": jobs}

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"connected": False, "message": "hermes CLI nicht verfügbar oder Timeout", "jobs": []}
    except Exception as e:
        return {"connected": False, "message": str(e), "jobs": []}


@app.get("/api/dashboard/tasks")
def dashboard_tasks():
    MAX_TASKS = 50
    tasks_path = Path.home() / ".hermes" / "tasks.json"
    if not tasks_path.exists():
        return {"connected": False, "message": "tasks.json nicht gefunden", "tasks": []}
    try:
        tasks_data = json.loads(tasks_path.read_text())
        tasks = tasks_data if isinstance(tasks_data, list) else tasks_data.get("tasks", [])
        return {"connected": True, "tasks": tasks[:MAX_TASKS]}
    except (json.JSONDecodeError, OSError):
        return {"connected": False, "message": "tasks.json nicht lesbar", "tasks": []}


@app.get("/api/dashboard/inbox")
def dashboard_inbox():
    MAX_ITEMS = 30
    inbox_path = Path.home() / ".hermes" / "shared" / "inbox.md"
    if not inbox_path.exists():
        return {"connected": False, "message": "inbox.md nicht gefunden", "entries": []}
    try:
        raw = inbox_path.read_text()
        entries = []
        for i, line in enumerate(raw.strip().split("\n")):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Strip status markers: [x] [o] [>]
            status = "new"
            for marker, st in [("[x]", "done"), ("[o]", "seen"), ("[>]", "later")]:
                if line.startswith(marker + " "):
                    status = st
                    line = line[len(marker) + 1:].strip()
                    break
            if line.startswith("- "):
                line = line[2:]
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                title = parts[0] if len(parts) > 0 else line
                source = parts[1] if len(parts) > 1 else ""
                t = parts[2] if len(parts) > 2 else ""
            else:
                title, source, t = line, "", ""
            entries.append({"id": title[:40], "title": title, "source": source, "time": t, "status": status, "line_index": i})
        return {"connected": True, "entries": entries[:MAX_ITEMS]}
    except OSError as e:
        return {"connected": False, "message": str(e), "entries": []}


@app.get("/api/dashboard/news")
def dashboard_news():
    MAX_ITEMS = 20
    news_path = Path.home() / ".hermes" / "news" / "latest.json"
    if not news_path.exists():
        return {"connected": False, "message": "Backend-Hook fehlt", "news": []}
    try:
        data = json.loads(news_path.read_text())
        news = data if isinstance(data, list) else data.get("news", data.get("items", []))
        return {"connected": True, "news": news[:MAX_ITEMS]}
    except (json.JSONDecodeError, OSError):
        return {"connected": False, "message": "latest.json nicht lesbar", "news": []}


# ── Einzel-Action-Endpunkte ────────────────────────────────────────


def _acquire_action_lock(action_name: str) -> dict | None:
    """Try to acquire the global action lock. Returns None on success, or a 'busy' response dict."""
    if _action_lock.acquire(blocking=False):
        return None
    return {"status": "busy", "action": action_name,
            "output": "Aktion blockiert – eine andere läuft bereits",
            "duration_ms": 0, "items": []}


@app.post("/api/actions/ollama")
def action_ollama():
    busy = _acquire_action_lock("ollama")
    if busy:
        return busy
    try:
        start = time.time()
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return {"status": "error", "action": "ollama", "output": "Ollama nicht erreichbar", "duration_ms": round((time.time() - start) * 1000), "items": []}
            raw = result.stdout.strip()
            if not raw:
                return {"status": "ok", "action": "ollama", "output": "Keine Modelle installiert", "duration_ms": round((time.time() - start) * 1000), "items": []}
            items = []
            for line in raw.split("\n")[1:]:
                line = line.strip()
                if not line:
                    continue
                cols = line.split()
                if len(cols) >= 4:
                    items.append({"name": cols[0], "id": cols[1], "size": cols[2] + " " + cols[3], "modified": " ".join(cols[4:])})
                elif len(cols) >= 2:
                    items.append({"name": cols[0], "id": cols[1], "size": "", "modified": ""})
            return {"status": "ok", "action": "ollama", "output": f"{len(items)} Modelle", "duration_ms": round((time.time() - start) * 1000), "items": items}
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return {"status": "error", "action": "ollama", "output": f"Ollama nicht erreichbar: {e}", "duration_ms": round((time.time() - start) * 1000), "items": []}
        except Exception as e:
            return {"status": "error", "action": "ollama", "output": str(e), "duration_ms": round((time.time() - start) * 1000), "items": []}
    finally:
        _action_lock.release()


@app.post("/api/actions/cronjobs")
def action_cronjobs():
    busy = _acquire_action_lock("cronjobs")
    if busy:
        return busy
    try:
        start = time.time()
        try:
            result = subprocess.run(["hermes", "cron", "list"], capture_output=True, text=True, timeout=10)
            raw = (result.stdout + result.stderr).strip()
            if not raw and result.returncode != 0:
                return {"status": "error", "action": "cronjobs", "output": "Hermes CLI nicht verfügbar", "duration_ms": round((time.time() - start) * 1000), "items": []}
            if not raw:
                return {"status": "ok", "action": "cronjobs", "output": "Keine Cronjobs eingerichtet", "duration_ms": round((time.time() - start) * 1000), "items": []}
            items = []
            for line in raw.split("\n"):
                line = line.strip()
                if not line or line.startswith("===") or "NAME" in line.upper():
                    continue
                parts_line = [p.strip() for p in line.split("|")] if "|" in line else line.split()
                if len(parts_line) >= 2:
                    items.append({
                        "name": parts_line[0],
                        "schedule": parts_line[1] if len(parts_line) > 1 else "",
                        "next_run": parts_line[2] if len(parts_line) > 2 else "",
                        "last_run": parts_line[3] if len(parts_line) > 3 else "",
                        "status": "aktiv" if "ok" in line.lower() or "active" in line.lower() else "--"
                    })
                else:
                    items.append({"name": line, "schedule": "", "status": "--"})
            return {"status": "ok", "action": "cronjobs", "output": f"{len(items)} Cronjobs", "duration_ms": round((time.time() - start) * 1000), "items": items}
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {"status": "error", "action": "cronjobs", "output": "Hermes CLI nicht verfügbar oder Timeout", "duration_ms": round((time.time() - start) * 1000), "items": []}
        except Exception as e:
            return {"status": "error", "action": "cronjobs", "output": str(e), "duration_ms": round((time.time() - start) * 1000), "items": []}
    finally:
        _action_lock.release()


@app.post("/api/actions/skills")
def action_skills():
    busy = _acquire_action_lock("skills")
    if busy:
        return busy
    try:
        start = time.time()
        skills_dir = Path.home() / ".hermes" / "skills" / "holger"
        if not skills_dir.is_dir():
            return {"status": "error", "action": "skills", "output": "Skills-Verzeichnis nicht gefunden", "duration_ms": round((time.time() - start) * 1000), "items": []}
        try:
            names = sorted(e for e in os.listdir(skills_dir) if (skills_dir / e).is_dir())
            items = [{"name": n} for n in names]
            return {"status": "ok", "action": "skills", "output": f"{len(names)} Skills geladen", "duration_ms": round((time.time() - start) * 1000), "items": items}
        except OSError:
            return {"status": "error", "action": "skills", "output": "Skills-Verzeichnis nicht lesbar", "duration_ms": round((time.time() - start) * 1000), "items": []}
    finally:
        _action_lock.release()


@app.post("/api/actions/memory")
def action_memory():
    busy = _acquire_action_lock("memory")
    if busy:
        return busy
    try:
        start = time.time()
        mem_path = Path.home() / ".hermes" / "memories" / "MEMORY.md"
        if not mem_path.exists():
            return {"status": "error", "action": "memory", "output": "Memory-Datei nicht gefunden", "duration_ms": round((time.time() - start) * 1000), "items": []}
        try:
            content = mem_path.read_text()
            chars = len(content)
            pct = min(100, round(chars / 8000 * 100))
            return {"status": "ok", "action": "memory", "output": f"Memory {pct}% · {chars} Zeichen", "duration_ms": round((time.time() - start) * 1000), "items": []}
        except OSError:
            return {"status": "error", "action": "memory", "output": "Memory-Datei nicht lesbar", "duration_ms": round((time.time() - start) * 1000), "items": []}
    finally:
        _action_lock.release()


@app.post("/api/actions/update")
def action_update():
    busy = _acquire_action_lock("update")
    if busy:
        return busy
    try:
        start = time.time()
        hermes_dir = Path.home() / ".hermes" / "hermes-agent"
        if not hermes_dir.is_dir():
            return {"status": "error", "action": "update", "output": "Hermes-Verzeichnis nicht gefunden", "duration_ms": round((time.time() - start) * 1000), "items": []}
        try:
            # Nur Dry-Run: fetch + log count, kein pull
            subprocess.run(["git", "-C", str(hermes_dir), "fetch", "origin"], capture_output=True, text=True, timeout=15)
            result = subprocess.run(
                ["git", "-C", str(hermes_dir), "log", "--oneline", "HEAD..origin/main"],
                capture_output=True, text=True, timeout=10
            )
            new = result.stdout.strip()
            if new:
                lines = new.split("\n")
                items = [{"name": l[:100]} for l in lines[:10]]
                return {"status": "ok", "action": "update", "output": f"{len(lines)} neue(r) Commit(s) · Nur Dry-Run, kein Update ausgeführt", "duration_ms": round((time.time() - start) * 1000), "items": items}
            return {"status": "ok", "action": "update", "output": "Hermes ist aktuell · Kein Update nötig", "duration_ms": round((time.time() - start) * 1000), "items": []}
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {"status": "error", "action": "update", "output": "Git nicht verfügbar oder Timeout", "duration_ms": round((time.time() - start) * 1000), "items": []}
        except Exception as e:
            return {"status": "error", "action": "update", "output": str(e), "duration_ms": round((time.time() - start) * 1000), "items": []}
    finally:
        _action_lock.release()


@app.post("/api/actions/quick")
def action_quick():
    busy = _acquire_action_lock("quick")
    if busy:
        return busy
    try:
        start = time.time()
        items = []
        # Memory
        mem_path = Path.home() / ".hermes" / "memories" / "MEMORY.md"
        mem_pct = 0
        if mem_path.exists():
            try:
                content = mem_path.read_text()
                mem_pct = min(100, round(len(content) / 8000 * 100))
            except OSError:
                pass
        items.append({"label": "Memory", "value": f"{mem_pct}%"})
        # Skills
        skills_dir = Path.home() / ".hermes" / "skills" / "holger"
        sk = 0
        if skills_dir.is_dir():
            try:
                sk = len(os.listdir(skills_dir))
            except OSError:
                pass
        items.append({"label": "Skills", "value": str(sk)})
        # Updates: only check git fetch indicator via rev-list (fast, no fetch)
        updates_val = "—"
        hermes_dir = Path.home() / ".hermes" / "hermes-agent"
        if hermes_dir.is_dir():
            try:
                r = subprocess.run(
                    ["git", "-C", str(hermes_dir), "rev-list", "--count", "HEAD..origin/main"],
                    capture_output=True, text=True, timeout=5
                )
                n = int(r.stdout.strip() or "0")
                updates_val = f"{n} neu" if n else "aktuell"
            except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
                pass
        items.append({"label": "Updates", "value": updates_val})
        return {"status": "ok", "action": "quick",
                "output": "Alles ruhig",
                "duration_ms": round((time.time() - start) * 1000), "items": items}
    finally:
        _action_lock.release()


@app.post("/api/actions/fullcheck")
def action_fullcheck():
    busy = _acquire_action_lock("fullcheck")
    if busy:
        return busy
    try:
        start = time.time()
        items = []
        # Memory
        mem_path = Path.home() / ".hermes" / "memories" / "MEMORY.md"
        mem_pct = 0
        if mem_path.exists():
            try:
                mem_pct = min(100, round(len(mem_path.read_text()) / 8000 * 100))
            except OSError:
                pass
        items.append({"label": "Memory", "value": f"{mem_pct}%"})
        # Skills
        skills_dir = Path.home() / ".hermes" / "skills" / "holger"
        sk = 0
        try:
            sk = len(os.listdir(skills_dir)) if skills_dir.is_dir() else 0
        except OSError:
            pass
        items.append({"label": "Skills", "value": str(sk)})
        # Cronjobs
        cron_val = "—"
        try:
            cr = subprocess.run(["hermes", "cron", "list"], capture_output=True, text=True, timeout=10)
            cron_count = len([l for l in (cr.stdout + cr.stderr).strip().split("\n") if l.strip()])
            cron_val = str(cron_count)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        items.append({"label": "Cronjobs", "value": cron_val})
        # Updates (Dry-Run)
        updates_val = "—"
        hermes_dir = Path.home() / ".hermes" / "hermes-agent"
        if hermes_dir.is_dir():
            try:
                subprocess.run(["git", "-C", str(hermes_dir), "fetch", "origin"],
                               capture_output=True, text=True, timeout=15)
                r = subprocess.run(
                    ["git", "-C", str(hermes_dir), "rev-list", "--count", "HEAD..origin/main"],
                    capture_output=True, text=True, timeout=10
                )
                n = int(r.stdout.strip() or "0")
                updates_val = f"{n} neu" if n else "aktuell"
            except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
                pass
        items.append({"label": "Updates", "value": updates_val})
        # Ollama
        ollama_val = "—"
        try:
            ol = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
            ol_count = max(0, len([l for l in ol.stdout.strip().split("\n") if l.strip()]) - 1)
            ollama_val = str(ol_count)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        items.append({"label": "Ollama", "value": ollama_val})
        return {"status": "ok", "action": "fullcheck",
                "output": "Briefing erledigt",
                "duration_ms": round((time.time() - start) * 1000), "items": items}
    finally:
        _action_lock.release()


@app.post("/api/actions/inbox")
def action_inbox(body: dict):
    """Update status of an inbox entry by title match."""
    busy = _acquire_action_lock("inbox")
    if busy:
        return busy
    try:
        start = time.time()
        inbox_path = Path.home() / ".hermes" / "shared" / "inbox.md"
        if not inbox_path.exists():
            return {"status": "error", "action": "inbox",
                    "output": "inbox.md nicht gefunden",
                    "duration_ms": round((time.time() - start) * 1000), "items": []}

        action_type = body.get("action", "seen")
        entry_title = body.get("title", "")

        if not entry_title:
            return {"status": "error", "action": "inbox",
                    "output": "title fehlt",
                    "duration_ms": round((time.time() - start) * 1000), "items": []}

        try:
            raw = inbox_path.read_text()
        except OSError:
            return {"status": "error", "action": "inbox",
                    "output": "Datei nicht lesbar",
                    "duration_ms": round((time.time() - start) * 1000), "items": []}

        lines = raw.split("\n")
        found = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Strip existing markers
            for marker in ["[x]", "[o]", "[>]"]:
                if stripped.startswith(marker + " "):
                    stripped = stripped[len(marker) + 1:].strip()
                    break
            if stripped.startswith("- "):
                stripped = stripped[2:].strip()
            # Check if this line contains our title
            if entry_title in stripped or stripped == entry_title:
                # Remove existing markers, apply new one
                clean = line
                for marker in ["[x] ", "[o] ", "[>] "]:
                    pl = len(line) - len(line.lstrip())
                    if line.lstrip().startswith(marker):
                        clean = line[:pl] + line[pl:].replace(marker, "", 1).lstrip()
                        break
                marker_map = {"done": "[x]", "later": "[>]", "seen": "[o]"}
                marker = marker_map.get(action_type, "[o]")
                leading = " " * (len(line) - len(line.lstrip()))
                lines[i] = leading + marker + " " + clean.lstrip()
                found = True
                break

        if not found:
            return {"status": "error", "action": "inbox",
                    "output": "Eintrag nicht gefunden",
                    "duration_ms": round((time.time() - start) * 1000), "items": []}

        try:
            inbox_path.write_text("\n".join(lines))
        except OSError:
            return {"status": "error", "action": "inbox",
                    "output": "Datei nicht schreibbar",
                    "duration_ms": round((time.time() - start) * 1000), "items": []}

        return {"status": "ok", "action": "inbox",
                "output": f"Status {action_type} gesetzt",
                "duration_ms": round((time.time() - start) * 1000),
                "items": [{"label": "Status", "value": action_type}]}
    finally:
        _action_lock.release()


# ── Spotlight / Christian ──────────────────────────────────────────

OBSIDIAN_VAULT = Path.home() / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents" / "Obsidian-mobile"
SPOTLIGHT_DIR = OBSIDIAN_VAULT / "4_Ressourcen" / "Recherchen" / "KI-News-Analysen"
SPOTLIGHT_MAX_CHARS = 12000
SPOTLIGHT_MAX_FILES = 20


def _find_newest_spotlight() -> Path | None:
    """Find the newest Markdown file in the Spotlight directory."""
    if not SPOTLIGHT_DIR.is_dir():
        return None
    md_files = sorted(
        (p for p in SPOTLIGHT_DIR.iterdir() if p.suffix == ".md" and p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:SPOTLIGHT_MAX_FILES]
    return md_files[0] if md_files else None


def _parse_frontmatter(text: str) -> dict:
    """Parse simple YAML-like frontmatter between --- markers."""
    result: dict = {}
    if not text.startswith("---"):
        return result
    end = text.find("---", 3)
    if end == -1:
        return result
    block = text[3:end].strip()
    for line in block.split("\n"):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip("'\"").strip("[]")
        if value:
            result[key] = value
    return result


@app.post("/api/actions/spotlight")
def action_spotlight():
    busy = _acquire_action_lock("spotlight")
    if busy:
        return busy
    try:
        start = time.time()
        path = _find_newest_spotlight()
        if not path:
            return {"status": "error", "action": "spotlight",
                    "output": "Keine Spotlight-Notiz gefunden",
                    "duration_ms": round((time.time() - start) * 1000), "items": []}

        try:
            raw = path.read_text()
        except OSError:
            return {"status": "error", "action": "spotlight",
                    "output": "Datei nicht lesbar: " + str(path),
                    "duration_ms": round((time.time() - start) * 1000), "items": []}

        fm = _parse_frontmatter(raw)

        # Extract body (after frontmatter, skip first heading)
        end_fm = raw.find("---", 3)
        body = raw[end_fm + 3:].strip() if end_fm != -1 else raw
        # Remove leading # Title line
        if body.startswith("# "):
            nl = body.find("\n")
            title = body[2:nl].strip() if nl != -1 else body[2:].strip()
            body = body[nl + 1:].strip() if nl != -1 else ""
        else:
            title = path.stem

        # Limit body
        body = body[:SPOTLIGHT_MAX_CHARS]

        items = [
            {"label": "Titel", "value": title},
            {"label": "Datum", "value": fm.get("date", "—")},
            {"label": "Quelle", "value": fm.get("source", "—")},
            {"label": "Autor", "value": fm.get("autor", "—")},
            {"label": "Relevanz", "value": fm.get("relevanz", "—") + "/100"},
            {"label": "Hermes", "value": fm.get("hermes_impact", "—")},
            {"label": "Zeichen", "value": str(len(raw))},
        ]

        return {"status": "ok", "action": "spotlight",
                "output": title,
                "duration_ms": round((time.time() - start) * 1000),
                "items": items,
                "body": body}
    finally:
        _action_lock.release()


@app.post("/api/actions/christian")
def action_christian():
    busy = _acquire_action_lock("christian")
    if busy:
        return busy
    try:
        start = time.time()
        path = _find_newest_spotlight()
        if not path:
            return {"status": "error", "action": "christian",
                    "output": "Keine Spotlight-Notiz gefunden",
                    "duration_ms": round((time.time() - start) * 1000), "items": []}

        try:
            raw = path.read_text()
        except OSError:
            return {"status": "error", "action": "christian",
                    "output": "Datei nicht lesbar",
                    "duration_ms": round((time.time() - start) * 1000), "items": []}

        fm = _parse_frontmatter(raw)
        end_fm = raw.find("---", 3)
        body = raw[end_fm + 3:].strip() if end_fm != -1 else raw

        if body.startswith("# "):
            nl = body.find("\n")
            title = body[2:nl].strip() if nl != -1 else body[2:].strip()
            body = body[nl + 1:].strip() if nl != -1 else ""
        else:
            title = path.stem

        # Limit body for the prompt
        body = body[:SPOTLIGHT_MAX_CHARS]

        # Extract structured sections from body
        def _first_paragraph(text: str) -> str:
            """First non-empty, non-heading paragraph."""
            for para in text.split("\n\n"):
                stripped = para.strip()
                if stripped and not stripped.startswith("##"):
                    return stripped[:300]
            return ""

        def _extract_section(text: str, heading: str) -> str:
            """Extract content under a ## heading."""
            idx = text.find(f"## {heading}")
            if idx == -1:
                return ""
            section = text[idx + len(heading) + 3:].strip()
            # Stop at next ## heading
            next_idx = section.find("\n## ")
            if next_idx != -1:
                section = section[:next_idx].strip()
            return section[:300]

        kontext = _first_paragraph(body)

        # Kernpunkt: first bullet from Kernaussagen or first line from Relevanz
        kern = _extract_section(body, "Kernaussagen")
        if kern:
            # Take first bullet item
            for line in kern.split("\n"):
                line = line.strip()
                if line.startswith("- **") or line.startswith("- "):
                    kern = line.lstrip("- ").strip()[:250]
                    break
            else:
                kern = kern[:250]
        if not kern:
            kern = _extract_section(body, "Relevanz für Hermes") or _extract_section(body, "Relevanz")

        # Generate Frage and Ziel from topic
        frage = f"Wie übertragbar ist dieses Konzept auf unsere Arbeit mit Hermes?"
        ziel = "Konkrete Einschätzung zur Umsetzbarkeit und nächsten Schritten."

        prompt = (
            f"KONTEXT:\n{kontext}\n\n"
            f"KERNPUNKT:\n{kern}\n\n"
            f"FRAGE AN CHRISTIAN:\n{frage}\n\n"
            f"ZIEL:\n{ziel}\n\n"
            f"---\n"
            f"Quelle: {fm.get('source', '—')}\n"
            f"Pfad: {path}\n"
        )

        # Truncate if too long
        if len(prompt) > SPOTLIGHT_MAX_CHARS:
            prompt = prompt[:SPOTLIGHT_MAX_CHARS] + "\n… [gekürzt]"

        return {"status": "ok", "action": "christian",
                "output": title,
                "duration_ms": round((time.time() - start) * 1000),
                "items": [{"label": "Titel", "value": title},
                          {"label": "Datum", "value": fm.get("date", "—")},
                          {"label": "Quelle", "value": fm.get("source", "—")},
                          {"label": "Pfad", "value": str(path)}],
                "prompt": prompt}
    finally:
        _action_lock.release()
