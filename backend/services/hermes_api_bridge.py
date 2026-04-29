import asyncio
import datetime
import json

import httpx

HERMES_API_URL = "http://127.0.0.1:8642"
HERMES_API_KEY = "hermi-local"
HEADERS = {"Authorization": f"Bearer {HERMES_API_KEY}"}
QUERY_TIMEOUT = 120


def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


async def run_query(text: str, broadcast_fn) -> None:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5, read=QUERY_TIMEOUT, write=10, pool=5)
        ) as client:
            r = await client.post(
                f"{HERMES_API_URL}/v1/runs",
                json={"input": text},
                headers=HEADERS,
            )
            if r.status_code != 200:
                await broadcast_fn({
                    "type": "error",
                    "level": "error",
                    "source": "system",
                    "message": f"Hermes API Fehler (POST /v1/runs): {r.status_code}",
                    "timestamp": _ts(),
                })
                return

            data = r.json()
            run_id = data.get("run_id")
            if not run_id:
                await broadcast_fn({
                    "type": "error",
                    "level": "error",
                    "source": "system",
                    "message": "Kein run_id in API-Response",
                    "timestamp": _ts(),
                })
                return

            async with client.stream(
                "GET",
                f"{HERMES_API_URL}/v1/runs/{run_id}/events",
                headers=HEADERS,
            ) as response:
                if response.status_code != 200:
                    await broadcast_fn({
                        "type": "error",
                        "level": "error",
                        "source": "system",
                        "message": f"Hermes SSE Stream Fehler: {response.status_code}",
                        "timestamp": _ts(),
                    })
                    return

                delta_buffer = ""
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    try:
                        payload_str = line[6:]
                        event = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("event", "")

                    if event_type == "tool.started":
                        tool = event.get("tool", "unknown")
                        preview = event.get("preview", "")
                        await broadcast_fn({
                            "type": "tool",
                            "level": "info",
                            "source": "hermes",
                            "message": f"\u27f3 {tool}: {preview[:80]}",
                            "timestamp": _ts(),
                        })

                    elif event_type == "tool.completed":
                        tool = event.get("tool", "unknown")
                        duration = event.get("duration", 0)
                        has_error = event.get("error", False)
                        await broadcast_fn({
                            "type": "tool",
                            "level": "warning" if has_error else "info",
                            "source": "hermes",
                            "message": f"\u2713 {tool} ({duration:.1f}s)",
                            "timestamp": _ts(),
                        })

                    elif event_type == "message.delta":
                        delta_buffer += event.get("delta", "")

                    elif event_type == "run.completed":
                        output = event.get("output", "")
                        usage = event.get("usage", {})
                        message = output if output else delta_buffer
                        if message:
                            await broadcast_fn({
                                "type": "done",
                                "level": "success",
                                "source": "hermes",
                                "message": message,
                                "meta": {
                                    "input_tokens": usage.get("input_tokens"),
                                    "output_tokens": usage.get("output_tokens"),
                                },
                                "timestamp": _ts(),
                            })
                        await broadcast_fn({
                            "type": "query",
                            "level": "success",
                            "source": "system",
                            "message": "Query abgeschlossen",
                            "timestamp": _ts(),
                        })

                    elif event_type == "run.failed":
                        await broadcast_fn({
                            "type": "error",
                            "level": "error",
                            "source": "hermes",
                            "message": f"Hermes Fehler: {event.get('error', 'unbekannt')}",
                            "timestamp": _ts(),
                        })

    except httpx.ConnectError:
        await broadcast_fn({
            "type": "error",
            "level": "error",
            "source": "system",
            "message": "Hermes API Server nicht erreichbar \u2014 l\u00e4uft hermes gateway?",
            "timestamp": _ts(),
        })
    except httpx.TimeoutException:
        await broadcast_fn({
            "type": "error",
            "level": "error",
            "source": "system",
            "message": "Query Timeout (120s)",
            "timestamp": _ts(),
        })
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await broadcast_fn({
            "type": "error",
            "level": "error",
            "source": "system",
            "message": f"Query Fehler: {str(e)}",
            "timestamp": _ts(),
        })
