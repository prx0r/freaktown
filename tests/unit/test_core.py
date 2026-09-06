"""Unit tests for core domain models and services."""

import hashlib
import json
import uuid

import pytest


# ── Draw Protocol Tests ────────────────────────────────────────────────

class TestDrawProtocol:
    """Test the deterministic draw protocol."""

    def test_seed_generation(self):
        from backend.services.draw import generate_seed, commit_seed

        seed, seed_hex = generate_seed()
        assert len(seed) == 32
        assert len(seed_hex) == 64

        commitment = commit_seed(seed)
        assert len(commitment) == 64

        # Same seed produces same commitment
        commitment2 = commit_seed(seed)
        assert commitment == commitment2

    def test_deterministic_draw(self):
        from backend.services.draw import generate_seed, execute_draw

        seed, _ = generate_seed()
        eligible_ids = [str(uuid.uuid4()) for _ in range(100)]

        # Same seed produces same result
        result1 = execute_draw(eligible_ids, seed, random_slots=4, resident_slots=1)
        result2 = execute_draw(eligible_ids, seed, random_slots=4, resident_slots=1)

        assert result1.selected_ids == result2.selected_ids
        assert result1.algorithm == "FREAK_TOWN_DRAW_V1"

    def test_draw_selects_correct_count(self):
        from backend.services.draw import generate_seed, execute_draw

        seed, _ = generate_seed()
        eligible_ids = [str(uuid.uuid4()) for _ in range(100)]
        resident_ids = [eligible_ids[0]]  # First ID is resident

        result = execute_draw(
            eligible_ids, seed,
            random_slots=4, resident_slots=1,
            resident_ids=resident_ids,
        )

        # Should select 5 total (4 random + 1 resident)
        assert len(result.selected_ids) == 5
        # Resident should be included
        assert resident_ids[0] in result.selected_ids

    def test_draw_verification(self):
        from backend.services.draw import (
            generate_seed, execute_draw, commit_seed, verify_draw
        )

        seed, seed_hex = generate_seed()
        eligible_ids = [str(uuid.uuid4()) for _ in range(100)]
        commitment = commit_seed(seed)

        result = execute_draw(eligible_ids, seed, random_slots=4, resident_slots=1)

        # Verification should pass
        assert verify_draw(
            eligible_ids=eligible_ids,
            seed_hex=seed_hex,
            expected_commitment=commitment,
            expected_selected=result.selected_ids,
            random_slots=4,
            resident_slots=1,
        )

    def test_draw_fails_with_wrong_seed(self):
        from backend.services.draw import (
            generate_seed, execute_draw, commit_seed, verify_draw
        )

        seed, _ = generate_seed()
        eligible_ids = [str(uuid.uuid4()) for _ in range(100)]
        commitment = commit_seed(seed)

        result = execute_draw(eligible_ids, seed, random_slots=4, resident_slots=1)

        # Wrong seed should fail verification
        wrong_seed = "a" * 64
        assert not verify_draw(
            eligible_ids=eligible_ids,
            seed_hex=wrong_seed,
            expected_commitment=commitment,
            expected_selected=result.selected_ids,
            random_slots=4,
            resident_slots=1,
        )


# ── PerformancePlan Compiler Tests ─────────────────────────────────────

class TestPerformanceCompiler:
    """Test the performance plan compiler."""

    def test_segment_script(self):
        from backend.services.performance_compiler import _segment_script

        text = "Hello world. This is a test. Another sentence."
        segments = _segment_script(text, 10000)

        assert len(segments) == 3
        assert segments[0].text == "Hello world"
        assert segments[1].text == "This is a test"
        assert segments[2].text == "Another sentence"

    def test_generate_cues_from_text(self):
        from backend.services.performance_compiler import _generate_cues_from_text

        text = "I'm so fucking angry about this! What do you think?"
        cues = _generate_cues_from_text(text, 10000)

        # Should have cues for angry text and question
        assert len(cues) > 0
        # Check for angry cue (fist is triggered by "fuck")
        angry_cues = [c for c in cues if c.value in ("fist",)]
        assert len(angry_cues) > 0


