import asyncio
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
import time
import urllib.request
import urllib.error

from services.hermes_log_stream import get_log_stream
from services.hermes_api_bridge import run_query as hermes_run_query

GATEWAY_STATE_PATH = Path.home() / ".hermes" / "gateway_state.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    stream = get_log_stream()
    stream.set_broadcast(broadcast_event)
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

connected_clients: set[WebSocket] = set()

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


def now_ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


async def _run_query(text: str):
    global _query_running
    _query_running = True
    try:
        await broadcast_event({
            "type": "query",
            "level": "info",
            "source": "system",
            "message": f"Hermes Query gestartet: {text[:60]}",
            "timestamp": now_ts(),
        })
        await hermes_run_query(text, broadcast_event)
    finally:
        _query_running = False


async def broadcast_event(event: dict) -> int:
    disconnected: list[WebSocket] = []
    count = 0
    for ws in connected_clients:
        try:
            await ws.send_json(event)
            count += 1
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.discard(ws)
    return count


@app.get("/")
def root():
    return {"status": "Hermi Cockpit Backend läuft 🚀"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.datetime.now().isoformat()
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    print(f"Client connected ({len(connected_clients)} total)")
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected_clients.discard(ws)
        print(f"Client disconnected ({len(connected_clients)} total)")


@app.get("/test-event")
async def test_event():
    event = {
        "type": "test_event",
        "level": "info",
        "source": "system",
        "message": f"Test-Event triggered at {datetime.datetime.now().isoformat()}",
        "timestamp": now_ts(),
    }
    count = await broadcast_event(event)
    return JSONResponse({
        "status": "broadcast",
        "clients_count": len(connected_clients),
        "broadcast_count": count,
        "event": event,
    })


@app.post("/events")
async def ingest_event(event: Event):
    payload = event.model_dump()
    if not payload.get("timestamp"):
        payload["timestamp"] = now_ts()

    count = await broadcast_event(payload)
    print(f"[Event] type={event.type} level={event.level} source={event.source} "
          f"→ {count} clients")

    return JSONResponse({
        "status": "broadcast" if count > 0 else "stored",
        "clients_count": len(connected_clients),
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

    cpu = psutil.cpu_percent(interval=0.1)
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


@app.get("/api/memory")
def memory():
    memory_path = Path.home() / ".hermes" / "memories" / "MEMORY.md"
    if not memory_path.exists():
        return {"content": "", "memory_chars": 0, "user_chars": 0,
                "total_chars": 0, "memory_pct": 0, "user_pct": 0, "entries": 0}
    try:
        text = memory_path.read_text()
    except OSError:
        return {"content": "", "memory_chars": 0, "user_chars": 0,
                "total_chars": 0, "memory_pct": 0, "user_pct": 0, "entries": 0}

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

    return {
        "content": text,
        "memory_chars": memory_chars,
        "user_chars": user_chars,
        "total_chars": total_chars,
        "memory_pct": memory_pct,
        "user_pct": user_pct,
        "entries": entries,
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
            ["hermes", "cron", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            print(f"[Cron] hermes cronjob list fehlgeschlagen: {result.stderr.strip()}")
            return {"jobs": []}

        jobs: list[dict] = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("---") or line.startswith("ID"):
                continue
            parts = line.split()
            if len(parts) >= 4:
                jobs.append({
                    "id": parts[0],
                    "name": " ".join(parts[1:-2]),
                    "schedule": parts[-2],
                    "status": parts[-1],
                })
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
    news_path = Path.home() / ".hermes" / "news" / "latest.json"
    if not news_path.exists():
        return {"news": []}
    try:
        return {"news": json.loads(news_path.read_text())}
    except (json.JSONDecodeError, OSError):
        return {"news": []}


@app.get("/api/tasks")
def tasks():
    tasks_path = Path.home() / ".hermes" / "tasks.json"
    if not tasks_path.exists():
        return {"tasks": []}
    try:
        return {"tasks": json.loads(tasks_path.read_text())}
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
