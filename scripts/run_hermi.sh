#!/bin/bash

# run_hermi.sh – Startet den Hermi CLI-Agenten mit aktiviertem Cockpit-Tracking
#
# Voraussetzung: Hermi Cockpit Backend muss laufen (Port 8000)
# Starten via: ./scripts/start_hermi_cockpit.sh

cd "$(dirname "$0")/.." || exit 1

cd backend || exit 1
source venv/bin/activate

echo "Hermi CLI Agent (Events -> Cockpit http://127.0.0.1:8000)"
echo ""

python -m hermi.cli
