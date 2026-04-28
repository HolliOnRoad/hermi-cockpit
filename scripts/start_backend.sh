#!/bin/bash

echo "🚀 Starte Hermi Cockpit Backend..."

cd ~/Claude\ Projekt/hermi-cockpit/backend || exit

source venv/bin/activate

echo "📡 Backend läuft auf http://127.0.0.1:8000"

uvicorn api.main:app --reload
