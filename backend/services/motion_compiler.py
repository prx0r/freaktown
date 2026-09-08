"""Motion Compiler — resolves semantic directions to concrete animation plans.

Takes a PerformanceEngine + script + TTS word timings + body capabilities
and produces a PerformancePlan: a timestamped sequence of motion commands
that the stage renderer can execute.

Reference: anime.dm
"""

from dataclasses import dataclass, field

from backend.models.motion import (
    BODY_MANIFESTS,
    CapabilityManifest,
    HUMANOID_V1,
)
from backend.models.motion_assets import SEED_MOTIONS, MotionAsset
from backend.models.performance import PerformanceEngine


# ── Output Types ────────────────────────────────────────────────────

@dataclass
class MotionCue:
    """A single motion command at a specific time."""
    at_ms: int
    action: str               # resolved semantic action
    motion_asset_id: str | None = None  # which clip to play
    duration_ms: int = 0      # 0 = use clip default
    intensity: float = 0.5    # blend weight
    bone_mask: str = "full"   # which body parts to affect
    layer: str = "base"       # "base", "upper", "head", "face"
    metadata: dict = field(default_factory=dict)


@dataclass
class PerformancePlan:
    """The compiled output: a timestamped motion plan for the stage renderer.

    This is what gets sent to the browser. It contains:
    - timed motion cues
    - the base idle
    - gaze directives
    - face expression changes
    - additive layers
    """
    appearance_id: str
    body_class: str
    duration_ms: int

    # Base motion (full body, always playing)
    base_idle_asset_id: str | None = None
    base_locomotion: list[MotionCue] = field(default_factory=list)

    # Upper body gestures (additive layer)
    gesture_cues: list[MotionCue] = field(default_factory=list)

    # Head/gaze (separate layer)
    gaze_cues: list[MotionCue] = field(default_factory=list)

    # Face expressions (separate layer)
    face_cues: list[MotionCue] = field(default_factory=list)

    # Style parameters for the renderer
    energy: float = 0.5
    stillness: float = 0.5
    gesture_density: float = 0.5

    def all_cues(self) -> list[MotionCue]:
        """Get all cues sorted by time."""
        all_c = (
            self.base_locomotion +
            self.gesture_cues +
            self.gaze_cues +
            self.face_cues
        )
        return sorted(all_c, key=lambda c: c.at_ms)

    def to_dict(self) -> dict:
        return {
            "appearance_id": self.appearance_id,
            "body_class": self.body_class,
            "duration_ms": self.duration_ms,
            "base_idle_asset_id": self.base_idle_asset_id,
            "energy": self.energy,
            "stillness": self.stillness,
            "gesture_density": self.gesture_density,
            "cue_count": len(self.all_cues()),
            "cues": [
                {
                    "at_ms": c.at_ms,
                    "action": c.action,
                    "motion_asset_id": c.motion_asset_id,
                    "duration_ms": c.duration_ms,
                    "intensity": c.intensity,
                    "bone_mask": c.bone_mask,
                    "layer": c.layer,
                }
                for c in self.all_cues()
            ],
        }


# ── Motion Search ───────────────────────────────────────────────────

