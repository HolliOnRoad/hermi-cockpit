import asyncio
from unittest.mock import patch

from httpx import AsyncClient, ASGITransport

from api.main import app


async def test_query_empty_text():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.post("/api/query", json={"text": ""})
        assert res.status_code == 422

        res = await client.post("/api/query", json={"text": "   "})
        assert res.status_code == 422


async def test_query_conflict():
    import api.main

    api.main._query_running = True
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.post("/api/query", json={"text": "test query"})
            assert res.status_code == 409
    finally:
        api.main._query_running = False


async def test_api_bridge_called():
    called_text = None

    async def mock_run_query(text, broadcast_fn):
        nonlocal called_text
        called_text = text

    with patch("api.main.hermes_run_query", side_effect=mock_run_query):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.post("/api/query", json={"text": "test query"})
            assert res.status_code == 200

            await asyncio.sleep(0.05)

            assert called_text == "test query"


async def test_api_server_offline():
    async def mock_run_query(text, broadcast_fn):
        await broadcast_fn({
            "type": "error",
            "level": "error",
            "source": "system",
            "message": "Hermes API Server nicht erreichbar",
            "timestamp": "...",
        })

    with patch("api.main.hermes_run_query", side_effect=mock_run_query):
        with patch("api.main.broadcast_event") as mock_broadcast:
            mock_broadcast.return_value = 0

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                res = await client.post("/api/query", json={"text": "test"})
                assert res.status_code == 200

                await asyncio.sleep(0.05)

                calls = [
                    c[0][0] for c in mock_broadcast.call_args_list if c[0]
                ]
                error_msgs = [
                    e["message"]
                    for e in calls
                    if e.get("type") == "error"
                ]
                assert any(
                    "Hermes API Server nicht erreichbar" in m
                    for m in error_msgs
                )
