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

---

## Side work: TOR-27399 - ADK agents exploration
Status: in progress

Not a program module. Jira ticket "ADK Agents Exploration - explore google adk
version 2, its agents and orchestration patterns", built on branch `TOR-27399`.
Findings feed Module 3 (first agent) and Module 5 (multi-agent systems).

### What I built
`src/atlas/agents/code_agent/` - a GitHub code-reading agent on ADK 2.15.0.

```
START --+--> structure_scout  --+
        +--> dependency_scout --+--> gather --> reporter
        +--> code_scout        --+
```

Three `LlmAgent` scouts with deliberately disjoint tool sets, a `JoinNode`
barrier, and a reporter that owns no tools. Splitting them is structural, not
advisory: a scout cannot wander outside its remit because it lacks the tool,
and the reporter cannot cite a file because it cannot fetch one. Tools live in
`src/atlas/tools/github.py` and are all GET-only.

Test suite: 32 tests, 92% coverage overall, 100% on both `tools/github.py` and
`agents/code_agent/agent.py`. `tests/test_github_tools.py` mocks the transport
with `httpx.MockTransport`, so nothing touches the network.
`tests/test_agent_graph.py` asserts the structure rather than the behaviour -
that `gather` is the only barrier, that retry sits on the nodes and not the
workflow, that the reporter holds no tools, and that no scout can both list
and search. Guarantees worth claiming are worth asserting.

### What I measured
Sequential two-node version (explorer + reporter) on gemini-3.1-flash-lite:
12 tool calls, correct answer, roughly 6 model requests per minute.

Free tier model availability, 2026-11-20:
- `gemini-2.5-flash` - 404, retired for new keys; Google points at 3.8-flash
- `gemini-3.8-flash`, `gemini-3.5-flash`, `gemini-3.6-flash` - 503, saturated
- `gemini-3.1-flash-lite`, `gemini-flash-lite-latest` - available

Free tier quota: 15 `generate_content` requests per minute, per model.

### What surprised me / got wrong
1. **`retry_config` on a `Workflow` retries the whole workflow, not the failing
   node.** Proved it with a function node that fails twice then succeeds: the
   log reads "Node retrytest failed and is being retried locally", naming the
   Workflow. So one scout's 429 re-ran all three scouts and tripled the burst
   against a per-minute quota - the config meant to fix throttling was causing
   it. `retry_config` is a field on `BaseNode`, so it belongs on each
   `LlmAgent`. The wrong choice is silently catastrophic and invisible without
   a deliberate test.

2. **Fan-out multiplies request rate, not just speed.** The sequential version
   made 12 calls over about two minutes (~6/min, under the cap). The same work
   across three concurrent scouts makes a similar number of calls in about
   forty seconds (~18/min, over the cap). Identical work and identical token
   spend; one design runs and the other throttles.

3. **Exponential backoff is the wrong shape for a per-minute quota.** It is
   right for a 503, where capacity returns independently of you. For a 429 your
   own retries are consuming the budget you are waiting for. A ladder starting
   at 1s (1+2+4+8 = 15s total) gave up before a window that needed 20-58s.
   Retuned to start at 5s.

4. `RetryConfig.exceptions` normalises classes to their names: pass
   `[ServerError]`, read back `['ServerError']`. Matching is by name.

5. Function-node parameters resolve from workflow state by name. A parameter
   with no default and no matching state key raises `WorkflowDataError` before
   the function ever runs.

6. The agent reads GitHub's default branch, not the local working tree. It
   correctly answered "no Pydantic models" because the schemas were never
   pushed.

7. **Free tier quotas differ by model in kind, not just size.**
   `gemini-3.1-flash-lite` allows 15 requests per MINUTE.
   `gemini-3.6-flash` allows 20 per DAY. One agent run costs 15-40 requests,
   so a full flash model gives roughly one run per day and then blocks for 22
   hours. No retry policy helps against a daily cap. I picked 3.6-flash for
   its stronger multi-step tool use, checked only that it responded, and
   burned the day's budget in a single run. Model choice on free tier is a
   quota decision first.

8. A fan-out with no join is a configuration error, not just untidy:
   `WorkflowConfigurationError: multiple terminal nodes produced output (2).
   A workflow must have at most one terminal output.` That is a second reason
   `JoinNode` matters.

9. I reported "two scouts made zero tool calls" as a defect. It was my own
   instrumentation: the trace printed only `function_call` parts, so scouts
   that answered in text looked silent. The lesson is that a trace which does
   not show everything an agent did will invent defects. Print text and tool
   calls, count per agent, and flag duplicate calls.

### Decisions
- Stay on the free tier. `ATLAS_CONCURRENCY` defaults to 1 so the fan-out runs
  in turn and stays under the cap; set it to 3 to demonstrate the throttling.
- `ATLAS_MODEL` defaults to `gemini-3.8-flash` in code, overridden in `.env` to
  `gemini-3.1-flash-lite` while the flash tier is saturated.
- Public repositories only. Pointing at a private work repo would send
  proprietary source to the free tier, which per Google's pricing page may be
  used to improve Google's products and reviewed by humans.

### Open questions
- How does an `LlmAgent` emit a route value for conditional edges? The dict
  form `{"route_a": node_a}` is documented in the ADK source, but not how a
  model-backed node selects a route. Conditional routing left unbuilt.
- Would a token-bucket limiter in front of the model beat backoff on a
  per-minute quota?
- Does `max_concurrency` throttle model calls or only node scheduling?
