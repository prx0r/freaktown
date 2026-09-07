"""Running Gags / Callback System — semantic matching with freshness decay.

Tracks callbacks across episodes. Enables continuity and recurring jokes.
Characters can reference previous sets, creating narrative arcs.
"""

import json
import logging
import math
import time
from dataclasses import dataclass, field

logger = logging.getLogger("freak_town.callbacks")


@dataclass
class Callback:
    """A single callback reference."""
    id: str
    episode_id: str
    performer_id: str
    setup_text: str       # the original line
    punchline_text: str   # the callback reference
    set_time_seconds: float
    created_at: float = field(default_factory=time.time)
    hit_count: int = 0
    last_used_at: float = 0.0


@dataclass
class RunningGag:
    """A recurring joke across episodes."""
    id: str
    performer_id: str
    keyword: str          # e.g. "printer", "taxes", "government drone"
    setup_count: int = 0
    callback_count: int = 0
    total_laughs: int = 0
    best_laugh_ms: float = 0
    created_at: float = field(default_factory=time.time)
    last_used_at: float = 0.0


class CallbackTracker:
    """Track running gags and callbacks across episodes."""

    def __init__(self):
        self.callbacks: list[Callback] = []
        self.gags: dict[str, RunningGag] = {}  # keyed by keyword
        self._decay_rate = 0.1  # freshness decays 10% per episode

    def register_callback(
        self,
        episode_id: str,
        performer_id: str,
        setup_text: str,
        callback_text: str,
        set_time_seconds: float,
        laugh_count: int = 0,
    ) -> Callback:
        """Register a callback (setup or reference to previous setup)."""
        cb = Callback(
            id=f"cb_{len(self.callbacks)+1}",
            episode_id=episode_id,
            performer_id=performer_id,
            setup_text=setup_text,
            punchline_text=callback_text,
            set_time_seconds=set_time_seconds,
        )
        self.callbacks.append(cb)

        # Check if this creates a running gag
        keyword = self._extract_keyword(setup_text, callback_text)
        if keyword:
            gag = self.gags.get(keyword)
            if gag:
                gag.callback_count += 1
                gag.total_laughs += laugh_count
                gag.last_used_at = time.time()
            else:
                self.gags[keyword] = RunningGag(
                    id=f"gag_{len(self.gags)+1}",
                    performer_id=performer_id,
                    keyword=keyword,
                    setup_count=1,
                    callback_count=0,
                )
            cb.hit_count = laugh_count

        return cb

    def get_suggestions(self, performer_id: str, current_text: str) -> list[dict]:
        """Suggest callbacks based on previous gags and freshness."""
        suggestions = []
        current_words = set(current_text.lower().split())

        for gag in self.gags.values():
            if gag.performer_id != performer_id:
                continue
            # Freshness decay
            episodes_since = (time.time() - gag.last_used_at) / (7 * 24 * 3600)  # weeks
            freshness = math.exp(-self._decay_rate * episodes_since)

            if freshness > 0.3 and gag.keyword in current_words:
                suggestions.append({
                    "keyword": gag.keyword,
                    "freshness": round(freshness, 2),
                    "total_laughs": gag.total_laughs,
                    "callback_count": gag.callback_count,
                    "suggestion": f"Callback to '{gag.keyword}' — {gag.callback_count} previous references",
                })

        return sorted(suggestions, key=lambda s: s["freshness"], reverse=True)

    def get_stats(self, performer_id: str) -> dict:
        """Get callback stats for a performer."""
        performer_gags = [g for g in self.gags.values() if g.performer_id == performer_id]
        return {
            "total_gags": len(performer_gags),
            "total_callbacks": sum(g.callback_count for g in performer_gags),
            "total_setups": sum(g.setup_count for g in performer_gags),
            "best_keyword": max(performer_gags, key=lambda g: g.total_laughs).keyword if performer_gags else None,
        }

    def _extract_keyword(self, setup: str, callback: str) -> str | None:
        """Extract the key concept linking setup to callback."""
        setup_words = set(setup.lower().split())
        callback_words = set(callback.lower().split())
        overlap = setup_words & callback_words
        # Remove common words
        stopwords = {"i", "the", "a", "is", "it", "to", "and", "of", "my", "you", "that", "this", "was"}
        meaningful = overlap - stopwords
        if meaningful:
            return max(meaningful, key=lambda w: len(w))
        return None
