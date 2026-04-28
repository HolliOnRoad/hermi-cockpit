from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Literal
import datetime

app = FastAPI()

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
