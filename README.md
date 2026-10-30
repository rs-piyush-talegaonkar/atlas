# Atlas

A small team assistant agent, built incrementally as the practice project for the
Agentic AI Developer Program.

**Status: Module 0.** This is the project skeleton — the package layout, tooling and
environment are in place, but there is no agent yet. Each module of the program adds
a layer: schemas and async clients, then a single tool-calling agent, then retrieval,
then multiple agents, and so on.

## Requirements

- [uv](https://docs.astral.sh/uv/) — manages the Python version, the virtual
  environment and the dependencies
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

You do not need to install Python yourself. uv reads `requires-python` and fetches a
matching interpreter; this project is pinned to 3.12.

## Setup

```bash
git clone https://github.com/rs-piyush-talegaonkar/atlas.git
cd atlas
uv sync
```

`uv sync` creates `.venv` and installs everything from `uv.lock`, so you get the exact
same package versions this was developed against.

Then create your local environment file:

```bash
cp .env.example .env
```

and put your Gemini API key in it. `.env` is git-ignored and must never be committed.

## Commands

| | |
|---|---|
| `uv run pytest` | run the test suite |
| `uv run pytest --cov` | run with coverage |
| `uv run ruff check .` | lint |
| `uv run ruff format .` | format |
| `uv add <package>` | add a dependency and update the lock file |

There is no need to activate the virtual environment — `uv run` executes inside it.

## Layout

```
src/atlas/
├── schemas/   Pydantic models: inputs, outputs, tool results
├── tools/     every network or database call lives here
├── agents/    agent definitions and prompts
└── api/       HTTP layer
tests/         pytest suite
evals/         agent evaluation sets
```

The separation is the point: tools own all I/O, agents own behaviour and prompts, and
schemas define the typed boundary between them. Keeping network calls out of agent
code is what makes the agents testable with a fake model.

## Learning log

[`LEARNING_LOG.md`](LEARNING_LOG.md) carries the per-module notes — what was built,
what the measurements said, and what went wrong. Model comparisons, token and latency
numbers and cost estimates go there rather than in commit messages.
