"""Lightweight mock Ollama HTTP service for local demos and tests."""

from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping, Sequence

from .gateway_process import DEFAULT_MOCK_OLLAMA_PORT

__all__ = ["run", "main"]


class _MockOllamaRequestHandler(BaseHTTPRequestHandler):
    """Serve minimal Ollama-compatible endpoints for local development."""

    server_version = "MockOllama/0.1"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - signature defined by BaseHTTPRequestHandler
        """Silence default request logging to keep console output tidy."""

        return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _send_json(self, status: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Mapping[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        data = self.rfile.read(length)
        if not data:
            return {}
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return {}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # HTTP verb handlers
    # ------------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/api/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "mock-ollama",
                    "timestamp": self._now(),
                },
            )
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/api/chat":
            payload = self._read_json()
            message = "Hello from SOLLOL's mock Ollama backend!"
            messages = payload.get("messages")
            if isinstance(messages, list) and messages:
                last = messages[-1]
                if isinstance(last, Mapping):
                    content = last.get("content")
                    if isinstance(content, str) and content.strip():
                        message = f"Echo: {content.strip()}"

            response_payload: dict[str, Any] = {
                "model": payload.get("model", "llama3.2"),
                "created_at": self._now(),
                "message": {
                    "role": "assistant",
                    "content": message,
                },
                "done": True,
                "done_reason": "stop",
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 12,
                    "total_tokens": 20,
                },
            }
            self._send_json(200, response_payload)
            return

        if self.path == "/api/generate":
            payload = self._read_json()
            prompt = payload.get("prompt")
            if isinstance(prompt, str) and prompt.strip():
                response_text = f"Generated mock completion for: {prompt.strip()}"
            else:
                response_text = "This is a generated response from the mock Ollama server."

            response_payload = {
                "model": payload.get("model", "llama3.2"),
                "created_at": self._now(),
                "response": response_text,
                "done": True,
                "done_reason": "stop",
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 16,
                    "total_tokens": 24,
                },
            }
            self._send_json(200, response_payload)
            return

        if self.path == "/api/embed":
            payload = self._read_json()
            texts = payload.get("input")
            if isinstance(texts, str):
                inputs = [texts]
            elif isinstance(texts, Sequence):
                inputs = [str(item) for item in texts]
            else:
                inputs = ["mock embedding"]

            embedding = [0.1] * 384
            response_payload = {
                "model": payload.get("model", "mxbai-embed-large"),
                "created_at": self._now(),
                "embeddings": [embedding for _ in inputs],
                "usage": {
                    "prompt_tokens": 8 * len(inputs),
                    "total_tokens": 8 * len(inputs),
                },
            }
            self._send_json(200, response_payload)
            return

        self.send_error(404, "Not Found")


def _serve(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), _MockOllamaRequestHandler)
    thread_name = threading.current_thread().name
    print(f"[{thread_name}] Mock Ollama server listening on http://{host}:{port}")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the SOLLOL mock Ollama service")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind the mock server")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_MOCK_OLLAMA_PORT,
        help=f"Port to bind the mock server (default: {DEFAULT_MOCK_OLLAMA_PORT})",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> None:
    """Entry-point used by demos/tests to launch the mock service."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    _serve(args.host, int(args.port))


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point for ``python -m examples.gateway_local_cluster.mock_ollama``."""

    run(argv)


if __name__ == "__main__":  # pragma: no cover - manual invocation hook
    main()
