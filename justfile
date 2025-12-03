list:
    just --list

setup:
    uv sync

test:
    uv run pytest

uv publish:
    uv build
    uv publish
