# Atlas - Learning Log

Working notes for the Agentic AI Developer Program. One entry per module: what I
built, what the numbers said, and what I got wrong. Measurements (token counts,
latency, cost, model comparisons) belong here, not in commit messages.

Entry template:

```
## Module N: <title>
Status: not started | in progress | done | skipped - already known

### What I built
### What I measured
### What surprised me / got wrong
### Open questions
```

---

## Module 0: Setup
Status: in progress

### What I built
Atlas repository skeleton:

```
atlas/
├── pyproject.toml
├── src/atlas/
│   ├── schemas/   # Pydantic models: inputs, outputs, tool results
│   ├── tools/     # every network or database call lives here
│   ├── agents/    # agent definitions and prompts
│   └── api/       # HTTP layer
├── tests/
├── evals/
└── LEARNING_LOG.md
```

### Still to do
- [x] Install uv and rebuild the venv with it - done, `uv.lock` committed to the tree
- [x] Install Ruff and confirm `ruff check .` is clean - passes
- [x] Point PyCharm's project interpreter at `D:/atlas/.venv/Scripts/python.exe`
- [ ] Create a Gemini API key in Google AI Studio, copy `.env.example` to `.env`
- [ ] Clone the team agent project, install its dependencies, run its test suite
- [ ] Run the team project locally on demo data, walk the main user flow end to end
- [ ] Find a learning buddy

### Exit check
- [ ] Tests run green in both repositories
- [ ] I can draw the team project's main flow: where a request enters, which agents
      and tools it passes through, and what comes back

### What surprised me / got wrong
- **Deleting a venv while the IDE is using it.** `uv venv --clear` failed with
  `failed to remove directory .venv\Scripts: Access is denied (os error 5)`.
  PyCharm's "Add Local Python SDK" dialog had just probed that interpreter, so
  Windows still held an open handle on `python.exe` and refused to remove the
  directory. Close the interpreter dialog (or PyCharm) before rebuilding a venv.
- **Corporate TLS interception.** `uv python install 3.12` failed with
  `invalid peer certificate: UnknownIssuer`. uv ships its own CA bundle and does
  not read the Windows certificate store by default, so the proxy's root CA is
  unknown to it. PyPI worked; only the GitHub download was intercepted. Fixed with
  `system-certs = true` under `[tool.uv]` in pyproject.toml (CLI flag:
  `--system-certs`, env var: `UV_SYSTEM_CERTS=1`).

### Decisions
- **Python 3.12.16**, not the system 3.14.6. The program asks for 3.12+, so 3.14
  was within spec, but the agent stack (Google ADK and its dependencies) is
  unlikely to have wheels for 3.14 yet. uv manages the 3.12 build; the system 3.14
  is untouched and still the default outside this project.

---

## Module 1: Python essentials for AI work
Status: not started

## Module 2: LLM fundamentals, cost and model choice
Status: not started

## Module 3: Build your first agent
Status: not started

## Module 4: Knowledge and memory (RAG)
Status: not started

## Module 5: Multi-agent systems and integration
Status: not started

## Module 6: Agent protocols (MCP and A2A)
Status: not started

## Module 7: Human-in-the-loop
Status: not started

## Module 8: Guardrails, observability and evaluation
Status: not started

## Module 9: Responsible AI and compliance
Status: not started

## Module 10: Deployment and operations
Status: not started

## Module 11: Capstone
Status: not started
