"""Draw verification test with known seed.

Tests that the deterministic draw produces the same output
given the same seed and eligible set.
"""

import hashlib
import uuid

import pytest


class TestDrawVerification:
    """Verify deterministic draw is reproducible."""

    def test_known_seed_produces_deterministic_result(self):
        """Same seed + same eligible set = same result, every time."""
        from backend.services.draw import execute_draw, commit_seed

        # Fixed seed for reproducibility
        seed_hex = "a" * 64
        seed = bytes.fromhex(seed_hex)

        # Fixed eligible set
        eligible_ids = [f"id-{i:04d}" for i in range(100)]
        resident_ids = ["id-0000"]

        # Run 1
        result1 = execute_draw(
            eligible_ids=eligible_ids,
            seed=seed,
            random_slots=4,
            resident_slots=1,
            resident_ids=resident_ids,
        )

        # Run 2
        result2 = execute_draw(
            eligible_ids=eligible_ids,
            seed=seed,
            random_slots=4,
            resident_slots=1,
            resident_ids=resident_ids,
        )

        # Must be identical
        assert result1.selected_ids == result2.selected_ids
        assert result1.seed_commitment == result2.seed_commitment
        assert result1.eligible_set_hash == result2.eligible_set_hash

    def test_different_seeds_produce_different_results(self):
        """Different seeds should produce different selections."""
        from backend.services.draw import execute_draw

        eligible_ids = [f"id-{i:04d}" for i in range(100)]

        seed1 = bytes.fromhex("a" * 64)
        seed2 = bytes.fromhex("b" * 64)

        result1 = execute_draw(eligible_ids, seed1, random_slots=4, resident_slots=1)
        result2 = execute_draw(eligible_ids, seed2, random_slots=4, resident_slots=1)

        # Different seeds should produce different selections
        # (with astronomically high probability)
        assert result1.selected_ids != result2.selected_ids

    def test_eligible_set_hash_changes_with_different_ids(self):
        """Changing the eligible set changes the hash."""
        from backend.services.draw import _hash_eligible_set

        ids1 = ["a", "b", "c"]
        ids2 = ["a", "b", "d"]

        hash1 = _hash_eligible_set(ids1)
        hash2 = _hash_eligible_set(ids2)

        assert hash1 != hash2

    def test_eligible_set_hash_is_order_independent(self):
        """Hash should be the same regardless of order."""
        from backend.services.draw import _hash_eligible_set

        ids1 = ["c", "a", "b"]
        ids2 = ["a", "b", "c"]

        hash1 = _hash_eligible_set(ids1)
        hash2 = _hash_eligible_set(ids2)

        assert hash1 == hash2

    def test_resident_always_included(self):
        """Resident IDs must always be in the selected set."""
        from backend.services.draw import execute_draw

        seed = bytes.fromhex("a" * 64)
        eligible_ids = [f"id-{i:04d}" for i in range(100)]
        resident_ids = ["id-0001", "id-0002"]

        result = execute_draw(
            eligible_ids=eligible_ids,
            seed=seed,
            random_slots=3,
            resident_slots=2,
            resident_ids=resident_ids,
        )

        assert "id-0001" in result.selected_ids
        assert "id-0002" in result.selected_ids
        assert len(result.selected_ids) == 5  # 3 random + 2 resident

    def test_draw_with_empty_pool(self):
        """Draw with only residents should work."""
        from backend.services.draw import execute_draw

        seed = bytes.fromhex("a" * 64)
        eligible_ids = ["id-0001", "id-0002"]
        resident_ids = ["id-0001", "id-0002"]

        result = execute_draw(
            eligible_ids=eligible_ids,
            seed=seed,
            random_slots=0,
            resident_slots=2,
            resident_ids=resident_ids,
        )

        assert result.selected_ids == ["id-0001", "id-0002"]

    def test_commitment_matches_seed(self):
        """Seed commitment should verify correctly."""
        from backend.services.draw import generate_seed, commit_seed

        seed, seed_hex = generate_seed()
        commitment = commit_seed(seed)

        # Verify
        assert len(commitment) == 64
        assert commitment == commit_seed(seed)  # Same seed = same commitment
