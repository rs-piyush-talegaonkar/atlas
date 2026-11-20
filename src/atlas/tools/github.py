"""Read-only GitHub tools exposed to the agent.

Every network call the agent can make lives in this module. Each function
returns a plain JSON-serialisable dict, which is what ADK hands back to the
model, and each docstring is the tool description the model selects on.
"""

from __future__ import annotations

import base64
import os

import httpx

API_BASE = "https://api.github.com"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_CHARS = 20_000


def _repo() -> str:
    repo = os.environ.get("GITHUB_REPO")
    if not repo:
        raise RuntimeError("GITHUB_REPO is not set. Copy .env.example to .env.")
    return repo


def _client() -> httpx.AsyncClient:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    return httpx.AsyncClient(base_url=API_BASE, headers=headers, timeout=TIMEOUT)


async def list_repo_files(subdirectory: str = "") -> dict:
    """List the files and directories at a path in the configured repository.

    Use this to discover what exists before reading anything. Pass an empty
    subdirectory to see the repository root.

    Args:
        subdirectory: Path inside the repository, such as "src/atlas". Use an
            empty string for the repository root.

    Returns:
        A dict with "repo", "path" and "entries". Each entry carries "name",
        "path", "type" (either "file" or "dir") and "size" in bytes.
    """
    repo = _repo()
    async with _client() as client:
        response = await client.get("/repos/" + repo + "/contents/" + subdirectory.strip("/"))
        if response.status_code == 404:
            return {"repo": repo, "path": subdirectory, "error": "path not found"}
        response.raise_for_status()
        payload = response.json()
    if isinstance(payload, dict):
        return {
            "repo": repo,
            "path": subdirectory,
            "error": "that path is a file; use read_repo_file",
        }
    entries = [
        {"name": e["name"], "path": e["path"], "type": e["type"], "size": e.get("size", 0)}
        for e in payload
    ]
    return {"repo": repo, "path": subdirectory or "/", "entries": entries}


async def read_repo_file(path: str) -> dict:
    """Read the text of one file from the configured repository.

    Args:
        path: Full path to the file inside the repository, such as
            "src/atlas/schemas/document.py".

    Returns:
        A dict with "repo", "path", "text" and "truncated". Files longer than
        20000 characters are cut short, and "truncated" is then true.
    """
    repo = _repo()
    async with _client() as client:
        response = await client.get("/repos/" + repo + "/contents/" + path.strip("/"))
        if response.status_code == 404:
            return {"repo": repo, "path": path, "error": "file not found"}
        response.raise_for_status()
        payload = response.json()
    if isinstance(payload, list):
        return {
            "repo": repo,
            "path": path,
            "error": "that path is a directory; use list_repo_files",
        }
    if payload.get("encoding") != "base64":
        return {"repo": repo, "path": path, "error": "unsupported content encoding"}
    raw = base64.b64decode(payload["content"])
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"repo": repo, "path": path, "error": "file is not utf-8 text"}
    return {
        "repo": repo,
        "path": path,
        "text": text[:MAX_CHARS],
        "truncated": len(text) > MAX_CHARS,
    }


async def search_repo_code(query: str) -> dict:
    """Search for code inside the configured repository.

    Use this when you need to find where something is defined or used and do
    not already know the file path.

    Args:
        query: Text or symbol to look for, such as "class Document".

    Returns:
        A dict with "repo", "query", "total" and "matches". Each match carries
        "path" and "url". At most 20 matches are returned.
    """
    repo = _repo()
    async with _client() as client:
        response = await client.get(
            "/search/code", params={"q": query + " repo:" + repo, "per_page": 20}
        )
        if response.status_code == 403:
            return {"repo": repo, "query": query, "error": "search rate limit reached"}
        response.raise_for_status()
        payload = response.json()
    matches = [{"path": i["path"], "url": i["html_url"]} for i in payload.get("items", [])]
    return {
        "repo": repo,
        "query": query,
        "total": payload.get("total_count", 0),
        "matches": matches,
    }
