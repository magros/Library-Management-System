"""
Unit tests for app.core.security – password hashing, JWT creation/decoding.
"""
from datetime import timedelta, datetime, timezone
from unittest.mock import patch

import pytest

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


# ─── Password hashing ──────────────────────────────────────────


class TestHashPassword:
    def test_hash_returns_string(self):
        hashed = hash_password("mypassword")
        assert isinstance(hashed, str)
        assert hashed != "mypassword"

    def test_hash_is_bcrypt_format(self):
        hashed = hash_password("mypassword")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_same_password_yields_different_hashes(self):
        h1 = hash_password("samepass")
        h2 = hash_password("samepass")
        assert h1 != h2  # salted hashes differ


class TestVerifyPassword:
    def test_correct_password(self):
        hashed = hash_password("correcthorse")
        assert verify_password("correcthorse", hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("correcthorse")
        assert verify_password("wronghorse", hashed) is False

    def test_empty_password_rejected(self):
        hashed = hash_password("notempty")
        assert verify_password("", hashed) is False


# ─── JWT tokens ─────────────────────────────────────────────────


class TestCreateAccessToken:
    def test_returns_string(self):
        token = create_access_token(data={"sub": "user123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_has_three_parts(self):
        token = create_access_token(data={"sub": "user123"})
        parts = token.split(".")
        assert len(parts) == 3  # header.payload.signature

    def test_custom_expiration(self):
        token = create_access_token(
            data={"sub": "user123"},
            expires_delta=timedelta(hours=2),
        )
        payload = decode_access_token(token)
        assert payload is not None
        # exp should be roughly 2 hours from now
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = (exp - now).total_seconds()
        assert 7100 < diff < 7300  # ~2h with tolerance

    def test_token_contains_jti(self):
        token = create_access_token(data={"sub": "user123"})
        payload = decode_access_token(token)
        assert "jti" in payload
        assert isinstance(payload["jti"], str)

    def test_each_token_has_unique_jti(self):
        t1 = create_access_token(data={"sub": "user123"})
        t2 = create_access_token(data={"sub": "user123"})
        p1 = decode_access_token(t1)
        p2 = decode_access_token(t2)
        assert p1["jti"] != p2["jti"]

    def test_custom_data_preserved(self):
        token = create_access_token(data={"sub": "uid-42", "role": "admin"})
        payload = decode_access_token(token)
        assert payload["sub"] == "uid-42"
        assert payload["role"] == "admin"


class TestDecodeAccessToken:
    def test_valid_token(self):
        token = create_access_token(data={"sub": "user123"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"

    def test_expired_token_returns_none(self):
        token = create_access_token(
            data={"sub": "user123"},
            expires_delta=timedelta(seconds=-1),
        )
        payload = decode_access_token(token)
        assert payload is None

    def test_tampered_token_returns_none(self):
        token = create_access_token(data={"sub": "user123"})
        # Flip a character in the signature
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        payload = decode_access_token(tampered)
        assert payload is None

    def test_garbage_string_returns_none(self):
        assert decode_access_token("not.a.token") is None
        assert decode_access_token("") is None
        assert decode_access_token("abc") is None

    def test_token_with_wrong_secret_returns_none(self):
        """A token signed with a different secret should return None."""
        from jose import jwt
        token = jwt.encode({"sub": "user123"}, "wrong-secret-key", algorithm="HS256")
        payload = decode_access_token(token)
        assert payload is None

