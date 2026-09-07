"""Privy JWT verification — offline tests with a local RSA keypair.

A forged payload with valid shape must fail. Only tokens signed by the
JWKS key, with correct issuer/audience and a live expiry, pass.
"""

import base64
import time

import pytest

from backend.auth_privy import clear_jwks_cache, verify_privy_access_token


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_keypair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = key.public_key().public_numbers()
    n = _b64url(public.n.to_bytes(256, "big"))
    e = _b64url(public.e.to_bytes(3, "big"))
    jwks = {"keys": [{
        "kty": "RSA", "kid": "test-key", "use": "sig", "alg": "RS256",
        "n": n, "e": e,
    }]}
    return private_pem, jwks


def sign(private_pem: bytes, claims: dict, kid: str = "test-key") -> str:
    import jwt

    return jwt.encode(claims, private_pem, algorithm="RS256",
                      headers={"kid": kid})


@pytest.fixture
def crypto_setup():
    clear_jwks_cache()
    private_pem, jwks = make_keypair()
    fetcher = lambda url: jwks  # noqa: E731 — offline: never hits network
    now = int(time.time())
    base = {"iss": "privy.io", "aud": "test-app",
            "sub": "did:privy:abc123", "exp": now + 300, "iat": now}
    return private_pem, fetcher, base


class TestPrivyVerify:
    def test_valid_token_passes(self, crypto_setup):
        private_pem, fetcher, base = crypto_setup
        token = sign(private_pem, base)
        claims = verify_privy_access_token(token, "test-app", fetcher=fetcher)
        assert claims["sub"] == "did:privy:abc123"

    def test_forged_payload_fails(self, crypto_setup):
        """Valid shape, attacker-signed: must fail (this is the old bug)."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        _, fetcher, base = crypto_setup
        evil = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        evil_pem = evil.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        token = sign(evil_pem, base)
        with pytest.raises(ValueError, match="invalid token"):
            verify_privy_access_token(token, "test-app", fetcher=fetcher)

    def test_wrong_audience_fails(self, crypto_setup):
        private_pem, fetcher, base = crypto_setup
        token = sign(private_pem, {**base, "aud": "other-app"})
        with pytest.raises(ValueError, match="invalid token"):
            verify_privy_access_token(token, "test-app", fetcher=fetcher)

    def test_wrong_issuer_fails(self, crypto_setup):
        private_pem, fetcher, base = crypto_setup
        token = sign(private_pem, {**base, "iss": "evil.io"})
        with pytest.raises(ValueError, match="invalid token"):
            verify_privy_access_token(token, "test-app", fetcher=fetcher)

    def test_expired_fails(self, crypto_setup):
        private_pem, fetcher, base = crypto_setup
        token = sign(private_pem, {**base, "exp": int(time.time()) - 10})
        with pytest.raises(ValueError, match="invalid token"):
            verify_privy_access_token(token, "test-app", fetcher=fetcher)

    def test_missing_token_fails(self, crypto_setup):
        _, fetcher, _ = crypto_setup
        with pytest.raises(ValueError, match="missing token"):
            verify_privy_access_token("", "test-app", fetcher=fetcher)

    def test_garbage_fails(self, crypto_setup):
        _, fetcher, _ = crypto_setup
        with pytest.raises(ValueError):
            verify_privy_access_token("not.a.jwt", "test-app", fetcher=fetcher)

    def test_missing_sub_fails(self, crypto_setup):
        private_pem, fetcher, base = crypto_setup
        claims = {k: v for k, v in base.items() if k != "sub"}
        token = sign(private_pem, claims)
        with pytest.raises(ValueError):
            verify_privy_access_token(token, "test-app", fetcher=fetcher)

    def test_jwks_cache_used(self, crypto_setup):
        from backend import auth_privy

        private_pem, _, base = crypto_setup
        calls = []
        fetcher = lambda url: calls.append(url) or {"keys": []}  # noqa: E731
        with pytest.raises(ValueError):
            verify_privy_access_token(sign(private_pem, base), "test-app", fetcher=fetcher)
        assert len(calls) == 1
        # Second call with a different fetcher must NOT refetch (cached by URL)
        with pytest.raises(ValueError):
            verify_privy_access_token(sign(private_pem, base), "test-app",
                                      fetcher=lambda url: calls.append(url))
        assert len(calls) == 1