class MotionSearch:
    """Search the motion bank for clips matching semantic criteria."""

    def __init__(self, motions: list[MotionAsset] | None = None):
        self.motions = motions or SEED_MOTIONS

    def search(
        self,
        semantic: str | None = None,
        style: list[str] | None = None,
        body_class: str = "humanoid-v1",
        max_energy: float | None = None,
        min_energy: float | None = None,
        limit: int = 3,
    ) -> list[MotionAsset]:
        """Find motions matching criteria, ranked by relevance."""
        candidates = []

        for m in self.motions:
            # Body class filter
            if m.body_class != body_class and m.body_class != "universal":
                continue

            # Semantic match
            if semantic and semantic not in m.semantic:
                # Check prefix match
                prefix = semantic.split(".")[0] + ".*"
                if prefix not in m.semantic and not any(
                    s.startswith(semantic.split(".")[0]) for s in m.semantic
                ):
                    continue

            # Style filter
            if style:
                if not any(s in m.style for s in style):
                    continue

            # Energy filter
            if max_energy is not None and m.energy > max_energy:
                continue
            if min_energy is not None and m.energy < min_energy:
                continue

            candidates.append(m)

        # Rank by specificity (more semantic tags = more specific = better)
        candidates.sort(key=lambda m: len(m.semantic), reverse=True)
        return candidates[:limit]

    def search_for_style(self, engine: PerformanceEngine, body_class: str = "humanoid-v1") -> dict[str, MotionAsset]:
        """Get the best idle + signature motions for a PerformanceEngine."""
        style_tags = engine.tags

        # Find best idle
        idles = self.search(semantic="procedural.breathing", style=style_tags,
                           body_class=body_class, max_energy=engine.style.energy + 0.2,
                           limit=1)
        idle = idles[0] if idles else self.search(body_class=body_class, limit=1)[0]

        # Find best signature moves
        signatures = {}
        for move in engine.signature_moves:
            matches = self.search(semantic=move.action, style=style_tags,
                                body_class=body_class, limit=1)
            if matches:
                signatures[move.name] = matches[0]

        return {"idle": idle, "signatures": signatures}


# ── Motion Compiler ────────────────────────────────────────────────

