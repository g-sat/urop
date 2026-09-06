from __future__ import annotations

from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field, HttpUrl, model_validator


class EvaluateRequest(BaseModel):
    urls: List[HttpUrl] = Field(
        default_factory=list,
        description="Evidence URLs. Optional if discover_evidence is on.",
    )
    statement: str = Field(
        ...,
        description="Claim / LLM statement to score",
        validation_alias=AliasChoices("statement", "llm_output_to_test"),
    )
    model: Optional[str] = Field(default="llama3.1", description="Ollama judge model")
    judge_runs: int = Field(default=1, ge=1, le=5, description="Average this many judge passes")
    discover_evidence: bool = Field(
        default=False,
        description="Find trusted pages when urls are missing",
    )
    discovery_depth: int = Field(default=1, ge=0, le=2, description="Trusted-link BFS depth")
    max_discovered_urls: int = Field(default=4, ge=1, le=8, description="Cap on discovered URLs")
    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def require_urls_or_discovery(self) -> "EvaluateRequest":
        if not self.urls and not self.discover_evidence:
            return self.model_copy(update={"discover_evidence": True})
        return self


class UrlAuthority(BaseModel):
    url: str
    domain: str
    authority_multiplier: float


class EvidenceItem(BaseModel):
    url: str
    source: str = Field(..., description="live | cache | fallback")
    char_count: int
    usable: bool = Field(..., description="False when only fallback text was used")
    origin: str = Field(default="caller", description="caller | discovered")


class DiscoveredUrlItem(BaseModel):
    url: str
    score: float = Field(..., description="Claim/page overlap used to rank hits")
    origin: str
    title: str = ""


class EvaluateResponse(BaseModel):
    groundedness_score: float = Field(..., description="Primary support score in [0, 1]")
    authority_multiplier: float = Field(..., description="Mean OPR prestige — not truth")
    trust_index: float = Field(..., description="support × prestige (secondary)")
    analyst_reasoning: str
    per_url_authority: List[UrlAuthority] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    evidence_quality: float
    evidence_mode: str = Field(default="caller", description="caller | discovered | mixed")
    discovery_weight: float = Field(default=1.0, description="1.0 for caller links; lower for discovery")
    discovered_urls: List[DiscoveredUrlItem] = Field(default_factory=list)
    judge_std: Optional[float] = None
    model_used: str
    claim_count: int
    notes: List[str] = Field(default_factory=list)
    research: dict = Field(default_factory=dict, description="LCSE block: support, prestige, flags")
