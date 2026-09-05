"""HTTP request and response schemas for the LinkGround measurement API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class EvaluateRequest(BaseModel):
    urls: List[HttpUrl] = Field(..., description="Evidence links used to measure the LLM statement")
    statement: str = Field(
        ...,
        description="LLM-generated statement to measure against the linked sources",
        alias="llm_output_to_test",
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
    groundedness_score: float = Field(..., description="Continuous [0, 1] support vs linked sources")
    source_authority_multiplier: float = Field(
        ..., description="Mean Open PageRank authority multiplier across links"
    )
    final_verified_trust_index: float = Field(
        ...,
        description="groundedness_score * source_authority_multiplier, capped at 1.0",
    )
    academic_reasoning: str = Field(..., description="Analyst claim and support breakdown")
    per_url_authority: List[UrlAuthority] = Field(default_factory=list)
    model_used: str
    claim_count_expected: int
