from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients: set[WebSocket] = set()


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
        "message": f"Test-Event triggered at {datetime.datetime.now().isoformat()}",
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
    }
    disconnected: list[WebSocket] = []
    for ws in connected_clients:
        try:
            await ws.send_json(event)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.discard(ws)

    return JSONResponse({
        "status": "broadcast",
        "clients_count": len(connected_clients),
        "event": event,
    })
