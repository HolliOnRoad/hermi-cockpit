import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from unittest.mock import AsyncMock, patch


def pytest_configure(config):
    config.option.asyncio_mode = "auto"


@pytest.fixture(autouse=True)
def mock_log_stream():
    stream = AsyncMock()
    with patch("api.main.get_log_stream", return_value=stream):
        yield


@pytest.fixture
def anyio_backend():
    return "asyncio"
