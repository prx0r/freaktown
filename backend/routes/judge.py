"""Judge panel routes — three-judge scoring API.

POST /v1/judge/score    → run Ella + ChatGPT + Stream on a set
GET  /v1/judge/rubric   → score a set with the 5-dimension rubric
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.services.judge.panel import JudgePanel, generate_panel_argument
from backend.services.scoring.rubric import RubricScorer

router = APIRouter()

_judge_panel = JudgePanel()
_rubric_scorer = RubricScorer()


class JudgeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="The comedy set transcript")
    events: list[dict] = Field(default_factory=list, description="Audience reaction events")


@router.post("/judge/score")
async def score_set(req: JudgeRequest):
    """Run the three-judge panel on a set."""
    result = _judge_panel.judge_set(req.text, req.events)
    argument = generate_panel_argument(result)
    return {
        **result.to_dict(),
        "argument": argument or None,
    }


class RubricRequest(BaseModel):
    text: str = Field(..., min_length=1)


@router.post("/judge/rubric")
async def rubric_score(req: RubricRequest):
    """Score a set with the 5-dimension rubric."""
    return {"rubric": _rubric_scorer.score(req.text)}
