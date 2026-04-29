from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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


def now_ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


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
            "gateway_state": data.get("state", "unknown"),
            "active_agents": data.get("active_agents", []),
            "updated_at": data.get("updated_at", ""),
        }
    except (json.JSONDecodeError, OSError):
        return JSONResponse(
            {"error": "failed to read gateway_state.json"},
            status_code=500,
        )
