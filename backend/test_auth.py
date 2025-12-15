import pytest
import asyncio
from datetime import datetime
from bson import ObjectId
from auth import get_password_hash, verify_password, create_access_token, decode_access_token


def test_password_hashing():
    """Test password hashing and verification"""
    password = "test_password_123"
    hashed = get_password_hash(password)
    
    # Should not be the same as plaintext
    assert hashed != password
    
    # Should verify correctly
    assert verify_password(password, hashed)
    
    # Should not verify incorrect password
    assert not verify_password("wrong_password", hashed)


def test_jwt_token_creation():
    """Test JWT token creation and decoding"""
    test_data = {"sub": "test@example.com", "user_id": "12345"}
    token = create_access_token(test_data)
    
    # Should create a token
    assert token is not None
    assert isinstance(token, str)
    
    # Should decode correctly
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "test@example.com"
    assert decoded["user_id"] == "12345"


def test_invalid_token():
    """Test decoding invalid token"""
    decoded = decode_access_token("invalid_token_string")
    assert decoded is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
