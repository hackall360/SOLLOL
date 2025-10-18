"""Helpers for interacting with the gateway local cluster endpoints.

This module provides thin httpx-based helpers that the example CLI runner
and tests can reuse to exercise the local cluster demo.  Both synchronous
and asynchronous entry points are exposed so callers can pick what fits
their control flow.
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
    "fetch_dashboard_config_async",
    "fetch_dashboard_config",
    "fetch_dashboard_applications_async",
    "fetch_dashboard_applications",
    "fetch_dashboard_routing_logs_async",
    "fetch_dashboard_routing_logs",
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
    return payload


_CHAT_PAYLOAD = _load_payload("chat_request.json")
_GENERATE_PAYLOAD = _load_payload("generate_request.json")
_EMBED_PAYLOAD = _load_payload("embed_request.json")

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _ensure_model_matches(
    response: Mapping[str, Any],
    expected_model: str,
    *,
    context: str,
) -> None:
    actual_model = response.get("model")
    _ensure(
        actual_model == expected_model,
        f"{context} response model {actual_model!r} did not match requested {expected_model!r}",
    )


def _ensure_done_flag(response: Mapping[str, Any], *, context: str) -> None:
    if "done" in response:
        _ensure(response.get("done") is True, f"{context} response did not report done=True")
    if "done_reason" in response:
        done_reason = response.get("done_reason")
        _ensure(
            isinstance(done_reason, str) and done_reason.strip(),
            f"{context} response included empty done_reason",
        )


def _ensure_usage_tokens(response: Mapping[str, Any], *, context: str) -> None:
    usage = response.get("usage")
    if isinstance(usage, Mapping):
        total_tokens = usage.get("total_tokens")
        if total_tokens is not None:
            _ensure(
                isinstance(total_tokens, int) and total_tokens >= 0,
                f"{context} usage reported invalid total_tokens {total_tokens!r}",
            )


async def _async_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    json_payload: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
) -> Any:
    response = await client.request(method, url, json=json_payload, params=params)
    response.raise_for_status()
    return response.json()


def _sync_request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json_payload: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
) -> Any:
    response = client.request(method, url, json=json_payload, params=params)
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


async def fetch_dashboard_config_async(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = await _async_request(client, "GET", "/api/dashboard/config")
        _ensure(
            "ray_dashboard_url" in data,
            "Dashboard config response missing ray_dashboard_url",
        )
        return data
    finally:
        if owns_client and client is not None:
            await client.aclose()


def fetch_dashboard_config(
    base_url: str,
    *,
    client: httpx.Client | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    if owns_client:
        client = httpx.Client(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = _sync_request(client, "GET", "/api/dashboard/config")
        _ensure(
            "ray_dashboard_url" in data,
            "Dashboard config response missing ray_dashboard_url",
        )
        return data
    finally:
        if owns_client and client is not None:
            client.close()


async def fetch_dashboard_applications_async(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = await _async_request(client, "GET", "/api/applications")
        _ensure(
            "applications" in data and isinstance(data["applications"], list),
            "Dashboard applications response missing list of applications",
        )
        return data
    finally:
        if owns_client and client is not None:
            await client.aclose()


def fetch_dashboard_applications(
    base_url: str,
    *,
    client: httpx.Client | None = None,
) -> Mapping[str, Any]:
    owns_client = client is None
    if owns_client:
        client = httpx.Client(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = _sync_request(client, "GET", "/api/applications")
        _ensure(
            "applications" in data and isinstance(data["applications"], list),
            "Dashboard applications response missing list of applications",
        )
        return data
    finally:
        if owns_client and client is not None:
            client.close()


async def fetch_dashboard_routing_logs_async(
    base_url: str,
    *,
    client: httpx.AsyncClient | None = None,
    limit: int = 25,
) -> Mapping[str, Any]:
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = await _async_request(
            client,
            "GET",
            "/api/routing_logs",
            params={"limit": int(limit)},
        )
        _ensure(
            "logs" in data and isinstance(data["logs"], list),
            "Routing logs response missing logs array",
        )
        return data
    finally:
        if owns_client and client is not None:
            await client.aclose()


def fetch_dashboard_routing_logs(
    base_url: str,
    *,
    client: httpx.Client | None = None,
    limit: int = 25,
) -> Mapping[str, Any]:
    owns_client = client is None
    if owns_client:
        client = httpx.Client(base_url=base_url, timeout=_TIMEOUT)
    try:
        data = _sync_request(
            client,
            "GET",
            "/api/routing_logs",
            params={"limit": int(limit)},
        )
        _ensure(
            "logs" in data and isinstance(data["logs"], list),
            "Routing logs response missing logs array",
        )
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
        _ensure_model_matches(data, payload["model"], context="Chat")
        _ensure_done_flag(data, context="Chat")
        _ensure_usage_tokens(data, context="Chat")

        message = data.get("message")
        _ensure(isinstance(message, Mapping), "Chat response missing message object")
        role = message.get("role") if isinstance(message, Mapping) else None
        _ensure(role == "assistant", "Chat message role was not 'assistant'")
        content = message.get("content") if isinstance(message, Mapping) else None
        _ensure(
            isinstance(content, str) and content.strip(),
            "Chat response did not include assistant content",
        )
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
        _ensure_model_matches(data, payload["model"], context="Chat")
        _ensure_done_flag(data, context="Chat")
        _ensure_usage_tokens(data, context="Chat")

        message = data.get("message")
        _ensure(isinstance(message, Mapping), "Chat response missing message object")
        role = message.get("role") if isinstance(message, Mapping) else None
        _ensure(role == "assistant", "Chat message role was not 'assistant'")
        content = message.get("content") if isinstance(message, Mapping) else None
        _ensure(
            isinstance(content, str) and content.strip(),
            "Chat response did not include assistant content",
        )
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
        _ensure_model_matches(data, payload["model"], context="Generate")
        _ensure_done_flag(data, context="Generate")
        _ensure_usage_tokens(data, context="Generate")

        response_text = data.get("response")
        _ensure(
            isinstance(response_text, str) and response_text.strip(),
            "Generate response did not include text content",
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
        _ensure_model_matches(data, payload["model"], context="Generate")
        _ensure_done_flag(data, context="Generate")
        _ensure_usage_tokens(data, context="Generate")

        response_text = data.get("response")
        _ensure(
            isinstance(response_text, str) and response_text.strip(),
            "Generate response did not include text content",
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
        _ensure_model_matches(data, payload["model"], context="Embed")

        vector = data.get("embedding")
        if vector is None and "embeddings" in data:
            embeddings_field = data["embeddings"]
            if isinstance(embeddings_field, Iterable) and not isinstance(embeddings_field, (str, bytes)):
                embeddings_list = list(embeddings_field)
                if embeddings_list:
                    vector = embeddings_list[0]
        if isinstance(vector, Iterable) and not isinstance(vector, (str, bytes)):
            vector = list(vector)
        _ensure(
            isinstance(vector, list) and len(vector) > 0,
            "Embed response did not include embedding vector",
        )
        if vector:
            _ensure(
                all(isinstance(value, (int, float)) for value in vector[: min(5, len(vector))]),
                "Embed response vector did not contain numeric values",
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
        _ensure_model_matches(data, payload["model"], context="Embed")

        vector = data.get("embedding")
        if vector is None and "embeddings" in data:
            embeddings_field = data["embeddings"]
            if isinstance(embeddings_field, Iterable) and not isinstance(embeddings_field, (str, bytes)):
                embeddings_list = list(embeddings_field)
                if embeddings_list:
                    vector = embeddings_list[0]
        if isinstance(vector, Iterable) and not isinstance(vector, (str, bytes)):
            vector = list(vector)
        _ensure(
            isinstance(vector, list) and len(vector) > 0,
            "Embed response did not include embedding vector",
        )
        if vector:
            _ensure(
                all(isinstance(value, (int, float)) for value in vector[: min(5, len(vector))]),
                "Embed response vector did not contain numeric values",
            )
        return data
    finally:
        if owns_client and client is not None:
            client.close()


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _collect_ray_status(responses: Mapping[str, Any]) -> Mapping[str, Any]:
    summary: dict[str, Any] = {}
    health = _as_mapping(responses.get("health"))
    stats = _as_mapping(responses.get("stats"))

    ray_health = _as_mapping(health.get("ray_parallel_execution")) if health else None
    if ray_health:
        summary["ray_parallel_execution"] = ray_health

    hybrid_stats = _as_mapping(stats.get("hybrid_routing")) if stats else None
    if hybrid_stats:
        summary["hybrid_routing"] = hybrid_stats

    return summary


def _collect_dask_status(responses: Mapping[str, Any]) -> Mapping[str, Any]:
    summary: dict[str, Any] = {}
    health = _as_mapping(responses.get("health"))
    stats = _as_mapping(responses.get("stats"))

    dask_health = _as_mapping(health.get("dask_batch_processing")) if health else None
    if dask_health:
        summary["dask_batch_processing"] = dask_health

    batch_stats = _as_mapping(stats.get("batch_jobs")) if stats else None
    if batch_stats:
        summary["batch_jobs"] = batch_stats

    return summary


def _collect_routing_metadata(responses: Mapping[str, Any]) -> Mapping[str, Any]:
    routing_details: dict[str, Any] = {}
    stats = _as_mapping(responses.get("stats"))
    if stats:
        hybrid = _as_mapping(stats.get("hybrid_routing"))
        if hybrid:
            routing_details["stats_hybrid_routing"] = hybrid

    for key in ("chat", "generate", "embed"):
        data = _as_mapping(responses.get(key))
        if not data:
            continue
        routing = _as_mapping(data.get("_sollol_routing"))
        if routing:
            routing_details[f"{key}_routing"] = routing

    return routing_details


def _attach_gateway_metadata(responses: MutableMapping[str, Any]) -> None:
    ray_status = _collect_ray_status(responses)
    if ray_status:
        responses.setdefault("ray_status", ray_status)

    dask_status = _collect_dask_status(responses)
    if dask_status:
        responses.setdefault("dask_status", dask_status)

    routing_metadata = _collect_routing_metadata(responses)
    if routing_metadata:
        responses.setdefault("routing_metadata", routing_metadata)


async def run_full_sequence_async(
    base_url: str,
    *,
    dashboard_url: str | None = None,
) -> dict[str, Mapping[str, Any]]:
    async with httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT) as client:
        health = await fetch_health_async(base_url, client=client)
        stats = await fetch_stats_async(base_url, client=client)
        chat = await run_chat_async(base_url, client=client)
        generate = await run_generate_async(base_url, client=client)
        embed = await run_embed_async(base_url, client=client)

    results: dict[str, Any] = {
        "health": health,
        "stats": stats,
        "chat": chat,
        "generate": generate,
        "embed": embed,
    }
    _attach_gateway_metadata(results)

    if dashboard_url:
        async with httpx.AsyncClient(base_url=dashboard_url, timeout=_TIMEOUT) as dashboard_client:
            results["dashboard_config"] = await fetch_dashboard_config_async(
                dashboard_url, client=dashboard_client
            )
            results["dashboard_applications"] = await fetch_dashboard_applications_async(
                dashboard_url, client=dashboard_client
            )
            results["dashboard_routing_logs"] = await fetch_dashboard_routing_logs_async(
                dashboard_url, client=dashboard_client
            )

    return results


def run_full_sequence(
    base_url: str,
    *,
    dashboard_url: str | None = None,
) -> dict[str, Mapping[str, Any]]:
    with httpx.Client(base_url=base_url, timeout=_TIMEOUT) as client:
        health = fetch_health(base_url, client=client)
        stats = fetch_stats(base_url, client=client)
        chat = run_chat(base_url, client=client)
        generate = run_generate(base_url, client=client)
        embed = run_embed(base_url, client=client)

    results: dict[str, Any] = {
        "health": health,
        "stats": stats,
        "chat": chat,
        "generate": generate,
        "embed": embed,
    }
    _attach_gateway_metadata(results)

    if dashboard_url:
        with httpx.Client(base_url=dashboard_url, timeout=_TIMEOUT) as dashboard_client:
            results["dashboard_config"] = fetch_dashboard_config(
                dashboard_url, client=dashboard_client
            )
            results["dashboard_applications"] = fetch_dashboard_applications(
                dashboard_url, client=dashboard_client
            )
            results["dashboard_routing_logs"] = fetch_dashboard_routing_logs(
                dashboard_url, client=dashboard_client
            )

    return results


def _format_multiline_strings(pretty: str) -> str:
    """Render JSON strings that contain newlines as readable blocks."""

    lines = pretty.splitlines()
    rendered: list[str] = []

    for line in lines:
        if "\\n" not in line:
            rendered.append(line)
            continue

        stripped = line.rstrip()
        prefix, sep, remainder = stripped.partition(": ")
        if not sep:
            rendered.append(line)
            continue

        trailing_comma = ""
        if remainder.endswith(","):
            remainder = remainder[:-1]
            trailing_comma = ","

        if not (remainder.startswith('"') and remainder.endswith('"')):
            rendered.append(line)
            continue

        try:
            actual = json.loads(remainder)
        except json.JSONDecodeError:
            rendered.append(line)
            continue

        if not isinstance(actual, str) or "\n" not in actual:
            rendered.append(line)
            continue

        base_indent = " " * (len(prefix) - len(prefix.lstrip()))
        content_indent = base_indent + "  "
        rendered.append(f"{prefix}: \"\"\"")
        for part in actual.splitlines():
            rendered.append(f"{content_indent}{part}")
        rendered.append(f"{base_indent}\"\"\"{trailing_comma}")

    return "\n".join(rendered)


def format_results(results: Mapping[str, Any]) -> str:
    sections: list[str] = []
    for key in (
        "health",
        "stats",
        "ray_status",
        "dask_status",
        "routing_metadata",
        "dashboard_config",
        "dashboard_applications",
        "dashboard_routing_logs",
        "chat",
        "generate",
        "embed",
    ):
        if key in results:
            pretty = json.dumps(
                results[key], indent=2, sort_keys=True, default=str, ensure_ascii=False
            )
            formatted = _format_multiline_strings(pretty)
            sections.append(f"{key.upper()}\n{formatted}")
    return "\n\n".join(sections)
