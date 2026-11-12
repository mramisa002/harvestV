from datetime import date
from typing import Literal
from pydantic import BaseModel, Field


class Window(BaseModel):
    start: date
    end: date
    mean_score: float = Field(ge=0, le=100)


class Candidate(BaseModel):
    day: date
    score: float = Field(ge=0, le=100)
    smoothed_score: float = Field(ge=0, le=100)
    vetoes: list[str]
    components: dict[str, float]
    basis: str


class Advisory(BaseModel):
    district: str
    district_id: str
    crop: str
    status: Literal['GO', 'WAIT', 'AVOID']
    today_score: float = Field(ge=0, le=100)
    best_window: Window | None
    next_best_window: Window | None
    reasons: list[str]
    action: str
    confidence: Literal['HIGH', 'MEDIUM', 'LOW']
    confidence_reason: str
    data_freshness: dict[str, date | None]
    model_version: str
    candidates: list[Candidate]
    indicators: dict[str, float]
    limitations: list[str]
    soil_estimate_method: str
    advisory_type: str
