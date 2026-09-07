"""Clip package planner — the distribution engine.

Every minute automatically becomes a content package. The runtime already
knows set start/end, camera cuts, captions, laugh spikes and scores, so
finishing a set generates a deterministic export plan:

  full-set-16x9  — YouTube / Rumble / archive (hook + set + score flash)
  full-set-9x16  — TikTok / Reels / Shorts (63-75s, clears the 1-min rule)
  best-20s       — viral hook (peak laugh-density window)
  best-40s       — longer social clip (peak laugh-density window)
  score-reveal   — panel content (from event seq range)
  ella-roast     — reaction content (from event seq range)
  thumbnail      — peak laugh moment timestamp
  captions       — SRT + JSON from word timings
  manifest       — freaktown.clips.v1 (ML + export jobs)

This service plans; it does not render. Rendering is an ffmpeg cut-list
executed against the episode recording (OBS local record). Boundaries are
computed from data, never guessed.
"""

from dataclasses import dataclass, field

SCHEMA_VERSION = "freaktown.clips.v1"

# TikTok Creator Rewards requires >= 60s. Canonical export is hook + set +
# score flash, clamped to 63-75s. Padding extends the tail (never the set).
TIKTOK_MIN_MS = 63_000
TIKTOK_MAX_MS = 75_000
TIKTOK_HOOK_MS = 2_000
TIKTOK_SCORE_FLASH_MS = 3_000


@dataclass
class LaughBucket:
    """One crowd bucket. start_ms is ms since set start."""
    start_ms: int
    laugh_events: int = 0
    unique_laughers: int = 0
    claps: int = 0


@dataclass
class Word:
    word: str
    start_ms: int
    end_ms: int


@dataclass
class ClipSegment:
    name: str
    start_ms: int
    end_ms: int
    purpose: str
    aspect: str = "16x9"

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "purpose": self.purpose,
            "aspect": self.aspect,
        }


@dataclass
class ClipPackage:
    performance_id: str
    character_slug: str
    episode_id: str
    set_start_ms: int = 0
    set_end_ms: int = 0
    segments: list[ClipSegment] = field(default_factory=list)
    thumbnail_at_ms: int = 0
    captions_srt: str = ""
    captions_json: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": SCHEMA_VERSION,
            "performance_id": self.performance_id,
            "character_slug": self.character_slug,
            "episode_id": self.episode_id,
            "set_start_ms": self.set_start_ms,
            "set_end_ms": self.set_end_ms,
            "thumbnail_at_ms": self.thumbnail_at_ms,
            "segments": [s.to_dict() for s in self.segments],
            "captions_srt": self.captions_srt,
            "captions_json": self.captions_json,
        }


def find_best_window(buckets: list[LaughBucket], window_ms: int) -> tuple[int, int, int]:
    """Sliding window over laugh buckets. Returns (start_ms, end_ms, laughs).

    Scores by laugh_events (volume) with unique_laughers as tiebreak
    (breadth beats a single spammer). Empty input → (0, window_ms, 0).
    """
    if not buckets:
        return (0, window_ms, 0)

    points = sorted(
        ((b.start_ms, b.laugh_events, b.unique_laughers) for b in buckets),
        key=lambda p: p[0],
    )

    best: tuple[int, int, int] | None = None
    for i, (start, _, _) in enumerate(points):
        end = start + window_ms
        laughs = 0
        breadth = 0
        for s, le, ul in points[i:]:
            if s >= end:
                break
            laughs += le
            breadth = max(breadth, ul)
        key = (laughs, breadth)
        if best is None or key > (best[2], best[3]):
            best = (start, end, laughs, breadth)

    assert best is not None
    return (best[0], best[1], best[2])


def peak_moment(buckets: list[LaughBucket]) -> int:
    """Timestamp of the single highest-laugh bucket. Thumbnail anchor."""
    if not buckets:
        return 0
    return max(buckets, key=lambda b: (b.laugh_events, b.unique_laughers)).start_ms


def tiktok_plan(set_ms: int) -> dict:
    """63-75s TikTok-safe export plan.

    Layout: 2s hook + full set + score flash, tail-padded to >= 63s,
    tail-trimmed to <= 75s. The set itself is never cut.
    """
    hook = TIKTOK_HOOK_MS
    flash = TIKTOK_SCORE_FLASH_MS
    total = hook + set_ms + flash
    pad = 0
    if total < TIKTOK_MIN_MS:
        pad = TIKTOK_MIN_MS - total
        total = TIKTOK_MIN_MS
    elif total > TIKTOK_MAX_MS:
        over = total - TIKTOK_MAX_MS
        # Trim flash first, then hook; set is sacred.
        trim_flash = min(flash, over)
        flash -= trim_flash
        over -= trim_flash
        trim_hook = min(hook, over)
        hook -= trim_hook
        over -= trim_hook
        total = hook + set_ms + flash + pad
    return {
        "hook_ms": hook,
        "set_ms": set_ms,
        "score_flash_ms": flash,
        "pad_ms": pad,
        "total_ms": total,
    }


