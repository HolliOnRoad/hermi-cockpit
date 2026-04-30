import asyncio
from unittest.mock import patch, AsyncMock

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
        with patch("api.main.broadcast_chat") as mock_broadcast:
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


async def test_chat_log_channel_separation():
    chat_mock = AsyncMock()
    log_mock = AsyncMock()

    import api.main
    api.main.chat_clients.add(chat_mock)
    api.main.log_clients.add(log_mock)

    try:
        async def mock_query(text, broadcast_fn, session_id=None):
            await broadcast_fn({
                "type": "tool",
                "level": "info",
                "source": "hermes",
                "message": "test tool event",
                "timestamp": "12:00:00",
            })
            await broadcast_fn({
                "type": "done",
                "level": "success",
                "source": "hermes",
                "message": "test done",
                "timestamp": "12:00:01",
            })

        with patch("api.main.hermes_run_query", side_effect=mock_query):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                res = await client.post(
                    "/api/chat",
                    json={"text": "test", "session_id": "test-session"},
                )
                assert res.status_code == 200
                await asyncio.sleep(0.05)

        chat_mock.send_json.assert_called()
        log_mock.send_json.assert_not_called()
    finally:
        api.main.chat_clients.discard(chat_mock)
        api.main.log_clients.discard(log_mock)


async def test_pty_echo_output():
    from services.hermes_pty import PtyBridge
    bridge = PtyBridge(cmd=["echo", "hello"])

    chunks = []
    async def collect(data: bytes):
        if data:
            chunks.append(data)

    await bridge.start(collect)
    await asyncio.sleep(0.3)

    output = b"".join(chunks)
    assert b"hello" in output
    assert bridge.exit_code == 0


async def test_pty_write_read():
    from services.hermes_pty import PtyBridge
    bridge = PtyBridge(cmd=["python3", "-c",
        "import sys; sys.stdout.write('READY\\n'); sys.stdout.flush(); "
        "line = sys.stdin.readline(); sys.stdout.write('GOT:' + line); sys.stdout.flush()"])

    chunks = []
    async def collect(data: bytes):
        if data:
            chunks.append(data)

    await bridge.start(collect)
    await asyncio.sleep(0.3)

    bridge.write(b"HELLO\n")
    await asyncio.sleep(0.3)

    output = b"".join(chunks)
    assert b"READY" in output
    assert b"GOT:HELLO" in output
    assert bridge.exit_code == 0


async def test_pty_cleanup():
    from services.hermes_pty import PtyBridge
    bridge = PtyBridge(cmd=["sleep", "30"])

    chunks = []
    async def collect(data: bytes):
        if data:
            chunks.append(data)

    await bridge.start(collect)
    await asyncio.sleep(0.2)

    assert bridge._process is not None
    assert bridge._process.isalive()

    await bridge.stop()
    await asyncio.sleep(0.2)

    assert bridge.exit_code is not None
