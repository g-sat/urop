"""HTTP request and response schemas for the LinkGround measurement API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field, HttpUrl


class EvaluateRequest(BaseModel):
    """Measure an LLM statement against linked evidence pages."""

    urls: List[HttpUrl] = Field(..., description="Evidence URLs used to ground the statement")
    statement: str = Field(
        ...,
        description="LLM statement to measure",
        validation_alias=AliasChoices("statement", "llm_output_to_test"),
    )
    model: Optional[str] = Field(
        default="llama3.1",
        description="Local Ollama model used as the closed-context analyst",
    )

    model_config = {"populate_by_name": True}


class UrlAuthority(BaseModel):
    url: str
    domain: str
    authority_multiplier: float


class EvaluateResponse(BaseModel):
    groundedness_score: float = Field(..., description="Continuous support in [0, 1] vs linked evidence")
    authority_multiplier: float = Field(..., description="Mean Open PageRank authority across links")
    trust_index: float = Field(
        ...,
        description="groundedness_score * authority_multiplier, capped at 1.0",
    )
    analyst_reasoning: str = Field(..., description="Claim-level SUPPORT breakdown from the analyst")
    per_url_authority: List[UrlAuthority] = Field(default_factory=list)
    model_used: str
    claim_count: int = Field(..., description="Expected atomic claim count used for scoring")
