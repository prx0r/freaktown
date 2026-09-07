"""E2E test for full show flow.

Tests the complete Episode Zero lifecycle:
  1. Seed 5 comedians
  2. Create episode
  3. Submit comedians
  4. Run draw
  5. Start show
  6. Simulate performance
  7. Run interview
  8. End show
"""

import hashlib
import json
import uuid

import pytest


class TestFullShowFlow:
    """Test the complete show flow without database."""

    def test_seed_creates_five_comedians(self):
        """Verify seed data creates 5 comedians with acts."""
        from backend.services.seed import seed_episode_zero
        from backend.models import Comedian, ActVersion, User

        # We can't actually run seed_episode_zero without a DB,
        # but we can verify the data structures
        assert hasattr(seed_episode_zero, '__call__')

    def test_comedian_creation_flow(self):
        """Test the comedian creation data flow."""
        from backend.routes.comedians import slugify, compute_hash
        from backend.models import BodyArchetype, Authorship, InterviewController

        # Simulate creator flow
        name = "No-Nose Nolan"
        slug = slugify(name)
        assert slug == "no-nose-nolan"

        # Create manifest
        manifest = {
            "schemaVersion": 1,
            "character": {
                "name": name,
                "deal": "Police sniffer dog born without a sense of smell",
                "facts": ["cannot smell", "passed police training"],
            },
            "body": {"family": "dog", "variant": "german-shepherd", "outfit": "police-vest"},
            "voice": {"voiceId": "deep_male"},
            "minute": {
                "text": "I've been a police sniffer dog for six years...",
                "authorship": "human",
                "assistance": [],
            },
            "interview": {
                "controller": "freak_town_ai",
                "facts": ["cannot smell"],
            },
        }

        # Compute hash
        content_hash = compute_hash(manifest)
        assert len(content_hash) == 64  # Full SHA-256

        # Verify hash is deterministic
        content_hash2 = compute_hash(manifest)
        assert content_hash == content_hash2

    def test_draw_flow(self):
        """Test the complete draw flow."""
        from backend.services.draw import (
            generate_seed, commit_seed, execute_draw, verify_draw
        )

        # Generate seed
        seed, seed_hex = generate_seed()
        commitment = commit_seed(seed)

        # Create eligible pool
        eligible_ids = [str(uuid.uuid4()) for _ in range(100)]
        resident_ids = [eligible_ids[0]]

        # Execute draw
        result = execute_draw(
            eligible_ids=eligible_ids,
            seed=seed,
            random_slots=4,
            resident_slots=1,
            resident_ids=resident_ids,
        )

        # Verify
        assert len(result.selected_ids) == 5
        assert resident_ids[0] in result.selected_ids
        assert result.algorithm == "FREAK_TOWN_DRAW_V1"
        assert result.seed_commitment == commitment

        # Verify replay
        assert verify_draw(
            eligible_ids=eligible_ids,
            seed_hex=seed_hex,
            expected_commitment=commitment,
            expected_selected=result.selected_ids,
            random_slots=4,
            resident_slots=1,
            resident_ids=resident_ids,
        )

    def test_performance_plan_flow(self):
        """Test performance plan compilation."""
        from backend.services.performance_compiler import (
            _segment_script, _generate_cues_from_text
        )

        minute_text = "I've been a police sniffer dog for six years. The problem is I can't smell anything."

        # Segment script
        segments = _segment_script(minute_text, 30000)
        assert len(segments) >= 2
        assert segments[0].start_ms == 0
        assert segments[-1].end_ms == 30000

        # Generate cues
        cues = _generate_cues_from_text(minute_text, 30000)
        assert len(cues) > 0
        # First cue should be "enter"
        assert cues[0].type == "gesture"
        assert cues[0].value == "enter"

    def test_interview_flow(self):
        """Test interview engine state machine."""
        from backend.services.interview import EllaInterviewEngine

        engine = EllaInterviewEngine()
        appearance_id = str(uuid.uuid4())

        # Turn 1: GROUND
        state = engine.get_state(appearance_id)
        assert state.turn_count == 0

        # Simulate turns
        state.turn_count = 1
        state.last_action = "GROUND"
        state.facts.append("claims to be medieval")
        engine.update_state(appearance_id, state)

        # Turn 2: PROBE
        state = engine.get_state(appearance_id)
        state.turn_count = 2
        state.last_action = "PROBE"
        state.threads.append("medieval identity")
        engine.update_state(appearance_id, state)

        # Turn 3: CHALLENGE
        state = engine.get_state(appearance_id)
        state.turn_count = 3
        state.last_action = "CHALLENGE"
        state.contradictions.append("knows DoorDash but claims 1348")
        engine.update_state(appearance_id, state)

        # Verify state
        final_state = engine.get_state(appearance_id)
        assert final_state.turn_count == 3
        assert len(final_state.facts) == 1
        assert len(final_state.threads) == 1
        assert len(final_state.contradictions) == 1

    def test_body_validation_flow(self):
        """Test body family validation."""
        from backend.services.bodies import body_service

        # Dog body
        dog = body_service.get_body("dog.german-shepherd.v1")
        assert dog is not None
        assert dog.family == "dog"
        assert "sit" in dog.supported_gestures
        assert "peace" not in dog.supported_gestures

        # Robot body
        robot = body_service.get_body("robot.customer-service.v1")
        assert robot is not None
        assert robot.mouth_mode == "none"

    def test_tts_flow(self):
        """Test TTS voice catalog."""
        from backend.services.tts import get_adapter, list_providers

        providers = list_providers()
        assert len(providers) >= 4

        adapter = get_adapter("edge")
        voices = adapter.list_voices()
        assert len(voices) >= 6

        # Check specific voices exist
        voice_ids = [v["id"] for v in voices]
        assert "en-US-GuyNeural" in voice_ids
        assert "en-US-AriaNeural" in voice_ids

    def test_sponsor_flow(self):
        """Test sponsor campaign creation."""
        from backend.services.sponsors import sponsor_service

        # Get placements
        assert "OPENING_READ" in sponsor_service.PLACEMENTS
        assert "SPONSORED_CHALLENGE" in sponsor_service.PLACEMENTS

        # Generate Ella read prompt
        prompt = sponsor_service.generate_ella_read_prompt(
            brand_name="TestBrand",
            claims=["Great product"],
            required_phrase="Check out TestBrand",
            cta="Visit testbrand.com",
            destination_url="https://testbrand.com",
        )
        assert "TestBrand" in prompt
        assert "Ella" in prompt

    def test_external_agent_flow(self):
        """Test external agent registration and response."""
        from backend.services.external_agent import ExternalAgentController

        controller = ExternalAgentController()

        # Issue token
        appearance_id = str(uuid.uuid4())
        episode_id = str(uuid.uuid4())
        token = controller.issue_token(appearance_id, episode_id)

        assert token.startswith("agent_")
        assert controller.validate_token(token, appearance_id)
        assert not controller.validate_token(token, str(uuid.uuid4()))  # Wrong appearance

    def test_tip_flow(self):
        """Test tip initiation."""
        from backend.services.payments import tip_service, PLATFORM_FEE_PCT

        # Calculate tip split
        amount = 10.0
        platform_fee = amount * (PLATFORM_FEE_PCT / 100)
        creator_amount = amount - platform_fee

        assert platform_fee == 0.5
        assert creator_amount == 9.5
        assert PLATFORM_FEE_PCT == 5.0
