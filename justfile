list:
    just --list

setup:
    uv sync

test:
    uv run pytest

publish:
    uv build
    uv publish
