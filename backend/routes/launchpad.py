"""Launchpad API — character profiles, leaderboard, clips, pot, tickets.

The viral surface of Freak Town. Profiles and leaderboard are public
(characters must be able to escape the show); mutations are admin-only.

  POST /v1/clips/plan            → automatic content package for a set
  GET  /v1/characters/{slug}     → public character profile + record
  GET  /v1/leaderboard           → ranked character records
  GET  /v1/pot                   → tonight's pot (+ season pot)
  POST /v1/pot/contribute        → admin: add to the pot (event-sourced)
  POST /v1/tickets/issue         → admin/Ella: issue numbered Golden Ticket
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import require_admin_from_api_key
from backend.db import get_db
from backend.models import Appearance, Comedian, JudgeRun, ShowEvent, Submission, User
from backend.services.clips import (
    LaughBucket,
    Word,
    ffmpeg_cut_list,
    plan_package,
)
from backend.services.events import emit_event
from backend.services.pot import (
    POT_EVENT_TYPE,
    contribution_payload,
    format_usd,
    pot_total,
    pot_total_for_episode,
    validate_contribution,
)
from backend.services.reputation import (
    AppearanceResult,
    aggregate_character,
    aggregate_creator,
    creator_code,
    leaderboard,
    next_ticket_number,
    ticket_label,
)

router = APIRouter()

TICKET_EVENT_TYPE = "award.golden_ticket"


# ── Clips ────────────────────────────────────────────────────────────

class BucketIn(BaseModel):
    start_ms: int
    laugh_events: int = 0
    unique_laughers: int = 0
    claps: int = 0


class WordIn(BaseModel):
    word: str
    start_ms: int
    end_ms: int


class ClipPlanRequest(BaseModel):
    performance_id: str
    character_slug: str
    episode_id: str
    duration_ms: int = Field(..., gt=0)
    buckets: list[BucketIn] = Field(default_factory=list)
    words: list[WordIn] = Field(default_factory=list)
    score_reveal_ms: tuple[int, int] | None = None
    ella_roast_ms: tuple[int, int] | None = None
    source_path: str = ""
    out_dir: str = ""


@router.post("/clips/plan")
async def plan_clips(req: ClipPlanRequest):
    """Generate the automatic content package for one finished set.

    Pure function of performance data — no DB. Returns the
    freaktown.clips.v1 manifest plus ffmpeg cut commands when a
    source recording path and output dir are provided.
    """
    pkg = plan_package(
        performance_id=req.performance_id,
        character_slug=req.character_slug,
        episode_id=req.episode_id,
        duration_ms=req.duration_ms,
        buckets=[LaughBucket(**b.model_dump()) for b in req.buckets],
        words=[Word(**w.model_dump()) for w in req.words],
        score_reveal_ms=req.score_reveal_ms,
        ella_roast_ms=req.ella_roast_ms,
    )
    out = pkg.to_dict()
    if req.source_path and req.out_dir:
        out["ffmpeg_cut_list"] = ffmpeg_cut_list(pkg, req.source_path, req.out_dir)
    return out


# ── Character profiles ───────────────────────────────────────────────

def _scores_from_runs(runs: list[JudgeRun]) -> tuple[float | None, float | None]:
    ella: float | None = None
    stream: float | None = None
    for r in runs:
        out = r.output_json or {}
        e = (out.get("ella") or {}).get("score")
        s = (out.get("stream") or {}).get("score")
        if isinstance(e, (int, float)):
            ella = e if ella is None else max(ella, e)
        if isinstance(s, (int, float)):
            stream = s if stream is None else max(stream, s)
    return ella, stream


async def _tickets_for_comedian(db: AsyncSession, comedian_id: str) -> list[dict]:
    """Full Golden Ticket records for one character, oldest first."""
    result = await db.execute(
        select(ShowEvent)
        .where(ShowEvent.type == TICKET_EVENT_TYPE)
        .order_by(ShowEvent.created_at)
    )
    tickets = []
    for e in result.scalars().all():
        payload = e.payload or {}
        if str(payload.get("comedian_id")) != str(comedian_id):
            continue
        num = payload.get("ticket_number")
        if isinstance(num, int):
            tickets.append({
                "number": num,
                "episode_id": str(e.episode_id),
                "appearance_id": payload.get("appearance_id"),
                "label": ticket_label(num, str(e.episode_id)),
            })
    return sorted(tickets, key=lambda t: t["number"])


async def _ticket_numbers_by_comedian(db: AsyncSession) -> dict[str, list[int]]:
    """All issued Golden Ticket numbers, keyed by comedian id. Tickets are scarce."""
    result = await db.execute(select(ShowEvent).where(ShowEvent.type == TICKET_EVENT_TYPE))
    mapping: dict[str, list[int]] = {}
    for e in result.scalars().all():
        payload = e.payload or {}
        cid = payload.get("comedian_id")
        num = payload.get("ticket_number")
        if cid and isinstance(num, int):
            mapping.setdefault(str(cid), []).append(num)
    return mapping


async def _results_for_comedian(
    db: AsyncSession, comedian_id: uuid.UUID
) -> list[AppearanceResult]:
    ap_result = await db.execute(
        select(Appearance, Submission)
        .join(Submission, Appearance.submission_id == Submission.id)
        .where(Submission.comedian_id == comedian_id)
        .order_by(Appearance.draw_position)
    )
    rows = ap_result.all()
    if not rows:
        return []

    ap_ids = [ap.id for ap, _ in rows]
    jr_result = await db.execute(select(JudgeRun).where(JudgeRun.appearance_id.in_(ap_ids)))
    runs_by_ap: dict[str, list[JudgeRun]] = {}
    for jr in jr_result.scalars().all():
        runs_by_ap.setdefault(str(jr.appearance_id), []).append(jr)

    results = []
    for ap, _ in rows:
        ella_score, stream_score = _scores_from_runs(runs_by_ap.get(str(ap.id), []))
        res = (ap.result_json or {})
        results.append(AppearanceResult(
            appearance_id=str(ap.id),
            comedian_id=str(comedian_id),
            ella_verdict=ap.ella_verdict,
            ella_score=ella_score,
            stream_score=stream_score,
            peak_laugh_share=ap.peak_laugh_share,
            golden_ticket=bool(res.get("golden_ticket")),
        ))
    return results


@router.get("/characters/{slug}")
async def character_profile(slug: str, db: AsyncSession = Depends(get_db)):
    """Public character profile: identity, record, tickets, sets.

    This is the tap-through target at the bottom of every viral clip.
    """
    result = await db.execute(select(Comedian).where(Comedian.slug == slug))
    comedian = result.scalar_one_or_none()
    if not comedian:
        raise HTTPException(404, "Character not found")

    results = await _results_for_comedian(db, comedian.id)
    record = aggregate_character(str(comedian.id), results)

    tickets = await _tickets_for_comedian(db, str(comedian.id))

    return {
        "id": str(comedian.id),
        "name": comedian.name,
        "slug": comedian.slug,
        "premise": comedian.premise,
        "body_archetype": comedian.body_archetype,
        "status": comedian.status,
        "created_at": str(comedian.created_at),
        "created_by": creator_code(comedian.owner_user_id),
        "record": record.to_dict(),
        "golden_tickets": tickets,
        "sets": [
            {
                "appearance_id": r.appearance_id,
                "ella_verdict": r.ella_verdict,
                "ella_score": r.ella_score,
                "stream_score": r.stream_score,
                "peak_laugh_share": r.peak_laugh_share,
                "golden_ticket": r.golden_ticket,
            }
            for r in results
        ],
    }


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Ranked character records: wins, then best Ella, then fewest losses."""
    com_result = await db.execute(
        select(Comedian).where(Comedian.status == "active").limit(limit * 2)
    )
    comedians = list(com_result.scalars().all())

    records = []
    names = {}
    for c in comedians:
        results = await _results_for_comedian(db, c.id)
        if not results:
            continue
        records.append(aggregate_character(str(c.id), results))
        names[str(c.id)] = {"name": c.name, "slug": c.slug}

    ranked = leaderboard(records, limit=limit)
    return {
        "leaderboard": [
            {**r.to_dict(), **names.get(r.comedian_id, {})} for r in ranked
        ]
    }