def words_to_srt(words: list[Word]) -> str:
    """Word timings → SRT. Groups words into ~2s caption cues."""
    if not words:
        return ""
    cues: list[list[Word]] = []
    current: list[Word] = []
    for w in words:
        current.append(w)
        if w.end_ms - current[0].start_ms >= 2000 or len(current) >= 8:
            cues.append(current)
            current = []
    if current:
        cues.append(current)

    out: list[str] = []
    for i, cue in enumerate(cues, 1):
        out.append(str(i))
        out.append(f"{_srt_ts(cue[0].start_ms)} --> {_srt_ts(cue[-1].end_ms)}")
        out.append(" ".join(w.word for w in cue))
        out.append("")
    return "\n".join(out)


def _srt_ts(ms: int) -> str:
    ms = max(0, ms)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def words_to_captions_json(words: list[Word]) -> list[dict]:
    return [{"word": w.word, "start_ms": w.start_ms, "end_ms": w.end_ms} for w in words]


def plan_package(
    performance_id: str,
    character_slug: str,
    episode_id: str,
    duration_ms: int,
    buckets: list[LaughBucket],
    words: list[Word],
    score_reveal_ms: tuple[int, int] | None = None,
    ella_roast_ms: tuple[int, int] | None = None,
) -> ClipPackage:
    """Build the full automatic content package for one finished set."""
    pkg = ClipPackage(
        performance_id=performance_id,
        character_slug=character_slug,
        episode_id=episode_id,
        set_start_ms=0,
        set_end_ms=duration_ms,
        thumbnail_at_ms=peak_moment(buckets),
        captions_srt=words_to_srt(words),
        captions_json=words_to_captions_json(words),
    )

    tp = tiktok_plan(duration_ms)

    pkg.segments = [
        ClipSegment(
            name="full-set-16x9.mp4",
            start_ms=0,
            end_ms=tp["hook_ms"] + duration_ms + tp["score_flash_ms"] + tp["pad_ms"],
            purpose="youtube/rumble/archive",
            aspect="16x9",
        ),
        ClipSegment(
            name="full-set-9x16.mp4",
            start_ms=0,
            end_ms=tp["total_ms"],
            purpose="tiktok/reels/shorts (63-75s, clears 1-min rule)",
            aspect="9x16",
        ),
    ]

    best20 = find_best_window(buckets, 20_000)
    pkg.segments.append(ClipSegment(
        name="best-20s.mp4", start_ms=best20[0], end_ms=best20[1],
        purpose=f"viral hook ({best20[2]} laughs in window)", aspect="9x16",
    ))

    best40 = find_best_window(buckets, 40_000)
    pkg.segments.append(ClipSegment(
        name="best-40s.mp4", start_ms=best40[0], end_ms=best40[1],
        purpose=f"longer social clip ({best40[2]} laughs in window)", aspect="9x16",
    ))

    if score_reveal_ms:
        pkg.segments.append(ClipSegment(
            name="score-reveal.mp4", start_ms=score_reveal_ms[0], end_ms=score_reveal_ms[1],
            purpose="panel content", aspect="16x9",
        ))

    if ella_roast_ms:
        pkg.segments.append(ClipSegment(
            name="ella-roast.mp4", start_ms=ella_roast_ms[0], end_ms=ella_roast_ms[1],
            purpose="reaction content", aspect="9x16",
        ))

    return pkg


def ffmpeg_cut_list(pkg: ClipPackage, source_path: str, out_dir: str) -> list[str]:
    """Render plan → ffmpeg commands cutting segments from a recording.

    Cuts on exact ms boundaries (`-ss`/`-t` after `-i` for accuracy).
    Re-encode is left to the operator (add `-c copy` for speed when the
    source codec allows clean cuts, or libx264 for frame accuracy).
    """
    cmds = []
    for seg in pkg.segments:
        start_s = seg.start_ms / 1000
        dur_s = seg.duration_ms / 1000
        out_path = f"{out_dir.rstrip('/')}/{pkg.character_slug}-{seg.name}"
        cmds.append(
            f'ffmpeg -v error -y -i "{source_path}" -ss {start_s:.3f} -t {dur_s:.3f} '
            f'"{out_path}"'
        )
    thumb = f"{out_dir.rstrip('/')}/{pkg.character_slug}-thumbnail.jpg"
    cmds.append(
        f'ffmpeg -v error -y -i "{source_path}" -ss {pkg.thumbnail_at_ms / 1000:.3f} '
        f'-frames:v 1 "{thumb}"'
    )
    return cmds
