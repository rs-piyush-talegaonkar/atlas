"""A GitHub code-reading agent, built as an ADK 2.x workflow graph.

Three scouts explore the repository, a join barrier waits for all of them, and
a reporter that owns no tools writes the answer. The scouts are independent and
the graph can run them at once, but ATLAS_CONCURRENCY defaults to 1 because the
free tier punishes bursts. Keeping retrieval and phrasing apart means the
reporter cannot cite a file no scout actually opened.

    START --+--> structure_scout  --+
            +--> dependency_scout --+--> gather --> reporter
            +--> code_scout        --+
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent

# Private, but it is ADK's own type for a 429 and the only precise handle on
# one: the public ClientError would also swallow 400s that must never retry.
from google.adk.models.google_llm import _ResourceExhaustedError
from google.adk.workflow import START, JoinNode, RetryConfig, Workflow
from google.genai.errors import ServerError

from atlas.tools.github import list_repo_files, read_repo_file, search_repo_code

# adk web is launched from an arbitrary working directory, so point dotenv at
# the project root rather than trusting the cwd.
load_dotenv(Path(__file__).resolve().parents[4] / ".env")

# Model choice on the free tier is a quota decision as much as a capability
# one: the full flash models allow only 20 requests PER DAY, while flash-lite
# allows 15 per minute with a far larger daily budget. One agent run costs
# 15-40 requests, so flash-lite is the only model you can iterate on.
MODEL = os.environ.get("ATLAS_MODEL", "gemini-3.8-flash")

# The free tier allows 15 model requests a minute, and a three-way fan-out
# exceeds that in a burst. Default to 1 so the scouts take turns and stay under
# the cap. Raise it on paid quota, or to demonstrate the throttling.
MAX_CONCURRENCY = int(os.environ.get("ATLAS_CONCURRENCY", "1"))

# Retry belongs on each node, not on the Workflow. A Workflow-level
# retry_config restarts the whole graph, so one scout's 429 would re-run all
# three and triple the burst against a 15-requests-per-minute budget.
NODE_RETRY = RetryConfig(
    max_attempts=6,
    # A per-minute quota needs delays on the order of tens of seconds, so the
    # ladder starts at 5s (5, 10, 20, 40, 75) rather than at 1s.
    initial_delay=5.0,
    # A 429 asks for a retry up to ~58s out, so the ceiling must clear that.
    max_delay=75.0,
    backoff_factor=2.0,
    jitter=0.3,
    exceptions=[ServerError, _ResourceExhaustedError],
)

# gemini-3.1-flash-lite looped on an identical list_repo_files call 19 times
# in a row. Stating the rule explicitly is cheaper than hoping the model infers
# it, and it holds for stronger models under an ambiguous result too.
LOOP_GUARD = """

Never repeat a tool call you have already made with identical arguments: the
answer will not change. If a result does not move you forward, change the
argument or stop and report what you have. Stopping early beats calling the
same tool again."""

structure_scout = LlmAgent(
    model=MODEL,
    name="structure_scout",
    description="Maps the parts of the repository layout that bear on the question.",
    instruction="""Map the parts of the repository layout that bear on the question.

Walk the tree with list_repo_files, following only where the question points.
Do not enumerate the whole repository. Report the paths you saw, and say so
plainly if the layout has no bearing on the question."""
    + LOOP_GUARD,
    tools=[list_repo_files],
    output_key="structure",
    retry_config=NODE_RETRY,
)

dependency_scout = LlmAgent(
    model=MODEL,
    name="dependency_scout",
    description="Reads manifests to establish what the project depends on.",
    instruction="""Establish what this project depends on and how it is configured.

Read manifests such as pyproject.toml, requirements.txt, package.json or
pom.xml with read_repo_file. If the question does not touch dependencies or
configuration, read the main manifest anyway and say in one line that it does
not bear on the question. Do not skip the read entirely: a one-line opinion
with no file behind it is worth nothing to the reporter."""
    + LOOP_GUARD,
    tools=[list_repo_files, read_repo_file],
    output_key="dependencies",
    retry_config=NODE_RETRY,
)

code_scout = LlmAgent(
    model=MODEL,
    name="code_scout",
    description="Finds and reads the source that answers the question.",
    instruction="""Find the source code that answers the question.

Search for the symbols or phrases from the question with search_repo_code,
then read only the files the search points at. Quote the exact path of every
file you open. Always run at least one search before concluding anything. If the
searches genuinely return nothing, say so rather than guessing at paths."""
    + LOOP_GUARD,
    tools=[search_repo_code, read_repo_file],
    output_key="code",
    retry_config=NODE_RETRY,
)

gather = JoinNode(
    name="gather",
    description="Waits for all three scouts before the reporter runs.",
)

reporter = LlmAgent(
    model=MODEL,
    name="reporter",
    retry_config=NODE_RETRY,
    description="Turns the scouts' findings into one short answer.",
    instruction="""Answer the developer's question from the three scout reports below.

Layout:
{structure}

Dependencies:
{dependencies}

Code:
{code}

Lead with the answer itself, then the file paths it rests on. Where the scouts
disagree, prefer whichever one quoted a path. If none of them actually found an
answer, say so plainly instead of filling the gap with plausible detail.""",
)

SCOUTS = (structure_scout, dependency_scout, code_scout)

root_agent = Workflow(
    name="code_agent",
    description="Answers questions about a GitHub repository by reading its code.",
    edges=[
        (START, SCOUTS),
        (SCOUTS, gather, reporter),
    ],
    max_concurrency=MAX_CONCURRENCY,
    # Throttled retries dominate the wall clock on the free tier, so the
    # ceiling is generous; a healthy run finishes in well under a minute.
    timeout=900.0,
)
