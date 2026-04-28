#!/bin/bash

set -e

PROJECT_DIR="$HOME/Claude Projekt/hermi-cockpit"
BACKEND_PORT=8000
FRONTEND_PORT=5173

cd "$PROJECT_DIR" || exit 1

mkdir -p logs

# ---- Farb-Ausgabe ----
green() { printf "\033[32m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }
red() { printf "\033[31m%s\033[0m\n" "$1"; }
bold() { printf "\033[1m%s\033[0m\n" "$1"; }

bold "=== Hermi Cockpit Starter ==="
echo ""

# ---- Backend ----
if lsof -ti :$BACKEND_PORT &>/dev/null; then
    yellow "[Backend]  Port $BACKEND_PORT bereits belegt – ueberspringe Start."
else
    echo "[Backend]  Starte auf Port $BACKEND_PORT ..."
    cd "$PROJECT_DIR/backend"
    source venv/bin/activate
    nohup uvicorn api.main:app --reload --host 127.0.0.1 --port $BACKEND_PORT \
        > "$PROJECT_DIR/logs/backend.log" 2>&1 &
    echo $! > "$PROJECT_DIR/logs/backend.pid"
    green "[Backend]  Gestartet (PID $(cat "$PROJECT_DIR/logs/backend.pid"))"
fi

# ---- Frontend ----
if lsof -ti :$FRONTEND_PORT &>/dev/null; then
    yellow "[Frontend] Port $FRONTEND_PORT bereits belegt – ueberspringe Start."
else
    echo "[Frontend] Starte auf Port $FRONTEND_PORT ..."
    cd "$PROJECT_DIR/frontend"
    nohup npm run dev \
        > "$PROJECT_DIR/logs/frontend.log" 2>&1 &
    echo $! > "$PROJECT_DIR/logs/frontend.pid"
    green "[Frontend] Gestartet (PID $(cat "$PROJECT_DIR/logs/frontend.pid"))"
fi

# ---- Warten auf Bereitschaft ----
echo ""
echo "[Wait]     Warte auf Dienste..."

for i in $(seq 1 30); do
    backend_ok=0
    frontend_ok=0
    curl -s "http://127.0.0.1:$BACKEND_PORT/health" &>/dev/null && backend_ok=1
    curl -s "http://localhost:$FRONTEND_PORT" &>/dev/null && frontend_ok=1

    if [ "$backend_ok" = "1" ] && [ "$frontend_ok" = "1" ]; then
        break
    fi
    sleep 1
done

if [ "$backend_ok" = "1" ]; then
    green "[Backend]  http://127.0.0.1:$BACKEND_PORT/health  -> OK"
else
    red "[Backend]  http://127.0.0.1:$BACKEND_PORT/health  -> NICHT ERREICHBAR"
fi

if [ "$frontend_ok" = "1" ]; then
    green "[Frontend] http://localhost:$FRONTEND_PORT       -> OK"
else
    red "[Frontend] http://localhost:$FRONTEND_PORT       -> NICHT ERREICHBAR"
fi

# ---- Browser ----
echo ""
echo "[Browser]  Oeffne http://localhost:$FRONTEND_PORT ..."
open "http://localhost:$FRONTEND_PORT"

echo ""
bold "=== Hermi Cockpit laeuft ==="
echo ""
echo "  Backend:  http://127.0.0.1:$BACKEND_PORT"
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Logs:     $PROJECT_DIR/logs/"
echo ""

# Clean exit – keep terminal open for .command wrapper
exit 0