@router.get("/creators/{code}")
async def creator_profile(code: str, db: AsyncSession = Depends(get_db)):
    """Public pseudonymous creator profile, looked up by creator code.

    Note: reverse lookup scans users (fine at Episode Zero scale;
    add a stored creator_code column before public launch).
    """
    com_result = await db.execute(select(Comedian))
    by_creator: dict[str, list[str]] = {}
    owners: dict[str, uuid.UUID] = {}
    for c in com_result.scalars().all():
        cc = creator_code(c.owner_user_id)
        by_creator.setdefault(cc, []).append(str(c.id))
        owners[cc] = c.owner_user_id

    if code not in by_creator:
        raise HTTPException(404, "Creator not found")

    records = {}
    for cid in by_creator[code]:
        results = await _results_for_comedian(db, uuid.UUID(cid))
        records[cid] = aggregate_character(cid, results)

    stats = aggregate_creator(owners[code], by_creator[code], records)
    return stats.to_dict()


# ── The Pot ──────────────────────────────────────────────────────────

@router.get("/pot")
async def get_pot(
    episode_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Tonight's pot (and the season pot). May be $0.00. That's funny."""
    result = await db.execute(select(ShowEvent).where(ShowEvent.type == POT_EVENT_TYPE))
    events = [
        {"type": e.type, "episode_id": str(e.episode_id), "payload": e.payload or {}}
        for e in result.scalars().all()
    ]
    season_cents = pot_total(events)
    out: dict = {
        "season_pot_cents": season_cents,
        "season_pot": format_usd(season_cents),
    }
    if episode_id is not None:
        tonight = pot_total_for_episode(events, str(episode_id))
        out["tonight_pot_cents"] = tonight
        out["tonight_pot"] = format_usd(tonight)
    return out


class PotContributeRequest(BaseModel):
    episode_id: uuid.UUID
    amount_cents: int = Field(..., gt=0)
    source: str = "manual"
    note: str = ""


@router.post("/pot/contribute", status_code=201)
async def contribute_to_pot(
    req: PotContributeRequest,
    user: User = Depends(require_admin_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Admin: add to the pot. Recorded as a pot.contribution ShowEvent."""
    try:
        payload = contribution_payload(req.amount_cents, req.source, req.note)
    except ValueError as e:
        raise HTTPException(400, str(e))

    await emit_event(db, req.episode_id, POT_EVENT_TYPE, f"admin:{user.id}", payload)
    await db.flush()

    result = await db.execute(
        select(ShowEvent).where(
            ShowEvent.type == POT_EVENT_TYPE,
            ShowEvent.episode_id == req.episode_id,
        )
    )
    events = [
        {"type": POT_EVENT_TYPE, "episode_id": str(req.episode_id), "payload": e.payload or {}}
        for e in result.scalars().all()
    ]
    tonight = pot_total(events)
    return {"tonight_pot_cents": tonight, "tonight_pot": format_usd(tonight)}


# ── Golden Tickets ───────────────────────────────────────────────────

class TicketIssueRequest(BaseModel):
    episode_id: uuid.UUID
    appearance_id: uuid.UUID
    comedian_id: uuid.UUID


@router.post("/tickets/issue", status_code=201)
async def issue_ticket(
    req: TicketIssueRequest,
    user: User = Depends(require_admin_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Ella (via admin) issues a numbered Golden Ticket to a character.

    Numbering is global and append-only: tickets are scarce forever.
    Writes both the award.golden_ticket event and the appearance flag.
    """
    ap_result = await db.execute(select(Appearance).where(Appearance.id == req.appearance_id))
    appearance = ap_result.scalar_one_or_none()
    if not appearance:
        raise HTTPException(404, "Appearance not found")
    if appearance.episode_id != req.episode_id:
        raise HTTPException(400, "Appearance is not in this episode")

    tickets_by_comedian = await _ticket_numbers_by_comedian(db)
    all_numbers = [n for nums in tickets_by_comedian.values() for n in nums]
    number = next_ticket_number(all_numbers)

    payload = {
        "ticket_number": number,
        "comedian_id": str(req.comedian_id),
        "appearance_id": str(req.appearance_id),
        "issued_by": "ella",
        "label": ticket_label(number, str(req.episode_id)),
    }
    await emit_event(db, req.episode_id, TICKET_EVENT_TYPE, f"ella:{user.id}", payload)

    res = dict(appearance.result_json or {})
    res["golden_ticket"] = True
    res["golden_ticket_number"] = number
    appearance.result_json = res
    await db.flush()

    return {"ticket_number": number, "label": payload["label"]}
