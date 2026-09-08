"""Storage interfaces (§14): product code talks to Protocols, never to disk.

Today: LocalPerformanceRepository (freaks/ bundles) + LocalMediaStore.
Later: PostgresPerformanceRepository + R2MediaStore behind the same Protocols,
selected by env. No caller changes.
"""

import hashlib
import json
from pathlib import Path
from typing import Protocol


class PerformanceRepository(Protocol):
    async def save(self, key: str, doc: dict) -> None: ...
    async def get(self, key: str) -> dict | None: ...
    async def list(self, prefix: str = "") -> list[str]: ...


class MediaStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str = "") -> str: ...
    async def get(self, key: str) -> bytes | None: ...


def _safe_key(key: str) -> str:
    raw = [p for p in key.replace("\\", "/").split("/") if p not in ("", ".")]
    if not raw or any(p == ".." for p in raw):
        raise ValueError("bad key")
    return "/".join(raw)


class LocalPerformanceRepository:
    """Filesystem bundle adapter: canonical local adapter for development."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    async def save(self, key: str, doc: dict) -> None:
        p = self.root / (_safe_key(key) + ".json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=2, sort_keys=True))

    async def get(self, key: str) -> dict | None:
        p = self.root / (_safe_key(key) + ".json")
        if not p.exists():
            return None
        return json.loads(p.read_text())

    async def list(self, prefix: str = "") -> list[str]:
        pre = _safe_key(prefix) if prefix else ""
        out = []
        for p in sorted(self.root.rglob("*.json")):
            rel = str(p.relative_to(self.root))[:-5]
            if rel.startswith(pre):
                out.append(rel)
        return out


class LocalMediaStore:
    """Local media adapter: content-addressed under root."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    async def put(self, key: str, data: bytes, content_type: str = "") -> str:
        p = self.root / _safe_key(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    async def get(self, key: str) -> bytes | None:
        p = self.root / _safe_key(key)
        return p.read_bytes() if p.exists() else None
