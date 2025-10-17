"""Module entry point for ``python -m examples.gateway_mock_cluster``."""
from __future__ import annotations

from .cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
