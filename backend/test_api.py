import pytest
from httpx import AsyncClient
from main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test the root endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "Recreation.gov Notifier API" in response.json()["message"]


@pytest.mark.asyncio
async def test_register_user():
    """Test user registration"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        test_email = f"test_{datetime.now().timestamp()}@example.com"
        response = await client.post(
            "/api/auth/register",
            json={
                "email": test_email,
                "password": "testpassword123",
                "phone_number": "+1234567890"
            }
        )
        
        # Should return 200 or 400 (if user exists)
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials():
    """Test login with invalid credentials"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_without_auth():
    """Test accessing protected route without authentication"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/auth/me")
        assert response.status_code == 403  # Forbidden without auth header


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
