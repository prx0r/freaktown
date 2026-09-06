"""Green Room Compiler — ties the full pipeline together.

Takes a PerformanceDraft and produces a PerformancePlan:
  script + word timings + stage directions + speech directives + body + engine
        ↓
    PerformancePlan (timestamped motion cues for the stage renderer)

Reference: anime.dm — compilation flow
"""

from backend.models.draft import PerformanceDraft, StageDirection
from backend.models.performance import PerformanceEngine, StyleProfile
from backend.models.motion import BODY_MANIFESTS, HUMANOID_V1
from backend.services.motion_compiler import MotionCompiler, MotionCue, PerformancePlan
from backend.services.direction_parser import stage_direction_parser


class GreenRoomCompiler:
    """Compile a PerformanceDraft into a PerformancePlan.

    This is the core of the Green Room experience.
    It merges:
      1. The PerformanceEngine (style preferences)
      2. The actual TTS word timings (real timing)
      3. Creator's stage directions (movement cues)
      4. Speech directives (voice emphasis)
      5. Body capabilities (what the character can do)
    """

    def __init__(self):
        self.motion_compiler = MotionCompiler()

    def compile(
        self,
        draft: PerformanceDraft,
        engine: PerformanceEngine,
        body_class: str = "humanoid-v1",
    ) -> PerformancePlan:
        """Compile a draft into a performance plan."""
        manifest = BODY_MANIFESTS.get(body_class, HUMANOID_V1)
        duration_ms = draft.audio_duration_ms or draft.estimated_duration_ms

        plan = PerformancePlan(
            appearance_id=draft.id,
            body_class=body_class,
            duration_ms=duration_ms,
            energy=engine.style.energy,
            stillness=engine.style.stillness,
            gesture_density=engine.style.gesture_density,
        )

        # 1. Base idle from engine
        idle = self.motion_compiler.search.search(
            semantic="procedural.breathing",
            style=engine.tags,
            body_class=body_class,
            max_energy=engine.style.energy + 0.2,
            limit=1,
        )
        if idle:
            plan.base_idle_asset_id = idle[0].id

        # 2. Add signature moves from engine
        for sig in engine.signature_moves:
            trigger = sig.trigger
            # Find the word index that triggers this
            for i, word in enumerate(draft.word_timings):
                # Simple heuristic: signature move near end of big laugh section
                pass  # Will be refined with actual laugh detection

        # 3. Process stage directions (the creator's explicit cues)
        for direction in draft.stage_directions:
            self._process_direction(plan, direction, draft, engine, manifest)

        # 4. Add default pacing cues if gesture density warrants it
        gesture_interval = self._gesture_interval(engine.style)
        existing_times = {c.at_ms for c in plan.gesture_cues}

        t = gesture_interval
        while t < duration_ms - 2000:
            if not any(abs(t - et) < 1000 for et in existing_times):
                gesture = self._pick_pacing_gesture(engine, manifest)
                if gesture:
                    plan.gesture_cues.append(MotionCue(
                        at_ms=t,
                        action=gesture.semantic[0],
                        motion_asset_id=gesture.id,
                        duration_ms=gesture.duration_ms,
                        intensity=engine.style.gesture_amplitude * 0.5,
                        bone_mask=gesture.bone_mask,
                        layer="upper",
                    ))
            t += gesture_interval

        # 5. Add gaze shifts at natural pauses
        if draft.word_timings:
            self._add_gaze_cues(plan, draft, engine, manifest, duration_ms)

        return plan

    def _process_direction(
        self,
        plan: PerformancePlan,
        direction: StageDirection,
        draft: PerformanceDraft,
        engine: PerformanceEngine,
        manifest,
    ):
        """Process a single stage direction into motion cues."""
        # Resolve time from word index
        at_ms = direction.at_ms
        if direction.at_word >= 0 and direction.at_word < len(draft.word_timings):
            at_ms = draft.word_timings[direction.at_word].start_ms

        # Parse natural language if no direct action
        if direction.action and not direction.description:
            actions = [{"action": direction.action, "intensity": direction.intensity}]
        elif direction.description:
            parsed = stage_direction_parser.parse(direction.description)
            actions = parsed.actions
        else:
            return

        for action_info in actions:
            action = action_info.get("action", "gesture.beat")
            intensity = action_info.get("intensity", direction.intensity)
            duration = action_info.get("duration_ms", direction.duration_ms)

            # Resolve through body capabilities
            resolved = manifest.resolve(action)

            # Find a matching motion asset
            motions = self.motion_compiler.search.search(
                semantic=action,
                body_class=manifest.body_class,
                limit=1,
            )
            motion_id = motions[0].id if motions else None

            # Determine layer from action type
            layer = "upper"
            bone_mask = "upper_body"
            if action.startswith("gaze.") or action.startswith("reaction."):
                layer = "head"
                bone_mask = "head"
            elif action.startswith("face."):
                layer = "face"
                bone_mask = "face"
            elif action.startswith("locomotion."):
                layer = "base"
                bone_mask = "full"
            elif action.startswith("pose."):
                layer = "base"
                bone_mask = "full"

            cue = MotionCue(
                at_ms=at_ms,
                action=resolved,
                motion_asset_id=motion_id,
                duration_ms=duration,
                intensity=intensity,
                bone_mask=bone_mask,
                layer=layer,
                metadata={"source": "stage_direction", "raw": direction.description},
            )

            if layer == "head":
                plan.gaze_cues.append(cue)
            elif layer == "face":
                plan.face_cues.append(cue)
            else:
                plan.gesture_cues.append(cue)

    def _add_gaze_cues(
        self,
        plan: PerformancePlan,
        draft: PerformanceDraft,
        engine: PerformanceEngine,
        manifest,
        duration_ms: int,
    ):
        """Add gaze shifts at natural transition points."""
        if not draft.word_timings:
            return

        # Find sentence endings (periods, question marks)
        sentences = []
        for i, wt in enumerate(draft.word_timings):
            if wt.word.endswith((".", "?", "!")):
                sentences.append(i)

        # Add gaze shifts at ~30% and ~70% of sentences
        for sent_end in sentences:
            if sent_end < len(draft.word_timings):
                # Look at audience at sentence start
                start_ms = draft.word_timings[max(0, sent_end - 5)].start_ms
                if manifest.can_do("gaze.audience"):
                    plan.gaze_cues.append(MotionCue(
                        at_ms=start_ms,
                        action="gaze.audience",
                        duration_ms=2000,
                        intensity=0.5,
                        bone_mask="head",
                        layer="head",
                    ))

                # Look at Ella periodically
                if sent_end % 15 == 0 and manifest.can_do("gaze.ella"):
                    plan.gaze_cues.append(MotionCue(
                        at_ms=draft.word_timings[sent_end].start_ms,
                        action="gaze.ella",
                        duration_ms=1500,
                        intensity=0.4,
                        bone_mask="head",
                        layer="head",
                    ))

    def _gesture_interval(self, style) -> int:
        """Calculate milliseconds between gestures based on density."""
        if style.gesture_density < 0.1:
            return 999999
        return int(800 + (1.0 - style.gesture_density) * 6000)

    def _pick_pacing_gesture(self, engine, manifest):
        """Pick a contextually appropriate gesture for pacing."""
        import random
        candidates = self.motion_compiler.search.search(
            body_class=manifest.body_class,
            max_energy=engine.style.energy + 0.3,
            min_energy=max(0, engine.style.energy - 0.2),
            limit=5,
        )
        return random.choice(candidates) if candidates else None
