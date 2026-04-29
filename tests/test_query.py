import asyncio
from unittest.mock import AsyncMock, patch

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


async def test_query_no_shell():
    mock_process = AsyncMock()
    mock_process.stdout = AsyncMock()
    mock_process.stderr = AsyncMock()
    mock_process.stdout.readline = AsyncMock(side_effect=[b"output line\n", b""])
    mock_process.stderr.readline = AsyncMock(side_effect=[b""])
    mock_process.wait = AsyncMock(return_value=0)
    mock_process.returncode = 0

    with patch("api.main.asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.return_value = mock_process

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.post("/api/query", json={"text": "test query"})
            assert res.status_code == 200

            await asyncio.sleep(0.05)

            assert mock_exec.called
            call_kwargs = mock_exec.call_args[1]
            assert call_kwargs.get("shell") in (None, False)

            args = mock_exec.call_args[0] if mock_exec.call_args[0] else []
            assert "hermes" in args
            assert "-q" in args
            assert "test query" in args


async def test_query_hermes_not_found():
    with patch("api.main.asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = FileNotFoundError("hermes not found")

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
                error_calls = [
                    e
                    for e in calls
                    if e.get("type") == "error"
                    and "hermes CLI nicht gefunden" in e.get("message", "")
                ]
                assert len(error_calls) >= 1
