"""Canonical manifest hashing (extracted from the legacy comedians route).

Pure function, no routes attached: full SHA-256 of canonical JSON.
64 hex chars. Never truncate.
"""

import hashlib
import json


def canonicalize_manifest(manifest: dict) -> str:
    """Canonical JSON serialization. Recursively sorts object keys, preserves array order."""
    return json.dumps(manifest, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def compute_hash(manifest: dict) -> str:
    """Compute full SHA-256 of canonical manifest. 64 hex chars. Never truncate."""
    canonical = canonicalize_manifest(manifest)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
