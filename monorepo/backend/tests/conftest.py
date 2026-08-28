import asyncio
import sys
from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Stub heavy external deps before app.main is imported.
# sentence_transformers and qdrant_client are not installed in the test
# environment; the stubs prevent ImportError during module collection.
for _name in [
    "sentence_transformers",
    "qdrant_client",
    "qdrant_client.http",
    "qdrant_client.http.models",
    "qdrant_client.models",
]:
    sys.modules.setdefault(_name, MagicMock())

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
