set dotenv-load := true
set shell := ["bash", "-c"]

list:
    just --list

setup:
    uv sync

publish:
    uv build
    uv publish

run ARGS="":
    TEXTUAL=devtools uv run eview {{ ARGS }}

textual-console:
    uv run textual console

test OPTS="":
    cd tests && uv run pytest {{ OPTS }}
