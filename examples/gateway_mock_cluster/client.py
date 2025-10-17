"""Helpers for interacting with the mock gateway cluster endpoints.

This module provides thin httpx-based helpers that the example CLI runner
and tests can reuse to exercise the mock cluster.  Both synchronous and
asynchronous entry points are exposed so callers can pick what fits their
control flow.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping

import httpx

__all__ = [
    "fetch_health_async",
    "fetch_health",
    "fetch_stats_async",
    "fetch_stats",
    "run_chat_async",
    "run_chat",
    "run_generate_async",
    "run_generate",
    "run_embed_async",
    "run_embed",
    "run_full_sequence_async",
    "run_full_sequence",
    "format_results",
]

_DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_payload(filename: str) -> MutableMapping[str, Any]:
    path = _DATA_DIR / filename
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    payload.pop("_note", None)
    return payload


_CHAT_PAYLOAD = _load_payload("chat_request.json")
_GENERATE_PAYLOAD = _load_payload("generate_request.json")
_EMBED_PAYLOAD = _load_payload("embed_request.json")

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


async def _async_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    json_payload: Mapping[str, Any] | None = None,
) -> Any:
    response = await client.request(method, url, json=json_payload)
    response.raise_for_status()
    return response.json()


def _sync_request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json_payload: Mapping[str, Any] | None = None,
) -> Any:
    response = client.request(method, url, json=json_payload)
    response.raise_for_status()
    return response.json()


async def fetch_health_async(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = await _async_request(client, "GET", "/api/health")
        _ensure(data.get("service") == "SOLLOL", "Gateway health check did not identify SOLLOL service")
        return data
    finally:
        if owns_client and client is not None:
            await client.aclose()


def fetch_health(
    base_url: str,
    *,
    client: httpx.Client | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    if owns_client:
        client = httpx.Client(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = _sync_request(client, "GET", "/api/health")
        _ensure(data.get("service") == "SOLLOL", "Gateway health check did not identify SOLLOL service")
        return data
    finally:
        if owns_client and client is not None:
            client.close()


async def fetch_stats_async(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = await _async_request(client, "GET", "/api/stats")
        _ensure("timestamp" in data, "Stats response missing timestamp field")
        return data
    finally:
        if owns_client and client is not None:
            await client.aclose()


def fetch_stats(
    base_url: str,
    *,
    client: httpx.Client | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    if owns_client:
        client = httpx.Client(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = _sync_request(client, "GET", "/api/stats")
        _ensure("timestamp" in data, "Stats response missing timestamp field")
        return data
    finally:
        if owns_client and client is not None:
            client.close()


async def run_chat_async(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    payload = deepcopy(_CHAT_PAYLOAD)
    if owns_client:
        client = httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = await _async_request(client, "POST", "/api/chat", json_payload=payload)
        message = data.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        _ensure(content and "ready" in content.lower(), "Chat response did not include expected 'ready' content")
        return data
    finally:
        if owns_client and client is not None:
            await client.aclose()


def run_chat(
    base_url: str,
    *,
    client: httpx.Client | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    payload = deepcopy(_CHAT_PAYLOAD)
    if owns_client:
        client = httpx.Client(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = _sync_request(client, "POST", "/api/chat", json_payload=payload)
        message = data.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        _ensure(content and "ready" in content.lower(), "Chat response did not include expected 'ready' content")
        return data
    finally:
        if owns_client and client is not None:
            client.close()


async def run_generate_async(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    payload = deepcopy(_GENERATE_PAYLOAD)
    if owns_client:
        client = httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = await _async_request(client, "POST", "/api/generate", json_payload=payload)
        response_text = data.get("response")
        _ensure(
            isinstance(response_text, str) and "ready" in response_text.lower(),
            "Generate response did not include expected 'ready' text",
        )
        return data
    finally:
        if owns_client and client is not None:
            await client.aclose()


def run_generate(
    base_url: str,
    *,
    client: httpx.Client | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    payload = deepcopy(_GENERATE_PAYLOAD)
    if owns_client:
        client = httpx.Client(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = _sync_request(client, "POST", "/api/generate", json_payload=payload)
        response_text = data.get("response")
        _ensure(
            isinstance(response_text, str) and "ready" in response_text.lower(),
            "Generate response did not include expected 'ready' text",
        )
        return data
    finally:
        if owns_client and client is not None:
            client.close()


async def run_embed_async(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    payload = deepcopy(_EMBED_PAYLOAD)
    if owns_client:
        client = httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = await _async_request(client, "POST", "/api/embed", json_payload=payload)
        embedding = data.get("embedding")
        if isinstance(embedding, Iterable) and not isinstance(embedding, (str, bytes)):
            embedding = list(embedding)
        _ensure(
            isinstance(embedding, list) and len(embedding) > 0,
            "Embed response did not include embedding vector",
        )
        return data
    finally:
        if owns_client and client is not None:
            await client.aclose()


def run_embed(
    base_url: str,
    *,
    client: httpx.Client | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    payload = deepcopy(_EMBED_PAYLOAD)
    if owns_client:
        client = httpx.Client(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = _sync_request(client, "POST", "/api/embed", json_payload=payload)
        embedding = data.get("embedding")
        if isinstance(embedding, Iterable):
            embedding = list(embedding)
        _ensure(
            isinstance(embedding, list) and len(embedding) > 0,
            "Embed response did not include embedding vector",
        )
        return data
    finally:
        if owns_client and client is not None:
            client.close()


async def run_full_sequence_async(base_url: str) -> dict[str, Mapping[str, Any]]:
    async with httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT) as client:
        health = await fetch_health_async(base_url, client=client)
        stats = await fetch_stats_async(base_url, client=client)
        chat = await run_chat_async(base_url, client=client)
        generate = await run_generate_async(base_url, client=client)
        embed = await run_embed_async(base_url, client=client)
    return {
        "health": health,
        "stats": stats,
        "chat": chat,
        "generate": generate,
        "embed": embed,
    }


def run_full_sequence(base_url: str) -> dict[str, Mapping[str, Any]]:
    with httpx.Client(base_url=base_url, timeout=_TIMEOUT) as client:
        health = fetch_health(base_url, client=client)
        stats = fetch_stats(base_url, client=client)
        chat = run_chat(base_url, client=client)
        generate = run_generate(base_url, client=client)
        embed = run_embed(base_url, client=client)
    return {
        "health": health,
        "stats": stats,
        "chat": chat,
        "generate": generate,
        "embed": embed,
    }


def format_results(results: Mapping[str, Any]) -> str:
    sections: list[str] = []
    for key in ("health", "stats", "chat", "generate", "embed"):
        if key in results:
            pretty = json.dumps(results[key], indent=2, sort_keys=True, default=str)
            sections.append(f"{key.upper()}\n{pretty}")
    return "\n\n".join(sections)
