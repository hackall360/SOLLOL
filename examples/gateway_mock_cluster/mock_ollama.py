"""Lightweight FastAPI mock mimicking a subset of Ollama's HTTP API.

This module provides stub implementations of the `/api/chat`, `/api/generate`,
and `/api/embed` endpoints so integration tests and local demos can run
without a real Ollama runtime.  Responses are deterministic to keep example
outputs predictable.
"""

from __future__ import annotations

import argparse
import os
from typing import List, Sequence, Union

from fastapi import FastAPI
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Minimal representation of a chat message."""

    role: str
    content: str


class ChatRequest(BaseModel):
    """Subset of the Ollama chat payload used in the mock cluster examples."""

    model: str
    messages: List[ChatMessage]
    stream: bool = False


class GenerateRequest(BaseModel):
    """Subset of the generate payload used by the mock cluster demo."""

    model: str
    prompt: str
    stream: bool = False


class EmbedRequest(BaseModel):
    """Subset of the embed payload used by the mock cluster demo."""

    model: str
    input: Union[str, Sequence[str]] = Field(..., description="Text to embed")


app = FastAPI(title="Mock Ollama Service", version="0.1.0")


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Simple readiness endpoint."""

    return {"status": "ok"}


@app.post("/api/chat")
async def chat_endpoint(_: ChatRequest) -> dict[str, object]:
    """Return a deterministic chat completion payload."""

    return {
        "model": "llama3.2",
        "created_at": "2024-01-01T00:00:00Z",
        "message": {"role": "assistant", "content": "ready"},
        "done": True,
    }


@app.post("/api/generate")
async def generate_endpoint(_: GenerateRequest) -> dict[str, object]:
    """Return a deterministic generate response payload."""

    return {
        "model": "llama3.2",
        "created_at": "2024-01-01T00:00:00Z",
        "response": "Status: ready.",
        "done": True,
    }


@app.post("/api/embed")
async def embed_endpoint(_: EmbedRequest) -> dict[str, object]:
    """Return a deterministic embedding response payload."""

    # Short vector keeps things easy to assert against.
    return {
        "model": "nomic-embed-text",
        "created_at": "2024-01-01T00:00:00Z",
        "embedding": [0.1, 0.2, 0.3, 0.4],
    }


def run(argv: Sequence[str] | None = None) -> None:
    """Launch the mock Ollama FastAPI application via Uvicorn."""

    parser = argparse.ArgumentParser(description="Run the mock Ollama service")
    parser.add_argument(
        "--host",
        default=os.getenv("MOCK_OLLAMA_HOST", "0.0.0.0"),
        help="Interface to bind (default: 0.0.0.0 or MOCK_OLLAMA_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MOCK_OLLAMA_PORT", "11434")),
        help="Port to bind (default: 11434 or MOCK_OLLAMA_PORT)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("MOCK_OLLAMA_RELOAD", "false").lower() in {"1", "true", "yes"},
        help="Enable Uvicorn reload (or set MOCK_OLLAMA_RELOAD=true)",
    )

    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    run()
