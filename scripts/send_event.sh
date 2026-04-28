#!/bin/bash

# send_event.sh – Hermi Cockpit Event Sender
#
# Usage:
#   ./scripts/send_event.sh "Message text"
#   ./scripts/send_event.sh "Tool call" --type tool
#   ./scripts/send_event.sh "Error occurred" --level error
#
# Defaults: type=log, level=info, source=hermi

MESSAGE="${1:?Usage: $0 \"message\" [--type type] [--level level] [--source source]}"
shift

TYPE="log"
LEVEL="info"
SOURCE="hermi"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)   TYPE="$2"; shift 2 ;;
        --level)  LEVEL="$2"; shift 2 ;;
        --source) SOURCE="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

curl -s -X POST http://127.0.0.1:8000/events \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"$TYPE\",
    \"level\": \"$LEVEL\",
    \"source\": \"$SOURCE\",
    \"message\": \"$MESSAGE\"
  }" | python3 -m json.tool