# ── Interview Engine Tests ─────────────────────────────────────────────

class TestInterviewEngine:
    """Test the Ella interview engine."""

    def test_state_management(self):
        from backend.services.interview import EllaInterviewEngine

        engine = EllaInterviewEngine()
        appearance_id = str(uuid.uuid4())

        # Get state creates new
        state = engine.get_state(appearance_id)
        assert state.turn_count == 0

        # Update state
        state.facts.append("test fact")
        engine.update_state(appearance_id, state)

        # Get same state
        state2 = engine.get_state(appearance_id)
        assert "test fact" in state2.facts

    def test_fallback_response(self):
        from backend.services.interview import EllaInterviewEngine

        engine = EllaInterviewEngine()
        state = engine.get_state("test")
        state.turn_count = 1

        response = engine._fallback_response("TestBot", "A test character", state)
        assert "ELLACONNECT" in response
        assert "GROUND" in response


# ── Body Service Tests ─────────────────────────────────────────────────

class TestBodyService:
    """Test the body family animation system."""

    def test_catalog(self):
        from backend.services.bodies import body_service

        catalog = body_service.get_catalog()
        assert len(catalog) > 0

        # Check families
        families = {b["family"] for b in catalog}
        assert "human" in families
        assert "dog" in families
        assert "robot" in families

    def test_gesture_validation(self):
        from backend.services.bodies import body_service

        # Dog supports "sit"
        assert body_service.validate_gesture("dog.german-shepherd.v1", "sit")
        # Dog doesn't support "peace"
        assert not body_service.validate_gesture("dog.german-shepherd.v1", "peace")

    def test_emotion_validation(self):
        from backend.services.bodies import body_service

        # Robot supports "neutral"
        assert body_service.validate_emotion("robot.customer-service.v1", "neutral")
        # Robot doesn't support "contempt"
        assert not body_service.validate_emotion("robot.customer-service.v1", "contempt")


# ── TTS Service Tests ──────────────────────────────────────────────────

class TestTTS:
    """Test the TTS service."""

    def test_voice_catalog(self):
        from backend.services.tts import VOICE_CATALOG

        assert "default" in VOICE_CATALOG
        assert "ella" in VOICE_CATALOG
        assert len(VOICE_CATALOG) >= 6

    def test_list_voices(self):
        from backend.services.tts import list_voices

        voices = list_voices()
        assert len(voices) > 0
        assert any(v["key"] == "default" for v in voices)


# ── Event Sequencing Tests ─────────────────────────────────────────────

class TestEventSequencing:
    """Test event sequencing helpers."""

    def test_get_next_seq_empty(self):
        # This would need a database mock, but we can test the logic
        from backend.services.events import get_next_seq_safe, emit_event
        # In production, test with a real or mocked database
        assert callable(get_next_seq_safe)

    def test_emit_event_callable(self):
        from backend.services.events import emit_event
        assert callable(emit_event)


# ── Sponsor Service Tests ──────────────────────────────────────────────

class TestSponsorService:
    """Test the sponsor campaign system."""

    def test_placements(self):
        from backend.services.sponsors import sponsor_service

        assert "OPENING_READ" in sponsor_service.PLACEMENTS
        assert "TRANSITION" in sponsor_service.PLACEMENTS

    def test_ella_read_prompt(self):
        from backend.services.sponsors import sponsor_service

        prompt = sponsor_service.generate_ella_read_prompt(
            brand_name="TestBrand",
            claims=["Great product", "Best ever"],
            required_phrase="Check out TestBrand",
            cta="Visit testbrand.com",
            destination_url="https://testbrand.com",
        )

        assert "TestBrand" in prompt
        assert "Check out TestBrand" in prompt
        assert "Ella" in prompt
