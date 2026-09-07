"""Show API — daily show endpoints.

The daily show: Ella intro → 5 acts → return vote → outro.
No live LLM. No conversation. No crypto. No judges.

Reference: anime.dm — Episode 1 format
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.show_runtime import show_runner, ShowAct
from backend.services.chat_summary import chat_summary_engine, ChatSummary

router = APIRouter()


# ── Request Schemas ─────────────────────────────────────────────────

class ActSpec(BaseModel):
    character_name: str = Field(..., description="Character name")
    comedian_id: str = Field("", description="Comedian ID")
    performance_plan: dict = Field(default_factory=dict, description="Compiled performance plan")
    audio_url: str = Field("", description="Audio R2 key or URL")
    duration_ms: int = Field(60000, description="Duration in ms")


class CreateShowRequest(BaseModel):
    date: str = Field(..., description="Show date (YYYY-MM-DD)")
    acts: list[ActSpec] = Field(..., description="Acts to include (max 5)")


class LaughRecord(BaseModel):
    act_id: str
    timestamp_ms: int


class VoteRecord(BaseModel):
    act_id: str
    vote: bool  # True = YES, False = NO


class ChatMessage(BaseModel):
    act_id: str
    messages: list[str]


# ── Show Endpoints ──────────────────────────────────────────────────

@router.post("/shows")
async def create_show(req: CreateShowRequest):
    """Create a new daily show from act specs."""
    acts = []
    for i, spec in enumerate(req.acts[:5]):
        act = ShowAct(
            position=i + 1,
            comedian_id=spec.comedian_id,
            character_name=spec.character_name,
            performance_plan=spec.performance_plan,
            audio_url=spec.audio_url,
            duration_ms=spec.duration_ms,
        )
        acts.append(act)

    show = show_runner.create_show(req.date, acts)
    return {"show": show.to_dict()}


@router.post("/shows/{show_id}/start")
async def start_show(show_id: str):
    """Start the show."""
    show = show_runner.start_show(show_id)
    return {"show": show.to_dict(), "phase": "ella_intro"}


@router.post("/shows/{show_id}/acts/{act_id}/start")
async def start_act(show_id: str, act_id: str):
    """Start playing an act."""
    act = show_runner.start_act(show_id, act_id)
    show = show_runner.shows.get(show_id)
    return {
        "act": act.to_dict(),
        "show_phase": show.phase.value if show else "unknown",
    }


@router.post("/shows/{show_id}/acts/{act_id}/end")
async def end_act(show_id: str, act_id: str):
    """End an act — transition to return voting."""
    act = show_runner.end_act(show_id, act_id)
    return {
        "act": act.to_dict(),
        "show_phase": "return_vote",
        "return_vote_window_sec": 5,
    }


@router.post("/shows/{show_id}/laugh")
async def record_laugh(show_id: str, req: LaughRecord):
    """Record a HAHA click at a timestamp."""
    show_runner.record_laugh(show_id, req.act_id, req.timestamp_ms)

    show = show_runner.shows.get(show_id)
    act = show.get_act(req.act_id) if show else None
    return {
        "laugh_count": act.laugh_count if act else 0,
        "total_laughs": show.total_laughs if show else 0,
    }


@router.post("/shows/{show_id}/vote")
async def record_vote(show_id: str, req: VoteRecord):
    """Record a SEE THEM AGAIN? vote."""
    show_runner.record_return_vote(show_id, req.act_id, req.vote)

    show = show_runner.shows.get(show_id)
    act = show.get_act(req.act_id) if show else None
    return {
        "return_votes": act.return_votes if act else 0,
        "return_total": act.return_total if act else 0,
        "return_rate": act.return_rate if act else 0,
    }


@router.post("/shows/{show_id}/chat")
async def process_chat(show_id: str, req: ChatMessage):
    """Process chat messages and generate summary for an act."""
    show = show_runner.shows.get(show_id)
    if not show:
        raise HTTPException(404, "Show not found")

    act = show.get_act(req.act_id)
    if not act:
        raise HTTPException(404, "Act not found")

    summary = chat_summary_engine.analyze(
        req.messages,
        return_votes=act.return_votes,
        total_viewers=act.return_total,
    )

    return {
        "labels": summary.labels,
        "nicknames": summary.nicknames,
        "top_reactions": summary.top_reactions,
        "sentiment": summary.sentiment,
        "sentiment_score": summary.sentiment_score,
        "highlight_quotes": summary.highlight_quotes,
    }


@router.post("/shows/{show_id}/end")
async def end_show(show_id: str):
    """End the show — Ella outro."""
    show = show_runner.end_show(show_id)
    return {"show": show.to_dict()}


@router.get("/shows/{show_id}/summary")
async def get_show_summary(show_id: str):
    """Get post-show summary with all audience data."""
    summary = show_runner.get_show_summary(show_id)
    if not summary:
        raise HTTPException(404, "Show not found")

    # Generate per-act reviews
    for act_data in summary.get("acts", []):
        char_name = act_data.get("character_name", "Unknown")
        act_summary = ChatSummary(
            labels=[],
            top_reactions=[],
            return_rate=act_data.get("return_rate", 0) / 100,
        )
        act_data["review"] = chat_summary_engine.generate_review(act_summary, char_name)

    return {"summary": summary}


@router.get("/shows/{show_id}/timeline")
async def get_laugh_timeline(show_id: str, act_id: str):
    """Get the laugh timeline for an act."""
    show = show_runner.shows.get(show_id)
    if not show:
        raise HTTPException(404, "Show not found")

    act = show.get_act(act_id)
    if not act:
        raise HTTPException(404, "Act not found")

    max_count = max((b["count"] for b in act.laugh_timeline), default=1)
    timeline = []
    for ms in range(0, act.duration_ms, 1000):
        window_count = sum(
            b["count"] for b in act.laugh_timeline
            if ms <= b["ms"] < ms + 1000
        )
        intensity = window_count / max_count if max_count > 0 else 0
        timeline.append({
            "sec": ms // 1000,
            "laughs": window_count,
            "intensity": round(intensity, 2),
        })

    return {
        "act_id": act_id,
        "duration_sec": act.duration_ms // 1000,
        "total_laughs": act.laugh_count,
        "peak_laugh_ms": act.peak_laugh_ms,
        "peak_laugh_pct": act.peak_laugh_pct,
        "timeline": timeline,
    }


@router.get("/shows")
async def list_shows():
    """List all shows."""
    return {
        "shows": [s.to_dict() for s in show_runner.shows.values()]
    }
