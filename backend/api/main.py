from fastapi import FastAPI
from fastapi.responses import JSONResponse
import datetime

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Hermi Cockpit Backend läuft 🚀"}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.datetime.now().isoformat()
    }
