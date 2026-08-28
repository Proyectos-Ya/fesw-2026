import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_read_root(client: AsyncClient):
    """Prueba que el endpoint raíz responda correctamente."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "Welcome" in data["message"]

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Prueba que el endpoint de salud responda healthy."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