class MotionCompiler:
    """Compiles semantic directions + PerformanceEngine into a PerformancePlan.

    This is the core of the Killella Motion Language.
    It resolves:
      "character should freeze after punchlines and stare at Ella"
    into:
      timestamped MotionCues with specific animation assets.
    """

    def __init__(self):
        self.search = MotionSearch()

    def compile(
        self,
        engine: PerformanceEngine,
        body_class: str,
        duration_ms: int,
        word_timings: list[dict] | None = None,
        script_sections: list[dict] | None = None,
        appearance_id: str = "",
    ) -> PerformancePlan:
        """Compile a PerformanceEngine into a concrete PerformancePlan.

        Args:
            engine: The creator's performance engine
            body_class: The character's body type
            duration_ms: Total performance duration
            word_timings: TTS word-level timings [{word, start_ms, end_ms}]
            script_sections: Script breakdown [{type, text, start_ms, end_ms}]
                             types: "setup", "punchline", "tag", "pause"
            appearance_id: The appearance this plan is for
        """
        manifest = BODY_MANIFESTS.get(body_class, HUMANOID_V1)
        plan = PerformancePlan(
            appearance_id=appearance_id,
            body_class=body_class,
            duration_ms=duration_ms,
            energy=engine.style.energy,
            stillness=engine.style.stillness,
            gesture_density=engine.style.gesture_density,
        )

        # 1. Select base idle
        idle_motions = self.search.search(
            semantic="procedural.breathing",
            style=engine.tags,
            body_class=body_class,
            max_energy=engine.style.energy + 0.2,
            limit=1,
        )
        if idle_motions:
            plan.base_idle_asset_id = idle_motions[0].id

        # 2. If we have word timings and script sections, compile with timing
        if word_timings and script_sections:
            plan = self._compile_with_timing(
                plan, engine, manifest, word_timings, script_sections
            )
        else:
            # 3. Otherwise, generate a basic plan from style alone
            plan = self._compile_from_style(plan, engine, manifest, duration_ms)

        return plan

    def _compile_from_style(
        self,
        plan: PerformancePlan,
        engine: PerformanceEngine,
        manifest: CapabilityManifest,
        duration_ms: int,
    ) -> PerformancePlan:
        """Generate cues from style parameters alone (no script)."""
        gesture_interval = self._gesture_interval(engine.style)

        # Add gestures at regular intervals
        t = gesture_interval
        while t < duration_ms - 2000:
            gesture = self._pick_gesture(engine, manifest)
            if gesture and manifest.can_do(gesture.semantic[0]):
                cue = MotionCue(
                    at_ms=t,
                    action=gesture.semantic[0],
                    motion_asset_id=gesture.id,
                    duration_ms=gesture.duration_ms,
                    intensity=engine.style.gesture_amplitude,
                    bone_mask=gesture.bone_mask,
                    layer="upper",
                )
                plan.gesture_cues.append(cue)
            t += gesture_interval

        # Add gaze shift to Ella mid-performance
        if manifest.can_do("gaze.ella") and duration_ms > 10000:
            mid = duration_ms // 2
            plan.gaze_cues.append(MotionCue(
                at_ms=mid,
                action="gaze.ella",
                duration_ms=2000,
                intensity=0.6,
                bone_mask="head",
                layer="head",
            ))

        return plan

    def _compile_with_timing(
        self,
        plan: PerformancePlan,
        engine: PerformanceEngine,
        manifest: CapabilityManifest,
        word_timings: list[dict],
        script_sections: list[dict],
    ) -> PerformancePlan:
        """Compile with actual script timing data."""
        for section in script_sections:
            section_type = section.get("type", "setup")
            start_ms = section.get("start_ms", 0)
            end_ms = section.get("end_ms", 0)

            if section_type == "setup":
                # During setup: subtle beats, audience gaze
                preferred = engine.get_motion_for_context("setup")
                self._add_cues_for_section(
                    plan, engine, manifest, preferred, start_ms, end_ms, "upper"
                )

            elif section_type == "punchline":
                # During punchline: freeze (if stillness is high)
                if engine.style.stillness > 0.4:
                    plan.gesture_cues.append(MotionCue(
                        at_ms=start_ms,
                        action="locomotion.freeze",
                        duration_ms=end_ms - start_ms,
                        intensity=0.8,
                        layer="base",
                    ))
                # Gaze at audience during punchline
                if manifest.can_do("gaze.audience"):
                    plan.gaze_cues.append(MotionCue(
                        at_ms=start_ms,
                        action="gaze.audience",
                        duration_ms=end_ms - start_ms + 1000,
                        intensity=0.7,
                        bone_mask="head",
                        layer="head",
                    ))

            elif section_type == "punchline_end" or section_type == "tag":
                # After punchline: signature move or dead stare
                hold = engine.style.punchline_hold_ms
                sig = engine.get_signature_for_trigger("after_big_punchline")
                if sig and manifest.can_do(sig.action):
                    plan.gesture_cues.append(MotionCue(
                        at_ms=end_ms,
                        action=sig.action,
                        duration_ms=hold,
                        intensity=sig.intensity,
                        layer="upper",
                    ))
                elif manifest.can_do("reaction.dead_stare"):
                    plan.face_cues.append(MotionCue(
                        at_ms=end_ms,
                        action="reaction.dead_stare",
                        duration_ms=hold,
                        intensity=0.8,
                        bone_mask="face",
                        layer="face",
                    ))

        return plan

    def _add_cues_for_section(
        self,
        plan: PerformancePlan,
        engine: PerformanceEngine,
        manifest: CapabilityManifest,
        preferred_actions: list[str],
        start_ms: int,
        end_ms: int,
        layer: str,
    ):
        """Add gesture cues for a script section at appropriate density."""
        interval = self._gesture_interval(engine.style)
        t = start_ms + interval  # don't gesture immediately at section start

        while t < end_ms - 500:
            for action in preferred_actions:
                if manifest.can_do(action):
                    motions = self.search.search(
                        semantic=action, body_class=manifest.body_class, limit=1
                    )
                    if motions:
                        plan.gesture_cues.append(MotionCue(
                            at_ms=t,
                            action=action,
                            motion_asset_id=motions[0].id,
                            duration_ms=motions[0].duration_ms,
                            intensity=engine.style.gesture_amplitude,
                            bone_mask=motions[0].bone_mask,
                            layer=layer,
                        ))
                    break
            t += interval

    def _gesture_interval(self, style) -> int:
        """Calculate milliseconds between gestures based on density."""
        # density 0 = never, density 1 = every 800ms
        if style.gesture_density < 0.1:
            return 999999  # effectively never
        base = 800 + (1.0 - style.gesture_density) * 6000
        return int(base)

    def _pick_gesture(self, engine: PerformanceEngine, manifest: CapabilityManifest) -> MotionAsset | None:
        """Pick a contextually appropriate gesture."""
        import random
        candidates = self.search.search(
            body_class=manifest.body_class,
            max_energy=engine.style.energy + 0.3,
            min_energy=max(0, engine.style.energy - 0.2),
            limit=5,
        )
        if not candidates:
            return None
        return random.choice(candidates)
