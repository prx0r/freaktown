"""Privy access-token verification (real JWT verification, not decoding).

Mirrors apps/web/worker/auth/privy.ts: RS256 signature via Privy JWKS,
issuer privy.io, audience = our app ID, expiry enforced. The `sub`
(did:privy:...) is the stable user id.

The JWKS document fetcher is injectable so tests run fully offline
against a locally-generated RSA keypair.
"""

import time

import jwt

ISSUER = "privy.io"


def default_jwks_url(app_id: str) -> str:
    return f"https://auth.privy.io/api/v1/apps/{app_id}/jwks.json"


_jwks_cache: dict[str, tuple[float, dict]] = {}
JWKS_TTL_SEC = 600


def _fetch_jwks(url: str) -> dict:
    import urllib.request

    with urllib.request.urlopen(url, timeout=10) as response:
        import json

        return json.load(response)


def get_jwks(url: str, fetcher=None) -> dict:
    """Fetch (and briefly cache) a JWKS document."""
    now = time.time()
    cached = _jwks_cache.get(url)
    if cached and now - cached[0] < JWKS_TTL_SEC:
        return cached[1]
    doc = (fetcher or _fetch_jwks)(url)
    _jwks_cache[url] = (now, doc)
    return doc


def clear_jwks_cache() -> None:
    _jwks_cache.clear()


def verify_privy_access_token(token: str, app_id: str, jwks_url: str | None = None,
                              fetcher=None) -> dict:
    """Verify a Privy access token. Returns the claims on success.

    Raises ValueError on any failure (missing token, bad signature,
    wrong issuer/audience, expiry, missing sub). Callers map this to 401.
    """
    if not token or not isinstance(token, str):
        raise ValueError("missing token")
    if not app_id:
        raise ValueError("Privy app ID not configured")
    jwks = get_jwks(jwks_url or default_jwks_url(app_id), fetcher=fetcher)
    try:
        # We already hold the JWKS document, so resolve the signing key
        # from it directly rather than via PyJWKClient's URI fetch.
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        key_data = None
        for k in jwks.get("keys", []):
            if kid is None or k.get("kid") == kid:
                key_data = k
                break
        if key_data is None:
            raise ValueError("no matching JWK")
        from jwt.algorithms import RSAAlgorithm

        key = RSAAlgorithm.from_jwk(key_data)
        claims = jwt.decode(
            token, key=key, algorithms=["RS256"],
            issuer=ISSUER, audience=app_id,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as e:
        raise ValueError(f"invalid token: {e}")
    if not claims.get("sub"):
        raise ValueError("token has no sub")
    return claims
