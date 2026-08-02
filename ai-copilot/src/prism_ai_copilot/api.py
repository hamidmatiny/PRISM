"""FastAPI surface for Ask PRISM."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from prism_ai_copilot import __version__
from prism_ai_copilot.config import CopilotConfig
from prism_ai_copilot.graph import run_ask


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    control_plane_token: str | None = Field(
        default=None,
        description="Bearer token for control-plane tools (viewer/inspector).",
    )


class AskResponse(BaseModel):
    answer: str
    grounded: bool
    tools_used: list[str]
    tool_calls: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    redactions: list[str] = []
    error: str | None = None


def create_app(config: CopilotConfig | None = None) -> FastAPI:
    cfg = config or CopilotConfig.from_env()
    app = FastAPI(
        title="PRISM AI Copilot",
        version=__version__,
        description="Tool-grounded Ask PRISM — ADR-004 non-fabrication.",
    )
    app.state.config = cfg
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    try:
        from prism_otel import instrument_fastapi

        instrument_fastapi(app, "ai-copilot")
    except ImportError:
        pass

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "ai-copilot",
            "version": __version__,
            "activation_url": cfg.activation_url,
            "control_plane_url": cfg.control_plane_url,
        }

    @app.post("/v1/ask", response_model=AskResponse)
    def ask(body: AskRequest) -> AskResponse:
        result = run_ask(
            body.question,
            config=cfg,
            control_plane_token=body.control_plane_token,
        )
        return AskResponse(
            answer=result.answer,
            grounded=result.grounded,
            tools_used=result.tools_used,
            tool_calls=result.tool_calls,
            evidence=result.evidence,
            redactions=result.redactions,
            error=result.error,
        )

    return app
