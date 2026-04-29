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

from services.hermes_log_stream import get_log_stream

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


class QueryRequest(BaseModel):
    text: str


QUERY_TIMEOUT = 120


def now_ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


async def _run_query(text: str):
    global _query_running
    start_ts = now_ts()

    await broadcast_event({
        "type": "query",
        "level": "info",
        "source": "system",
        "message": f"Hermes Query gestartet: {text[:60]}",
        "timestamp": start_ts,
    })

    try:
        process = await asyncio.create_subprocess_exec(
            "hermes", "-q", text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def read_stream(stream, is_stderr: bool):
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip("\n")
                if decoded:
                    event = {
                        "type": "error" if is_stderr else "log",
                        "level": "error" if is_stderr else "info",
                        "source": "hermes",
                        "message": decoded,
                        "timestamp": now_ts(),
                    }
                    await broadcast_event(event)

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    read_stream(process.stdout, False),
                    read_stream(process.stderr, True),
                    process.wait(),
                ),
                timeout=QUERY_TIMEOUT,
            )
        except asyncio.TimeoutError:
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass
            await broadcast_event({
                "type": "error",
                "level": "error",
                "source": "system",
                "message": "Query fehlgeschlagen: Timeout",
                "timestamp": now_ts(),
                "meta": {"timeout": QUERY_TIMEOUT},
            })
            return

        if process.returncode == 0:
            await broadcast_event({
                "type": "query",
                "level": "success",
                "source": "system",
                "message": "Query abgeschlossen",
                "timestamp": now_ts(),
            })
        else:
            await broadcast_event({
                "type": "error",
                "level": "error",
                "source": "system",
                "message": f"Query fehlgeschlagen: {process.returncode}",
                "timestamp": now_ts(),
                "meta": {"returncode": process.returncode},
            })

    except FileNotFoundError:
        await broadcast_event({
            "type": "error",
            "level": "error",
            "source": "system",
            "message": "hermes CLI nicht gefunden",
            "timestamp": now_ts(),
        })
    except Exception as e:
        await broadcast_event({
            "type": "error",
            "level": "error",
            "source": "system",
            "message": f"Query fehlgeschlagen: {str(e)}",
            "timestamp": now_ts(),
        })
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
    if not GATEWAY_STATE_PATH.exists():
        return JSONResponse(
            {"error": "gateway_state.json not found"},
            status_code=404,
        )

    try:
        data = json.loads(GATEWAY_STATE_PATH.read_text())
        return {
            "gateway_state": data.get("gateway_state", "unknown"),
            "active_agents_count": int(data.get("active_agents", 0)),
            "updated_at": data.get("updated_at", ""),
        }
    except (json.JSONDecodeError, OSError):
        return JSONResponse(
            {"error": "failed to read gateway_state.json"},
            status_code=500,
        )


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
    memory_path = Path.home() / ".hermes" / "learnings.md"
    if not memory_path.exists():
        return {"content": ""}
    try:
        return {"content": memory_path.read_text()}
    except OSError:
        return {"content": ""}


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
