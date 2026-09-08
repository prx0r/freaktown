"""Deterministic draw protocol for selecting appearances.

Per BUILD_BRIEF.md section 20:
  - Versioned deterministic draw
  - CSPRNG seed
  - Fisher-Yates shuffle
  - Replayable
  - No random.shuffle()
"""

import hashlib
import secrets
import struct
from dataclasses import dataclass


@dataclass
class DrawResult:
    """Result of a deterministic draw."""
    algorithm: str
    eligible_set_hash: str
    seed_commitment: str  # SHA256(seed) published before reveal
    seed: str  # revealed after commitment
    selected_ids: list[str]
    resident_ids: list[str]
    random_slots: int
    resident_slots: int


def _hash_eligible_set(ids: list[str]) -> str:
    """Hash the complete eligible set for verification."""
    sorted_ids = sorted(ids)
    content = "|".join(sorted_ids)
    return hashlib.sha256(content.encode()).hexdigest()


def _derive_random_bytes(seed: bytes, counter: int, length: int = 32) -> bytes:
    """Derive deterministic random bytes from seed + counter."""
    data = seed + struct.pack(">I", counter)
    result = b""
    counter_val = 0
    while len(result) < length:
        chunk = hashlib.sha256(data + struct.pack(">I", counter_val)).digest()
        result += chunk
        counter_val += 1
    return result[:length]


def _fisher_yates_select(ids: list[str], seed: bytes, count: int) -> tuple[list[str], list[str]]:
    """Deterministic Fisher-Yates to select `count` items from `ids`.

    Returns (selected, remaining).
    """
    pool = list(ids)
    n = len(pool)

    for i in range(n - 1, max(n - count - 1, -1), -1):
        # Derive random index from seed + position
        rand_bytes = _derive_random_bytes(seed, i, 4)
        j = struct.unpack(">I", rand_bytes)[0] % (i + 1)
        pool[i], pool[j] = pool[j], pool[i]

    selected = pool[n - count:]
    remaining = pool[:n - count]
    return selected, remaining


def generate_seed() -> tuple[bytes, str]:
    """Generate a cryptographically secure seed.

    Returns:
        (raw_seed, hex_representation)
    """
    raw_seed = secrets.token_bytes(32)
    return raw_seed, raw_seed.hex()


def commit_seed(seed: bytes) -> str:
    """Create a seed commitment (publish before reveal)."""
    return hashlib.sha256(seed).hexdigest()


def execute_draw(
    eligible_ids: list[str],
    seed: bytes,
    random_slots: int = 4,
    resident_slots: int = 1,
    resident_ids: list[str] | None = None,
) -> DrawResult:
    """Execute a deterministic draw.

    Args:
        eligible_ids: All eligible submission IDs
        seed: Cryptographic seed for randomness
        random_slots: Number of random slots to fill
        resident_slots: Number of resident slots
        resident_ids: IDs to always include (residents)

    Returns:
        DrawResult with selected IDs and verification data
    """
    if resident_ids is None:
        resident_ids = []

    # Hash the eligible set
    eligible_set_hash = _hash_eligible_set(eligible_ids)

    # Remove residents from random pool
    random_pool = [id_ for id_ in eligible_ids if id_ not in resident_ids]

    # Select random slots
    selected_random, _ = _fisher_yates_select(random_pool, seed, random_slots)

    # Combine
    selected_all = resident_ids[:resident_slots] + selected_random

    # Commit
    seed_hex = seed.hex()
    seed_commitment = commit_seed(seed)

    return DrawResult(
        algorithm="FREAK_TOWN_DRAW_V1",
        eligible_set_hash=eligible_set_hash,
        seed_commitment=seed_commitment,
        seed=seed_hex,
        selected_ids=selected_all,
        resident_ids=resident_ids[:resident_slots],
        random_slots=random_slots,
        resident_slots=resident_slots,
    )


def verify_draw(
    eligible_ids: list[str],
    seed_hex: str,
    expected_commitment: str,
    expected_selected: list[str],
    random_slots: int = 4,
    resident_slots: int = 1,
    resident_ids: list[str] | None = None,
) -> bool:
    """Verify a draw was executed correctly."""
    seed = bytes.fromhex(seed_hex)

    # Verify seed commitment
    if commit_seed(seed) != expected_commitment:
        return False

    # Re-execute draw
    result = execute_draw(
        eligible_ids=eligible_ids,
        seed=seed,
        random_slots=random_slots,
        resident_slots=resident_slots,
        resident_ids=resident_ids,
    )

    # Compare results
    return sorted(result.selected_ids) == sorted(expected_selected)
